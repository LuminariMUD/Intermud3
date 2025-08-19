"""Tests for the event distribution system."""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.events import (
    Event,
    EventDispatcher,
    EventFilter,
    EventType,
    event_dispatcher
)
from src.api.session import Session


@pytest.fixture
def dispatcher():
    """Create event dispatcher for testing."""
    return EventDispatcher()


@pytest.fixture
def mock_session():
    """Create mock session for testing."""
    session = MagicMock(spec=Session)
    session.session_id = "test-session-1"
    session.mud_name = "TestMUD"
    session.is_connected.return_value = True
    session.permissions = {"tell", "channel", "info"}
    session.subscriptions = {"chat", "gossip"}
    session.send = AsyncMock(return_value=True)
    return session


class TestEvent:
    """Test Event class."""
    
    def test_event_creation(self):
        """Test creating an event."""
        event = Event(
            type=EventType.TELL_RECEIVED,
            data={"from_user": "Alice", "message": "Hello"},
            priority=3,
            ttl=300
        )
        
        assert event.type == EventType.TELL_RECEIVED
        assert event.data["from_user"] == "Alice"
        assert event.priority == 3
        assert event.ttl == 300
        assert isinstance(event.timestamp, datetime)
    
    def test_event_to_json_rpc(self):
        """Test converting event to JSON-RPC format."""
        event = Event(
            type=EventType.TELL_RECEIVED,
            data={"from_user": "Alice", "message": "Hello"}
        )
        
        json_str = event.to_json_rpc()
        data = json.loads(json_str)
        
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "tell_received"
        assert data["params"]["from_user"] == "Alice"
        assert data["params"]["message"] == "Hello"
        assert "timestamp" in data["params"]
    
    def test_event_expiry(self):
        """Test event expiry checking."""
        # Non-expiring event
        event1 = Event(
            type=EventType.TELL_RECEIVED,
            data={},
            ttl=None
        )
        assert not event1.is_expired()
        
        # Expired event
        event2 = Event(
            type=EventType.TELL_RECEIVED,
            data={},
            ttl=1
        )
        event2.timestamp = datetime.utcnow() - timedelta(seconds=2)
        assert event2.is_expired()
        
        # Not expired event
        event3 = Event(
            type=EventType.TELL_RECEIVED,
            data={},
            ttl=60
        )
        assert not event3.is_expired()


class TestEventFilter:
    """Test EventFilter class."""
    
    def test_filter_by_event_type(self, mock_session):
        """Test filtering by event type."""
        filter_obj = EventFilter(
            event_types={EventType.TELL_RECEIVED, EventType.CHANNEL_MESSAGE}
        )
        
        # Matching event
        event1 = Event(
            type=EventType.TELL_RECEIVED,
            data={"from_mud": "OtherMUD"}
        )
        assert filter_obj.matches(event1, mock_session)
        
        # Non-matching event
        event2 = Event(
            type=EventType.MUD_ONLINE,
            data={"mud_name": "NewMUD"}
        )
        assert not filter_obj.matches(event2, mock_session)
    
    def test_filter_by_channel(self, mock_session):
        """Test filtering by channel."""
        filter_obj = EventFilter(
            channels={"chat", "gossip"}
        )
        
        # Matching channel
        event1 = Event(
            type=EventType.CHANNEL_MESSAGE,
            data={"channel": "chat", "from_mud": "OtherMUD"}
        )
        assert filter_obj.matches(event1, mock_session)
        
        # Non-matching channel
        event2 = Event(
            type=EventType.CHANNEL_MESSAGE,
            data={"channel": "admin", "from_mud": "OtherMUD"}
        )
        assert not filter_obj.matches(event2, mock_session)
    
    def test_filter_exclude_self(self, mock_session):
        """Test excluding events from same MUD."""
        filter_obj = EventFilter(exclude_self=True)
        
        # Event from same MUD
        event1 = Event(
            type=EventType.TELL_RECEIVED,
            data={"from_mud": "TestMUD"}
        )
        assert not filter_obj.matches(event1, mock_session)
        
        # Event from different MUD
        event2 = Event(
            type=EventType.TELL_RECEIVED,
            data={"from_mud": "OtherMUD"}
        )
        assert filter_obj.matches(event2, mock_session)


