"""Session management for API clients.

This module handles client sessions, authentication, rate limiting,
and message queuing for the API server.
"""

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Set

from src.config.models import APIConfig
from src.utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class RateLimiter:
    """Token bucket rate limiter."""

    per_minute: int
    burst: int

    def __init__(self, per_minute: int = 100, burst: int = 20):
        """Initialize rate limiter.

        Args:
            per_minute: Requests allowed per minute
            burst: Maximum burst size
        """
        self.per_minute = per_minute
        self.burst = burst
        self.tokens = float(burst)
        self.last_update = time.time()
        self.refill_rate = per_minute / 60.0  # Tokens per second

    def check(self) -> bool:
        """Check if request is allowed.

        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()
        elapsed = now - self.last_update

        # Refill tokens
        self.tokens = min(self.burst, self.tokens + (elapsed * self.refill_rate))
        self.last_update = now

        # Check if we have a token
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True

        return False

    def reset(self):
        """Reset rate limiter to full capacity."""
        self.tokens = float(self.burst)
        self.last_update = time.time()


@dataclass
class SessionMetrics:
    """Metrics for a session."""

    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    rate_limit_hits: int = 0
    last_error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "errors": self.errors,
            "rate_limit_hits": self.rate_limit_hits,
            "last_error": self.last_error,
            "uptime_seconds": (datetime.utcnow() - self.created_at).total_seconds(),
        }


@dataclass
class Session:
    """Client session."""

    session_id: str
    mud_name: str
    api_key: str
    connected_at: datetime
    last_activity: datetime
    permissions: Set[str] = field(default_factory=set)
    subscriptions: Set[str] = field(default_factory=set)  # Channel subscriptions
    message_queue: Deque[str] = field(default_factory=deque)
    rate_limiter: RateLimiter = field(default_factory=RateLimiter)
    metrics: SessionMetrics = field(default_factory=SessionMetrics)
    websocket: Optional[Any] = None  # WebSocket connection if applicable
    tcp_connection: Optional[Any] = None  # TCP connection if applicable

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()

    def is_expired(self, timeout_seconds: int) -> bool:
        """Check if session has expired.

        Args:
            timeout_seconds: Session timeout in seconds

        Returns:
            True if expired, False otherwise
        """
        elapsed = (datetime.utcnow() - self.last_activity).total_seconds()
        return elapsed > timeout_seconds

    def is_connected(self) -> bool:
        """Check if session has an active connection.

        Returns:
            True if connected, False otherwise
        """
        if self.websocket:
            return not self.websocket.closed
        if self.tcp_connection:
            # Check TCP connection status
            return True  # Simplified for now
        return False

    async def send(self, message: str) -> bool:
        """Send message to client.

        Args:
            message: Message to send

        Returns:
            True if sent, False if queued or failed
        """
        self.metrics.messages_sent += 1

        if self.websocket and not self.websocket.closed:
            try:
                await self.websocket.send_str(message)
                return True
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")
                self.queue_message(message)
                return False
        elif self.tcp_connection:
            # Handle TCP send
            try:
                # Simplified TCP send
                return True
            except Exception as e:
                logger.error(f"Failed to send TCP message: {e}")
                self.queue_message(message)
                return False
        else:
            # No active connection, queue the message
            self.queue_message(message)
            return False

    def queue_message(self, message: str):
        """Queue message for later delivery.

        Args:
            message: Message to queue
        """
        # Limit queue size to prevent memory issues
        max_queue_size = 1000
        if len(self.message_queue) >= max_queue_size:
            # Remove oldest message
            self.message_queue.popleft()

        self.message_queue.append(message)

    async def flush_queue(self) -> int:
        """Flush queued messages to client.

        Returns:
            Number of messages sent
        """
        sent = 0
        while self.message_queue and self.is_connected():
            message = self.message_queue.popleft()
            if await self.send(message):
                sent += 1
            else:
                # Failed to send, put it back
                self.message_queue.appendleft(message)
                break

        return sent

    async def check_rate_limit(self, method: str) -> bool:
        """Check if request is within rate limits.

        Args:
            method: Method being called

        Returns:
            True if allowed, False if rate limited
        """
        if self.rate_limiter.check():
            return True

        self.metrics.rate_limit_hits += 1
        return False

    def has_permission(self, permission: str) -> bool:
        """Check if session has a permission.

        Args:
            permission: Permission to check

        Returns:
            True if has permission, False otherwise
        """
        return "*" in self.permissions or permission in self.permissions

    def subscribe(self, channel: str):
        """Subscribe to a channel.

        Args:
            channel: Channel name
        """
        self.subscriptions.add(channel)
        logger.info(f"Session {self.session_id} subscribed to {channel}")

    def unsubscribe(self, channel: str):
        """Unsubscribe from a channel.

        Args:
            channel: Channel name
        """
        self.subscriptions.discard(channel)
        logger.info(f"Session {self.session_id} unsubscribed from {channel}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "mud_name": self.mud_name,
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "is_connected": self.is_connected(),
            "permissions": list(self.permissions),
            "subscriptions": list(self.subscriptions),
            "queued_messages": len(self.message_queue),
            "metrics": self.metrics.to_dict(),
        }


class SessionManager:
    """Manages client sessions."""

    def __init__(self, config: APIConfig):
        """Initialize session manager.

        Args:
            config: API configuration
        """
        self.config = config
        self.sessions: Dict[str, Session] = {}
        self.sessions_by_mud: Dict[str, Set[str]] = defaultdict(set)
        self.api_keys: Dict[str, Dict[str, Any]] = {}

        # Load API keys from config
        if config.auth and config.auth.api_keys:
            for key_config in config.auth.api_keys:
                self.api_keys[key_config.key] = {
                    "mud_name": key_config.mud_name,
                    "permissions": set(key_config.permissions),
                    "rate_limit_override": key_config.rate_limit_override,
                }

        logger.info(f"Session manager initialized with {len(self.api_keys)} API keys")

    async def authenticate(self, api_key: str) -> Session:
        """Authenticate and create a session.

        Args:
            api_key: API key to authenticate

        Returns:
            Session object

        Raises:
            ValueError: If authentication fails
        """
        if not self.config.auth or not self.config.auth.enabled:
            # Authentication disabled, create default session
            return self._create_session("default", api_key, set(["*"]))

        key_info = self.api_keys.get(api_key)
        if not key_info:
            raise ValueError("Invalid API key")

        # Create session
        session = self._create_session(key_info["mud_name"], api_key, key_info["permissions"])

        # Apply rate limit override if specified
        if key_info.get("rate_limit_override"):
            rate_limit = key_info["rate_limit_override"]
            session.rate_limiter = RateLimiter(
                per_minute=rate_limit, burst=max(20, rate_limit // 3)
            )
        elif self.config.rate_limits and self.config.rate_limits.default:
            session.rate_limiter = RateLimiter(
                per_minute=self.config.rate_limits.default.per_minute,
                burst=self.config.rate_limits.default.burst,
            )

        return session

    def _create_session(self, mud_name: str, api_key: str, permissions: Set[str]) -> Session:
        """Create a new session.

        Args:
            mud_name: MUD name
            api_key: API key
            permissions: Set of permissions

        Returns:
            Session object
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        session = Session(
            session_id=session_id,
            mud_name=mud_name,
            api_key=api_key,
            connected_at=now,
            last_activity=now,
            permissions=permissions,
        )

        # Store session
        self.sessions[session_id] = session
        self.sessions_by_mud[mud_name].add(session_id)

        logger.info(f"Created session {session_id} for {mud_name}")

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session or None
        """
        return self.sessions.get(session_id)

    def get_sessions_by_mud(self, mud_name: str) -> List[Session]:
        """Get all sessions for a MUD.

        Args:
            mud_name: MUD name

        Returns:
            List of sessions
        """
        session_ids = self.sessions_by_mud.get(mud_name, set())
        return [self.sessions[sid] for sid in session_ids if sid in self.sessions]

    async def disconnect(self, session: Session):
        """Handle session disconnection.

        Args:
            session: Session to disconnect
        """
        logger.info(f"Disconnecting session {session.session_id}")

        # Clear connection references
        session.websocket = None
        session.tcp_connection = None

        # Session remains in memory for reconnection
        # It will be cleaned up by cleanup_expired if inactive

    async def cleanup_expired(self):
        """Clean up expired sessions."""
        if not self.config.session:
            return

        timeout = self.config.session.timeout
        expired = []

        for session_id, session in self.sessions.items():
            if session.is_expired(timeout) and not session.is_connected():
                expired.append(session_id)

        for session_id in expired:
            session = self.sessions[session_id]
            logger.info(f"Cleaning up expired session {session_id} for {session.mud_name}")

            # Remove from indexes
            self.sessions_by_mud[session.mud_name].discard(session_id)
            if not self.sessions_by_mud[session.mud_name]:
                del self.sessions_by_mud[session.mud_name]

            # Remove session
            del self.sessions[session_id]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    async def cleanup(self):
        """Clean up all sessions."""
        logger.info("Cleaning up all sessions")

        for session in self.sessions.values():
            if session.websocket:
                try:
                    await session.websocket.close()
                except:
                    pass

        self.sessions.clear()
        self.sessions_by_mud.clear()

    def get_active_count(self) -> int:
        """Get count of active sessions.

        Returns:
            Number of active sessions
        """
        return sum(1 for session in self.sessions.values() if session.is_connected())

    def get_all_sessions(self) -> List[Session]:
        """Get all sessions.

        Returns:
            List of all sessions
        """
        return list(self.sessions.values())

    def get_statistics(self) -> Dict[str, Any]:
        """Get session statistics.

        Returns:
            Statistics dictionary
        """
        active = 0
        inactive = 0
        total_messages_sent = 0
        total_messages_received = 0
        total_errors = 0
        muds = set()

        for session in self.sessions.values():
            if session.is_connected():
                active += 1
            else:
                inactive += 1

            total_messages_sent += session.metrics.messages_sent
            total_messages_received += session.metrics.messages_received
            total_errors += session.metrics.errors
            muds.add(session.mud_name)

        return {
            "total_sessions": len(self.sessions),
            "active_sessions": active,
            "inactive_sessions": inactive,
            "unique_muds": len(muds),
            "total_messages_sent": total_messages_sent,
            "total_messages_received": total_messages_received,
            "total_errors": total_errors,
        }


# Global session manager instance (will be initialized by the server)
session_manager: Optional[SessionManager] = None
