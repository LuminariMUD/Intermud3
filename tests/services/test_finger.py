"""Comprehensive unit tests for FingerService."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.models.connection import UserSession
from src.models.packet import FingerPacket, I3Packet, PacketType
from src.services.finger import FingerService
from src.state.manager import StateManager


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
    gateway.settings.services = Mock()
    gateway.settings.services.finger = {"hide_ip": True}
    gateway.send_packet = AsyncMock(return_value=True)
    return gateway


@pytest.fixture
def finger_service(mock_state_manager, mock_gateway):
    """Create a FingerService instance for testing."""
    service = FingerService(mock_state_manager, mock_gateway)
    return service


@pytest.fixture
def sample_finger_request():
    """Create a sample finger request packet."""
    # Create a mock packet that can return LPC array data
    packet = Mock(spec=I3Packet)
    packet.packet_type = PacketType.FINGER_REQ
    packet.ttl = 200
    packet.originator_mud = "RemoteMUD"
    packet.originator_user = "requester"
    packet.target_mud = "TestMUD"
    packet.target_user = ""

    # Mock the to_lpc_array method to return finger-req format
    packet.to_lpc_array.return_value = [
        "finger-req",
        200,
        "RemoteMUD",
        "requester",
        "TestMUD",
        0,
        "testuser",
    ]

    return packet


@pytest.fixture
def sample_finger_reply():
    """Create a sample finger reply packet."""
    packet = Mock(spec=I3Packet)
    packet.packet_type = PacketType.FINGER_REPLY
    packet.ttl = 200
    packet.originator_mud = "RemoteMUD"
    packet.originator_user = ""
    packet.target_mud = "TestMUD"
    packet.target_user = "requester"

    packet.to_lpc_array.return_value = [
        "finger-reply",
        200,
        "RemoteMUD",
        0,
        "TestMUD",
        "requester",
        "testuser",
        "info",
    ]

    return packet


@pytest.fixture
def online_user_session():
    """Create an online user session."""
    session = Mock(spec=UserSession)
    session.is_online = True
    session.user_name = "testuser"
    session.title = "The Test User"
    session.real_name = "Test Person"
    session.email = "test@example.com"
    session.login_time = datetime.now()
    session.last_activity = datetime.now()
    session.ip_address = "192.168.1.100"
    session.level = 45
    session.race = "human"
    session.guild = "testers"
    session.location = "Test Room"
    session.website = "http://test.example.com"
    return session


@pytest.fixture
def offline_user_session():
    """Create an offline user session."""
    session = Mock(spec=UserSession)
    session.is_online = False
    session.user_name = "testuser"
    return session


class TestFingerServiceInitialization:
    """Test FingerService initialization."""

    async def test_initialization(self, finger_service):
        """Test service initialization."""
        await finger_service.initialize()
        assert finger_service.service_name == "finger"
        assert PacketType.FINGER_REQ in finger_service.supported_packets
        assert PacketType.FINGER_REPLY in finger_service.supported_packets
        assert not finger_service.requires_auth
        assert finger_service.finger_cache == {}
        assert finger_service.cache_ttl == 60.0

    async def test_initialization_without_gateway(self, mock_state_manager):
        """Test service initialization without gateway."""
        service = FingerService(mock_state_manager, None)
        await service.initialize()
        assert service.gateway is None
        assert service.service_name == "finger"

    async def test_supported_packet_types(self, finger_service):
        """Test that service supports correct packet types."""
        assert len(finger_service.supported_packets) == 2
        assert PacketType.FINGER_REQ in finger_service.supported_packets
        assert PacketType.FINGER_REPLY in finger_service.supported_packets

    async def test_service_properties(self, finger_service):
        """Test basic service properties."""
        assert finger_service.service_name == "finger"
        assert finger_service.requires_auth is False
        assert hasattr(finger_service, "logger")
        assert hasattr(finger_service, "finger_cache")


class TestFingerRequestHandling:
    """Test handling of finger request packets."""

    async def test_handle_finger_request_online_user(
        self, finger_service, sample_finger_request, mock_state_manager, online_user_session
    ):
        """Test handling finger request for online user."""
        mock_state_manager.get_session.return_value = online_user_session

        result = await finger_service.handle_packet(sample_finger_request)

        assert isinstance(result, FingerPacket)
        assert result.packet_type == PacketType.FINGER_REPLY
        assert result.target_mud == "RemoteMUD"
        assert result.target_user == "requester"
        assert result.username == "testuser"
        assert result.user_info["name"] == "testuser"
        assert result.user_info["title"] == "The Test User"
        assert result.user_info["level"] == 45

    async def test_handle_finger_request_offline_user(
        self, finger_service, sample_finger_request, mock_state_manager
    ):
        """Test handling finger request for offline/nonexistent user."""
        mock_state_manager.get_session.return_value = None

        result = await finger_service.handle_packet(sample_finger_request)

        assert isinstance(result, FingerPacket)
        assert result.user_info == {}  # Empty when user not found
        assert result.username == "testuser"

    async def test_finger_request_invalid_packet_format(self, finger_service, mock_state_manager):
        """Test handling finger request with invalid packet format."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.FINGER_REQ
        packet.to_lpc_array.return_value = ["finger-req", 200, "MUD"]  # Too short

        result = await finger_service.handle_packet(packet)

        assert result is None  # Should return None for invalid packets

    async def test_finger_request_empty_username(self, finger_service, mock_state_manager):
        """Test handling finger request with empty username."""
        # Mock get_session to return None for empty username
        mock_state_manager.get_session.return_value = None

        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.FINGER_REQ
        packet.originator_mud = "RemoteMUD"
        packet.originator_user = "requester"
        packet.target_mud = "TestMUD"
        packet.target_user = ""
        packet.to_lpc_array.return_value = [
            "finger-req",
            200,
            "RemoteMUD",
            "requester",
            "TestMUD",
            0,
            "",
        ]

        result = await finger_service.handle_packet(packet)

        # Should still create a reply even with empty username
        assert isinstance(result, FingerPacket)
        assert result.username == ""
        assert result.user_info == {}

    async def test_finger_request_case_insensitive(
        self, finger_service, mock_state_manager, online_user_session
    ):
        """Test that finger requests are case-insensitive."""
        mock_state_manager.get_session.return_value = online_user_session

        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.FINGER_REQ
        packet.originator_mud = "RemoteMUD"
        packet.originator_user = "requester"
        packet.target_mud = "TestMUD"
        packet.target_user = ""
        packet.to_lpc_array.return_value = [
            "finger-req",
            200,
            "RemoteMUD",
            "requester",
            "TestMUD",
            0,
            "TESTUSER",  # Uppercase
        ]

        result = await finger_service.handle_packet(packet)

        assert isinstance(result, FingerPacket)
        assert result.username == "TESTUSER"  # Should preserve original case
        # Should have found the user despite case difference
        mock_state_manager.get_session.assert_called_with("testuser")  # lowercase

    async def test_finger_request_with_number_username(self, finger_service, mock_state_manager):
        """Test handling finger request with numeric username field."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.FINGER_REQ
        packet.originator_mud = "RemoteMUD"
        packet.originator_user = "requester"
        packet.target_mud = "TestMUD"
        packet.target_user = ""
        packet.to_lpc_array.return_value = [
            "finger-req",
            200,
            "RemoteMUD",
            "requester",
            "TestMUD",
            0,
            123,  # Number
        ]

        result = await finger_service.handle_packet(packet)

        assert isinstance(result, FingerPacket)
        assert result.username == "123"  # Should convert to string

    async def test_finger_request_user_info_fields(
        self, finger_service, mock_state_manager, online_user_session, sample_finger_request
    ):
        """Test that all user info fields are included correctly."""
        mock_state_manager.get_session.return_value = online_user_session

        result = await finger_service.handle_packet(sample_finger_request)

        user_info = result.user_info
        assert user_info["name"] == "testuser"
        assert user_info["title"] == "The Test User"
        assert user_info["real_name"] == "Test Person"
        assert user_info["email"] == "test@example.com"
        assert user_info["level"] == 45
        assert "login_time" in user_info
        assert "idle_time" in user_info
        assert "ip_address" in user_info
        assert "extra" in user_info

        # Check extra fields
        assert user_info["extra"]["race"] == "human"
        assert user_info["extra"]["guild"] == "testers"
        assert user_info["extra"]["location"] == "Test Room"
        assert user_info["extra"]["website"] == "http://test.example.com"

    async def test_finger_request_hide_ip_setting(
        self, finger_service, mock_state_manager, online_user_session, sample_finger_request
    ):
        """Test IP address hiding based on settings."""
        mock_state_manager.get_session.return_value = online_user_session

        # Test with IP hiding enabled (default)
        result = await finger_service.handle_packet(sample_finger_request)
        assert result.user_info["ip_address"] == ""  # Should be empty

        # Clear the cache before testing with different settings
        finger_service.finger_cache.clear()

        # Test with IP hiding disabled
        finger_service.gateway.settings.services.finger["hide_ip"] = False
        result = await finger_service.handle_packet(sample_finger_request)
        assert result.user_info["ip_address"] == "192.168.1.100"  # Should show IP


class TestFingerReplyHandling:
    """Test handling of finger reply packets."""

    async def test_handle_finger_reply(self, finger_service, sample_finger_reply):
        """Test handling finger reply packet."""
        result = await finger_service.handle_packet(sample_finger_reply)

        assert result is None  # Replies don't generate responses

    async def test_finger_reply_logging(self, finger_service, sample_finger_reply):
        """Test that finger reply is properly logged."""
        with patch.object(finger_service.logger, "info") as mock_log:
            await finger_service.handle_packet(sample_finger_reply)

            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "Received finger reply" in str(call_args)


class TestFingerCaching:
    """Test finger result caching."""

    async def test_cache_finger_results(
        self, finger_service, sample_finger_request, mock_state_manager, online_user_session
    ):
        """Test that finger results are cached."""
        mock_state_manager.get_session.return_value = online_user_session

        # First request - should cache results
        result1 = await finger_service.handle_packet(sample_finger_request)
        assert len(finger_service.finger_cache) == 1

        # Second request - should use cache
        with patch.object(finger_service, "_get_user_info") as mock_get_info:
            result2 = await finger_service.handle_packet(sample_finger_request)
            mock_get_info.assert_not_called()  # Should not be called due to cache

        assert result1.user_info == result2.user_info

    async def test_cache_expiry(
        self, finger_service, sample_finger_request, mock_state_manager, online_user_session
    ):
        """Test that cache expires after TTL."""
        mock_state_manager.get_session.return_value = online_user_session
        finger_service.cache_ttl = 0.1  # Very short cache

        # First request
        await finger_service.handle_packet(sample_finger_request)

        # Wait for cache to expire
        await asyncio.sleep(0.2)

        # Second request should not use cache
        with patch.object(finger_service, "_get_user_info") as mock_get_info:
            mock_get_info.return_value = {"name": "testuser", "title": "New Title"}
            await finger_service.handle_packet(sample_finger_request)
            mock_get_info.assert_called_once()

    async def test_cache_only_successful_results(
        self, finger_service, sample_finger_request, mock_state_manager
    ):
        """Test that only successful results are cached."""
        mock_state_manager.get_session.return_value = None  # User not found

        # Request for nonexistent user
        await finger_service.handle_packet(sample_finger_request)

        # Should not cache negative results
        assert len(finger_service.finger_cache) == 0

    async def test_clear_cache(
        self, finger_service, sample_finger_request, mock_state_manager, online_user_session
    ):
        """Test clearing the finger cache."""
        mock_state_manager.get_session.return_value = online_user_session

        # Add something to cache
        await finger_service.handle_packet(sample_finger_request)
        assert len(finger_service.finger_cache) > 0

        # Clear cache
        finger_service.clear_cache()
        assert len(finger_service.finger_cache) == 0


class TestPacketValidation:
    """Test packet validation."""

    async def test_validate_valid_finger_request(self, finger_service):
        """Test validation of valid finger request."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.FINGER_REQ

        assert await finger_service.validate_packet(packet) is True

    async def test_validate_valid_finger_reply(self, finger_service):
        """Test validation of valid finger reply."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.FINGER_REPLY

        assert await finger_service.validate_packet(packet) is True

    async def test_validate_unsupported_packet_type(self, finger_service):
        """Test validation rejects unsupported packet types."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.TELL

        assert await finger_service.validate_packet(packet) is False


