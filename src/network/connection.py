"""Connection management for Intermud-3 Gateway.

This module handles TCP connections to I3 routers with automatic
reconnection, keepalive, and failover support.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .mudmode import MudModeError, MudModeStreamProtocol


class ConnectionState(Enum):
    """Connection state enumeration."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    READY = "ready"
    ERROR = "error"
    CLOSING = "closing"


@dataclass
class RouterInfo:
    """Information about an I3 router."""

    name: str
    address: str
    port: int
    priority: int = 0  # Lower is higher priority
    last_attempt: float = 0
    last_success: float = 0
    failure_count: int = 0

    @property
    def backoff_time(self) -> float:
        """Calculate exponential backoff time based on failure count."""
        # Cap at 5 minutes
        max_backoff = 300
        base_backoff = 5

        if self.failure_count == 0:
            return 0

        backoff = min(base_backoff * (2 ** (self.failure_count - 1)), max_backoff)
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, backoff * 0.1)
        return backoff + jitter

    def can_attempt(self) -> bool:
        """Check if enough time has passed for another connection attempt."""
        if self.failure_count == 0:
            return True

        elapsed = time.time() - self.last_attempt
        return elapsed >= self.backoff_time


@dataclass
class ConnectionStats:
    """Connection statistics tracking."""

    packets_sent: int = 0
    packets_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    connection_time: float = 0
    reconnect_count: int = 0
    last_error: str | None = None


class ConnectionManager:
    """Manages connections to I3 routers with failover and reconnection."""

    def __init__(
        self,
        routers: list[RouterInfo],
        on_message: Callable[[Any], Awaitable[None]] | None = None,
        on_state_change: Callable[[ConnectionState], Awaitable[None]] | None = None,
        keepalive_interval: float = 60.0,
        connection_timeout: float = 30.0,
    ):
        """Initialize the connection manager.

        Args:
            routers: List of routers to connect to (in priority order)
            on_message: Callback for received messages
            on_state_change: Callback for connection state changes
            keepalive_interval: Seconds between keepalive messages
            connection_timeout: Seconds to wait for connection
        """
        self.routers = sorted(routers, key=lambda r: r.priority)
        self.on_message = on_message
        self.on_state_change = on_state_change
        self.keepalive_interval = keepalive_interval
        self.connection_timeout = connection_timeout

        self.state = ConnectionState.DISCONNECTED
        self.current_router: RouterInfo | None = None
        self.protocol: MudModeStreamProtocol | None = None
        self.transport: asyncio.Transport | None = None
        self.stats = ConnectionStats()

        self._reconnect_task: asyncio.Task | None = None
        self._keepalive_task: asyncio.Task | None = None
        self._closing = False

    async def connect(self) -> bool:
        """Establish connection to an I3 router.

        Returns:
            True if connection was successful
        """
        if self.state != ConnectionState.DISCONNECTED:
            return False

        await self._set_state(ConnectionState.CONNECTING)

        # Try routers in priority order
        for router in self.routers:
            if not router.can_attempt():
                continue

            router.last_attempt = time.time()

            try:
                # Create protocol instance
                self.protocol = MudModeStreamProtocol(
                    on_message=self._handle_message, on_connection_lost=self._handle_connection_lost
                )

                # Attempt connection
                loop = asyncio.get_event_loop()
                self.transport, _ = await asyncio.wait_for(
                    loop.create_connection(lambda: self.protocol, router.address, router.port),
                    timeout=self.connection_timeout,
                )

                # Connection successful
                router.last_success = time.time()
                router.failure_count = 0
                self.current_router = router
                self.stats.connection_time = time.time()

                await self._set_state(ConnectionState.CONNECTED)

                # Start keepalive
                self._start_keepalive()

                return True

            except (TimeoutError, OSError, ConnectionError) as e:
                router.failure_count += 1
                self.stats.last_error = str(e)
                continue

        # All routers failed
        await self._set_state(ConnectionState.ERROR)

        # Schedule reconnection
        if not self._closing:
            self._schedule_reconnect()

        return False

    async def disconnect(self):
        """Disconnect from the current router."""
        self._closing = True

        # Cancel tasks
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        if self._keepalive_task:
            self._keepalive_task.cancel()
            self._keepalive_task = None

        # Close connection
        if self.protocol:
            await self._set_state(ConnectionState.CLOSING)
            self.protocol.close()
            self.protocol = None
            self.transport = None

        await self._set_state(ConnectionState.DISCONNECTED)
        self._closing = False

    async def send_message(self, data: Any) -> bool:
        """Send a message through the current connection.

        Args:
            data: Data to send

        Returns:
            True if message was sent successfully
        """
        if self.state not in (ConnectionState.CONNECTED, ConnectionState.READY):
            return False

        if not self.protocol:
            return False

        try:
            self.protocol.send_message(data)
            self.stats.packets_sent += 1
            return True
        except MudModeError:
            return False

    async def send_packet(self, packet: Any) -> bool:
        """Send an I3 packet through the current connection.

        Args:
            packet: I3 packet to send

        Returns:
            True if packet was sent successfully
        """
        if self.state not in (ConnectionState.CONNECTED, ConnectionState.READY):
            return False

        if not self.protocol:
            return False

        try:
            self.protocol.send_packet(packet)
            self.stats.packets_sent += 1
            return True
        except MudModeError:
            return False

    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self.state in (ConnectionState.CONNECTED, ConnectionState.READY)

    def get_current_router(self) -> RouterInfo | None:
        """Get information about the current router."""
        return self.current_router

    def get_stats(self) -> ConnectionStats:
        """Get connection statistics."""
        return self.stats

    async def _set_state(self, state: ConnectionState):
        """Update connection state and notify callback."""
        self.state = state

        if self.on_state_change:
            await self.on_state_change(state)

    async def _handle_message(self, message: Any):
        """Handle received message from protocol."""
        self.stats.packets_received += 1

        if self.on_message:
            await self.on_message(message)

    async def _handle_connection_lost(self):
        """Handle connection loss from protocol."""
        if self._closing:
            return

        await self._set_state(ConnectionState.DISCONNECTED)

        # Mark router as failed
        if self.current_router:
            self.current_router.failure_count += 1

        self.current_router = None
        self.protocol = None
        self.transport = None

        # Schedule reconnection
        self._schedule_reconnect()

    def _schedule_reconnect(self):
        """Schedule automatic reconnection."""
        if self._reconnect_task:
            return

        self.stats.reconnect_count += 1

        async def reconnect():
            # Wait for shortest backoff among routers
            min_backoff = min(r.backoff_time for r in self.routers)
            if min_backoff > 0:
                await asyncio.sleep(min_backoff)

            if not self._closing:
                await self.connect()

        self._reconnect_task = asyncio.create_task(reconnect())

    def _start_keepalive(self):
        """Start keepalive task."""
        if self._keepalive_task:
            self._keepalive_task.cancel()

        async def keepalive():
            while self.is_connected() and not self._closing:
                await asyncio.sleep(self.keepalive_interval)

                if self.is_connected() and self.state == ConnectionState.READY:
                    # Send a ping packet as keepalive
                    # I3 doesn't have an explicit ping, so we can send a who-req to ourselves
                    # or just track the connection time
                    # The router will close idle connections, so any packet will keep it alive
                    pass

        self._keepalive_task = asyncio.create_task(keepalive())