class TestEventDispatcher:
    """Test EventDispatcher class."""
    
    @pytest.mark.asyncio
    async def test_start_stop(self, dispatcher):
        """Test starting and stopping dispatcher."""
        await dispatcher.start()
        assert dispatcher.running
        assert dispatcher.dispatch_task is not None
        
        await dispatcher.stop()
        assert not dispatcher.running
    
    @pytest.mark.asyncio
    async def test_register_unregister_session(self, dispatcher, mock_session):
        """Test session registration."""
        dispatcher.register_session(mock_session)
        assert mock_session.session_id in dispatcher.sessions
        
        dispatcher.unregister_session(mock_session.session_id)
        assert mock_session.session_id not in dispatcher.sessions
    
    @pytest.mark.asyncio
    async def test_dispatch_event(self, dispatcher, mock_session):
        """Test dispatching an event."""
        # Register session
        dispatcher.register_session(mock_session)
        
        # Create and dispatch event
        event = Event(
            type=EventType.TELL_RECEIVED,
            data={"from_mud": "OtherMUD", "from_user": "Alice", "message": "Hello"}
        )
        
        # Manually dispatch (without background task)
        await dispatcher._dispatch_event(event)
        
        # Check that send was called
        mock_session.send.assert_called_once()
        call_args = mock_session.send.call_args[0][0]
        data = json.loads(call_args)
        
        assert data["method"] == "tell_received"
        assert data["params"]["from_user"] == "Alice"
    
    @pytest.mark.asyncio
    async def test_permission_checking(self, dispatcher, mock_session):
        """Test permission checking for events."""
        dispatcher.register_session(mock_session)
        
        # Event requiring 'tell' permission (which session has)
        event1 = Event(
            type=EventType.TELL_RECEIVED,
            data={"from_mud": "OtherMUD"}
        )
        assert dispatcher._should_send_event(mock_session, event1)
        
        # Event requiring wildcard permission (all users get it)
        event2 = Event(
            type=EventType.ERROR_OCCURRED,
            data={"error": "test"}
        )
        assert dispatcher._should_send_event(mock_session, event2)
        
        # Remove 'tell' permission
        mock_session.permissions = {"channel"}
        event3 = Event(
            type=EventType.TELL_RECEIVED,
            data={"from_mud": "OtherMUD"}
        )
        assert not dispatcher._should_send_event(mock_session, event3)
    
    @pytest.mark.asyncio
    async def test_channel_subscription_filtering(self, dispatcher, mock_session):
        """Test channel subscription filtering."""
        dispatcher.register_session(mock_session)
        
        # Event for subscribed channel
        event1 = Event(
            type=EventType.CHANNEL_MESSAGE,
            data={"channel": "chat", "from_mud": "OtherMUD"}
        )
        assert dispatcher._should_send_event(mock_session, event1)
        
        # Event for non-subscribed channel
        event2 = Event(
            type=EventType.CHANNEL_MESSAGE,
            data={"channel": "admin", "from_mud": "OtherMUD"}
        )
        assert not dispatcher._should_send_event(mock_session, event2)
    
    @pytest.mark.asyncio
    async def test_expired_event_handling(self, dispatcher, mock_session):
        """Test handling of expired events."""
        dispatcher.register_session(mock_session)
        
        # Create expired event
        event = Event(
            type=EventType.TELL_RECEIVED,
            data={"message": "old"},
            ttl=1
        )
        event.timestamp = datetime.utcnow() - timedelta(seconds=2)
        
        # Dispatch expired event
        await dispatcher._dispatch_event(event)
        
        # Should not be sent
        mock_session.send.assert_not_called()
        assert dispatcher.stats["events_dropped"] == 1
    
    @pytest.mark.asyncio
    async def test_custom_filter(self, dispatcher, mock_session):
        """Test custom event filter."""
        # Set custom filter
        custom_filter = EventFilter(
            event_types={EventType.CHANNEL_MESSAGE},
            channels={"chat"},
            exclude_self=True
        )
        dispatcher.set_filter(mock_session.session_id, custom_filter)
        dispatcher.register_session(mock_session)
        
        # Event matching filter
        event1 = Event(
            type=EventType.CHANNEL_MESSAGE,
            data={"channel": "chat", "from_mud": "OtherMUD"}
        )
        assert dispatcher._should_send_event(mock_session, event1)
        
        # Event not matching filter (wrong channel)
        event2 = Event(
            type=EventType.CHANNEL_MESSAGE,
            data={"channel": "gossip", "from_mud": "OtherMUD"}
        )
        assert not dispatcher._should_send_event(mock_session, event2)
        
        # Event not matching filter (wrong type)
        event3 = Event(
            type=EventType.TELL_RECEIVED,
            data={"from_mud": "OtherMUD"}
        )
        assert not dispatcher._should_send_event(mock_session, event3)
    
    def test_get_stats(self, dispatcher):
        """Test getting dispatcher statistics."""
        stats = dispatcher.get_stats()
        
        assert "events_dispatched" in stats
        assert "events_dropped" in stats
        assert "events_queued" in stats
        assert "active_sessions" in stats
        assert "queue_size" in stats
        assert "filters_active" in stats


@pytest.mark.asyncio
async def test_event_dispatcher_integration():
    """Test full event dispatcher integration."""
    dispatcher = EventDispatcher()
    
    # Create mock sessions
    session1 = MagicMock(spec=Session)
    session1.session_id = "session-1"
    session1.mud_name = "MUD1"
    session1.is_connected.return_value = True
    session1.permissions = {"tell", "channel"}
    session1.subscriptions = {"chat"}
    session1.send = AsyncMock(return_value=True)
    
    session2 = MagicMock(spec=Session)
    session2.session_id = "session-2"
    session2.mud_name = "MUD2"
    session2.is_connected.return_value = True
    session2.permissions = {"channel"}
    session2.subscriptions = {"chat", "gossip"}
    session2.send = AsyncMock(return_value=True)
    
    # Register sessions
    dispatcher.register_session(session1)
    dispatcher.register_session(session2)
    
    # Start dispatcher
    await dispatcher.start()
    
    try:
        # Dispatch tell event (only session1 should receive)
        tell_event = dispatcher.create_event(
            EventType.TELL_RECEIVED,
            {"from_mud": "MUD3", "from_user": "Alice", "message": "Hello"},
            priority=3
        )
        await dispatcher.dispatch(tell_event)
        
        # Dispatch channel event (both should receive)
        channel_event = dispatcher.create_event(
            EventType.CHANNEL_MESSAGE,
            {"channel": "chat", "from_mud": "MUD3", "message": "Hi all"},
            priority=5
        )
        await dispatcher.dispatch(channel_event)
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Verify session1 received both events
        assert session1.send.call_count >= 2
        
        # Verify session2 received only channel event
        assert session2.send.call_count >= 1
        
    finally:
        await dispatcher.stop()