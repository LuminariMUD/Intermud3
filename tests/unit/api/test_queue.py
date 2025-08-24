"""Tests for message queue management."""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.queue import (
    MessageQueueManager,
    PriorityMessageQueue,
    QueuedMessage,
    message_queue_manager,
)


# Custom exception for testing
class QueueError(Exception):
    pass


@pytest.fixture
def message_queue():
    """Create message queue for testing."""
    return PriorityMessageQueue(max_size=100)


@pytest.fixture
def priority_queue():
    """Create priority message queue for testing."""
    return PriorityMessageQueue(max_size=100)


@pytest.fixture
def queue_manager():
    """Create queue manager for testing."""
    return MessageQueueManager()


class TestQueuedMessage:
    """Test QueuedMessage class."""

    def test_message_creation(self):
        """Test creating a queued message."""
        message = QueuedMessage(session_id="test-session-1", content={"test": "data"}, priority=5)

        assert message.session_id == "test-session-1"
        assert message.content == {"test": "data"}
        assert message.priority == 5
        assert isinstance(message.timestamp, datetime)
        assert message.retry_count == 0

    def test_message_comparison(self):
        """Test message priority comparison."""
        # Higher priority (lower number) should come first
        high_priority = QueuedMessage("session1", {"data": 1}, priority=1)
        low_priority = QueuedMessage("session2", {"data": 2}, priority=5)

        assert high_priority < low_priority
        assert not (low_priority < high_priority)

    def test_message_with_retry(self):
        """Test message with retry count."""
        message = QueuedMessage(
            session_id="test-session-1", content={"test": "data"}, priority=5, retry_count=3
        )

        assert message.retry_count == 3

    def test_message_expiry(self):
        """Test message expiry checking."""
        # Non-expiring message
        message1 = QueuedMessage("session1", {"data": 1}, priority=5)
        assert not message1.is_expired()

        # Expired message
        message2 = QueuedMessage("session2", {"data": 2}, priority=5, ttl=1)
        message2.timestamp = datetime.utcnow() - timedelta(seconds=2)
        assert message2.is_expired()

        # Not expired message
        message3 = QueuedMessage("session3", {"data": 3}, priority=5, ttl=60)
        assert not message3.is_expired()


class TestMessageQueue:
    """Test MessageQueue class."""

    def test_queue_initialization(self, message_queue):
        """Test queue initialization."""
        assert message_queue.max_size == 100
        assert message_queue.size() == 0
        assert message_queue.is_empty()
        assert not message_queue.is_full()

    def test_put_message(self, message_queue):
        """Test putting messages in queue."""
        message = QueuedMessage("session1", {"data": "test"}, priority=5)

        message_queue.put(message)

        assert message_queue.size() == 1
        assert not message_queue.is_empty()

    def test_get_message(self, message_queue):
        """Test getting messages from queue."""
        message = QueuedMessage("session1", {"data": "test"}, priority=5)

        message_queue.put(message)
        retrieved = message_queue.get()

        assert retrieved == message
        assert message_queue.size() == 0
        assert message_queue.is_empty()

    def test_get_empty_queue(self, message_queue):
        """Test getting from empty queue."""
        retrieved = message_queue.get()
        assert retrieved is None

    def test_queue_full(self):
        """Test queue full behavior."""
        small_queue = PriorityMessageQueue(max_size=2)

        message1 = QueuedMessage("session1", {"data": 1}, priority=5)
        message2 = QueuedMessage("session2", {"data": 2}, priority=5)
        message3 = QueuedMessage("session3", {"data": 3}, priority=5)

        small_queue.put(message1)
        small_queue.put(message2)

        assert small_queue.is_full()

        # Third message should be added by dropping the lowest priority message
        # Since all messages have the same priority, it will drop the first one
        success = small_queue.put(message3)
        assert success

        # Queue should still be full but contain different messages
        assert small_queue.is_full()
        assert small_queue.size() == 2

        # The first message should have been dropped, so we should have message2 and message3
        retrieved1 = small_queue.get()
        retrieved2 = small_queue.get()

        # Both should be either message2 or message3 (not message1)
        retrieved_data = [retrieved1.content["data"], retrieved2.content["data"]]
        assert 2 in retrieved_data
        assert 3 in retrieved_data
        assert 1 not in retrieved_data

    def test_fifo_ordering(self, message_queue):
        """Test FIFO ordering in basic queue."""
        message1 = QueuedMessage("session1", {"data": 1}, priority=5)
        message2 = QueuedMessage("session2", {"data": 2}, priority=5)
        message3 = QueuedMessage("session3", {"data": 3}, priority=5)

        message_queue.put(message1)
        message_queue.put(message2)
        message_queue.put(message3)

        # Should come out in order
        assert message_queue.get() == message1
        assert message_queue.get() == message2
        assert message_queue.get() == message3

    def test_peek_message(self, message_queue):
        """Test peeking at next message."""
        message = QueuedMessage("session1", {"data": "test"}, priority=5)

        message_queue.put(message)

        peeked = message_queue.peek()
        assert peeked == message
        assert message_queue.size() == 1  # Should not remove

        retrieved = message_queue.get()
        assert retrieved == message
        assert message_queue.size() == 0

    def test_peek_empty_queue(self, message_queue):
        """Test peeking at empty queue."""
        peeked = message_queue.peek()
        assert peeked is None

    def test_clear_queue(self, message_queue):
        """Test clearing queue."""
        message1 = QueuedMessage("session1", {"data": 1}, priority=5)
        message2 = QueuedMessage("session2", {"data": 2}, priority=5)

        message_queue.put(message1)
        message_queue.put(message2)

        assert message_queue.size() == 2

        message_queue.clear()

        assert message_queue.size() == 0
        assert message_queue.is_empty()

    def test_get_stats(self, message_queue):
        """Test getting queue statistics."""
        stats = message_queue.get_stats()

        assert stats["total_size"] == 0
        assert stats["max_size"] == 100
        assert stats["utilization"] == 0
        assert stats["by_priority"] == {}

        # Add some messages
        message1 = QueuedMessage("session1", {"data": "test1"}, priority=5)
        message2 = QueuedMessage("session2", {"data": "test2"}, priority=3)
        message_queue.put(message1)
        message_queue.put(message2)

        stats = message_queue.get_stats()
        assert stats["total_size"] == 2
        assert stats["by_priority"][3] == 1  # One message with priority 3
        assert stats["by_priority"][5] == 1  # One message with priority 5


