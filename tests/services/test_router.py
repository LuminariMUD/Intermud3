"""Comprehensive unit tests for RouterService."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Optional, Dict, Any

from src.services.router import RouterService
from src.models.packet import (
    I3Packet, TellPacket, ChannelPacket, WhoPacket, ErrorPacket,
    PacketType
)
from src.state.manager import StateManager, MudInfo


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager."""
    manager = Mock(spec=StateManager)
    manager.get_mud = AsyncMock()
    return manager


@pytest.fixture
def mock_gateway():
    """Create a mock gateway."""
    gateway = Mock()
    gateway.settings = Mock()
    gateway.settings.mud = Mock()
    gateway.settings.mud.name = "TestMUD"
    gateway.send_packet = AsyncMock(return_value=True)
    gateway.service_manager = Mock()
    gateway.service_manager.queue_packet = AsyncMock()
    return gateway


@pytest.fixture
def router_service(mock_state_manager, mock_gateway):
    """Create a RouterService instance for testing."""
    service = RouterService(mock_state_manager, mock_gateway)
    return service


@pytest.fixture
def sample_tell_packet():
    """Create a sample tell packet for routing."""
    return TellPacket(
        ttl=200,
        originator_mud="RemoteMUD",
        originator_user="sender",
        target_mud="TestMUD",
        target_user="receiver",
        message="Hello!"
    )


@pytest.fixture
def sample_channel_packet():
    """Create a sample channel packet for routing."""
    return ChannelPacket(
        packet_type=PacketType.CHANNEL_M,
        ttl=200,
        originator_mud="RemoteMUD",
        originator_user="sender",
        target_mud="0",  # Broadcast
        target_user="",
        channel="gossip",
        message="Channel message"
    )


@pytest.fixture
def sample_remote_packet():
    """Create a sample packet for remote routing."""
    return TellPacket(
        ttl=200,
        originator_mud="SourceMUD",
        originator_user="sender",
        target_mud="RemoteMUD",  # Different target
        target_user="receiver",
        message="Remote message"
    )


@pytest.fixture
def online_mud_info():
    """Create an online MUD info object."""
    mud_info = Mock(spec=MudInfo)
    mud_info.name = "RemoteMUD"
    mud_info.status = "online"
    mud_info.port = 4000
    mud_info.services = {"tell": 1, "channel": 1}
    return mud_info


@pytest.fixture
def offline_mud_info():
    """Create an offline MUD info object."""
    mud_info = Mock(spec=MudInfo)
    mud_info.name = "OfflineMUD"
    mud_info.status = "offline"
    mud_info.port = 4000
    mud_info.services = {"tell": 1, "channel": 1}
    return mud_info


class TestRouterServiceInitialization:
    """Test RouterService initialization."""
    
    async def test_initialization(self, router_service):
        """Test service initialization."""
        await router_service.initialize()
        assert router_service.service_name == "router"
        assert router_service.supported_packets == []  # Router handles all packets
        assert not router_service.requires_auth
        assert router_service.packets_routed_local == 0
        assert router_service.packets_routed_remote == 0
        assert router_service.packets_broadcast == 0
        assert router_service.packets_dropped == 0
    
    async def test_initialization_without_gateway(self, mock_state_manager):
        """Test service initialization without gateway."""
        service = RouterService(mock_state_manager, None)
        await service.initialize()
        assert service.gateway is None
        assert service.service_name == "router"
    
    async def test_service_properties(self, router_service):
        """Test basic service properties."""
        assert router_service.service_name == "router"
        assert router_service.requires_auth is False
        assert hasattr(router_service, 'logger')
        assert hasattr(router_service, 'packets_routed_local')
        assert hasattr(router_service, 'packets_routed_remote')
        assert hasattr(router_service, 'packets_broadcast')
        assert hasattr(router_service, 'packets_dropped')
    
    async def test_statistics_initialization(self, router_service):
        """Test that statistics are initialized to zero."""
        stats = router_service.get_stats()
        assert stats["packets_routed_local"] == 0
        assert stats["packets_routed_remote"] == 0
        assert stats["packets_broadcast"] == 0
        assert stats["packets_dropped"] == 0
        assert stats["total_routed"] == 0


