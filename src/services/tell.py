"""Tell service for private messaging.

This service handles tell and emoteto packets for private
communication between users on different MUDs.
"""

import asyncio

import structlog

from ..models.packet import (
    EmotetoPacket,
    ErrorPacket,
    I3Packet,
    PacketType,
    TellPacket,
)
from .base import BaseService


class TellService(BaseService):
    """Service for handling private messages."""

    service_name = "tell"
    supported_packets = [PacketType.TELL, PacketType.EMOTETO]
    requires_auth = False

    def __init__(self, state_manager, gateway=None):
        """Initialize tell service.

        Args:
            state_manager: State manager instance
            gateway: Reference to the gateway for sending packets
        """
        super().__init__(state_manager)
        self.gateway = gateway
        self.logger = structlog.get_logger()

        # Cache for recent tells (for reply functionality)
        self.recent_tells: dict[str, str] = {}  # user -> last_sender_mud:user
        self.tell_history: dict[str, list] = {}  # user -> list of recent messages

    async def initialize(self) -> None:
        """Initialize the tell service."""
        await super().initialize()
        self.logger.info("Tell service initialized")

    async def handle_packet(self, packet: I3Packet) -> I3Packet | None:
        """Handle incoming tell or emoteto packet.

        Args:
            packet: The incoming packet

        Returns:
            Optional error packet if delivery failed
        """
        if packet.packet_type == PacketType.TELL:
            return await self._handle_tell(packet)
        if packet.packet_type == PacketType.EMOTETO:
            return await self._handle_emoteto(packet)

        return None

    async def _handle_tell(self, packet: TellPacket) -> I3Packet | None:
        """Handle a tell packet.

        Args:
            packet: The tell packet

        Returns:
            Optional error packet if delivery failed
        """
        self.logger.info(
            "Received tell",
            from_mud=packet.originator_mud,
            from_user=packet.originator_user,
            to_user=packet.target_user,
            message_len=len(packet.message),
        )

        # Check if target user exists and is online
        user_session = await self.state_manager.get_session(packet.target_user)

        if not user_session or not user_session.is_online:
            # User not online, send error reply
            self.logger.warning("Tell target user not online", target_user=packet.target_user)

            return ErrorPacket(
                ttl=200,
                originator_mud=self.gateway.settings.mud.name if self.gateway else "",
                originator_user="",
                target_mud=packet.originator_mud,
                target_user=packet.originator_user,
                error_code="unk-user",
                error_message=f"User {packet.target_user} is not online",
                bad_packet=packet.to_lpc_array(),  # Note: ErrorPacket uses 'bad_packet' not 'error_packet'
            )

        # Store in recent tells for reply functionality
        self.recent_tells[packet.target_user] = f"{packet.originator_mud}:{packet.originator_user}"

        # Add to history
        # IMPORTANT: Both TellPacket and EmotetoPacket HAVE a visname attribute
        # This is REQUIRED by the I3 protocol specification
        # visname is the visual/display name of the sender (can differ from username)
        if packet.target_user not in self.tell_history:
            self.tell_history[packet.target_user] = []

        self.tell_history[packet.target_user].append(
            {
                "from_mud": packet.originator_mud,
                "from_user": packet.originator_user,
                "visname": packet.visname,  # Direct access - TellPacket ALWAYS has visname per I3 spec
                "message": packet.message,
                "timestamp": asyncio.get_event_loop().time(),
            }
        )

        # Keep only last 20 messages in history
        if len(self.tell_history[packet.target_user]) > 20:
            self.tell_history[packet.target_user] = self.tell_history[packet.target_user][-20:]

        # Deliver the tell to the local MUD
        # In a real implementation, this would forward to the MUD server
        # For now, we just log successful delivery
        self.logger.info(
            "Tell delivered",
            to_user=packet.target_user,
            from_user=f"{packet.originator_user}@{packet.originator_mud}",
        )

        # Update metrics
        self.metrics.packets_handled += 1

        return None  # No error response needed

    async def _handle_emoteto(self, packet: EmotetoPacket) -> I3Packet | None:
        """Handle an emoteto packet.

        Args:
            packet: The emoteto packet

        Returns:
            Optional error packet if delivery failed
        """
        self.logger.info(
            "Received emoteto",
            from_mud=packet.originator_mud,
            from_user=packet.originator_user,
            to_user=packet.target_user,
            message_len=len(packet.message),
        )

        # Check if target user exists and is online
        user_session = await self.state_manager.get_session(packet.target_user)

        if not user_session or not user_session.is_online:
            # User not online, send error reply
            self.logger.warning("Emoteto target user not online", target_user=packet.target_user)

            return ErrorPacket(
                ttl=200,
                originator_mud=self.gateway.settings.mud.name if self.gateway else "",
                originator_user="",
                target_mud=packet.originator_mud,
                target_user=packet.originator_user,
                error_code="unk-user",
                error_message=f"User {packet.target_user} is not online",
                bad_packet=packet.to_lpc_array(),  # Note: ErrorPacket uses 'bad_packet' not 'error_packet'
            )

        # Store in recent tells for reply functionality
        self.recent_tells[packet.target_user] = f"{packet.originator_mud}:{packet.originator_user}"

        # Deliver the emoteto to the local MUD
        self.logger.info(
            "Emoteto delivered",
            to_user=packet.target_user,
            from_user=f"{packet.originator_user}@{packet.originator_mud}",
        )

        # Update metrics
        self.metrics.packets_handled += 1

        return None

    async def validate_packet(self, packet: I3Packet) -> bool:
        """Validate a tell/emoteto packet.

        Args:
            packet: The packet to validate

        Returns:
            True if packet is valid
        """
        if packet.packet_type not in self.supported_packets:
            return False

        # Check required fields
        if not packet.originator_user:
            self.logger.warning("Tell/emoteto missing originator user")
            return False

        if not packet.target_user:
            self.logger.warning("Tell/emoteto missing target user")
            return False

        if packet.packet_type == PacketType.TELL:
            if not isinstance(packet, TellPacket):
                return False
            if not packet.message:
                self.logger.warning("Tell has empty message")
                return False

        elif packet.packet_type == PacketType.EMOTETO:
            if not isinstance(packet, EmotetoPacket):
                return False
            if not packet.message:
                self.logger.warning("Emoteto has empty message")
                return False

        return True

    async def send_tell(
        self, from_user: str, to_user: str, to_mud: str, message: str, visname: str | None = None
    ) -> bool:
        """Send a tell to another user.

        Args:
            from_user: Local user sending the tell
            to_user: Remote user receiving the tell
            to_mud: Remote MUD name
            message: Message content
            visname: Visual name of sender (optional)

        Returns:
            True if tell was sent successfully
        """
        if not self.gateway:
            self.logger.error("No gateway available for sending tell")
            return False

        tell_packet = TellPacket(
            ttl=200,
            originator_mud=self.gateway.settings.mud.name,
            originator_user=from_user,
            target_mud=to_mud,
            target_user=to_user,
            visname=visname or from_user,
            message=message,
        )

        success = await self.gateway.send_packet(tell_packet)

        if success:
            self.logger.info("Sent tell", from_user=from_user, to_user=f"{to_user}@{to_mud}")

        return success

    async def send_emoteto(
        self, from_user: str, to_user: str, to_mud: str, message: str, visname: str | None = None
    ) -> bool:
        """Send an emoteto to another user.

        Args:
            from_user: Local user sending the emoteto
            to_user: Remote user receiving the emoteto
            to_mud: Remote MUD name
            message: Emote message
            visname: Visual name of sender (optional)

        Returns:
            True if emoteto was sent successfully
        """
        if not self.gateway:
            self.logger.error("No gateway available for sending emoteto")
            return False

        emoteto_packet = EmotetoPacket(
            ttl=200,
            originator_mud=self.gateway.settings.mud.name,
            originator_user=from_user,
            target_mud=to_mud,
            target_user=to_user,
            visname=visname or from_user,
            message=message,
        )

        success = await self.gateway.send_packet(emoteto_packet)

        if success:
            self.logger.info("Sent emoteto", from_user=from_user, to_user=f"{to_user}@{to_mud}")

        return success

    def get_last_tell_sender(self, user: str) -> str | None:
        """Get the last user who sent a tell to this user.

        Args:
            user: Local user

        Returns:
            "mud:user" string or None
        """
        return self.recent_tells.get(user)

    def get_tell_history(self, user: str) -> list:
        """Get tell history for a user.

        Args:
            user: Local user

        Returns:
            List of recent tell messages
        """
        return self.tell_history.get(user, [])
