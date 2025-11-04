"""Tests for retry mechanism implementation."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.utils.retry import (
    BackoffStrategy,
    RetryConfig,
    RetryHandler,
    RetryManager,
    RetryStats,
    get_retry_handler,
    get_retry_manager,
    retry,
    retry_on_network_error,
    retry_on_timeout,
    retry_with_decorrelated_jitter,
    retry_with_fibonacci,
)


class TestBackoffStrategy:
    """Test BackoffStrategy enum."""

    def test_backoff_strategy_values(self):
        """Test backoff strategy enum values."""
        assert BackoffStrategy.FIXED.value == "fixed"
        assert BackoffStrategy.LINEAR.value == "linear"
        assert BackoffStrategy.EXPONENTIAL.value == "exponential"
        assert BackoffStrategy.FIBONACCI.value == "fibonacci"
        assert BackoffStrategy.DECORRELATED.value == "decorrelated"


class TestRetryConfig:
    """Test RetryConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert config.strategy == BackoffStrategy.EXPONENTIAL
        assert config.retry_on == Exception
        assert config.retry_if is None
        assert config.on_retry is None

    def test_custom_config(self):
        """Test custom configuration values."""

        def custom_retry_if(exc):
            return isinstance(exc, ValueError)

        def custom_on_retry(exc, attempt):
            pass

        config = RetryConfig(
            max_attempts=5,
            initial_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=False,
            strategy=BackoffStrategy.LINEAR,
            retry_on=ValueError,
            retry_if=custom_retry_if,
            on_retry=custom_on_retry,
        )

        assert config.max_attempts == 5
        assert config.initial_delay == 2.0
        assert config.max_delay == 120.0
        assert config.exponential_base == 3.0
        assert config.jitter is False
        assert config.strategy == BackoffStrategy.LINEAR
        assert config.retry_on == ValueError
        assert config.retry_if == custom_retry_if
        assert config.on_retry == custom_on_retry


class TestRetryStats:
    """Test RetryStats dataclass."""

    def test_initial_stats(self):
        """Test initial statistics values."""
        stats = RetryStats()

        assert stats.total_attempts == 0
        assert stats.successful_attempts == 0
        assert stats.failed_attempts == 0
        assert stats.total_retries == 0
        assert stats.last_exception is None
        assert stats.retry_history == []

    def test_record_attempt_success(self):
        """Test recording successful attempt."""
        stats = RetryStats()

        stats.record_attempt(True, retries=2)

        assert stats.total_attempts == 1
        assert stats.successful_attempts == 1
        assert stats.failed_attempts == 0
        assert stats.total_retries == 2

    def test_record_attempt_failure(self):
        """Test recording failed attempt."""
        stats = RetryStats()

        stats.record_attempt(False, retries=3)

        assert stats.total_attempts == 1
        assert stats.successful_attempts == 0
        assert stats.failed_attempts == 1
        assert stats.total_retries == 3

    def test_record_retry(self):
        """Test recording retry delay."""
        stats = RetryStats()

        stats.record_retry(1.5)
        stats.record_retry(3.0)

        assert stats.retry_history == [1.5, 3.0]

    def test_get_success_rate(self):
        """Test success rate calculation."""
        stats = RetryStats()

        # No attempts
        assert stats.get_success_rate() == 0.0

        # Mixed results
        stats.record_attempt(True)
        stats.record_attempt(False)
        stats.record_attempt(True)

        assert stats.get_success_rate() == 2.0 / 3.0

    def test_get_average_retries(self):
        """Test average retries calculation."""
        stats = RetryStats()

        # No attempts
        assert stats.get_average_retries() == 0.0

        # With retries
        stats.record_attempt(True, retries=1)
        stats.record_attempt(False, retries=3)

        assert stats.get_average_retries() == 2.0


