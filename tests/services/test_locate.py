"""Comprehensive unit tests for LocateService."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Optional, Dict, Any
from datetime import datetime

from src.services.locate import LocateService
from src.models.packet import (
    LocatePacket, ErrorPacket, PacketType, I3Packet
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
    return gateway


@pytest.fixture
def locate_service(mock_state_manager, mock_gateway):
    """Create a LocateService instance for testing."""
    service = LocateService(mock_state_manager, mock_gateway)
    return service


@pytest.fixture
def sample_locate_request():
    """Create a sample locate request packet."""
    return LocatePacket(
        packet_type=PacketType.LOCATE_REQ,
        ttl=200,
        originator_mud="RemoteMUD",
        originator_user="requester",
        target_mud="0",  # Broadcast
        target_user="",
        user_to_locate="testuser"
    )


@pytest.fixture
def sample_locate_request_direct():
    """Create a sample direct locate request packet."""
    return LocatePacket(
        packet_type=PacketType.LOCATE_REQ,
        ttl=200,
        originator_mud="RemoteMUD",
        originator_user="requester",
        target_mud="TestMUD",  # Direct to specific MUD
        target_user="",
        user_to_locate="testuser"
    )


@pytest.fixture
def sample_locate_reply():
    """Create a sample locate reply packet."""
    return LocatePacket(
        packet_type=PacketType.LOCATE_REPLY,
        ttl=200,
        originator_mud="RemoteMUD",
        originator_user="",
        target_mud="TestMUD",
        target_user="requester",
        user_to_locate="",
        located_mud="RemoteMUD",
        located_user="testuser",
        idle_time=120,
        status_string="online"
    )


@pytest.fixture
def sample_locate_reply_not_found():
    """Create a sample locate reply packet for user not found."""
    return LocatePacket(
        packet_type=PacketType.LOCATE_REPLY,
        ttl=200,
        originator_mud="RemoteMUD",
        originator_user="",
        target_mud="TestMUD",
        target_user="requester",
        user_to_locate="",
        located_mud="",  # Empty when not found
        located_user="",
        idle_time=0,
        status_string=""
    )


@pytest.fixture
def online_user_session():
    """Create an online user session."""
    session = Mock(spec=UserSession)
    session.is_online = True
    session.user_name = "testuser"
    session.status_message = "Testing the system"
    session.last_activity = datetime.now()
    return session


@pytest.fixture
def offline_user_session():
    """Create an offline user session."""
    session = Mock(spec=UserSession)
    session.is_online = False
    session.user_name = "testuser"
    return session


class TestLocateServiceInitialization:
    """Test LocateService initialization."""
    
    async def test_initialization(self, locate_service):
        """Test service initialization."""
        await locate_service.initialize()
        assert locate_service.service_name == "locate"
        assert PacketType.LOCATE_REQ in locate_service.supported_packets
        assert PacketType.LOCATE_REPLY in locate_service.supported_packets
        assert not locate_service.requires_auth
        assert locate_service.pending_locates == {}
        assert locate_service.locate_cache == {}
        assert locate_service.cache_ttl == 30.0
        assert locate_service.locate_timeout == 5.0
    
    async def test_initialization_without_gateway(self, mock_state_manager):
        """Test service initialization without gateway."""
        service = LocateService(mock_state_manager, None)
        await service.initialize()
        assert service.gateway is None
        assert service.service_name == "locate"
    
    async def test_supported_packet_types(self, locate_service):
        """Test that service supports correct packet types."""
        assert len(locate_service.supported_packets) == 2
        assert PacketType.LOCATE_REQ in locate_service.supported_packets
        assert PacketType.LOCATE_REPLY in locate_service.supported_packets
    
    async def test_service_properties(self, locate_service):
        """Test basic service properties."""
        assert locate_service.service_name == "locate"
        assert locate_service.requires_auth is False
        assert hasattr(locate_service, 'logger')
        assert hasattr(locate_service, 'pending_locates')
        assert hasattr(locate_service, 'locate_cache')


class TestLocateRequestHandling:
    """Test handling of locate request packets."""
    
    async def test_handle_locate_request_user_found_locally(
        self, locate_service, sample_locate_request, online_user_session
    ):
        """Test handling locate request when user is found locally."""
        locate_service.state_manager.sessions = {"session_1": online_user_session}
        
        result = await locate_service.handle_packet(sample_locate_request)
        
        assert isinstance(result, LocatePacket)
        assert result.packet_type == PacketType.LOCATE_REPLY
        assert result.target_mud == "RemoteMUD"
        assert result.target_user == "requester"
        assert result.located_mud == "TestMUD"
        assert result.located_user == "testuser"
        assert result.status_string == "Testing the system"
        assert isinstance(result.idle_time, int)
    
    async def test_handle_locate_request_user_not_found_broadcast(
        self, locate_service, sample_locate_request
    ):
        """Test handling broadcast locate request when user not found locally."""
        locate_service.state_manager.sessions = {}  # No users
        
        result = await locate_service.handle_packet(sample_locate_request)
        
        # For broadcast requests, should return None when not found
        assert result is None
    
    async def test_handle_locate_request_user_not_found_direct(
        self, locate_service, sample_locate_request_direct
    ):
        """Test handling direct locate request when user not found locally."""
        locate_service.state_manager.sessions = {}  # No users
        
        result = await locate_service.handle_packet(sample_locate_request_direct)
        
        # For direct requests, should return empty reply when not found
        assert isinstance(result, LocatePacket)
        assert result.packet_type == PacketType.LOCATE_REPLY
        assert result.located_mud == ""
        assert result.located_user == ""
        assert result.idle_time == 0
    
    async def test_handle_locate_request_offline_user(
        self, locate_service, sample_locate_request, offline_user_session
    ):
        """Test handling locate request for offline user."""
        locate_service.state_manager.sessions = {"session_1": offline_user_session}
        
        result = await locate_service.handle_packet(sample_locate_request)
        
        # Offline users should not be found
        assert result is None  # Broadcast request, no reply for not found
    
    async def test_handle_locate_request_case_insensitive(
        self, locate_service, online_user_session
    ):
        """Test that locate requests are case-insensitive."""
        locate_service.state_manager.sessions = {"session_1": online_user_session}
        
        # Request with uppercase username
        request = LocatePacket(
            packet_type=PacketType.LOCATE_REQ,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="requester",
            target_mud="TestMUD",
            target_user="",
            user_to_locate="TESTUSER"  # Uppercase
        )
        
        result = await locate_service.handle_packet(request)
        
        assert isinstance(result, LocatePacket)
        assert result.located_user == "testuser"  # Should find the user
    
    async def test_locate_request_with_status_message(
        self, locate_service, sample_locate_request
    ):
        """Test locate request includes user status message."""
        session = Mock(spec=UserSession)
        session.is_online = True
        session.user_name = "testuser"
        session.status_message = "Away from keyboard"
        session.last_activity = datetime.now()
        
        locate_service.state_manager.sessions = {"session_1": session}
        
        result = await locate_service.handle_packet(sample_locate_request)
        
        assert result.status_string == "Away from keyboard"
    
    async def test_locate_request_no_status_message(
        self, locate_service, sample_locate_request
    ):
        """Test locate request with user having no status message."""
        session = Mock(spec=UserSession)
        session.is_online = True
        session.user_name = "testuser"
        session.status_message = None
        session.last_activity = datetime.now()
        
        locate_service.state_manager.sessions = {"session_1": session}
        
        result = await locate_service.handle_packet(sample_locate_request)
        
        assert result.status_string == ""


class TestLocateReplyHandling:
    """Test handling of locate reply packets."""
    
    async def test_handle_locate_reply_found(self, locate_service, sample_locate_reply):
        """Test handling locate reply when user was found."""
        result = await locate_service.handle_packet(sample_locate_reply)
        
        assert result is None  # Replies don't generate responses
        
        # Should cache the result
        cache_key = "locate:testuser"
        assert cache_key in locate_service.locate_cache
        cached_data, _ = locate_service.locate_cache[cache_key]
        assert cached_data["found"] is True
        assert cached_data["mud"] == "RemoteMUD"
        assert cached_data["user"] == "testuser"
    
    async def test_handle_locate_reply_not_found(
        self, locate_service, sample_locate_reply_not_found
    ):
        """Test handling locate reply when user was not found."""
        result = await locate_service.handle_packet(sample_locate_reply_not_found)
        
        assert result is None
        
        # Should not cache negative results from replies
        cache_key = "locate:testuser"
        assert cache_key not in locate_service.locate_cache
    
    async def test_handle_locate_reply_with_pending_request(
        self, locate_service, sample_locate_reply
    ):
        """Test handling locate reply that matches a pending request."""
        # Set up a pending request
        request_key = "requester:testuser"
        event = asyncio.Event()
        locate_service.pending_locates[request_key] = {
            'event': event,
            'result': None,
            'timestamp': datetime.now()
        }
        
        await locate_service.handle_packet(sample_locate_reply)
        
        # Should update the pending request
        assert locate_service.pending_locates[request_key]['result'] is not None
        assert locate_service.pending_locates[request_key]['result']['found'] is True
        assert event.is_set()
    
    async def test_locate_reply_logging(self, locate_service, sample_locate_reply):
        """Test that locate reply is properly logged."""
        with patch.object(locate_service.logger, 'info') as mock_log:
            await locate_service.handle_packet(sample_locate_reply)
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "Received locate reply" in str(call_args)


class TestLocateCaching:
    """Test locate result caching."""
    
    async def test_cache_locate_results(
        self, locate_service, sample_locate_request, online_user_session
    ):
        """Test that locate results are cached."""
        locate_service.state_manager.sessions = {"session_1": online_user_session}
        
        # First request - should cache results
        result1 = await locate_service.handle_packet(sample_locate_request)
        assert len(locate_service.locate_cache) == 1
        
        # Second request - should use cache
        with patch.object(locate_service, '_search_local_user') as mock_search:
            result2 = await locate_service.handle_packet(sample_locate_request)
            mock_search.assert_not_called()  # Should not be called due to cache
            
        assert result1.located_user == result2.located_user
    
    async def test_cache_expiry(
        self, locate_service, sample_locate_request, online_user_session
    ):
        """Test that cache expires after TTL."""
        locate_service.state_manager.sessions = {"session_1": online_user_session}
        locate_service.cache_ttl = 0.1  # Very short cache
        
        # First request
        await locate_service.handle_packet(sample_locate_request)
        
        # Wait for cache to expire
        await asyncio.sleep(0.2)
        
        # Second request should not use cache
        with patch.object(locate_service, '_search_local_user') as mock_search:
            mock_search.return_value = {
                'user': 'testuser', 'idle_time': 0, 'status': 'test'
            }
            await locate_service.handle_packet(sample_locate_request)
            mock_search.assert_called_once()
    
    async def test_clear_cache(
        self, locate_service, sample_locate_request, online_user_session
    ):
        """Test clearing the locate cache."""
        locate_service.state_manager.sessions = {"session_1": online_user_session}
        
        # Add something to cache
        await locate_service.handle_packet(sample_locate_request)
        assert len(locate_service.locate_cache) > 0
        
        # Clear cache
        locate_service.clear_cache()
        assert len(locate_service.locate_cache) == 0


class TestPacketValidation:
    """Test packet validation."""
    
    async def test_validate_valid_locate_request(self, locate_service, sample_locate_request):
        """Test validation of valid locate request."""
        assert await locate_service.validate_packet(sample_locate_request) is True
    
    async def test_validate_valid_locate_reply(self, locate_service, sample_locate_reply):
        """Test validation of valid locate reply."""
        assert await locate_service.validate_packet(sample_locate_reply) is True
    
    async def test_validate_unsupported_packet_type(self, locate_service):
        """Test validation rejects unsupported packet types."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.TELL
        
        assert await locate_service.validate_packet(packet) is False
    
    async def test_validate_wrong_packet_class(self, locate_service):
        """Test validation rejects wrong packet class."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.LOCATE_REQ
        
        # Not actually a LocatePacket instance
        assert await locate_service.validate_packet(packet) is False
    
    async def test_validate_locate_request_missing_username(self, locate_service):
        """Test validation rejects locate request without username."""
        request = LocatePacket(
            packet_type=PacketType.LOCATE_REQ,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="requester",
            target_mud="TestMUD",
            target_user="",
            user_to_locate=""  # Empty username
        )
        
        assert await locate_service.validate_packet(request) is False


class TestLocateUserMethod:
    """Test the locate_user method for programmatic locate requests."""
    
    async def test_locate_user_found_locally(
        self, locate_service, online_user_session
    ):
        """Test locating user found locally."""
        locate_service.state_manager.sessions = {"session_1": online_user_session}
        
        result = await locate_service.locate_user("testuser")
        
        assert result is not None
        assert result["found"] is True
        assert result["mud"] == "TestMUD"
        assert result["user"] == "testuser"
        assert "idle_time" in result
        assert "status" in result
    
    async def test_locate_user_not_found_locally_with_timeout(
        self, locate_service, mock_gateway
    ):
        """Test locating user not found locally with network timeout."""
        locate_service.state_manager.sessions = {}
        locate_service.locate_timeout = 0.1  # Very short timeout
        
        result = await locate_service.locate_user("nonexistent")
        
        assert result is None
        # Should have sent a broadcast locate request
        mock_gateway.send_packet.assert_called_once()
    
    async def test_locate_user_found_via_network(
        self, locate_service, mock_gateway
    ):
        """Test locating user found via network response."""
        locate_service.state_manager.sessions = {}
        
        async def mock_send_packet(packet):
            # Simulate receiving a locate reply
            reply = LocatePacket(
                packet_type=PacketType.LOCATE_REPLY,
                ttl=200,
                originator_mud="RemoteMUD",
                originator_user="",
                target_mud="TestMUD",
                target_user="TestMUD",  # Using MUD name as user for tracking
                user_to_locate="",
                located_mud="RemoteMUD",
                located_user="testuser",
                idle_time=300,
                status_string="online"
            )
            
            # Trigger the reply handling
            asyncio.create_task(locate_service.handle_packet(reply))
            return True
        
        mock_gateway.send_packet.side_effect = mock_send_packet
        
        # Start the locate request
        task = asyncio.create_task(locate_service.locate_user("testuser"))
        
        # Give some time for the reply to be processed
        await asyncio.sleep(0.1)
        
        result = await task
        
        assert result is not None
        assert result["found"] is True
        assert result["mud"] == "RemoteMUD"
        assert result["user"] == "testuser"
    
    async def test_locate_user_no_gateway(self, mock_state_manager):
        """Test locate_user without gateway."""
        service = LocateService(mock_state_manager, None)
        
        result = await service.locate_user("testuser")
        assert result is None
    
    async def test_locate_user_gateway_send_failure(
        self, locate_service, mock_gateway
    ):
        """Test locate_user when gateway send fails."""
        locate_service.state_manager.sessions = {}
        mock_gateway.send_packet.return_value = False
        
        result = await locate_service.locate_user("testuser")
        assert result is None
    
    async def test_locate_user_custom_timeout(self, locate_service):
        """Test locate_user with custom timeout."""
        locate_service.state_manager.sessions = {}
        
        start_time = asyncio.get_event_loop().time()
        result = await locate_service.locate_user("testuser", timeout=0.1)
        end_time = asyncio.get_event_loop().time()
        
        assert result is None
        # Should have timed out in approximately 0.1 seconds
        assert end_time - start_time < 0.2
    
    async def test_locate_user_uses_cache(
        self, locate_service, online_user_session
    ):
        """Test that locate_user uses cached results."""
        locate_service.state_manager.sessions = {"session_1": online_user_session}
        
        # First call caches result
        result1 = await locate_service.locate_user("testuser")
        
        # Clear sessions to ensure cache is used
        locate_service.state_manager.sessions = {}
        
        # Second call should use cache
        result2 = await locate_service.locate_user("testuser")
        
        assert result1 == result2
        assert result2 is not None


class TestUtilityMethods:
    """Test utility methods."""
    
    async def test_search_local_user_found(
        self, locate_service, online_user_session
    ):
        """Test searching for local user that exists."""
        locate_service.state_manager.sessions = {"session_1": online_user_session}
        
        result = await locate_service._search_local_user("testuser")
        
        assert result is not None
        assert result["user"] == "testuser"
        assert result["status"] == "Testing the system"
        assert isinstance(result["idle_time"], int)
    
    async def test_search_local_user_not_found(self, locate_service):
        """Test searching for local user that doesn't exist."""
        locate_service.state_manager.sessions = {}
        
        result = await locate_service._search_local_user("nonexistent")
        
        assert result is None
    
    async def test_search_local_user_offline(
        self, locate_service, offline_user_session
    ):
        """Test searching for offline local user."""
        locate_service.state_manager.sessions = {"session_1": offline_user_session}
        
        result = await locate_service._search_local_user("testuser")
        
        assert result is None  # Offline users not returned
    
    def test_create_locate_reply_found(self, locate_service, sample_locate_request):
        """Test creating locate reply for found user."""
        result_data = {
            'found': True,
            'mud': 'TestMUD',
            'user': 'testuser',
            'idle_time': 120,
            'status': 'online'
        }
        
        reply = locate_service._create_locate_reply(sample_locate_request, result_data)
        
        assert isinstance(reply, LocatePacket)
        assert reply.packet_type == PacketType.LOCATE_REPLY
        assert reply.located_mud == 'TestMUD'
        assert reply.located_user == 'testuser'
        assert reply.idle_time == 120
        assert reply.status_string == 'online'
    
    def test_create_locate_reply_not_found(
        self, locate_service, sample_locate_request
    ):
        """Test creating locate reply for user not found."""
        result_data = {'found': False}
        
        reply = locate_service._create_locate_reply(sample_locate_request, result_data)
        
        assert isinstance(reply, LocatePacket)
        assert reply.packet_type == PacketType.LOCATE_REPLY
        assert reply.located_mud == ""
        assert reply.located_user == ""
        assert reply.idle_time == 0
        assert reply.status_string == ""
    
    async def test_cleanup_pending(self, locate_service):
        """Test cleanup of old pending requests."""
        old_time = datetime.now().replace(hour=0)  # Very old timestamp
        
        # Add some pending requests
        locate_service.pending_locates = {
            "old_request": {
                'event': asyncio.Event(),
                'result': None,
                'timestamp': old_time
            },
            "new_request": {
                'event': asyncio.Event(),
                'result': None,
                'timestamp': datetime.now()
            }
        }
        
        await locate_service.cleanup_pending()
        
        # Old request should be removed, new one kept
        assert "old_request" not in locate_service.pending_locates
        assert "new_request" in locate_service.pending_locates


