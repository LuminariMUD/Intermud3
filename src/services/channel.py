"""Channel service for inter-MUD chat channels.

This service handles channel messages, subscriptions, and management
for the I3 channel system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from ..models.packet import I3Packet, PacketType
from .base import BaseService


@dataclass
class ChannelSubscription:
    """Represents a channel subscription."""

    channel_name: str
    mud_name: str
    subscribed_at: datetime = field(default_factory=datetime.now)
    filters: list[str] = field(default_factory=list)
    is_admin: bool = False
    is_banned: bool = False


@dataclass
class ChannelHistory:
    """Stores channel message history."""

    messages: list[dict[str, Any]] = field(default_factory=list)
    max_size: int = 100

    def add_message(self, message: dict[str, Any]):
        """Add a message to history, maintaining max size."""
        self.messages.append(message)
        if len(self.messages) > self.max_size:
            self.messages = self.messages[-self.max_size :]

    def get_recent(self, count: int = 20) -> list[dict[str, Any]]:
        """Get recent messages."""
        return self.messages[-count:]


class ChannelService(BaseService):
    """Service for handling I3 channels."""

    service_name = "channel"
    supported_packets = [
        PacketType.CHANNEL_M,
        PacketType.CHANNEL_E,
        PacketType.CHANNEL_T,
        PacketType.CHANNEL_ADD,
        PacketType.CHANNEL_REMOVE,
        PacketType.CHANNEL_ADMIN,
        PacketType.CHANNEL_FILTER,
        PacketType.CHANNEL_WHO,
        PacketType.CHANNEL_LISTEN,
        PacketType.CHANLIST_REPLY,
    ]
    requires_auth = False

    def __init__(self, state_manager, gateway=None):
        """Initialize channel service.

        Args:
            state_manager: State manager instance
            gateway: Reference to the gateway for sending packets
        """
        super().__init__(state_manager)
        self.gateway = gateway
        self.logger = structlog.get_logger()

        # Channel subscriptions: channel_name -> set of (mud_name, user_name)
        self.subscriptions: dict[str, set[tuple[str, str]]] = {}

        # Channel history
        self.channel_history: dict[str, ChannelHistory] = {}

        # Channel administrators: channel_name -> set of mud_names
        self.channel_admins: dict[str, set[str]] = {}

        # Channel filters: channel_name -> list of filter patterns
        self.channel_filters: dict[str, list[str]] = {}

        # User channel subscriptions: (mud, user) -> set of channels
        self.user_channels: dict[tuple[str, str], set[str]] = {}

    async def initialize(self) -> None:
        """Initialize the channel service."""
        await super().initialize()

        # Load channel list from state manager
        channels = self.state_manager.channels
        for channel_name, channel_info in channels.items():
            # Initialize history for known channels
            self.channel_history[channel_name] = ChannelHistory()

            # Set up admin list if available
            if hasattr(channel_info, "owner") and channel_info.owner:
                self.channel_admins[channel_name] = {channel_info.owner}

        self.logger.info("Channel service initialized", channels=len(channels))

    async def handle_packet(self, packet: I3Packet) -> I3Packet | None:
        """Handle incoming channel packet.

        Args:
            packet: The incoming packet

        Returns:
            Optional response packet
        """
        packet_type = packet.packet_type

        if packet_type == PacketType.CHANNEL_M:
            return await self._handle_channel_message(packet)
        if packet_type == PacketType.CHANNEL_E:
            return await self._handle_channel_emote(packet)
        if packet_type == PacketType.CHANNEL_T:
            return await self._handle_channel_targeted_emote(packet)
        if packet_type == PacketType.CHANNEL_ADD:
            return await self._handle_channel_add(packet)
        if packet_type == PacketType.CHANNEL_REMOVE:
            return await self._handle_channel_remove(packet)
        if packet_type == PacketType.CHANNEL_ADMIN:
            return await self._handle_channel_admin(packet)
        if packet_type == PacketType.CHANNEL_FILTER:
            return await self._handle_channel_filter(packet)
        if packet_type == PacketType.CHANNEL_WHO:
            return await self._handle_channel_who(packet)
        if packet_type == PacketType.CHANNEL_LISTEN:
            return await self._handle_channel_listen(packet)
        if packet_type == PacketType.CHANLIST_REPLY:
            return await self._handle_chanlist_reply(packet)

        return None

    async def _handle_channel_message(self, packet: I3Packet) -> I3Packet | None:
        """Handle a channel message packet.

        Args:
            packet: Channel message packet

        Returns:
            None (messages are broadcast, no direct response)
        """
        # Extract channel message fields
        # Format: [type, ttl, orig_mud, orig_user, 0, 0, channel, visname, message]
        data = packet.to_lpc_array()
        if len(data) < 9:
            self.logger.warning("Invalid channel-m packet", data_len=len(data))
            return None

        channel_name = str(data[6]).lower() if data[6] else ""
        visname = str(data[7]) if data[7] else packet.originator_user
        message = str(data[8]) if data[8] else ""

        self.logger.info(
            "Channel message",
            channel=channel_name,
            from_mud=packet.originator_mud,
            from_user=packet.originator_user,
            message_len=len(message),
        )

        # Check if channel exists
        channel_info = await self.state_manager.get_channel(channel_name)
        if not channel_info:
            self.logger.warning("Message to unknown channel", channel=channel_name)
            return None

        # Apply filters
        if not await self._check_filters(channel_name, packet.originator_mud, message):
            self.logger.info("Message filtered", channel=channel_name)
            return None

        # Store in history
        if channel_name not in self.channel_history:
            self.channel_history[channel_name] = ChannelHistory()

        self.channel_history[channel_name].add_message(
            {
                "type": "message",
                "mud": packet.originator_mud,
                "user": packet.originator_user,
                "visname": visname,
                "message": message,
                "timestamp": datetime.now(),
            }
        )

        # Broadcast to local subscribers
        await self._broadcast_to_local_subscribers(channel_name, packet)

        return None

    async def _handle_channel_emote(self, packet: I3Packet) -> I3Packet | None:
        """Handle a channel emote packet.

        Args:
            packet: Channel emote packet

        Returns:
            None
        """
        # Format: [type, ttl, orig_mud, orig_user, 0, 0, channel, visname, message]
        data = packet.to_lpc_array()
        if len(data) < 9:
            return None

        channel_name = str(data[6]).lower() if data[6] else ""
        visname = str(data[7]) if data[7] else packet.originator_user
        message = str(data[8]) if data[8] else ""

        self.logger.info(
            "Channel emote",
            channel=channel_name,
            from_mud=packet.originator_mud,
            from_user=packet.originator_user,
        )

        # Store in history
        if channel_name not in self.channel_history:
            self.channel_history[channel_name] = ChannelHistory()

        self.channel_history[channel_name].add_message(
            {
                "type": "emote",
                "mud": packet.originator_mud,
                "user": packet.originator_user,
                "visname": visname,
                "message": message,
                "timestamp": datetime.now(),
            }
        )

        # Broadcast to local subscribers
        await self._broadcast_to_local_subscribers(channel_name, packet)

        return None

    async def _handle_channel_targeted_emote(self, packet: I3Packet) -> I3Packet | None:
        """Handle a targeted channel emote packet.

        Args:
            packet: Channel targeted emote packet

        Returns:
            None
        """
        # Format: [type, ttl, orig_mud, orig_user, 0, 0, channel, targetmud, targetuser, visname_orig, visname_target, message]
        data = packet.to_lpc_array()
        if len(data) < 12:
            return None

        channel_name = str(data[6]).lower() if data[6] else ""
        target_mud = str(data[7]) if data[7] else ""
        target_user = str(data[8]) if data[8] else ""
        visname_orig = str(data[9]) if data[9] else packet.originator_user
        visname_target = str(data[10]) if data[10] else target_user
        message = str(data[11]) if data[11] else ""

        self.logger.info(
            "Channel targeted emote",
            channel=channel_name,
            from_mud=packet.originator_mud,
            from_user=packet.originator_user,
            target=f"{target_user}@{target_mud}",
        )

        # Store in history
        if channel_name not in self.channel_history:
            self.channel_history[channel_name] = ChannelHistory()

        self.channel_history[channel_name].add_message(
            {
                "type": "targeted_emote",
                "mud": packet.originator_mud,
                "user": packet.originator_user,
                "target_mud": target_mud,
                "target_user": target_user,
                "visname_orig": visname_orig,
                "visname_target": visname_target,
                "message": message,
                "timestamp": datetime.now(),
            }
        )

        # Broadcast to local subscribers
        await self._broadcast_to_local_subscribers(channel_name, packet)

        return None

    async def _handle_channel_add(self, packet: I3Packet) -> I3Packet | None:
        """Handle channel subscription request.

        Args:
            packet: Channel add packet

        Returns:
            None
        """
        # Format: [type, ttl, orig_mud, orig_user, 0, 0, channel]
        data = packet.to_lpc_array()
        if len(data) < 7:
            return None

        channel_name = str(data[6]).lower() if data[6] else ""

        self.logger.info(
            "Channel add request",
            channel=channel_name,
            mud=packet.originator_mud,
            user=packet.originator_user,
        )

        # Add to subscriptions
        if channel_name not in self.subscriptions:
            self.subscriptions[channel_name] = set()

        sub_key = (packet.originator_mud, packet.originator_user)
        self.subscriptions[channel_name].add(sub_key)

        # Track user subscriptions
        if sub_key not in self.user_channels:
            self.user_channels[sub_key] = set()
        self.user_channels[sub_key].add(channel_name)

        return None

    async def _handle_channel_remove(self, packet: I3Packet) -> I3Packet | None:
        """Handle channel unsubscribe request.

        Args:
            packet: Channel remove packet

        Returns:
            None
        """
        # Format: [type, ttl, orig_mud, orig_user, 0, 0, channel]
        data = packet.to_lpc_array()
        if len(data) < 7:
            return None

        channel_name = str(data[6]).lower() if data[6] else ""

        self.logger.info(
            "Channel remove request",
            channel=channel_name,
            mud=packet.originator_mud,
            user=packet.originator_user,
        )

        # Remove from subscriptions
        if channel_name in self.subscriptions:
            sub_key = (packet.originator_mud, packet.originator_user)
            self.subscriptions[channel_name].discard(sub_key)

            # Update user subscriptions
            if sub_key in self.user_channels:
                self.user_channels[sub_key].discard(channel_name)
                if not self.user_channels[sub_key]:
                    del self.user_channels[sub_key]

        return None

    async def _handle_channel_admin(self, packet: I3Packet) -> I3Packet | None:
        """Handle channel admin operations.

        Args:
            packet: Channel admin packet

        Returns:
            None or error packet
        """
        # Admin operations require special permissions
        # For now, just log the request
        self.logger.info(
            "Channel admin request",
            from_mud=packet.originator_mud,
            from_user=packet.originator_user,
        )

        return None

    async def _handle_channel_filter(self, packet: I3Packet) -> I3Packet | None:
        """Handle channel filter configuration.

        Args:
            packet: Channel filter packet

        Returns:
            None
        """
        self.logger.info(
            "Channel filter request",
            from_mud=packet.originator_mud,
            from_user=packet.originator_user,
        )

        return None

    async def _handle_channel_who(self, packet: I3Packet) -> I3Packet | None:
        """Handle channel who request.

        Args:
            packet: Channel who packet

        Returns:
            Response packet with user list
        """
        # Format: [type, ttl, orig_mud, orig_user, 0, 0, channel]
        data = packet.to_lpc_array()
        if len(data) < 7:
            return None

        channel_name = str(data[6]).lower() if data[6] else ""

        self.logger.info(
            "Channel who request", channel=channel_name, from_mud=packet.originator_mud
        )

        # Get subscribers for this channel
        subscribers = self.subscriptions.get(channel_name, set())

        # Build user list
        user_list = []
        for mud_name, user_name in subscribers:
            user_list.append({"mud": mud_name, "user": user_name})

        # TODO: Create and return channel-who-reply packet

        return None

    async def _handle_channel_listen(self, packet: I3Packet) -> I3Packet | None:
        """Handle channel listen request (bulk subscription).

        Args:
            packet: Channel listen packet

        Returns:
            None
        """
        self.logger.info("Channel listen request", from_mud=packet.originator_mud)

        # This is typically used by routers to subscribe to all channels
        # For a gateway, we might not need to handle this

        return None

    async def _handle_chanlist_reply(self, packet: I3Packet) -> I3Packet | None:
        """Handle channel list reply from router.

        Args:
            packet: Channel list reply packet

        Returns:
            None
        """
        # Format: [type, ttl, orig_mud, 0, target_mud, 0, chanlist_id, chanlist]
        data = packet.to_lpc_array()
        if len(data) < 8:
            return None

        chanlist_id = int(data[6]) if data[6] else 0
        chanlist = data[7] if isinstance(data[7], dict) else {}

        self.logger.info(
            "Received channel list", chanlist_id=chanlist_id, channel_count=len(chanlist)
        )

        # Update state manager with new channel list
        await self.state_manager.update_chanlist(chanlist, chanlist_id)

        # Initialize history for new channels
        for channel_name in chanlist:
            if channel_name not in self.channel_history:
                self.channel_history[channel_name] = ChannelHistory()

        return None

    async def validate_packet(self, packet: I3Packet) -> bool:
        """Validate a channel packet.

        Args:
            packet: The packet to validate

        Returns:
            True if packet is valid
        """
        if packet.packet_type not in self.supported_packets:
            return False

        # Most channel packets require originator mud
        if not packet.originator_mud:
            self.logger.warning("Channel packet missing originator mud")
            return False

        return True

    async def _check_filters(self, channel_name: str, mud_name: str, message: str) -> bool:
        """Check if a message passes channel filters.

        Args:
            channel_name: Channel name
            mud_name: Originating MUD
            message: Message content

        Returns:
            True if message passes filters
        """
        # TODO: Implement filter logic
        # For now, allow all messages
        return True

    async def _broadcast_to_local_subscribers(self, channel_name: str, packet: I3Packet):
        """Broadcast a channel packet to local subscribers.

        Args:
            channel_name: Channel name
            packet: Packet to broadcast
        """
        # In a real implementation, this would forward to the MUD server
        # For now, just log the broadcast
        local_subs = 0
        for mud_name, user_name in self.subscriptions.get(channel_name, set()):
            if mud_name == self.gateway.settings.mud.name if self.gateway else "":
                local_subs += 1

        if local_subs > 0:
            self.logger.debug(
                "Broadcasting to local subscribers",
                channel=channel_name,
                subscriber_count=local_subs,
            )

    async def send_channel_message(
        self, channel: str, user: str, message: str, visname: str | None = None
    ) -> bool:
        """Send a message to a channel.

        Args:
            channel: Channel name
            user: Local user sending the message
            message: Message content
            visname: Visual name (optional)

        Returns:
            True if message was sent
        """
        if not self.gateway:
            return False

        # Create channel-m packet
        from ..models.packet import ChannelMessagePacket

        packet = ChannelMessagePacket(
            ttl=200,
            originator_mud=self.gateway.settings.mud.name,
            originator_user=user,
            target_mud="0",  # Broadcast
            target_user="",
            channel=channel,
            visname=visname or user,
            message=message,
        )

        return await self.gateway.send_packet(packet)

    def get_channel_history(self, channel: str, count: int = 20) -> list[dict[str, Any]]:
        """Get recent channel history.

        Args:
            channel: Channel name
            count: Number of messages to retrieve

        Returns:
            List of recent messages
        """
        if channel not in self.channel_history:
            return []

        return self.channel_history[channel].get_recent(count)

    def get_user_channels(self, mud: str, user: str) -> set[str]:
        """Get channels a user is subscribed to.

        Args:
            mud: MUD name
            user: User name

        Returns:
            Set of channel names
        """
        return self.user_channels.get((mud, user), set())

    def get_channel_subscribers(self, channel: str) -> set[tuple[str, str]]:
        """Get subscribers for a channel.

        Args:
            channel: Channel name

        Returns:
            Set of (mud, user) tuples
        """
        return self.subscriptions.get(channel, set())
