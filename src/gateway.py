"""Main I3 Gateway implementation."""

import asyncio
from pathlib import Path
from typing import Optional, Any, Dict, List

import structlog

from .config.models import Settings
from .network import (
    ConnectionManager,
    ConnectionState,
    RouterInfo
)
from .models.packet import PacketFactory, I3Packet, PacketType
from .state.manager import StateManager
from .services.base import ServiceManager


class I3Gateway:
    """Main I3 Gateway service."""
    
    def __init__(self, settings: Settings) -> None:
        """Initialize the I3 Gateway."""
        self.settings = settings
        self.logger = structlog.get_logger()
        self.running = False
        self._shutdown_event = asyncio.Event()
        
        # Initialize components
        self.state_manager = StateManager(
            persistence_dir=Path("data") if settings.gateway.state_dir else None,
            cache_ttl=300.0
        )
        
        self.service_manager = ServiceManager(self.state_manager)
        
        # Setup routers
        routers = []
        if settings.router.primary:
            routers.append(RouterInfo(
                name=settings.router.primary.name or "*i3",
                address=settings.router.primary.host,
                port=settings.router.primary.port,
                priority=0
            ))
        
        for i, fallback in enumerate(settings.router.fallback or []):
            routers.append(RouterInfo(
                name=fallback.name or f"fallback-{i}",
                address=fallback.host,
                port=fallback.port,
                priority=i + 1
            ))
        
        self.connection_manager = ConnectionManager(
            routers=routers,
            on_message=self._handle_message,
            on_state_change=self._handle_state_change,
            keepalive_interval=60.0,
            connection_timeout=30.0
        )
        
        # Packet processing
        self.packet_queue: asyncio.Queue = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None
    
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
        elif state == ConnectionState.DISCONNECTED:
            # Clear router-specific state
            pass
    
    async def _send_startup(self):
        """Send startup packet to router."""
        from .models.packet import StartupPacket
        
        # Build services dictionary
        services = {}
        for service_name in ["tell", "channel", "who", "finger", "locate", "mail", "news", "file"]:
            if getattr(self.settings.services, service_name, False):
                services[service_name] = 1
        
        # Create startup packet
        startup = StartupPacket(
            ttl=200,
            originator_mud=self.settings.mud.name,
            originator_user="",
            target_mud="*i3",
            target_user="",
            password=getattr(self.settings.mud, 'password', 0),
            mud_port=self.settings.mud.port,
            tcp_port=getattr(self.settings.mud, 'tcp_port', 0),
            udp_port=getattr(self.settings.mud, 'udp_port', 0),
            mudlib=getattr(self.settings.mud, 'mudlib', ''),
            base_mudlib=getattr(self.settings.mud, 'base_mudlib', ''),
            driver=getattr(self.settings.mud, 'driver', ''),
            mud_type=getattr(self.settings.mud, 'mud_type', 'MUD'),
            open_status=getattr(self.settings.mud, 'open_status', 'open'),
            admin_email=getattr(self.settings.mud, 'admin_email', ''),
            services=services
        )
        
        # Send startup packet
        await self.send_packet(startup)
        self.logger.info("Sent startup packet", mud_name=self.settings.mud.name)
    
    async def _process_packets(self):
        """Process incoming packets from the queue."""
        while self.running:
            try:
                # Get packet with timeout
                packet = await asyncio.wait_for(
                    self.packet_queue.get(),
                    timeout=1.0
                )
                
                # Handle special packets
                if packet.packet_type == PacketType.MUDLIST:
                    await self._handle_mudlist(packet)
                elif packet.packet_type == PacketType.STARTUP_REPLY:
                    await self._handle_startup_reply(packet)
                elif packet.packet_type == PacketType.ERROR:
                    await self._handle_error(packet)
                else:
                    # Route to service
                    await self.service_manager.queue_packet(packet)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error processing packet", error=str(e))
    
    async def _handle_mudlist(self, packet: Any):
        """Handle mudlist update from router."""
        from .models.packet import MudlistPacket
        
        if isinstance(packet, MudlistPacket):
            await self.state_manager.update_mudlist(
                packet.mudlist,
                packet.mudlist_id
            )
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
                "Router error",
                error_code=packet.error_code,
                error_message=packet.error_message
            )
    
    def get_stats(self) -> Dict[str, Any]:
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
                "sessions": len(self.state_manager.sessions)
            }
        }
        
        current_router = self.connection_manager.get_current_router()
        if current_router:
            stats["router"] = {
                "name": current_router.name,
                "address": current_router.address,
                "port": current_router.port
            }
        
        return stats