"""Unit tests for I3 packet models - with protocol fixes."""

import pytest
from src.models.packet import (
    I3Packet,
    PacketType,
    TellPacket,
    EmotetoPacket,
    LocatePacket,
    ChannelPacket,
    WhoPacket,
    FingerPacket,
    StartupPacket,
    StartupReplyPacket,
    MudlistPacket,
    ErrorPacket,
    PacketFactory,
    PacketValidationError
)


class TestTellPacketFixed:
    """Test fixed TellPacket with visname field.
    
    CRITICAL: Tell packets have EXACTLY 8 FIELDS with visname at position 6!
    See docs/intermud3_docs/VISNAME_CLARIFICATION.md
    """
    
    def test_tell_packet_with_visname(self):
        """Test tell packet structure - visname is REQUIRED."""
        packet = TellPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="targetuser",
            message="Hello, World!"
        )
        
        lpc_array = packet.to_lpc_array()
        # CRITICAL: Tell packets have 8 fields WITH visname
        assert len(lpc_array) == 8  # MUST have 8 fields with visname
        assert lpc_array[6] == "testuser"  # visname at position 6 (defaults to originator_user)
        assert lpc_array[7] == "Hello, World!"  # message at position 7
    
    def test_tell_packet_visname_defaults(self):
        """Test tell packet visname defaults to originator_user."""
        packet = TellPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="targetuser",
            message="Hello!"
        )
        
        # Validate packet structure
        packet.validate()
        assert packet.originator_user == "testuser"
        # CRITICAL: visname defaults to originator_user
        assert packet.visname == "testuser"
    
    def test_tell_packet_field_zero_handling(self):
        """Test that tell packet requires target_user."""
        # TellPacket now requires target_user, test valid packet
        packet = TellPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="targetuser",
            message="Message"
        )
        
        lpc_array = packet.to_lpc_array()
        assert lpc_array[4] == "TargetMUD"  # target_mud
        assert lpc_array[5] == "targetuser"  # target_user
        assert lpc_array[6] == "testuser"  # visname defaults to originator_user
        assert lpc_array[7] == "Message"  # message at position 7
    
    def test_tell_packet_from_lpc_with_zeros(self):
        """Test creating packet from LPC array.
        
        CRITICAL: Tell packets have EXACTLY 8 FIELDS!
        See docs/intermud3_docs/VISNAME_CLARIFICATION.md
        """
        lpc_array = [
            "tell",
            200,
            "TestMUD",
            "testuser",
            "TargetMUD",
            "targetuser",  # Required field
            "testuser",    # Position 6: visname (REQUIRED)
            "Message"       # Position 7: message
        ]
        
        packet = TellPacket.from_lpc_array(lpc_array)
        assert packet.target_mud == "TargetMUD"
        assert packet.target_user == "targetuser"


class TestEmotetoPacket:
    """Test EmotetoPacket functionality."""
    
    def test_create_emoteto_packet(self):
        """Test creating emoteto packet."""
        packet = EmotetoPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="targetuser",
            visname="TestUser",
            message="smiles warmly"
        )
        
        assert packet.packet_type == PacketType.EMOTETO
        assert packet.visname == "TestUser"
        assert packet.message == "smiles warmly"
        
        lpc_array = packet.to_lpc_array()
        assert lpc_array[0] == "emoteto"
        assert len(lpc_array) == 8


class TestLocatePacket:
    """Test LocatePacket functionality."""
    
    def test_create_locate_request(self):
        """Test creating locate request packet."""
        packet = LocatePacket(
            packet_type=PacketType.LOCATE_REQ,
            ttl=200,
            originator_mud="TestMUD",
            originator_user="seeker",
            target_mud="",  # Broadcast
            target_user="",
            user_to_locate="lostuser"
        )
        
        assert packet.packet_type == PacketType.LOCATE_REQ
        assert packet.user_to_locate == "lostuser"
        
        lpc_array = packet.to_lpc_array()
        assert lpc_array[0] == "locate-req"
        assert lpc_array[4] == 0  # Broadcast
        assert lpc_array[6] == "lostuser"
    
    def test_create_locate_reply(self):
        """Test creating locate reply packet."""
        packet = LocatePacket(
            packet_type=PacketType.LOCATE_REPLY,
            ttl=200,
            originator_mud="FoundMUD",
            originator_user="",
            target_mud="TestMUD",
            target_user="seeker",
            located_mud="FoundMUD",
            located_user="lostuser",
            idle_time=300,
            status_string="In the tavern"
        )
        
        assert packet.packet_type == PacketType.LOCATE_REPLY
        assert packet.located_mud == "FoundMUD"
        assert packet.idle_time == 300
        
        lpc_array = packet.to_lpc_array()
        assert lpc_array[0] == "locate-reply"
        assert len(lpc_array) == 10