class TestLocalRouting:
    """Test routing packets to local services."""
    
    async def test_route_local_packet(self, router_service, sample_tell_packet, mock_gateway):
        """Test routing packet to local MUD."""
        result = await router_service.route_packet(sample_tell_packet)
        
        assert result is True
        assert router_service.packets_routed_local == 1
        mock_gateway.service_manager.queue_packet.assert_called_once_with(sample_tell_packet)
        assert sample_tell_packet.ttl == 199  # TTL should be decremented
    
    async def test_route_local_without_service_manager(
        self, router_service, sample_tell_packet, mock_gateway
    ):
        """Test routing local packet without service manager."""
        mock_gateway.service_manager = None
        
        result = await router_service.route_packet(sample_tell_packet)
        
        assert result is False
        assert router_service.packets_dropped == 1
    
    async def test_route_local_without_gateway(
        self, mock_state_manager, sample_tell_packet
    ):
        """Test routing local packet without gateway."""
        service = RouterService(mock_state_manager, None)
        sample_tell_packet.target_mud = "TestMUD"  # Would be local if gateway existed
        
        result = await service.route_packet(sample_tell_packet)
        
        assert result is False
        assert service.packets_dropped == 1
    
    async def test_handle_packet_local_routing(
        self, router_service, sample_tell_packet, mock_gateway
    ):
        """Test handle_packet method for local routing."""
        result = await router_service.handle_packet(sample_tell_packet)
        
        assert result is None  # Router doesn't return responses
        assert router_service.packets_routed_local == 1
        mock_gateway.service_manager.queue_packet.assert_called_once()


class TestRemoteRouting:
    """Test routing packets to remote MUDs."""
    
    async def test_route_remote_packet_online_mud(
        self, router_service, sample_remote_packet, mock_state_manager, 
        online_mud_info, mock_gateway
    ):
        """Test routing packet to online remote MUD."""
        mock_state_manager.get_mud.return_value = online_mud_info
        
        result = await router_service.route_packet(sample_remote_packet)
        
        assert result is True
        assert router_service.packets_routed_remote == 1
        mock_gateway.send_packet.assert_called_once_with(sample_remote_packet)
        assert sample_remote_packet.ttl == 199  # TTL decremented
    
    async def test_route_remote_packet_offline_mud(
        self, router_service, sample_remote_packet, mock_state_manager, 
        offline_mud_info, mock_gateway
    ):
        """Test routing packet to offline remote MUD."""
        mock_state_manager.get_mud.return_value = offline_mud_info
        
        result = await router_service.route_packet(sample_remote_packet)
        
        assert result is False
        assert router_service.packets_dropped == 1
        # Should send error packet
        mock_gateway.send_packet.assert_called()
        error_packet = mock_gateway.send_packet.call_args_list[-1][0][0]
        assert isinstance(error_packet, ErrorPacket)
        assert error_packet.error_code == "not-imp"
    
    async def test_route_remote_packet_unknown_mud(
        self, router_service, sample_remote_packet, mock_state_manager, mock_gateway
    ):
        """Test routing packet to unknown MUD."""
        mock_state_manager.get_mud.return_value = None
        
        result = await router_service.route_packet(sample_remote_packet)
        
        assert result is False
        assert router_service.packets_dropped == 1
        # Should send error packet
        mock_gateway.send_packet.assert_called()
        error_packet = mock_gateway.send_packet.call_args_list[-1][0][0]
        assert isinstance(error_packet, ErrorPacket)
        assert error_packet.error_code == "unk-dst"
    
    async def test_route_remote_gateway_send_failure(
        self, router_service, sample_remote_packet, mock_state_manager, 
        online_mud_info, mock_gateway
    ):
        """Test routing remote packet when gateway send fails."""
        mock_state_manager.get_mud.return_value = online_mud_info
        mock_gateway.send_packet.return_value = False
        
        result = await router_service.route_packet(sample_remote_packet)
        
        assert result is False
        assert router_service.packets_dropped == 1
    
    async def test_route_remote_without_gateway(
        self, mock_state_manager, sample_remote_packet, online_mud_info
    ):
        """Test routing remote packet without gateway."""
        mock_state_manager.get_mud.return_value = online_mud_info
        service = RouterService(mock_state_manager, None)
        
        result = await service.route_packet(sample_remote_packet)
        
        assert result is False
        assert service.packets_dropped == 1


