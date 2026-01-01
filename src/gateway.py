"""Main I3 Gateway implementation."""

import asyncio
from pathlib import Path
from typing import Any

import structlog

from .api.event_bridge import event_bridge
from .api.server import APIServer
from .config.models import Settings
from .models.packet import I3Packet, PacketFactory, PacketType
from .network import ConnectionManager, ConnectionState, RouterInfo
from .services.base import ServiceManager
from .state.manager import StateManager


class I3Gateway:
    """Main I3 Gateway service."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the I3 Gateway."""
        self.settings = settings
        self.logger = structlog.get_logger()
        self.running = False
        self._shutdown_event = asyncio.Event()

        # Initialize components
        self.state_manager = StateManager(persistence_dir=Path("data"), cache_ttl=300.0)

        self.service_manager = ServiceManager(self.state_manager)

        # Import and register router service
        from .services.router import RouterService

        self.router_service = RouterService(self.state_manager, self)

        # Setup routers
        routers = []
        if settings.router.primary:
            routers.append(
                RouterInfo(
                    name=settings.router.primary.name,
                    address=settings.router.primary.host,
                    port=settings.router.primary.port,
                    priority=0,
                )
            )

        for i, fallback in enumerate(settings.router.fallback or []):
            routers.append(
                RouterInfo(
                    name=f"fallback-{i}",
                    address=fallback.host,
                    port=fallback.port,
                    priority=i + 1,
                )
            )

        self.connection_manager = ConnectionManager(
            routers=routers,
            on_message=self._handle_message,
            on_state_change=self._handle_state_change,
            keepalive_interval=60.0,
            connection_timeout=30.0,
        )

        # Packet processing
        self.packet_queue: asyncio.Queue = asyncio.Queue()
        self._processing_task: asyncio.Task | None = None

        # API Server
        self.api_server = APIServer(settings.api, self) if settings.api.enabled else None

    async def start(self) -> None:
        """Start the I3 Gateway service."""
        self.logger.info(
            "Starting I3 Gateway",
            mud_name=self.settings.mud.name,
            router=self.settings.router.primary.host,
        )

        self.running = True

        # Start components
        await self.state_manager.start()
        await self.service_manager.start()

        # Start packet processing
        self._processing_task = asyncio.create_task(self._process_packets())

        # Connect to router
        connected = await self.connection_manager.connect()
        if not connected:
            self.logger.error("Failed to connect to any I3 router")
            # Gateway will keep trying to reconnect automatically

        # Start API server if enabled
        if self.api_server:
            await self.api_server.start()
            self.logger.info(
                "API servers started",
                websocket_port=self.settings.api.port,
                tcp_port=self.settings.api.tcp.port if self.settings.api.tcp.enabled else None,
            )

        self.logger.info("I3 Gateway started successfully")

    async def shutdown(self) -> None:
        """Shutdown the I3 Gateway service."""
        self.logger.info("Shutting down I3 Gateway...")
        self.running = False

        # Stop packet processing
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        # Stop API server if running
        if self.api_server:
            await self.api_server.stop()

        # Disconnect from router
        await self.connection_manager.disconnect()

        # Stop components
        await self.service_manager.stop()
        await self.state_manager.stop()

        self._shutdown_event.set()
        self.logger.info("I3 Gateway shutdown complete")

    async def wait_for_shutdown(self) -> None:
        """Wait for the gateway to shutdown."""
        await self._shutdown_event.wait()

    def is_connected(self) -> bool:
        """Check if gateway is connected to I3 router.

        Returns:
            True if connected, False otherwise
        """
        return self.connection_manager.is_connected()

    async def reconnect(self) -> None:
        """Force reconnection to I3 router."""
        self.logger.info("Forcing reconnection to I3 router")
        if self.connection_manager.is_connected():
            await self.connection_manager.disconnect()
        await self.connection_manager.connect()

    async def send_packet(self, packet: I3Packet) -> bool:
        """Send a packet to the I3 network.

        Args:
            packet: Packet to send

        Returns:
            True if packet was sent successfully
        """
        if not self.connection_manager.is_connected():
            self.logger.warning("Not connected to router, cannot send packet")
            return False

        try:
            # Convert to LPC array for transmission
            lpc_array = packet.to_lpc_array()
            success = await self.connection_manager.send_message(lpc_array)

            if success:
                self.logger.debug("Sent packet", packet_type=packet.packet_type.value)
            else:
                self.logger.warning("Failed to send packet", packet_type=packet.packet_type.value)

            return success

        except Exception as e:
            self.logger.error("Error sending packet", error=str(e))
            return False

    async def _handle_message(self, message: Any):
        """Handle incoming message from router.

        Args:
            message: Raw message data (LPC array)
        """
        try:
            # Parse packet
            if not isinstance(message, list):
                self.logger.warning("Invalid message format", type=type(message).__name__)
                return

            packet = PacketFactory.create_packet(message)

            # Queue for processing
            await self.packet_queue.put(packet)

        except Exception as e:
            self.logger.error("Error handling message", error=str(e))

    async def _handle_state_change(self, state: ConnectionState):
        """Handle connection state change.

        Args:
            state: New connection state
        """
        self.logger.info("Connection state changed", state=state.value)

        if state == ConnectionState.CONNECTED:
            # Send startup packet
            await self._send_startup()
        elif state == ConnectionState.READY:
            # Notify event bridge of reconnection
            await event_bridge.notify_gateway_reconnect()
        elif state == ConnectionState.DISCONNECTED:
            # Clear router-specific state
            pass

    async def _send_startup(self):
        """Send startup packet to router."""
        from .models.packet import StartupPacket

        # Build services dictionary
        services = {}
        # Regular services
        for service_name in ["tell", "channel", "who", "finger", "locate"]:
            if getattr(self.settings.mud.services, service_name, False):
                services[service_name] = 1
        # OOB services
        for service_name in ["mail", "news", "file"]:
            if getattr(self.settings.mud.oob_services, service_name, False):
                services[service_name] = 1

        # Get current mudlist and chanlist IDs from state
        # Use 0 to request fresh full list on startup
        old_mudlist_id = 0  # Force fresh request
        old_chanlist_id = 0  # We'll track this later

        # Get current router name for target_mud field
        current_router = self.connection_manager.get_current_router()
        router_name = current_router.name if current_router else self.settings.router.primary.name

        # Create startup packet with correct field names
        startup = StartupPacket(
            ttl=200,
            originator_mud=self.settings.mud.name,
            originator_user="",
            target_mud=router_name,
            target_user="",
            password=getattr(self.settings.mud, "password", 0),
            old_mudlist_id=old_mudlist_id,
            old_chanlist_id=old_chanlist_id,
            player_port=self.settings.mud.port,
            imud_tcp_port=getattr(self.settings.mud, "tcp_port", 0),
            imud_udp_port=getattr(self.settings.mud, "udp_port", 0),
            mudlib=getattr(self.settings.mud, "mudlib", "LPMud"),
            base_mudlib=getattr(self.settings.mud, "base_mudlib", "LPMud"),
            driver=getattr(self.settings.mud, "driver", "FluffOS"),
            mud_type=getattr(self.settings.mud, "mud_type", "LP"),
            open_status=getattr(self.settings.mud, "open_status", "open"),
            admin_email=getattr(self.settings.mud, "admin_email", ""),
            services=services,
            other_data={},
        )

        # Send startup packet
        lpc_array = startup.to_lpc_array()
        self.logger.debug("Startup packet LPC array",
                          router_name=router_name,
                          packet_fields=len(lpc_array),
                          lpc_data=str(lpc_array))
        await self.send_packet(startup)
        self.logger.info("Sent startup packet", mud_name=self.settings.mud.name)

    async def _process_packets(self):
        """Process incoming packets from the queue."""
        while self.running:
            try:
                # Get packet with timeout
                packet = await asyncio.wait_for(self.packet_queue.get(), timeout=1.0)

                # Handle special router packets first
                if packet.packet_type == PacketType.MUDLIST:
                    await self._handle_mudlist(packet)
                elif packet.packet_type == PacketType.STARTUP_REPLY:
                    await self._handle_startup_reply(packet)
                elif packet.packet_type == PacketType.ERROR:
                    await self._handle_error(packet)
                # Route packet through router service
                # This will handle local vs remote routing
                elif self.router_service:
                    await self.router_service.route_packet(packet)
                    # Also send packet to event bridge for API event generation
                    await event_bridge.process_incoming_packet(packet)
                else:
                    # Fallback to direct service routing
                    await self.service_manager.queue_packet(packet)
                    # Also send packet to event bridge for API event generation
                    await event_bridge.process_incoming_packet(packet)

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error processing packet", error=str(e))

    async def _handle_mudlist(self, packet: Any):
        """Handle mudlist update from router.

        Note: The mudlist is sent by the I3 router after the initial connection
        is established. It may take a few seconds after gateway startup before
        the full mudlist is available. Clients should handle empty mudlist
        responses gracefully during this initial period.
        """
        from .models.packet import MudlistPacket

        if isinstance(packet, MudlistPacket):
            await self.state_manager.update_mudlist(packet.mudlist, packet.mudlist_id)
            self.logger.info("Updated mudlist", mudlist_id=packet.mudlist_id)

    async def _handle_startup_reply(self, packet: Any):
        """Handle startup reply from router."""
        self.logger.info("Received startup reply - connection established")
        await self.connection_manager._set_state(ConnectionState.READY)

    async def _handle_error(self, packet: Any):
        """Handle error packet from router."""
        from .models.packet import ErrorPacket

        if isinstance(packet, ErrorPacket):
            self.logger.error(
                "Router error", error_code=packet.error_code, error_message=packet.error_message
            )

    def get_stats(self) -> dict[str, Any]:
        """Get gateway statistics.

        Returns:
            Dictionary of statistics
        """
        stats = {
            "running": self.running,
            "connected": self.connection_manager.is_connected(),
            "connection": self.connection_manager.get_stats().__dict__,
            "services": self.service_manager.get_metrics(),
            "state": {
                "muds": len(self.state_manager.mudlist),
                "channels": len(self.state_manager.channels),
                "sessions": len(self.state_manager.sessions),
            },
        }

        current_router = self.connection_manager.get_current_router()
        if current_router:
            stats["router"] = {
                "name": current_router.name,
                "address": current_router.address,
                "port": current_router.port,
            }

        return stats
