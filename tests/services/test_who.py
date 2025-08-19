"""Comprehensive unit tests for WhoService."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Optional, Dict, Any
from datetime import datetime

from src.services.who import WhoService
from src.models.packet import (
    WhoPacket, ErrorPacket, PacketType, I3Packet
)
from src.state.manager import StateManager
from src.models.connection import UserSession


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager."""
    manager = Mock(spec=StateManager)
    manager.sessions = {}
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
    return gateway


@pytest.fixture
def who_service(mock_state_manager, mock_gateway):
    """Create a WhoService instance for testing."""
    service = WhoService(mock_state_manager, mock_gateway)
    return service


@pytest.fixture
def sample_who_request():
    """Create a sample who request packet."""
    return WhoPacket(
        packet_type=PacketType.WHO_REQ,
        ttl=200,
        originator_mud="RemoteMUD",
        originator_user="requester",
        target_mud="TestMUD",
        target_user="",
        filter_criteria={}
    )


@pytest.fixture
def sample_who_reply():
    """Create a sample who reply packet."""
    return WhoPacket(
        packet_type=PacketType.WHO_REPLY,
        ttl=200,
        originator_mud="RemoteMUD",
        originator_user="",
        target_mud="TestMUD",
        target_user="requester",
        who_data=[
            {"name": "TestUser", "idle": 120, "level": 50, "extra": "The Tester"}
        ]
    )


@pytest.fixture
def online_user_session():
    """Create an online user session."""
    session = Mock(spec=UserSession)
    session.is_online = True
    session.user_name = "TestUser"
    session.title = "The Brave Adventurer"
    session.level = 45
    session.race = "human"
    session.guild = "warriors"
    session.last_activity = datetime.now()
    return session


@pytest.fixture
def multiple_user_sessions():
    """Create multiple online user sessions."""
    sessions = {}
    users_data = [
        {"name": "Alice", "level": 20, "race": "elf", "guild": "mages", "title": "The Wise"},
        {"name": "Bob", "level": 35, "race": "dwarf", "guild": "warriors", "title": "The Strong"},
        {"name": "Charlie", "level": 50, "race": "human", "guild": "thieves", "title": "The Sneaky"},
        {"name": "Diana", "level": 15, "race": "halfling", "guild": "rangers", "title": "The Swift"}
    ]
    
    for i, user_data in enumerate(users_data):
        session = Mock(spec=UserSession)
        session.is_online = True
        session.user_name = user_data["name"]
        session.title = user_data["title"]
        session.level = user_data["level"]
        session.race = user_data["race"]
        session.guild = user_data["guild"]
        session.last_activity = datetime.now()
        sessions[f"session_{i}"] = session
    
    return sessions


class TestWhoServiceInitialization:
    """Test WhoService initialization."""
    
    async def test_initialization(self, who_service):
        """Test service initialization."""
        await who_service.initialize()
        assert who_service.service_name == "who"
        assert PacketType.WHO_REQ in who_service.supported_packets
        assert PacketType.WHO_REPLY in who_service.supported_packets
        assert not who_service.requires_auth
        assert who_service.who_cache == {}
        assert who_service.cache_ttl == 30.0
    
    async def test_initialization_without_gateway(self, mock_state_manager):
        """Test service initialization without gateway."""
        service = WhoService(mock_state_manager, None)
        await service.initialize()
        assert service.gateway is None
        assert service.service_name == "who"
    
    async def test_supported_packet_types(self, who_service):
        """Test that service supports correct packet types."""
        assert len(who_service.supported_packets) == 2
        assert PacketType.WHO_REQ in who_service.supported_packets
        assert PacketType.WHO_REPLY in who_service.supported_packets
    
    async def test_service_properties(self, who_service):
        """Test basic service properties."""
        assert who_service.service_name == "who"
        assert who_service.requires_auth is False
        assert hasattr(who_service, 'logger')
        assert hasattr(who_service, 'who_cache')