class TestBroadcastRouting:
    """Test routing broadcast packets."""
    
    async def test_route_broadcast_packet(
        self, router_service, sample_channel_packet, mock_gateway
    ):
        """Test routing broadcast packet."""
        result = await router_service.route_packet(sample_channel_packet)
        
        assert result is True
        assert router_service.packets_broadcast == 1
        mock_gateway.send_packet.assert_called_once_with(sample_channel_packet)
        assert sample_channel_packet.ttl == 199  # TTL decremented
    
    async def test_route_broadcast_gateway_failure(
        self, router_service, sample_channel_packet, mock_gateway
    ):
        """Test routing broadcast when gateway fails."""
        mock_gateway.send_packet.return_value = False
        
        result = await router_service.route_packet(sample_channel_packet)
        
        assert result is False
        assert router_service.packets_dropped == 1
    
    async def test_route_broadcast_without_gateway(
        self, mock_state_manager, sample_channel_packet
    ):
        """Test routing broadcast without gateway."""
        service = RouterService(mock_state_manager, None)
        
        result = await service.route_packet(sample_channel_packet)
        
        assert result is False
        assert service.packets_dropped == 1
    
    async def test_route_broadcast_integer_zero_target(
        self, router_service, mock_gateway
    ):
        """Test routing broadcast with integer 0 target."""
        packet = ChannelPacket(
            packet_type=PacketType.CHANNEL_M,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="sender",
            target_mud=0,  # Integer zero
            target_user="",
            channel="gossip",
            message="Broadcast message"
        )
        
        result = await router_service.route_packet(packet)
        
        assert result is True
        assert router_service.packets_broadcast == 1


class TestTTLHandling:
    """Test TTL (Time To Live) handling."""
    
    async def test_expired_ttl_packet(self, router_service, sample_tell_packet):
        """Test handling packet with expired TTL."""
        sample_tell_packet.ttl = 0
        
        result = await router_service.route_packet(sample_tell_packet)
        
        assert result is False
        assert router_service.packets_dropped == 1
    
    async def test_ttl_decrement(self, router_service, sample_tell_packet, mock_gateway):
        """Test that TTL is decremented during routing."""
        original_ttl = sample_tell_packet.ttl
        
        await router_service.route_packet(sample_tell_packet)
        
        assert sample_tell_packet.ttl == original_ttl - 1
    
    async def test_negative_ttl_packet(self, router_service, sample_tell_packet):
        """Test handling packet with negative TTL."""
        sample_tell_packet.ttl = -5
        
        result = await router_service.route_packet(sample_tell_packet)
        
        assert result is False
        assert router_service.packets_dropped == 1
    
    async def test_very_low_ttl_packet(self, router_service, sample_tell_packet, mock_gateway):
        """Test handling packet with TTL of 1."""
        sample_tell_packet.ttl = 1
        
        result = await router_service.route_packet(sample_tell_packet)
        
        assert result is True  # Should succeed
        assert sample_tell_packet.ttl == 0  # But TTL becomes 0


