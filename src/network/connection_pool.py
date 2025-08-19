"""Connection pooling for efficient resource management.

Provides connection pooling with health checks, automatic recycling,
and load balancing for improved performance and reliability.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar


logger = logging.getLogger(__name__)

T = TypeVar("T")


class ConnectionState(Enum):
    """Connection states in the pool."""

    IDLE = "idle"  # Available for use
    IN_USE = "in_use"  # Currently being used
    TESTING = "testing"  # Being health checked
    INVALID = "invalid"  # Failed health check
    CLOSED = "closed"  # Connection closed


@dataclass
class PoolConfig:
    """Configuration for connection pool."""

    min_size: int = 2  # Minimum connections to maintain
    max_size: int = 10  # Maximum connections allowed
    max_idle_time: float = 300.0  # Max idle time before closing (seconds)
    max_lifetime: float = 3600.0  # Max connection lifetime (seconds)
    health_check_interval: float = 60.0  # Health check interval (seconds)
    acquire_timeout: float = 10.0  # Timeout for acquiring connection
    retry_attempts: int = 3  # Retry attempts for failed connections
    enable_stats: bool = True  # Enable statistics collection


@dataclass
class PoolStats:
    """Statistics for connection pool."""

    created_connections: int = 0
    closed_connections: int = 0
    failed_connections: int = 0
    acquired_connections: int = 0
    released_connections: int = 0
    health_checks_passed: int = 0
    health_checks_failed: int = 0
    wait_time_total: float = 0.0
    wait_count: int = 0
    active_connections: int = 0
    idle_connections: int = 0

    def record_acquire(self, wait_time: float):
        """Record connection acquisition."""
        self.acquired_connections += 1
        self.wait_time_total += wait_time
        self.wait_count += 1

    def record_release(self):
        """Record connection release."""
        self.released_connections += 1

    def get_average_wait_time(self) -> float:
        """Get average wait time for connections."""
        if self.wait_count == 0:
            return 0.0
        return self.wait_time_total / self.wait_count

    def get_utilization(self) -> float:
        """Get pool utilization percentage."""
        total = self.active_connections + self.idle_connections
        if total == 0:
            return 0.0
        return self.active_connections / total


@dataclass
class PooledConnection(Generic[T]):
    """Wrapper for pooled connection."""

    connection: T
    pool: "ConnectionPool"
    state: ConnectionState = ConnectionState.IDLE
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    use_count: int = 0
    health_check_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if connection has exceeded lifetime."""
        if self.pool.config.max_lifetime <= 0:
            return False
        age = time.time() - self.created_at
        return age > self.pool.config.max_lifetime

    def is_idle_expired(self) -> bool:
        """Check if connection has been idle too long."""
        if self.pool.config.max_idle_time <= 0:
            return False
        idle_time = time.time() - self.last_used_at
        return idle_time > self.pool.config.max_idle_time

    def needs_health_check(self) -> bool:
        """Check if connection needs health check."""
        if self.pool.config.health_check_interval <= 0:
            return False
        time_since_check = time.time() - self.health_check_at
        return time_since_check > self.pool.config.health_check_interval

    async def close(self):
        """Close the connection."""
        if self.state != ConnectionState.CLOSED:
            self.state = ConnectionState.CLOSED
            if hasattr(self.connection, "close"):
                if asyncio.iscoroutinefunction(self.connection.close):
                    await self.connection.close()
                else:
                    self.connection.close()