class TestSendingFingerRequests:
    """Test sending finger requests."""

    async def test_send_finger_request_success(self, finger_service, mock_gateway):
        """Test successful finger request sending."""
        result = await finger_service.send_finger_request("RemoteMUD", "testuser")

        assert result is True
        mock_gateway.send_packet.assert_called_once()

        sent_packet = mock_gateway.send_packet.call_args[0][0]
        assert isinstance(sent_packet, FingerPacket)
        assert sent_packet.packet_type == PacketType.FINGER_REQ
        assert sent_packet.target_mud == "RemoteMUD"
        assert sent_packet.originator_mud == "TestMUD"
        assert sent_packet.username == "testuser"

    async def test_send_finger_request_no_gateway(self, mock_state_manager):
        """Test finger request sending without gateway."""
        service = FingerService(mock_state_manager, None)

        result = await service.send_finger_request("RemoteMUD", "testuser")
        assert result is False

    async def test_send_finger_request_gateway_failure(self, finger_service, mock_gateway):
        """Test finger request when gateway fails."""
        mock_gateway.send_packet.return_value = False

        result = await finger_service.send_finger_request("RemoteMUD", "testuser")
        assert result is False

    async def test_send_finger_request_empty_username(self, finger_service, mock_gateway):
        """Test sending finger request with empty username."""
        result = await finger_service.send_finger_request("RemoteMUD", "")

        assert result is True
        sent_packet = mock_gateway.send_packet.call_args[0][0]
        assert sent_packet.username == ""