class TestBroadcastVsDirectRequests:
    """Test differences between broadcast and direct locate requests."""
    
    async def test_broadcast_request_identification(
        self, locate_service, online_user_session
    ):
        """Test identification of broadcast requests."""
        locate_service.state_manager.sessions = {"session_1": online_user_session}
        
        # Test string "0"
        request1 = LocatePacket(
            packet_type=PacketType.LOCATE_REQ,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="requester",
            target_mud="0",
            target_user="",
            user_to_locate="testuser"
        )
        
        # Test integer 0
        request2 = LocatePacket(
            packet_type=PacketType.LOCATE_REQ,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="requester",
            target_mud=0,
            target_user="",
            user_to_locate="testuser"
        )
        
        result1 = await locate_service.handle_packet(request1)
        result2 = await locate_service.handle_packet(request2)
        
        # Both should be treated as broadcast and return replies
        assert isinstance(result1, LocatePacket)
        assert isinstance(result2, LocatePacket)
    
    async def test_broadcast_no_reply_when_not_found(
        self, locate_service, sample_locate_request
    ):
        """Test that broadcast requests don't reply when user not found."""
        locate_service.state_manager.sessions = {}
        
        result = await locate_service.handle_packet(sample_locate_request)
        
        # Should not reply for broadcast when not found
        assert result is None
    
    async def test_direct_reply_when_not_found(
        self, locate_service, sample_locate_request_direct
    ):
        """Test that direct requests reply even when user not found."""
        locate_service.state_manager.sessions = {}
        
        result = await locate_service.handle_packet(sample_locate_request_direct)
        
        # Should reply with empty result for direct requests
        assert isinstance(result, LocatePacket)
        assert result.located_mud == ""
        assert result.located_user == ""


