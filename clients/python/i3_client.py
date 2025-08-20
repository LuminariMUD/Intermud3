#!/usr/bin/env python3
"""
Intermud3 Gateway Client Library for Python

A Python client library for connecting to the Intermud3 Gateway API.
Provides both synchronous and asynchronous interfaces for MUD integration.
"""

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
from urllib.parse import urlparse

import aiohttp
from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


class RPCError(Exception):
    """JSON-RPC error exception."""
    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"RPC Error {code}: {message}")


@dataclass
class I3Config:
    """Client configuration."""
    url: str
    api_key: str  # Provided by user at runtime
    mud_name: str
    auto_reconnect: bool = True
    reconnect_interval: float = 5.0
    max_reconnect_attempts: int = 10
    ping_interval: float = 30.0
    ping_timeout: float = 10.0
    queue_size: int = 1000
    request_timeout: float = 30.0
    ssl_verify: bool = True


@dataclass
class PendingRequest:
    """Pending RPC request tracking."""
    id: str
    method: str
    params: Dict[str, Any]
    future: asyncio.Future
    timestamp: float = field(default_factory=time.time)


class I3Client:
    """
    Intermud3 Gateway API Client
    
    Example usage:
        async def main():
            # API credentials should be loaded from environment or config
            client = I3Client(
                url="ws://localhost:8080",
                api_key=os.environ['I3_API_KEY'],  # Load from environment
                mud_name="YourMUD"
            )
            
            # Register event handlers
            client.on("tell_received", handle_tell)
            client.on("channel_message", handle_channel_message)
            
            # Connect to gateway
            await client.connect()
            
            # Send a tell
            await client.tell("OtherMUD", "PlayerName", "Hello!")
            
            # Join a channel
            await client.channel_join("chat")
            
            # Send channel message
            await client.channel_send("chat", "Hello everyone!")
            
            # Keep running
            await client.wait_closed()
    """
    
    def __init__(
        self,
        url: str,
        api_key: str,  # Provided at runtime
        mud_name: str,
        **kwargs
    ):
        """
        Initialize I3 client.
        
        Args:
            url: Gateway WebSocket URL (ws:// or wss://)
            api_key: API authentication credential (load from secure source)
            mud_name: Your MUD's name
            **kwargs: Additional configuration options
        """
        self.config = I3Config(
            url=url,
            api_key=api_key,
            mud_name=mud_name,
            **kwargs
        )
        
        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self.session: Optional[ClientSession] = None
        self.websocket: Optional[ClientWebSocketResponse] = None
        self.reconnect_attempts = 0
        
        # Request tracking
        self.pending_requests: Dict[str, PendingRequest] = {}
        self.request_counter = 0
        
        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Subscriptions
        self.subscribed_channels: Set[str] = set()
        
        # Tasks
        self.tasks: List[asyncio.Task] = []
        self._closing = False
        
        # Statistics
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "events_received": 0,
            "errors": 0,
            "reconnects": 0,
            "connected_at": None,
            "last_activity": None
        }
    
    async def connect(self) -> None:
        """Connect to the I3 Gateway."""
        if self.state != ConnectionState.DISCONNECTED:
            raise RuntimeError(f"Cannot connect in state {self.state}")
        
        self.state = ConnectionState.CONNECTING
        self._closing = False
        
        try:
            # Create session
            self.session = ClientSession()
            
            # Parse URL and prepare headers
            headers = {
                "X-API-Key": self.config.api_key,
                "X-MUD-Name": self.config.mud_name
            }
            
            # Connect WebSocket
            self.websocket = await self.session.ws_connect(
                self.config.url,
                headers=headers,
                ssl=self.config.ssl_verify if self.config.url.startswith("wss") else None
            )
            
            self.state = ConnectionState.CONNECTED
            self.reconnect_attempts = 0
            self.stats["connected_at"] = datetime.utcnow().isoformat()
            
            # Start background tasks
            self.tasks = [
                asyncio.create_task(self._receive_loop()),
                asyncio.create_task(self._ping_loop())
            ]
            
            # Trigger connected event
            await self._trigger_event("connected", {})
            
            logger.info(f"Connected to I3 Gateway at {self.config.url}")
            
        except Exception as e:
            self.state = ConnectionState.DISCONNECTED
            if self.session:
                await self.session.close()
                self.session = None
            raise ConnectionError(f"Failed to connect: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect from the I3 Gateway."""
        self._closing = True
        self.state = ConnectionState.CLOSED
        
        # Cancel tasks
        for task in self.tasks:
            task.cancel()
        
        # Close WebSocket
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        # Close session
        if self.session:
            await self.session.close()
            self.session = None
        
        # Trigger disconnected event
        await self._trigger_event("disconnected", {})
        
        logger.info("Disconnected from I3 Gateway")
    
    async def _receive_loop(self) -> None:
        """Receive and process messages from gateway."""
        while not self._closing and self.websocket:
            try:
                msg = await self.websocket.receive()
                
                if msg.type == WSMsgType.TEXT:
                    await self._handle_message(msg.data)
                    
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self.websocket.exception()}")
                    self.stats["errors"] += 1
                    
                elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED):
                    logger.info("WebSocket closed by server")
                    break
                    
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                self.stats["errors"] += 1
                break
        
        # Handle reconnection
        if self.config.auto_reconnect and not self._closing:
            await self._reconnect()
    
    async def _ping_loop(self) -> None:
        """Send periodic ping messages."""
        while not self._closing and self.websocket:
            try:
                await asyncio.sleep(self.config.ping_interval)
                
                if self.websocket:
                    await self.send_request("ping", {})
                    
            except Exception as e:
                logger.error(f"Error in ping loop: {e}")
    
    async def _reconnect(self) -> None:
        """Attempt to reconnect to gateway."""
        if self.reconnect_attempts >= self.config.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            await self.disconnect()
            return
        
        self.state = ConnectionState.RECONNECTING
        self.reconnect_attempts += 1
        self.stats["reconnects"] += 1
        
        logger.info(f"Reconnecting (attempt {self.reconnect_attempts}/{self.config.max_reconnect_attempts})")
        
        # Clean up current connection
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        # Wait before reconnecting
        await asyncio.sleep(self.config.reconnect_interval * self.reconnect_attempts)
        
        try:
            # Reconnect
            self.state = ConnectionState.DISCONNECTED
            await self.connect()
            
            # Restore subscriptions
            for channel in self.subscribed_channels:
                await self.channel_join(channel)
                
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            await self._reconnect()
    
    async def _handle_message(self, data: str) -> None:
        """Handle incoming message from gateway."""
        try:
            message = json.loads(data)
            self.stats["messages_received"] += 1
            self.stats["last_activity"] = datetime.utcnow().isoformat()
            
            # Check if it's a response or event
            if "id" in message:
                # Response to our request
                await self._handle_response(message)
            else:
                # Event from gateway
                await self._handle_event(message)
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            self.stats["errors"] += 1
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            self.stats["errors"] += 1
    
    async def _handle_response(self, message: Dict[str, Any]) -> None:
        """Handle RPC response."""
        request_id = message.get("id")
        if not request_id or request_id not in self.pending_requests:
            logger.warning(f"Received response for unknown request: {request_id}")
            return
        
        pending = self.pending_requests.pop(request_id)
        
        if "error" in message:
            # Error response
            error = message["error"]
            exc = RPCError(
                error.get("code", -1),
                error.get("message", "Unknown error"),
                error.get("data")
            )
            pending.future.set_exception(exc)
        else:
            # Success response
            pending.future.set_result(message.get("result"))
    
    async def _handle_event(self, message: Dict[str, Any]) -> None:
        """Handle incoming event."""
        method = message.get("method")
        params = message.get("params", {})
        
        if not method:
            logger.warning("Received event without method")
            return
        
        self.stats["events_received"] += 1
        await self._trigger_event(method, params)
    
    async def _trigger_event(self, event: str, data: Dict[str, Any]) -> None:
        """Trigger event handlers."""
        handlers = self.event_handlers.get(event, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Error in event handler for {event}: {e}")
    
    def on(self, event: str, handler: Callable) -> None:
        """
        Register an event handler.
        
        Args:
            event: Event name (e.g., "tell_received", "channel_message")
            handler: Callback function to handle the event
        """
        self.event_handlers[event].append(handler)
    
    def off(self, event: str, handler: Optional[Callable] = None) -> None:
        """
        Remove an event handler.
        
        Args:
            event: Event name
            handler: Specific handler to remove, or None to remove all
        """
        if handler:
            self.event_handlers[event].remove(handler)
        else:
            self.event_handlers[event] = []
    
    async def send_request(
        self,
        method: str,
        params: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> Any:
        """
        Send a JSON-RPC request to the gateway.
        
        Args:
            method: RPC method name
            params: Method parameters
            timeout: Request timeout in seconds
            
        Returns:
            Response result
            
        Raises:
            RPCError: If the request fails
            asyncio.TimeoutError: If the request times out
        """
        if self.state != ConnectionState.CONNECTED:
            raise ConnectionError(f"Not connected (state: {self.state})")
        
        # Generate request ID
        self.request_counter += 1
        request_id = f"{self.config.mud_name}-{self.request_counter}-{uuid.uuid4().hex[:8]}"
        
        # Create request
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        # Track pending request
        future = asyncio.Future()
        self.pending_requests[request_id] = PendingRequest(
            id=request_id,
            method=method,
            params=params,
            future=future
        )
        
        # Send request
        try:
            await self.websocket.send_str(json.dumps(request))
            self.stats["messages_sent"] += 1
            
            # Wait for response
            timeout = timeout or self.config.request_timeout
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise
        except Exception as e:
            self.pending_requests.pop(request_id, None)
            raise
    
    # Communication methods
    
    async def tell(
        self,
        target_mud: str,
        target_user: str,
        message: str,
        from_user: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a tell to a user on another MUD.
        
        Args:
            target_mud: Target MUD name
            target_user: Target username
            message: Message to send
            from_user: Optional sender name
            
        Returns:
            Response from gateway
        """
        params = {
            "target_mud": target_mud,
            "target_user": target_user,
            "message": message
        }
        if from_user:
            params["from_user"] = from_user
            
        return await self.send_request("tell", params)
    
    async def emoteto(
        self,
        target_mud: str,
        target_user: str,
        message: str,
        from_user: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send an emote to a user on another MUD."""
        params = {
            "target_mud": target_mud,
            "target_user": target_user,
            "message": message
        }
        if from_user:
            params["from_user"] = from_user
            
        return await self.send_request("emoteto", params)
    
    async def channel_send(
        self,
        channel: str,
        message: str,
        from_user: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a message to a channel.
        
        Args:
            channel: Channel name
            message: Message to send
            from_user: Optional sender name
            
        Returns:
            Response from gateway
        """
        params = {
            "channel": channel,
            "message": message
        }
        if from_user:
            params["from_user"] = from_user
            
        return await self.send_request("channel_send", params)
    
    async def channel_emote(
        self,
        channel: str,
        message: str,
        from_user: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send an emote to a channel."""
        params = {
            "channel": channel,
            "message": message
        }
        if from_user:
            params["from_user"] = from_user
            
        return await self.send_request("channel_emote", params)
    
    # Information methods
    
    async def who(
        self,
        target_mud: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of users on a MUD.
        
        Args:
            target_mud: Target MUD name
            filters: Optional filters (min_level, max_level, race, guild)
            
        Returns:
            List of user information
        """
        params = {"target_mud": target_mud}
        if filters:
            params["filters"] = filters
            
        result = await self.send_request("who", params)
        return result.get("users", [])
    
    async def finger(
        self,
        target_mud: str,
        target_user: str
    ) -> Dict[str, Any]:
        """Get detailed information about a user."""
        params = {
            "target_mud": target_mud,
            "target_user": target_user
        }
        return await self.send_request("finger", params)
    
    async def locate(self, target_user: str) -> List[Dict[str, Any]]:
        """
        Locate a user on the network.
        
        Args:
            target_user: Username to search for
            
        Returns:
            List of MUDs where user was found
        """
        result = await self.send_request("locate", {"target_user": target_user})
        return result.get("locations", [])
    
    async def mudlist(
        self,
        refresh: bool = False,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of MUDs on the network.
        
        Args:
            refresh: Force refresh from router
            filter: Optional filters (status, driver, has_service)
            
        Returns:
            List of MUD information
        """
        params = {"refresh": refresh}
        if filter:
            params["filter"] = filter
            
        result = await self.send_request("mudlist", params)
        return result.get("muds", [])
    
    # Channel management
    
    async def channel_join(
        self,
        channel: str,
        listen_only: bool = False
    ) -> Dict[str, Any]:
        """
        Join a channel.
        
        Args:
            channel: Channel name
            listen_only: If True, can only receive messages
            
        Returns:
            Response from gateway
        """
        params = {
            "channel": channel,
            "listen_only": listen_only
        }
        result = await self.send_request("channel_join", params)
        self.subscribed_channels.add(channel)
        return result
    
    async def channel_leave(self, channel: str) -> Dict[str, Any]:
        """
        Leave a channel.
        
        Args:
            channel: Channel name
            
        Returns:
            Response from gateway
        """
        result = await self.send_request("channel_leave", {"channel": channel})
        self.subscribed_channels.discard(channel)
        return result
    
    async def channel_list(self) -> List[str]:
        """
        Get list of available channels.
        
        Returns:
            List of channel names
        """
        result = await self.send_request("channel_list", {})
        return result.get("channels", [])
    
    async def channel_who(self, channel: str) -> List[Dict[str, Any]]:
        """
        Get list of users on a channel.
        
        Args:
            channel: Channel name
            
        Returns:
            List of users on the channel
        """
        result = await self.send_request("channel_who", {"channel": channel})
        return result.get("users", [])
    
    async def channel_history(
        self,
        channel: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get channel message history.
        
        Args:
            channel: Channel name
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of historical messages
        """
        params = {
            "channel": channel,
            "limit": limit
        }
        result = await self.send_request("channel_history", params)
        return result.get("messages", [])
    
    # Administrative methods
    
    async def status(self) -> Dict[str, Any]:
        """
        Get gateway connection status.
        
        Returns:
            Status information
        """
        return await self.send_request("status", {})
    
    async def stats(self) -> Dict[str, Any]:
        """
        Get gateway statistics.
        
        Returns:
            Statistics information
        """
        return await self.send_request("stats", {})
    
    async def ping(self) -> float:
        """
        Ping the gateway.
        
        Returns:
            Round-trip time in milliseconds
        """
        start = time.time()
        await self.send_request("ping", {})
        return (time.time() - start) * 1000
    
    async def reconnect_router(self) -> Dict[str, Any]:
        """Force gateway to reconnect to I3 router."""
        return await self.send_request("reconnect", {})
    
    # Utility methods
    
    async def wait_closed(self) -> None:
        """Wait until the connection is closed."""
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
    
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self.state == ConnectionState.CONNECTED
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return self.stats.copy()
    
    def get_subscribed_channels(self) -> Set[str]:
        """Get list of subscribed channels."""
        return self.subscribed_channels.copy()


# Convenience function for quick setup
def create_client(url: str, api_key: str, mud_name: str, **kwargs) -> I3Client:
    """
    Create an I3 client instance.
    
    Args:
        url: Gateway WebSocket URL
        api_key: API authentication credential (load from secure source)
        mud_name: Your MUD's name
        **kwargs: Additional configuration options
        
    Returns:
        Configured I3Client instance
    """
    return I3Client(url, api_key, mud_name, **kwargs)


# Synchronous wrapper for compatibility
class SyncI3Client:
    """
    Synchronous wrapper for I3Client.
    
    This class provides a synchronous interface for MUDs that don't use asyncio.
    """
    
    def __init__(self, url: str, api_key: str, mud_name: str, **kwargs):
        self.client = I3Client(url, api_key, mud_name, **kwargs)
        self.loop = asyncio.new_event_loop()
        self.thread = None
    
    def connect(self) -> None:
        """Connect to the gateway."""
        self.loop.run_until_complete(self.client.connect())
    
    def disconnect(self) -> None:
        """Disconnect from the gateway."""
        self.loop.run_until_complete(self.client.disconnect())
    
    def tell(self, target_mud: str, target_user: str, message: str, from_user: Optional[str] = None) -> Dict[str, Any]:
        """Send a tell."""
        return self.loop.run_until_complete(
            self.client.tell(target_mud, target_user, message, from_user)
        )
    
    def channel_send(self, channel: str, message: str, from_user: Optional[str] = None) -> Dict[str, Any]:
        """Send a channel message."""
        return self.loop.run_until_complete(
            self.client.channel_send(channel, message, from_user)
        )
    
    def who(self, target_mud: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get who list."""
        return self.loop.run_until_complete(
            self.client.who(target_mud, filters)
        )
    
    def mudlist(self, refresh: bool = False, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get MUD list."""
        return self.loop.run_until_complete(
            self.client.mudlist(refresh, filter)
        )
    
    def on(self, event: str, handler: Callable) -> None:
        """Register event handler."""
        self.client.on(event, handler)
    
    def off(self, event: str, handler: Optional[Callable] = None) -> None:
        """Remove event handler."""
        self.client.off(event, handler)