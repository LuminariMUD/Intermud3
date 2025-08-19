"""Who service for listing online users.

This service handles who-req and who-reply packets to provide
information about users currently online on a MUD.
"""

from datetime import datetime
from typing import Any

import structlog

from ..models.packet import I3Packet, PacketType, WhoPacket
from .base import BaseService


class WhoService(BaseService):
    """Service for handling who requests."""

    service_name = "who"
    supported_packets = [PacketType.WHO_REQ, PacketType.WHO_REPLY]
    requires_auth = False

    def __init__(self, state_manager, gateway=None):
        """Initialize who service.

        Args:
            state_manager: State manager instance
            gateway: Reference to the gateway for sending packets
        """
        super().__init__(state_manager)
        self.gateway = gateway
        self.logger = structlog.get_logger()

        # Cache for who results
        self.who_cache: dict[str, tuple[list[dict], float]] = {}
        self.cache_ttl = 30.0  # 30 seconds cache

    async def initialize(self) -> None:
        """Initialize the who service."""
        await super().initialize()
        self.logger.info("Who service initialized")

    async def handle_packet(self, packet: I3Packet) -> I3Packet | None:
        """Handle incoming who packet.

        Args:
            packet: The incoming packet

        Returns:
            Optional response packet
        """
        if packet.packet_type == PacketType.WHO_REQ:
            return await self._handle_who_request(packet)
        if packet.packet_type == PacketType.WHO_REPLY:
            return await self._handle_who_reply(packet)

        return None

    async def _handle_who_request(self, packet: WhoPacket) -> I3Packet | None:
        """Handle a who request packet.

        Args:
            packet: The who request packet

        Returns:
            Who reply packet
        """
        self.logger.info(
            "Received who request",
            from_mud=packet.originator_mud,
            from_user=packet.originator_user,
            filters=packet.filter_criteria,
        )

        # Check cache first
        cache_key = f"{self.gateway.settings.mud.name if self.gateway else 'local'}"
        if cache_key in self.who_cache:
            cached_data, cache_time = self.who_cache[cache_key]
            if (datetime.now().timestamp() - cache_time) < self.cache_ttl:
                self.logger.debug("Returning cached who data")
                return self._create_who_reply(packet, cached_data)

        # Get online users from state manager
        online_users = await self._get_online_users(packet.filter_criteria)

        # Cache the results
        self.who_cache[cache_key] = (online_users, datetime.now().timestamp())

        # Create and return who reply
        return self._create_who_reply(packet, online_users)

    async def _handle_who_reply(self, packet: WhoPacket) -> I3Packet | None:
        """Handle a who reply packet.

        Args:
            packet: The who reply packet

        Returns:
            None (replies are informational)
        """
        self.logger.info(
            "Received who reply",
            from_mud=packet.originator_mud,
            user_count=len(packet.who_data) if packet.who_data else 0,
        )

        # Store the who data for retrieval by the MUD
        # In a real implementation, this would be forwarded to the MUD

        return None

    async def _get_online_users(
        self, filter_criteria: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Get list of online users matching filter criteria.

        Args:
            filter_criteria: Optional filter criteria

        Returns:
            List of user information dictionaries
        """
        online_users = []

        # Get all sessions from state manager
        sessions = self.state_manager.sessions

        for session_id, session in sessions.items():
            if not session.is_online:
                continue

            # Apply filters if provided
            if filter_criteria:
                # Check level filter
                if "level_min" in filter_criteria:
                    if session.level < filter_criteria["level_min"]:
                        continue
                if "level_max" in filter_criteria:
                    if session.level > filter_criteria["level_max"]:
                        continue

                # Check race filter
                if "race" in filter_criteria:
                    if session.race != filter_criteria["race"]:
                        continue

                # Check guild filter
                if "guild" in filter_criteria:
                    if session.guild != filter_criteria["guild"]:
                        continue

            # Calculate idle time
            idle_time = int((datetime.now() - session.last_activity).total_seconds())

            # Build user info
            user_info = {
                "name": session.user_name,
                "idle": idle_time,
                "level": session.level,
                "extra": session.title or "",
            }

            # Add optional fields if available
            if hasattr(session, "race") and session.race:
                user_info["race"] = session.race
            if hasattr(session, "guild") and session.guild:
                user_info["guild"] = session.guild

            online_users.append(user_info)

        # Sort by name
        online_users.sort(key=lambda u: u["name"].lower())

        return online_users

    def _create_who_reply(self, request: WhoPacket, users: list[dict[str, Any]]) -> WhoPacket:
        """Create a who reply packet.

        Args:
            request: The original who request
            users: List of user information

        Returns:
            Who reply packet
        """
        return WhoPacket(
            packet_type=PacketType.WHO_REPLY,
            ttl=200,
            originator_mud=self.gateway.settings.mud.name if self.gateway else "",
            originator_user="",
            target_mud=request.originator_mud,
            target_user=request.originator_user,
            who_data=users,
        )

    async def validate_packet(self, packet: I3Packet) -> bool:
        """Validate a who packet.

        Args:
            packet: The packet to validate

        Returns:
            True if packet is valid
        """
        if packet.packet_type not in self.supported_packets:
            return False

        if not isinstance(packet, WhoPacket):
            return False

        # who-req doesn't require any specific fields
        # who-reply requires who_data but that's checked in the packet itself

        return True

    async def send_who_request(
        self, target_mud: str, filter_criteria: dict[str, Any] | None = None
    ) -> bool:
        """Send a who request to another MUD.

        Args:
            target_mud: Target MUD name
            filter_criteria: Optional filter criteria

        Returns:
            True if request was sent successfully
        """
        if not self.gateway:
            self.logger.error("No gateway available for sending who request")
            return False

        who_req = WhoPacket(
            packet_type=PacketType.WHO_REQ,
            ttl=200,
            originator_mud=self.gateway.settings.mud.name,
            originator_user="",
            target_mud=target_mud,
            target_user="",
            filter_criteria=filter_criteria,
        )

        success = await self.gateway.send_packet(who_req)

        if success:
            self.logger.info("Sent who request", target_mud=target_mud, filters=filter_criteria)

        return success

    def clear_cache(self):
        """Clear the who cache."""
        self.who_cache.clear()
        self.logger.debug("Who cache cleared")