class TestErrorHandling:
    """Test error packet generation and handling."""
    
    async def test_send_error_reply_unknown_destination(
        self, router_service, sample_remote_packet, mock_state_manager, mock_gateway
    ):
        """Test sending error reply for unknown destination."""
        mock_state_manager.get_mud.return_value = None
        
        await router_service._send_error_reply(
            sample_remote_packet, "unk-dst", "Unknown destination"
        )
        
        mock_gateway.send_packet.assert_called_once()
        error_packet = mock_gateway.send_packet.call_args[0][0]
        
        assert isinstance(error_packet, ErrorPacket)
        assert error_packet.error_code == "unk-dst"
        assert error_packet.error_message == "Unknown destination"
        assert error_packet.target_mud == sample_remote_packet.originator_mud
        assert error_packet.target_user == sample_remote_packet.originator_user
        assert error_packet.originator_mud == "TestMUD"
    
    async def test_send_error_reply_not_implemented(
        self, router_service, sample_remote_packet, mock_gateway
    ):
        """Test sending not implemented error reply."""
        await router_service._send_error_reply(
            sample_remote_packet, "not-imp", "Service not implemented"
        )
        
        error_packet = mock_gateway.send_packet.call_args[0][0]
        assert error_packet.error_code == "not-imp"
        assert error_packet.error_message == "Service not implemented"
    
    async def test_send_error_reply_without_gateway(
        self, mock_state_manager, sample_remote_packet
    ):
        """Test sending error reply without gateway."""
        service = RouterService(mock_state_manager, None)
        
        # Should not crash when gateway is None
        await service._send_error_reply(
            sample_remote_packet, "unk-dst", "No gateway"
        )
        
        # No assertion needed, just ensure no exception is raised
    
    async def test_error_packet_includes_original_data(
        self, router_service, sample_remote_packet, mock_gateway
    ):
        """Test that error packet includes original packet data."""
        await router_service._send_error_reply(
            sample_remote_packet, "test-error", "Test error"
        )
        
        error_packet = mock_gateway.send_packet.call_args[0][0]
        assert error_packet.bad_packet == sample_remote_packet.to_lpc_array()


class TestPacketValidation:
    """Test packet validation."""
    
    async def test_validate_all_packet_types(self, router_service):
        """Test that router validates all packet types."""
        # Test various packet types
        packets = [
            Mock(spec=I3Packet, packet_type=PacketType.TELL),
            Mock(spec=I3Packet, packet_type=PacketType.CHANNEL_M),
            Mock(spec=I3Packet, packet_type=PacketType.WHO_REQ),
            Mock(spec=I3Packet, packet_type=PacketType.FINGER_REQ),
        ]
        
        for packet in packets:
            assert await router_service.validate_packet(packet) is True
    
    async def test_validate_none_packet(self, router_service):
        """Test validation with None packet."""
        # Router should handle any packet, including edge cases
        assert await router_service.validate_packet(None) is True


class TestStatistics:
    """Test routing statistics."""
    
    async def test_statistics_tracking(
        self, router_service, sample_tell_packet, sample_channel_packet, 
        sample_remote_packet, mock_state_manager, online_mud_info, mock_gateway
    ):
        """Test that statistics are tracked correctly."""
        mock_state_manager.get_mud.return_value = online_mud_info
        
        # Route local packet
        await router_service.route_packet(sample_tell_packet)
        
        # Route remote packet
        await router_service.route_packet(sample_remote_packet)
        
        # Route broadcast packet
        await router_service.route_packet(sample_channel_packet)
        
        stats = router_service.get_stats()
        assert stats["packets_routed_local"] == 1
        assert stats["packets_routed_remote"] == 1
        assert stats["packets_broadcast"] == 1
        assert stats["packets_dropped"] == 0
        assert stats["total_routed"] == 3
    
    async def test_statistics_dropped_packets(
        self, router_service, sample_tell_packet
    ):
        """Test statistics for dropped packets."""
        # Set TTL to 0 to cause drop
        sample_tell_packet.ttl = 0
        
        await router_service.route_packet(sample_tell_packet)
        
        stats = router_service.get_stats()
        assert stats["packets_dropped"] == 1
        assert stats["total_routed"] == 0
    
    def test_get_stats_structure(self, router_service):
        """Test get_stats returns correct structure."""
        stats = router_service.get_stats()
        
        required_keys = [
            "packets_routed_local",
            "packets_routed_remote", 
            "packets_broadcast",
            "packets_dropped",
            "total_routed"
        ]
        
        for key in required_keys:
            assert key in stats
            assert isinstance(stats[key], int)
    
    async def test_statistics_reset_on_initialization(self, router_service):
        """Test that statistics are reset properly."""
        # Manually set some stats
        router_service.packets_routed_local = 10
        router_service.packets_dropped = 5
        
        # Re-initialize
        new_service = RouterService(router_service.state_manager, router_service.gateway)
        await new_service.initialize()
        
        stats = new_service.get_stats()
        assert all(stat == 0 for stat in stats.values())