class TestUserInfoRetrieval:
    """Test user information retrieval."""

    async def test_get_user_info_complete_profile(
        self, finger_service, mock_state_manager, online_user_session
    ):
        """Test getting complete user information."""
        mock_state_manager.get_session.return_value = online_user_session

        user_info = await finger_service._get_user_info("testuser")

        assert user_info is not None
        assert user_info["name"] == "testuser"
        assert user_info["title"] == "The Test User"
        assert user_info["real_name"] == "Test Person"
        assert user_info["email"] == "test@example.com"
        assert user_info["level"] == 45
        assert isinstance(user_info["idle_time"], int)
        assert user_info["extra"]["race"] == "human"
        assert user_info["extra"]["guild"] == "testers"

    async def test_get_user_info_minimal_profile(self, finger_service, mock_state_manager):
        """Test getting user info with minimal session data."""
        minimal_session = Mock(spec=UserSession)
        minimal_session.user_name = "minimaluser"
        minimal_session.title = None  # No title
        minimal_session.login_time = datetime.now()
        minimal_session.last_activity = datetime.now()
        minimal_session.ip_address = "127.0.0.1"
        minimal_session.level = 1

        mock_state_manager.get_session.return_value = minimal_session

        user_info = await finger_service._get_user_info("minimaluser")

        assert user_info is not None
        assert user_info["name"] == "minimaluser"
        assert user_info["title"] == "minimaluser the Adventurer"  # Default title
        assert user_info["real_name"] == ""
        assert user_info["email"] == ""
        assert user_info["level"] == 1
        assert user_info["extra"] == {}  # No extra fields

    async def test_get_user_info_nonexistent_user(self, finger_service, mock_state_manager):
        """Test getting info for nonexistent user."""
        mock_state_manager.get_session.return_value = None

        user_info = await finger_service._get_user_info("nonexistent")

        assert user_info is None

    async def test_idle_time_calculation(self, finger_service, mock_state_manager):
        """Test idle time calculation."""
        past_time = datetime.now()

        session = Mock(spec=UserSession)
        session.user_name = "testuser"
        session.title = "Test"
        session.login_time = past_time
        session.last_activity = past_time
        session.ip_address = "127.0.0.1"
        session.level = 1

        mock_state_manager.get_session.return_value = session

        with patch("src.services.finger.datetime") as mock_datetime:
            # Mock current time to be 10 minutes later
            current_time = past_time.replace(minute=past_time.minute + 10)
            mock_datetime.now.return_value = current_time

            user_info = await finger_service._get_user_info("testuser")

            assert user_info["idle_time"] == 600  # 10 minutes in seconds


