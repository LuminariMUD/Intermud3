"""Locate service for finding users across the I3 network.

This service handles locate-req and locate-reply packets to find
users across multiple MUDs on the I3 network.
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog

from .base import BaseService
from ..models.packet import (
    I3Packet, PacketType, LocatePacket, PacketValidationError
)


class LocateService(BaseService):
    """Service for handling locate requests."""
    
    service_name = "locate"
    supported_packets = [PacketType.LOCATE_REQ, PacketType.LOCATE_REPLY]
    requires_auth = False
    
    def __init__(self, state_manager, gateway=None):
        """Initialize locate service.
        
        Args:
            state_manager: State manager instance
            gateway: Reference to the gateway for sending packets
        """
        super().__init__(state_manager)
        self.gateway = gateway
        self.logger = structlog.get_logger()
        
        # Track pending locate requests
        self.pending_locates: Dict[str, Dict[str, Any]] = {}
        
        # Cache for locate results
        self.locate_cache: Dict[str, tuple[Dict, float]] = {}
        self.cache_ttl = 30.0  # 30 seconds cache
        
        # Timeout for locate requests
        self.locate_timeout = 5.0  # 5 seconds
    
    async def initialize(self) -> None:
        """Initialize the locate service."""
        await super().initialize()
        self.logger.info("Locate service initialized")
    
    async def handle_packet(self, packet: I3Packet) -> Optional[I3Packet]:
        """Handle incoming locate packet.
        
        Args:
            packet: The incoming packet
            
        Returns:
            Optional response packet
        """
        if packet.packet_type == PacketType.LOCATE_REQ:
            return await self._handle_locate_request(packet)
        elif packet.packet_type == PacketType.LOCATE_REPLY:
            return await self._handle_locate_reply(packet)
        
        return None
    
    async def _handle_locate_request(self, packet: LocatePacket) -> Optional[I3Packet]:
        """Handle a locate request packet.
        
        Args:
            packet: The locate request packet
            
        Returns:
            Locate reply packet if user is found locally
        """
        self.logger.info(
            "Received locate request",
            from_mud=packet.originator_mud,
            from_user=packet.originator_user,
            searching_for=packet.user_to_locate
        )
        
        # Check if this is a broadcast request (target_mud == 0)
        is_broadcast = packet.target_mud == "0" or packet.target_mud == 0
        
        # Check cache first
        cache_key = f"locate:{packet.user_to_locate.lower()}"
        if cache_key in self.locate_cache:
            cached_data, cache_time = self.locate_cache[cache_key]
            if (datetime.now().timestamp() - cache_time) < self.cache_ttl:
                self.logger.debug("Returning cached locate data", user=packet.user_to_locate)
                if cached_data.get('found'):
                    return self._create_locate_reply(packet, cached_data)
        
        # Search locally first
        local_result = await self._search_local_user(packet.user_to_locate)
        
        if local_result:
            # User found locally
            self.logger.info(
                "User found locally",
                user=packet.user_to_locate,
                idle=local_result.get('idle_time', 0)
            )
            
            # Cache the result
            result_data = {
                'found': True,
                'mud': self.gateway.settings.mud.name if self.gateway else 'local',
                'user': local_result['user'],
                'idle_time': local_result['idle_time'],
                'status': local_result.get('status', '')
            }
            self.locate_cache[cache_key] = (result_data, datetime.now().timestamp())
            
            # Send reply
            return self._create_locate_reply(packet, result_data)
        
        elif not is_broadcast:
            # Not found locally and not a broadcast - send empty reply
            return self._create_locate_reply(packet, {'found': False})
        
        # For broadcast requests, don't reply if not found locally
        # Other MUDs will respond if they have the user
        return None
    
    async def _handle_locate_reply(self, packet: LocatePacket) -> Optional[I3Packet]:
        """Handle a locate reply packet.
        
        Args:
            packet: The locate reply packet
            
        Returns:
            None (replies are informational)
        """
        self.logger.info(
            "Received locate reply",
            from_mud=packet.originator_mud,
            found_mud=packet.located_mud,
            found_user=packet.located_user,
            idle=packet.idle_time
        )
        
        # Check if this is a response to one of our pending requests
        request_key = f"{packet.target_user}:{packet.located_user.lower()}"
        if request_key in self.pending_locates:
            # Store the result
            self.pending_locates[request_key]['result'] = {
                'found': bool(packet.located_mud),
                'mud': packet.located_mud,
                'user': packet.located_user,
                'idle_time': packet.idle_time,
                'status': packet.status_string
            }
            
            # Signal that we got a response
            if 'event' in self.pending_locates[request_key]:
                self.pending_locates[request_key]['event'].set()
        
        # Cache the result if user was found
        if packet.located_mud:
            cache_key = f"locate:{packet.located_user.lower()}"
            result_data = {
                'found': True,
                'mud': packet.located_mud,
                'user': packet.located_user,
                'idle_time': packet.idle_time,
                'status': packet.status_string
            }
            self.locate_cache[cache_key] = (result_data, datetime.now().timestamp())
        
        return None
    
    async def _search_local_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Search for a user locally.
        
        Args:
            username: Username to search for
            
        Returns:
            User information if found, None otherwise
        """
        # Search sessions for matching user (case-insensitive)
        username_lower = username.lower()
        
        for session_id, session in self.state_manager.sessions.items():
            if session.user_name.lower() == username_lower and session.is_online:
                # Calculate idle time
                idle_time = int((datetime.now() - session.last_activity).total_seconds())
                
                return {
                    'user': session.user_name,
                    'idle_time': idle_time,
                    'status': session.status_message or ''
                }
        
        return None
    
    def _create_locate_reply(self, request: LocatePacket, 
                           result: Dict[str, Any]) -> LocatePacket:
        """Create a locate reply packet.
        
        Args:
            request: The original locate request
            result: Search result dictionary
            
        Returns:
            Locate reply packet
        """
        if not result.get('found'):
            # User not found - send empty reply
            return LocatePacket(
                packet_type=PacketType.LOCATE_REPLY,
                ttl=200,
                originator_mud=self.gateway.settings.mud.name if self.gateway else "",
                originator_user="",
                target_mud=request.originator_mud,
                target_user=request.originator_user,
                user_to_locate="",
                located_mud="",
                located_user="",
                idle_time=0,
                status_string=""
            )
        
        return LocatePacket(
            packet_type=PacketType.LOCATE_REPLY,
            ttl=200,
            originator_mud=self.gateway.settings.mud.name if self.gateway else "",
            originator_user="",
            target_mud=request.originator_mud,
            target_user=request.originator_user,
            user_to_locate="",
            located_mud=result['mud'],
            located_user=result['user'],
            idle_time=result.get('idle_time', 0),
            status_string=result.get('status', '')
        )
    
    async def validate_packet(self, packet: I3Packet) -> bool:
        """Validate a locate packet.
        
        Args:
            packet: The packet to validate
            
        Returns:
            True if packet is valid
        """
        if packet.packet_type not in self.supported_packets:
            return False
        
        if not isinstance(packet, LocatePacket):
            return False
        
        if packet.packet_type == PacketType.LOCATE_REQ:
            if not packet.user_to_locate:
                self.logger.warning("Locate request missing user_to_locate")
                return False
        
        return True
    
    async def locate_user(self, username: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Locate a user across the I3 network.
        
        Args:
            username: Username to locate
            timeout: Optional timeout in seconds
            
        Returns:
            Location information if found, None otherwise
        """
        if not self.gateway:
            self.logger.error("No gateway available for locate request")
            return None
        
        timeout = timeout or self.locate_timeout
        
        # Check cache first
        cache_key = f"locate:{username.lower()}"
        if cache_key in self.locate_cache:
            cached_data, cache_time = self.locate_cache[cache_key]
            if (datetime.now().timestamp() - cache_time) < self.cache_ttl:
                if cached_data.get('found'):
                    return cached_data
        
        # Check locally first
        local_result = await self._search_local_user(username)
        if local_result:
            result = {
                'found': True,
                'mud': self.gateway.settings.mud.name,
                'user': local_result['user'],
                'idle_time': local_result['idle_time'],
                'status': local_result.get('status', '')
            }
            self.locate_cache[cache_key] = (result, datetime.now().timestamp())
            return result
        
        # Create pending request
        request_key = f"{self.gateway.settings.mud.name}:{username.lower()}"
        event = asyncio.Event()
        self.pending_locates[request_key] = {
            'event': event,
            'result': None,
            'timestamp': datetime.now()
        }
        
        # Send broadcast locate request
        locate_req = LocatePacket(
            packet_type=PacketType.LOCATE_REQ,
            ttl=200,
            originator_mud=self.gateway.settings.mud.name,
            originator_user=self.gateway.settings.mud.name,  # Use MUD name as user for tracking
            target_mud="0",  # Broadcast
            target_user="",
            user_to_locate=username
        )
        
        success = await self.gateway.send_packet(locate_req)
        
        if not success:
            del self.pending_locates[request_key]
            return None
        
        # Wait for response with timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            result = self.pending_locates[request_key].get('result')
            del self.pending_locates[request_key]
            
            if result and result.get('found'):
                # Cache successful result
                self.locate_cache[cache_key] = (result, datetime.now().timestamp())
            
            return result
            
        except asyncio.TimeoutError:
            # No response within timeout
            del self.pending_locates[request_key]
            
            # Cache negative result
            negative_result = {'found': False}
            self.locate_cache[cache_key] = (negative_result, datetime.now().timestamp())
            
            return None
    
    def clear_cache(self):
        """Clear the locate cache."""
        self.locate_cache.clear()
        self.logger.debug("Locate cache cleared")
    
    async def cleanup_pending(self):
        """Clean up old pending requests."""
        now = datetime.now()
        expired = []
        
        for key, data in self.pending_locates.items():
            age = (now - data['timestamp']).total_seconds()
            if age > 60:  # Remove requests older than 1 minute
                expired.append(key)
        
        for key in expired:
            del self.pending_locates[key]
        
        if expired:
            self.logger.debug("Cleaned up expired locate requests", count=len(expired))