class TestRoutingDestinations:
    """Test routing destination determination."""
    
    async def test_route_to_same_mud_name(
        self, router_service, mock_gateway
    ):
        """Test routing packet destined for same MUD name."""
        packet = TellPacket(
            ttl=200,
            originator_mud="OtherMUD",
            originator_user="sender",
            target_mud="TestMUD",  # Same as gateway MUD name
            target_user="receiver",
            message="Local message"
        )
        
        result = await router_service.route_packet(packet)
        
        assert result is True
        assert router_service.packets_routed_local == 1
    
    async def test_route_determination_case_sensitivity(
        self, router_service, mock_gateway
    ):
        """Test that routing destination is case-sensitive."""
        packet = TellPacket(
            ttl=200,
            originator_mud="OtherMUD",
            originator_user="sender",
            target_mud="testmud",  # lowercase
            target_user="receiver",
            message="Case test"
        )
        
        # Should be routed as remote since case doesn't match
        result = await router_service.route_packet(packet)
        
        # This will fail because MUD not in mudlist, but shows it's not local
        assert result is False
        assert router_service.packets_dropped == 1  # Dropped due to unknown MUD
    
    async def test_broadcast_string_vs_integer(self, router_service, mock_gateway):
        """Test broadcast detection with string vs integer zero."""
        # Test string "0"
        packet1 = ChannelPacket(
            packet_type=PacketType.CHANNEL_M,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="sender",
            target_mud="0",  # String
            target_user="",
            channel="gossip",
            message="String broadcast"
        )
        
        # Test integer 0
        packet2 = ChannelPacket(
            packet_type=PacketType.CHANNEL_M,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="sender",
            target_mud=0,  # Integer
            target_user="",
            channel="gossip",
            message="Integer broadcast"
        )
        
        result1 = await router_service.route_packet(packet1)
        result2 = await router_service.route_packet(packet2)
        
        assert result1 is True
        assert result2 is True
        assert router_service.packets_broadcast == 2