class TestUtilityMethods:
    """Test utility methods."""

    def test_create_finger_reply_with_user_info(self, finger_service, sample_finger_request):
        """Test creating finger reply with user info."""
        user_info = {"name": "testuser", "level": 30, "title": "Test User"}

        reply = finger_service._create_finger_reply(sample_finger_request, "testuser", user_info)

        assert isinstance(reply, FingerPacket)
        assert reply.packet_type == PacketType.FINGER_REPLY
        assert reply.username == "testuser"
        assert reply.user_info == user_info
        assert reply.target_mud == "RemoteMUD"
        assert reply.target_user == "requester"

    def test_create_finger_reply_no_user_info(self, finger_service, sample_finger_request):
        """Test creating finger reply without user info."""
        reply = finger_service._create_finger_reply(sample_finger_request, "nonexistent", None)

        assert isinstance(reply, FingerPacket)
        assert reply.username == "nonexistent"
        assert reply.user_info == {}  # Empty dict for None input

    def test_create_finger_reply_no_gateway(self, mock_state_manager):
        """Test creating finger reply without gateway."""
        service = FingerService(mock_state_manager, None)

        request = Mock(spec=I3Packet)
        request.originator_mud = "RemoteMUD"
        request.originator_user = "requester"

        reply = service._create_finger_reply(request, "testuser", {})

        assert reply.originator_mud == ""  # Empty when no gateway


