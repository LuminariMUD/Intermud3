"""Graceful shutdown mechanism for the I3 Gateway.

Provides coordinated shutdown with proper cleanup of resources,
connection draining, and state persistence.
"""

import asyncio
import logging
import signal
import sys
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


logger = logging.getLogger(__name__)


class ShutdownPhase(Enum):
    """Phases of graceful shutdown."""

    RUNNING = "running"  # Normal operation
    DRAINING = "draining"  # Not accepting new connections
    CLOSING = "closing"  # Closing active connections
    CLEANUP = "cleanup"  # Cleaning up resources
    TERMINATED = "terminated"  # Shutdown complete


@dataclass
class ShutdownConfig:
    """Configuration for graceful shutdown."""

    drain_timeout: float = 30.0  # Time to wait for connections to drain
    close_timeout: float = 10.0  # Time to wait for connections to close
    cleanup_timeout: float = 5.0  # Time for cleanup operations
    force_timeout: float = 60.0  # Total time before forced shutdown
    save_state: bool = True  # Save state before shutdown
    notify_peers: bool = True  # Notify peers of shutdown


@dataclass
class ShutdownStats:
    """Statistics for shutdown process."""

    start_time: float | None = None
    end_time: float | None = None
    phase_times: dict[ShutdownPhase, float] = field(default_factory=dict)
    active_connections_start: int = 0
    active_connections_drained: int = 0
    active_connections_closed: int = 0
    cleanup_tasks_completed: int = 0
    cleanup_tasks_failed: int = 0
    forced_shutdown: bool = False

    def record_phase_start(self, phase: ShutdownPhase):
        """Record phase start time."""
        self.phase_times[phase] = time.time()

    def get_phase_duration(self, phase: ShutdownPhase) -> float | None:
        """Get duration of a phase."""
        if phase not in self.phase_times:
            return None
        start = self.phase_times[phase]

        # Find next phase or use end time
        phases = list(ShutdownPhase)
        phase_index = phases.index(phase)

        if phase_index < len(phases) - 1:
            next_phase = phases[phase_index + 1]
            if next_phase in self.phase_times:
                return self.phase_times[next_phase] - start

        if self.end_time:
            return self.end_time - start

        return time.time() - start

    def get_total_duration(self) -> float | None:
        """Get total shutdown duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        if self.start_time:
            return time.time() - self.start_time
        return None


class GracefulShutdown:
    """Manages graceful shutdown of the gateway.

    Features:
    - Phased shutdown process
    - Connection draining
    - State persistence
    - Resource cleanup
    - Timeout protection
    """

    def __init__(self, config: ShutdownConfig | None = None):
        """Initialize graceful shutdown manager."""
        self.config = config or ShutdownConfig()
        self.phase = ShutdownPhase.RUNNING
        self.stats = ShutdownStats()

        self._shutdown_event = asyncio.Event()
        self._shutdown_complete = asyncio.Event()
        self._handlers: list[Callable] = []
        self._cleanup_tasks: list[Callable] = []
        self._active_connections: list[Any] = []
        self._force_shutdown_task: asyncio.Task | None = None

        # Register signal handlers
        self._original_handlers = {}
        self._register_signal_handlers()

    def _register_signal_handlers(self):
        """Register signal handlers for shutdown."""
        signals = [signal.SIGTERM, signal.SIGINT]

        # Windows doesn't have SIGHUP
        if hasattr(signal, "SIGHUP"):
            signals.append(signal.SIGHUP)

        for sig in signals:
            try:
                # Save original handler
                self._original_handlers[sig] = signal.signal(sig, self._handle_signal)
            except Exception as e:
                logger.warning(f"Could not register handler for {sig}: {e}")

    def _handle_signal(self, signum: int, frame):
        """Handle shutdown signal."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")

        # Schedule shutdown in event loop
        asyncio.create_task(self.shutdown())

    def register_handler(self, handler: Callable):
        """Register a shutdown handler.

        Handler will be called during shutdown to perform cleanup.
        """
        self._handlers.append(handler)

    def register_cleanup(self, task: Callable):
        """Register a cleanup task.

        Task will be called during cleanup phase.
        """
        self._cleanup_tasks.append(task)

    def register_connection(self, connection: Any):
        """Register an active connection."""
        self._active_connections.append(connection)

    def unregister_connection(self, connection: Any):
        """Unregister a connection."""
        if connection in self._active_connections:
            self._active_connections.remove(connection)

    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self.phase != ShutdownPhase.RUNNING

    def should_accept_connections(self) -> bool:
        """Check if new connections should be accepted."""
        return self.phase == ShutdownPhase.RUNNING

    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    async def shutdown(self, reason: str = "Manual shutdown"):
        """Initiate graceful shutdown.

        Args:
            reason: Reason for shutdown
        """
        if self.is_shutting_down():
            logger.warning("Shutdown already in progress")
            return

        logger.info(f"Starting graceful shutdown: {reason}")
        self.stats.start_time = time.time()
        self.stats.active_connections_start = len(self._active_connections)

        # Signal shutdown
        self._shutdown_event.set()

        # Start force shutdown timer
        self._force_shutdown_task = asyncio.create_task(self._force_shutdown_timer())

        try:
            # Phase 1: Draining
            await self._drain_connections()

            # Phase 2: Closing
            await self._close_connections()

            # Phase 3: Cleanup
            await self._cleanup_resources()

            # Phase 4: Terminated
            self.phase = ShutdownPhase.TERMINATED
            self.stats.record_phase_start(ShutdownPhase.TERMINATED)

        except asyncio.CancelledError:
            logger.warning("Shutdown cancelled")
            raise

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        finally:
            # Cancel force shutdown timer
            if self._force_shutdown_task:
                self._force_shutdown_task.cancel()

            self.stats.end_time = time.time()
            self._shutdown_complete.set()

            # Log shutdown statistics
            self._log_shutdown_stats()

    async def _drain_connections(self):
        """Phase 1: Stop accepting new connections and drain existing."""
        logger.info("Phase 1: Draining connections")
        self.phase = ShutdownPhase.DRAINING
        self.stats.record_phase_start(ShutdownPhase.DRAINING)

        # Notify handlers to stop accepting new connections
        for handler in self._handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler("drain")
                else:
                    handler("drain")
            except Exception as e:
                logger.error(f"Handler error during drain: {e}")

        # Wait for connections to drain naturally
        start_time = time.time()
        initial_count = len(self._active_connections)

        while self._active_connections and time.time() - start_time < self.config.drain_timeout:

            current_count = len(self._active_connections)
            logger.info(f"Draining: {current_count}/{initial_count} connections active")

            # Check for progress
            if current_count < initial_count:
                initial_count = current_count
                start_time = time.time()  # Reset timeout on progress

            await asyncio.sleep(1)

        self.stats.active_connections_drained = len(self._active_connections)
        logger.info(
            f"Drain complete: {self.stats.active_connections_drained} connections remaining"
        )

    async def _close_connections(self):
        """Phase 2: Close remaining connections."""
        logger.info("Phase 2: Closing connections")
        self.phase = ShutdownPhase.CLOSING
        self.stats.record_phase_start(ShutdownPhase.CLOSING)

        if not self._active_connections:
            logger.info("No active connections to close")
            return

        # Notify connections to close
        close_tasks = []
        for connection in self._active_connections[:]:  # Copy list
            try:
                if hasattr(connection, "close"):
                    if asyncio.iscoroutinefunction(connection.close):
                        close_tasks.append(connection.close())
                    else:
                        connection.close()
                self._active_connections.remove(connection)
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

        # Wait for close tasks
        if close_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*close_tasks, return_exceptions=True),
                    timeout=self.config.close_timeout,
                )
            except TimeoutError:
                logger.warning("Timeout waiting for connections to close")

        self.stats.active_connections_closed = initial_count - len(self._active_connections)
        logger.info(f"Closed {self.stats.active_connections_closed} connections")

    async def _cleanup_resources(self):
        """Phase 3: Clean up resources."""
        logger.info("Phase 3: Cleaning up resources")
        self.phase = ShutdownPhase.CLEANUP
        self.stats.record_phase_start(ShutdownPhase.CLEANUP)

        # Run cleanup tasks
        cleanup_tasks = []
        for task in self._cleanup_tasks:
            try:
                if asyncio.iscoroutinefunction(task):
                    cleanup_tasks.append(task())
                else:
                    task()
                    self.stats.cleanup_tasks_completed += 1
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
                self.stats.cleanup_tasks_failed += 1

        # Wait for async cleanup tasks
        if cleanup_tasks:
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=self.config.cleanup_timeout,
                )

                for result in results:
                    if isinstance(result, Exception):
                        self.stats.cleanup_tasks_failed += 1
                    else:
                        self.stats.cleanup_tasks_completed += 1

            except TimeoutError:
                logger.warning("Timeout during cleanup")
                self.stats.cleanup_tasks_failed += len(cleanup_tasks)

        # Restore original signal handlers
        for sig, handler in self._original_handlers.items():
            try:
                signal.signal(sig, handler)
            except Exception as e:
                logger.warning(f"Could not restore handler for {sig}: {e}")

        logger.info(
            f"Cleanup complete: {self.stats.cleanup_tasks_completed} tasks completed, "
            f"{self.stats.cleanup_tasks_failed} failed"
        )

    async def _force_shutdown_timer(self):
        """Force shutdown after timeout."""
        try:
            await asyncio.sleep(self.config.force_timeout)

            logger.error(f"Force shutdown after {self.config.force_timeout}s timeout")
            self.stats.forced_shutdown = True

            # Force exit
            sys.exit(1)

        except asyncio.CancelledError:
            # Normal cancellation when shutdown completes
            pass

    def _log_shutdown_stats(self):
        """Log shutdown statistics."""
        total_duration = self.stats.get_total_duration()

        logger.info("=" * 60)
        logger.info("SHUTDOWN STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total Duration: {total_duration:.2f}s")
        logger.info(f"Forced Shutdown: {self.stats.forced_shutdown}")
        logger.info(f"Connections at Start: {self.stats.active_connections_start}")
        logger.info(
            f"Connections Drained: {self.stats.active_connections_start - self.stats.active_connections_drained}"
        )
        logger.info(f"Connections Closed: {self.stats.active_connections_closed}")
        logger.info(
            f"Cleanup Tasks: {self.stats.cleanup_tasks_completed} completed, "
            f"{self.stats.cleanup_tasks_failed} failed"
        )

        logger.info("\nPhase Durations:")
        for phase in ShutdownPhase:
            duration = self.stats.get_phase_duration(phase)
            if duration is not None:
                logger.info(f"  {phase.value}: {duration:.2f}s")

        logger.info("=" * 60)


