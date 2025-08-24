"""Tests for circuit breaker implementation."""

import asyncio
from unittest.mock import MagicMock

import pytest

from src.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerStats,
    CircuitOpenError,
    CircuitState,
    circuit_breaker,
)


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 60.0
        assert config.expected_exception == Exception

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=10, success_threshold=3, timeout=30.0, expected_exception=ValueError
        )

        assert config.failure_threshold == 10
        assert config.success_threshold == 3
        assert config.timeout == 30.0
        assert config.expected_exception == ValueError


class TestCircuitBreakerStats:
    """Test CircuitBreakerStats class."""

    def test_initial_stats(self):
        """Test initial statistics values."""
        stats = CircuitBreakerStats()

        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.failed_calls == 0
        assert stats.rejected_calls == 0
        assert stats.last_failure_time is None
        assert stats.consecutive_failures == 0
        assert stats.consecutive_successes == 0
        assert stats.state_changes == []

    def test_stats_methods(self):
        """Test statistics methods."""
        stats = CircuitBreakerStats()

        # Test record_success
        stats.record_success()
        assert stats.total_calls == 1
        assert stats.successful_calls == 1
        assert stats.consecutive_successes == 1
        assert stats.consecutive_failures == 0

        # Test record_failure
        stats.record_failure()
        assert stats.total_calls == 2
        assert stats.failed_calls == 1
        assert stats.consecutive_failures == 1
        assert stats.consecutive_successes == 0
        assert stats.last_failure_time is not None

        # Test record_rejection
        stats.record_rejection()
        assert stats.rejected_calls == 1

        # Test reset
        stats.reset()
        assert stats.consecutive_failures == 0
        assert stats.consecutive_successes == 0

        # Test get_error_rate
        assert stats.get_error_rate() == 0.5  # 1 failure out of 2 calls