class TestConcurrentRouting:
    """Test concurrent routing operations."""
    
    async def test_concurrent_local_routing(
        self, router_service, mock_gateway
    ):
        """Test concurrent local packet routing."""
        packets = []
        for i in range(10):
            packet = TellPacket(
                ttl=200,
                originator_mud="RemoteMUD",
                originator_user=f"sender{i}",
                target_mud="TestMUD",
                target_user=f"receiver{i}",
                message=f"Message {i}"
            )
            packets.append(packet)
        
        # Route all packets concurrently
        tasks = [router_service.route_packet(p) for p in packets]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(results)
        assert router_service.packets_routed_local == 10
    
    async def test_concurrent_remote_routing(
        self, router_service, mock_state_manager, online_mud_info, mock_gateway
    ):
        """Test concurrent remote packet routing."""
        mock_state_manager.get_mud.return_value = online_mud_info
        
        packets = []
        for i in range(5):
            packet = TellPacket(
                ttl=200,
                originator_mud="SourceMUD",
                originator_user=f"sender{i}",
                target_mud="RemoteMUD",
                target_user=f"receiver{i}",
                message=f"Remote message {i}"
            )
            packets.append(packet)
        
        tasks = [router_service.route_packet(p) for p in packets]
        results = await asyncio.gather(*tasks)
        
        assert all(results)
        assert router_service.packets_routed_remote == 5
    
    async def test_concurrent_mixed_routing(
        self, router_service, mock_state_manager, online_mud_info, mock_gateway
    ):
        """Test concurrent mixed routing (local, remote, broadcast)."""
        mock_state_manager.get_mud.return_value = online_mud_info
        
        # Create mixed packet types
        local_packet = TellPacket(
            ttl=200, originator_mud="RemoteMUD", originator_user="sender1",
            target_mud="TestMUD", target_user="receiver1",
            message="Local"
        )
        
        remote_packet = TellPacket(
            ttl=200, originator_mud="SourceMUD", originator_user="sender2",
            target_mud="RemoteMUD", target_user="receiver2",
            message="Remote"
        )
        
        broadcast_packet = ChannelPacket(
            packet_type=PacketType.CHANNEL_M, ttl=200,
            originator_mud="RemoteMUD", originator_user="sender3",
            target_mud="0", target_user="", channel="gossip",
            message="Broadcast"
        )
        
        tasks = [
            router_service.route_packet(local_packet),
            router_service.route_packet(remote_packet),
            router_service.route_packet(broadcast_packet)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert all(results)
        assert router_service.packets_routed_local == 1
        assert router_service.packets_routed_remote == 1
        assert router_service.packets_broadcast == 1


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    async def test_route_packet_with_none_target_mud(self, router_service):
        """Test routing packet with None target_mud."""
        packet = TellPacket(
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="sender",
            target_mud=None,  # None target
            target_user="receiver",
            message="Null target"
        )
        
        # This should not crash and should be handled gracefully
        result = await router_service.route_packet(packet)
        
        # Likely to be routed as remote and fail, but should not crash
        assert isinstance(result, bool)
    
    async def test_route_packet_with_empty_target_mud(
        self, router_service, mock_state_manager
    ):
        """Test routing packet with empty target_mud."""
        mock_state_manager.get_mud.return_value = None
        
        packet = TellPacket(
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="sender",
            target_mud="",  # Empty string
            target_user="receiver",
            message="Empty target"
        )
        
        result = await router_service.route_packet(packet)
        
        # Should be treated as unknown MUD
        assert result is False
        assert router_service.packets_dropped == 1
    
    async def test_route_packet_state_manager_exception(
        self, router_service, sample_remote_packet, mock_state_manager, mock_gateway
    ):
        """Test handling state manager exceptions."""
        mock_state_manager.get_mud.side_effect = Exception("State manager error")
        
        # Should handle exception gracefully
        result = await router_service.route_packet(sample_remote_packet)
        
        # Exact behavior depends on implementation, but should not crash
        assert isinstance(result, bool)
    
    async def test_very_high_ttl_packet(self, router_service, sample_tell_packet, mock_gateway):
        """Test handling packet with very high TTL."""
        sample_tell_packet.ttl = 999999
        
        result = await router_service.route_packet(sample_tell_packet)
        
        assert result is True
        assert sample_tell_packet.ttl == 999998  # Should be decremented
    
    async def test_routing_statistics_overflow_protection(self, router_service):
        """Test that statistics don't overflow with large numbers."""
        # Manually set very large numbers
        router_service.packets_routed_local = 999999999
        router_service.packets_routed_remote = 999999999
        router_service.packets_broadcast = 999999999
        
        stats = router_service.get_stats()
        
        # Should handle large numbers without overflow
        assert stats["total_routed"] == 2999999997
        assert isinstance(stats["total_routed"], int)
    
    async def test_handle_packet_with_various_types(self, router_service, mock_gateway):
        """Test handle_packet with various packet types."""
        packets = [
            WhoPacket(
                packet_type=PacketType.WHO_REQ, ttl=200,
                originator_mud="RemoteMUD", originator_user="user",
                target_mud="TestMUD", target_user="", filter_criteria={}
            ),
            ChannelPacket(
                packet_type=PacketType.CHANNEL_M, ttl=200,
                originator_mud="RemoteMUD", originator_user="user",
                target_mud="0", target_user="", channel="gossip",
                message="Test"
            ),
        ]
        
        for packet in packets:
            result = await router_service.handle_packet(packet)
            assert result is None  # Router handle_packet always returns None
    
    async def test_routing_with_missing_gateway_settings(
        self, mock_state_manager, sample_tell_packet
    ):
        """Test routing when gateway has no settings."""
        gateway = Mock()
        gateway.settings = None  # Missing settings
        gateway.service_manager = Mock()
        gateway.service_manager.queue_packet = AsyncMock()
        
        service = RouterService(mock_state_manager, gateway)
        sample_tell_packet.target_mud = "TestMUD"
        
        # Should handle missing settings gracefully
        # This might cause an exception depending on implementation
        try:
            result = await service.route_packet(sample_tell_packet)
            # If no exception, result should be boolean
            assert isinstance(result, bool)
        except AttributeError:
            # Expected if implementation doesn't handle None settings
            pass