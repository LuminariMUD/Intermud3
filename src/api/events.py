"""Event distribution system for real-time notifications.

This module manages event dispatching to connected API clients.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from src.api.session import Session
from src.utils.logging import get_logger


logger = get_logger(__name__)


class EventType(Enum):
    """Event types for the API."""

    # Communication Events
    TELL_RECEIVED = "tell_received"
    EMOTETO_RECEIVED = "emoteto_received"
    CHANNEL_MESSAGE = "channel_message"
    CHANNEL_EMOTE = "channel_emote"

    # System Events
    MUD_ONLINE = "mud_online"
    MUD_OFFLINE = "mud_offline"
    CHANNEL_JOINED = "channel_joined"
    CHANNEL_LEFT = "channel_left"
    ERROR_OCCURRED = "error_occurred"
    GATEWAY_RECONNECTED = "gateway_reconnected"

    # User Events
    USER_JOINED_CHANNEL = "user_joined_channel"
    USER_LEFT_CHANNEL = "user_left_channel"
    USER_STATUS_CHANGED = "user_status_changed"

    # Administrative Events
    MAINTENANCE_SCHEDULED = "maintenance_scheduled"
    SHUTDOWN_WARNING = "shutdown_warning"
    RATE_LIMIT_WARNING = "rate_limit_warning"


@dataclass
class Event:
    """Base event class."""

    type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: int = 5  # 1-10, 1 is highest priority
    ttl: Optional[int] = None  # Time to live in seconds

    def to_json_rpc(self) -> str:
        """Convert event to JSON-RPC notification format.

        Returns:
            JSON-RPC formatted notification string
        """
        notification = {
            "jsonrpc": "2.0",
            "method": self.type.value,
            "params": {**self.data, "timestamp": self.timestamp.isoformat() + "Z"},
        }
        return json.dumps(notification)

    def is_expired(self) -> bool:
        """Check if event has expired based on TTL.

        Returns:
            True if expired, False otherwise
        """
        if self.ttl is None:
            return False

        elapsed = (datetime.utcnow() - self.timestamp).total_seconds()
        return elapsed > self.ttl


@dataclass
class EventFilter:
    """Filter for event subscriptions."""

    event_types: Set[EventType] = field(default_factory=set)
    channels: Set[str] = field(default_factory=set)  # Specific channels to filter
    mud_names: Set[str] = field(default_factory=set)  # Specific MUDs to filter
    exclude_self: bool = True  # Exclude events from same MUD

    def matches(self, event: Event, session: Session) -> bool:
        """Check if event matches filter criteria.

        Args:
            event: Event to check
            session: Session to check against

        Returns:
            True if event matches filter, False otherwise
        """
        # Check event type filter
        if self.event_types and event.type not in self.event_types:
            return False

        # Check channel filter for channel events
        if event.type in [EventType.CHANNEL_MESSAGE, EventType.CHANNEL_EMOTE]:
            channel = event.data.get("channel")
            if self.channels and channel not in self.channels:
                return False

        # Check MUD name filter
        from_mud = event.data.get("from_mud") or event.data.get("mud_name")
        if self.mud_names and from_mud not in self.mud_names:
            return False

        # Check exclude_self
        if self.exclude_self and from_mud == session.mud_name:
            return False

        return True


class EventDispatcher:
    """Manages event distribution to connected clients."""

    def __init__(self):
        """Initialize event dispatcher."""
        self.sessions: Dict[str, Session] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.filters: Dict[str, EventFilter] = {}
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        self.running = False
        self.dispatch_task: Optional[asyncio.Task] = None
        self.stats = {"events_dispatched": 0, "events_dropped": 0, "events_queued": 0}

    async def start(self):
        """Start the event dispatcher."""
        if self.running:
            logger.warning("Event dispatcher already running")
            return

        self.running = True
        self.dispatch_task = asyncio.create_task(self._dispatch_loop())
        logger.info("Event dispatcher started")

    async def stop(self):
        """Stop the event dispatcher."""
        self.running = False

        if self.dispatch_task:
            self.dispatch_task.cancel()
            try:
                await self.dispatch_task
            except asyncio.CancelledError:
                pass

        logger.info("Event dispatcher stopped")

    async def _dispatch_loop(self):
        """Main dispatch loop."""
        while self.running:
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)

                # Dispatch event
                await self._dispatch_event(event)

            except asyncio.TimeoutError:
                # Check for expired events in queues
                await self._cleanup_expired_events()
            except Exception as e:
                logger.error(f"Error in dispatch loop: {e}")

    async def _dispatch_event(self, event: Event):
        """Dispatch single event to subscribers.

        Args:
            event: Event to dispatch
        """
        # Check if event is expired
        if event.is_expired():
            self.stats["events_dropped"] += 1
            logger.debug(f"Dropping expired event: {event.type}")
            return

        # Get list of sessions to dispatch to
        target_sessions = []
        for session_id, session in self.sessions.items():
            if self._should_send_event(session, event):
                target_sessions.append(session)

        # Dispatch to each session
        dispatch_tasks = []
        for session in target_sessions:
            dispatch_tasks.append(self._send_event_to_session(session, event))

        # Wait for all dispatches to complete
        if dispatch_tasks:
            results = await asyncio.gather(*dispatch_tasks, return_exceptions=True)

            # Log any errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to dispatch event to session: {result}")

        self.stats["events_dispatched"] += 1

    def _should_send_event(self, session: Session, event: Event) -> bool:
        """Check if event should be sent to session.

        Args:
            session: Session to check
            event: Event to check

        Returns:
            True if event should be sent, False otherwise
        """
        # Check if session is connected
        if not session.is_connected():
            return False

        # Check permissions for event type
        if not self._check_permissions(session, event):
            return False

        # Check channel subscriptions for channel events
        if event.type in [EventType.CHANNEL_MESSAGE, EventType.CHANNEL_EMOTE]:
            channel = event.data.get("channel")
            if channel and channel not in session.subscriptions:
                return False

        # Check custom filter if exists
        filter_obj = self.filters.get(session.session_id)
        if filter_obj and not filter_obj.matches(event, session):
            return False

        return True

    def _check_permissions(self, session: Session, event: Event) -> bool:
        """Check if session has permission for event type.

        Args:
            session: Session to check
            event: Event to check

        Returns:
            True if permitted, False otherwise
        """
        # Map event types to required permissions
        permission_map = {
            EventType.TELL_RECEIVED: "tell",
            EventType.EMOTETO_RECEIVED: "tell",
            EventType.CHANNEL_MESSAGE: "channel",
            EventType.CHANNEL_EMOTE: "channel",
            EventType.MUD_ONLINE: "info",
            EventType.MUD_OFFLINE: "info",
            EventType.CHANNEL_JOINED: "channel",
            EventType.CHANNEL_LEFT: "channel",
            EventType.USER_JOINED_CHANNEL: "channel",
            EventType.USER_LEFT_CHANNEL: "channel",
            EventType.USER_STATUS_CHANGED: "info",
            EventType.ERROR_OCCURRED: "*",  # All users get errors
            EventType.GATEWAY_RECONNECTED: "*",  # All users get reconnect notices
            EventType.MAINTENANCE_SCHEDULED: "*",
            EventType.SHUTDOWN_WARNING: "*",
            EventType.RATE_LIMIT_WARNING: "*",
        }

        required_perm = permission_map.get(event.type, "info")

        # Check if user has wildcard permission
        if "*" in session.permissions:
            return True

        # Check if event requires wildcard (all users)
        if required_perm == "*":
            return True

        # Check specific permission
        return required_perm in session.permissions

    async def _send_event_to_session(self, session: Session, event: Event):
        """Send event to specific session.

        Args:
            session: Session to send to
            event: Event to send
        """
        try:
            message = event.to_json_rpc()
            sent = await session.send(message)

            if not sent:
                logger.debug(f"Event queued for session {session.session_id}")
        except Exception as e:
            logger.error(f"Failed to send event to session {session.session_id}: {e}")

    async def _cleanup_expired_events(self):
        """Clean up expired events from session queues."""
        # This would clean up expired events from session message queues
        # For now, just a placeholder

    def register_session(self, session: Session):
        """Register a session for event dispatch.

        Args:
            session: Session to register
        """
        self.sessions[session.session_id] = session
        logger.debug(f"Registered session {session.session_id} for events")

    def unregister_session(self, session_id: str):
        """Unregister a session from event dispatch.

        Args:
            session_id: Session ID to unregister
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.debug(f"Unregistered session {session_id} from events")

        # Remove filter if exists
        if session_id in self.filters:
            del self.filters[session_id]

    def set_filter(self, session_id: str, filter_obj: EventFilter):
        """Set event filter for session.

        Args:
            session_id: Session ID
            filter_obj: Filter to apply
        """
        self.filters[session_id] = filter_obj
        logger.debug(f"Set filter for session {session_id}")

    async def dispatch(self, event: Event):
        """Queue event for dispatch.

        Args:
            event: Event to dispatch
        """
        # Add to queue
        await self.event_queue.put(event)
        self.stats["events_queued"] += 1

    def create_event(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        priority: int = 5,
        ttl: Optional[int] = None,
    ) -> Event:
        """Create a new event.

        Args:
            event_type: Type of event
            data: Event data
            priority: Event priority (1-10, 1 is highest)
            ttl: Time to live in seconds

        Returns:
            Created event
        """
        return Event(type=event_type, data=data, priority=priority, ttl=ttl)

    def get_stats(self) -> Dict[str, Any]:
        """Get dispatcher statistics.

        Returns:
            Statistics dictionary
        """
        return {
            **self.stats,
            "active_sessions": len(self.sessions),
            "queue_size": self.event_queue.qsize(),
            "filters_active": len(self.filters),
        }


# Global event dispatcher instance
event_dispatcher = EventDispatcher()
