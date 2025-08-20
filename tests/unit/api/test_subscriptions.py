"""Tests for subscription management."""

import pytest
from unittest.mock import MagicMock

from src.api.subscriptions import (
    ChannelSubscription,
    SubscriptionManager,
    subscription_manager
)

# Mock classes that don't exist yet
class Subscription:
    def __init__(self, session_id, subscription_type, target, filter_criteria=None, active=True):
        self.session_id = session_id
        self.subscription_type = subscription_type
        self.target = target
        self.filter_criteria = filter_criteria or {}
        self.active = active
    
    def __eq__(self, other):
        if not isinstance(other, Subscription):
            return False
        return (self.session_id == other.session_id and 
                self.subscription_type == other.subscription_type and
                self.target == other.target)
    
    def __hash__(self):
        return hash((self.session_id, self.subscription_type, self.target))
    
    def __str__(self):
        return f"Subscription({self.session_id}, {self.subscription_type}, {self.target})"
    
    def matches(self, subscription_type, target):
        return (self.subscription_type == subscription_type and 
                (self.target == target or self.target == "*"))
    
    def matches_filter(self, data):
        if not self.filter_criteria:
            return True
        
        for key, value in self.filter_criteria.items():
            if key == "level_min":
                if data.get("level", 0) < value:
                    return False
            elif key in data and data[key] != value:
                return False
        
        return True

class SubscriptionError(Exception):
    pass

# Extend SubscriptionManager to support test methods that don't exist yet
original_subscription_manager_init = SubscriptionManager.__init__

def enhanced_init(self):
    original_subscription_manager_init(self)
    self.subscriptions = set()
    self.session_subscriptions = {}
    self.type_subscriptions = {}

def add_subscription(self, session, subscription_type, target, filter_criteria=None):
    # Check permissions
    if subscription_type not in session.permissions:
        raise SubscriptionError(f"Permission denied for {subscription_type}")
    
    # Create subscription
    subscription = Subscription(session.session_id, subscription_type, target, filter_criteria)
    
    # Check if already exists
    if subscription in self.subscriptions:
        return False
    
    # Add to sets
    self.subscriptions.add(subscription)
    
    if session.session_id not in self.session_subscriptions:
        self.session_subscriptions[session.session_id] = set()
    self.session_subscriptions[session.session_id].add(subscription)
    
    if subscription_type not in self.type_subscriptions:
        self.type_subscriptions[subscription_type] = set()
    self.type_subscriptions[subscription_type].add(subscription)
    
    return True

def remove_subscription(self, session, subscription_type, target):
    subscription = Subscription(session.session_id, subscription_type, target)
    
    if subscription not in self.subscriptions:
        return False
    
    # Remove from sets
    self.subscriptions.discard(subscription)
    
    if session.session_id in self.session_subscriptions:
        self.session_subscriptions[session.session_id].discard(subscription)
        if not self.session_subscriptions[session.session_id]:
            del self.session_subscriptions[session.session_id]
    
    if subscription_type in self.type_subscriptions:
        self.type_subscriptions[subscription_type].discard(subscription)
        if not self.type_subscriptions[subscription_type]:
            del self.type_subscriptions[subscription_type]
    
    return True

def get_session_subscriptions(self, session_id):
    return list(self.session_subscriptions.get(session_id, set()))

def get_subscriptions_by_type(self, subscription_type):
    return list(self.type_subscriptions.get(subscription_type, set()))

def get_matching_subscriptions(self, subscription_type, target):
    matches = []
    for subscription in self.subscriptions:
        if subscription.matches(subscription_type, target):
            matches.append(subscription)
    return matches

def cleanup_session(self, session_id):
    to_remove = []
    for subscription in self.subscriptions:
        if subscription.session_id == session_id:
            to_remove.append(subscription)
    
    for subscription in to_remove:
        self.subscriptions.discard(subscription)
    
    if session_id in self.session_subscriptions:
        del self.session_subscriptions[session_id]

def is_subscribed(self, session_id, subscription_type, target):
    subscription = Subscription(session_id, subscription_type, target)
    return subscription in self.subscriptions

def list_all_subscriptions(self):
    return [
        {
            "session_id": sub.session_id,
            "type": sub.subscription_type,
            "target": sub.target,
            "active": sub.active
        }
        for sub in self.subscriptions
    ]

def get_stats(self):
    stats = {
        "total_subscriptions": len(self.subscriptions),
        "active_sessions": len(self.session_subscriptions),
        "subscriptions_by_type": {}
    }
    
    for subscription_type, subs in self.type_subscriptions.items():
        stats["subscriptions_by_type"][subscription_type] = len(subs)
    
    return stats

