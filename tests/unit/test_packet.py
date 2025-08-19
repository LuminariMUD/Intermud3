"""Unit tests for I3 packet models."""

import pytest
from src.models.packet import (
    I3Packet,
    PacketType,
    TellPacket,
    ChannelPacket,
    WhoPacket,
    FingerPacket,
    StartupPacket,
    MudlistPacket,
    ErrorPacket,
    PacketFactory,
    PacketValidationError
)


class TestTellPacket:
    """Test TellPacket functionality."""
    
    def test_create_tell_packet(self):
        """Test creating a tell packet."""
        packet = TellPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="targetuser",
            message="Hello, World!"
        )
        
        assert packet.packet_type == PacketType.TELL
        assert packet.ttl == 200
        assert packet.originator_mud == "TestMUD"
        assert packet.originator_user == "testuser"
        assert packet.target_mud == "TargetMUD"
        assert packet.target_user == "targetuser"
        assert packet.message == "Hello, World!"
    
    def test_tell_packet_validation(self):
        """Test tell packet validation."""
        # Valid packet
        packet = TellPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="targetuser",
            message="Hello"
        )
        packet.validate()  # Should not raise
        
        # Invalid TTL
        with pytest.raises(PacketValidationError, match="Invalid TTL"):
            TellPacket(
                ttl=-1,
                originator_mud="TestMUD",
                originator_user="testuser",
                target_mud="TargetMUD",
                target_user="targetuser",
                message="Hello"
            )
        
        # Missing originator user
        with pytest.raises(PacketValidationError, match="originator user"):
            TellPacket(
                ttl=200,
                originator_mud="TestMUD",
                originator_user="",
                target_mud="TargetMUD",
                target_user="targetuser",
                message="Hello"
            )
        
        # Missing target user
        with pytest.raises(PacketValidationError, match="target user"):
            TellPacket(
                ttl=200,
                originator_mud="TestMUD",
                originator_user="testuser",
                target_mud="TargetMUD",
                target_user="",
                message="Hello"
            )
        
        # Missing message
        with pytest.raises(PacketValidationError, match="message"):
            TellPacket(
                ttl=200,
                originator_mud="TestMUD",
                originator_user="testuser",
                target_mud="TargetMUD",
                target_user="targetuser",
                message=""
            )
    
    def test_tell_packet_to_lpc_array(self):
        """Test converting tell packet to LPC array.
        
        CRITICAL: Tell packets have EXACTLY 8 FIELDS!
        See docs/intermud3_docs/VISNAME_CLARIFICATION.md
        """
        packet = TellPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="targetuser",
            message="Hello, World!"
        )
        
        lpc_array = packet.to_lpc_array()
        
        # CRITICAL: Tell packets have 8 fields - visname at position 6!
        assert lpc_array == [
            "tell",
            200,
            "TestMUD",
            "testuser",
            "TargetMUD",
            "targetuser",
            "testuser",  # Position 6: visname defaults to originator_user
            "Hello, World!"
        ]
    
    def test_tell_packet_from_lpc_array(self):
        """Test creating tell packet from LPC array.
        
        CRITICAL: Tell packets have EXACTLY 8 FIELDS!
        See docs/intermud3_docs/VISNAME_CLARIFICATION.md
        """
        # CRITICAL: Tell packets have 8 fields - visname at position 6!
        lpc_array = [
            "tell",
            200,
            "TestMUD",
            "testuser",
            "TargetMUD",
            "targetuser",
            "testuser",  # Position 6: visname
            "Hello, World!"
        ]
        
        packet = TellPacket.from_lpc_array(lpc_array)
        
        assert packet.ttl == 200
        assert packet.originator_mud == "TestMUD"
        assert packet.originator_user == "testuser"
        assert packet.target_mud == "TargetMUD"
        assert packet.target_user == "targetuser"
        assert packet.message == "Hello, World!"
    
    def test_tell_packet_roundtrip(self):
        """Test roundtrip conversion of tell packet."""
        original = TellPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="targetuser",
            message="Test message with special chars: 你好!"
        )
        
        lpc_array = original.to_lpc_array()
        restored = TellPacket.from_lpc_array(lpc_array)
        
        assert restored.ttl == original.ttl
        assert restored.originator_mud == original.originator_mud
        assert restored.originator_user == original.originator_user
        assert restored.target_mud == original.target_mud
        assert restored.target_user == original.target_user
        assert restored.message == original.message