class TestWhoRequestHandling:
    """Test handling of who request packets."""
    
    async def test_handle_who_request_single_user(
        self, who_service, sample_who_request, online_user_session
    ):
        """Test handling who request with single online user."""
        who_service.state_manager.sessions = {"session_1": online_user_session}
        
        result = await who_service.handle_packet(sample_who_request)
        
        assert isinstance(result, WhoPacket)
        assert result.packet_type == PacketType.WHO_REPLY
        assert result.target_mud == "RemoteMUD"
        assert result.target_user == "requester"
        assert len(result.who_data) == 1
        assert result.who_data[0]["name"] == "TestUser"
        assert result.who_data[0]["level"] == 45
    
    async def test_handle_who_request_multiple_users(
        self, who_service, sample_who_request, multiple_user_sessions
    ):
        """Test handling who request with multiple online users."""
        who_service.state_manager.sessions = multiple_user_sessions
        
        result = await who_service.handle_packet(sample_who_request)
        
        assert isinstance(result, WhoPacket)
        assert len(result.who_data) == 4
        # Should be sorted by name
        assert result.who_data[0]["name"] == "Alice"
        assert result.who_data[3]["name"] == "Diana"
    
    async def test_handle_who_request_no_users(
        self, who_service, sample_who_request
    ):
        """Test handling who request with no online users."""
        who_service.state_manager.sessions = {}
        
        result = await who_service.handle_packet(sample_who_request)
        
        assert isinstance(result, WhoPacket)
        assert len(result.who_data) == 0
    
    async def test_handle_who_request_offline_users(
        self, who_service, sample_who_request
    ):
        """Test handling who request with offline users."""
        offline_session = Mock(spec=UserSession)
        offline_session.is_online = False
        offline_session.user_name = "OfflineUser"
        
        who_service.state_manager.sessions = {"session_1": offline_session}
        
        result = await who_service.handle_packet(sample_who_request)
        
        assert isinstance(result, WhoPacket)
        assert len(result.who_data) == 0  # Offline users not included
    
    async def test_who_request_with_level_filters(
        self, who_service, multiple_user_sessions
    ):
        """Test who request with level filters."""
        who_service.state_manager.sessions = multiple_user_sessions
        
        # Request with minimum level 30
        request = WhoPacket(
            packet_type=PacketType.WHO_REQ,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="requester",
            target_mud="TestMUD",
            target_user="",
            filter_criteria={"level_min": 30}
        )
        
        result = await who_service.handle_packet(request)
        
        assert len(result.who_data) == 2  # Bob(35) and Charlie(50)
        assert all(user["level"] >= 30 for user in result.who_data)
    
    async def test_who_request_with_level_range_filters(
        self, who_service, multiple_user_sessions
    ):
        """Test who request with level range filters."""
        who_service.state_manager.sessions = multiple_user_sessions
        
        # Request with level range 20-40
        request = WhoPacket(
            packet_type=PacketType.WHO_REQ,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="requester",
            target_mud="TestMUD",
            target_user="",
            filter_criteria={"level_min": 20, "level_max": 40}
        )
        
        result = await who_service.handle_packet(request)
        
        assert len(result.who_data) == 2  # Alice(20) and Bob(35)
        assert all(20 <= user["level"] <= 40 for user in result.who_data)
    
    async def test_who_request_with_race_filter(
        self, who_service, multiple_user_sessions
    ):
        """Test who request with race filter."""
        who_service.state_manager.sessions = multiple_user_sessions
        
        request = WhoPacket(
            packet_type=PacketType.WHO_REQ,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="requester",
            target_mud="TestMUD",
            target_user="",
            filter_criteria={"race": "elf"}
        )
        
        result = await who_service.handle_packet(request)
        
        assert len(result.who_data) == 1
        assert result.who_data[0]["name"] == "Alice"
        assert result.who_data[0]["race"] == "elf"
    
    async def test_who_request_with_guild_filter(
        self, who_service, multiple_user_sessions
    ):
        """Test who request with guild filter."""
        who_service.state_manager.sessions = multiple_user_sessions
        
        request = WhoPacket(
            packet_type=PacketType.WHO_REQ,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="requester",
            target_mud="TestMUD",
            target_user="",
            filter_criteria={"guild": "warriors"}
        )
        
        result = await who_service.handle_packet(request)
        
        assert len(result.who_data) == 1
        assert result.who_data[0]["name"] == "Bob"
        assert result.who_data[0]["guild"] == "warriors"


class TestWhoReplyHandling:
    """Test handling of who reply packets."""
    
    async def test_handle_who_reply(self, who_service, sample_who_reply):
        """Test handling who reply packet."""
        result = await who_service.handle_packet(sample_who_reply)
        
        assert result is None  # Replies don't generate responses
    
    async def test_who_reply_logging(self, who_service, sample_who_reply):
        """Test that who reply is properly logged."""
        with patch.object(who_service.logger, 'info') as mock_log:
            await who_service.handle_packet(sample_who_reply)
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "Received who reply" in str(call_args)