class ConnectionPool:
    """Manages multiple connections for load balancing and redundancy."""

    def __init__(self, max_connections: int = 3):
        """Initialize the connection pool.

        Args:
            max_connections: Maximum number of concurrent connections
        """
        self.max_connections = max_connections
        self.connections: list[ConnectionManager] = []
        self._current_index = 0

    async def add_connection(self, manager: ConnectionManager) -> bool:
        """Add a connection manager to the pool.

        Args:
            manager: Connection manager to add

        Returns:
            True if added successfully
        """
        if len(self.connections) >= self.max_connections:
            return False

        self.connections.append(manager)

        # Start connection
        await manager.connect()
        return True

    async def remove_connection(self, manager: ConnectionManager):
        """Remove a connection manager from the pool.

        Args:
            manager: Connection manager to remove
        """
        if manager in self.connections:
            await manager.disconnect()
            self.connections.remove(manager)

    def get_connection(self) -> ConnectionManager | None:
        """Get next available connection (round-robin).

        Returns:
            Available connection manager or None
        """
        if not self.connections:
            return None

        # Find next connected manager
        for _ in range(len(self.connections)):
            manager = self.connections[self._current_index]
            self._current_index = (self._current_index + 1) % len(self.connections)

            if manager.is_connected():
                return manager

        return None

    async def broadcast(self, data: Any) -> int:
        """Send data to all connected managers.

        Args:
            data: Data to broadcast

        Returns:
            Number of successful sends
        """
        count = 0
        for manager in self.connections:
            if await manager.send_message(data):
                count += 1

        return count

    async def close_all(self):
        """Close all connections in the pool."""
        tasks = [manager.disconnect() for manager in self.connections]
        await asyncio.gather(*tasks)
        self.connections.clear()
