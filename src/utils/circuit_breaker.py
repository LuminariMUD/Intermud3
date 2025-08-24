"""Circuit breaker implementation for fault tolerance.

Provides circuit breaker pattern to prevent cascading failures
and allow systems to recover gracefully from errors.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar


logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes in half-open before closing
    timeout: float = 60.0  # Seconds before trying half-open
    expected_exception: type = Exception  # Exception types to catch


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: float | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    state_changes: list = field(default_factory=list)

    def record_success(self):
        """Record a successful call."""
        self.total_calls += 1
        self.successful_calls += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0

    def record_failure(self):
        """Record a failed call."""
        self.total_calls += 1
        self.failed_calls += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = time.time()

    def record_rejection(self):
        """Record a rejected call."""
        self.rejected_calls += 1

    def reset(self):
        """Reset consecutive counters."""
        self.consecutive_failures = 0
        self.consecutive_successes = 0

    def get_error_rate(self) -> float:
        """Get the error rate."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls


class CircuitBreaker(Generic[T]):
    """Circuit breaker for protecting against cascading failures.

    The circuit breaker has three states:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Too many failures, calls are rejected
    - HALF_OPEN: Testing if service has recovered
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        """Initialize circuit breaker."""
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
        self._half_open_timer: asyncio.Task | None = None

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function through circuit breaker.

        Args:
            func: Function to call
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            CircuitOpenError: If circuit is open
            Original exception: If function fails
        """
        async with self._lock:
            # Check circuit state
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    await self._transition_to_half_open()
                else:
                    self.stats.record_rejection()
                    raise CircuitOpenError(f"Circuit breaker '{self.name}' is OPEN")

        # Execute function
        try:
            # Handle both sync and async functions
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._on_success()
            return result

        except self.config.expected_exception:
            await self._on_failure()
            raise

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            self.stats.record_success()

            if self.state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    await self._transition_to_closed()

    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.stats.record_failure()

            if self.state == CircuitState.CLOSED:
                if self.stats.consecutive_failures >= self.config.failure_threshold:
                    await self._transition_to_open()

            elif self.state == CircuitState.HALF_OPEN:
                await self._transition_to_open()

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset circuit."""
        if self.stats.last_failure_time is None:
            return True

        time_since_failure = time.time() - self.stats.last_failure_time
        return time_since_failure >= self.config.timeout

    async def _transition_to_open(self):
        """Transition to OPEN state."""
        logger.warning(f"Circuit breaker '{self.name}' transitioning to OPEN")
        self.state = CircuitState.OPEN
        self.stats.state_changes.append((CircuitState.OPEN, time.time()))

        # Schedule transition to half-open
        if self._half_open_timer:
            self._half_open_timer.cancel()

        self._half_open_timer = asyncio.create_task(self._schedule_half_open())

    async def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
        self.state = CircuitState.HALF_OPEN
        self.stats.state_changes.append((CircuitState.HALF_OPEN, time.time()))
        self.stats.reset()

    async def _transition_to_closed(self):
        """Transition to CLOSED state."""
        logger.info(f"Circuit breaker '{self.name}' transitioning to CLOSED")
        self.state = CircuitState.CLOSED
        self.stats.state_changes.append((CircuitState.CLOSED, time.time()))
        self.stats.reset()

    async def _schedule_half_open(self):
        """Schedule transition to half-open after timeout."""
        await asyncio.sleep(self.config.timeout)
        async with self._lock:
            if self.state == CircuitState.OPEN:
                await self._transition_to_half_open()

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state

    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self.stats

    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    def is_open(self) -> bool:
        """Check if circuit is open (failing)."""
        return self.state == CircuitState.OPEN

    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing)."""
        return self.state == CircuitState.HALF_OPEN

    async def reset(self):
        """Manually reset circuit breaker."""
        async with self._lock:
            await self._transition_to_closed()

    async def trip(self):
        """Manually trip circuit breaker to open."""
        async with self._lock:
            await self._transition_to_open()


class CircuitOpenError(Exception):
    """Exception raised when circuit breaker is open."""


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""

    def __init__(self):
        """Initialize circuit breaker manager."""
        self._breakers: dict[str, CircuitBreaker] = {}

    def create_breaker(
        self, name: str, config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        """Create or get a circuit breaker.

        Args:
            name: Breaker name
            config: Breaker configuration

        Returns:
            Circuit breaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get_breaker(self, name: str) -> CircuitBreaker | None:
        """Get circuit breaker by name."""
        return self._breakers.get(name)

    def get_all_breakers(self) -> dict[str, CircuitBreaker]:
        """Get all circuit breakers."""
        return self._breakers.copy()

    def get_status(self) -> dict[str, dict]:
        """Get status of all circuit breakers."""
        status = {}
        for name, breaker in self._breakers.items():
            stats = breaker.get_stats()
            status[name] = {
                "state": breaker.get_state().value,
                "total_calls": stats.total_calls,
                "successful_calls": stats.successful_calls,
                "failed_calls": stats.failed_calls,
                "rejected_calls": stats.rejected_calls,
                "error_rate": stats.get_error_rate(),
                "consecutive_failures": stats.consecutive_failures,
                "consecutive_successes": stats.consecutive_successes,
            }
        return status

    async def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            await breaker.reset()

    async def check_health(self) -> tuple[bool, dict]:
        """Check health of all circuit breakers.

        Returns:
            Tuple of (all_healthy, status_dict)
        """
        status = self.get_status()
        all_healthy = all(self._breakers[name].is_closed() for name in self._breakers)
        return all_healthy, status


# Global circuit breaker manager
_manager = CircuitBreakerManager()


def get_circuit_breaker(name: str, config: CircuitBreakerConfig | None = None) -> CircuitBreaker:
    """Get or create a circuit breaker.

    Args:
        name: Circuit breaker name
        config: Configuration (used only on creation)

    Returns:
        Circuit breaker instance
    """
    return _manager.create_breaker(name, config)


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager."""
    return _manager


# Decorator for circuit breaker protection
def circuit_breaker(
    name: str | None = None,
    failure_threshold: int = 5,
    success_threshold: int = 2,
    timeout: float = 60.0,
    expected_exception: type = Exception,
):
    """Decorator to add circuit breaker protection to a function.

    Args:
        name: Circuit breaker name (defaults to function name)
        failure_threshold: Failures before opening
        success_threshold: Successes before closing
        timeout: Seconds before trying half-open
        expected_exception: Exception types to catch

    Example:
        @circuit_breaker(failure_threshold=3, timeout=30)
        async def call_external_service():
            # Make external call
            pass
    """

    def decorator(func: Callable) -> Callable:
        breaker_name = name or f"{func.__module__}.{func.__name__}"
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout,
            expected_exception=expected_exception,
        )
        breaker = get_circuit_breaker(breaker_name, config)

        async def async_wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            # For sync functions, run in event loop
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(breaker.call(func, *args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
