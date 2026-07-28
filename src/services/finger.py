"""Finger service for user information queries.

This service handles finger-req and finger-reply packets to provide
detailed information about specific users.
"""

from datetime import datetime, datetime as DateTimeType
from typing import Any

import structlog

from ..models.packet import I3Packet, PacketType
from .base import BaseService


class FingerService(BaseService):
    """Service for handling finger requests."""

    service_name = "finger"
    supported_packets = [PacketType.FINGER_REQ, PacketType.FINGER_REPLY]
    requires_auth = False

    def __init__(self, state_manager, gateway=None):
        """Initialize finger service.

        Args:
            state_manager: State manager instance
            gateway: Reference to the gateway for sending packets
        """
        super().__init__(state_manager)
        self.gateway = gateway
        self.logger = structlog.get_logger()

        # Cache for finger results
        self.finger_cache: dict[str, tuple[dict, float]] = {}
        self.cache_ttl = 60.0  # 60 seconds cache

    async def initialize(self) -> None:
        """Initialize the finger service."""
        await super().initialize()
        self.logger.info("Finger service initialized")

    async def handle_packet(self, packet: I3Packet) -> I3Packet | None:
        """Handle incoming finger packet.

        Args:
            packet: The incoming packet

        Returns:
            Optional response packet
        """
        if packet.packet_type == PacketType.FINGER_REQ:
            return await self._handle_finger_request(packet)
        if packet.packet_type == PacketType.FINGER_REPLY:
            return await self._handle_finger_reply(packet)

        return None

    async def _handle_finger_request(self, packet: I3Packet) -> I3Packet | None:
        """Handle a finger request packet.

        Args:
            packet: The finger request packet

        Returns:
            Finger reply packet
        """
        # Extract user to finger from packet
        # Format: [type, ttl, orig_mud, orig_user, target_mud, 0, username]
        data = packet.to_lpc_array()
        if len(data) < 7:
            self.logger.warning("Invalid finger-req packet", data_len=len(data))
            return None

        original_username = str(data[6]) if data[6] else ""
        username = original_username.lower()

        self.logger.info(
            "Received finger request",
            from_mud=packet.originator_mud,
            from_user=packet.originator_user,
            target_user=username,
        )

        # Check cache first
        cache_key = f"{username}@{self.gateway.settings.mud.name if self.gateway else 'local'}"
        if cache_key in self.finger_cache:
            cached_data, cache_time = self.finger_cache[cache_key]
            if (datetime.now().timestamp() - cache_time) < self.cache_ttl:
                self.logger.debug("Returning cached finger data", user=username)
                return self._create_finger_reply(packet, original_username, cached_data)

        # Get user information from state manager
        user_info = await self._get_user_info(username)

        # Cache the results
        if user_info:
            self.finger_cache[cache_key] = (user_info, datetime.now().timestamp())

        # Create and return finger reply
        return self._create_finger_reply(packet, original_username, user_info)

    async def _handle_finger_reply(self, packet: I3Packet) -> I3Packet | None:
        """Handle a finger reply packet.

        Args:
            packet: The finger reply packet

        Returns:
            None (replies are informational)
        """
        # Extract finger data from packet
        # Format: [type, ttl, orig_mud, 0, target_mud, target_user, ...finger_data]
        data = packet.to_lpc_array()

        self.logger.info(
            "Received finger reply", from_mud=packet.originator_mud, for_user=packet.target_user
        )

        # Store the finger data for retrieval by the MUD
        # In a real implementation, this would be forwarded to the MUD

        return None

    async def _get_user_info(self, username: str) -> dict[str, Any] | None:
        """Get detailed information about a user.

        Args:
            username: Username to look up

        Returns:
            User information dictionary or None if not found
        """
        local_mud = self.gateway.settings.mud.name if self.gateway else "local"
        session = await self.state_manager.find_user_session(local_mud, username)

        if not session or not session.is_online:
            # User not found or offline
            return None

        # Calculate idle time
        idle_time = int((datetime.now() - session.last_activity).total_seconds())
        hide_ip = self.gateway is not None
        if self.gateway:
            service_settings = getattr(self.gateway.settings, "services", None)
            finger_settings = getattr(service_settings, "finger", None)
            if isinstance(finger_settings, dict):
                hide_ip = finger_settings.get("hide_ip", True)

        # Build user info
        title = getattr(session, "title", "")
        real_name = getattr(session, "real_name", "")
        email = getattr(session, "email", "")
        ip_address = getattr(session, "ip_address", "")
        login_time = getattr(session, "login_time", None)
        user_info = {
            "name": session.user_name,
            "title": (
                title
                if isinstance(title, str) and title
                else f"{session.user_name} the Adventurer"
            ),
            "real_name": real_name if isinstance(real_name, str) else "",
            "email": email if isinstance(email, str) else "",
            "login_time": (
                login_time.isoformat()
                if isinstance(login_time, DateTimeType)
                else ""
            ),
            "idle_time": idle_time,
            "ip_address": (
                ""
                if hide_ip or not isinstance(ip_address, str)
                else ip_address
            ),
            "level": session.level,
            "extra": {},
        }

        # Add optional fields
        for field_name in ("race", "guild", "location", "website"):
            value = getattr(session, field_name, "")
            if isinstance(value, str) and value:
                user_info["extra"][field_name] = value

        return user_info

    def _create_finger_reply(
        self, request: I3Packet, username: str, user_info: dict[str, Any] | None
    ) -> I3Packet:
        """Create a finger reply packet.

        Args:
            request: The original finger request
            username: Username that was queried
            user_info: User information or None if not found

        Returns:
            Finger reply packet
        """
        from ..models.packet import FingerPacket

        return FingerPacket(
            packet_type=PacketType.FINGER_REPLY,
            ttl=200,
            originator_mud=self.gateway.settings.mud.name if self.gateway else "",
            originator_user="",
            target_mud=request.originator_mud,
            target_user=request.originator_user,
            username=username,
            user_info=user_info or {},
        )

    async def validate_packet(self, packet: I3Packet) -> bool:
        """Validate a finger packet.

        Args:
            packet: The packet to validate

        Returns:
            True if packet is valid
        """
        if packet.packet_type not in self.supported_packets:
            return False

        # finger-req requires a username in field 6
        # finger-reply has specific fields

        return True

    async def send_finger_request(self, target_mud: str, username: str) -> bool:
        """Send a finger request to another MUD.

        Args:
            target_mud: Target MUD name
            username: Username to finger

        Returns:
            True if request was sent successfully
        """
        if not self.gateway:
            self.logger.error("No gateway available for sending finger request")
            return False

        from ..models.packet import FingerPacket

        finger_req = FingerPacket(
            packet_type=PacketType.FINGER_REQ,
            ttl=200,
            originator_mud=self.gateway.settings.mud.name,
            originator_user="",
            target_mud=target_mud,
            target_user="",
            username=username,
        )

        success = await self.gateway.send_packet(finger_req)

        if success:
            self.logger.info("Sent finger request", target_mud=target_mud, username=username)

        return success

    def clear_cache(self):
        """Clear the finger cache."""
        self.finger_cache.clear()
        self.logger.debug("Finger cache cleared")