class TestConcurrentOperations:
    """Test concurrent operations."""
    
    async def test_concurrent_locate_requests(
        self, locate_service, online_user_session
    ):
        """Test handling concurrent locate requests."""
        locate_service.state_manager.sessions = {"session_1": online_user_session}
        
        # Create multiple locate request packets
        requests = []
        for i in range(5):
            request = LocatePacket(
                packet_type=PacketType.LOCATE_REQ,
                ttl=200,
                originator_mud=f"MUD{i}",
                originator_user=f"user{i}",
                target_mud="TestMUD",
                target_user="",
                user_to_locate="testuser"
            )
            requests.append(request)
        
        # Handle them concurrently
        tasks = [locate_service.handle_packet(req) for req in requests]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 5
        assert all(isinstance(r, LocatePacket) for r in results)
        assert all(r.located_user == "testuser" for r in results)
    
    async def test_concurrent_locate_user_calls(
        self, locate_service, online_user_session
    ):
        """Test concurrent locate_user method calls."""
        locate_service.state_manager.sessions = {"session_1": online_user_session}
        
        async def locate_call():
            return await locate_service.locate_user("testuser")
        
        # Multiple concurrent calls
        tasks = [locate_call() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed and return same result
        assert len(results) == 5
        assert all(r is not None for r in results)
        assert all(r["user"] == "testuser" for r in results)


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    async def test_handle_invalid_packet_type(self, locate_service):
        """Test handling unsupported packet type."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_M
        
        result = await locate_service.handle_packet(packet)
        assert result is None
    
    async def test_idle_time_calculation(self, locate_service):
        """Test idle time calculation accuracy."""
        past_time = datetime.now()
        
        session = Mock(spec=UserSession)
        session.is_online = True
        session.user_name = "testuser"
        session.status_message = "test"
        session.last_activity = past_time
        
        locate_service.state_manager.sessions = {"session_1": session}
        
        with patch('src.services.locate.datetime') as mock_datetime:
            # Mock current time to be 5 minutes later
            current_time = past_time.replace(minute=past_time.minute + 5)
            mock_datetime.now.return_value = current_time
            
            result = await locate_service._search_local_user("testuser")
            
            assert result["idle_time"] == 300  # 5 minutes in seconds
    
    async def test_pending_request_without_event(self, locate_service, sample_locate_reply):
        """Test handling locate reply with pending request missing event."""
        # Set up pending request without event
        request_key = "requester:testuser"
        locate_service.pending_locates[request_key] = {
            'result': None,
            'timestamp': datetime.now()
            # Missing 'event' key
        }
        
        # Should not crash when event is missing
        await locate_service.handle_packet(sample_locate_reply)
        
        # Should still update result
        assert locate_service.pending_locates[request_key]['result'] is not None
    
    async def test_no_gateway_in_create_reply(self, mock_state_manager):
        """Test creating locate reply without gateway."""
        service = LocateService(mock_state_manager, None)
        
        request = LocatePacket(
            packet_type=PacketType.LOCATE_REQ,
            ttl=200,
            originator_mud="RemoteMUD",
            originator_user="requester",
            target_mud="TestMUD",
            target_user="",
            user_to_locate="testuser"
        )
        
        result_data = {'found': True, 'mud': 'TestMUD', 'user': 'testuser'}
        reply = service._create_locate_reply(request, result_data)
        
        assert reply.originator_mud == ""  # Empty when no gateway
    
    async def test_empty_sessions_dict(self, locate_service):
        """Test behavior with completely empty sessions."""
        locate_service.state_manager.sessions = {}
        
        result = await locate_service._search_local_user("anyone")
        assert result is None