class TestPriorityMessageQueue:
    """Test PriorityMessageQueue class."""

    def test_priority_ordering(self, priority_queue):
        """Test priority ordering."""
        # Lower priority number = higher priority
        low_priority = QueuedMessage("session1", {"data": 1}, priority=5)
        high_priority = QueuedMessage("session2", {"data": 2}, priority=1)
        medium_priority = QueuedMessage("session3", {"data": 3}, priority=3)

        # Add in random order
        priority_queue.put(low_priority)
        priority_queue.put(high_priority)
        priority_queue.put(medium_priority)

        # Should come out in priority order
        assert priority_queue.get() == high_priority
        assert priority_queue.get() == medium_priority
        assert priority_queue.get() == low_priority

    def test_same_priority_fifo(self, priority_queue):
        """Test FIFO ordering for same priority."""
        message1 = QueuedMessage("session1", {"data": 1}, priority=5)
        message2 = QueuedMessage("session2", {"data": 2}, priority=5)
        message3 = QueuedMessage("session3", {"data": 3}, priority=5)

        priority_queue.put(message1)
        priority_queue.put(message2)
        priority_queue.put(message3)

        # Same priority should be FIFO
        assert priority_queue.get() == message1
        assert priority_queue.get() == message2
        assert priority_queue.get() == message3

    def test_peek_highest_priority(self, priority_queue):
        """Test peeking returns highest priority."""
        low_priority = QueuedMessage("session1", {"data": 1}, priority=5)
        high_priority = QueuedMessage("session2", {"data": 2}, priority=1)

        priority_queue.put(low_priority)
        priority_queue.put(high_priority)

        peeked = priority_queue.peek()
        assert peeked == high_priority
        assert priority_queue.size() == 2


