"""Connection state models for Intermud3 Gateway.

This module defines data structures for tracking MUD information,
channel state, and user sessions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MudStatus(Enum):
    """MUD status enumeration."""

    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"
    REBOOT = "reboot"


@dataclass
class MudInfo:
    """Information about a MUD in the I3 network."""

    name: str
    address: str
    player_port: int
    tcp_port: int = 0
    udp_port: int = 0

    # MUD characteristics
    mudlib: str = ""
    base_mudlib: str = ""
    driver: str = ""
    mud_type: str = ""
    open_status: str = ""
    admin_email: str = ""

    # Supported services
    services: dict[str, int] = field(default_factory=dict)

    # State tracking
    status: MudStatus = MudStatus.UNKNOWN
    last_startup: datetime | None = None
    last_seen: datetime | None = None

    # Additional data
    other_data: dict[str, Any] = field(default_factory=dict)

    def supports_service(self, service: str) -> bool:
        """Check if MUD supports a specific service.

        Args:
            service: Service name to check

        Returns:
            True if service is supported
        """
        return service in self.services and self.services[service] > 0

    def is_online(self) -> bool:
        """Check if MUD is currently online."""
        return self.status == MudStatus.UP

    def update_from_mudlist(self, data: list[Any]) -> None:
        """Update MUD info from mudlist data.

        Args:
            data: Mudlist entry data array
        """
        if len(data) < 15:
            return

        # Update connection info
        if data[0]:  # Address
            self.address = str(data[0])
        if data[1]:  # Player port
            self.player_port = int(data[1])
        if data[2]:  # TCP port
            self.tcp_port = int(data[2])
        if data[3]:  # UDP port
            self.udp_port = int(data[3])

        # Update MUD characteristics
        if data[4]:
            self.mudlib = str(data[4])
        if data[5]:
            self.base_mudlib = str(data[5])
        if data[6]:
            self.driver = str(data[6])
        if data[7]:
            self.mud_type = str(data[7])
        if data[8]:
            self.open_status = str(data[8])
        if data[9]:
            self.admin_email = str(data[9])

        # Update services
        if data[10] and isinstance(data[10], dict):
            self.services = data[10]

        # Update other data
        if len(data) > 11 and isinstance(data[11], dict):
            self.other_data = data[11]

        # Update status
        if data[0] == "0":  # Address "0" means down
            self.status = MudStatus.DOWN
        else:
            self.status = MudStatus.UP

        self.last_seen = datetime.now()


@dataclass
class ChannelInfo:
    """Information about an I3 channel."""

    name: str
    owner: str = ""
    type: int = 0  # 0=public, 1=selective, 2=private

    # Channel configuration
    banned_muds: set[str] = field(default_factory=set)
    admitted_muds: set[str] = field(default_factory=set)

    # Current state
    listening_muds: set[str] = field(default_factory=set)
    active_users: dict[str, set[str]] = field(default_factory=dict)  # mud -> users

    # Statistics
    message_count: int = 0
    created_at: datetime | None = None
    last_activity: datetime | None = None

    def is_public(self) -> bool:
        """Check if channel is public."""
        return self.type == 0

    def is_selective(self) -> bool:
        """Check if channel is selective."""
        return self.type == 1

    def is_private(self) -> bool:
        """Check if channel is private."""
        return self.type == 2

    def can_access(self, mud_name: str) -> bool:
        """Check if a MUD can access this channel.

        Args:
            mud_name: Name of the MUD to check

        Returns:
            True if MUD can access the channel
        """
        if mud_name in self.banned_muds:
            return False

        if self.is_public():
            return True

        if self.is_selective() or self.is_private():
            return mud_name in self.admitted_muds

        return False

    def add_listener(self, mud_name: str):
        """Add a MUD as a listener to this channel."""
        self.listening_muds.add(mud_name)

    def remove_listener(self, mud_name: str):
        """Remove a MUD as a listener from this channel."""
        self.listening_muds.discard(mud_name)
        # Also remove any active users from that MUD
        self.active_users.pop(mud_name, None)

    def add_user(self, mud_name: str, user_name: str):
        """Add an active user to the channel."""
        if mud_name not in self.active_users:
            self.active_users[mud_name] = set()
        self.active_users[mud_name].add(user_name)
        self.last_activity = datetime.now()

    def remove_user(self, mud_name: str, user_name: str):
        """Remove an active user from the channel."""
        if mud_name in self.active_users:
            self.active_users[mud_name].discard(user_name)
            if not self.active_users[mud_name]:
                del self.active_users[mud_name]


@dataclass
class UserSession:
    """Represents a user session for the gateway."""

    session_id: str
    mud_name: str
    user_name: str

    # Authentication
    authenticated: bool = False
    auth_time: datetime | None = None
    auth_token: str | None = None

    # Session state
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    # User preferences
    blocked_users: set[str] = field(default_factory=set)
    blocked_muds: set[str] = field(default_factory=set)
    listening_channels: set[str] = field(default_factory=set)

    # Statistics
    messages_sent: int = 0
    messages_received: int = 0

    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = datetime.now()

    def is_blocked(self, mud_name: str, user_name: str) -> bool:
        """Check if a user/MUD is blocked.

        Args:
            mud_name: Name of the MUD
            user_name: Name of the user

        Returns:
            True if blocked
        """
        if mud_name in self.blocked_muds:
            return True

        full_name = f"{user_name}@{mud_name}"
        return full_name in self.blocked_users

    def block_user(self, mud_name: str, user_name: str):
        """Block a specific user."""
        full_name = f"{user_name}@{mud_name}"
        self.blocked_users.add(full_name)

    def unblock_user(self, mud_name: str, user_name: str):
        """Unblock a specific user."""
        full_name = f"{user_name}@{mud_name}"
        self.blocked_users.discard(full_name)

    def block_mud(self, mud_name: str):
        """Block all users from a MUD."""
        self.blocked_muds.add(mud_name)

    def unblock_mud(self, mud_name: str):
        """Unblock all users from a MUD."""
        self.blocked_muds.discard(mud_name)


@dataclass
class RouterConfig:
    """Configuration for connecting to an I3 router."""

    name: str
    address: str
    port: int

    # Authentication
    password: int | None = None

    # Connection parameters
    priority: int = 0
    connect_timeout: float = 30.0
    keepalive_interval: float = 60.0

    # Features
    supports_binary: bool = True
    supports_auth: bool = True

    def to_router_info(self) -> "RouterInfo":
        """Convert to RouterInfo for connection manager.

        Note: This imports RouterInfo from network.connection to avoid
        circular imports. In production, might want to restructure.
        """
        from ..network.connection import RouterInfo

        return RouterInfo(
            name=self.name, address=self.address, port=self.port, priority=self.priority
        )
