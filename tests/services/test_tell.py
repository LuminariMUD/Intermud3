"""Comprehensive unit tests for TellService."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Optional

from src.services.tell import TellService
from src.models.packet import (
    TellPacket, EmotetoPacket, ErrorPacket, 
    PacketType, I3Packet
)
from src.state.manager import StateManager
from src.models.connection import UserSession


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager."""
    manager = Mock(spec=StateManager)
    manager.get_session = AsyncMock()
    return manager


@pytest.fixture
def mock_gateway():
    """Create a mock gateway."""
    gateway = Mock()
    gateway.settings = Mock()
    gateway.settings.mud = Mock()
    gateway.settings.mud.name = "TestMUD"
    gateway.send_packet = AsyncMock(return_value=True)
    return gateway


@pytest.fixture
def tell_service(mock_state_manager, mock_gateway):
    """Create a TellService instance for testing."""
    service = TellService(mock_state_manager, mock_gateway)
    return service


@pytest.fixture
def sample_tell_packet():
    """Create a sample tell packet."""
    return TellPacket(
        ttl=200,
        originator_mud="RemoteMUD",
        originator_user="sender",
        target_mud="TestMUD",
        target_user="receiver",
        message="Hello there!"
    )


@pytest.fixture
def sample_emoteto_packet():
    """Create a sample emoteto packet."""
    return EmotetoPacket(
        ttl=200,
        originator_mud="RemoteMUD",
        originator_user="sender",
        target_mud="TestMUD",
        target_user="receiver",
        message="waves happily."
    )


@pytest.fixture
def online_user_session():
    """Create an online user session."""
    session = Mock(spec=UserSession)
    session.is_online = True
    session.username = "receiver"
    return session


@pytest.fixture
def offline_user_session():
    """Create an offline user session."""
    session = Mock(spec=UserSession)
    session.is_online = False
    session.username = "receiver"
    return session


class TestTellServiceInitialization:
    """Test TellService initialization."""
    
    async def test_initialization(self, tell_service):
        """Test service initialization."""
        await tell_service.initialize()
        assert tell_service.service_name == "tell"
        assert PacketType.TELL in tell_service.supported_packets
        assert PacketType.EMOTETO in tell_service.supported_packets
        assert not tell_service.requires_auth
        assert tell_service.recent_tells == {}
        assert tell_service.tell_history == {}
    
    async def test_initialization_without_gateway(self, mock_state_manager):
        """Test service initialization without gateway."""
        service = TellService(mock_state_manager, None)
        await service.initialize()
        assert service.gateway is None