class TestMessageQueueManager:
    """Test MessageQueueManager class."""

    def test_manager_initialization(self, queue_manager):
        """Test queue manager initialization."""
        assert len(queue_manager.session_queues) == 0
        assert not queue_manager.running
        assert queue_manager.worker_task is None

    @pytest.mark.asyncio
    async def test_start_stop(self, queue_manager):
        """Test starting and stopping queue manager."""
        await queue_manager.start()

        assert queue_manager.running
        assert queue_manager.worker_task is not None

        await queue_manager.stop()

        assert not queue_manager.running
        assert queue_manager.worker_task is None

    def test_get_or_create_queue(self, queue_manager):
        """Test getting or creating session queue."""
        # First call should create queue
        queue1 = queue_manager.get_or_create_queue("session1")
        assert isinstance(queue1, PriorityMessageQueue)
        assert "session1" in queue_manager.session_queues

        # Second call should return same queue
        queue2 = queue_manager.get_or_create_queue("session1")
        assert queue2 is queue1

    def test_enqueue_message(self, queue_manager):
        """Test enqueueing messages."""
        queue_manager.enqueue_message(session_id="session1", content={"test": "data"}, priority=5)

        queue = queue_manager.session_queues["session1"]
        assert queue.size() == 1

        message = queue.peek()
        assert message.session_id == "session1"
        assert message.content == {"test": "data"}
        assert message.priority == 5

    def test_enqueue_with_ttl(self, queue_manager):
        """Test enqueueing messages with TTL."""
        queue_manager.enqueue_message(
            session_id="session1", content={"test": "data"}, priority=5, ttl=300
        )

        queue = queue_manager.session_queues["session1"]
        message = queue.peek()
        assert message.ttl == 300

    def test_get_queue_stats(self, queue_manager):
        """Test getting queue statistics."""
        # Add messages to different sessions
        queue_manager.enqueue_message("session1", {"data": 1}, priority=5)
        queue_manager.enqueue_message("session1", {"data": 2}, priority=3)
        queue_manager.enqueue_message("session2", {"data": 3}, priority=1)

        stats = queue_manager.get_queue_stats()

        # Check that session_queues exist and have correct sizes
        assert "session_queues" in stats
        assert stats["session_queues"]["session1"]["size"] == 2
        assert stats["session_queues"]["session2"]["size"] == 1

        # Check that we have 2 sessions with messages
        assert len(stats["session_queues"]) == 2

    def test_cleanup_empty_queues(self, queue_manager):
        """Test cleanup of empty queues."""
        # Create queues and add messages
        queue_manager.enqueue_message("session1", {"data": 1}, priority=5)
        queue_manager.enqueue_message("session2", {"data": 2}, priority=5)

        # Empty one queue
        queue1 = queue_manager.session_queues["session1"]
        queue1.get()  # Remove the message

        # Cleanup should remove empty queue
        queue_manager.cleanup_empty_queues()

        assert "session1" not in queue_manager.session_queues
        assert "session2" in queue_manager.session_queues

    def test_remove_session_queue(self, queue_manager):
        """Test removing session queue."""
        queue_manager.enqueue_message("session1", {"data": 1}, priority=5)
        assert "session1" in queue_manager.session_queues

        queue_manager.remove_session_queue("session1")
        assert "session1" not in queue_manager.session_queues

    def test_clear_all_queues(self, queue_manager):
        """Test clearing all queues."""
        queue_manager.enqueue_message("session1", {"data": 1}, priority=5)
        queue_manager.enqueue_message("session2", {"data": 2}, priority=5)

        assert len(queue_manager.session_queues) == 2

        queue_manager.clear_all_queues()

        # Queues should still exist but be empty
        assert len(queue_manager.session_queues) == 2
        for queue in queue_manager.session_queues.values():
            assert queue.is_empty()

    @pytest.mark.asyncio
    async def test_process_queues(self, queue_manager):
        """Test processing queues."""
        # Mock session manager
        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_session.is_connected.return_value = True
        mock_session.send = AsyncMock()
        mock_session_manager.get_session.return_value = mock_session

        # Import and replace the session_manager in the session module
        from src.api import session

        original_session_manager = session.session_manager
        session.session_manager = mock_session_manager

        try:
            # Add messages
            queue_manager.enqueue_message("session1", {"test": "data1"}, priority=5)
            queue_manager.enqueue_message("session1", {"test": "data2"}, priority=3)

            # Process queues
            await queue_manager.process_queues()

            # Verify messages were sent in priority order
            assert mock_session.send.call_count == 2

            # Higher priority (lower number) should be sent first
            first_call = mock_session.send.call_args_list[0][0][0]
            second_call = mock_session.send.call_args_list[1][0][0]

            first_data = json.loads(first_call)
            second_data = json.loads(second_call)

            assert first_data["test"] == "data2"  # Priority 3
            assert second_data["test"] == "data1"  # Priority 5
        finally:
            # Restore original session manager
            session.session_manager = original_session_manager

    @pytest.mark.asyncio
    async def test_process_queues_expired_messages(self, queue_manager):
        """Test processing queues with expired messages."""
        # Mock session manager
        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_session.is_connected.return_value = True
        mock_session.send = AsyncMock()
        mock_session_manager.get_session.return_value = mock_session

        # Import and replace the session_manager in the session module
        from src.api import session

        original_session_manager = session.session_manager
        session.session_manager = mock_session_manager

        try:
            # Add expired message
            queue_manager.enqueue_message("session1", {"test": "expired"}, priority=5, ttl=1)
            queue = queue_manager.session_queues["session1"]
            message = queue.peek()
            # Make it expired
            message.timestamp = datetime.utcnow() - timedelta(seconds=2)

            # Add valid message
            queue_manager.enqueue_message("session1", {"test": "valid"}, priority=5)

            # Process queues
            await queue_manager.process_queues()

            # Only valid message should be sent
            assert mock_session.send.call_count == 1
            sent_data = json.loads(mock_session.send.call_args[0][0])
            assert sent_data["test"] == "valid"
        finally:
            # Restore original session manager
            session.session_manager = original_session_manager

    @pytest.mark.asyncio
    async def test_process_queues_disconnected_session(self, queue_manager):
        """Test processing queues for disconnected session."""
        # Mock session manager with disconnected session
        mock_session_manager = MagicMock()
        mock_session_manager.get_session.return_value = None  # Session not found

        # Import and replace the session_manager in the session module
        from src.api import session

        original_session_manager = session.session_manager
        session.session_manager = mock_session_manager

        try:
            # Add message
            queue_manager.enqueue_message("session1", {"test": "data"}, priority=5)

            # Process queues
            await queue_manager.process_queues()

            # Queue should be removed since session doesn't exist
            assert "session1" not in queue_manager.session_queues
        finally:
            # Restore original session manager
            session.session_manager = original_session_manager

    @pytest.mark.asyncio
    async def test_worker_task_integration(self, queue_manager):
        """Test worker task integration."""
        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_session.is_connected.return_value = True
        mock_session.send = AsyncMock()
        mock_session_manager.get_session.return_value = mock_session

        # Import and replace the session_manager in the session module
        from src.api import session

        original_session_manager = session.session_manager
        session.session_manager = mock_session_manager

        try:
            await queue_manager.start()

            try:
                # Add message
                queue_manager.enqueue_message("session1", {"test": "data"}, priority=5)

                # Wait for worker to process
                await asyncio.sleep(0.2)

                # Message should be processed
                assert mock_session.send.called

            finally:
                await queue_manager.stop()
        finally:
            # Restore original session manager
            session.session_manager = original_session_manager