class ConnectionPool(Generic[T]):
    """Generic connection pool for managing reusable connections.

    Features:
    - Automatic connection lifecycle management
    - Health checking and validation
    - Statistics and monitoring
    - Graceful degradation under load
    """

    def __init__(
        self,
        create_connection: Callable[[], T],
        config: PoolConfig | None = None,
        validate_connection: Callable[[T], bool] | None = None,
        reset_connection: Callable[[T], None] | None = None,
    ):
        """Initialize connection pool.

        Args:
            create_connection: Factory function to create connections
            config: Pool configuration
            validate_connection: Function to validate connection health
            reset_connection: Function to reset connection state
        """
        self.create_connection = create_connection
        self.config = config or PoolConfig()
        self.validate_connection = validate_connection
        self.reset_connection = reset_connection

        self._pool: list[PooledConnection] = []
        self._semaphore = asyncio.Semaphore(self.config.max_size)
        self._lock = asyncio.Lock()
        self._waiters: list[asyncio.Future] = []
        self._closing = False
        self._stats = PoolStats() if self.config.enable_stats else None

        # Background tasks
        self._maintenance_task: asyncio.Task | None = None

    async def start(self):
        """Start the connection pool."""
        # Create minimum connections
        await self._ensure_min_connections()

        # Start maintenance task
        if not self._maintenance_task:
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())

    async def _ensure_min_connections(self):
        """Ensure minimum connections are available."""
        async with self._lock:
            current_size = len(self._pool)
            needed = self.config.min_size - current_size

            for _ in range(needed):
                try:
                    conn = await self._create_new_connection()
                    if conn:
                        self._pool.append(conn)
                except Exception as e:
                    logger.error(f"Failed to create connection: {e}")

    async def _create_new_connection(self) -> PooledConnection | None:
        """Create a new connection."""
        try:
            if asyncio.iscoroutinefunction(self.create_connection):
                connection = await self.create_connection()
            else:
                connection = self.create_connection()

            pooled = PooledConnection(connection=connection, pool=self)

            if self._stats:
                self._stats.created_connections += 1
                self._stats.idle_connections += 1

            logger.debug(f"Created new connection: {id(connection)}")
            return pooled

        except Exception as e:
            if self._stats:
                self._stats.failed_connections += 1
            logger.error(f"Failed to create connection: {e}")
            return None

    async def _validate_connection(self, pooled: PooledConnection) -> bool:
        """Validate connection health."""
        if not self.validate_connection:
            return True

        try:
            pooled.state = ConnectionState.TESTING

            if asyncio.iscoroutinefunction(self.validate_connection):
                valid = await self.validate_connection(pooled.connection)
            else:
                valid = self.validate_connection(pooled.connection)

            pooled.health_check_at = time.time()

            if valid:
                if self._stats:
                    self._stats.health_checks_passed += 1
                pooled.state = ConnectionState.IDLE
            else:
                if self._stats:
                    self._stats.health_checks_failed += 1
                pooled.state = ConnectionState.INVALID

            return valid

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            if self._stats:
                self._stats.health_checks_failed += 1
            pooled.state = ConnectionState.INVALID
            return False

    async def _reset_connection(self, pooled: PooledConnection):
        """Reset connection state before reuse."""
        if not self.reset_connection:
            return

        try:
            if asyncio.iscoroutinefunction(self.reset_connection):
                await self.reset_connection(pooled.connection)
            else:
                self.reset_connection(pooled.connection)
        except Exception as e:
            logger.error(f"Failed to reset connection: {e}")
            pooled.state = ConnectionState.INVALID

    @asynccontextmanager
    async def acquire(self, timeout: float | None = None):
        """Acquire a connection from the pool.

        Args:
            timeout: Acquisition timeout (uses config default if None)

        Yields:
            Connection instance

        Raises:
            TimeoutError: If acquisition times out
        """
        timeout = timeout or self.config.acquire_timeout
        start_time = time.time()
        pooled = None

        try:
            # Try to get existing connection
            pooled = await self._acquire_connection(timeout)

            if not pooled:
                raise TimeoutError(f"Failed to acquire connection within {timeout}s")

            # Record statistics
            if self._stats:
                wait_time = time.time() - start_time
                self._stats.record_acquire(wait_time)
                self._stats.active_connections += 1
                self._stats.idle_connections -= 1

            # Yield the connection
            yield pooled.connection

        finally:
            # Release the connection
            if pooled:
                await self._release_connection(pooled)

    async def _acquire_connection(self, timeout: float) -> PooledConnection | None:
        """Acquire a connection from the pool."""
        deadline = time.time() + timeout
        attempts = 0

        while time.time() < deadline and not self._closing:
            attempts += 1

            async with self._lock:
                # Try to find an idle connection
                for pooled in self._pool:
                    if pooled.state != ConnectionState.IDLE:
                        continue

                    # Check if connection is still valid
                    if pooled.is_expired() or pooled.is_idle_expired():
                        await self._remove_connection(pooled)
                        continue

                    # Perform health check if needed
                    if pooled.needs_health_check():
                        if not await self._validate_connection(pooled):
                            await self._remove_connection(pooled)
                            continue

                    # Reset and return connection
                    await self._reset_connection(pooled)
                    if pooled.state != ConnectionState.INVALID:
                        pooled.state = ConnectionState.IN_USE
                        pooled.last_used_at = time.time()
                        pooled.use_count += 1
                        return pooled

                # Try to create new connection if under limit
                if len(self._pool) < self.config.max_size:
                    pooled = await self._create_new_connection()
                    if pooled:
                        self._pool.append(pooled)
                        pooled.state = ConnectionState.IN_USE
                        pooled.use_count = 1
                        return pooled

            # Wait before retry
            remaining = deadline - time.time()
            if remaining > 0:
                await asyncio.sleep(min(0.1, remaining))

        return None

    async def _release_connection(self, pooled: PooledConnection):
        """Release connection back to pool."""
        async with self._lock:
            if pooled.state == ConnectionState.IN_USE:
                pooled.state = ConnectionState.IDLE
                pooled.last_used_at = time.time()

                if self._stats:
                    self._stats.record_release()
                    self._stats.active_connections -= 1
                    self._stats.idle_connections += 1

    async def _remove_connection(self, pooled: PooledConnection):
        """Remove connection from pool."""
        try:
            await pooled.close()
            if pooled in self._pool:
                self._pool.remove(pooled)

            if self._stats:
                self._stats.closed_connections += 1
                if pooled.state == ConnectionState.IDLE:
                    self._stats.idle_connections -= 1
                elif pooled.state == ConnectionState.IN_USE:
                    self._stats.active_connections -= 1

        except Exception as e:
            logger.error(f"Error closing connection: {e}")

    async def _maintenance_loop(self):
        """Background maintenance loop."""
        while not self._closing:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds

                async with self._lock:
                    # Remove expired connections
                    to_remove = []
                    for pooled in self._pool:
                        if pooled.state == ConnectionState.IDLE:
                            if pooled.is_expired() or pooled.is_idle_expired():
                                to_remove.append(pooled)

                    for pooled in to_remove:
                        await self._remove_connection(pooled)

                # Ensure minimum connections
                await self._ensure_min_connections()

            except Exception as e:
                logger.error(f"Maintenance loop error: {e}")

    async def close(self):
        """Close all connections and shut down pool."""
        self._closing = True

        # Cancel maintenance task
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        async with self._lock:
            for pooled in self._pool:
                await pooled.close()
            self._pool.clear()

        logger.info("Connection pool closed")

    def get_stats(self) -> PoolStats | None:
        """Get pool statistics."""
        return self._stats

    def get_status(self) -> dict[str, Any]:
        """Get pool status."""
        status = {
            "size": len(self._pool),
            "min_size": self.config.min_size,
            "max_size": self.config.max_size,
            "closing": self._closing,
        }

        if self._stats:
            status.update(
                {
                    "active": self._stats.active_connections,
                    "idle": self._stats.idle_connections,
                    "total_created": self._stats.created_connections,
                    "total_closed": self._stats.closed_connections,
                    "total_failed": self._stats.failed_connections,
                    "utilization": self._stats.get_utilization(),
                    "avg_wait_time": self._stats.get_average_wait_time(),
                }
            )

        return status


