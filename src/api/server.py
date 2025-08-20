"""Main API server coordinating WebSocket and TCP servers.

This module implements the core API server that handles client connections
via WebSocket and TCP protocols, managing the JSON-RPC API for MUD integration.
"""

import asyncio
import json
import logging
import signal
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Set

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_ws import WebSocketResponse

from src.api.protocol import JSONRPCProtocol, JSONRPCRequest, JSONRPCError
from src.api.session import Session, SessionManager
from src.api.tcp_server import TCPServer
from src.api.events import event_dispatcher
from src.api.event_bridge import event_bridge
from src.api.subscriptions import subscription_manager
from src.api.queue import message_queue_manager
from src.config.models import APIConfig
from src.utils.logging import get_logger
from src.utils.shutdown import ShutdownManager

logger = get_logger(__name__)


class APIServer:
    """Main API server coordinating WebSocket and TCP servers."""

    def __init__(self, config: APIConfig, gateway=None):
        """Initialize API server.
        
        Args:
            config: API configuration
            gateway: Gateway instance for I3 network communication
        """
        self.config = config
        self.gateway = gateway
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
        # Protocol and session management
        self.protocol = JSONRPCProtocol()
        self.session_manager = SessionManager(config)
        
        # TCP server
        self.tcp_server = TCPServer(config, self.session_manager) if config.tcp and config.tcp.enabled else None
        
        # Active WebSocket connections
        self._websockets: Set[WebSocketResponse] = set()
        
        # Shutdown management
        self.shutdown_manager = ShutdownManager()
        self._shutdown_event = asyncio.Event()
        
        logger.info("API server initialized", extra={
            "host": config.host,
            "port": config.port,
            "websocket_enabled": config.websocket.enabled if config.websocket else False,
            "tcp_enabled": config.tcp.enabled if config.tcp else False
        })

    async def start(self):
        """Start both WebSocket and TCP servers."""
        try:
            # Start event system components
            await event_dispatcher.start()
            await message_queue_manager.start()
            event_bridge.start()
            
            logger.info("Event system components started")
            
            # Create web application
            self.app = web.Application()
            
            # Setup routes
            self._setup_routes()
            
            # Setup middleware
            self._setup_middleware()
            
            # Create and start runner
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            # Start HTTP/WebSocket server
            self.site = web.TCPSite(
                self.runner,
                self.config.host,
                self.config.port
            )
            await self.site.start()
            
            logger.info(
                "API server started",
                extra={
                    "host": self.config.host,
                    "port": self.config.port,
                    "url": f"http://{self.config.host}:{self.config.port}"
                }
            )
            
            # Start TCP server if enabled
            if self.tcp_server:
                await self.tcp_server.start()
                logger.info(f"TCP server started on port {self.config.tcp.port}")
            
            # Start background tasks
            asyncio.create_task(self._cleanup_sessions())
            asyncio.create_task(self._ping_websockets())
            asyncio.create_task(self._process_event_queues())
            
        except Exception as e:
            logger.error(f"Failed to start API server: {e}")
            raise

    async def stop(self):
        """Stop the API server gracefully."""
        logger.info("Stopping API server...")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Close all WebSocket connections
        for ws in list(self._websockets):
            await ws.close(code=1001, message=b"Server shutting down")
        
        # Stop TCP server
        if self.tcp_server:
            await self.tcp_server.stop()
        
        # Stop the site
        if self.site:
            await self.site.stop()
        
        # Cleanup runner
        if self.runner:
            await self.runner.cleanup()
        
        # Cleanup sessions
        await self.session_manager.cleanup()
        
        # Stop event system components
        event_bridge.stop()
        await event_dispatcher.stop()
        await message_queue_manager.stop()
        
        logger.info("API server stopped")

    def _setup_routes(self):
        """Setup HTTP and WebSocket routes."""
        # WebSocket endpoint
        if self.config.websocket and self.config.websocket.enabled:
            self.app.router.add_get("/ws", self.handle_websocket)
        
        # Health check endpoints
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/health/live", self.handle_liveness)
        self.app.router.add_get("/health/ready", self.handle_readiness)
        
        # Metrics endpoint
        self.app.router.add_get("/metrics", self.handle_metrics)
        
        # API info endpoint
        self.app.router.add_get("/api/info", self.handle_api_info)

    def _setup_middleware(self):
        """Setup middleware for request processing."""
        @web.middleware
        async def error_middleware(request, handler):
            try:
                return await handler(request)
            except web.HTTPException:
                raise
            except Exception as e:
                logger.error(f"Unhandled error in request handler: {e}")
                return web.json_response(
                    {"error": "Internal server error"},
                    status=500
                )
        
        self.app.middlewares.append(error_middleware)

    async def handle_websocket(self, request: Request) -> WebSocketResponse:
        """Handle WebSocket connection.
        
        Args:
            request: HTTP request that initiated the WebSocket
            
        Returns:
            WebSocket response
        """
        ws = WebSocketResponse()
        await ws.prepare(request)
        
        # Add to active connections
        self._websockets.add(ws)
        
        # Create session
        session = None
        
        try:
            # Get authentication from headers or first message
            api_key = request.headers.get("X-API-Key")
            
            if api_key:
                # Authenticate immediately if API key in headers
                session = await self.session_manager.authenticate(api_key)
                session.websocket = ws
                
                # Register session with event dispatcher
                event_dispatcher.register_session(session)
                
                logger.info(f"WebSocket authenticated for {session.mud_name}")
            
            # Process messages
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        # Parse message
                        data = json.loads(msg.data)
                        
                        # Handle authentication if not yet authenticated
                        if not session and data.get("method") == "authenticate":
                            api_key = data.get("params", {}).get("api_key")
                            if api_key:
                                session = await self.session_manager.authenticate(api_key)
                                session.websocket = ws
                                
                                # Register session with event dispatcher
                                event_dispatcher.register_session(session)
                                
                                # Send success response
                                response = self.protocol.format_response(
                                    data.get("id"),
                                    {"status": "authenticated", "mud_name": session.mud_name}
                                )
                                await ws.send_str(response)
                                logger.info(f"WebSocket authenticated for {session.mud_name}")
                            else:
                                # Send error response
                                response = self.protocol.format_error(
                                    data.get("id"),
                                    JSONRPCError.INVALID_PARAMS,
                                    "Missing api_key parameter"
                                )
                                await ws.send_str(response)
                        elif session:
                            # Process authenticated request
                            await self.process_message(session, msg.data)
                        else:
                            # Not authenticated
                            response = self.protocol.format_error(
                                data.get("id"),
                                JSONRPCError.INVALID_REQUEST,
                                "Not authenticated. Please authenticate first."
                            )
                            await ws.send_str(response)
                            
                    except json.JSONDecodeError:
                        response = self.protocol.format_error(
                            None,
                            JSONRPCError.PARSE_ERROR,
                            "Invalid JSON"
                        )
                        await ws.send_str(response)
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        response = self.protocol.format_error(
                            None,
                            JSONRPCError.INTERNAL_ERROR,
                            str(e)
                        )
                        await ws.send_str(response)
                        
                elif msg.type == web.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    
        finally:
            # Cleanup
            self._websockets.discard(ws)
            if session:
                # Unregister from event dispatcher
                event_dispatcher.unregister_session(session.session_id)
                subscription_manager.cleanup_session(session.session_id)
                
                session.websocket = None
                await self.session_manager.disconnect(session)
            
        return ws

    async def process_message(self, session: Session, message: str):
        """Process incoming JSON-RPC message.
        
        Args:
            session: Client session
            message: Raw JSON message
        """
        try:
            # Parse request
            request = self.protocol.parse_request(message)
            
            # Update session activity
            session.update_activity()
            
            # Check rate limits
            if not await session.check_rate_limit(request.method):
                response = self.protocol.format_error(
                    request.id,
                    JSONRPCError.INVALID_REQUEST,
                    "Rate limit exceeded"
                )
                await session.send(response)
                return
            
            # Route to appropriate handler
            handler = self._get_handler(request.method)
            if not handler:
                response = self.protocol.format_error(
                    request.id,
                    JSONRPCError.METHOD_NOT_FOUND,
                    f"Unknown method: {request.method}"
                )
                await session.send(response)
                return
            
            # Execute handler
            result = await handler(session, request.params)
            
            # Send response
            response = self.protocol.format_response(request.id, result)
            await session.send(response)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            response = self.protocol.format_error(
                None,
                JSONRPCError.INTERNAL_ERROR,
                str(e)
            )
            await session.send(response)

    def _get_handler(self, method: str):
        """Get handler for a method.
        
        Args:
            method: JSON-RPC method name
            
        Returns:
            Handler function or None
        """
        # This will be populated with actual handlers in the next step
        # For now, return a placeholder
        handlers = {
            "ping": self._handle_ping,
            "status": self._handle_status,
        }
        return handlers.get(method)

    async def _handle_ping(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request."""
        return {"pong": True, "timestamp": asyncio.get_event_loop().time()}

    async def _handle_status(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle status request."""
        return {
            "connected": True,
            "mud_name": session.mud_name,
            "session_id": session.session_id,
            "uptime": asyncio.get_event_loop().time() - session.connected_at.timestamp()
        }

    async def _start_tcp_server(self):
        """Start TCP socket server for legacy support."""
        # This will be implemented in the TCP server module
        logger.info("TCP server support will be implemented in tcp_server.py")

    async def _cleanup_sessions(self):
        """Background task to cleanup expired sessions."""
        while not self._shutdown_event.is_set():
            try:
                await self.session_manager.cleanup_expired()
                await asyncio.sleep(60)  # Cleanup every minute
            except Exception as e:
                logger.error(f"Error in session cleanup: {e}")

    async def _ping_websockets(self):
        """Background task to ping WebSocket connections."""
        if not self.config.websocket or not self.config.websocket.ping_interval:
            return
        
        ping_interval = self.config.websocket.ping_interval
        
        while not self._shutdown_event.is_set():
            try:
                for ws in list(self._websockets):
                    try:
                        await ws.ping()
                    except:
                        self._websockets.discard(ws)
                
                await asyncio.sleep(ping_interval)
            except Exception as e:
                logger.error(f"Error in WebSocket ping: {e}")
    
    async def _process_event_queues(self):
        """Process queued messages for sessions."""
        while not self._shutdown_event.is_set():
            try:
                # Process message queues for all active sessions
                for session in self.session_manager.get_all_sessions():
                    if session.is_connected() and session.message_queue:
                        await session.flush_queue()
                
                # Small delay to prevent busy loop
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error processing event queues: {e}")

    async def handle_health(self, request: Request) -> web.Response:
        """Handle health check request."""
        return web.json_response({
            "status": "healthy",
            "service": "i3-gateway-api",
            "websocket_connections": len(self._websockets),
            "active_sessions": self.session_manager.get_active_count()
        })

    async def handle_liveness(self, request: Request) -> web.Response:
        """Handle liveness probe."""
        return web.json_response({"status": "alive"})

    async def handle_readiness(self, request: Request) -> web.Response:
        """Handle readiness probe."""
        ready = self.gateway and self.gateway.is_connected() if self.gateway else True
        status_code = 200 if ready else 503
        return web.json_response(
            {"status": "ready" if ready else "not_ready"},
            status=status_code
        )

    async def handle_metrics(self, request: Request) -> web.Response:
        """Handle metrics request."""
        metrics = [
            "# HELP api_websocket_connections Active WebSocket connections",
            "# TYPE api_websocket_connections gauge",
            f"api_websocket_connections {len(self._websockets)}",
            "",
            "# HELP api_active_sessions Active API sessions",
            "# TYPE api_active_sessions gauge",
            f"api_active_sessions {self.session_manager.get_active_count()}",
        ]
        return web.Response(text="\n".join(metrics), content_type="text/plain")

    async def handle_api_info(self, request: Request) -> web.Response:
        """Handle API info request."""
        return web.json_response({
            "version": "1.0.0",
            "protocol": "JSON-RPC 2.0",
            "transports": ["websocket", "tcp"] if self.config.tcp and self.config.tcp.enabled else ["websocket"],
            "authentication": "api_key",
            "documentation": "/api/docs"
        })