class TestChannelPacket:
    """Test ChannelPacket functionality."""
    
    def test_create_channel_packet(self):
        """Test creating channel packets."""
        # channel-m packet
        packet = ChannelPacket(
            packet_type=PacketType.CHANNEL_M,
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="*",
            target_user="*",
            channel="chat",
            message="Hello, channel!"
        )
        
        assert packet.packet_type == PacketType.CHANNEL_M
        assert packet.channel == "chat"
        assert packet.message == "Hello, channel!"
    
    def test_channel_packet_validation(self):
        """Test channel packet validation."""
        # Missing channel name
        with pytest.raises(PacketValidationError, match="Channel name"):
            ChannelPacket(
                packet_type=PacketType.CHANNEL_M,
                ttl=200,
                originator_mud="TestMUD",
                originator_user="testuser",
                target_mud="*",
                target_user="*",
                channel="",
                message="Hello"
            )
        
        # Missing message
        with pytest.raises(PacketValidationError, match="message"):
            ChannelPacket(
                packet_type=PacketType.CHANNEL_M,
                ttl=200,
                originator_mud="TestMUD",
                originator_user="testuser",
                target_mud="*",
                target_user="*",
                channel="chat",
                message=""
            )
    
    def test_channel_packet_types(self):
        """Test different channel packet types."""
        types = [PacketType.CHANNEL_M, PacketType.CHANNEL_E, PacketType.CHANNEL_T]
        
        for packet_type in types:
            packet = ChannelPacket(
                packet_type=packet_type,
                ttl=200,
                originator_mud="TestMUD",
                originator_user="testuser",
                target_mud="*",
                target_user="*",
                channel="chat",
                message="Test"
            )
            
            lpc_array = packet.to_lpc_array()
            assert lpc_array[0] == packet_type.value


class TestWhoPacket:
    """Test WhoPacket functionality."""
    
    def test_create_who_request(self):
        """Test creating who request packet."""
        packet = WhoPacket(
            packet_type=PacketType.WHO_REQ,
            ttl=200,
            originator_mud="TestMUD",
            originator_user="testuser",
            target_mud="TargetMUD",
            target_user="",
            filter_criteria={"level": ">10", "class": "wizard"}
        )
        
        assert packet.packet_type == PacketType.WHO_REQ
        assert packet.filter_criteria == {"level": ">10", "class": "wizard"}
        assert packet.who_data is None
    
    def test_create_who_reply(self):
        """Test creating who reply packet."""
        who_data = [
            {"name": "player1", "level": 15, "class": "wizard"},
            {"name": "player2", "level": 12, "class": "warrior"}
        ]
        
        packet = WhoPacket(
            packet_type=PacketType.WHO_REPLY,
            ttl=200,
            originator_mud="TargetMUD",
            originator_user="",
            target_mud="TestMUD",
            target_user="testuser",
            who_data=who_data
        )
        
        assert packet.packet_type == PacketType.WHO_REPLY
        assert packet.who_data == who_data
        assert packet.filter_criteria is None
    
    def test_who_packet_validation(self):
        """Test who packet validation."""
        # who-reply without data should fail
        with pytest.raises(PacketValidationError, match="who_data"):
            WhoPacket(
                packet_type=PacketType.WHO_REPLY,
                ttl=200,
                originator_mud="TestMUD",
                originator_user="",
                target_mud="TargetMUD",
                target_user="",
                who_data=None
            )


class TestStartupPacket:
    """Test StartupPacket functionality."""
    
    def test_create_startup_packet(self):
        """Test creating startup packet."""
        services = {
            "tell": 1,
            "channel": 1,
            "who": 1,
            "finger": 1
        }
        
        packet = StartupPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="",
            target_mud="*i3",
            target_user="",
            password=12345,
            mud_port=4000,
            tcp_port=4001,
            udp_port=0,
            mudlib="custom",
            base_mudlib="LPMud",
            driver="DGD",
            mud_type="MUD",
            open_status="open",
            admin_email="admin@test.mud",
            services=services
        )
        
        assert packet.packet_type == PacketType.STARTUP_REQ_3
        assert packet.password == 12345
        assert packet.mud_port == 4000
        assert packet.services == services
    
    def test_startup_packet_validation(self):
        """Test startup packet validation."""
        # Missing originator MUD
        with pytest.raises(PacketValidationError, match="originator MUD"):
            StartupPacket(
                ttl=200,
                originator_mud="",
                originator_user="",
                target_mud="*i3",
                target_user="",
                password=12345,
                mud_port=4000
            )
    
    def test_startup_packet_to_lpc_array(self):
        """Test converting startup packet to LPC array.
        
        StartupPacket has 20 fields (indices 0-19) including old_mudlist_id, 
        old_chanlist_id, and other_data field.
        """
        packet = StartupPacket(
            ttl=200,
            originator_mud="TestMUD",
            originator_user="",
            target_mud="*i3",
            target_user="",
            password=12345,
            mud_port=4000,
            tcp_port=4001,
            services={"tell": 1}
        )
        
        lpc_array = packet.to_lpc_array()
        
        # StartupPacket generates 20 fields (0-19)
        assert len(lpc_array) == 20
        assert lpc_array[0] == "startup-req-3"
        assert lpc_array[6] == 12345  # password
        assert lpc_array[9] == 4000   # mud_port (not index 7!)