class ConnectionPoolManager:
    """Manager for multiple connection pools."""

    def __init__(self):
        """Initialize pool manager."""
        self._pools: dict[str, ConnectionPool] = {}

    def create_pool(
        self, name: str, create_connection: Callable, config: PoolConfig | None = None, **kwargs
    ) -> ConnectionPool:
        """Create or get a connection pool."""
        if name not in self._pools:
            self._pools[name] = ConnectionPool(create_connection, config, **kwargs)
        return self._pools[name]

    def get_pool(self, name: str) -> ConnectionPool | None:
        """Get pool by name."""
        return self._pools.get(name)

    async def close_all(self):
        """Close all pools."""
        for pool in self._pools.values():
            await pool.close()
        self._pools.clear()

    def get_status(self) -> dict[str, dict]:
        """Get status of all pools."""
        return {name: pool.get_status() for name, pool in self._pools.items()}


# Global pool manager
_pool_manager = ConnectionPoolManager()


def get_connection_pool(
    name: str, create_connection: Callable, config: PoolConfig | None = None, **kwargs
) -> ConnectionPool:
    """Get or create a connection pool."""
    return _pool_manager.create_pool(name, create_connection, config, **kwargs)


def get_pool_manager() -> ConnectionPoolManager:
    """Get the global pool manager."""
    return _pool_manager