class TestWhoCaching:
    """Test who result caching."""
    
    async def test_cache_who_results(
        self, who_service, sample_who_request, online_user_session
    ):
        """Test that who results are cached."""
        who_service.state_manager.sessions = {"session_1": online_user_session}
        
        # First request - should cache results
        result1 = await who_service.handle_packet(sample_who_request)
        assert len(who_service.who_cache) == 1
        
        # Second request - should use cache
        with patch.object(who_service, '_get_online_users') as mock_get_users:
            result2 = await who_service.handle_packet(sample_who_request)
            mock_get_users.assert_not_called()  # Should not be called due to cache
            
        assert result1.who_data == result2.who_data
    
    async def test_cache_expiry(
        self, who_service, sample_who_request, online_user_session
    ):
        """Test that cache expires after TTL."""
        who_service.state_manager.sessions = {"session_1": online_user_session}
        who_service.cache_ttl = 0.1  # Very short cache
        
        # First request
        await who_service.handle_packet(sample_who_request)
        
        # Wait for cache to expire
        await asyncio.sleep(0.2)
        
        # Second request should not use cache
        with patch.object(who_service, '_get_online_users') as mock_get_users:
            mock_get_users.return_value = []
            await who_service.handle_packet(sample_who_request)
            mock_get_users.assert_called_once()
    
    async def test_clear_cache(self, who_service, sample_who_request, online_user_session):
        """Test clearing the who cache."""
        who_service.state_manager.sessions = {"session_1": online_user_session}
        
        # Add something to cache
        await who_service.handle_packet(sample_who_request)
        assert len(who_service.who_cache) > 0
        
        # Clear cache
        who_service.clear_cache()
        assert len(who_service.who_cache) == 0


class TestPacketValidation:
    """Test packet validation."""
    
    async def test_validate_valid_who_request(self, who_service, sample_who_request):
        """Test validation of valid who request."""
        assert await who_service.validate_packet(sample_who_request) is True
    
    async def test_validate_valid_who_reply(self, who_service, sample_who_reply):
        """Test validation of valid who reply."""
        assert await who_service.validate_packet(sample_who_reply) is True
    
    async def test_validate_unsupported_packet_type(self, who_service):
        """Test validation rejects unsupported packet types."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.TELL
        
        assert await who_service.validate_packet(packet) is False
    
    async def test_validate_wrong_packet_class(self, who_service):
        """Test validation rejects wrong packet class."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.WHO_REQ
        
        # Not actually a WhoPacket instance
        assert await who_service.validate_packet(packet) is False


class TestSendingWhoRequests:
    """Test sending who requests."""
    
    async def test_send_who_request_success(self, who_service, mock_gateway):
        """Test successful who request sending."""
        result = await who_service.send_who_request("RemoteMUD")
        
        assert result is True
        mock_gateway.send_packet.assert_called_once()
        
        sent_packet = mock_gateway.send_packet.call_args[0][0]
        assert isinstance(sent_packet, WhoPacket)
        assert sent_packet.packet_type == PacketType.WHO_REQ
        assert sent_packet.target_mud == "RemoteMUD"
        assert sent_packet.originator_mud == "TestMUD"
    
    async def test_send_who_request_with_filters(self, who_service, mock_gateway):
        """Test sending who request with filters."""
        filters = {"level_min": 20, "race": "elf"}
        result = await who_service.send_who_request("RemoteMUD", filters)
        
        assert result is True
        sent_packet = mock_gateway.send_packet.call_args[0][0]
        assert sent_packet.filter_criteria == filters
    
    async def test_send_who_request_no_gateway(self, mock_state_manager):
        """Test who request sending without gateway."""
        service = WhoService(mock_state_manager, None)
        
        result = await service.send_who_request("RemoteMUD")
        assert result is False
    
    async def test_send_who_request_gateway_failure(self, who_service, mock_gateway):
        """Test who request when gateway fails."""
        mock_gateway.send_packet.return_value = False
        
        result = await who_service.send_who_request("RemoteMUD")
        assert result is False