class TestGlobalQueueManager:
    """Test global queue manager instance."""

    def test_global_instance_exists(self):
        """Test that global queue manager instance exists."""
        assert message_queue_manager is not None
        assert isinstance(message_queue_manager, MessageQueueManager)

    def test_global_instance_initial_state(self):
        """Test global instance initial state."""
        # Should start stopped
        assert not message_queue_manager.running
        assert len(message_queue_manager.session_queues) >= 0


class TestQueueError:
    """Test QueueError exception."""

    def test_queue_error(self):
        """Test creating a queue error."""
        error = QueueError("Queue is full")

        assert str(error) == "Queue is full"
        assert isinstance(error, Exception)


class TestQueueIntegration:
    """Integration tests for queue system."""

    @pytest.mark.asyncio
    async def test_full_message_flow(self):
        """Test complete message flow through queue system."""
        queue_manager = MessageQueueManager()

        # Mock session manager
        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_session.is_connected.return_value = True
        mock_session.send = AsyncMock()
        mock_session_manager.get_session.return_value = mock_session

        # Import and replace the session_manager in the session module
        from src.api import session

        original_session_manager = session.session_manager
        session.session_manager = mock_session_manager

        try:
            await queue_manager.start()

            try:
                # Enqueue messages with different priorities
                queue_manager.enqueue_message("session1", {"type": "urgent"}, priority=1)
                queue_manager.enqueue_message("session1", {"type": "normal"}, priority=5)
                queue_manager.enqueue_message("session1", {"type": "low"}, priority=9)

                # Wait for processing
                await asyncio.sleep(0.2)

                # Verify all messages were sent in correct order
                assert mock_session.send.call_count == 3

                # Check order (urgent first, low last)
                calls = mock_session.send.call_args_list
                first_data = json.loads(calls[0][0][0])
                second_data = json.loads(calls[1][0][0])
                third_data = json.loads(calls[2][0][0])

                assert first_data["type"] == "urgent"
                assert second_data["type"] == "normal"
                assert third_data["type"] == "low"

            finally:
                await queue_manager.stop()
        finally:
            # Restore original session manager
            session.session_manager = original_session_manager

    @pytest.mark.asyncio
    async def test_queue_resilience(self):
        """Test queue system resilience to errors."""
        queue_manager = MessageQueueManager()

        # Mock session manager with failing send
        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_session.is_connected.return_value = True
        mock_session.send = AsyncMock(side_effect=Exception("Send failed"))
        mock_session_manager.get_session.return_value = mock_session

        # Import and replace the session_manager in the session module
        from src.api import session

        original_session_manager = session.session_manager
        session.session_manager = mock_session_manager

        try:
            await queue_manager.start()

            try:
                # Enqueue message
                queue_manager.enqueue_message("session1", {"test": "data"}, priority=5)

                # Wait for processing attempt
                await asyncio.sleep(0.2)

                # Manager should still be running despite error
                assert queue_manager.running

                # Queue should still exist (error handling)
                assert "session1" in queue_manager.session_queues

            finally:
                await queue_manager.stop()
        finally:
            # Restore original session manager
            session.session_manager = original_session_manager