class TestConcurrentOperations:
    """Test concurrent operations."""

    async def test_concurrent_finger_requests(
        self, finger_service, mock_state_manager, online_user_session
    ):
        """Test handling concurrent finger requests."""
        mock_state_manager.get_session.return_value = online_user_session

        # Create multiple finger request packets
        requests = []
        for i in range(5):
            packet = Mock(spec=I3Packet)
            packet.packet_type = PacketType.FINGER_REQ
            packet.originator_mud = f"MUD{i}"
            packet.originator_user = f"user{i}"
            packet.target_mud = "TestMUD"
            packet.target_user = ""
            packet.to_lpc_array.return_value = [
                "finger-req",
                200,
                f"MUD{i}",
                f"user{i}",
                "TestMUD",
                0,
                "testuser",
            ]
            requests.append(packet)

        # Handle them concurrently
        tasks = [finger_service.handle_packet(req) for req in requests]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 5
        assert all(isinstance(r, FingerPacket) for r in results)
        assert all(r.username == "testuser" for r in results)

    async def test_cache_thread_safety(
        self, finger_service, sample_finger_request, mock_state_manager, online_user_session
    ):
        """Test cache operations are thread-safe."""
        mock_state_manager.get_session.return_value = online_user_session

        async def make_request():
            return await finger_service.handle_packet(sample_finger_request)

        # Multiple concurrent requests should not cause issues
        tasks = [make_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(isinstance(r, FingerPacket) for r in results)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    async def test_handle_invalid_packet_type(self, finger_service):
        """Test handling unsupported packet type."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_M

        result = await finger_service.handle_packet(packet)
        assert result is None

    async def test_missing_optional_session_attributes(self, finger_service, mock_state_manager):
        """Test handling session with missing optional attributes."""
        session = Mock(spec=UserSession)
        session.user_name = "testuser"
        session.title = "Test User"
        session.login_time = datetime.now()
        session.last_activity = datetime.now()
        session.ip_address = "127.0.0.1"
        session.level = 30
        # Missing: real_name, email, race, guild, location, website

        mock_state_manager.get_session.return_value = session

        user_info = await finger_service._get_user_info("testuser")

        assert user_info is not None
        assert user_info["real_name"] == ""
        assert user_info["email"] == ""
        assert "race" not in user_info["extra"]
        assert "guild" not in user_info["extra"]
        assert "location" not in user_info["extra"]
        assert "website" not in user_info["extra"]

    async def test_none_username_in_packet(self, finger_service):
        """Test handling packet with None username."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.FINGER_REQ
        packet.originator_mud = "RemoteMUD"
        packet.originator_user = "requester"
        packet.target_mud = "TestMUD"
        packet.target_user = ""
        packet.to_lpc_array.return_value = [
            "finger-req",
            200,
            "RemoteMUD",
            "requester",
            "TestMUD",
            0,
            None,
        ]

        result = await finger_service.handle_packet(packet)

        assert isinstance(result, FingerPacket)
        assert result.username == ""  # Should convert None to empty string

    async def test_login_time_none(self, finger_service, mock_state_manager):
        """Test handling session with None login_time."""
        session = Mock(spec=UserSession)
        session.user_name = "testuser"
        session.title = "Test User"
        session.login_time = None
        session.last_activity = datetime.now()
        session.ip_address = "127.0.0.1"
        session.level = 30

        mock_state_manager.get_session.return_value = session

        user_info = await finger_service._get_user_info("testuser")

        assert user_info["login_time"] == ""  # Should be empty string for None

    async def test_no_gateway_in_ip_check(self, mock_state_manager, online_user_session):
        """Test IP hiding logic without gateway."""
        service = FingerService(mock_state_manager, None)
        mock_state_manager.get_session.return_value = online_user_session

        user_info = await service._get_user_info("testuser")

        # Should show IP when no gateway (no hiding settings)
        assert user_info["ip_address"] == "192.168.1.100"