class TestRetryHandler:
    """Test RetryHandler class."""

    def test_handler_initialization(self):
        """Test retry handler initialization."""
        config = RetryConfig(max_attempts=5)
        handler = RetryHandler(config)

        assert handler.config == config
        assert isinstance(handler.stats, RetryStats)
        assert handler._fibonacci_cache == [0, 1]

    def test_handler_default_config(self):
        """Test handler with default configuration."""
        handler = RetryHandler()

        assert isinstance(handler.config, RetryConfig)
        assert handler.config.max_attempts == 3

    def test_calculate_delay_fixed(self):
        """Test fixed delay calculation."""
        config = RetryConfig(strategy=BackoffStrategy.FIXED, initial_delay=2.0, jitter=False)
        handler = RetryHandler(config)

        assert handler.calculate_delay(0) == 2.0
        assert handler.calculate_delay(1) == 2.0
        assert handler.calculate_delay(5) == 2.0

    def test_calculate_delay_linear(self):
        """Test linear delay calculation."""
        config = RetryConfig(strategy=BackoffStrategy.LINEAR, initial_delay=1.0, jitter=False)
        handler = RetryHandler(config)

        assert handler.calculate_delay(0) == 1.0
        assert handler.calculate_delay(1) == 2.0
        assert handler.calculate_delay(2) == 3.0
        assert handler.calculate_delay(4) == 5.0

    def test_calculate_delay_exponential(self):
        """Test exponential delay calculation."""
        config = RetryConfig(
            strategy=BackoffStrategy.EXPONENTIAL,
            initial_delay=1.0,
            exponential_base=2.0,
            jitter=False,
        )
        handler = RetryHandler(config)

        assert handler.calculate_delay(0) == 1.0
        assert handler.calculate_delay(1) == 2.0
        assert handler.calculate_delay(2) == 4.0
        assert handler.calculate_delay(3) == 8.0

    def test_calculate_delay_fibonacci(self):
        """Test Fibonacci delay calculation."""
        config = RetryConfig(strategy=BackoffStrategy.FIBONACCI, initial_delay=1.0, jitter=False)
        handler = RetryHandler(config)

        assert handler.calculate_delay(0) == 0.0  # F(0) = 0
        assert handler.calculate_delay(1) == 1.0  # F(1) = 1
        assert handler.calculate_delay(2) == 1.0  # F(2) = 1
        assert handler.calculate_delay(3) == 2.0  # F(3) = 2
        assert handler.calculate_delay(4) == 3.0  # F(4) = 3
        assert handler.calculate_delay(5) == 5.0  # F(5) = 5

    @patch("random.uniform")
    def test_calculate_delay_decorrelated(self, mock_uniform):
        """Test decorrelated jitter delay calculation."""
        mock_uniform.return_value = 3.0

        config = RetryConfig(strategy=BackoffStrategy.DECORRELATED, initial_delay=1.0)
        handler = RetryHandler(config)

        # First attempt uses initial delay
        assert handler.calculate_delay(0) == 1.0

        # Subsequent attempts use decorrelated jitter
        handler.stats.retry_history = [2.0]
        delay = handler.calculate_delay(1)

        mock_uniform.assert_called_with(1.0, 6.0)  # 2.0 * 3
        assert delay == 3.0

    def test_calculate_delay_max_delay_cap(self):
        """Test maximum delay cap."""
        config = RetryConfig(
            strategy=BackoffStrategy.EXPONENTIAL,
            initial_delay=10.0,
            exponential_base=10.0,
            max_delay=50.0,
            jitter=False,
        )
        handler = RetryHandler(config)

        # Should cap at max_delay
        assert handler.calculate_delay(3) == 50.0  # 10 * 10^3 = 10000, capped to 50

    @patch("random.uniform")
    def test_calculate_delay_with_jitter(self, mock_uniform):
        """Test delay calculation with jitter."""
        mock_uniform.return_value = 0.5  # Add 50% of jitter range

        config = RetryConfig(strategy=BackoffStrategy.FIXED, initial_delay=4.0, jitter=True)
        handler = RetryHandler(config)

        delay = handler.calculate_delay(0)

        # Jitter range is 25% of delay = 1.0
        # random.uniform(-1.0, 1.0) returns 0.5
        # Expected: 4.0 + 0.5 = 4.5
        mock_uniform.assert_called_with(-1.0, 1.0)
        assert delay == 4.5

    def test_calculate_delay_negative_protection(self):
        """Test protection against negative delays."""
        config = RetryConfig(strategy=BackoffStrategy.FIXED, initial_delay=1.0, jitter=True)
        handler = RetryHandler(config)

        with patch("random.uniform", return_value=-2.0):  # Large negative jitter
            delay = handler.calculate_delay(0)
            assert delay == 0.0  # Should be clamped to 0

    def test_get_fibonacci(self):
        """Test Fibonacci number calculation and caching."""
        handler = RetryHandler()

        # Test basic sequence
        assert handler._get_fibonacci(0) == 0
        assert handler._get_fibonacci(1) == 1
        assert handler._get_fibonacci(2) == 1
        assert handler._get_fibonacci(3) == 2
        assert handler._get_fibonacci(4) == 3
        assert handler._get_fibonacci(5) == 5
        assert handler._get_fibonacci(8) == 21

        # Test cache expansion
        initial_cache_len = len(handler._fibonacci_cache)
        handler._get_fibonacci(10)
        assert len(handler._fibonacci_cache) > initial_cache_len

    def test_should_retry_exception_type(self):
        """Test retry decision based on exception type."""
        config = RetryConfig(retry_on=ValueError)
        handler = RetryHandler(config)

        # Should retry on specified exception
        assert handler.should_retry(ValueError("test"))

        # Should not retry on different exception
        assert not handler.should_retry(TypeError("test"))

    def test_should_retry_exception_tuple(self):
        """Test retry decision with tuple of exception types."""
        config = RetryConfig(retry_on=(ValueError, TypeError))
        handler = RetryHandler(config)

        assert handler.should_retry(ValueError("test"))
        assert handler.should_retry(TypeError("test"))
        assert not handler.should_retry(RuntimeError("test"))

    def test_should_retry_custom_condition(self):
        """Test retry decision with custom condition."""

        def custom_condition(exc):
            return "retry" in str(exc)

        config = RetryConfig(retry_if=custom_condition)
        handler = RetryHandler(config)

        assert handler.should_retry(Exception("please retry"))
        assert not handler.should_retry(Exception("don't try again"))

    def test_should_retry_custom_condition_overrides_type(self):
        """Test that custom condition overrides exception type check."""

        def always_false(exc):
            return False

        config = RetryConfig(retry_on=Exception, retry_if=always_false)
        handler = RetryHandler(config)

        assert not handler.should_retry(Exception("test"))

    @pytest.mark.asyncio
    async def test_execute_async_success(self):
        """Test successful async execution."""
        handler = RetryHandler()
        mock_func = AsyncMock(return_value="success")

        result = await handler.execute_async(mock_func, "arg1", kwarg="kwarg1")

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg="kwarg1")
        assert handler.stats.total_attempts == 1
        assert handler.stats.successful_attempts == 1
        assert handler.stats.total_retries == 0

    @pytest.mark.asyncio
    async def test_execute_async_failure_no_retry(self):
        """Test async execution with non-retryable failure."""
        config = RetryConfig(retry_on=ValueError)
        handler = RetryHandler(config)
        mock_func = AsyncMock(side_effect=TypeError("not retryable"))

        with pytest.raises(TypeError):
            await handler.execute_async(mock_func)

        assert mock_func.call_count == 1
        assert handler.stats.total_attempts == 1
        assert handler.stats.failed_attempts == 1
        assert handler.stats.total_retries == 0

    @pytest.mark.asyncio
    async def test_execute_async_with_retries(self):
        """Test async execution with retries."""
        config = RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False)
        handler = RetryHandler(config)

        # Fail twice, then succeed
        mock_func = AsyncMock(side_effect=[ValueError("fail1"), ValueError("fail2"), "success"])

        with patch("asyncio.sleep") as mock_sleep:
            result = await handler.execute_async(mock_func)

        assert result == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2  # Two retry sleeps
        assert handler.stats.total_attempts == 1
        assert handler.stats.successful_attempts == 1
        assert handler.stats.total_retries == 2

    @pytest.mark.asyncio
    async def test_execute_async_exhausted_retries(self):
        """Test async execution with exhausted retries."""
        config = RetryConfig(max_attempts=2, initial_delay=0.01, jitter=False)
        handler = RetryHandler(config)
        mock_func = AsyncMock(side_effect=ValueError("always fails"))

        with patch("asyncio.sleep") as mock_sleep:
            with pytest.raises(ValueError, match="always fails"):
                await handler.execute_async(mock_func)

        assert mock_func.call_count == 2
        assert mock_sleep.call_count == 1  # One retry sleep
        assert handler.stats.total_attempts == 1
        assert handler.stats.failed_attempts == 1
        assert handler.stats.total_retries == 1

    @pytest.mark.asyncio
    async def test_execute_async_with_retry_callback(self):
        """Test async execution with retry callback."""
        callback_calls = []

        def on_retry_callback(exc, attempt):
            callback_calls.append((str(exc), attempt))

        config = RetryConfig(
            max_attempts=3, initial_delay=0.01, on_retry=on_retry_callback, jitter=False
        )
        handler = RetryHandler(config)
        mock_func = AsyncMock(side_effect=[ValueError("fail1"), ValueError("fail2"), "success"])

        with patch("asyncio.sleep"):
            result = await handler.execute_async(mock_func)

        assert result == "success"
        assert len(callback_calls) == 2
        assert callback_calls[0] == ("fail1", 1)
        assert callback_calls[1] == ("fail2", 2)

    def test_execute_sync_success(self):
        """Test successful sync execution."""
        handler = RetryHandler()
        mock_func = Mock(return_value="success")

        result = handler.execute_sync(mock_func, "arg1", kwarg="kwarg1")

        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg="kwarg1")
        assert handler.stats.total_attempts == 1
        assert handler.stats.successful_attempts == 1

    def test_execute_sync_with_retries(self):
        """Test sync execution with retries."""
        config = RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False)
        handler = RetryHandler(config)

        # Fail twice, then succeed
        mock_func = Mock(side_effect=[ValueError("fail1"), ValueError("fail2"), "success"])

        with patch("time.sleep") as mock_sleep:
            result = handler.execute_sync(mock_func)

        assert result == "success"
        assert mock_func.call_count == 3
        assert mock_sleep.call_count == 2
        assert handler.stats.total_attempts == 1
        assert handler.stats.successful_attempts == 1
        assert handler.stats.total_retries == 2

    def test_execute_sync_exhausted_retries(self):
        """Test sync execution with exhausted retries."""
        config = RetryConfig(max_attempts=2, initial_delay=0.01, jitter=False)
        handler = RetryHandler(config)
        mock_func = Mock(side_effect=ValueError("always fails"))

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(ValueError, match="always fails"):
                handler.execute_sync(mock_func)

        assert mock_func.call_count == 2
        assert mock_sleep.call_count == 1
        assert handler.stats.total_attempts == 1
        assert handler.stats.failed_attempts == 1