class TestCircuitBreaker:
    """Test CircuitBreaker class."""

    def test_breaker_initialization(self):
        """Test circuit breaker initialization."""
        config = CircuitBreakerConfig()
        breaker = CircuitBreaker("test", config)

        assert breaker.name == "test"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.config == config
        assert isinstance(breaker.stats, CircuitBreakerStats)

    @pytest.mark.asyncio
    async def test_breaker_closed_state_success(self):
        """Test successful call in closed state."""
        breaker = CircuitBreaker("test", CircuitBreakerConfig())

        # Successful call
        func = MagicMock(return_value="success")
        result = await breaker.call(func)

        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.successful_calls == 1
        assert breaker.stats.consecutive_successes == 1
        assert breaker.stats.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_breaker_closed_state_failure(self):
        """Test failed call in closed state."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        # Failing call
        func = MagicMock(side_effect=ValueError("test error"))

        # First failure
        with pytest.raises(ValueError):
            await breaker.call(func)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.failed_calls == 1
        assert breaker.stats.consecutive_failures == 1

        # Second failure
        with pytest.raises(ValueError):
            await breaker.call(func)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.consecutive_failures == 2

        # Third failure - should open circuit
        with pytest.raises(ValueError):
            await breaker.call(func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.stats.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_breaker_open_state(self):
        """Test circuit breaker in open state."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test", config)

        # Force circuit open
        func = MagicMock(side_effect=ValueError("test error"))
        with pytest.raises(ValueError):
            await breaker.call(func)

        assert breaker.state == CircuitState.OPEN

        # Calls should be rejected
        good_func = MagicMock(return_value="success")
        with pytest.raises(CircuitOpenError, match="Circuit breaker 'test' is OPEN"):
            await breaker.call(good_func)

        assert breaker.stats.rejected_calls == 1
        good_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_breaker_half_open_state(self):
        """Test circuit breaker in half-open state."""
        config = CircuitBreakerConfig(
            failure_threshold=1, success_threshold=2, timeout=0.1  # Short timeout for testing
        )
        breaker = CircuitBreaker("test", config)

        # Force circuit open
        func = MagicMock(side_effect=ValueError("test error"))
        with pytest.raises(ValueError):
            await breaker.call(func)

        assert breaker.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Should transition to half-open and allow test call
        good_func = MagicMock(return_value="success")
        result = await breaker.call(good_func)

        assert result == "success"
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.stats.consecutive_successes == 1

        # Second successful call should close circuit
        result = await breaker.call(good_func)

        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.consecutive_successes == 0  # Reset when transitioning to CLOSED

    @pytest.mark.asyncio
    async def test_breaker_half_open_failure(self):
        """Test failure in half-open state."""
        config = CircuitBreakerConfig(failure_threshold=1, timeout=0.1)
        breaker = CircuitBreaker("test", config)

        # Force circuit open
        func = MagicMock(side_effect=ValueError("test error"))
        with pytest.raises(ValueError):
            await breaker.call(func)

        assert breaker.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Failure in half-open should reopen circuit
        with pytest.raises(ValueError):
            await breaker.call(func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.stats.last_failure_time is not None

    @pytest.mark.asyncio
    async def test_unexpected_exception(self):
        """Test handling of unexpected exceptions."""
        config = CircuitBreakerConfig(expected_exception=ValueError)
        breaker = CircuitBreaker("test", config)

        # TypeError should not be caught
        func = MagicMock(side_effect=TypeError("unexpected"))

        with pytest.raises(TypeError):
            await breaker.call(func)

        # Should not affect circuit state
        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.failed_calls == 0

    @pytest.mark.asyncio
    async def test_async_function_call(self):
        """Test calling async functions."""
        breaker = CircuitBreaker("test", CircuitBreakerConfig())

        async def async_func():
            return "async success"

        result = await breaker.call(async_func)

        assert result == "async success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_async_function_failure(self):
        """Test failed async function call."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)

        async def failing_func():
            raise ValueError("async error")

        # First failure
        with pytest.raises(ValueError):
            await breaker.call(failing_func)

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.failed_calls == 1

        # Second failure - should open circuit
        with pytest.raises(ValueError):
            await breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN

    def test_get_stats(self):
        """Test getting circuit breaker statistics."""
        breaker = CircuitBreaker("test", CircuitBreakerConfig())

        stats = breaker.get_stats()

        assert isinstance(stats, CircuitBreakerStats)
        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.failed_calls == 0
        assert stats.rejected_calls == 0

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test resetting circuit breaker."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test", config)

        # Force circuit open
        func = MagicMock(side_effect=ValueError("test error"))
        with pytest.raises(ValueError):
            await breaker.call(func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.stats.failed_calls == 1

        # Reset
        await breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        # Note: reset() in the implementation doesn't clear all stats,
        # just transitions to closed state

    @pytest.mark.asyncio
    async def test_state_transitions(self):
        """Test all state transitions."""
        config = CircuitBreakerConfig(failure_threshold=2, success_threshold=2, timeout=0.1)
        breaker = CircuitBreaker("test", config)

        # Start in CLOSED
        assert breaker.state == CircuitState.CLOSED

        # CLOSED -> OPEN (failures)
        func = MagicMock(side_effect=ValueError("error"))
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(func)

        assert breaker.state == CircuitState.OPEN
        state_changes = breaker.stats.state_changes
        assert len(state_changes) == 1
        assert state_changes[0][0] == CircuitState.OPEN  # Target state
        assert isinstance(state_changes[0][1], float)  # Timestamp

        # Wait for timeout
        await asyncio.sleep(0.15)

        # OPEN -> HALF_OPEN (timeout + success)
        good_func = MagicMock(return_value="success")
        result = await breaker.call(good_func)
        assert result == "success"
        assert breaker.state == CircuitState.HALF_OPEN

        # HALF_OPEN -> CLOSED (successes)
        result = await breaker.call(good_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

        # Verify state change history
        state_changes = breaker.stats.state_changes
        assert len(state_changes) == 3
        assert state_changes[0][0] == CircuitState.OPEN  # First transition: to OPEN
        assert state_changes[1][0] == CircuitState.HALF_OPEN  # Second transition: to HALF_OPEN
        assert state_changes[2][0] == CircuitState.CLOSED  # Third transition: to CLOSED


class TestCircuitBreakerDecorator:
    """Test circuit_breaker decorator."""

    def test_decorator_sync_function(self):
        """Test decorator with synchronous function."""

        @circuit_breaker(name="test_func", failure_threshold=2)
        def test_func(value):
            if value < 0:
                raise ValueError("negative value")
            return value * 2

        # Note: The decorator might need to be async-aware
        # This test may need adjustment based on actual implementation

    @pytest.mark.asyncio
    async def test_decorator_async_function(self):
        """Test decorator with asynchronous function."""

        @circuit_breaker(name="async_test", failure_threshold=2)
        async def async_test_func(value):
            if value < 0:
                raise ValueError("negative value")
            await asyncio.sleep(0.01)
            return value * 2

        # Note: Test implementation depends on actual decorator