class ShutdownManager:
    """Manager for coordinating shutdown across components."""

    def __init__(self, config: ShutdownConfig | None = None):
        """Initialize shutdown manager."""
        self.config = config or ShutdownConfig()
        self.shutdown_handler = GracefulShutdown(self.config)
        self._components: dict[str, Any] = {}

    def register_component(self, name: str, component: Any):
        """Register a component for shutdown coordination."""
        self._components[name] = component

        # Register cleanup if component has cleanup method
        if hasattr(component, "cleanup"):
            self.shutdown_handler.register_cleanup(component.cleanup)
        elif hasattr(component, "close"):
            self.shutdown_handler.register_cleanup(component.close)

    async def shutdown(self, reason: str = "Shutdown requested"):
        """Initiate coordinated shutdown."""
        logger.info(f"Shutdown manager: {reason}")

        # Save state if configured
        if self.config.save_state:
            await self._save_state()

        # Notify peers if configured
        if self.config.notify_peers:
            await self._notify_peers()

        # Execute graceful shutdown
        await self.shutdown_handler.shutdown(reason)

    async def _save_state(self):
        """Save component states before shutdown."""
        logger.info("Saving component states")

        for name, component in self._components.items():
            try:
                if hasattr(component, "save_state"):
                    if asyncio.iscoroutinefunction(component.save_state):
                        await component.save_state()
                    else:
                        component.save_state()
                    logger.debug(f"Saved state for {name}")
            except Exception as e:
                logger.error(f"Failed to save state for {name}: {e}")

    async def _notify_peers(self):
        """Notify peer systems of shutdown."""
        logger.info("Notifying peers of shutdown")

        # Send shutdown notifications
        for name, component in self._components.items():
            try:
                if hasattr(component, "notify_shutdown"):
                    if asyncio.iscoroutinefunction(component.notify_shutdown):
                        await component.notify_shutdown()
                    else:
                        component.notify_shutdown()
                    logger.debug(f"Notified shutdown for {name}")
            except Exception as e:
                logger.error(f"Failed to notify shutdown for {name}: {e}")

    @asynccontextmanager
    async def shutdown_context(self):
        """Context manager for automatic shutdown handling."""
        try:
            yield self
        finally:
            await self.shutdown("Context exit")


# Global shutdown manager
_shutdown_manager: ShutdownManager | None = None


def get_shutdown_manager(config: ShutdownConfig | None = None) -> ShutdownManager:
    """Get or create the global shutdown manager."""
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = ShutdownManager(config)
    return _shutdown_manager


def register_shutdown_handler(handler: Callable):
    """Register a global shutdown handler."""
    manager = get_shutdown_manager()
    manager.shutdown_handler.register_handler(handler)


def register_cleanup_task(task: Callable):
    """Register a global cleanup task."""
    manager = get_shutdown_manager()
    manager.shutdown_handler.register_cleanup(task)


async def wait_for_shutdown():
    """Wait for shutdown signal."""
    manager = get_shutdown_manager()
    await manager.shutdown_handler.wait_for_shutdown()
