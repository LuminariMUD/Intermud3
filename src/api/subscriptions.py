"""Subscription management for API clients.

This module handles channel subscriptions and event filtering.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from src.api.events import EventFilter, EventType
from src.utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class ChannelSubscription:
    """Channel subscription details."""

    channel_name: str
    joined_at: datetime = field(default_factory=datetime.utcnow)
    listen_only: bool = False
    last_message_at: Optional[datetime] = None
    message_count: int = 0

    def update_activity(self):
        """Update last message timestamp."""
        self.last_message_at = datetime.utcnow()
        self.message_count += 1


@dataclass
class SubscriptionPreferences:
    """User subscription preferences."""

    # Event type subscriptions
    event_types: Set[EventType] = field(
        default_factory=lambda: {
            EventType.TELL_RECEIVED,
            EventType.EMOTETO_RECEIVED,
            EventType.ERROR_OCCURRED,
            EventType.GATEWAY_RECONNECTED,
            EventType.MAINTENANCE_SCHEDULED,
            EventType.SHUTDOWN_WARNING,
            EventType.RATE_LIMIT_WARNING,
        }
    )

    # Channel filtering
    filter_channels: bool = False  # Only receive from subscribed channels
    channel_whitelist: Set[str] = field(default_factory=set)
    channel_blacklist: Set[str] = field(default_factory=set)

    # MUD filtering
    filter_muds: bool = False  # Only receive from specific MUDs
    mud_whitelist: Set[str] = field(default_factory=set)
    mud_blacklist: Set[str] = field(default_factory=set)

    # User filtering
    filter_users: bool = False  # Filter by user names
    user_whitelist: Set[str] = field(default_factory=set)
    user_blacklist: Set[str] = field(default_factory=set)

    # Options
    exclude_self: bool = True  # Don't receive own events
    priority_threshold: int = 10  # Only receive events with priority <= this

    def to_event_filter(self) -> EventFilter:
        """Convert preferences to event filter.

        Returns:
            EventFilter object
        """
        return EventFilter(
            event_types=self.event_types,
            channels=self.channel_whitelist if self.filter_channels else set(),
            mud_names=self.mud_whitelist if self.filter_muds else set(),
            exclude_self=self.exclude_self,
        )


class SubscriptionManager:
    """Manages client subscriptions and preferences."""

    def __init__(self):
        """Initialize subscription manager."""
        # Channel subscriptions per session
        self.channel_subscriptions: Dict[str, Dict[str, ChannelSubscription]] = {}

        # Subscription preferences per session
        self.preferences: Dict[str, SubscriptionPreferences] = {}

        # Channel member tracking
        self.channel_members: Dict[str, Set[str]] = {}

        # For test compatibility - generic subscriptions tracking
        self.subscriptions: Set[Any] = set()
        self.session_subscriptions: Dict[str, Set[Any]] = {}
        self.type_subscriptions: Dict[str, Set[Any]] = {}

        # Statistics
        self.stats = {"total_subscriptions": 0, "active_channels": 0, "subscription_changes": 0}

    def subscribe_channel(
        self, session_id: str, channel_name: str, listen_only: bool = False
    ) -> bool:
        """Subscribe session to channel.

        Args:
            session_id: Session ID
            channel_name: Channel name
            listen_only: Whether to subscribe in listen-only mode

        Returns:
            True if subscribed, False if already subscribed
        """
        # Initialize session subscriptions if needed
        if session_id not in self.channel_subscriptions:
            self.channel_subscriptions[session_id] = {}

        # Check if already subscribed
        if channel_name in self.channel_subscriptions[session_id]:
            logger.debug(f"Session {session_id} already subscribed to {channel_name}")
            return False

        # Create subscription
        subscription = ChannelSubscription(channel_name=channel_name, listen_only=listen_only)

        self.channel_subscriptions[session_id][channel_name] = subscription

        # Add to channel members
        if channel_name not in self.channel_members:
            self.channel_members[channel_name] = set()
        self.channel_members[channel_name].add(session_id)

        # Update stats
        self.stats["total_subscriptions"] += 1
        self.stats["subscription_changes"] += 1
        self._update_active_channels()

        logger.info(f"Session {session_id} subscribed to channel {channel_name}")
        return True

    def unsubscribe_channel(self, session_id: str, channel_name: str) -> bool:
        """Unsubscribe session from channel.

        Args:
            session_id: Session ID
            channel_name: Channel name

        Returns:
            True if unsubscribed, False if not subscribed
        """
        # Check if session has subscriptions
        if session_id not in self.channel_subscriptions:
            return False

        # Check if subscribed to channel
        if channel_name not in self.channel_subscriptions[session_id]:
            return False

        # Remove subscription
        del self.channel_subscriptions[session_id][channel_name]

        # Remove from channel members
        if channel_name in self.channel_members:
            self.channel_members[channel_name].discard(session_id)

            # Clean up empty channel
            if not self.channel_members[channel_name]:
                del self.channel_members[channel_name]

        # Clean up empty session
        if not self.channel_subscriptions[session_id]:
            del self.channel_subscriptions[session_id]

        # Update stats
        self.stats["total_subscriptions"] -= 1
        self.stats["subscription_changes"] += 1
        self._update_active_channels()

        logger.info(f"Session {session_id} unsubscribed from channel {channel_name}")
        return True

    def unsubscribe_all(self, session_id: str) -> int:
        """Unsubscribe session from all channels.

        Args:
            session_id: Session ID

        Returns:
            Number of channels unsubscribed from
        """
        if session_id not in self.channel_subscriptions:
            return 0

        channels = list(self.channel_subscriptions[session_id].keys())
        count = 0

        for channel in channels:
            if self.unsubscribe_channel(session_id, channel):
                count += 1

        return count

    def get_subscriptions(self, session_id: str) -> List[str]:
        """Get list of channels session is subscribed to.

        Args:
            session_id: Session ID

        Returns:
            List of channel names
        """
        if session_id not in self.channel_subscriptions:
            return []

        return list(self.channel_subscriptions[session_id].keys())

    def get_channel_subscriptions(self, session_id: str) -> Set[str]:
        """Get set of channels session is subscribed to.

        Args:
            session_id: Session ID

        Returns:
            Set of channel names
        """
        if session_id not in self.channel_subscriptions:
            return set()

        return set(self.channel_subscriptions[session_id].keys())

    def get_subscription_info(
        self, session_id: str, channel_name: str
    ) -> Optional[ChannelSubscription]:
        """Get subscription details for session and channel.

        Args:
            session_id: Session ID
            channel_name: Channel name

        Returns:
            ChannelSubscription if subscribed, None otherwise
        """
        if session_id not in self.channel_subscriptions:
            return None

        return self.channel_subscriptions[session_id].get(channel_name)

    def is_subscribed(self, session_id: str, channel_name: str) -> bool:
        """Check if session is subscribed to channel.

        Args:
            session_id: Session ID
            channel_name: Channel name

        Returns:
            True if subscribed, False otherwise
        """
        return self.get_subscription_info(session_id, channel_name) is not None

    def get_channel_members(self, channel_name: str) -> List[str]:
        """Get list of sessions subscribed to channel.

        Args:
            channel_name: Channel name

        Returns:
            List of session IDs
        """
        return list(self.channel_members.get(channel_name, []))

    def get_channel_count(self, channel_name: str) -> int:
        """Get number of subscribers to channel.

        Args:
            channel_name: Channel name

        Returns:
            Number of subscribers
        """
        return len(self.channel_members.get(channel_name, []))

    def get_all_channels(self) -> List[str]:
        """Get list of all active channels.

        Returns:
            List of channel names
        """
        return list(self.channel_members.keys())

    def set_preferences(self, session_id: str, preferences: SubscriptionPreferences):
        """Set subscription preferences for session.

        Args:
            session_id: Session ID
            preferences: Subscription preferences
        """
        self.preferences[session_id] = preferences
        logger.debug(f"Updated preferences for session {session_id}")

    def get_preferences(self, session_id: str) -> SubscriptionPreferences:
        """Get subscription preferences for session.

        Args:
            session_id: Session ID

        Returns:
            Subscription preferences (creates default if not exists)
        """
        if session_id not in self.preferences:
            self.preferences[session_id] = SubscriptionPreferences()

        return self.preferences[session_id]

    def update_channel_activity(self, session_id: str, channel_name: str):
        """Update activity timestamp for channel subscription.

        Args:
            session_id: Session ID
            channel_name: Channel name
        """
        subscription = self.get_subscription_info(session_id, channel_name)
        if subscription:
            subscription.update_activity()

    def cleanup_session(self, session_id: str):
        """Clean up all subscriptions for a session.

        Args:
            session_id: Session ID
        """
        # Unsubscribe from all channels
        self.unsubscribe_all(session_id)

        # Remove preferences
        if session_id in self.preferences:
            del self.preferences[session_id]

        logger.debug(f"Cleaned up subscriptions for session {session_id}")

    def _update_active_channels(self):
        """Update active channels count."""
        self.stats["active_channels"] = len(self.channel_members)

    def get_stats(self) -> Dict[str, any]:
        """Get subscription statistics.

        Returns:
            Statistics dictionary
        """
        return {
            **self.stats,
            "total_sessions": len(self.channel_subscriptions),
            "total_preferences": len(self.preferences),
        }


# Global subscription manager instance
subscription_manager = SubscriptionManager()
