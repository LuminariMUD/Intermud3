"""Unit tests for network connection management."""

import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call
from dataclasses import dataclass
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from src.network.connection import (
    ConnectionState,
    RouterInfo,
    ConnectionStats,
    ConnectionManager,
    ConnectionPool
)
from src.network.mudmode import MudModeStreamProtocol, MudModeError


class TestConnectionState:
    """Test ConnectionState enumeration."""
    
    def test_connection_states(self):
        """Test all connection states exist."""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.AUTHENTICATING.value == "authenticating"
        assert ConnectionState.READY.value == "ready"
        assert ConnectionState.ERROR.value == "error"
        assert ConnectionState.CLOSING.value == "closing"


class TestRouterInfo:
    """Test RouterInfo dataclass."""
    
    def test_router_info_creation(self):
        """Test RouterInfo creation with defaults."""
        router = RouterInfo(
            name="test-router",
            address="test.example.com",
            port=8080
        )
        
        assert router.name == "test-router"
        assert router.address == "test.example.com"
        assert router.port == 8080
        assert router.priority == 0
        assert router.last_attempt == 0
        assert router.last_success == 0
        assert router.failure_count == 0
    
    def test_router_info_with_priority(self):
        """Test RouterInfo with custom priority."""
        router = RouterInfo(
            name="fallback",
            address="fallback.example.com",
            port=8080,
            priority=1
        )
        
        assert router.priority == 1
    
    def test_backoff_time_no_failures(self):
        """Test backoff time with no failures."""
        router = RouterInfo("test", "test.com", 8080)
        router.failure_count = 0
        
        assert router.backoff_time == 0
    
    def test_backoff_time_single_failure(self):
        """Test backoff time with single failure."""
        router = RouterInfo("test", "test.com", 8080)
        router.failure_count = 1
        
        backoff = router.backoff_time
        assert backoff >= 5  # Base backoff
        assert backoff <= 5.5  # Base + 10% jitter
    
    def test_backoff_time_multiple_failures(self):
        """Test exponential backoff with multiple failures."""
        router = RouterInfo("test", "test.com", 8080)
        
        router.failure_count = 2
        backoff2 = router.backoff_time
        
        router.failure_count = 3
        backoff3 = router.backoff_time
        
        # Should be exponentially increasing (approximately)
        assert backoff3 > backoff2
    
    def test_backoff_time_max_cap(self):
        """Test backoff time maximum cap."""
        router = RouterInfo("test", "test.com", 8080)
        router.failure_count = 20  # Very high failure count
        
        backoff = router.backoff_time
        # Should be capped at 300 + jitter
        assert backoff <= 330  # 300 + 10% jitter
    
    @patch('time.time', return_value=1000.0)
    def test_can_attempt_no_failures(self, mock_time):
        """Test can_attempt with no failures."""
        router = RouterInfo("test", "test.com", 8080)
        router.failure_count = 0
        
        assert router.can_attempt() is True
    
    @patch('time.time')
    def test_can_attempt_recent_failure(self, mock_time):
        """Test can_attempt with recent failure."""
        router = RouterInfo("test", "test.com", 8080)
        router.failure_count = 1
        router.last_attempt = 1000.0
        
        # Current time is just after attempt
        mock_time.return_value = 1001.0
        assert router.can_attempt() is False
        
        # Current time is after backoff period
        mock_time.return_value = 1010.0
        assert router.can_attempt() is True


class TestConnectionStats:
    """Test ConnectionStats dataclass."""
    
    def test_stats_creation(self):
        """Test ConnectionStats creation with defaults."""
        stats = ConnectionStats()
        
        assert stats.packets_sent == 0
        assert stats.packets_received == 0
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0
        assert stats.connection_time == 0
        assert stats.reconnect_count == 0
        assert stats.last_error is None
    
    def test_stats_with_values(self):
        """Test ConnectionStats with custom values."""
        stats = ConnectionStats(
            packets_sent=10,
            packets_received=15,
            bytes_sent=1024,
            bytes_received=2048,
            connection_time=1000.0,
            reconnect_count=3,
            last_error="Connection timeout"
        )
        
        assert stats.packets_sent == 10
        assert stats.packets_received == 15
        assert stats.bytes_sent == 1024
        assert stats.bytes_received == 2048
        assert stats.connection_time == 1000.0
        assert stats.reconnect_count == 3
        assert stats.last_error == "Connection timeout"


