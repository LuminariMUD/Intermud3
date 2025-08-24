"""Unit tests for graceful shutdown mechanism."""

import asyncio
import signal
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from src.utils.shutdown import (
    GracefulShutdown,
    ShutdownConfig,
    ShutdownManager,
    ShutdownPhase,
    ShutdownStats,
    get_shutdown_manager,
    register_cleanup_task,
    register_shutdown_handler,
    wait_for_shutdown,
)


class TestShutdownPhase:
    """Test ShutdownPhase enumeration."""

    def test_shutdown_phases(self):
        """Test all shutdown phases exist."""
        assert ShutdownPhase.RUNNING.value == "running"
        assert ShutdownPhase.DRAINING.value == "draining"
        assert ShutdownPhase.CLOSING.value == "closing"
        assert ShutdownPhase.CLEANUP.value == "cleanup"
        assert ShutdownPhase.TERMINATED.value == "terminated"


class TestShutdownConfig:
    """Test ShutdownConfig dataclass."""

    def test_config_creation(self):
        """Test ShutdownConfig creation with defaults."""
        config = ShutdownConfig()

        assert config.drain_timeout == 30.0
        assert config.close_timeout == 10.0
        assert config.cleanup_timeout == 5.0
        assert config.force_timeout == 60.0
        assert config.save_state is True
        assert config.notify_peers is True

    def test_config_with_custom_values(self):
        """Test ShutdownConfig with custom values."""
        config = ShutdownConfig(
            drain_timeout=60.0,
            close_timeout=20.0,
            cleanup_timeout=10.0,
            force_timeout=120.0,
            save_state=False,
            notify_peers=False,
        )

        assert config.drain_timeout == 60.0
        assert config.close_timeout == 20.0
        assert config.cleanup_timeout == 10.0
        assert config.force_timeout == 120.0
        assert config.save_state is False
        assert config.notify_peers is False


class TestShutdownStats:
    """Test ShutdownStats dataclass."""

    def test_stats_creation(self):
        """Test ShutdownStats creation with defaults."""
        stats = ShutdownStats()

        assert stats.start_time is None
        assert stats.end_time is None
        assert stats.phase_times == {}
        assert stats.active_connections_start == 0
        assert stats.active_connections_drained == 0
        assert stats.active_connections_closed == 0
        assert stats.cleanup_tasks_completed == 0
        assert stats.cleanup_tasks_failed == 0
        assert stats.forced_shutdown is False

    @patch("time.time", return_value=1000.0)
    def test_record_phase_start(self, mock_time):
        """Test recording phase start time."""
        stats = ShutdownStats()

        stats.record_phase_start(ShutdownPhase.DRAINING)

        assert stats.phase_times[ShutdownPhase.DRAINING] == 1000.0

    @patch("time.time", return_value=1010.0)
    def test_get_phase_duration(self, mock_time):
        """Test getting phase duration."""
        stats = ShutdownStats()
        stats.phase_times[ShutdownPhase.DRAINING] = 1000.0
        stats.phase_times[ShutdownPhase.CLOSING] = 1005.0

        # Duration between draining and closing
        duration = stats.get_phase_duration(ShutdownPhase.DRAINING)
        assert duration == 5.0

        # Duration from closing to current time
        duration = stats.get_phase_duration(ShutdownPhase.CLOSING)
        assert duration == 5.0

    def test_get_phase_duration_no_phase(self):
        """Test getting duration for non-existent phase."""
        stats = ShutdownStats()

        duration = stats.get_phase_duration(ShutdownPhase.DRAINING)
        assert duration is None

    @patch("time.time", return_value=1010.0)
    def test_get_phase_duration_with_end_time(self, mock_time):
        """Test getting phase duration with end time set."""
        stats = ShutdownStats()
        stats.start_time = 1000.0
        stats.end_time = 1008.0
        stats.phase_times[ShutdownPhase.DRAINING] = 1003.0

        # Should use end time instead of current time
        duration = stats.get_phase_duration(ShutdownPhase.DRAINING)
        assert duration == 5.0  # 1008 - 1003

    def test_get_total_duration(self):
        """Test getting total shutdown duration."""
        stats = ShutdownStats()
        stats.start_time = 1000.0
        stats.end_time = 1050.0

        duration = stats.get_total_duration()
        assert duration == 50.0

    @patch("time.time", return_value=1030.0)
    def test_get_total_duration_no_end_time(self, mock_time):
        """Test getting total duration without end time."""
        stats = ShutdownStats()
        stats.start_time = 1000.0

        duration = stats.get_total_duration()
        assert duration == 30.0

    def test_get_total_duration_no_start_time(self):
        """Test getting total duration without start time."""
        stats = ShutdownStats()

        duration = stats.get_total_duration()
        assert duration is None


