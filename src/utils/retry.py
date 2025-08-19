"""Retry mechanism with exponential backoff for resilient operations.

Provides configurable retry logic with various backoff strategies
to handle transient failures gracefully.
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import TypeVar


logger = logging.getLogger(__name__)

T = TypeVar("T")


class BackoffStrategy(Enum):
    """Backoff strategies for retry logic."""

    FIXED = "fixed"  # Fixed delay between retries
    LINEAR = "linear"  # Linear increase in delay
    EXPONENTIAL = "exponential"  # Exponential increase in delay
    FIBONACCI = "fibonacci"  # Fibonacci sequence delays
    DECORRELATED = "decorrelated"  # Decorrelated jitter


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3  # Maximum number of attempts
    initial_delay: float = 1.0  # Initial delay in seconds
    max_delay: float = 60.0  # Maximum delay between retries
    exponential_base: float = 2.0  # Base for exponential backoff
    jitter: bool = True  # Add randomization to delays
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    retry_on: type[Exception] | tuple = Exception  # Exceptions to retry on
    retry_if: Callable[[Exception], bool] | None = None  # Custom retry condition
    on_retry: Callable[[Exception, int], None] | None = None  # Callback on retry


@dataclass
class RetryStats:
    """Statistics for retry operations."""

    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_retries: int = 0
    last_exception: Exception | None = None
    retry_history: list[float] = None

    def __post_init__(self):
        if self.retry_history is None:
            self.retry_history = []

    def record_attempt(self, success: bool, retries: int = 0):
        """Record an attempt."""
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
        else:
            self.failed_attempts += 1
        self.total_retries += retries

    def record_retry(self, delay: float):
        """Record a retry with delay."""
        self.retry_history.append(delay)

    def get_success_rate(self) -> float:
        """Get success rate."""
        if self.total_attempts == 0:
            return 0.0
        return self.successful_attempts / self.total_attempts

    def get_average_retries(self) -> float:
        """Get average number of retries per attempt."""
        if self.total_attempts == 0:
            return 0.0
        return self.total_retries / self.total_attempts


class RetryHandler:
    """Handler for retry logic with configurable backoff."""

    def __init__(self, config: RetryConfig | None = None):
        """Initialize retry handler."""
        self.config = config or RetryConfig()
        self.stats = RetryStats()
        self._fibonacci_cache = [0, 1]

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number.

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        if self.config.strategy == BackoffStrategy.FIXED:
            delay = self.config.initial_delay

        elif self.config.strategy == BackoffStrategy.LINEAR:
            delay = self.config.initial_delay * (attempt + 1)

        elif self.config.strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.initial_delay * (self.config.exponential_base**attempt)

        elif self.config.strategy == BackoffStrategy.FIBONACCI:
            delay = self.config.initial_delay * self._get_fibonacci(attempt)

        elif self.config.strategy == BackoffStrategy.DECORRELATED:
            # Decorrelated jitter: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
            if attempt == 0:
                delay = self.config.initial_delay
            else:
                prev_delay = (
                    self.stats.retry_history[-1]
                    if self.stats.retry_history
                    else self.config.initial_delay
                )
                delay = random.uniform(self.config.initial_delay, prev_delay * 3)

        else:
            delay = self.config.initial_delay

        # Apply maximum delay cap
        delay = min(delay, self.config.max_delay)

        # Apply jitter if enabled
        if self.config.jitter and self.config.strategy != BackoffStrategy.DECORRELATED:
            # Add ±25% jitter
            jitter_range = delay * 0.25
            delay = delay + random.uniform(-jitter_range, jitter_range)

        return max(0, delay)  # Ensure non-negative

    def _get_fibonacci(self, n: int) -> int:
        """Get nth Fibonacci number (cached)."""
        while len(self._fibonacci_cache) <= n:
            self._fibonacci_cache.append(self._fibonacci_cache[-1] + self._fibonacci_cache[-2])
        return self._fibonacci_cache[n]

    def should_retry(self, exception: Exception) -> bool:
        """Check if exception should trigger retry.

        Args:
            exception: Exception that occurred

        Returns:
            True if should retry
        """
        # Check exception type
        if not isinstance(exception, self.config.retry_on):
            return False

        # Check custom condition
        if self.config.retry_if:
            return self.config.retry_if(exception)

        return True

    async def execute_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute async function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        retries = 0

        for attempt in range(self.config.max_attempts):
            try:
                result = await func(*args, **kwargs)
                self.stats.record_attempt(True, retries)
                return result

            except Exception as e:
                last_exception = e
                self.stats.last_exception = e

                # Check if we should retry
                if not self.should_retry(e):
                    self.stats.record_attempt(False, retries)
                    raise

                # Check if we have attempts left
                if attempt >= self.config.max_attempts - 1:
                    self.stats.record_attempt(False, retries)
                    logger.error(f"Retry exhausted after {self.config.max_attempts} attempts: {e}")
                    raise

                # Calculate delay
                delay = self.calculate_delay(attempt)
                self.stats.record_retry(delay)
                retries += 1

                # Log retry
                logger.warning(
                    f"Retry attempt {attempt + 1}/{self.config.max_attempts} "
                    f"after {delay:.2f}s delay: {e}"
                )

                # Call retry callback if provided
                if self.config.on_retry:
                    self.config.on_retry(e, attempt + 1)

                # Wait before retry
                await asyncio.sleep(delay)

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception

    def execute_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute sync function with retry logic.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        retries = 0

        for attempt in range(self.config.max_attempts):
            try:
                result = func(*args, **kwargs)
                self.stats.record_attempt(True, retries)
                return result

            except Exception as e:
                last_exception = e
                self.stats.last_exception = e

                # Check if we should retry
                if not self.should_retry(e):
                    self.stats.record_attempt(False, retries)
                    raise

                # Check if we have attempts left
                if attempt >= self.config.max_attempts - 1:
                    self.stats.record_attempt(False, retries)
                    logger.error(f"Retry exhausted after {self.config.max_attempts} attempts: {e}")
                    raise

                # Calculate delay
                delay = self.calculate_delay(attempt)
                self.stats.record_retry(delay)
                retries += 1

                # Log retry
                logger.warning(
                    f"Retry attempt {attempt + 1}/{self.config.max_attempts} "
                    f"after {delay:.2f}s delay: {e}"
                )

                # Call retry callback if provided
                if self.config.on_retry:
                    self.config.on_retry(e, attempt + 1)

                # Wait before retry
                time.sleep(delay)

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception


# Decorator for retry logic
def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
    retry_on: type[Exception] | tuple = Exception,
    retry_if: Callable[[Exception], bool] | None = None,
    on_retry: Callable[[Exception, int], None] | None = None,
):
    """Decorator to add retry logic to a function.

    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        jitter: Add randomization to delays
        strategy: Backoff strategy to use
        retry_on: Exception types to retry on
        retry_if: Custom condition for retry
        on_retry: Callback function on retry

    Example:
        @retry(max_attempts=5, initial_delay=2.0)
        async def fetch_data():
            # Make network call
            pass
    """

    def decorator(func: Callable) -> Callable:
        config = RetryConfig(
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            max_delay=max_delay,
            exponential_base=exponential_base,
            jitter=jitter,
            strategy=strategy,
            retry_on=retry_on,
            retry_if=retry_if,
            on_retry=on_retry,
        )
        handler = RetryHandler(config)

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await handler.execute_async(func, *args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return handler.execute_sync(func, *args, **kwargs)

        return sync_wrapper

    return decorator


# Convenience decorators for common patterns
def retry_on_network_error(max_attempts: int = 5):
    """Retry decorator for network errors."""
    return retry(
        max_attempts=max_attempts,
        initial_delay=1.0,
        strategy=BackoffStrategy.EXPONENTIAL,
        retry_on=(ConnectionError, TimeoutError, OSError),
    )


def retry_on_timeout(max_attempts: int = 3, timeout_delay: float = 5.0):
    """Retry decorator for timeout errors."""
    return retry(
        max_attempts=max_attempts,
        initial_delay=timeout_delay,
        strategy=BackoffStrategy.FIXED,
        retry_on=TimeoutError,
    )


def retry_with_fibonacci(max_attempts: int = 5):
    """Retry decorator using Fibonacci backoff."""
    return retry(max_attempts=max_attempts, initial_delay=1.0, strategy=BackoffStrategy.FIBONACCI)


def retry_with_decorrelated_jitter(max_attempts: int = 5):
    """Retry decorator using decorrelated jitter."""
    return retry(
        max_attempts=max_attempts, initial_delay=1.0, strategy=BackoffStrategy.DECORRELATED
    )


class RetryManager:
    """Manager for retry handlers with shared configuration."""

    def __init__(self, default_config: RetryConfig | None = None):
        """Initialize retry manager."""
        self.default_config = default_config or RetryConfig()
        self._handlers: dict[str, RetryHandler] = {}

    def create_handler(self, name: str, config: RetryConfig | None = None) -> RetryHandler:
        """Create or get a retry handler."""
        if name not in self._handlers:
            handler_config = config or self.default_config
            self._handlers[name] = RetryHandler(handler_config)
        return self._handlers[name]

    def get_handler(self, name: str) -> RetryHandler | None:
        """Get retry handler by name."""
        return self._handlers.get(name)

    def get_stats(self) -> dict[str, dict]:
        """Get statistics for all handlers."""
        stats = {}
        for name, handler in self._handlers.items():
            handler_stats = handler.stats
            stats[name] = {
                "total_attempts": handler_stats.total_attempts,
                "successful_attempts": handler_stats.successful_attempts,
                "failed_attempts": handler_stats.failed_attempts,
                "total_retries": handler_stats.total_retries,
                "success_rate": handler_stats.get_success_rate(),
                "average_retries": handler_stats.get_average_retries(),
            }
        return stats

    def reset_stats(self):
        """Reset statistics for all handlers."""
        for handler in self._handlers.values():
            handler.stats = RetryStats()


# Global retry manager
_retry_manager = RetryManager()


def get_retry_handler(name: str, config: RetryConfig | None = None) -> RetryHandler:
    """Get or create a retry handler."""
    return _retry_manager.create_handler(name, config)


def get_retry_manager() -> RetryManager:
    """Get the global retry manager."""
    return _retry_manager