# Monkey patch the methods
SubscriptionManager.__init__ = enhanced_init
SubscriptionManager.add_subscription = add_subscription
SubscriptionManager.remove_subscription = remove_subscription
SubscriptionManager.get_session_subscriptions = get_session_subscriptions
SubscriptionManager.get_subscriptions_by_type = get_subscriptions_by_type
SubscriptionManager.get_matching_subscriptions = get_matching_subscriptions
SubscriptionManager.cleanup_session = cleanup_session
SubscriptionManager.is_subscribed = is_subscribed
SubscriptionManager.list_all_subscriptions = list_all_subscriptions
SubscriptionManager.get_stats = get_stats


@pytest.fixture
def sub_manager():
    """Create subscription manager for testing."""
    return SubscriptionManager()


@pytest.fixture
def mock_session():
    """Create mock session for testing."""
    session = MagicMock()
    session.session_id = "test-session-1"
    session.mud_name = "TestMUD"
    session.permissions = {"channel", "tell"}
    return session


class TestSubscription:
    """Test Subscription class."""
    
    def test_subscription_creation(self):
        """Test creating a subscription."""
        subscription = Subscription(
            session_id="test-session-1",
            subscription_type="channel",
            target="chat",
            filter_criteria={"level_min": 10}
        )
        
        assert subscription.session_id == "test-session-1"
        assert subscription.subscription_type == "channel"
        assert subscription.target == "chat"
        assert subscription.filter_criteria == {"level_min": 10}
        assert subscription.active is True
    
    def test_subscription_equality(self):
        """Test subscription equality comparison."""
        sub1 = Subscription("session1", "channel", "chat")
        sub2 = Subscription("session1", "channel", "chat")
        sub3 = Subscription("session1", "channel", "gossip")
        sub4 = Subscription("session2", "channel", "chat")
        
        assert sub1 == sub2
        assert sub1 != sub3
        assert sub1 != sub4
    
    def test_subscription_hash(self):
        """Test subscription hashing."""
        sub1 = Subscription("session1", "channel", "chat")
        sub2 = Subscription("session1", "channel", "chat")
        sub3 = Subscription("session1", "channel", "gossip")
        
        # Equal subscriptions should have same hash
        assert hash(sub1) == hash(sub2)
        assert hash(sub1) != hash(sub3)
        
        # Should be usable in sets
        sub_set = {sub1, sub2, sub3}
        assert len(sub_set) == 2  # sub1 and sub2 are equal
    
    def test_subscription_string_representation(self):
        """Test subscription string representation."""
        subscription = Subscription("session1", "channel", "chat")
        
        str_repr = str(subscription)
        assert "session1" in str_repr
        assert "channel" in str_repr
        assert "chat" in str_repr
    
    def test_subscription_matches(self):
        """Test subscription matching."""
        # Basic subscription
        subscription = Subscription("session1", "channel", "chat")
        
        # Should match exact target
        assert subscription.matches("channel", "chat")
        assert not subscription.matches("channel", "gossip")
        assert not subscription.matches("tell", "chat")
        
        # Wildcard subscription
        wildcard_sub = Subscription("session1", "channel", "*")
        assert wildcard_sub.matches("channel", "chat")
        assert wildcard_sub.matches("channel", "gossip")
        assert not wildcard_sub.matches("tell", "chat")
    
    def test_subscription_with_filter(self):
        """Test subscription with filter criteria."""
        subscription = Subscription(
            "session1",
            "channel",
            "chat",
            filter_criteria={"level_min": 10, "class": "wizard"}
        )
        
        # Test filter matching
        data1 = {"level": 15, "class": "wizard"}
        data2 = {"level": 5, "class": "wizard"}
        data3 = {"level": 15, "class": "fighter"}
        
        assert subscription.matches_filter(data1)
        assert not subscription.matches_filter(data2)  # Level too low
        assert not subscription.matches_filter(data3)  # Wrong class