class TestGracefulShutdown:
    """Test GracefulShutdown functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = ShutdownConfig(
            drain_timeout=1.0, close_timeout=1.0, cleanup_timeout=1.0, force_timeout=5.0
        )

    @patch("signal.signal")
    def test_graceful_shutdown_init(self, mock_signal):
        """Test GracefulShutdown initialization."""
        shutdown = GracefulShutdown(self.config)

        assert shutdown.config == self.config
        assert shutdown.phase == ShutdownPhase.RUNNING
        assert isinstance(shutdown.stats, ShutdownStats)
        assert shutdown._shutdown_event is not None
        assert shutdown._shutdown_complete is not None
        assert shutdown._handlers == []
        assert shutdown._cleanup_tasks == []
        assert shutdown._active_connections == []
        assert shutdown._force_shutdown_task is None
        assert shutdown._original_handlers == {}

        # Should register signal handlers
        assert mock_signal.call_count >= 2  # At least SIGTERM and SIGINT

    @patch("signal.signal")
    def test_graceful_shutdown_default_config(self, mock_signal):
        """Test GracefulShutdown with default config."""
        shutdown = GracefulShutdown()

        assert isinstance(shutdown.config, ShutdownConfig)
        assert shutdown.config.drain_timeout == 30.0

    def test_register_handler(self):
        """Test registering shutdown handler."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown()
            mock_handler = MagicMock()

            shutdown.register_handler(mock_handler)

            assert mock_handler in shutdown._handlers

    def test_register_cleanup(self):
        """Test registering cleanup task."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown()
            mock_task = MagicMock()

            shutdown.register_cleanup(mock_task)

            assert mock_task in shutdown._cleanup_tasks

    def test_register_connection(self):
        """Test registering active connection."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown()
            mock_connection = MagicMock()

            shutdown.register_connection(mock_connection)

            assert mock_connection in shutdown._active_connections

    def test_unregister_connection(self):
        """Test unregistering connection."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown()
            mock_connection = MagicMock()

            shutdown.register_connection(mock_connection)
            shutdown.unregister_connection(mock_connection)

            assert mock_connection not in shutdown._active_connections

    def test_unregister_connection_not_present(self):
        """Test unregistering connection not in list."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown()
            mock_connection = MagicMock()

            # Should not raise exception
            shutdown.unregister_connection(mock_connection)

    def test_is_shutting_down(self):
        """Test shutdown status check."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown()

            assert shutdown.is_shutting_down() is False

            shutdown.phase = ShutdownPhase.DRAINING
            assert shutdown.is_shutting_down() is True

    def test_should_accept_connections(self):
        """Test connection acceptance check."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown()

            assert shutdown.should_accept_connections() is True

            shutdown.phase = ShutdownPhase.DRAINING
            assert shutdown.should_accept_connections() is False

    @pytest.mark.asyncio
    async def test_wait_for_shutdown(self):
        """Test waiting for shutdown signal."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown()

            # Start wait task
            wait_task = asyncio.create_task(shutdown.wait_for_shutdown())

            # Let it start waiting
            await asyncio.sleep(0.01)

            # Signal shutdown
            shutdown._shutdown_event.set()

            # Wait should complete
            await wait_task

            assert shutdown._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_basic_flow(self):
        """Test basic shutdown flow."""
        with patch("signal.signal"), patch("time.time", return_value=1000.0):

            shutdown = GracefulShutdown(self.config)

            with (
                patch.object(shutdown, "_drain_connections") as mock_drain,
                patch.object(shutdown, "_close_connections") as mock_close,
                patch.object(shutdown, "_cleanup_resources") as mock_cleanup,
            ):

                await shutdown.shutdown("Test shutdown")

                mock_drain.assert_called_once()
                mock_close.assert_called_once()
                mock_cleanup.assert_called_once()

                assert shutdown.phase == ShutdownPhase.TERMINATED
                assert shutdown._shutdown_event.is_set()
                assert shutdown._shutdown_complete.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_already_shutting_down(self):
        """Test shutdown when already in progress."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown()
            shutdown.phase = ShutdownPhase.DRAINING

            with patch.object(shutdown, "_drain_connections") as mock_drain:
                await shutdown.shutdown("Test shutdown")

                # Should not call drain again
                mock_drain.assert_not_called()

    @pytest.mark.asyncio
    async def test_shutdown_with_exception(self):
        """Test shutdown with exception during process."""
        with patch("signal.signal"), patch("time.time", return_value=1000.0):

            shutdown = GracefulShutdown(self.config)

            with (
                patch.object(shutdown, "_drain_connections", side_effect=Exception("Drain error")),
                patch.object(shutdown, "_close_connections") as mock_close,
                patch.object(shutdown, "_cleanup_resources") as mock_cleanup,
            ):

                await shutdown.shutdown("Test shutdown")

                # Should continue despite exception
                mock_close.assert_called_once()
                mock_cleanup.assert_called_once()
                assert shutdown._shutdown_complete.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_cancelled(self):
        """Test shutdown cancellation."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown(self.config)

            with patch.object(shutdown, "_drain_connections", side_effect=asyncio.CancelledError()):

                with pytest.raises(asyncio.CancelledError):
                    await shutdown.shutdown("Test shutdown")

    @pytest.mark.asyncio
    async def test_drain_connections_no_handlers(self):
        """Test connection draining with no handlers."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown(self.config)

            await shutdown._drain_connections()

            assert shutdown.phase == ShutdownPhase.DRAINING

    @pytest.mark.asyncio
    async def test_drain_connections_with_handlers(self):
        """Test connection draining with handlers."""
        with patch("signal.signal"), patch("time.time", return_value=1000.0):

            shutdown = GracefulShutdown(self.config)

            # Add sync and async handlers
            sync_handler = MagicMock()
            async_handler = AsyncMock()

            shutdown.register_handler(sync_handler)
            shutdown.register_handler(async_handler)

            await shutdown._drain_connections()

            sync_handler.assert_called_once_with("drain")
            async_handler.assert_called_once_with("drain")

    @pytest.mark.asyncio
    async def test_drain_connections_handler_exception(self):
        """Test connection draining with handler exception."""
        with patch("signal.signal"), patch("time.time", return_value=1000.0):

            shutdown = GracefulShutdown(self.config)

            # Handler that raises exception
            error_handler = MagicMock(side_effect=Exception("Handler error"))
            shutdown.register_handler(error_handler)

            # Should not raise exception
            await shutdown._drain_connections()

            error_handler.assert_called_once_with("drain")

    @pytest.mark.asyncio
    async def test_drain_connections_with_active_connections(self):
        """Test draining with active connections."""
        with (
            patch("signal.signal"),
            patch("time.time", return_value=1000.0),
            patch("asyncio.sleep"),
        ):  # Speed up the test

            shutdown = GracefulShutdown(self.config)

            # Add some mock connections
            conn1 = MagicMock()
            conn2 = MagicMock()
            shutdown.register_connection(conn1)
            shutdown.register_connection(conn2)

            # Simulate connections being removed during drain
            async def remove_connections():
                await asyncio.sleep(0.1)
                shutdown.unregister_connection(conn1)
                shutdown.unregister_connection(conn2)

            drain_task = asyncio.create_task(shutdown._drain_connections())
            remove_task = asyncio.create_task(remove_connections())

            await asyncio.gather(drain_task, remove_task)

            assert len(shutdown._active_connections) == 0

    @pytest.mark.asyncio
    async def test_close_connections_no_connections(self):
        """Test closing connections with no active connections."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown(self.config)

            await shutdown._close_connections()

            assert shutdown.phase == ShutdownPhase.CLOSING

    @pytest.mark.asyncio
    async def test_close_connections_with_connections(self):
        """Test closing active connections."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown(self.config)

            # Add mock connections with different close methods
            sync_conn = MagicMock()
            sync_conn.close = MagicMock()

            async_conn = MagicMock()
            async_conn.close = AsyncMock()

            no_close_conn = MagicMock()
            delattr(no_close_conn, "close")  # No close method

            shutdown.register_connection(sync_conn)
            shutdown.register_connection(async_conn)
            shutdown.register_connection(no_close_conn)

            await shutdown._close_connections()

            sync_conn.close.assert_called_once()
            async_conn.close.assert_called_once()

            # All connections should be removed
            assert len(shutdown._active_connections) == 0

    @pytest.mark.asyncio
    async def test_close_connections_with_exception(self):
        """Test closing connections with exception."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown(self.config)

            # Connection that raises exception on close
            error_conn = MagicMock()
            error_conn.close = MagicMock(side_effect=Exception("Close error"))

            shutdown.register_connection(error_conn)

            # Should not raise exception
            await shutdown._close_connections()

    @pytest.mark.asyncio
    async def test_close_connections_timeout(self):
        """Test closing connections with timeout."""
        with patch("signal.signal"):
            shutdown = GracefulShutdown(self.config)

            # Connection with slow async close
            slow_conn = MagicMock()

            async def slow_close():
                await asyncio.sleep(2.0)  # Longer than timeout

            slow_conn.close = slow_close

            shutdown.register_connection(slow_conn)

            # Should handle timeout gracefully
            await shutdown._close_connections()

    @pytest.mark.asyncio
    async def test_cleanup_resources_no_tasks(self):
        """Test resource cleanup with no tasks."""
        with patch("signal.signal"), patch.object(GracefulShutdown, "_register_signal_handlers"):

            shutdown = GracefulShutdown(self.config)

            await shutdown._cleanup_resources()

            assert shutdown.phase == ShutdownPhase.CLEANUP
            assert shutdown.stats.cleanup_tasks_completed == 0
            assert shutdown.stats.cleanup_tasks_failed == 0

    @pytest.mark.asyncio
    async def test_cleanup_resources_with_tasks(self):
        """Test resource cleanup with sync and async tasks."""
        with patch("signal.signal"), patch.object(GracefulShutdown, "_register_signal_handlers"):

            shutdown = GracefulShutdown(self.config)

            # Add sync and async cleanup tasks
            sync_task = MagicMock()
            async_task = AsyncMock()

            shutdown.register_cleanup(sync_task)
            shutdown.register_cleanup(async_task)

            await shutdown._cleanup_resources()

            sync_task.assert_called_once()
            async_task.assert_called_once()

            assert shutdown.stats.cleanup_tasks_completed == 2
            assert shutdown.stats.cleanup_tasks_failed == 0

    @pytest.mark.asyncio
    async def test_cleanup_resources_with_exceptions(self):
        """Test resource cleanup with task exceptions."""
        with patch("signal.signal"), patch.object(GracefulShutdown, "_register_signal_handlers"):

            shutdown = GracefulShutdown(self.config)

            # Tasks that raise exceptions
            error_sync = MagicMock(side_effect=Exception("Sync error"))
            error_async = AsyncMock(side_effect=Exception("Async error"))

            shutdown.register_cleanup(error_sync)
            shutdown.register_cleanup(error_async)

            await shutdown._cleanup_resources()

            assert shutdown.stats.cleanup_tasks_completed == 0
            assert shutdown.stats.cleanup_tasks_failed == 2

    @pytest.mark.asyncio
    async def test_cleanup_resources_timeout(self):
        """Test resource cleanup with timeout."""
        with patch("signal.signal"), patch.object(GracefulShutdown, "_register_signal_handlers"):

            shutdown = GracefulShutdown(self.config)

            # Slow async task
            async def slow_task():
                await asyncio.sleep(2.0)  # Longer than timeout

            shutdown.register_cleanup(slow_task)

            await shutdown._cleanup_resources()

            # Should mark as failed due to timeout
            assert shutdown.stats.cleanup_tasks_failed == 1

    @pytest.mark.asyncio
    async def test_force_shutdown_timer(self):
        """Test force shutdown timer."""
        with patch("signal.signal"), patch("sys.exit") as mock_exit:

            shutdown = GracefulShutdown(ShutdownConfig(force_timeout=0.1))

            # Start force shutdown timer
            await shutdown._force_shutdown_timer()

            # Should call sys.exit
            mock_exit.assert_called_once_with(1)
            assert shutdown.stats.forced_shutdown is True

    @pytest.mark.asyncio
    async def test_force_shutdown_timer_cancelled(self):
        """Test force shutdown timer cancellation."""
        with patch("signal.signal"), patch("sys.exit") as mock_exit:

            shutdown = GracefulShutdown(self.config)

            # Start and quickly cancel timer
            timer_task = asyncio.create_task(shutdown._force_shutdown_timer())
            await asyncio.sleep(0.01)
            timer_task.cancel()

            try:
                await timer_task
            except asyncio.CancelledError:
                pass

            # Should not call sys.exit
            mock_exit.assert_not_called()

    @patch("signal.signal")
    def test_log_shutdown_stats(self, mock_signal):
        """Test logging shutdown statistics."""
        shutdown = GracefulShutdown()
        shutdown.stats.start_time = 1000.0
        shutdown.stats.end_time = 1050.0
        shutdown.stats.active_connections_start = 10
        shutdown.stats.active_connections_drained = 3
        shutdown.stats.active_connections_closed = 7
        shutdown.stats.cleanup_tasks_completed = 5
        shutdown.stats.cleanup_tasks_failed = 2
        shutdown.stats.phase_times[ShutdownPhase.DRAINING] = 1010.0

        # Should not raise exception
        shutdown._log_shutdown_stats()

    @patch("signal.signal")
    @patch("asyncio.create_task")
    def test_handle_signal(self, mock_create_task, mock_signal):
        """Test signal handling."""
        shutdown = GracefulShutdown()

        # Simulate signal handler call
        shutdown._handle_signal(signal.SIGTERM.value, None)

        # Should create shutdown task
        mock_create_task.assert_called_once()

    @patch("signal.signal")
    def test_register_signal_handlers_with_sighup(self, mock_signal):
        """Test signal handler registration with SIGHUP."""
        with patch("hasattr", return_value=True):  # Mock SIGHUP availability
            shutdown = GracefulShutdown()

            # Should register at least SIGTERM, SIGINT, and SIGHUP
            assert mock_signal.call_count >= 3

    @patch("signal.signal", side_effect=Exception("Signal error"))
    def test_register_signal_handlers_with_exception(self, mock_signal):
        """Test signal handler registration with exception."""
        # Should not raise exception even if signal registration fails
        shutdown = GracefulShutdown()
        assert shutdown is not None


class TestShutdownManager:
    """Test ShutdownManager functionality."""

    def test_shutdown_manager_init(self):
        """Test ShutdownManager initialization."""
        config = ShutdownConfig()
        with patch("src.utils.shutdown.GracefulShutdown") as mock_graceful:
            manager = ShutdownManager(config)

            assert manager.config == config
            mock_graceful.assert_called_once_with(config)
            assert manager._components == {}

    def test_shutdown_manager_default_config(self):
        """Test ShutdownManager with default config."""
        with patch("src.utils.shutdown.GracefulShutdown"):
            manager = ShutdownManager()

            assert isinstance(manager.config, ShutdownConfig)

    def test_register_component_with_cleanup(self):
        """Test registering component with cleanup method."""
        with patch("src.utils.shutdown.GracefulShutdown") as mock_graceful:
            manager = ShutdownManager()
            mock_handler = mock_graceful.return_value

            # Component with cleanup method
            component = MagicMock()
            component.cleanup = MagicMock()

            manager.register_component("test", component)

            assert manager._components["test"] == component
            mock_handler.register_cleanup.assert_called_once_with(component.cleanup)

    def test_register_component_with_close(self):
        """Test registering component with close method."""
        with patch("src.utils.shutdown.GracefulShutdown") as mock_graceful:
            manager = ShutdownManager()
            mock_handler = mock_graceful.return_value

            # Component with close method (no cleanup)
            component = MagicMock()
            component.close = MagicMock()
            delattr(component, "cleanup")  # No cleanup method

            manager.register_component("test", component)

            assert manager._components["test"] == component
            mock_handler.register_cleanup.assert_called_once_with(component.close)

    def test_register_component_no_cleanup_methods(self):
        """Test registering component with no cleanup methods."""
        with patch("src.utils.shutdown.GracefulShutdown") as mock_graceful:
            manager = ShutdownManager()
            mock_handler = mock_graceful.return_value

            # Component with no cleanup methods
            component = MagicMock()
            delattr(component, "cleanup")
            delattr(component, "close")

            manager.register_component("test", component)

            assert manager._components["test"] == component
            mock_handler.register_cleanup.assert_not_called()

    @pytest.mark.asyncio
    async def test_shutdown_with_state_saving(self):
        """Test shutdown with state saving enabled."""
        config = ShutdownConfig(save_state=True, notify_peers=False)

        with patch("src.utils.shutdown.GracefulShutdown") as mock_graceful:
            manager = ShutdownManager(config)
            mock_handler = mock_graceful.return_value
            mock_handler.shutdown = AsyncMock()

            # Register component with save_state method
            component = MagicMock()
            component.save_state = MagicMock()
            manager.register_component("test", component)

            await manager.shutdown("Test reason")

            component.save_state.assert_called_once()
            mock_handler.shutdown.assert_called_once_with("Test reason")

    @pytest.mark.asyncio
    async def test_shutdown_with_async_save_state(self):
        """Test shutdown with async save_state method."""
        config = ShutdownConfig(save_state=True, notify_peers=False)

        with patch("src.utils.shutdown.GracefulShutdown") as mock_graceful:
            manager = ShutdownManager(config)
            mock_handler = mock_graceful.return_value
            mock_handler.shutdown = AsyncMock()

            # Component with async save_state method
            component = MagicMock()
            component.save_state = AsyncMock()
            manager.register_component("test", component)

            await manager.shutdown("Test reason")

            component.save_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_peer_notification(self):
        """Test shutdown with peer notification enabled."""
        config = ShutdownConfig(save_state=False, notify_peers=True)

        with patch("src.utils.shutdown.GracefulShutdown") as mock_graceful:
            manager = ShutdownManager(config)
            mock_handler = mock_graceful.return_value
            mock_handler.shutdown = AsyncMock()

            # Register component with notify_shutdown method
            component = MagicMock()
            component.notify_shutdown = MagicMock()
            manager.register_component("test", component)

            await manager.shutdown("Test reason")

            component.notify_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_with_async_notify_shutdown(self):
        """Test shutdown with async notify_shutdown method."""
        config = ShutdownConfig(save_state=False, notify_peers=True)

        with patch("src.utils.shutdown.GracefulShutdown") as mock_graceful:
            manager = ShutdownManager(config)
            mock_handler = mock_graceful.return_value
            mock_handler.shutdown = AsyncMock()

            # Component with async notify_shutdown method
            component = MagicMock()
            component.notify_shutdown = AsyncMock()
            manager.register_component("test", component)

            await manager.shutdown("Test reason")

            component.notify_shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_state_exception(self):
        """Test save state with exception."""
        config = ShutdownConfig(save_state=True)

        with patch("src.utils.shutdown.GracefulShutdown") as mock_graceful:
            manager = ShutdownManager(config)
            mock_handler = mock_graceful.return_value
            mock_handler.shutdown = AsyncMock()

            # Component that raises exception
            component = MagicMock()
            component.save_state = MagicMock(side_effect=Exception("Save error"))
            manager.register_component("test", component)

            # Should not raise exception
            await manager.shutdown("Test reason")

    @pytest.mark.asyncio
    async def test_notify_peers_exception(self):
        """Test notify peers with exception."""
        config = ShutdownConfig(notify_peers=True)

        with patch("src.utils.shutdown.GracefulShutdown") as mock_graceful:
            manager = ShutdownManager(config)
            mock_handler = mock_graceful.return_value
            mock_handler.shutdown = AsyncMock()

            # Component that raises exception
            component = MagicMock()
            component.notify_shutdown = MagicMock(side_effect=Exception("Notify error"))
            manager.register_component("test", component)

            # Should not raise exception
            await manager.shutdown("Test reason")

    @pytest.mark.asyncio
    async def test_shutdown_context(self):
        """Test shutdown context manager."""
        with patch("src.utils.shutdown.GracefulShutdown") as mock_graceful:
            manager = ShutdownManager()
            mock_handler = mock_graceful.return_value
            mock_handler.shutdown = AsyncMock()

            async with manager.shutdown_context() as ctx:
                assert ctx == manager

            # Should call shutdown on exit
            mock_handler.shutdown.assert_called_once_with("Context exit")


class TestGlobalFunctions:
    """Test global shutdown functions."""

    def test_get_shutdown_manager(self):
        """Test getting global shutdown manager."""
        # Reset global state
        import src.utils.shutdown

        src.utils.shutdown._shutdown_manager = None

        with patch("src.utils.shutdown.ShutdownManager") as mock_manager_class:
            manager1 = get_shutdown_manager()
            manager2 = get_shutdown_manager()

            # Should create only once
            mock_manager_class.assert_called_once_with(None)
            assert manager1 == manager2

    def test_get_shutdown_manager_with_config(self):
        """Test getting shutdown manager with config."""
        # Reset global state
        import src.utils.shutdown

        src.utils.shutdown._shutdown_manager = None

        config = ShutdownConfig()

        with patch("src.utils.shutdown.ShutdownManager") as mock_manager_class:
            get_shutdown_manager(config)

            mock_manager_class.assert_called_once_with(config)

    def test_register_shutdown_handler(self):
        """Test registering global shutdown handler."""
        mock_handler = MagicMock()

        with patch("src.utils.shutdown.get_shutdown_manager") as mock_get_manager:
            mock_manager = MagicMock()
            mock_get_manager.return_value = mock_manager

            register_shutdown_handler(mock_handler)

            mock_get_manager.assert_called_once()
            mock_manager.shutdown_handler.register_handler.assert_called_once_with(mock_handler)

    def test_register_cleanup_task(self):
        """Test registering global cleanup task."""
        mock_task = MagicMock()

        with patch("src.utils.shutdown.get_shutdown_manager") as mock_get_manager:
            mock_manager = MagicMock()
            mock_get_manager.return_value = mock_manager

            register_cleanup_task(mock_task)

            mock_get_manager.assert_called_once()
            mock_manager.shutdown_handler.register_cleanup.assert_called_once_with(mock_task)

    @pytest.mark.asyncio
    async def test_wait_for_shutdown(self):
        """Test waiting for global shutdown."""
        with patch("src.utils.shutdown.get_shutdown_manager") as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.shutdown_handler.wait_for_shutdown = AsyncMock()
            mock_get_manager.return_value = mock_manager

            await wait_for_shutdown()

            mock_get_manager.assert_called_once()
            mock_manager.shutdown_handler.wait_for_shutdown.assert_called_once()
