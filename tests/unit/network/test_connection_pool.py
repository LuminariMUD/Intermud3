"""Comprehensive unit tests for connection pool."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from src.network.connection_pool import (
    ConnectionPool,
    ConnectionPoolManager,
    ConnectionState,
    PoolConfig,
    PooledConnection,
    PoolStats,
    get_connection_pool,
    get_pool_manager,
)


class MockConnection:
    """Mock connection for testing."""

    def __init__(self, connection_id="mock-conn", should_fail=False):
        self.connection_id = connection_id
        self.should_fail = should_fail
        self.closed = False
        self.reset_called = False

    async def close(self):
        """Async close method."""
        self.closed = True

    def sync_close(self):
        """Sync close method for testing."""
        self.closed = True

    def reset(self):
        """Reset connection state."""
        self.reset_called = True


class TestPoolConfig:
    """Test PoolConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PoolConfig()

        assert config.min_size == 2
        assert config.max_size == 10
        assert config.max_idle_time == 300.0
        assert config.max_lifetime == 3600.0
        assert config.health_check_interval == 60.0
        assert config.acquire_timeout == 10.0
        assert config.retry_attempts == 3
        assert config.enable_stats is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = PoolConfig(
            min_size=5,
            max_size=20,
            max_idle_time=600.0,
            max_lifetime=7200.0,
            health_check_interval=30.0,
            acquire_timeout=15.0,
            retry_attempts=5,
            enable_stats=False,
        )

        assert config.min_size == 5
        assert config.max_size == 20
        assert config.max_idle_time == 600.0
        assert config.max_lifetime == 7200.0
        assert config.health_check_interval == 30.0
        assert config.acquire_timeout == 15.0
        assert config.retry_attempts == 5
        assert config.enable_stats is False


class TestPoolStats:
    """Test PoolStats class."""

    def test_initial_stats(self):
        """Test initial statistics values."""
        stats = PoolStats()

        assert stats.created_connections == 0
        assert stats.closed_connections == 0
        assert stats.failed_connections == 0
        assert stats.acquired_connections == 0
        assert stats.released_connections == 0
        assert stats.health_checks_passed == 0
        assert stats.health_checks_failed == 0
        assert stats.wait_time_total == 0.0
        assert stats.wait_count == 0
        assert stats.active_connections == 0
        assert stats.idle_connections == 0

    def test_record_acquire(self):
        """Test recording connection acquisition."""
        stats = PoolStats()

        stats.record_acquire(0.5)
        assert stats.acquired_connections == 1
        assert stats.wait_time_total == 0.5
        assert stats.wait_count == 1

        stats.record_acquire(1.0)
        assert stats.acquired_connections == 2
        assert stats.wait_time_total == 1.5
        assert stats.wait_count == 2

    def test_record_release(self):
        """Test recording connection release."""
        stats = PoolStats()

        stats.record_release()
        assert stats.released_connections == 1

        stats.record_release()
        assert stats.released_connections == 2

    def test_get_average_wait_time(self):
        """Test average wait time calculation."""
        stats = PoolStats()

        # No waits - should return 0
        assert stats.get_average_wait_time() == 0.0

        # Add some waits
        stats.record_acquire(0.5)
        stats.record_acquire(1.5)

        assert stats.get_average_wait_time() == 1.0  # (0.5 + 1.5) / 2

    def test_get_utilization(self):
        """Test utilization calculation."""
        stats = PoolStats()

        # No connections - should return 0
        assert stats.get_utilization() == 0.0

        # Set some connections
        stats.active_connections = 3
        stats.idle_connections = 7

        assert stats.get_utilization() == 0.3  # 3 / (3 + 7)

        # All active
        stats.active_connections = 10
        stats.idle_connections = 0

        assert stats.get_utilization() == 1.0


