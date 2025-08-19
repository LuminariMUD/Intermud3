"""Mock I3 router for testing.

This module provides a mock I3 router that can be used for testing
the gateway without connecting to a real I3 network.
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
import random

from src.network.mudmode import MudModeStreamProtocol
from src.models.packet import (
    PacketType, I3Packet, StartupPacket, PacketFactory,
    MudlistPacket, ErrorPacket
)


@dataclass
class MockMudInfo:
    """Mock MUD information."""
    name: str
    address: str
    port: int
    driver: str = "FluffOS"
    mudlib: str = "LPMud"
    status: str = "online"
    services: Dict[str, int] = field(default_factory=dict)


class MockRouter:
    """Mock I3 router for testing."""
    
    def __init__(self, port: int = 8090):
        """Initialize mock router.
        
        Args:
            port: Port to listen on
        """
        self.port = port
        self.server = None
        self.running = False
        
        # Connected MUDs
        self.connected_muds: Dict[str, MockMudInfo] = {}
        self.connections: Dict[str, MudModeStreamProtocol] = {}
        
        # Mock mudlist
        self.mudlist_id = random.randint(1000, 9999)
        self.mudlist = self._create_mock_mudlist()
        
        # Mock channel list
        self.chanlist_id = random.randint(1000, 9999)
        self.chanlist = self._create_mock_chanlist()
        
        # Message handlers
        self.handlers: Dict[PacketType, Callable] = {
            PacketType.STARTUP_REQ_3: self._handle_startup,
            PacketType.TELL: self._handle_tell,
            PacketType.CHANNEL_M: self._handle_channel_message,
            PacketType.WHO_REQ: self._handle_who_request,
            PacketType.FINGER_REQ: self._handle_finger_request,
            PacketType.LOCATE_REQ: self._handle_locate_request,
        }
        
        # Statistics
        self.packets_received = 0
        self.packets_sent = 0
    
    def _create_mock_mudlist(self) -> Dict[str, List[Any]]:
        """Create a mock mudlist.
        
        Returns:
            Mock mudlist data
        """
        return {
            "TestMUD": [
                -1,  # Status (-1 = up)
                "127.0.0.1 8080",  # Address
                8080,  # Player port
                0,  # TCP port
                0,  # UDP port
                "LPMud",  # Mudlib
                "LPMud",  # Base mudlib
                "FluffOS",  # Driver
                "LP",  # MUD type
                "open",  # Open status
                "admin@testmud.com",  # Admin email
                {  # Services
                    "tell": 1,
                    "channel": 1,
                    "who": 1,
                    "finger": 1,
                    "locate": 1
                },
                0  # Other data
            ],
            "OtherMUD": [
                -1,
                "192.168.1.1 9000",
                9000,
                0,
                0,
                "Diku",
                "Diku",
                "CircleMUD",
                "Diku",
                "open",
                "admin@othermud.com",
                {
                    "tell": 1,
                    "channel": 1,
                    "who": 1
                },
                0
            ]
        }
    
    def _create_mock_chanlist(self) -> Dict[str, Any]:
        """Create a mock channel list.
        
        Returns:
            Mock channel list data
        """
        return {
            "imud_gossip": {
                "owner": "*i3",
                "type": 0
            },
            "imud_code": {
                "owner": "*i3",
                "type": 0
            },
            "test": {
                "owner": "TestMUD",
                "type": 1
            }
        }
    
    async def start(self):
        """Start the mock router."""
        self.running = True
        
        # Create server
        loop = asyncio.get_event_loop()
        self.server = await loop.create_server(
            lambda: MudModeStreamProtocol(
                on_message=self._handle_message,
                on_connection_lost=self._handle_disconnect
            ),
            '127.0.0.1',
            self.port
        )
        
        print(f"Mock router listening on port {self.port}")
    
    async def stop(self):
        """Stop the mock router."""
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Close all connections
        for protocol in self.connections.values():
            protocol.close()
        
        self.connections.clear()
        self.connected_muds.clear()
    
    async def _handle_message(self, message: Any):
        """Handle incoming message from a MUD.
        
        Args:
            message: Incoming message (LPC array)
        """
        self.packets_received += 1
        
        try:
            # Parse packet
            packet = PacketFactory.create_packet(message)
            
            # Get handler
            handler = self.handlers.get(packet.packet_type)
            if handler:
                await handler(packet)
            else:
                print(f"No handler for packet type: {packet.packet_type}")
        
        except Exception as e:
            print(f"Error handling message: {e}")
    
    async def _handle_disconnect(self):
        """Handle MUD disconnection."""
        # Find and remove disconnected MUD
        disconnected = []
        for mud_name, protocol in self.connections.items():
            if not protocol.transport or protocol.transport.is_closing():
                disconnected.append(mud_name)
        
        for mud_name in disconnected:
            del self.connections[mud_name]
            if mud_name in self.connected_muds:
                del self.connected_muds[mud_name]
            print(f"MUD disconnected: {mud_name}")
    
    async def _handle_startup(self, packet: StartupPacket):
        """Handle startup packet from MUD.
        
        Args:
            packet: Startup packet
        """
        print(f"Startup from {packet.originator_mud}")
        
        # Register MUD
        mud_info = MockMudInfo(
            name=packet.originator_mud,
            address="127.0.0.1",
            port=packet.mud_port if packet.mud_port else packet.player_port,
            driver=packet.driver,
            mudlib=packet.mudlib,
            services=packet.services
        )
        self.connected_muds[packet.originator_mud] = mud_info
        
        # Send startup reply
        reply = [
            "startup-reply",
            200,
            "*i3",  # Router name
            0,
            packet.originator_mud,
            0,
            [  # Router list
                ["*i3", "127.0.0.1 " + str(self.port)]
            ],
            self.mudlist_id
        ]
        
        await self._send_to_mud(packet.originator_mud, reply)
        
        # Send mudlist if requested
        if packet.old_mudlist_id != self.mudlist_id:
            await self._send_mudlist(packet.originator_mud)
        
        # Send chanlist if requested
        if packet.old_chanlist_id != self.chanlist_id:
            await self._send_chanlist(packet.originator_mud)
    
    async def _send_mudlist(self, mud_name: str):
        """Send mudlist to a MUD.
        
        Args:
            mud_name: Target MUD name
        """
        mudlist_packet = MudlistPacket(
            ttl=200,
            originator_mud="*i3",
            originator_user="",
            target_mud=mud_name,
            target_user="",
            mudlist_id=self.mudlist_id,
            mudlist=self.mudlist
        )
        
        await self._send_to_mud(mud_name, mudlist_packet.to_lpc_array())
    
    async def _send_chanlist(self, mud_name: str):
        """Send channel list to a MUD.
        
        Args:
            mud_name: Target MUD name
        """
        chanlist_packet = [
            "chanlist-reply",
            200,
            "*i3",
            0,
            mud_name,
            0,
            self.chanlist_id,
            self.chanlist
        ]
        
        await self._send_to_mud(mud_name, chanlist_packet)
    
    async def _handle_tell(self, packet: I3Packet):
        """Handle tell packet.
        
        Args:
            packet: Tell packet
        """
        print(f"Tell from {packet.originator_mud}:{packet.originator_user} to {packet.target_mud}:{packet.target_user}")
        
        # Check if target MUD is connected
        if packet.target_mud in self.connected_muds:
            # Forward to target MUD
            await self._send_to_mud(packet.target_mud, packet.to_lpc_array())
        else:
            # Send error back
            error = ErrorPacket(
                ttl=200,
                originator_mud="*i3",
                originator_user="",
                target_mud=packet.originator_mud,
                target_user=packet.originator_user,
                error_code="unk-dst",
                error_message=f"Unknown MUD: {packet.target_mud}",
                error_packet=packet.to_lpc_array()
            )
            await self._send_to_mud(packet.originator_mud, error.to_lpc_array())
    
    async def _handle_channel_message(self, packet: I3Packet):
        """Handle channel message.
        
        Args:
            packet: Channel message packet
        """
        print(f"Channel message from {packet.originator_mud}:{packet.originator_user}")
        
        # Broadcast to all connected MUDs
        for mud_name in self.connected_muds:
            if mud_name != packet.originator_mud:
                await self._send_to_mud(mud_name, packet.to_lpc_array())
    
    async def _handle_who_request(self, packet: I3Packet):
        """Handle who request.
        
        Args:
            packet: Who request packet
        """
        print(f"Who request from {packet.originator_mud}")
        
        # Send mock who reply
        who_reply = [
            "who-reply",
            200,
            packet.target_mud,
            "",
            packet.originator_mud,
            packet.originator_user,
            [  # Mock user list
                {
                    "name": "TestPlayer",
                    "idle": 300,
                    "level": 50,
                    "extra": "Testing"
                }
            ]
        ]
        
        await self._send_to_mud(packet.originator_mud, who_reply)
    
    async def _handle_finger_request(self, packet: I3Packet):
        """Handle finger request.
        
        Args:
            packet: Finger request packet
        """
        print(f"Finger request from {packet.originator_mud}")
        
        # Send mock finger reply
        finger_reply = [
            "finger-reply",
            200,
            packet.target_mud,
            "",
            packet.originator_mud,
            packet.originator_user,
            {  # Mock user info
                "name": "TestPlayer",
                "title": "the Tester",
                "real_name": "Test User",
                "email": "test@example.com",
                "login_time": datetime.now().isoformat(),
                "idle_time": 300,
                "level": 50
            }
        ]
        
        await self._send_to_mud(packet.originator_mud, finger_reply)
    
    async def _handle_locate_request(self, packet: I3Packet):
        """Handle locate request.
        
        Args:
            packet: Locate request packet
        """
        print(f"Locate request from {packet.originator_mud}")
        
        # For broadcast, randomly decide if user is "found"
        if random.random() > 0.5:
            # Send locate reply
            locate_reply = [
                "locate-reply",
                200,
                "TestMUD",
                "",
                packet.originator_mud,
                packet.originator_user,
                "TestMUD",
                "TestPlayer",
                300,
                "Testing"
            ]
            
            await self._send_to_mud(packet.originator_mud, locate_reply)
    
    async def _send_to_mud(self, mud_name: str, data: Any):
        """Send data to a connected MUD.
        
        Args:
            mud_name: Target MUD name
            data: Data to send (LPC array)
        """
        if mud_name in self.connections:
            protocol = self.connections[mud_name]
            protocol.send_message(data)
            self.packets_sent += 1
        else:
            print(f"MUD not connected: {mud_name}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "connected_muds": len(self.connected_muds),
            "packets_received": self.packets_received,
            "packets_sent": self.packets_sent,
            "mudlist_id": self.mudlist_id,
            "chanlist_id": self.chanlist_id
        }