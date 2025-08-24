"""
State management for API clients.

This module provides:
- Per-client state tracking
- Channel membership management
- Message history buffers
- Statistics aggregation
- Session persistence
"""

import asyncio
import json
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

import structlog

from ..config import Settings as Config
from .session import Session


logger = structlog.get_logger(__name__)


@dataclass
class ClientStatistics:
    """Statistics tracked per client."""

    messages_sent: int = 0
    messages_received: int = 0
    tells_sent: int = 0
    tells_received: int = 0
    channels_joined: int = 0
    channels_left: int = 0
    errors_encountered: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    last_activity: datetime = field(default_factory=datetime.utcnow)

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["last_activity"] = self.last_activity.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "ClientStatistics":
        """Create from dictionary."""
        if "last_activity" in data:
            data["last_activity"] = datetime.fromisoformat(data["last_activity"])
        return cls(**data)


@dataclass
class ChannelState:
    """State for a channel membership."""

    channel_name: str
    joined_at: datetime = field(default_factory=datetime.utcnow)
    listen_only: bool = False
    last_message: Optional[datetime] = None
    message_count: int = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "channel_name": self.channel_name,
            "joined_at": self.joined_at.isoformat(),
            "listen_only": self.listen_only,
            "last_message": self.last_message.isoformat() if self.last_message else None,
            "message_count": self.message_count,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ChannelState":
        """Create from dictionary."""
        data["joined_at"] = datetime.fromisoformat(data["joined_at"])
        if data.get("last_message"):
            data["last_message"] = datetime.fromisoformat(data["last_message"])
        return cls(**data)


class MessageHistory:
    """Circular buffer for message history."""

    def __init__(self, max_size: int = 100):
        """Initialize message history buffer."""
        self.max_size = max_size
        self.messages: Deque[Dict] = deque(maxlen=max_size)

    def add(self, message: Dict):
        """Add a message to history."""
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()
        self.messages.append(message)

    def get_recent(self, count: int = 10) -> List[Dict]:
        """Get recent messages."""
        return list(self.messages)[-count:]

    def get_since(self, timestamp: datetime) -> List[Dict]:
        """Get messages since a timestamp."""
        result = []
        for msg in self.messages:
            msg_time = datetime.fromisoformat(msg["timestamp"])
            if msg_time > timestamp:
                result.append(msg)
        return result

    def clear(self):
        """Clear message history."""
        self.messages.clear()

    def to_list(self) -> List[Dict]:
        """Convert to list for serialization."""
        return list(self.messages)

    def from_list(self, messages: List[Dict]):
        """Load from list."""
        self.messages = deque(messages[-self.max_size :], maxlen=self.max_size)