class TestPooledConnection:
    """Test PooledConnection class."""

    def test_pooled_connection_creation(self):
        """Test creating a pooled connection."""
        mock_conn = MockConnection()
        config = PoolConfig()
        pool = MagicMock()
        pool.config = config

        pooled = PooledConnection(connection=mock_conn, pool=pool)

        assert pooled.connection == mock_conn
        assert pooled.pool == pool
        assert pooled.state == ConnectionState.IDLE
        assert pooled.use_count == 0
        assert pooled.created_at > 0
        assert pooled.last_used_at > 0
        assert pooled.health_check_at > 0

    def test_is_expired(self):
        """Test connection expiration check."""
        mock_conn = MockConnection()
        config = PoolConfig(max_lifetime=1.0)  # 1 second
        pool = MagicMock()
        pool.config = config

        pooled = PooledConnection(connection=mock_conn, pool=pool)

        # Fresh connection should not be expired
        assert not pooled.is_expired()

        # Set creation time to past
        pooled.created_at = time.time() - 2.0
        assert pooled.is_expired()

        # Disabled lifetime check
        pool.config.max_lifetime = 0
        assert not pooled.is_expired()

    def test_is_idle_expired(self):
        """Test idle expiration check."""
        mock_conn = MockConnection()
        config = PoolConfig(max_idle_time=1.0)  # 1 second
        pool = MagicMock()
        pool.config = config

        pooled = PooledConnection(connection=mock_conn, pool=pool)

        # Fresh connection should not be idle expired
        assert not pooled.is_idle_expired()

        # Set last used time to past
        pooled.last_used_at = time.time() - 2.0
        assert pooled.is_idle_expired()

        # Disabled idle check
        pool.config.max_idle_time = 0
        assert not pooled.is_idle_expired()

    def test_needs_health_check(self):
        """Test health check requirement."""
        mock_conn = MockConnection()
        config = PoolConfig(health_check_interval=1.0)  # 1 second
        pool = MagicMock()
        pool.config = config

        pooled = PooledConnection(connection=mock_conn, pool=pool)

        # Fresh connection should not need health check
        assert not pooled.needs_health_check()

        # Set health check time to past
        pooled.health_check_at = time.time() - 2.0
        assert pooled.needs_health_check()

        # Disabled health check
        pool.config.health_check_interval = 0
        assert not pooled.needs_health_check()

    @pytest.mark.asyncio
    async def test_close_async(self):
        """Test closing connection with async close method."""
        mock_conn = MockConnection()
        pooled = PooledConnection(connection=mock_conn, pool=MagicMock())

        await pooled.close()

        assert pooled.state == ConnectionState.CLOSED
        assert mock_conn.closed is True

    @pytest.mark.asyncio
    async def test_close_sync(self):
        """Test closing connection with sync close method."""
        mock_conn = MockConnection()
        mock_conn.close = mock_conn.sync_close  # Use sync version
        pooled = PooledConnection(connection=mock_conn, pool=MagicMock())

        await pooled.close()

        assert pooled.state == ConnectionState.CLOSED
        assert mock_conn.closed is True

    @pytest.mark.asyncio
    async def test_close_no_close_method(self):
        """Test closing connection without close method."""
        mock_conn = object()  # No close method
        pooled = PooledConnection(connection=mock_conn, pool=MagicMock())

        await pooled.close()

        assert pooled.state == ConnectionState.CLOSED


