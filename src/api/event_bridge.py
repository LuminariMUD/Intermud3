"""Event bridge between I3 services and API event system.

This module connects the I3 packet processing system to the API event dispatcher.
"""

import asyncio
from typing import Any, Dict, Optional

from src.api.events import Event, EventType, event_dispatcher
from src.models.packet import (
    ChannelMessagePacket,
    ChannelPacket,
    EmotetoPacket,
    ErrorPacket,
    I3Packet,
    PacketType,
    TellPacket
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EventBridge:
    """Bridge between I3 services and API event system."""
    
    def __init__(self):
        """Initialize event bridge."""
        self.enabled = False
        self.stats = {
            "packets_processed": 0,
            "events_generated": 0,
            "errors": 0
        }
    
    def start(self):
        """Start the event bridge."""
        self.enabled = True
        logger.info("Event bridge started")
    
    def stop(self):
        """Stop the event bridge."""
        self.enabled = False
        logger.info("Event bridge stopped")
    
    async def process_incoming_packet(self, packet: I3Packet):
        """Process incoming I3 packet and generate events.
        
        Args:
            packet: Incoming I3 packet
        """
        if not self.enabled:
            return
        
        try:
            self.stats["packets_processed"] += 1
            
            # Route based on packet type
            if packet.packet_type == PacketType.TELL:
                await self._process_tell(packet)
            elif packet.packet_type == PacketType.EMOTETO:
                await self._process_emoteto(packet)
            elif packet.packet_type == PacketType.CHANNEL_M:
                await self._process_channel_message(packet)
            elif packet.packet_type == PacketType.CHANNEL_E:
                await self._process_channel_emote(packet)
            elif packet.packet_type == PacketType.ERROR:
                await self._process_error(packet)
            elif packet.packet_type == PacketType.MUDLIST:
                await self._process_mudlist_update(packet)
            # Add more packet types as needed
            
        except Exception as e:
            logger.error(f"Error processing packet for events: {e}")
            self.stats["errors"] += 1
    
    async def _process_tell(self, packet: TellPacket):
        """Process tell packet and generate event.
        
        Args:
            packet: Tell packet
        """
        event_data = {
            "from_mud": packet.originator_mud,
            "from_user": packet.originator_user,
            "to_user": packet.target_user,
            "message": packet.message,
            "visname": getattr(packet, "visname", packet.originator_user)
        }
        
        event = event_dispatcher.create_event(
            EventType.TELL_RECEIVED,
            event_data,
            priority=3,  # High priority for direct messages
            ttl=300  # 5 minutes
        )
        
        await event_dispatcher.dispatch(event)
        self.stats["events_generated"] += 1
        
        logger.debug(f"Generated tell_received event for {packet.target_user}")
    
    async def _process_emoteto(self, packet: EmotetoPacket):
        """Process emoteto packet and generate event.
        
        Args:
            packet: Emoteto packet
        """
        event_data = {
            "from_mud": packet.originator_mud,
            "from_user": packet.originator_user,
            "to_user": packet.target_user,
            "message": packet.message,
            "visname": getattr(packet, "visname", packet.originator_user)
        }
        
        event = event_dispatcher.create_event(
            EventType.EMOTETO_RECEIVED,
            event_data,
            priority=3,
            ttl=300
        )
        
        await event_dispatcher.dispatch(event)
        self.stats["events_generated"] += 1
        
        logger.debug(f"Generated emoteto_received event for {packet.target_user}")
    
    async def _process_channel_message(self, packet: ChannelMessagePacket):
        """Process channel message packet and generate event.
        
        Args:
            packet: Channel message packet
        """
        event_data = {
            "channel": packet.channel,
            "from_mud": packet.originator_mud,
            "from_user": packet.originator_user,
            "message": packet.message,
            "visname": getattr(packet, "visname", packet.originator_user)
        }
        
        event = event_dispatcher.create_event(
            EventType.CHANNEL_MESSAGE,
            event_data,
            priority=5,  # Normal priority for channel messages
            ttl=60  # 1 minute - channel messages are more ephemeral
        )
        
        await event_dispatcher.dispatch(event)
        self.stats["events_generated"] += 1
        
        logger.debug(f"Generated channel_message event for channel {packet.channel}")
    
    async def _process_channel_emote(self, packet: ChannelPacket):
        """Process channel emote packet and generate event.
        
        Args:
            packet: Channel emote packet
        """
        event_data = {
            "channel": packet.channel,
            "from_mud": packet.originator_mud,
            "from_user": packet.originator_user,
            "message": packet.message,
            "visname": getattr(packet, "visname", packet.originator_user)
        }
        
        event = event_dispatcher.create_event(
            EventType.CHANNEL_EMOTE,
            event_data,
            priority=5,
            ttl=60
        )
        
        await event_dispatcher.dispatch(event)
        self.stats["events_generated"] += 1
        
        logger.debug(f"Generated channel_emote event for channel {packet.channel}")
    
    async def _process_error(self, packet: ErrorPacket):
        """Process error packet and generate event.
        
        Args:
            packet: Error packet
        """
        event_data = {
            "error_code": packet.error_code,
            "error_message": packet.error_message,
            "from_mud": packet.originator_mud,
            "context": "i3_packet_error"
        }
        
        event = event_dispatcher.create_event(
            EventType.ERROR_OCCURRED,
            event_data,
            priority=2,  # High priority for errors
            ttl=600  # 10 minutes
        )
        
        await event_dispatcher.dispatch(event)
        self.stats["events_generated"] += 1
        
        logger.debug(f"Generated error_occurred event: {packet.error_code}")
    
    async def _process_mudlist_update(self, packet):
        """Process mudlist update and generate events for mud status changes.
        
        Args:
            packet: Mudlist packet
        """
        # This would track MUD online/offline status and generate events
        # For now, just a placeholder
        pass
    
    async def notify_mud_status(self, mud_name: str, online: bool, info: Optional[Dict] = None):
        """Notify about MUD status change.
        
        Args:
            mud_name: Name of the MUD
            online: Whether MUD is online
            info: Optional MUD information
        """
        event_type = EventType.MUD_ONLINE if online else EventType.MUD_OFFLINE
        
        event_data = {
            "mud_name": mud_name,
            "status": "online" if online else "offline"
        }
        
        if info:
            event_data["info"] = info
        
        event = event_dispatcher.create_event(
            event_type,
            event_data,
            priority=6,
            ttl=300
        )
        
        await event_dispatcher.dispatch(event)
        self.stats["events_generated"] += 1
        
        logger.info(f"MUD status change: {mud_name} is {'online' if online else 'offline'}")
    
    async def notify_channel_activity(
        self,
        channel: str,
        user: str,
        mud: str,
        action: str  # "joined" or "left"
    ):
        """Notify about channel join/leave activity.
        
        Args:
            channel: Channel name
            user: User name
            mud: MUD name
            action: "joined" or "left"
        """
        event_type = (
            EventType.USER_JOINED_CHANNEL if action == "joined"
            else EventType.USER_LEFT_CHANNEL
        )
        
        event_data = {
            "channel": channel,
            "user": user,
            "mud": mud,
            "action": action
        }
        
        event = event_dispatcher.create_event(
            event_type,
            event_data,
            priority=7,
            ttl=60
        )
        
        await event_dispatcher.dispatch(event)
        self.stats["events_generated"] += 1
    
    async def notify_gateway_reconnect(self):
        """Notify about gateway reconnection to router."""
        event_data = {
            "message": "Gateway reconnected to I3 router",
            "status": "connected"
        }
        
        event = event_dispatcher.create_event(
            EventType.GATEWAY_RECONNECTED,
            event_data,
            priority=1,  # Highest priority
            ttl=None  # No expiry
        )
        
        await event_dispatcher.dispatch(event)
        self.stats["events_generated"] += 1
        
        logger.info("Gateway reconnection event dispatched")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            **self.stats,
            "enabled": self.enabled
        }


# Global event bridge instance
event_bridge = EventBridge()