class ClientState:
    """Complete state for a client connection."""

    def __init__(self, session: Session, config: Optional[Dict] = None):
        """Initialize client state."""
        self.session = session
        self.config = config or {}

        # Channel memberships
        self.channels: Dict[str, ChannelState] = {}

        # Message histories
        self.tell_history = MessageHistory(self.config.get("tell_history_size", 50))
        self.channel_history: Dict[str, MessageHistory] = {}

        # Statistics
        self.statistics = ClientStatistics()

        # Client preferences
        self.preferences: Dict[str, Any] = {}

        # Temporary state
        self.temp_state: Dict[str, Any] = {}

        # Last known status
        self.last_ping: Optional[datetime] = None
        self.is_active = True

        logger.debug(
            "client_state_initialized", session_id=session.session_id, mud_name=session.mud_name
        )

    def join_channel(self, channel_name: str, listen_only: bool = False):
        """Record channel join."""
        if channel_name not in self.channels:
            self.channels[channel_name] = ChannelState(
                channel_name=channel_name, listen_only=listen_only
            )

            # Create history buffer for channel
            if channel_name not in self.channel_history:
                self.channel_history[channel_name] = MessageHistory(
                    self.config.get("channel_history_size", 100)
                )

            self.statistics.channels_joined += 1
            self.statistics.update_activity()

            logger.info(
                "client_joined_channel",
                session_id=self.session.session_id,
                channel=channel_name,
                listen_only=listen_only,
            )

    def leave_channel(self, channel_name: str):
        """Record channel leave."""
        if channel_name in self.channels:
            del self.channels[channel_name]
            self.statistics.channels_left += 1
            self.statistics.update_activity()

            logger.info(
                "client_left_channel", session_id=self.session.session_id, channel=channel_name
            )

    def add_tell_to_history(self, tell: Dict):
        """Add a tell to history."""
        self.tell_history.add(tell)

        # Update statistics
        if tell.get("direction") == "sent":
            self.statistics.tells_sent += 1
        else:
            self.statistics.tells_received += 1

        self.statistics.update_activity()

    def add_channel_message_to_history(self, channel: str, message: Dict):
        """Add a channel message to history."""
        if channel not in self.channel_history:
            self.channel_history[channel] = MessageHistory(
                self.config.get("channel_history_size", 100)
            )

        self.channel_history[channel].add(message)

        # Update channel state
        if channel in self.channels:
            self.channels[channel].last_message = datetime.utcnow()
            self.channels[channel].message_count += 1

        self.statistics.messages_received += 1
        self.statistics.update_activity()

    def get_channel_list(self) -> List[str]:
        """Get list of joined channels."""
        return list(self.channels.keys())

    def is_in_channel(self, channel_name: str) -> bool:
        """Check if client is in a channel."""
        return channel_name in self.channels

    def set_preference(self, key: str, value: Any):
        """Set a client preference."""
        self.preferences[key] = value
        logger.debug(
            "client_preference_set", session_id=self.session.session_id, key=key, value=value
        )

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a client preference."""
        return self.preferences.get(key, default)

    def update_ping(self):
        """Update last ping timestamp."""
        self.last_ping = datetime.utcnow()
        self.statistics.update_activity()

    def is_stale(self, timeout_seconds: int = 3600) -> bool:
        """Check if client state is stale."""
        if not self.last_ping:
            return False

        age = (datetime.utcnow() - self.last_ping).total_seconds()
        return age > timeout_seconds

    def to_dict(self) -> Dict:
        """Convert state to dictionary for persistence."""
        return {
            "session_id": self.session.session_id,
            "mud_name": self.session.mud_name,
            "channels": {name: ch.to_dict() for name, ch in self.channels.items()},
            "tell_history": self.tell_history.to_list(),
            "channel_history": {
                name: hist.to_list() for name, hist in self.channel_history.items()
            },
            "statistics": self.statistics.to_dict(),
            "preferences": self.preferences,
            "last_ping": self.last_ping.isoformat() if self.last_ping else None,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(
        cls, data: Dict, session: Session, config: Optional[Dict] = None
    ) -> "ClientState":
        """Create state from dictionary."""
        state = cls(session, config)

        # Restore channels
        for name, ch_data in data.get("channels", {}).items():
            state.channels[name] = ChannelState.from_dict(ch_data)

        # Restore histories
        state.tell_history.from_list(data.get("tell_history", []))

        for name, messages in data.get("channel_history", {}).items():
            if name not in state.channel_history:
                state.channel_history[name] = MessageHistory(
                    config.get("channel_history_size", 100) if config else 100
                )
            state.channel_history[name].from_list(messages)

        # Restore statistics
        if "statistics" in data:
            state.statistics = ClientStatistics.from_dict(data["statistics"])

        # Restore preferences
        state.preferences = data.get("preferences", {})

        # Restore timestamps
        if data.get("last_ping"):
            state.last_ping = datetime.fromisoformat(data["last_ping"])
        state.is_active = data.get("is_active", True)

        return state


class StateManager:
    """Manages state for all connected clients."""

    def __init__(self, config: Config):
        """Initialize state manager."""
        self.config = config.api.get("state", {})
        self.clients: Dict[str, ClientState] = {}

        # Persistence settings
        self.persistence_enabled = self.config.get("persistence_enabled", False)
        self.persistence_path = Path(self.config.get("persistence_path", "data/api_state"))
        self.persistence_interval = self.config.get("persistence_interval", 300)

        # Cleanup settings
        self.cleanup_interval = self.config.get("cleanup_interval", 600)
        self.stale_timeout = self.config.get("stale_timeout", 3600)

        # Statistics
        self.global_stats = {
            "total_sessions": 0,
            "active_sessions": 0,
            "total_messages": 0,
            "total_tells": 0,
            "start_time": datetime.utcnow(),
        }

        # Background tasks
        self._persistence_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Load persisted state if enabled
        if self.persistence_enabled:
            self._load_persisted_state()

        logger.info(
            "state_manager_initialized",
            persistence_enabled=self.persistence_enabled,
            persistence_path=str(self.persistence_path),
        )

    def get_or_create_client_state(self, session: Session) -> ClientState:
        """Get existing client state or create new one."""
        if session.session_id not in self.clients:
            self.clients[session.session_id] = ClientState(
                session, self.config.get("client_config", {})
            )
            self.global_stats["total_sessions"] += 1

            logger.debug(
                "client_state_created", session_id=session.session_id, mud_name=session.mud_name
            )

        return self.clients[session.session_id]

    def get_client_state(self, session_id: str) -> Optional[ClientState]:
        """Get client state by session ID."""
        return self.clients.get(session_id)

    def remove_client_state(self, session_id: str):
        """Remove client state."""
        if session_id in self.clients:
            del self.clients[session_id]
            logger.debug("client_state_removed", session_id=session_id)

    def get_channel_members(self, channel_name: str) -> List[str]:
        """Get list of MUDs in a channel."""
        members = []
        for client in self.clients.values():
            if client.is_in_channel(channel_name):
                members.append(client.session.mud_name)
        return members

    def get_active_sessions(self) -> List[Session]:
        """Get list of active sessions."""
        active = []
        for client in self.clients.values():
            if client.is_active and not client.is_stale(self.stale_timeout):
                active.append(client.session)
        return active

    def get_statistics(self) -> Dict:
        """Get global statistics."""
        active_count = len(self.get_active_sessions())
        uptime = (datetime.utcnow() - self.global_stats["start_time"]).total_seconds()

        return {
            "total_sessions": self.global_stats["total_sessions"],
            "active_sessions": active_count,
            "total_messages": self.global_stats["total_messages"],
            "total_tells": self.global_stats["total_tells"],
            "uptime_seconds": uptime,
            "clients": len(self.clients),
            "memory_usage": self._estimate_memory_usage(),
        }

    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage in bytes."""
        # Rough estimation based on number of clients and histories
        base_per_client = 1024  # 1KB base
        per_message = 200  # 200 bytes per message

        total = 0
        for client in self.clients.values():
            total += base_per_client
            total += len(client.tell_history.messages) * per_message
            for history in client.channel_history.values():
                total += len(history.messages) * per_message

        return total

    async def start_background_tasks(self):
        """Start background maintenance tasks."""
        if self.persistence_enabled:
            self._persistence_task = asyncio.create_task(self._persistence_loop())

        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("state_manager_background_tasks_started")

    async def stop_background_tasks(self):
        """Stop background tasks."""
        if self._persistence_task:
            self._persistence_task.cancel()
            try:
                await self._persistence_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Final persistence
        if self.persistence_enabled:
            self._persist_state()

        logger.info("state_manager_background_tasks_stopped")

    async def _persistence_loop(self):
        """Periodically persist state to disk."""
        while True:
            try:
                await asyncio.sleep(self.persistence_interval)
                self._persist_state()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("state_persistence_error", error=str(e))

    async def _cleanup_loop(self):
        """Periodically clean up stale state."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                self._cleanup_stale_clients()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("state_cleanup_error", error=str(e))

    def _cleanup_stale_clients(self):
        """Remove stale client states."""
        to_remove = []

        for session_id, client in self.clients.items():
            if client.is_stale(self.stale_timeout):
                to_remove.append(session_id)

        for session_id in to_remove:
            self.remove_client_state(session_id)

        if to_remove:
            logger.info("stale_clients_removed", count=len(to_remove))

    def _persist_state(self):
        """Persist current state to disk."""
        if not self.persistence_enabled:
            return

        try:
            # Create persistence directory
            self.persistence_path.mkdir(parents=True, exist_ok=True)

            # Save each client state
            for session_id, client in self.clients.items():
                file_path = self.persistence_path / f"{session_id}.json"
                with open(file_path, "w") as f:
                    json.dump(client.to_dict(), f, indent=2)

            # Save global stats
            stats_path = self.persistence_path / "global_stats.json"
            stats_data = self.global_stats.copy()
            stats_data["start_time"] = stats_data["start_time"].isoformat()
            with open(stats_path, "w") as f:
                json.dump(stats_data, f, indent=2)

            logger.debug("state_persisted", clients_count=len(self.clients))

        except Exception as e:
            logger.error("state_persistence_failed", error=str(e))

    def _load_persisted_state(self):
        """Load persisted state from disk."""
        if not self.persistence_path.exists():
            return

        try:
            # Load global stats
            stats_path = self.persistence_path / "global_stats.json"
            if stats_path.exists():
                with open(stats_path) as f:
                    stats_data = json.load(f)
                    stats_data["start_time"] = datetime.fromisoformat(stats_data["start_time"])
                    self.global_stats.update(stats_data)

            # Note: Individual client states would need sessions to be restored
            # This is handled when clients reconnect with their session tokens

            logger.info("persisted_state_loaded", stats=self.global_stats)

        except Exception as e:
            logger.error("state_load_failed", error=str(e))