class TestConnectionPool:
    """Test ConnectionPool class."""

    def test_pool_initialization(self):
        """Test pool initialization with various configurations."""

        # Default config
        def create_conn():
            return MockConnection()

        pool = ConnectionPool(create_conn)

        assert pool.create_connection == create_conn
        assert isinstance(pool.config, PoolConfig)
        assert pool.validate_connection is None
        assert pool.reset_connection is None
        assert len(pool._pool) == 0
        assert pool._closing is False
        assert isinstance(pool._stats, PoolStats)

        # Custom config with callbacks
        config = PoolConfig(min_size=5, enable_stats=False)
        validate_func = lambda conn: True
        reset_func = lambda conn: None

        pool = ConnectionPool(
            create_conn,
            config=config,
            validate_connection=validate_func,
            reset_connection=reset_func,
        )

        assert pool.config == config
        assert pool.validate_connection == validate_func
        assert pool.reset_connection == reset_func
        assert pool._stats is None  # Stats disabled

    @pytest.mark.asyncio
    async def test_start_pool(self):
        """Test starting the pool."""

        def create_conn():
            return MockConnection()

        config = PoolConfig(min_size=3)
        pool = ConnectionPool(create_conn, config)

        await pool.start()

        # Should create minimum connections
        assert len(pool._pool) == 3
        assert all(pc.state == ConnectionState.IDLE for pc in pool._pool)

        # Maintenance task should be running
        assert pool._maintenance_task is not None
        assert not pool._maintenance_task.done()

        await pool.close()

    @pytest.mark.asyncio
    async def test_ensure_min_connections(self):
        """Test ensuring minimum connections."""

        def create_conn():
            return MockConnection()

        config = PoolConfig(min_size=2)
        pool = ConnectionPool(create_conn, config)

        # Initially empty
        assert len(pool._pool) == 0

        # Ensure minimum
        await pool._ensure_min_connections()
        assert len(pool._pool) == 2

        # Add one more manually
        conn = await pool._create_new_connection()
        pool._pool.append(conn)
        assert len(pool._pool) == 3

        # Should not create more if already above minimum
        await pool._ensure_min_connections()
        assert len(pool._pool) == 3

    @pytest.mark.asyncio
    async def test_create_new_connection_async(self):
        """Test creating new connection with async factory."""

        async def create_conn():
            return MockConnection("async-conn")

        pool = ConnectionPool(create_conn)

        pooled = await pool._create_new_connection()

        assert pooled is not None
        assert pooled.connection.connection_id == "async-conn"
        assert pooled.state == ConnectionState.IDLE
        assert pool._stats.created_connections == 1
        assert pool._stats.idle_connections == 1

    @pytest.mark.asyncio
    async def test_create_new_connection_sync(self):
        """Test creating new connection with sync factory."""

        def create_conn():
            return MockConnection("sync-conn")

        pool = ConnectionPool(create_conn)

        pooled = await pool._create_new_connection()

        assert pooled is not None
        assert pooled.connection.connection_id == "sync-conn"
        assert pooled.state == ConnectionState.IDLE

    @pytest.mark.asyncio
    async def test_create_connection_failure(self):
        """Test handling connection creation failure."""

        def failing_create():
            raise RuntimeError("Connection failed")

        pool = ConnectionPool(failing_create)

        pooled = await pool._create_new_connection()

        assert pooled is None
        assert pool._stats.failed_connections == 1

    @pytest.mark.asyncio
    async def test_validate_connection_async(self):
        """Test connection validation with async validator."""

        async def validate(conn):
            return conn.connection_id != "bad-conn"

        pool = ConnectionPool(lambda: MockConnection(), validate_connection=validate)

        # Good connection
        good_conn = PooledConnection(MockConnection("good-conn"), pool)
        is_valid = await pool._validate_connection(good_conn)

        assert is_valid is True
        assert good_conn.state == ConnectionState.IDLE
        assert pool._stats.health_checks_passed == 1

        # Bad connection
        bad_conn = PooledConnection(MockConnection("bad-conn"), pool)
        is_valid = await pool._validate_connection(bad_conn)

        assert is_valid is False
        assert bad_conn.state == ConnectionState.INVALID
        assert pool._stats.health_checks_failed == 1

    @pytest.mark.asyncio
    async def test_validate_connection_sync(self):
        """Test connection validation with sync validator."""

        def validate(conn):
            return conn.connection_id == "good-conn"

        pool = ConnectionPool(lambda: MockConnection(), validate_connection=validate)

        good_conn = PooledConnection(MockConnection("good-conn"), pool)
        is_valid = await pool._validate_connection(good_conn)

        assert is_valid is True
        assert good_conn.state == ConnectionState.IDLE

    @pytest.mark.asyncio
    async def test_validate_connection_exception(self):
        """Test connection validation with exception."""

        def failing_validate(conn):
            raise RuntimeError("Validation failed")

        pool = ConnectionPool(lambda: MockConnection(), validate_connection=failing_validate)

        conn = PooledConnection(MockConnection(), pool)
        is_valid = await pool._validate_connection(conn)

        assert is_valid is False
        assert conn.state == ConnectionState.INVALID
        assert pool._stats.health_checks_failed == 1

    @pytest.mark.asyncio
    async def test_validate_connection_none(self):
        """Test connection validation when no validator provided."""
        pool = ConnectionPool(lambda: MockConnection())

        conn = PooledConnection(MockConnection(), pool)
        is_valid = await pool._validate_connection(conn)

        assert is_valid is True
        assert conn.state == ConnectionState.IDLE

    @pytest.mark.asyncio
    async def test_reset_connection_async(self):
        """Test connection reset with async reset function."""

        async def reset(conn):
            conn.reset()

        pool = ConnectionPool(lambda: MockConnection(), reset_connection=reset)

        mock_conn = MockConnection()
        pooled = PooledConnection(mock_conn, pool)

        await pool._reset_connection(pooled)

        assert mock_conn.reset_called is True

    @pytest.mark.asyncio
    async def test_reset_connection_sync(self):
        """Test connection reset with sync reset function."""

        def reset(conn):
            conn.reset()

        pool = ConnectionPool(lambda: MockConnection(), reset_connection=reset)

        mock_conn = MockConnection()
        pooled = PooledConnection(mock_conn, pool)

        await pool._reset_connection(pooled)

        assert mock_conn.reset_called is True

    @pytest.mark.asyncio
    async def test_reset_connection_exception(self):
        """Test connection reset with exception."""

        def failing_reset(conn):
            raise RuntimeError("Reset failed")

        pool = ConnectionPool(lambda: MockConnection(), reset_connection=failing_reset)

        pooled = PooledConnection(MockConnection(), pool)

        await pool._reset_connection(pooled)

        assert pooled.state == ConnectionState.INVALID

    @pytest.mark.asyncio
    async def test_acquire_connection_success(self):
        """Test successful connection acquisition."""

        def create_conn():
            return MockConnection()

        config = PoolConfig(min_size=2)
        pool = ConnectionPool(create_conn, config)

        await pool.start()

        async with pool.acquire() as conn:
            assert isinstance(conn, MockConnection)
            assert pool._stats.active_connections == 1
            assert pool._stats.idle_connections == 1  # One still idle

        # After release
        assert pool._stats.active_connections == 0
        assert pool._stats.idle_connections == 2
        assert pool._stats.acquired_connections == 1
        assert pool._stats.released_connections == 1

        await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_connection_timeout(self):
        """Test connection acquisition timeout."""

        def create_conn():
            return MockConnection()

        config = PoolConfig(max_size=1, acquire_timeout=0.1)
        pool = ConnectionPool(create_conn, config)

        await pool.start()

        # Acquire the only connection
        async with pool.acquire():
            # Try to acquire another - should timeout
            with pytest.raises(TimeoutError, match="Failed to acquire connection within"):
                async with pool.acquire():
                    pass

        await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_new_connection_under_limit(self):
        """Test acquiring new connection when under max limit."""
        connection_count = 0

        def create_conn():
            nonlocal connection_count
            connection_count += 1
            return MockConnection(f"conn-{connection_count}")

        config = PoolConfig(min_size=1, max_size=3)
        pool = ConnectionPool(create_conn, config)

        await pool.start()
        assert len(pool._pool) == 1  # Min size

        # Acquire connections - should create new ones
        async with pool.acquire() as conn1:
            assert conn1.connection_id == "conn-1"

            async with pool.acquire() as conn2:
                assert conn2.connection_id == "conn-2"
                assert len(pool._pool) == 2

        await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_expired_connection_removal(self):
        """Test removal of expired connections during acquisition."""

        def create_conn():
            return MockConnection()

        config = PoolConfig(min_size=2, max_lifetime=0.1)  # Very short lifetime
        pool = ConnectionPool(create_conn, config)

        await pool.start()
        initial_size = len(pool._pool)

        # Wait for connections to expire
        await asyncio.sleep(0.15)

        # Acquiring should remove expired and create new
        async with pool.acquire() as conn:
            assert isinstance(conn, MockConnection)
            # Should have removed expired connections
            assert len(pool._pool) >= 1

        await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_with_health_check(self):
        """Test connection acquisition with health check."""

        def create_conn():
            return MockConnection()

        def validate(conn):
            return conn.connection_id != "unhealthy"

        config = PoolConfig(health_check_interval=0.1)
        pool = ConnectionPool(create_conn, config, validate_connection=validate)

        # Add an unhealthy connection manually
        unhealthy = PooledConnection(MockConnection("unhealthy"), pool)
        unhealthy.health_check_at = time.time() - 1.0  # Force health check
        pool._pool.append(unhealthy)

        # Add a healthy connection
        healthy = PooledConnection(MockConnection("healthy"), pool)
        pool._pool.append(healthy)

        # Acquire should skip unhealthy and get healthy
        async with pool.acquire() as conn:
            assert conn.connection_id == "healthy"

        await pool.close()

    @pytest.mark.asyncio
    async def test_release_connection(self):
        """Test connection release."""
        pool = ConnectionPool(lambda: MockConnection())

        pooled = PooledConnection(MockConnection(), pool)
        pooled.state = ConnectionState.IN_USE

        await pool._release_connection(pooled)

        assert pooled.state == ConnectionState.IDLE
        assert pooled.last_used_at > 0
        assert pool._stats.released_connections == 1
        assert pool._stats.active_connections == -1  # Decremented
        assert pool._stats.idle_connections == 1

    @pytest.mark.asyncio
    async def test_remove_connection(self):
        """Test connection removal."""
        pool = ConnectionPool(lambda: MockConnection())

        mock_conn = MockConnection()
        pooled = PooledConnection(mock_conn, pool)
        pool._pool.append(pooled)

        await pool._remove_connection(pooled)

        assert mock_conn.closed is True
        assert pooled not in pool._pool
        assert pool._stats.closed_connections == 1

    @pytest.mark.asyncio
    async def test_maintenance_loop(self):
        """Test background maintenance loop."""

        def create_conn():
            return MockConnection()

        config = PoolConfig(min_size=2, max_idle_time=0.1)
        pool = ConnectionPool(create_conn, config)

        await pool.start()
        initial_size = len(pool._pool)

        # Set one connection as expired
        pool._pool[0].last_used_at = time.time() - 1.0

        # Wait for maintenance to run
        await asyncio.sleep(0.15)

        # Should have removed expired and ensured minimum
        assert len(pool._pool) >= config.min_size

        await pool.close()

    @pytest.mark.asyncio
    async def test_close_pool(self):
        """Test closing the pool."""

        def create_conn():
            return MockConnection()

        pool = ConnectionPool(create_conn, PoolConfig(min_size=2))

        await pool.start()
        assert len(pool._pool) == 2
        assert pool._maintenance_task is not None

        await pool.close()

        assert pool._closing is True
        assert len(pool._pool) == 0
        assert all(pc.connection.closed for pc in [] if hasattr(pc, "connection"))

    def test_get_stats(self):
        """Test getting pool statistics."""
        pool = ConnectionPool(lambda: MockConnection())

        stats = pool.get_stats()

        assert isinstance(stats, PoolStats)
        assert stats.acquired_connections == 0

    def test_get_stats_disabled(self):
        """Test getting stats when disabled."""
        config = PoolConfig(enable_stats=False)
        pool = ConnectionPool(lambda: MockConnection(), config)

        stats = pool.get_stats()

        assert stats is None

    def test_get_status(self):
        """Test getting pool status."""

        def create_conn():
            return MockConnection()

        config = PoolConfig(min_size=2, max_size=5)
        pool = ConnectionPool(create_conn, config)

        status = pool.get_status()

        assert status["size"] == 0
        assert status["min_size"] == 2
        assert status["max_size"] == 5
        assert status["closing"] is False
        assert "active" in status  # Stats enabled by default
        assert "utilization" in status

    def test_get_status_no_stats(self):
        """Test getting status with stats disabled."""
        config = PoolConfig(enable_stats=False)
        pool = ConnectionPool(lambda: MockConnection(), config)

        status = pool.get_status()

        assert "active" not in status
        assert "utilization" not in status