class TestTellPacketHandling:
    """Test handling of tell packets."""
    
    async def test_handle_tell_online_user(
        self, tell_service, sample_tell_packet, 
        mock_state_manager, online_user_session
    ):
        """Test handling tell to online user."""
        mock_state_manager.get_session.return_value = online_user_session
        
        result = await tell_service.handle_packet(sample_tell_packet)
        
        assert result is None  # No error
        assert tell_service.recent_tells["receiver"] == "RemoteMUD:sender"
        assert len(tell_service.tell_history["receiver"]) == 1
        assert tell_service.tell_history["receiver"][0]["message"] == "Hello there!"
        assert tell_service.metrics.packets_handled == 1
    
    async def test_handle_tell_offline_user(
        self, tell_service, sample_tell_packet,
        mock_state_manager, offline_user_session
    ):
        """Test handling tell to offline user."""
        mock_state_manager.get_session.return_value = offline_user_session
        
        result = await tell_service.handle_packet(sample_tell_packet)
        
        assert isinstance(result, ErrorPacket)
        assert result.error_code == "unk-user"
        assert "not online" in result.error_message
        assert result.target_mud == "RemoteMUD"
        assert result.target_user == "sender"
    
    async def test_handle_tell_nonexistent_user(
        self, tell_service, sample_tell_packet, mock_state_manager
    ):
        """Test handling tell to nonexistent user."""
        mock_state_manager.get_session.return_value = None
        
        result = await tell_service.handle_packet(sample_tell_packet)
        
        assert isinstance(result, ErrorPacket)
        assert result.error_code == "unk-user"
    
    async def test_tell_history_management(
        self, tell_service, mock_state_manager, online_user_session
    ):
        """Test tell history is properly managed."""
        mock_state_manager.get_session.return_value = online_user_session
        
        # Send 25 tells to test history limit
        for i in range(25):
            packet = TellPacket(
                ttl=200,
                originator_mud="RemoteMUD",
                originator_user=f"sender{i}",
                target_mud="TestMUD",
                target_user="receiver",
                message=f"Message {i}"
            )
            await tell_service.handle_packet(packet)
        
        # History should be limited to 20 messages
        assert len(tell_service.tell_history["receiver"]) == 20
        # First 5 messages should have been removed
        assert tell_service.tell_history["receiver"][0]["message"] == "Message 5"
        assert tell_service.tell_history["receiver"][-1]["message"] == "Message 24"
    
    async def test_tell_updates_recent_tells(
        self, tell_service, mock_state_manager, online_user_session
    ):
        """Test that recent tells are properly updated."""
        mock_state_manager.get_session.return_value = online_user_session
        
        # Send tells from different users
        packet1 = TellPacket(
            ttl=200,
            originator_mud="MUD1",
            originator_user="user1",
            target_mud="TestMUD",
            target_user="receiver",
            message="First message"
        )
        packet2 = TellPacket(
            ttl=200,
            originator_mud="MUD2",
            originator_user="user2",
            target_mud="TestMUD",
            target_user="receiver",
            message="Second message"
        )
        
        await tell_service.handle_packet(packet1)
        assert tell_service.recent_tells["receiver"] == "MUD1:user1"
        
        await tell_service.handle_packet(packet2)
        assert tell_service.recent_tells["receiver"] == "MUD2:user2"


class TestEmotetoPacketHandling:
    """Test handling of emoteto packets."""
    
    async def test_handle_emoteto_online_user(
        self, tell_service, sample_emoteto_packet,
        mock_state_manager, online_user_session
    ):
        """Test handling emoteto to online user."""
        mock_state_manager.get_session.return_value = online_user_session
        
        result = await tell_service.handle_packet(sample_emoteto_packet)
        
        assert result is None  # No error
        assert tell_service.recent_tells["receiver"] == "RemoteMUD:sender"
        assert tell_service.metrics.packets_handled == 1
    
    async def test_handle_emoteto_offline_user(
        self, tell_service, sample_emoteto_packet,
        mock_state_manager, offline_user_session
    ):
        """Test handling emoteto to offline user."""
        mock_state_manager.get_session.return_value = offline_user_session
        
        result = await tell_service.handle_packet(sample_emoteto_packet)
        
        assert isinstance(result, ErrorPacket)
        assert result.error_code == "unk-user"
        assert "not online" in result.error_message
    
    async def test_emoteto_updates_recent_tells(
        self, tell_service, sample_emoteto_packet,
        mock_state_manager, online_user_session
    ):
        """Test that emoteto updates recent tells."""
        mock_state_manager.get_session.return_value = online_user_session
        
        await tell_service.handle_packet(sample_emoteto_packet)
        
        assert tell_service.recent_tells["receiver"] == "RemoteMUD:sender"


