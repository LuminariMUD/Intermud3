"""Router service for packet routing and forwarding.

This service handles packet routing logic, TTL management,
and forwarding packets to the correct destination.
"""

import structlog

from ..models.packet import I3Packet
from .base import BaseService


class RouterService(BaseService):
    """Service for routing I3 packets."""

    service_name = "router"
    supported_packets = []  # Router handles all packet types for routing
    requires_auth = False

    def __init__(self, state_manager, gateway=None):
        """Initialize router service.

        Args:
            state_manager: State manager instance
            gateway: Reference to the gateway for sending packets
        """
        super().__init__(state_manager)
        self.gateway = gateway
        self.logger = structlog.get_logger()

        # Statistics
        self.packets_routed_local = 0
        self.packets_routed_remote = 0
        self.packets_broadcast = 0
        self.packets_dropped = 0

    async def initialize(self) -> None:
        """Initialize the router service."""
        await super().initialize()
        self.logger.info("Router service initialized")

    async def route_packet(self, packet: I3Packet) -> bool:
        """Route a packet to its destination.

        Args:
            packet: The packet to route

        Returns:
            True if packet was routed successfully
        """
        # Check TTL
        if packet.ttl <= 0:
            self.logger.warning(
                "Dropping packet with expired TTL",
                packet_type=packet.packet_type.value,
                ttl=packet.ttl,
            )
            self.packets_dropped += 1
            return False

        # Decrement TTL for forwarding
        packet.ttl -= 1

        # Check for gateway
        if not self.gateway:
            self.logger.error("No gateway available for routing")
            self.packets_dropped += 1
            return False

        # Determine routing destination
        if packet.target_mud == self.gateway.settings.mud.name:
            # Local delivery
            return await self._route_local(packet)
        if packet.target_mud == "0" or packet.target_mud == 0:
            # Broadcast packet
            return await self._route_broadcast(packet)
        # Remote delivery
        return await self._route_remote(packet)

    async def _route_local(self, packet: I3Packet) -> bool:
        """Route packet to local service.

        Args:
            packet: The packet to route locally

        Returns:
            True if routed successfully
        """
        self.logger.debug(
            "Routing packet locally",
            packet_type=packet.packet_type.value,
            from_mud=packet.originator_mud,
            to_user=packet.target_user,
        )

        # Queue packet for local service processing
        if self.gateway and self.gateway.service_manager:
            await self.gateway.service_manager.queue_packet(packet)
            self.packets_routed_local += 1
            return True

        self.logger.error("No service manager available for local routing")
        self.packets_dropped += 1
        return False

    async def _route_remote(self, packet: I3Packet) -> bool:
        """Route packet to remote MUD via router.

        Args:
            packet: The packet to route remotely

        Returns:
            True if routed successfully
        """
        # Check if target MUD exists in mudlist
        try:
            mud_info = await self.state_manager.get_mud(packet.target_mud)
        except Exception as e:
            self.logger.error("Error getting MUD info", target_mud=packet.target_mud, error=str(e))
            self.packets_dropped += 1
            return False

        if not mud_info:
            self.logger.warning("Target MUD not found in mudlist", target_mud=packet.target_mud)
            # Send error packet back to originator
            await self._send_error_reply(
                packet, "unk-dst", f"Unknown destination MUD: {packet.target_mud}"
            )
            self.packets_dropped += 1
            return False

        # Check if MUD is online
        if mud_info.status != "online":
            self.logger.warning(
                "Target MUD is offline", target_mud=packet.target_mud, status=mud_info.status
            )
            await self._send_error_reply(
                packet, "not-imp", f"MUD {packet.target_mud} is currently offline"
            )
            self.packets_dropped += 1
            return False

        self.logger.debug(
            "Forwarding packet to remote MUD",
            packet_type=packet.packet_type.value,
            from_mud=packet.originator_mud,
            to_mud=packet.target_mud,
        )

        # Forward packet to router
        if self.gateway:
            success = await self.gateway.send_packet(packet)
            if success:
                self.packets_routed_remote += 1
            else:
                self.packets_dropped += 1
            return success

        self.packets_dropped += 1
        return False

    async def _route_broadcast(self, packet: I3Packet) -> bool:
        """Route broadcast packet.

        Args:
            packet: The broadcast packet

        Returns:
            True if broadcast successfully
        """
        self.logger.debug(
            "Broadcasting packet",
            packet_type=packet.packet_type.value,
            from_mud=packet.originator_mud,
        )

        # Broadcast packets are typically channel messages
        # Forward to router for distribution
        if self.gateway:
            success = await self.gateway.send_packet(packet)
            if success:
                self.packets_broadcast += 1
            else:
                self.packets_dropped += 1
            return success

        self.packets_dropped += 1
        return False

    async def _send_error_reply(
        self, original_packet: I3Packet, error_code: str, error_message: str
    ):
        """Send an error packet in response to a failed routing.

        Args:
            original_packet: The packet that failed to route
            error_code: Error code (e.g., "unk-dst", "not-imp")
            error_message: Human-readable error message
        """
        if not self.gateway:
            self.logger.warning("Cannot send error reply without gateway")
            return

        from ..models.packet import ErrorPacket

        error_packet = ErrorPacket(
            ttl=200,
            originator_mud=self.gateway.settings.mud.name,
            originator_user="",
            target_mud=original_packet.originator_mud,
            target_user=original_packet.originator_user,
            error_code=error_code,
            error_message=error_message,
            bad_packet=original_packet.to_lpc_array(),
        )

        await self.gateway.send_packet(error_packet)

    async def handle_packet(self, packet: I3Packet) -> I3Packet | None:
        """Handle incoming packet for routing.

        Args:
            packet: The incoming packet

        Returns:
            None (routing doesn't generate direct responses)
        """
        await self.route_packet(packet)
        return None

    async def validate_packet(self, packet: I3Packet) -> bool:
        """Validate packet for routing.

        Args:
            packet: The packet to validate

        Returns:
            True (router validates all packets)
        """
        return True

    def get_stats(self) -> dict[str, int]:
        """Get routing statistics.

        Returns:
            Dictionary of routing statistics
        """
        return {
            "packets_routed_local": self.packets_routed_local,
            "packets_routed_remote": self.packets_routed_remote,
            "packets_broadcast": self.packets_broadcast,
            "packets_dropped": self.packets_dropped,
            "total_routed": (
                self.packets_routed_local + self.packets_routed_remote + self.packets_broadcast
            ),
        }