class TestStartupPacketFixed:
    """Test fixed StartupPacket with correct field order."""
    
    def test_startup_packet_field_order(self):
        """Test startup packet has correct field order per protocol."""
        packet = StartupPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="",
            target_mud="*i3",
            target_user="",
            password=12345,
            old_mudlist_id=100,
            old_chanlist_id=50,
            player_port=4000,
            imud_tcp_port=4001,
            imud_udp_port=0,
            mudlib="custom",
            base_mudlib="LPMud",
            driver="DGD",
            mud_type="LP",
            open_status="open for public",
            admin_email="admin@test.mud",
            services={"tell": 1, "channel": 1}
        )
        
        lpc_array = packet.to_lpc_array()
        
        # Check field positions match protocol
        assert lpc_array[0] == "startup-req-3"
        assert lpc_array[1] == 200  # TTL
        assert lpc_array[2] == "TestMUD"
        assert lpc_array[3] == 0  # originator_user always 0
        assert lpc_array[4] == "*i3"
        assert lpc_array[5] == 0  # target_user always 0
        assert lpc_array[6] == 12345  # password
        assert lpc_array[7] == 100  # old_mudlist_id
        assert lpc_array[8] == 50  # old_chanlist_id
        assert lpc_array[9] == 4000  # player_port
        assert lpc_array[10] == 4001  # imud_tcp_port
        assert lpc_array[11] == 0  # imud_udp_port
        assert lpc_array[12] == "custom"  # mudlib
        assert lpc_array[13] == "LPMud"  # base_mudlib
        assert lpc_array[14] == "DGD"  # driver
        assert lpc_array[15] == "LP"  # mud_type
        assert lpc_array[16] == "open for public"  # open_status
        assert lpc_array[17] == "admin@test.mud"  # admin_email
        assert lpc_array[18] == {"tell": 1, "channel": 1}  # services
        
    def test_startup_packet_other_data_as_zero(self):
        """Test other_data can be 0 instead of empty dict."""
        packet = StartupPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="",
            target_mud="*i3",
            target_user=""
        )
        
        lpc_array = packet.to_lpc_array()
        assert lpc_array[19] == 0  # other_data becomes 0 when empty


class TestStartupReplyPacket:
    """Test StartupReplyPacket functionality."""
    
    def test_create_startup_reply(self):
        """Test creating startup reply packet."""
        router_list = [
            ["*i3", "204.209.44.3 8080"],
            ["*wpr", "195.242.99.94 8080"]
        ]
        
        packet = StartupReplyPacket(
            ttl=200,
            originator_mud="*i3",
            originator_user="",
            target_mud="TestMUD",
            target_user="",
            router_list=router_list,
            password=67890
        )
        
        assert packet.packet_type == PacketType.STARTUP_REPLY
        assert packet.router_list == router_list
        assert packet.password == 67890
        
        lpc_array = packet.to_lpc_array()
        assert lpc_array[0] == "startup-reply"
        assert lpc_array[6] == router_list
        assert lpc_array[7] == 67890


class TestPacketFactoryFixed:
    """Test PacketFactory with fixed packet types."""
    
    def test_create_emoteto_packet(self):
        """Test factory creates EmotetoPacket correctly."""
        lpc_array = [
            "emoteto",
            200,
            "TestMUD",
            "testuser",
            "TargetMUD",
            "targetuser",
            "TestUser",
            "grins"
        ]
        
        packet = PacketFactory.create_packet(lpc_array)
        assert isinstance(packet, EmotetoPacket)
        assert packet.message == "grins"
    
    def test_create_locate_packets(self):
        """Test factory creates LocatePacket correctly."""
        # locate-req
        req_array = [
            "locate-req",
            200,
            "TestMUD",
            "seeker",
            0,  # broadcast
            0,
            "findme"
        ]
        
        packet = PacketFactory.create_packet(req_array)
        assert isinstance(packet, LocatePacket)
        assert packet.user_to_locate == "findme"
        
        # locate-reply
        reply_array = [
            "locate-reply",
            200,
            "FoundMUD",
            "",
            "TestMUD",
            "seeker",
            "FoundMUD",
            "findme",
            120,
            "At the shop"
        ]
        
        packet = PacketFactory.create_packet(reply_array)
        assert isinstance(packet, LocatePacket)
        assert packet.located_user == "findme"
    
    def test_create_startup_reply_packet(self):
        """Test factory creates StartupReplyPacket correctly."""
        lpc_array = [
            "startup-reply",
            200,
            "*i3",
            0,
            "TestMUD",
            0,
            [["*i3", "204.209.44.3 8080"]],
            54321
        ]
        
        packet = PacketFactory.create_packet(lpc_array)
        assert isinstance(packet, StartupReplyPacket)
        assert packet.password == 54321


if __name__ == "__main__":
    pytest.main([__file__, "-v"])