class TestUtilityMethods:
    """Test utility methods."""
    
    async def test_get_online_users_with_optional_fields(self, who_service):
        """Test getting online users with optional fields."""
        session = Mock(spec=UserSession)
        session.is_online = True
        session.user_name = "TestUser"
        session.title = "The Tester"
        session.level = 30
        session.race = "elf"
        session.guild = "mages"
        session.last_activity = datetime.now()
        
        who_service.state_manager.sessions = {"session_1": session}
        
        users = await who_service._get_online_users({})
        
        assert len(users) == 1
        user = users[0]
        assert user["name"] == "TestUser"
        assert user["level"] == 30
        assert user["race"] == "elf"
        assert user["guild"] == "mages"
        assert "idle" in user
    
    async def test_get_online_users_missing_optional_fields(self, who_service):
        """Test getting online users without optional fields."""
        session = Mock(spec=UserSession)
        session.is_online = True
        session.user_name = "TestUser"
        session.title = "The Tester"
        session.level = 30
        session.last_activity = datetime.now()
        # Missing race, guild attributes
        
        who_service.state_manager.sessions = {"session_1": session}
        
        users = await who_service._get_online_users({})
        
        assert len(users) == 1
        user = users[0]
        assert "race" not in user
        assert "guild" not in user
    
    async def test_create_who_reply_structure(self, who_service, sample_who_request):
        """Test who reply packet structure."""
        users = [{"name": "TestUser", "idle": 120, "level": 50, "extra": ""}]
        
        reply = who_service._create_who_reply(sample_who_request, users)
        
        assert isinstance(reply, WhoPacket)
        assert reply.packet_type == PacketType.WHO_REPLY
        assert reply.target_mud == "RemoteMUD"
        assert reply.target_user == "requester"
        assert reply.originator_mud == "TestMUD"
        assert reply.who_data == users


class TestConcurrentOperations:
    """Test concurrent operations."""
    
    async def test_concurrent_who_requests(
        self, who_service, online_user_session
    ):
        """Test handling concurrent who requests."""
        who_service.state_manager.sessions = {"session_1": online_user_session}
        
        # Create multiple who request packets
        requests = []
        for i in range(5):
            request = WhoPacket(
                packet_type=PacketType.WHO_REQ,
                ttl=200,
                originator_mud=f"MUD{i}",
                originator_user=f"user{i}",
                target_mud="TestMUD",
                target_user="",
                filter_criteria={}
            )
            requests.append(request)
        
        # Handle them concurrently
        tasks = [who_service.handle_packet(req) for req in requests]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 5
        assert all(isinstance(r, WhoPacket) for r in results)
        assert all(len(r.who_data) == 1 for r in results)
    
    async def test_cache_thread_safety(
        self, who_service, sample_who_request, online_user_session
    ):
        """Test cache operations are thread-safe."""
        who_service.state_manager.sessions = {"session_1": online_user_session}
        
        async def make_request():
            return await who_service.handle_packet(sample_who_request)
        
        # Multiple concurrent requests should not cause issues
        tasks = [make_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 10
        assert all(isinstance(r, WhoPacket) for r in results)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    async def test_handle_invalid_packet_type(self, who_service):
        """Test handling unsupported packet type."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_M
        
        result = await who_service.handle_packet(packet)
        assert result is None
    
    async def test_idle_time_calculation(self, who_service):
        """Test idle time calculation accuracy."""
        past_time = datetime.now()
        
        session = Mock(spec=UserSession)
        session.is_online = True
        session.user_name = "TestUser"
        session.title = "The Tester"
        session.level = 30
        session.last_activity = past_time
        
        who_service.state_manager.sessions = {"session_1": session}
        
        with patch('src.services.who.datetime') as mock_datetime:
            # Mock current time to be 5 minutes later
            current_time = past_time.replace(minute=past_time.minute + 5)
            mock_datetime.now.return_value = current_time
            
            users = await who_service._get_online_users({})
            
            assert users[0]["idle"] == 300  # 5 minutes in seconds
    
    async def test_empty_filter_criteria(self, who_service, online_user_session):
        """Test handling empty filter criteria."""
        who_service.state_manager.sessions = {"session_1": online_user_session}
        
        users = await who_service._get_online_users(None)
        assert len(users) == 1
        
        users = await who_service._get_online_users({})
        assert len(users) == 1
    
    async def test_user_sorting(self, who_service, multiple_user_sessions):
        """Test that users are sorted correctly by name."""
        who_service.state_manager.sessions = multiple_user_sessions
        
        users = await who_service._get_online_users({})
        
        # Should be sorted alphabetically by name (case-insensitive)
        names = [user["name"] for user in users]
        assert names == sorted(names, key=str.lower)
    
    async def test_no_gateway_settings(self, mock_state_manager):
        """Test service behavior without gateway settings."""
        service = WhoService(mock_state_manager, None)
        
        # Should still work for basic operations
        users = await service._get_online_users({})
        assert users == []
        
        # Create reply should handle missing gateway
        request = WhoPacket(
            packet_type=PacketType.WHO_REQ,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="requester",
            target_mud="TestMUD",
            target_user="",
            filter_criteria={}
        )
        
        reply = service._create_who_reply(request, [])
        assert reply.originator_mud == ""  # Empty when no gateway