class TestPacketValidation:
    """Test packet validation."""
    
    async def test_validate_valid_tell_packet(self, tell_service, sample_tell_packet):
        """Test validation of valid tell packet."""
        assert await tell_service.validate_packet(sample_tell_packet) is True
    
    async def test_validate_valid_emoteto_packet(self, tell_service, sample_emoteto_packet):
        """Test validation of valid emoteto packet."""
        assert await tell_service.validate_packet(sample_emoteto_packet) is True
    
    async def test_validate_unsupported_packet_type(self, tell_service):
        """Test validation rejects unsupported packet types."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANLIST_REPLY
        
        assert await tell_service.validate_packet(packet) is False
    
    async def test_validate_tell_missing_originator(self, tell_service):
        """Test validation rejects tell without originator user."""
        packet = TellPacket(
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="",  # Empty
            target_mud="TestMUD",
            target_user="receiver",
            message="Hello"
        )
        
        assert await tell_service.validate_packet(packet) is False
    
    async def test_validate_tell_missing_target(self, tell_service):
        """Test validation rejects tell without target user."""
        packet = TellPacket(
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="sender",
            target_mud="TestMUD",
            target_user="",  # Empty
            message="Hello"
        )
        
        assert await tell_service.validate_packet(packet) is False
    
    async def test_validate_tell_empty_message(self, tell_service):
        """Test validation rejects tell with empty message."""
        packet = TellPacket(
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="sender",
            target_mud="TestMUD",
            target_user="receiver",
            message=""  # Empty
        )
        
        assert await tell_service.validate_packet(packet) is False
    
    async def test_validate_emoteto_empty_message(self, tell_service):
        """Test validation rejects emoteto with empty message."""
        packet = EmotetoPacket(
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="sender",
            target_mud="TestMUD",
            target_user="receiver",
            message=""  # Empty
        )
        
        assert await tell_service.validate_packet(packet) is False
    
    async def test_validate_wrong_packet_class(self, tell_service):
        """Test validation rejects wrong packet class."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.TELL
        packet.originator_user = "sender"
        packet.target_user = "receiver"
        
        # Not actually a TellPacket instance
        assert await tell_service.validate_packet(packet) is False


class TestSendingMessages:
    """Test sending tell and emoteto messages."""
    
    async def test_send_tell_success(self, tell_service, mock_gateway):
        """Test successful tell sending."""
        result = await tell_service.send_tell(
            from_user="alice",
            to_user="bob",
            to_mud="RemoteMUD",
            message="Hello Bob!",
        )
        
        assert result is True
        mock_gateway.send_packet.assert_called_once()
        
        sent_packet = mock_gateway.send_packet.call_args[0][0]
        assert isinstance(sent_packet, TellPacket)
        assert sent_packet.originator_user == "alice"
        assert sent_packet.target_user == "bob"
        assert sent_packet.target_mud == "RemoteMUD"
        assert sent_packet.message == "Hello Bob!"
        assert sent_packet.visname == "Alice"
    
    async def test_send_tell_without_visname(self, tell_service, mock_gateway):
        """Test sending tell without visname uses username."""
        result = await tell_service.send_tell(
            from_user="alice",
            to_user="bob",
            to_mud="RemoteMUD",
            message="Hello Bob!"
        )
        
        assert result is True
        sent_packet = mock_gateway.send_packet.call_args[0][0]
        assert sent_packet.visname == "alice"  # Defaults to from_user
    
    async def test_send_tell_gateway_failure(self, tell_service, mock_gateway):
        """Test tell sending when gateway fails."""
        mock_gateway.send_packet.return_value = False
        
        result = await tell_service.send_tell(
            from_user="alice",
            to_user="bob",
            to_mud="RemoteMUD",
            message="Hello Bob!"
        )
        
        assert result is False
    
    async def test_send_tell_no_gateway(self, mock_state_manager):
        """Test tell sending without gateway."""
        service = TellService(mock_state_manager, None)
        
        result = await service.send_tell(
            from_user="alice",
            to_user="bob",
            to_mud="RemoteMUD",
            message="Hello Bob!"
        )
        
        assert result is False
    
    async def test_send_emoteto_success(self, tell_service, mock_gateway):
        """Test successful emoteto sending."""
        result = await tell_service.send_emoteto(
            from_user="alice",
            to_user="bob",
            to_mud="RemoteMUD",
            message="waves happily.",
        )
        
        assert result is True
        mock_gateway.send_packet.assert_called_once()
        
        sent_packet = mock_gateway.send_packet.call_args[0][0]
        assert isinstance(sent_packet, EmotetoPacket)
        assert sent_packet.originator_user == "alice"
        assert sent_packet.target_user == "bob"
        assert sent_packet.message == "waves happily."
    
    async def test_send_emoteto_no_gateway(self, mock_state_manager):
        """Test emoteto sending without gateway."""
        service = TellService(mock_state_manager, None)
        
        result = await service.send_emoteto(
            from_user="alice",
            to_user="bob",
            to_mud="RemoteMUD",
            message="waves."
        )
        
        assert result is False