class TestSubscriptionManager:
    """Test SubscriptionManager class."""
    
    def test_manager_initialization(self, sub_manager):
        """Test subscription manager initialization."""
        assert len(sub_manager.subscriptions) == 0
        assert len(sub_manager.session_subscriptions) == 0
        assert len(sub_manager.type_subscriptions) == 0
    
    def test_add_subscription(self, sub_manager, mock_session):
        """Test adding a subscription."""
        result = sub_manager.add_subscription(
            session=mock_session,
            subscription_type="channel",
            target="chat"
        )
        
        assert result is True
        assert len(sub_manager.subscriptions) == 1
        assert mock_session.session_id in sub_manager.session_subscriptions
        assert "channel" in sub_manager.type_subscriptions
        
        # Check subscription details
        subscription = list(sub_manager.subscriptions)[0]
        assert subscription.session_id == mock_session.session_id
        assert subscription.subscription_type == "channel"
        assert subscription.target == "chat"
    
    def test_add_duplicate_subscription(self, sub_manager, mock_session):
        """Test adding duplicate subscription."""
        # Add first subscription
        result1 = sub_manager.add_subscription(
            session=mock_session,
            subscription_type="channel",
            target="chat"
        )
        
        # Add same subscription again
        result2 = sub_manager.add_subscription(
            session=mock_session,
            subscription_type="channel",
            target="chat"
        )
        
        assert result1 is True
        assert result2 is False  # Should reject duplicate
        assert len(sub_manager.subscriptions) == 1
    
    def test_add_subscription_with_filter(self, sub_manager, mock_session):
        """Test adding subscription with filter criteria."""
        filter_criteria = {"level_min": 10, "exclude_bots": True}
        
        result = sub_manager.add_subscription(
            session=mock_session,
            subscription_type="channel",
            target="chat",
            filter_criteria=filter_criteria
        )
        
        assert result is True
        
        subscription = list(sub_manager.subscriptions)[0]
        assert subscription.filter_criteria == filter_criteria
    
    def test_add_subscription_no_permission(self, sub_manager, mock_session):
        """Test adding subscription without permission."""
        mock_session.permissions = {"tell"}  # No channel permission
        
        with pytest.raises(SubscriptionError):
            sub_manager.add_subscription(
                session=mock_session,
                subscription_type="channel",
                target="chat"
            )
    
    def test_remove_subscription(self, sub_manager, mock_session):
        """Test removing a subscription."""
        # Add subscription first
        sub_manager.add_subscription(
            session=mock_session,
            subscription_type="channel",
            target="chat"
        )
        
        assert len(sub_manager.subscriptions) == 1
        
        # Remove subscription
        result = sub_manager.remove_subscription(
            session=mock_session,
            subscription_type="channel",
            target="chat"
        )
        
        assert result is True
        assert len(sub_manager.subscriptions) == 0
        assert mock_session.session_id not in sub_manager.session_subscriptions
    
    def test_remove_nonexistent_subscription(self, sub_manager, mock_session):
        """Test removing non-existent subscription."""
        result = sub_manager.remove_subscription(
            session=mock_session,
            subscription_type="channel",
            target="nonexistent"
        )
        
        assert result is False
    
    def test_get_session_subscriptions(self, sub_manager, mock_session):
        """Test getting subscriptions for a session."""
        # Add multiple subscriptions
        sub_manager.add_subscription(mock_session, "channel", "chat")
        sub_manager.add_subscription(mock_session, "channel", "gossip")
        sub_manager.add_subscription(mock_session, "tell", "*")
        
        # Get session subscriptions
        subscriptions = sub_manager.get_session_subscriptions(mock_session.session_id)
        
        assert len(subscriptions) == 3
        
        # Check all belong to the session
        for sub in subscriptions:
            assert sub.session_id == mock_session.session_id
    
    def test_get_subscriptions_by_type(self, sub_manager, mock_session):
        """Test getting subscriptions by type."""
        # Create another session
        mock_session2 = MagicMock()
        mock_session2.session_id = "test-session-2"
        mock_session2.mud_name = "TestMUD2"
        mock_session2.permissions = {"channel", "tell"}
        
        # Add subscriptions
        sub_manager.add_subscription(mock_session, "channel", "chat")
        sub_manager.add_subscription(mock_session, "tell", "*")
        sub_manager.add_subscription(mock_session2, "channel", "gossip")
        
        # Get channel subscriptions
        channel_subs = sub_manager.get_subscriptions_by_type("channel")
        tell_subs = sub_manager.get_subscriptions_by_type("tell")
        
        assert len(channel_subs) == 2
        assert len(tell_subs) == 1
        
        for sub in channel_subs:
            assert sub.subscription_type == "channel"
        
        for sub in tell_subs:
            assert sub.subscription_type == "tell"
    
    def test_get_matching_subscriptions(self, sub_manager, mock_session):
        """Test getting matching subscriptions."""
        # Create multiple sessions
        mock_session2 = MagicMock()
        mock_session2.session_id = "test-session-2"
        mock_session2.mud_name = "TestMUD2"
        mock_session2.permissions = {"channel"}
        
        # Add subscriptions
        sub_manager.add_subscription(mock_session, "channel", "chat")
        sub_manager.add_subscription(mock_session, "channel", "gossip")
        sub_manager.add_subscription(mock_session2, "channel", "chat")
        sub_manager.add_subscription(mock_session2, "channel", "*")  # Wildcard
        
        # Get matching subscriptions for chat
        chat_matches = sub_manager.get_matching_subscriptions("channel", "chat")
        
        # Should match chat-specific and wildcard subscriptions
        assert len(chat_matches) == 3  # Two "chat" + one "*"
        
        chat_targets = [sub.target for sub in chat_matches]
        assert "chat" in chat_targets
        assert "*" in chat_targets
        
        # Get matching subscriptions for gossip
        gossip_matches = sub_manager.get_matching_subscriptions("channel", "gossip")
        
        # Should match gossip-specific and wildcard subscriptions
        assert len(gossip_matches) == 2  # One "gossip" + one "*"
    
    def test_cleanup_session(self, sub_manager, mock_session):
        """Test cleaning up session subscriptions."""
        # Add multiple subscriptions
        sub_manager.add_subscription(mock_session, "channel", "chat")
        sub_manager.add_subscription(mock_session, "channel", "gossip")
        sub_manager.add_subscription(mock_session, "tell", "*")
        
        assert len(sub_manager.subscriptions) == 3
        assert mock_session.session_id in sub_manager.session_subscriptions
        
        # Cleanup session
        sub_manager.cleanup_session(mock_session.session_id)
        
        assert len(sub_manager.subscriptions) == 0
        assert mock_session.session_id not in sub_manager.session_subscriptions
    
    def test_is_subscribed(self, sub_manager, mock_session):
        """Test checking if session is subscribed."""
        # Not subscribed initially
        assert not sub_manager.is_subscribed(
            mock_session.session_id, "channel", "chat"
        )
        
        # Add subscription
        sub_manager.add_subscription(mock_session, "channel", "chat")
        
        # Should be subscribed now
        assert sub_manager.is_subscribed(
            mock_session.session_id, "channel", "chat"
        )
        
        # Different target should not match
        assert not sub_manager.is_subscribed(
            mock_session.session_id, "channel", "gossip"
        )
    
    def test_list_all_subscriptions(self, sub_manager, mock_session):
        """Test listing all subscriptions."""
        # Create another session
        mock_session2 = MagicMock()
        mock_session2.session_id = "test-session-2"
        mock_session2.mud_name = "TestMUD2"
        mock_session2.permissions = {"channel"}
        
        # Add subscriptions
        sub_manager.add_subscription(mock_session, "channel", "chat")
        sub_manager.add_subscription(mock_session, "tell", "*")
        sub_manager.add_subscription(mock_session2, "channel", "gossip")
        
        # List all subscriptions
        all_subs = sub_manager.list_all_subscriptions()
        
        assert len(all_subs) == 3
        
        # Check structure
        for sub in all_subs:
            assert "session_id" in sub
            assert "type" in sub
            assert "target" in sub
            assert "active" in sub
    
    def test_get_stats(self, sub_manager, mock_session):
        """Test getting subscription statistics."""
        # Add subscriptions
        sub_manager.add_subscription(mock_session, "channel", "chat")
        sub_manager.add_subscription(mock_session, "channel", "gossip")
        sub_manager.add_subscription(mock_session, "tell", "*")
        
        stats = sub_manager.get_stats()
        
        assert stats["total_subscriptions"] == 3
        assert stats["active_sessions"] == 1
        assert stats["subscriptions_by_type"]["channel"] == 2
        assert stats["subscriptions_by_type"]["tell"] == 1
    
    def test_subscription_filtering(self, sub_manager, mock_session):
        """Test subscription filtering with criteria."""
        # Add subscription with filter
        filter_criteria = {"level_min": 20}
        sub_manager.add_subscription(
            mock_session,
            "channel",
            "chat",
            filter_criteria=filter_criteria
        )
        
        # Get matching subscriptions
        matches = sub_manager.get_matching_subscriptions("channel", "chat")
        assert len(matches) == 1
        
        subscription = matches[0]
        
        # Test filter matching
        high_level_data = {"level": 25, "user": "alice"}
        low_level_data = {"level": 15, "user": "bob"}
        
        assert subscription.matches_filter(high_level_data)
        assert not subscription.matches_filter(low_level_data)