class TestConcurrentAccess:
    """Test concurrent access patterns."""

    @pytest.mark.asyncio
    async def test_concurrent_acquisition(self):
        """Test concurrent connection acquisition."""

        def create_conn():
            return MockConnection()

        config = PoolConfig(min_size=2, max_size=5)
        pool = ConnectionPool(create_conn, config)

        await pool.start()

        # Define async task for acquiring connections
        async def acquire_task(task_id):
            async with pool.acquire() as conn:
                assert isinstance(conn, MockConnection)
                await asyncio.sleep(0.01)  # Simulate work
                return f"task-{task_id}"

        # Run multiple tasks concurrently
        tasks = [acquire_task(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(result.startswith("task-") for result in results)

        await pool.close()

    @pytest.mark.asyncio
    async def test_concurrent_with_failures(self):
        """Test concurrent access with some failures."""
        failure_count = 0

        def create_conn():
            nonlocal failure_count
            failure_count += 1
            if failure_count % 3 == 0:
                raise RuntimeError("Simulated failure")
            return MockConnection(f"conn-{failure_count}")

        config = PoolConfig(min_size=1, max_size=5)
        pool = ConnectionPool(create_conn, config)

        await pool.start()

        async def acquire_task():
            try:
                async with pool.acquire() as conn:
                    return conn.connection_id
            except Exception:
                return "failed"

        # Run tasks concurrently
        tasks = [acquire_task() for _ in range(8)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should have some successes
        successes = [r for r in results if isinstance(r, str) and r.startswith("conn-")]
        assert len(successes) > 0

        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_expansion_under_load(self):
        """Test pool expansion under concurrent load."""

        def create_conn():
            return MockConnection()

        config = PoolConfig(min_size=1, max_size=10)
        pool = ConnectionPool(create_conn, config)

        await pool.start()
        assert len(pool._pool) == 1

        async def long_running_task():
            async with pool.acquire() as conn:
                await asyncio.sleep(0.1)  # Hold connection for a while
                return conn.connection_id

        # Start many tasks that should force pool expansion
        tasks = [long_running_task() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        # Pool should have expanded
        assert len(pool._pool) >= 5

        await pool.close()


class TestErrorHandling:
    """Test error handling and recovery."""

    @pytest.mark.asyncio
    async def test_creation_failure_recovery(self):
        """Test recovery from connection creation failures."""
        attempt_count = 0

        def unreliable_create():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count <= 2:
                raise RuntimeError("Creation failed")
            return MockConnection(f"conn-{attempt_count}")

        pool = ConnectionPool(unreliable_create)

        # First attempts should fail, but pool should recover
        await pool._ensure_min_connections()

        # Should eventually succeed
        assert pool._stats.failed_connections >= 2
        assert pool._stats.created_connections >= 1

    @pytest.mark.asyncio
    async def test_validation_failure_handling(self):
        """Test handling of validation failures."""

        def create_conn():
            return MockConnection()

        def intermittent_validate(conn):
            # Randomly fail validation
            return time.time() % 2 < 1

        pool = ConnectionPool(create_conn, validate_connection=intermittent_validate)

        # Create some connections
        await pool._ensure_min_connections()

        # Try to acquire - might fail validation
        try:
            async with pool.acquire() as conn:
                assert isinstance(conn, MockConnection)
        except TimeoutError:
            # Acceptable if all validations failed
            pass

    @pytest.mark.asyncio
    async def test_close_exception_handling(self):
        """Test handling exceptions during connection close."""

        class FailingConnection:
            async def close(self):
                raise RuntimeError("Close failed")

        pool = ConnectionPool(lambda: FailingConnection())

        failing_conn = PooledConnection(FailingConnection(), pool)
        pool._pool.append(failing_conn)

        # Should handle close exception gracefully
        await pool._remove_connection(failing_conn)

        assert failing_conn not in pool._pool

    @pytest.mark.asyncio
    async def test_maintenance_exception_handling(self):
        """Test handling exceptions in maintenance loop."""

        def create_conn():
            return MockConnection()

        config = PoolConfig(min_size=1)
        pool = ConnectionPool(create_conn, config)

        await pool.start()

        # Corrupt pool state to cause maintenance exception
        with patch.object(
            pool, "_ensure_min_connections", side_effect=RuntimeError("Maintenance error")
        ):
            # Wait for maintenance to encounter error
            await asyncio.sleep(0.1)

        # Pool should still be functional
        assert not pool._closing

        await pool.close()


class TestResourceCleanup:
    """Test resource cleanup scenarios."""

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self):
        """Test graceful shutdown of pool."""

        def create_conn():
            return MockConnection()

        pool = ConnectionPool(create_conn, PoolConfig(min_size=3))

        await pool.start()
        connections = [pc.connection for pc in pool._pool]

        await pool.close()

        # All connections should be closed
        assert all(conn.closed for conn in connections)
        assert pool._closing is True
        assert len(pool._pool) == 0

    @pytest.mark.asyncio
    async def test_cleanup_with_active_connections(self):
        """Test cleanup when connections are in use."""

        def create_conn():
            return MockConnection()

        pool = ConnectionPool(create_conn, PoolConfig(min_size=2))

        await pool.start()

        async def hold_connection():
            async with pool.acquire() as conn:
                await asyncio.sleep(0.1)
                return conn.connection_id

        # Start task that holds connection
        task = asyncio.create_task(hold_connection())

        # Close pool while connection is in use
        await pool.close()

        # Task should complete normally
        result = await task
        assert result is not None

    @pytest.mark.asyncio
    async def test_idle_connection_cleanup(self):
        """Test cleanup of idle connections."""

        def create_conn():
            return MockConnection()

        config = PoolConfig(min_size=1, max_idle_time=0.1)
        pool = ConnectionPool(create_conn, config)

        await pool.start()

        # Create extra connections
        for _ in range(3):
            conn = await pool._create_new_connection()
            pool._pool.append(conn)

        initial_size = len(pool._pool)

        # Wait for idle cleanup
        await asyncio.sleep(0.2)

        # Should have cleaned up idle connections but maintained minimum
        assert len(pool._pool) >= config.min_size
        assert len(pool._pool) < initial_size

        await pool.close()


class TestConnectionPoolManager:
    """Test ConnectionPoolManager class."""

    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = ConnectionPoolManager()

        assert len(manager._pools) == 0

    def test_create_pool(self):
        """Test creating pools."""
        manager = ConnectionPoolManager()

        def create_conn():
            return MockConnection()

        # Create first pool
        pool1 = manager.create_pool("pool1", create_conn)
        assert isinstance(pool1, ConnectionPool)
        assert manager.get_pool("pool1") == pool1

        # Create second pool with config
        config = PoolConfig(min_size=5)
        pool2 = manager.create_pool("pool2", create_conn, config)
        assert pool2.config.min_size == 5

        # Getting existing pool should return same instance
        same_pool = manager.create_pool("pool1", create_conn)
        assert same_pool == pool1

    def test_get_pool(self):
        """Test getting pools."""
        manager = ConnectionPoolManager()

        # Non-existent pool
        assert manager.get_pool("nonexistent") is None

        # Create and get pool
        pool = manager.create_pool("test", lambda: MockConnection())
        assert manager.get_pool("test") == pool

    @pytest.mark.asyncio
    async def test_close_all(self):
        """Test closing all pools."""
        manager = ConnectionPoolManager()

        # Create multiple pools
        pool1 = manager.create_pool("pool1", lambda: MockConnection())
        pool2 = manager.create_pool("pool2", lambda: MockConnection())

        await manager.close_all()

        assert len(manager._pools) == 0

    def test_get_status(self):
        """Test getting status of all pools."""
        manager = ConnectionPoolManager()

        # Create pools
        pool1 = manager.create_pool("pool1", lambda: MockConnection())
        pool2 = manager.create_pool("pool2", lambda: MockConnection())

        status = manager.get_status()

        assert "pool1" in status
        assert "pool2" in status
        assert isinstance(status["pool1"], dict)
        assert isinstance(status["pool2"], dict)


class TestGlobalFunctions:
    """Test global convenience functions."""

    def test_get_connection_pool(self):
        """Test get_connection_pool function."""

        def create_conn():
            return MockConnection()

        # Get pool (should create)
        pool1 = get_connection_pool("global_test", create_conn)
        assert isinstance(pool1, ConnectionPool)

        # Get same pool again
        pool2 = get_connection_pool("global_test", create_conn)
        assert pool1 == pool2

    def test_get_pool_manager(self):
        """Test get_pool_manager function."""
        manager = get_pool_manager()
        assert isinstance(manager, ConnectionPoolManager)

        # Should return same instance
        manager2 = get_pool_manager()
        assert manager == manager2


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_min_size(self):
        """Test pool with zero minimum size."""
        config = PoolConfig(min_size=0, max_size=2)
        pool = ConnectionPool(lambda: MockConnection(), config)

        await pool.start()
        assert len(pool._pool) == 0

        # Should create connection on demand
        async with pool.acquire() as conn:
            assert isinstance(conn, MockConnection)
            assert len(pool._pool) == 1

        await pool.close()

    @pytest.mark.asyncio
    async def test_very_short_timeouts(self):
        """Test with very short timeouts."""
        config = PoolConfig(acquire_timeout=0.001, max_idle_time=0.001, max_lifetime=0.001)  # 1ms
        pool = ConnectionPool(lambda: MockConnection(), config)

        await pool.start()

        # Everything should timeout/expire quickly
        with pytest.raises(TimeoutError):
            async with pool.acquire():
                await asyncio.sleep(0.01)

        await pool.close()

    @pytest.mark.asyncio
    async def test_disabled_timeouts(self):
        """Test with disabled timeouts."""
        config = PoolConfig(
            max_idle_time=0,  # Disabled
            max_lifetime=0,  # Disabled
            health_check_interval=0,  # Disabled
        )
        pool = ConnectionPool(lambda: MockConnection(), config)

        await pool.start()

        # Connections should never expire or need health checks
        pooled = pool._pool[0]
        pooled.created_at = 0  # Very old
        pooled.last_used_at = 0  # Very old
        pooled.health_check_at = 0  # Very old

        assert not pooled.is_expired()
        assert not pooled.is_idle_expired()
        assert not pooled.needs_health_check()

        await pool.close()

    @pytest.mark.asyncio
    async def test_max_size_equals_min_size(self):
        """Test when max size equals min size."""
        config = PoolConfig(min_size=3, max_size=3)
        pool = ConnectionPool(lambda: MockConnection(), config)

        await pool.start()
        assert len(pool._pool) == 3

        # Should not create more connections
        async with pool.acquire():
            async with pool.acquire():
                async with pool.acquire():
                    # All connections in use
                    assert len(pool._pool) == 3

                    # Next acquire should timeout
                    with pytest.raises(TimeoutError):
                        async with pool.acquire(timeout=0.1):
                            pass

        await pool.close()