class TestRetryDecorator:
    """Test retry decorator."""

    @pytest.mark.asyncio
    async def test_async_function_decorator(self):
        """Test retry decorator on async function."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01, jitter=False)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"attempt {call_count}")
            return "success"

        with patch("asyncio.sleep"):
            result = await test_func()

        assert result == "success"
        assert call_count == 3

    def test_sync_function_decorator(self):
        """Test retry decorator on sync function."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01, jitter=False)
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"attempt {call_count}")
            return "success"

        with patch("time.sleep"):
            result = test_func()

        assert result == "success"
        assert call_count == 3

    def test_decorator_with_arguments(self):
        """Test retry decorator with function arguments."""

        @retry(max_attempts=2, initial_delay=0.01, jitter=False)
        def test_func(x, y, z=None):
            if x < 0:
                raise ValueError("negative")
            return x + y + (z or 0)

        with patch("time.sleep"):
            result = test_func(1, 2, z=3)

        assert result == 6

    @pytest.mark.asyncio
    async def test_decorator_custom_config(self):
        """Test retry decorator with custom configuration."""
        call_count = 0

        @retry(
            max_attempts=5,
            initial_delay=0.02,
            strategy=BackoffStrategy.LINEAR,
            retry_on=ValueError,
            jitter=False,
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ValueError("retry me")
            return call_count

        with patch("asyncio.sleep"):
            result = await test_func()

        assert result == 4
        assert call_count == 4

    def test_decorator_non_retryable_exception(self):
        """Test decorator with non-retryable exception."""

        @retry(max_attempts=3, retry_on=ValueError)
        def test_func():
            raise TypeError("not retryable")

        with pytest.raises(TypeError):
            test_func()


class TestConvenienceDecorators:
    """Test convenience decorator functions."""

    def test_retry_on_network_error(self):
        """Test network error retry decorator."""
        decorator = retry_on_network_error(max_attempts=4)

        # Should create proper retry configuration
        # Test by applying to a function and checking behavior
        call_count = 0

        @decorator
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("network issue")
            return "connected"

        with patch("time.sleep"):
            result = test_func()

        assert result == "connected"
        assert call_count == 3

    def test_retry_on_timeout(self):
        """Test timeout retry decorator."""
        decorator = retry_on_timeout(max_attempts=3, timeout_delay=2.0)

        call_count = 0

        @decorator
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("timeout")
            return "completed"

        with patch("time.sleep") as mock_sleep:
            result = test_func()

        assert result == "completed"
        assert call_count == 2
        # Check that sleep was called with approximately 2.0 (allowing for jitter)
        mock_sleep.assert_called_once()
        call_args = mock_sleep.call_args[0][0]
        assert 1.5 <= call_args <= 2.5  # Allow some jitter around 2.0

    def test_retry_with_fibonacci(self):
        """Test Fibonacci retry decorator."""
        decorator = retry_with_fibonacci(max_attempts=4)

        call_count = 0

        @decorator
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("fail")
            return "success"

        with patch("time.sleep"):
            result = test_func()

        assert result == "success"
        assert call_count == 3

    def test_retry_with_decorrelated_jitter(self):
        """Test decorrelated jitter retry decorator."""
        decorator = retry_with_decorrelated_jitter(max_attempts=3)

        call_count = 0

        @decorator
        def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("fail")
            return "success"

        with patch("time.sleep"):
            result = test_func()

        assert result == "success"
        assert call_count == 2


class TestRetryManager:
    """Test RetryManager class."""

    def test_manager_initialization(self):
        """Test retry manager initialization."""
        config = RetryConfig(max_attempts=5)
        manager = RetryManager(config)

        assert manager.default_config == config
        assert manager._handlers == {}

    def test_manager_default_config(self):
        """Test manager with default configuration."""
        manager = RetryManager()

        assert isinstance(manager.default_config, RetryConfig)
        assert manager.default_config.max_attempts == 3

    def test_create_handler(self):
        """Test creating retry handler."""
        manager = RetryManager()

        handler = manager.create_handler("test")

        assert isinstance(handler, RetryHandler)
        assert "test" in manager._handlers
        assert manager._handlers["test"] == handler

    def test_create_handler_with_config(self):
        """Test creating handler with custom config."""
        manager = RetryManager()
        config = RetryConfig(max_attempts=10)

        handler = manager.create_handler("test", config)

        assert handler.config == config
        assert handler.config.max_attempts == 10

    def test_create_handler_reuse_existing(self):
        """Test that create_handler reuses existing handlers."""
        manager = RetryManager()

        handler1 = manager.create_handler("test")
        handler2 = manager.create_handler("test")

        assert handler1 is handler2

    def test_get_handler(self):
        """Test getting retry handler."""
        manager = RetryManager()

        # Non-existent handler
        assert manager.get_handler("nonexistent") is None

        # Existing handler
        created_handler = manager.create_handler("test")
        retrieved_handler = manager.get_handler("test")

        assert retrieved_handler is created_handler

    def test_get_stats(self):
        """Test getting statistics for all handlers."""
        manager = RetryManager()

        # Create handlers and simulate some activity
        handler1 = manager.create_handler("handler1")
        handler2 = manager.create_handler("handler2")

        handler1.stats.record_attempt(True, retries=1)
        handler2.stats.record_attempt(False, retries=2)

        stats = manager.get_stats()

        assert "handler1" in stats
        assert "handler2" in stats
        assert stats["handler1"]["total_attempts"] == 1
        assert stats["handler1"]["successful_attempts"] == 1
        assert stats["handler2"]["failed_attempts"] == 1
        assert stats["handler2"]["total_retries"] == 2

    def test_reset_stats(self):
        """Test resetting statistics for all handlers."""
        manager = RetryManager()

        # Create handler and add some stats
        handler = manager.create_handler("test")
        handler.stats.record_attempt(True, retries=1)

        assert handler.stats.total_attempts == 1

        # Reset stats
        manager.reset_stats()

        assert handler.stats.total_attempts == 0


class TestGlobalRetryManager:
    """Test global retry manager functions."""

    def test_get_retry_handler(self):
        """Test getting retry handler from global manager."""
        handler = get_retry_handler("global_test")

        assert isinstance(handler, RetryHandler)

    def test_get_retry_handler_with_config(self):
        """Test getting handler with custom config from global manager."""
        config = RetryConfig(max_attempts=7)
        handler = get_retry_handler("global_test_config", config)

        assert handler.config.max_attempts == 7

    def test_get_retry_manager(self):
        """Test getting global retry manager."""
        manager = get_retry_manager()

        assert isinstance(manager, RetryManager)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_max_attempts(self):
        """Test behavior with zero max attempts."""
        config = RetryConfig(max_attempts=0)
        handler = RetryHandler(config)
        mock_func = Mock(return_value="success")

        # Should not execute function at all
        result = handler.execute_sync(mock_func)

        # Function should not be called and result should be None
        assert mock_func.call_count == 0
        assert result is None

    def test_negative_delays(self):
        """Test handling of negative initial delays."""
        config = RetryConfig(initial_delay=-1.0, jitter=False)
        handler = RetryHandler(config)

        delay = handler.calculate_delay(0)
        assert delay == 0.0  # Should be clamped to 0

    def test_very_large_delays(self):
        """Test handling of very large calculated delays."""
        config = RetryConfig(
            strategy=BackoffStrategy.EXPONENTIAL,
            initial_delay=1000.0,
            exponential_base=10.0,
            max_delay=5000.0,
            jitter=False,
        )
        handler = RetryHandler(config)

        delay = handler.calculate_delay(5)  # Would be 1000 * 10^5 = 100M
        assert delay == 5000.0  # Should be capped

    @pytest.mark.asyncio
    async def test_exception_in_retry_callback(self):
        """Test handling of exceptions in retry callback."""

        def failing_callback(exc, attempt):
            raise RuntimeError("callback failed")

        config = RetryConfig(
            max_attempts=3, initial_delay=0.01, on_retry=failing_callback, jitter=False
        )
        handler = RetryHandler(config)
        mock_func = AsyncMock(side_effect=[ValueError("fail"), "success"])

        # Callback exception should not prevent retry logic
        with patch("asyncio.sleep"):
            with pytest.raises(RuntimeError):  # Callback exception propagates
                await handler.execute_async(mock_func)

    def test_fibonacci_large_numbers(self):
        """Test Fibonacci calculation for large numbers."""
        handler = RetryHandler()

        # Test reasonable large Fibonacci numbers
        fib_20 = handler._get_fibonacci(20)
        assert fib_20 == 6765

        # Cache should expand appropriately
        assert len(handler._fibonacci_cache) >= 21

    @pytest.mark.asyncio
    async def test_async_function_with_sync_handler(self):
        """Test calling async function with sync execute method."""
        handler = RetryHandler()

        async def async_func():
            return "async result"

        # This should work since the handler will await the coroutine
        # But if the implementation doesn't handle this, it might fail
        # This test documents the expected behavior
        try:
            result = handler.execute_sync(async_func)
            # If this works, the result might be a coroutine object
            if asyncio.iscoroutine(result):
                result = await result
            assert result == "async result"
        except TypeError:
            # This is acceptable behavior - sync handler can't handle async functions
            pass

    def test_unknown_backoff_strategy(self):
        """Test handling of unknown backoff strategy."""
        # This test assumes the implementation has a fallback for unknown strategies
        # Disable jitter for exact comparison
        config = RetryConfig(jitter=False)
        handler = RetryHandler(config)

        # Temporarily modify strategy to unknown value
        handler.config.strategy = "unknown_strategy"

        # Should fall back to initial_delay
        delay = handler.calculate_delay(0)
        assert delay == handler.config.initial_delay

    def test_stats_retry_history_initialization(self):
        """Test that retry history is properly initialized."""
        stats = RetryStats()
        assert stats.retry_history is not None
        assert isinstance(stats.retry_history, list)
        assert len(stats.retry_history) == 0

        # Test that post_init works correctly
        stats2 = RetryStats(retry_history=None)
        assert stats2.retry_history is not None
        assert isinstance(stats2.retry_history, list)


class TestLoggingBehavior:
    """Test logging behavior during retry operations."""

    @pytest.mark.asyncio
    async def test_retry_logging(self):
        """Test that retry attempts are logged correctly."""
        config = RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False)
        handler = RetryHandler(config)
        mock_func = AsyncMock(side_effect=[ValueError("fail1"), ValueError("fail2"), "success"])

        with patch("asyncio.sleep"):
            with patch("src.utils.retry.logger") as mock_logger:
                result = await handler.execute_async(mock_func)

        assert result == "success"
        assert mock_logger.warning.call_count == 2

        # Check warning messages
        warning_calls = mock_logger.warning.call_args_list
        assert "Retry attempt 1/3" in warning_calls[0][0][0]
        assert "Retry attempt 2/3" in warning_calls[1][0][0]

    @pytest.mark.asyncio
    async def test_exhausted_retry_logging(self):
        """Test logging when retries are exhausted."""
        config = RetryConfig(max_attempts=2, initial_delay=0.01, jitter=False)
        handler = RetryHandler(config)
        mock_func = AsyncMock(side_effect=ValueError("always fails"))

        with patch("asyncio.sleep"):
            with patch("src.utils.retry.logger") as mock_logger:
                with pytest.raises(ValueError):
                    await handler.execute_async(mock_func)

        # Should log the exhaustion
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Retry exhausted after 2 attempts" in error_call