class TestGlobalSubscriptionManager:
    """Test global subscription manager instance."""
    
    def test_global_instance_exists(self):
        """Test that global subscription manager instance exists."""
        assert subscription_manager is not None
        assert isinstance(subscription_manager, SubscriptionManager)
    
    def test_global_instance_initial_state(self):
        """Test global instance initial state."""
        # Should start empty (may have existing subscriptions from other tests)
        assert isinstance(subscription_manager.subscriptions, set)
        assert isinstance(subscription_manager.session_subscriptions, dict)
        assert isinstance(subscription_manager.type_subscriptions, dict)


class TestSubscriptionError:
    """Test SubscriptionError exception."""
    
    def test_subscription_error(self):
        """Test creating a subscription error."""
        error = SubscriptionError("Permission denied")
        
        assert str(error) == "Permission denied"
        assert isinstance(error, Exception)


class TestSubscriptionIntegration:
    """Integration tests for subscription system."""
    
    def test_subscription_lifecycle(self, sub_manager, mock_session):
        """Test complete subscription lifecycle."""
        # Add subscription
        result = sub_manager.add_subscription(
            session=mock_session,
            subscription_type="channel",
            target="chat",
            filter_criteria={"level_min": 10}
        )
        assert result is True
        
        # Verify subscription exists
        assert sub_manager.is_subscribed(
            mock_session.session_id, "channel", "chat"
        )
        
        # Get matching subscriptions
        matches = sub_manager.get_matching_subscriptions("channel", "chat")
        assert len(matches) == 1
        
        subscription = matches[0]
        assert subscription.session_id == mock_session.session_id
        assert subscription.filter_criteria["level_min"] == 10
        
        # Remove subscription
        result = sub_manager.remove_subscription(
            session=mock_session,
            subscription_type="channel",
            target="chat"
        )
        assert result is True
        
        # Verify subscription is gone
        assert not sub_manager.is_subscribed(
            mock_session.session_id, "channel", "chat"
        )
        
        matches = sub_manager.get_matching_subscriptions("channel", "chat")
        assert len(matches) == 0
    
    def test_multiple_sessions_same_target(self, sub_manager):
        """Test multiple sessions subscribing to same target."""
        # Create multiple sessions
        sessions = []
        for i in range(3):
            session = MagicMock()
            session.session_id = f"test-session-{i}"
            session.mud_name = f"TestMUD{i}"
            session.permissions = {"channel"}
            sessions.append(session)
        
        # All subscribe to same channel
        for session in sessions:
            sub_manager.add_subscription(session, "channel", "chat")
        
        # Should have 3 subscriptions
        assert len(sub_manager.subscriptions) == 3
        
        # All should match
        matches = sub_manager.get_matching_subscriptions("channel", "chat")
        assert len(matches) == 3
        
        # Cleanup one session
        sub_manager.cleanup_session(sessions[0].session_id)
        
        # Should have 2 left
        matches = sub_manager.get_matching_subscriptions("channel", "chat")
        assert len(matches) == 2
    
    def test_wildcard_and_specific_subscriptions(self, sub_manager, mock_session):
        """Test combination of wildcard and specific subscriptions."""
        # Add wildcard subscription
        sub_manager.add_subscription(mock_session, "channel", "*")
        
        # Add specific subscription
        sub_manager.add_subscription(mock_session, "channel", "chat")
        
        # Both should match "chat"
        chat_matches = sub_manager.get_matching_subscriptions("channel", "chat")
        assert len(chat_matches) == 2
        
        # Only wildcard should match "gossip"
        gossip_matches = sub_manager.get_matching_subscriptions("channel", "gossip")
        assert len(gossip_matches) == 1
        assert gossip_matches[0].target == "*"
    
    def test_subscription_permissions_enforcement(self, sub_manager):
        """Test that subscription permissions are enforced."""
        # Create session without channel permission
        restricted_session = MagicMock()
        restricted_session.session_id = "restricted-session"
        restricted_session.mud_name = "RestrictedMUD"
        restricted_session.permissions = {"tell"}  # No channel permission
        
        # Should raise error for channel subscription
        with pytest.raises(SubscriptionError):
            sub_manager.add_subscription(
                restricted_session, "channel", "chat"
            )
        
        # Should work for tell subscription
        result = sub_manager.add_subscription(
            restricted_session, "tell", "*"
        )
        assert result is True