class TestUtilityMethods:
    """Test utility methods."""
    
    async def test_get_last_tell_sender(
        self, tell_service, sample_tell_packet,
        mock_state_manager, online_user_session
    ):
        """Test getting last tell sender."""
        mock_state_manager.get_session.return_value = online_user_session
        
        # Initially no sender
        assert tell_service.get_last_tell_sender("receiver") is None
        
        # Handle a tell
        await tell_service.handle_packet(sample_tell_packet)
        
        # Now should have sender
        assert tell_service.get_last_tell_sender("receiver") == "RemoteMUD:sender"
    
    async def test_get_tell_history_empty(self, tell_service):
        """Test getting empty tell history."""
        history = tell_service.get_tell_history("unknown_user")
        assert history == []
    
    async def test_get_tell_history_with_messages(
        self, tell_service, sample_tell_packet,
        mock_state_manager, online_user_session
    ):
        """Test getting tell history with messages."""
        mock_state_manager.get_session.return_value = online_user_session
        
        # Send some tells
        for i in range(3):
            packet = TellPacket(
                ttl=200,
                originator_mud="RemoteMUD",
                originator_user=f"sender{i}",
                target_mud="TestMUD",
                target_user="receiver",
                message=f"Message {i}"
            )
            await tell_service.handle_packet(packet)
        
        history = tell_service.get_tell_history("receiver")
        assert len(history) == 3
        assert history[0]["message"] == "Message 0"
        assert history[2]["message"] == "Message 2"
        assert "timestamp" in history[0]


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    async def test_handle_invalid_packet_type(self, tell_service):
        """Test handling unsupported packet type."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_M  # Not supported
        
        result = await tell_service.handle_packet(packet)
        assert result is None
    
    async def test_concurrent_tells_to_same_user(
        self, tell_service, mock_state_manager, online_user_session
    ):
        """Test handling concurrent tells to same user."""
        mock_state_manager.get_session.return_value = online_user_session
        
        # Create multiple tell packets
        packets = []
        for i in range(10):
            packet = TellPacket(
                ttl=200,
                originator_mud="RemoteMUD",
                originator_user=f"sender{i}",
                target_mud="TestMUD",
                target_user="receiver",
                message=f"Concurrent message {i}"
            )
            packets.append(packet)
        
        # Handle them concurrently
        tasks = [tell_service.handle_packet(p) for p in packets]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(r is None for r in results)
        assert len(tell_service.tell_history["receiver"]) == 10
    
    async def test_metrics_tracking(
        self, tell_service, sample_tell_packet, sample_emoteto_packet,
        mock_state_manager, online_user_session
    ):
        """Test that metrics are properly tracked."""
        mock_state_manager.get_session.return_value = online_user_session
        
        assert tell_service.metrics.packets_handled == 0
        
        await tell_service.handle_packet(sample_tell_packet)
        assert tell_service.metrics.packets_handled == 1
        
        await tell_service.handle_packet(sample_emoteto_packet)
        assert tell_service.metrics.packets_handled == 2
    
    @patch('asyncio.get_event_loop')
    async def test_timestamp_in_history(
        self, mock_loop, tell_service, sample_tell_packet,
        mock_state_manager, online_user_session
    ):
        """Test that timestamps are added to history."""
        mock_state_manager.get_session.return_value = online_user_session
        mock_loop.return_value.time.return_value = 12345.678
        
        await tell_service.handle_packet(sample_tell_packet)
        
        history = tell_service.get_tell_history("receiver")
        assert history[0]["timestamp"] == 12345.678