"""TCP socket server for legacy MUD support.

This module provides a TCP-based JSON-RPC interface for MUDs that cannot
use WebSocket connections.
"""

import asyncio
import json
import logging
from typing import Dict, Optional, Set

from src.api.protocol import JSONRPCProtocol, JSONRPCError
from src.api.session import Session, SessionManager
from src.config.models import APIConfig
from src.utils.logging import get_logger

logger = get_logger(__name__)


class TCPConnection:
    """Represents a TCP client connection."""
    
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        session_manager: SessionManager,
        protocol: JSONRPCProtocol
    ):
        """Initialize TCP connection.
        
        Args:
            reader: Async stream reader
            writer: Async stream writer  
            session_manager: Session manager
            protocol: JSON-RPC protocol handler
        """
        self.reader = reader
        self.writer = writer
        self.session_manager = session_manager
        self.protocol = protocol
        self.session: Optional[Session] = None
        self.buffer = ""
        self.closed = False
        
        # Get connection info
        peername = writer.get_extra_info('peername')
        self.remote_address = f"{peername[0]}:{peername[1]}" if peername else "unknown"
        
        logger.info(f"New TCP connection from {self.remote_address}")
    
    async def handle(self):
        """Handle the TCP connection."""
        try:
            # Send welcome message
            welcome = {
                "jsonrpc": "2.0",
                "method": "welcome",
                "params": {
                    "service": "i3-gateway",
                    "version": "1.0.0",
                    "protocol": "JSON-RPC 2.0",
                    "authentication": "required"
                }
            }
            await self.send_json(welcome)
            
            # Read messages
            while not self.closed:
                try:
                    # Read data with timeout (0 = no timeout)
                    timeout = 3600.0  # 1 hour timeout (was 5 minutes)
                    if timeout > 0:
                        data = await asyncio.wait_for(
                            self.reader.read(4096),
                            timeout=timeout
                        )
                    else:
                        data = await self.reader.read(4096)
                    
                    if not data:
                        # Connection closed
                        break
                    
                    # Log raw data for debugging
                    logger.debug(f"Raw data from {self.remote_address}: {data[:100]}")
                    
                    # Add to buffer
                    self.buffer += data.decode('utf-8', errors='ignore')
                    
                    # Process complete messages (newline delimited)
                    while '\n' in self.buffer:
                        line, self.buffer = self.buffer.split('\n', 1)
                        line = line.strip()
                        
                        if line:
                            await self.process_message(line)
                            
                except asyncio.TimeoutError:
                    logger.info(f"TCP connection from {self.remote_address} timed out")
                    break
                except Exception as e:
                    logger.error(f"Error reading from TCP connection: {e}")
                    break
                    
        finally:
            await self.close()
    
    async def process_message(self, message: str):
        """Process a JSON-RPC message.
        
        Args:
            message: Raw JSON message
        """
        try:
            # Parse message
            data = json.loads(message)
            
            # Handle authentication
            if not self.session and data.get("method") == "authenticate":
                api_key = data.get("params", {}).get("api_key")
                if api_key:
                    try:
                        self.session = await self.session_manager.authenticate(api_key)
                        self.session.tcp_connection = self
                        
                        # Send success response
                        response = self.protocol.format_response(
                            data.get("id"),
                            {
                                "status": "authenticated",
                                "mud_name": self.session.mud_name,
                                "session_id": self.session.session_id
                            }
                        )
                        await self.send_json(json.loads(response))
                        
                        logger.info(
                            f"TCP connection from {self.remote_address} "
                            f"authenticated as {self.session.mud_name}"
                        )
                        
                        # Flush any queued messages
                        if self.session.message_queue:
                            flushed = await self.session.flush_queue()
                            if flushed:
                                logger.info(f"Flushed {flushed} queued messages to {self.session.mud_name}")
                                
                    except ValueError as e:
                        # Authentication failed
                        response = self.protocol.format_error(
                            data.get("id"),
                            JSONRPCError.NOT_AUTHENTICATED,
                            str(e)
                        )
                        await self.send_json(json.loads(response))
                else:
                    # Missing API key
                    response = self.protocol.format_error(
                        data.get("id"),
                        JSONRPCError.INVALID_PARAMS,
                        "Missing api_key parameter"
                    )
                    await self.send_json(json.loads(response))
                    
            elif self.session:
                # Process authenticated request
                request = self.protocol.parse_request(message)
                
                # Update session activity
                self.session.update_activity()
                self.session.metrics.messages_received += 1
                
                # Check rate limits
                if not await self.session.check_rate_limit(request.method):
                    response = self.protocol.format_error(
                        request.id,
                        JSONRPCError.RATE_LIMIT_EXCEEDED,
                        "Rate limit exceeded"
                    )
                    await self.send_json(json.loads(response))
                    return
                
                # This will be handled by the main server
                # For now, just echo back
                response = self.protocol.format_response(
                    request.id,
                    {"echo": request.params}
                )
                await self.send_json(json.loads(response))
                
            else:
                # Not authenticated
                response = self.protocol.format_error(
                    data.get("id"),
                    JSONRPCError.NOT_AUTHENTICATED,
                    "Not authenticated. Please authenticate first."
                )
                await self.send_json(json.loads(response))
                
        except json.JSONDecodeError:
            response = self.protocol.format_error(
                None,
                JSONRPCError.PARSE_ERROR,
                "Invalid JSON"
            )
            await self.send_json(json.loads(response))
        except Exception as e:
            logger.error(f"Error processing TCP message: {e}")
            response = self.protocol.format_error(
                None,
                JSONRPCError.INTERNAL_ERROR,
                str(e)
            )
            await self.send_json(json.loads(response))
    
    async def send_json(self, data: Dict):
        """Send JSON data to client.
        
        Args:
            data: Data to send as JSON
        """
        if self.closed:
            return
        
        try:
            # Convert to JSON and add newline delimiter
            message = json.dumps(data) + "\n"
            self.writer.write(message.encode('utf-8'))
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error sending to TCP client: {e}")
            self.closed = True
    
    async def close(self):
        """Close the connection."""
        if self.closed:
            return
        
        self.closed = True
        
        try:
            # Clean up session
            if self.session:
                self.session.tcp_connection = None
                await self.session_manager.disconnect(self.session)
            
            # Close writer
            self.writer.close()
            await self.writer.wait_closed()
            
        except Exception as e:
            logger.error(f"Error closing TCP connection: {e}")
        
        logger.info(f"TCP connection from {self.remote_address} closed")