class TestPacketFactory:
    """Test PacketFactory functionality."""
    
    def test_create_tell_packet(self):
        """Test factory creates correct tell packet.
        
        CRITICAL: Tell packets have EXACTLY 8 FIELDS!
        See docs/intermud3_docs/VISNAME_CLARIFICATION.md
        """
        # CRITICAL: Tell packets have 8 fields - visname at position 6!
        lpc_array = [
            "tell",
            200,
            "TestMUD",
            "testuser",
            "TargetMUD",
            "targetuser",
            "testuser",  # Position 6: visname
            "Hello"
        ]
        
        packet = PacketFactory.create_packet(lpc_array)
        
        assert isinstance(packet, TellPacket)
        assert packet.message == "Hello"
    
    def test_create_channel_packets(self):
        """Test factory creates correct channel packets."""
        for packet_type in ["channel-m", "channel-e", "channel-t"]:
            lpc_array = [
                packet_type,
                200,
                "TestMUD",
                "testuser",
                "*",
                "*",
                "chat",
                "Message"
            ]
            
            packet = PacketFactory.create_packet(lpc_array)
            
            assert isinstance(packet, ChannelPacket)
            assert packet.channel == "chat"
    
    def test_create_startup_packet(self):
        """Test factory creates correct startup packet.
        
        StartupPacket has 20 fields including old_mudlist_id and old_chanlist_id.
        """
        lpc_array = [
            "startup-req-3",
            200,              # ttl
            "TestMUD",        # originator_mud
            "",               # originator_user
            "*i3",            # target_mud
            "",               # target_user
            12345,            # password
            0,                # old_mudlist_id
            0,                # old_chanlist_id
            4000,             # mud_port
            4001,             # tcp_port
            0,                # udp_port
            "custom",         # mudlib
            "LPMud",          # base_mudlib
            "DGD",            # driver
            "MUD",            # mud_type
            "open",           # open_status
            "admin@test.mud",  # admin_email
            {"tell": 1},      # services
            {}                # other_data
        ]
        
        packet = PacketFactory.create_packet(lpc_array)
        
        assert isinstance(packet, StartupPacket)
        assert packet.password == 12345
        assert packet.mud_port == 4000  # Now at correct index
    
    def test_create_error_packet(self):
        """Test factory creates correct error packet."""
        lpc_array = [
            "error",
            200,
            "*i3",
            "",
            "TestMUD",
            "",
            "bad-pkt",
            "Invalid packet format",
            ["bad", "packet", "data"]
        ]
        
        packet = PacketFactory.create_packet(lpc_array)
        
        assert isinstance(packet, ErrorPacket)
        assert packet.error_code == "bad-pkt"
        assert packet.error_message == "Invalid packet format"
    
    def test_factory_invalid_packet(self):
        """Test factory handles invalid packets."""
        # Too few fields
        with pytest.raises(PacketValidationError, match="expected 6\\+ fields"):
            PacketFactory.create_packet([])
        
        with pytest.raises(PacketValidationError, match="expected 6\\+ fields"):
            PacketFactory.create_packet(["tell", 200])
        
        # Unknown packet type
        with pytest.raises(PacketValidationError, match="Unknown packet type"):
            PacketFactory.create_packet([
                "unknown-packet",
                200,
                "TestMUD",
                "",
                "TargetMUD",
                ""
            ])
    
    def test_register_custom_packet_class(self):
        """Test registering custom packet classes."""
        # This would be used for extending with new packet types
        # For now, just verify the method exists
        assert hasattr(PacketFactory, 'register_packet_class')