"""Integration tests for I3 Gateway.

These tests verify the complete gateway functionality including
connection establishment, packet routing, and service handling.
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.gateway import I3Gateway
from src.config.models import Settings, MudConfig, RouterConfig, RouterEndpoint, ServicesConfig
from src.models.packet import (
    PacketType, TellPacket, WhoPacket, LocatePacket,
    ChannelMessagePacket, StartupPacket
)
from src.network.connection import ConnectionState
from tests.fixtures.mock_router import MockRouter


@pytest.fixture
async def mock_router():
    """Create and start a mock router."""
    router = MockRouter(port=8091)
    await router.start()
    yield router
    await router.stop()


@pytest.fixture
def gateway_settings():
    """Create test gateway settings."""
    return Settings(
        mud=MudConfig(
            name="TestGatewayMUD",
            port=4000,
            password=0
        ),
        router=RouterConfig(
            primary=RouterEndpoint(
                name="*test",
                host="127.0.0.1",
                port=8091
            )
        ),
        gateway={
            "host": "127.0.0.1",
            "port": 8080,
            "state_dir": None
        },
        services=ServicesConfig(
            tell=True,
            channel=True,
            who=True,
            finger=True,
            locate=True
        )
    )


@pytest.fixture
async def gateway(gateway_settings):
    """Create and start a gateway instance."""
    gw = I3Gateway(gateway_settings)
    await gw.start()
    yield gw
    await gw.shutdown()


class TestGatewayConnection:
    """Test gateway connection establishment."""
    
    async def test_connect_to_router(self, gateway, mock_router):
        """Test that gateway can connect to router."""
        # Wait for connection
        await asyncio.sleep(0.5)
        
        # Check connection state
        assert gateway.connection_manager.is_connected()
        assert gateway.connection_manager.state in (
            ConnectionState.CONNECTED,
            ConnectionState.READY
        )
    
    async def test_startup_handshake(self, gateway, mock_router):
        """Test startup packet exchange."""
        # Wait for handshake
        await asyncio.sleep(1.0)
        
        # Check that router received startup
        assert "TestGatewayMUD" in mock_router.connected_muds
        
        # Check that gateway is ready
        assert gateway.connection_manager.state == ConnectionState.READY
    
    async def test_mudlist_sync(self, gateway, mock_router):
        """Test mudlist synchronization."""
        # Wait for mudlist sync
        await asyncio.sleep(1.0)
        
        # Check mudlist was updated
        assert len(gateway.state_manager.mudlist) > 0
        assert "TestMUD" in gateway.state_manager.mudlist
    
    async def test_reconnection(self, gateway, mock_router):
        """Test automatic reconnection."""
        # Wait for initial connection
        await asyncio.sleep(0.5)
        assert gateway.connection_manager.is_connected()
        
        # Simulate disconnect
        await gateway.connection_manager.disconnect()
        assert not gateway.connection_manager.is_connected()
        
        # Should reconnect automatically
        await asyncio.sleep(6.0)  # Wait for backoff
        assert gateway.connection_manager.is_connected()


class TestPacketRouting:
    """Test packet routing functionality."""
    
    async def test_route_local_packet(self, gateway):
        """Test routing packet to local service."""
        # Create a tell packet targeted at this MUD
        packet = TellPacket(
            ttl=200,
            originator_mud="OtherMUD",
            originator_user="TestUser",
            target_mud="TestGatewayMUD",
            target_user="LocalUser",
            visname="TestUser",
            message="Hello!"
        )
        
        # Route packet
        routed = await gateway.router_service.route_packet(packet)
        assert routed
        assert gateway.router_service.packets_routed_local > 0
    
    async def test_route_remote_packet(self, gateway, mock_router):
        """Test routing packet to remote MUD."""
        # Wait for connection
        await asyncio.sleep(1.0)
        
        # Create a tell packet for remote MUD
        packet = TellPacket(
            ttl=200,
            originator_mud="TestGatewayMUD",
            originator_user="LocalUser",
            target_mud="TestMUD",
            target_user="RemoteUser",
            visname="LocalUser",
            message="Hello remote!"
        )
        
        # Route packet
        routed = await gateway.router_service.route_packet(packet)
        assert routed
        assert gateway.router_service.packets_routed_remote > 0
    
    async def test_ttl_expiry(self, gateway):
        """Test that packets with expired TTL are dropped."""
        packet = TellPacket(
            ttl=0,
            originator_mud="OtherMUD",
            originator_user="TestUser",
            target_mud="TestGatewayMUD",
            target_user="LocalUser",
            visname="TestUser",
            message="This should be dropped"
        )
        
        routed = await gateway.router_service.route_packet(packet)
        assert not routed
        assert gateway.router_service.packets_dropped > 0
    
    async def test_unknown_mud_error(self, gateway):
        """Test error handling for unknown MUD."""
        packet = TellPacket(
            ttl=200,
            originator_mud="TestGatewayMUD",
            originator_user="LocalUser",
            target_mud="UnknownMUD",
            target_user="Someone",
            visname="LocalUser",
            message="This should fail"
        )
        
        routed = await gateway.router_service.route_packet(packet)
        assert not routed
        assert gateway.router_service.packets_dropped > 0


class TestServices:
    """Test individual I3 services."""
    
    async def test_tell_service(self, gateway):
        """Test tell service message handling."""
        # Register tell service
        from src.services.tell import TellService
        tell_service = TellService(gateway.state_manager, gateway)
        await tell_service.initialize()
        
        # Create mock session for target user
        await gateway.state_manager.create_session("TestGatewayMUD", "LocalUser")
        
        # Handle tell packet
        packet = TellPacket(
            ttl=200,
            originator_mud="OtherMUD",
            originator_user="Sender",
            target_mud="TestGatewayMUD",
            target_user="LocalUser",
            visname="Sender",
            message="Test message"
        )
        
        response = await tell_service.handle_packet(packet)
        assert response is None  # Successful delivery returns None
        assert tell_service.metrics.packets_handled == 1
    
    async def test_channel_service(self, gateway):
        """Test channel service message handling."""
        # Register channel service
        from src.services.channel import ChannelService
        channel_service = ChannelService(gateway.state_manager, gateway)
        await channel_service.initialize()
        
        # Handle channel message
        packet = ChannelMessagePacket(
            ttl=200,
            originator_mud="OtherMUD",
            originator_user="Sender",
            target_mud="0",  # Broadcast
            target_user="",
            channel="imud_gossip",
            visname="Sender",
            message="Hello channel!"
        )
        
        response = await channel_service.handle_packet(packet)
        assert response is None  # Channel messages don't return responses
        
        # Check message in history
        history = channel_service.get_channel_history("imud_gossip", 1)
        assert len(history) == 1
        assert history[0]["message"] == "Hello channel!"
    
    async def test_who_service(self, gateway):
        """Test who service request handling."""
        # Register who service
        from src.services.who import WhoService
        who_service = WhoService(gateway.state_manager, gateway)
        await who_service.initialize()
        
        # Create mock sessions
        await gateway.state_manager.create_session("TestGatewayMUD", "Player1")
        await gateway.state_manager.create_session("TestGatewayMUD", "Player2")
        
        # Handle who request
        packet = WhoPacket(
            packet_type=PacketType.WHO_REQ,
            ttl=200,
            originator_mud="OtherMUD",
            originator_user="Requester",
            target_mud="TestGatewayMUD",
            target_user="",
            filter_criteria=None
        )
        
        response = await who_service.handle_packet(packet)
        assert response is not None
        assert response.packet_type == PacketType.WHO_REPLY
        assert len(response.who_data) == 2
    
    async def test_locate_service(self, gateway):
        """Test locate service user search."""
        # Register locate service
        from src.services.locate import LocateService
        locate_service = LocateService(gateway.state_manager, gateway)
        await locate_service.initialize()
        
        # Create mock session
        session = await gateway.state_manager.create_session("TestGatewayMUD", "FindMe")
        session.is_online = True
        
        # Handle locate request
        packet = LocatePacket(
            packet_type=PacketType.LOCATE_REQ,
            ttl=200,
            originator_mud="OtherMUD",
            originator_user="Searcher",
            target_mud="TestGatewayMUD",
            target_user="",
            user_to_locate="FindMe"
        )
        
        response = await locate_service.handle_packet(packet)
        assert response is not None
        assert response.packet_type == PacketType.LOCATE_REPLY
        assert response.located_mud == "TestGatewayMUD"
        assert response.located_user == "FindMe"


class TestPerformance:
    """Test gateway performance metrics."""
    
    async def test_message_throughput(self, gateway):
        """Test message processing throughput."""
        # Send many packets rapidly
        packets_sent = 0
        start_time = asyncio.get_event_loop().time()
        
        for i in range(100):
            packet = TellPacket(
                ttl=200,
                originator_mud=f"MUD{i}",
                originator_user=f"User{i}",
                target_mud="TestGatewayMUD",
                target_user="Target",
                visname=f"User{i}",
                message=f"Message {i}"
            )
            
            await gateway.packet_queue.put(packet)
            packets_sent += 1
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        elapsed = asyncio.get_event_loop().time() - start_time
        throughput = packets_sent / elapsed
        
        # Should handle at least 100 msgs/sec
        assert throughput >= 100
    
    async def test_latency(self, gateway):
        """Test packet processing latency."""
        # Measure round-trip time for a packet
        start_time = asyncio.get_event_loop().time()
        
        packet = WhoPacket(
            packet_type=PacketType.WHO_REQ,
            ttl=200,
            originator_mud="TestMUD",
            originator_user="",
            target_mud="TestGatewayMUD",
            target_user="",
            filter_criteria=None
        )
        
        # Process packet
        await gateway.packet_queue.put(packet)
        await asyncio.sleep(0.1)  # Wait for processing
        
        latency = (asyncio.get_event_loop().time() - start_time) * 1000
        
        # Should be under 100ms
        assert latency < 100
    
    async def test_concurrent_connections(self, gateway):
        """Test handling multiple concurrent operations."""
        tasks = []
        
        # Create multiple concurrent operations
        for i in range(10):
            packet = TellPacket(
                ttl=200,
                originator_mud=f"MUD{i}",
                originator_user=f"User{i}",
                target_mud="TestGatewayMUD",
                target_user=f"Target{i}",
                visname=f"User{i}",
                message=f"Concurrent message {i}"
            )
            
            task = asyncio.create_task(gateway.send_packet(packet))
            tasks.append(task)
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(results)


@pytest.mark.asyncio
async def test_full_integration(gateway_settings):
    """Test complete gateway integration with mock router."""
    # Start mock router
    router = MockRouter(port=8092)
    await router.start()
    
    # Update settings for this router
    gateway_settings.router.primary.port = 8092
    
    # Start gateway
    gateway = I3Gateway(gateway_settings)
    await gateway.start()
    
    try:
        # Wait for connection
        await asyncio.sleep(1.0)
        
        # Verify connection established
        assert gateway.connection_manager.is_connected()
        assert "TestGatewayMUD" in router.connected_muds
        
        # Send a tell through the gateway
        from src.services.tell import TellService
        tell_service = TellService(gateway.state_manager, gateway)
        await tell_service.initialize()
        
        success = await tell_service.send_tell(
            from_user="LocalUser",
            to_user="RemoteUser",
            to_mud="TestMUD",
            message="Integration test message"
        )
        
        assert success
        
        # Check gateway statistics
        stats = gateway.get_stats()
        assert stats["running"]
        assert stats["connected"]
        assert stats["connection"]["packets_sent"] > 0
        
    finally:
        await gateway.shutdown()
        await router.stop()