class TCPServer:
    """TCP server for JSON-RPC API."""
    
    def __init__(self, config: APIConfig, session_manager: SessionManager):
        """Initialize TCP server.
        
        Args:
            config: API configuration
            session_manager: Session manager
        """
        self.config = config
        self.session_manager = session_manager
        self.protocol = JSONRPCProtocol()
        self.server: Optional[asyncio.Server] = None
        self.connections: Set[TCPConnection] = set()
        self._shutdown = False
        
        logger.info("TCP server initialized")
    
    async def start(self):
        """Start the TCP server."""
        if not self.config.tcp or not self.config.tcp.enabled:
            logger.info("TCP server is disabled")
            return
        
        try:
            self.server = await asyncio.start_server(
                self.handle_client,
                self.config.host,
                self.config.tcp.port
            )
            
            addr = self.server.sockets[0].getsockname()
            logger.info(f"TCP server listening on {addr[0]}:{addr[1]}")
            
            # Start server task
            asyncio.create_task(self.serve())
            
        except Exception as e:
            logger.error(f"Failed to start TCP server: {e}")
            raise
    
    async def serve(self):
        """Serve TCP connections."""
        if not self.server:
            return
        
        async with self.server:
            await self.server.serve_forever()
    
    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Handle a new TCP client connection.
        
        Args:
            reader: Stream reader
            writer: Stream writer
        """
        # Check connection limit
        if len(self.connections) >= self.config.tcp.max_connections:
            logger.warning("TCP connection limit reached, rejecting connection")
            writer.close()
            await writer.wait_closed()
            return
        
        # Create connection handler
        connection = TCPConnection(
            reader,
            writer,
            self.session_manager,
            self.protocol
        )
        
        # Track connection
        self.connections.add(connection)
        
        try:
            # Handle the connection
            await connection.handle()
        finally:
            # Remove from tracked connections
            self.connections.discard(connection)
    
    async def stop(self):
        """Stop the TCP server."""
        logger.info("Stopping TCP server...")
        
        self._shutdown = True
        
        # Close all connections
        for conn in list(self.connections):
            await conn.close()
        
        # Stop the server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        logger.info("TCP server stopped")
    
    def get_connection_count(self) -> int:
        """Get number of active connections.
        
        Returns:
            Number of active TCP connections
        """
        return len(self.connections)
    
    def get_statistics(self) -> Dict:
        """Get TCP server statistics.
        
        Returns:
            Statistics dictionary
        """
        authenticated = sum(
            1 for conn in self.connections
            if conn.session is not None
        )
        
        return {
            "total_connections": len(self.connections),
            "authenticated_connections": authenticated,
            "unauthenticated_connections": len(self.connections) - authenticated,
            "max_connections": self.config.tcp.max_connections if self.config.tcp else 0,
            "port": self.config.tcp.port if self.config.tcp else 0
        }