class TestConnectionManager:
    """Test ConnectionManager functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.primary_router = RouterInfo("primary", "primary.test", 8080, priority=0)
        self.fallback_router = RouterInfo("fallback", "fallback.test", 8080, priority=1)
        self.routers = [self.fallback_router, self.primary_router]  # Intentionally out of order
        
        self.mock_on_message = AsyncMock()
        self.mock_on_state_change = AsyncMock()
    
    def test_connection_manager_init(self):
        """Test ConnectionManager initialization."""
        manager = ConnectionManager(
            routers=self.routers,
            on_message=self.mock_on_message,
            on_state_change=self.mock_on_state_change,
            keepalive_interval=30.0,
            connection_timeout=15.0
        )
        
        # Routers should be sorted by priority
        assert manager.routers[0].priority == 0  # primary
        assert manager.routers[1].priority == 1  # fallback
        
        assert manager.on_message == self.mock_on_message
        assert manager.on_state_change == self.mock_on_state_change
        assert manager.keepalive_interval == 30.0
        assert manager.connection_timeout == 15.0
        
        assert manager.state == ConnectionState.DISCONNECTED
        assert manager.current_router is None
        assert manager.protocol is None
        assert manager.transport is None
        assert isinstance(manager.stats, ConnectionStats)
        assert manager._reconnect_task is None
        assert manager._keepalive_task is None
        assert manager._closing is False
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        manager = ConnectionManager(self.routers)
        
        mock_transport = MagicMock()
        mock_protocol = MagicMock(spec=MudModeStreamProtocol)
        
        with patch('asyncio.get_event_loop') as mock_get_loop, \
             patch('time.time', return_value=1000.0) as mock_time, \
             patch.object(manager, '_set_state') as mock_set_state, \
             patch.object(manager, '_start_keepalive') as mock_start_keepalive:
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.create_connection = AsyncMock(return_value=(mock_transport, mock_protocol))
            
            result = await manager.connect()
            
            assert result is True
            assert manager.current_router == self.primary_router  # Should use primary first
            assert manager.protocol is not None
            assert manager.transport == mock_transport
            assert manager.stats.connection_time == 1000.0
            
            # Should update router success info
            assert self.primary_router.last_success == 1000.0
            assert self.primary_router.failure_count == 0
            
            # Should call state changes
            mock_set_state.assert_has_calls([
                call(ConnectionState.CONNECTING),
                call(ConnectionState.CONNECTED)
            ])
            
            mock_start_keepalive.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """Test connecting when already connected."""
        manager = ConnectionManager(self.routers)
        manager.state = ConnectionState.CONNECTED
        
        result = await manager.connect()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_connect_primary_fails_fallback_succeeds(self):
        """Test fallback when primary fails."""
        manager = ConnectionManager(self.routers)
        
        mock_transport = MagicMock()
        
        with patch('asyncio.get_event_loop') as mock_get_loop, \
             patch('time.time', return_value=1000.0), \
             patch.object(manager, '_set_state') as mock_set_state, \
             patch.object(manager, '_start_keepalive'), \
             patch.object(manager, 'routers', self.routers):  # Ensure router order
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            
            # First call (primary) fails, second call (fallback) succeeds
            mock_loop.create_connection = AsyncMock(
                side_effect=[ConnectionError("Primary failed"), (mock_transport, MagicMock())]
            )
            
            result = await manager.connect()
            
            assert result is True
            assert manager.current_router == self.fallback_router
            
            # Primary should have failure recorded
            assert self.primary_router.failure_count == 1
            # Fallback should be successful
            assert self.fallback_router.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_connect_all_routers_fail(self):
        """Test when all routers fail."""
        manager = ConnectionManager(self.routers)
        
        with patch('asyncio.get_event_loop') as mock_get_loop, \
             patch('time.time', return_value=1000.0), \
             patch.object(manager, '_set_state') as mock_set_state, \
             patch.object(manager, '_schedule_reconnect') as mock_schedule:
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            mock_loop.create_connection = AsyncMock(side_effect=ConnectionError("Failed"))
            
            result = await manager.connect()
            
            assert result is False
            assert manager.current_router is None
            
            # All routers should have failures recorded
            assert self.primary_router.failure_count == 1
            assert self.fallback_router.failure_count == 1
            
            mock_set_state.assert_has_calls([
                call(ConnectionState.CONNECTING),
                call(ConnectionState.ERROR)
            ])
            mock_schedule.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_timeout(self):
        """Test connection timeout."""
        manager = ConnectionManager(self.routers, connection_timeout=0.1)
        
        with patch('asyncio.get_event_loop') as mock_get_loop, \
             patch('time.time', return_value=1000.0), \
             patch.object(manager, '_set_state'), \
             patch.object(manager, '_schedule_reconnect'):
            
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop
            
            # Simulate timeout
            async def slow_connect(*args, **kwargs):
                await asyncio.sleep(1.0)  # Longer than timeout
                return (MagicMock(), MagicMock())
            
            mock_loop.create_connection = slow_connect
            
            result = await manager.connect()
            
            assert result is False
            assert self.primary_router.failure_count == 1
    
    @pytest.mark.asyncio
    async def test_connect_router_backoff(self):
        """Test router backoff prevents attempts."""
        manager = ConnectionManager(self.routers)
        
        # Set router to have recent failure
        self.primary_router.failure_count = 1
        self.primary_router.last_attempt = 1000.0
        
        with patch('time.time', return_value=1001.0):  # Just after attempt
            # Router should not be attempted
            with patch.object(self.primary_router, 'can_attempt', return_value=False), \
                 patch.object(self.fallback_router, 'can_attempt', return_value=False), \
                 patch.object(manager, '_set_state') as mock_set_state, \
                 patch.object(manager, '_schedule_reconnect') as mock_schedule:
                
                result = await manager.connect()
                
                assert result is False
                mock_set_state.assert_has_calls([
                    call(ConnectionState.CONNECTING),
                    call(ConnectionState.ERROR)
                ])
                mock_schedule.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection."""
        manager = ConnectionManager(self.routers)
        
        # Set up connected state
        manager.protocol = MagicMock()
        manager.protocol.close = MagicMock()
        manager.transport = MagicMock()
        manager._reconnect_task = MagicMock()
        manager._keepalive_task = MagicMock()
        
        with patch.object(manager, '_set_state') as mock_set_state:
            await manager.disconnect()
            
            assert manager._closing is False  # Should be reset after
            assert manager.protocol is None
            assert manager.transport is None
            
            manager._reconnect_task.cancel.assert_called_once()
            manager._keepalive_task.cancel.assert_called_once()
            
            mock_set_state.assert_has_calls([
                call(ConnectionState.CLOSING),
                call(ConnectionState.DISCONNECTED)
            ])
    
    @pytest.mark.asyncio
    async def test_disconnect_no_tasks(self):
        """Test disconnection with no active tasks."""
        manager = ConnectionManager(self.routers)
        
        # No tasks set
        manager._reconnect_task = None
        manager._keepalive_task = None
        
        with patch.object(manager, '_set_state') as mock_set_state:
            await manager.disconnect()
            
            mock_set_state.assert_called_with(ConnectionState.DISCONNECTED)
    
    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test successful message sending."""
        manager = ConnectionManager(self.routers)
        manager.state = ConnectionState.CONNECTED
        manager.protocol = MagicMock()
        manager.protocol.send_message = MagicMock()
        
        test_data = ["test", "message"]
        result = await manager.send_message(test_data)
        
        assert result is True
        manager.protocol.send_message.assert_called_once_with(test_data)
        assert manager.stats.packets_sent == 1
    
    @pytest.mark.asyncio
    async def test_send_message_not_connected(self):
        """Test sending message when not connected."""
        manager = ConnectionManager(self.routers)
        manager.state = ConnectionState.DISCONNECTED
        
        result = await manager.send_message(["test"])
        
        assert result is False
        assert manager.stats.packets_sent == 0
    
    @pytest.mark.asyncio
    async def test_send_message_no_protocol(self):
        """Test sending message with no protocol."""
        manager = ConnectionManager(self.routers)
        manager.state = ConnectionState.CONNECTED
        manager.protocol = None
        
        result = await manager.send_message(["test"])
        
        assert result is False
        assert manager.stats.packets_sent == 0
    
    @pytest.mark.asyncio
    async def test_send_message_mudmode_error(self):
        """Test sending message with MudMode error."""
        manager = ConnectionManager(self.routers)
        manager.state = ConnectionState.CONNECTED
        manager.protocol = MagicMock()
        manager.protocol.send_message = MagicMock(side_effect=MudModeError("Encoding error"))
        
        result = await manager.send_message(["test"])
        
        assert result is False
        assert manager.stats.packets_sent == 0
    
    @pytest.mark.asyncio
    async def test_send_packet_success(self):
        """Test successful packet sending."""
        manager = ConnectionManager(self.routers)
        manager.state = ConnectionState.READY
        manager.protocol = MagicMock()
        manager.protocol.send_packet = MagicMock()
        
        test_packet = MagicMock()
        result = await manager.send_packet(test_packet)
        
        assert result is True
        manager.protocol.send_packet.assert_called_once_with(test_packet)
        assert manager.stats.packets_sent == 1
    
    @pytest.mark.asyncio
    async def test_send_packet_not_ready(self):
        """Test sending packet when not ready."""
        manager = ConnectionManager(self.routers)
        manager.state = ConnectionState.CONNECTING
        
        result = await manager.send_packet(MagicMock())
        
        assert result is False
        assert manager.stats.packets_sent == 0
    
    def test_is_connected(self):
        """Test connection status check."""
        manager = ConnectionManager(self.routers)
        
        manager.state = ConnectionState.DISCONNECTED
        assert manager.is_connected() is False
        
        manager.state = ConnectionState.CONNECTING
        assert manager.is_connected() is False
        
        manager.state = ConnectionState.CONNECTED
        assert manager.is_connected() is True
        
        manager.state = ConnectionState.READY
        assert manager.is_connected() is True
    
    def test_get_current_router(self):
        """Test getting current router."""
        manager = ConnectionManager(self.routers)
        
        assert manager.get_current_router() is None
        
        manager.current_router = self.primary_router
        assert manager.get_current_router() == self.primary_router
    
    def test_get_stats(self):
        """Test getting connection statistics."""
        manager = ConnectionManager(self.routers)
        
        stats = manager.get_stats()
        assert isinstance(stats, ConnectionStats)
        assert stats == manager.stats
    
    @pytest.mark.asyncio
    async def test_set_state(self):
        """Test state change handling."""
        manager = ConnectionManager(self.routers, on_state_change=self.mock_on_state_change)
        
        await manager._set_state(ConnectionState.CONNECTING)
        
        assert manager.state == ConnectionState.CONNECTING
        self.mock_on_state_change.assert_called_once_with(ConnectionState.CONNECTING)
    
    @pytest.mark.asyncio
    async def test_set_state_no_callback(self):
        """Test state change without callback."""
        manager = ConnectionManager(self.routers)  # No callback
        
        await manager._set_state(ConnectionState.CONNECTING)
        
        assert manager.state == ConnectionState.CONNECTING
    
    @pytest.mark.asyncio
    async def test_handle_message(self):
        """Test message handling."""
        manager = ConnectionManager(self.routers, on_message=self.mock_on_message)
        
        test_message = ["test", "packet"]
        await manager._handle_message(test_message)
        
        assert manager.stats.packets_received == 1
        self.mock_on_message.assert_called_once_with(test_message)
    
    @pytest.mark.asyncio
    async def test_handle_message_no_callback(self):
        """Test message handling without callback."""
        manager = ConnectionManager(self.routers)  # No callback
        
        test_message = ["test", "packet"]
        await manager._handle_message(test_message)
        
        assert manager.stats.packets_received == 1
    
    @pytest.mark.asyncio
    async def test_handle_connection_lost(self):
        """Test connection lost handling."""
        manager = ConnectionManager(self.routers)
        manager.current_router = self.primary_router
        manager.protocol = MagicMock()
        manager.transport = MagicMock()
        
        with patch.object(manager, '_set_state') as mock_set_state, \
             patch.object(manager, '_schedule_reconnect') as mock_schedule:
            
            await manager._handle_connection_lost()
            
            assert manager.current_router is None
            assert manager.protocol is None
            assert manager.transport is None
            assert self.primary_router.failure_count == 1
            
            mock_set_state.assert_called_once_with(ConnectionState.DISCONNECTED)
            mock_schedule.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_connection_lost_while_closing(self):
        """Test connection lost while closing."""
        manager = ConnectionManager(self.routers)
        manager._closing = True
        
        with patch.object(manager, '_set_state') as mock_set_state, \
             patch.object(manager, '_schedule_reconnect') as mock_schedule:
            
            await manager._handle_connection_lost()
            
            # Should not do anything when closing
            mock_set_state.assert_not_called()
            mock_schedule.assert_not_called()
    
    def test_schedule_reconnect(self):
        """Test reconnect scheduling."""
        manager = ConnectionManager(self.routers)
        
        with patch('asyncio.create_task') as mock_create_task:
            manager._schedule_reconnect()
            
            assert manager.stats.reconnect_count == 1
            mock_create_task.assert_called_once()
            assert manager._reconnect_task is not None
    
    def test_schedule_reconnect_task_exists(self):
        """Test reconnect scheduling when task exists."""
        manager = ConnectionManager(self.routers)
        manager._reconnect_task = MagicMock()
        
        with patch('asyncio.create_task') as mock_create_task:
            manager._schedule_reconnect()
            
            # Should not create new task
            mock_create_task.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_reconnect_task_execution(self):
        """Test reconnect task execution."""
        manager = ConnectionManager(self.routers)
        
        # Set up backoff times
        for router in manager.routers:
            router.failure_count = 1
        
        with patch('asyncio.sleep') as mock_sleep, \
             patch.object(manager, 'connect') as mock_connect:
            
            manager._schedule_reconnect()
            
            # Execute the task
            await manager._reconnect_task
            
            mock_sleep.assert_called_once()  # Should wait for backoff
            mock_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reconnect_task_while_closing(self):
        """Test reconnect task when closing."""
        manager = ConnectionManager(self.routers)
        manager._closing = True
        
        with patch('asyncio.sleep'), \
             patch.object(manager, 'connect') as mock_connect:
            
            manager._schedule_reconnect()
            
            # Execute the task
            await manager._reconnect_task
            
            # Should not attempt to connect when closing
            mock_connect.assert_not_called()
    
    def test_start_keepalive(self):
        """Test keepalive start."""
        manager = ConnectionManager(self.routers)
        
        with patch('asyncio.create_task') as mock_create_task:
            manager._start_keepalive()
            
            mock_create_task.assert_called_once()
            assert manager._keepalive_task is not None
    
    def test_start_keepalive_cancel_existing(self):
        """Test keepalive start cancels existing task."""
        manager = ConnectionManager(self.routers)
        existing_task = MagicMock()
        manager._keepalive_task = existing_task
        
        with patch('asyncio.create_task') as mock_create_task:
            manager._start_keepalive()
            
            existing_task.cancel.assert_called_once()
            mock_create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_keepalive_task_execution(self):
        """Test keepalive task execution."""
        manager = ConnectionManager(self.routers, keepalive_interval=0.1)
        manager.state = ConnectionState.READY
        
        with patch('asyncio.sleep') as mock_sleep, \
             patch.object(manager, 'is_connected', return_value=True):
            
            # Side effect to break the loop after first iteration
            mock_sleep.side_effect = [None, Exception("Break loop")]
            
            manager._start_keepalive()
            
            try:
                await manager._keepalive_task
            except Exception:
                pass  # Expected to break the loop
            
            mock_sleep.assert_called()


class TestConnectionPool:
    """Test ConnectionPool functionality."""
    
    def test_connection_pool_init(self):
        """Test ConnectionPool initialization."""
        pool = ConnectionPool(max_connections=5)
        
        assert pool.max_connections == 5
        assert pool.connections == []
        assert pool._current_index == 0
    
    def test_connection_pool_default_max(self):
        """Test ConnectionPool with default max connections."""
        pool = ConnectionPool()
        
        assert pool.max_connections == 3
    
    @pytest.mark.asyncio
    async def test_add_connection_success(self):
        """Test adding connection to pool."""
        pool = ConnectionPool(max_connections=2)
        
        mock_manager = MagicMock()
        mock_manager.connect = AsyncMock(return_value=True)
        
        result = await pool.add_connection(mock_manager)
        
        assert result is True
        assert mock_manager in pool.connections
        mock_manager.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_add_connection_pool_full(self):
        """Test adding connection when pool is full."""
        pool = ConnectionPool(max_connections=1)
        
        # Fill the pool
        mock_manager1 = MagicMock()
        mock_manager1.connect = AsyncMock(return_value=True)
        await pool.add_connection(mock_manager1)
        
        # Try to add another
        mock_manager2 = MagicMock()
        mock_manager2.connect = AsyncMock(return_value=True)
        result = await pool.add_connection(mock_manager2)
        
        assert result is False
        assert mock_manager2 not in pool.connections
        mock_manager2.connect.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_remove_connection(self):
        """Test removing connection from pool."""
        pool = ConnectionPool()
        
        mock_manager = MagicMock()
        mock_manager.connect = AsyncMock(return_value=True)
        mock_manager.disconnect = AsyncMock()
        
        # Add then remove
        await pool.add_connection(mock_manager)
        await pool.remove_connection(mock_manager)
        
        assert mock_manager not in pool.connections
        mock_manager.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_remove_connection_not_in_pool(self):
        """Test removing connection not in pool."""
        pool = ConnectionPool()
        
        mock_manager = MagicMock()
        mock_manager.disconnect = AsyncMock()
        
        # Should not raise exception
        await pool.remove_connection(mock_manager)
        
        mock_manager.disconnect.assert_called_once()
    
    def test_get_connection_empty_pool(self):
        """Test getting connection from empty pool."""
        pool = ConnectionPool()
        
        result = pool.get_connection()
        
        assert result is None
    
    def test_get_connection_round_robin(self):
        """Test round-robin connection selection."""
        pool = ConnectionPool()
        
        # Add mock managers
        mock_manager1 = MagicMock()
        mock_manager1.is_connected.return_value = True
        mock_manager2 = MagicMock()
        mock_manager2.is_connected.return_value = True
        
        pool.connections = [mock_manager1, mock_manager2]
        
        # Should cycle through connections
        result1 = pool.get_connection()
        result2 = pool.get_connection()
        result3 = pool.get_connection()
        
        assert result1 == mock_manager1
        assert result2 == mock_manager2
        assert result3 == mock_manager1  # Back to first
    
    def test_get_connection_skip_disconnected(self):
        """Test skipping disconnected connections."""
        pool = ConnectionPool()
        
        mock_manager1 = MagicMock()
        mock_manager1.is_connected.return_value = False  # Disconnected
        mock_manager2 = MagicMock()
        mock_manager2.is_connected.return_value = True   # Connected
        
        pool.connections = [mock_manager1, mock_manager2]
        
        result = pool.get_connection()
        
        assert result == mock_manager2  # Should skip disconnected
    
    def test_get_connection_all_disconnected(self):
        """Test getting connection when all are disconnected."""
        pool = ConnectionPool()
        
        mock_manager1 = MagicMock()
        mock_manager1.is_connected.return_value = False
        mock_manager2 = MagicMock()
        mock_manager2.is_connected.return_value = False
        
        pool.connections = [mock_manager1, mock_manager2]
        
        result = pool.get_connection()
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_broadcast_success(self):
        """Test broadcasting to all connections."""
        pool = ConnectionPool()
        
        mock_manager1 = MagicMock()
        mock_manager1.send_message = AsyncMock(return_value=True)
        mock_manager2 = MagicMock()
        mock_manager2.send_message = AsyncMock(return_value=True)
        
        pool.connections = [mock_manager1, mock_manager2]
        
        test_data = ["test", "message"]
        result = await pool.broadcast(test_data)
        
        assert result == 2
        mock_manager1.send_message.assert_called_once_with(test_data)
        mock_manager2.send_message.assert_called_once_with(test_data)
    
    @pytest.mark.asyncio
    async def test_broadcast_partial_failure(self):
        """Test broadcasting with partial failures."""
        pool = ConnectionPool()
        
        mock_manager1 = MagicMock()
        mock_manager1.send_message = AsyncMock(return_value=True)  # Success
        mock_manager2 = MagicMock()
        mock_manager2.send_message = AsyncMock(return_value=False)  # Failure
        
        pool.connections = [mock_manager1, mock_manager2]
        
        result = await pool.broadcast(["test"])
        
        assert result == 1  # Only one success
    
    @pytest.mark.asyncio
    async def test_close_all(self):
        """Test closing all connections."""
        pool = ConnectionPool()
        
        mock_manager1 = MagicMock()
        mock_manager1.disconnect = AsyncMock()
        mock_manager2 = MagicMock()
        mock_manager2.disconnect = AsyncMock()
        
        pool.connections = [mock_manager1, mock_manager2]
        
        await pool.close_all()
        
        assert pool.connections == []
        mock_manager1.disconnect.assert_called_once()
        mock_manager2.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_all_empty_pool(self):
        """Test closing all connections on empty pool."""
        pool = ConnectionPool()
        
        # Should not raise exception
        await pool.close_all()
        
        assert pool.connections == []