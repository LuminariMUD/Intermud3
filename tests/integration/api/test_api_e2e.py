"""End-to-end API integration tests."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from src.api.server import APIServer
from src.api.session import SessionManager
from src.config.models import APIConfig, WebSocketConfig


class TestAPIEndToEnd(AioHTTPTestCase):
    """End-to-end API tests."""

    async def get_application(self):
        """Create application for testing."""
        self.config = APIConfig(
            host="127.0.0.1", port=8080, websocket=WebSocketConfig(enabled=True)
        )

        # Mock gateway
        self.mock_gateway = MagicMock()
        self.mock_gateway.is_connected.return_value = True
        self.mock_gateway.send_packet = AsyncMock()

        # Create server
        self.api_server = APIServer(self.config, self.mock_gateway)

        # Mock event system components to avoid startup issues
        with (
            patch("src.api.server.event_dispatcher") as mock_dispatcher,
            patch("src.api.server.message_queue_manager") as mock_queue,
            patch("src.api.server.event_bridge") as mock_bridge,
        ):

            mock_dispatcher.start = AsyncMock()
            mock_dispatcher.stop = AsyncMock()
            mock_queue.start = AsyncMock()
            mock_queue.stop = AsyncMock()
            mock_bridge.start = MagicMock()
            mock_bridge.stop = MagicMock()

            await self.api_server.start()
            return self.api_server.app

    async def tearDown(self):
        """Clean up after tests."""
        await self.api_server.stop()
        await super().tearDown()

    @unittest_run_loop
    async def test_health_endpoints(self):
        """Test health check endpoints."""
        # Test main health endpoint
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200

        data = await resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "i3-gateway-api"
        assert "websocket_connections" in data
        assert "active_sessions" in data

        # Test liveness probe
        resp = await self.client.request("GET", "/health/live")
        assert resp.status == 200

        data = await resp.json()
        assert data["status"] == "alive"

        # Test readiness probe
        resp = await self.client.request("GET", "/health/ready")
        assert resp.status == 200

        data = await resp.json()
        assert data["status"] == "ready"

    @unittest_run_loop
    async def test_metrics_endpoint(self):
        """Test metrics endpoint."""
        resp = await self.client.request("GET", "/metrics")
        assert resp.status == 200
        assert resp.content_type == "text/plain"

        text = await resp.text()
        assert "api_websocket_connections" in text
        assert "api_active_sessions" in text

    @unittest_run_loop
    async def test_api_info_endpoint(self):
        """Test API info endpoint."""
        resp = await self.client.request("GET", "/api/info")
        assert resp.status == 200

        data = await resp.json()
        assert data["version"] == "1.0.0"
        assert data["protocol"] == "JSON-RPC 2.0"
        assert "websocket" in data["transports"]
        assert data["authentication"] == "api_key"


@pytest.mark.asyncio
async def test_websocket_authentication_flow():
    """Test WebSocket authentication flow."""
    config = APIConfig(host="127.0.0.1", port=8080, websocket=WebSocketConfig(enabled=True))

    mock_gateway = MagicMock()
    mock_gateway.is_connected.return_value = True

    server = APIServer(config, mock_gateway)

    # Mock session manager authentication
    mock_session = MagicMock()
    mock_session.mud_name = "TestMUD"
    mock_session.session_id = "test-session-123"
    mock_session.websocket = None

    with patch.object(
        server.session_manager, "authenticate", return_value=mock_session
    ) as mock_auth:
        with patch("src.api.server.event_dispatcher") as mock_dispatcher:
            mock_dispatcher.register_session = MagicMock()

            # Create mock request with authentication header
            mock_request = MagicMock()
            mock_request.headers.get.return_value = "test-auth-credential"

            # Mock WebSocket
            mock_ws = MagicMock()
            mock_ws.send_str = AsyncMock()

            # Mock message iteration (empty - connection closes)
            async def mock_aiter():
                return
                yield  # unreachable

            mock_ws.__aiter__ = mock_aiter

            with patch("aiohttp.web.WebSocketResponse", return_value=mock_ws):
                result = await server.handle_websocket(mock_request)

                # Verify authentication was called
                mock_auth.assert_called_once_with("test-auth-credential")

                # Verify session was registered with event dispatcher
                mock_dispatcher.register_session.assert_called_once_with(mock_session)


@pytest.mark.asyncio
async def test_websocket_message_processing():
    """Test WebSocket message processing flow."""
    config = APIConfig(host="127.0.0.1", port=8080, websocket=WebSocketConfig(enabled=True))

    mock_gateway = MagicMock()
    mock_gateway.is_connected.return_value = True
    mock_gateway.send_packet = AsyncMock()

    server = APIServer(config, mock_gateway)

    # Mock authenticated session
    mock_session = MagicMock()
    mock_session.mud_name = "TestMUD"
    mock_session.session_id = "test-session-123"
    mock_session.check_rate_limit = AsyncMock(return_value=True)
    mock_session.update_activity = MagicMock()
    mock_session.send = AsyncMock()

    # Mock a tell message
    tell_message = {
        "jsonrpc": "2.0",
        "method": "tell",
        "params": {"target_mud": "OtherMUD", "target_user": "alice", "message": "Hello there!"},
        "id": "123",
    }

    with patch.object(server, "_get_handler") as mock_get_handler:
        # Mock tell handler
        async def mock_tell_handler(session, params):
            return {"status": "sent", "message_id": "msg-456"}

        mock_get_handler.return_value = mock_tell_handler

        await server.process_message(mock_session, json.dumps(tell_message))

        # Verify handler was called
        mock_get_handler.assert_called_once_with("tell")

        # Verify session was updated
        mock_session.update_activity.assert_called_once()
        mock_session.check_rate_limit.assert_called_once_with("tell")

        # Verify response was sent
        mock_session.send.assert_called_once()
        sent_response = json.loads(mock_session.send.call_args[0][0])
        assert sent_response["result"]["status"] == "sent"
        assert sent_response["id"] == "123"


@pytest.mark.asyncio
async def test_session_management_flow():
    """Test session management lifecycle."""
    config = APIConfig(host="127.0.0.1", port=8080)

    session_manager = SessionManager(config)

    # Mock authentication
    with patch.object(session_manager.auth, "authenticate") as mock_auth:
        mock_auth.return_value = {"mud_name": "TestMUD", "permissions": {"tell", "channel", "who"}}

        # Authenticate and create session
        session = await session_manager.authenticate("test-auth-credential")

        assert session is not None
        assert session.mud_name == "TestMUD"
        assert session.session_id in session_manager.sessions
        assert "tell" in session.permissions
        assert "channel" in session.permissions
        assert "who" in session.permissions

        # Test session retrieval
        retrieved = session_manager.get_session(session.session_id)
        assert retrieved == session

        # Test session cleanup
        await session_manager.disconnect(session)
        assert session.session_id not in session_manager.sessions


@pytest.mark.asyncio
async def test_event_flow_integration():
    """Test event flow from packet to session."""
    from src.api.event_bridge import EventBridge
    from src.api.events import EventDispatcher, EventType

    # Create components
    dispatcher = EventDispatcher()
    bridge = EventBridge()

    # Mock session
    mock_session = MagicMock()
    mock_session.session_id = "test-session-123"
    mock_session.mud_name = "TestMUD"
    mock_session.is_connected.return_value = True
    mock_session.permissions = {"tell", "channel"}
    mock_session.subscriptions = {"chat"}
    mock_session.send = AsyncMock()

    # Start components
    await dispatcher.start()
    bridge.start()

    try:
        # Register session
        dispatcher.register_session(mock_session)

        # Create and dispatch event
        event = dispatcher.create_event(
            EventType.TELL_RECEIVED,
            {
                "from_mud": "OtherMUD",
                "from_user": "alice",
                "to_user": "bob",
                "message": "Hello!",
                "visname": "Alice",
            },
            priority=3,
        )

        await dispatcher.dispatch(event)

        # Give time for processing
        await asyncio.sleep(0.1)

        # Verify session received the event
        assert mock_session.send.called
        sent_data = json.loads(mock_session.send.call_args[0][0])
        assert sent_data["method"] == "tell_received"
        assert sent_data["params"]["from_user"] == "alice"
        assert sent_data["params"]["message"] == "Hello!"

    finally:
        await dispatcher.stop()
        bridge.stop()


@pytest.mark.asyncio
async def test_error_handling_integration():
    """Test error handling across the API stack."""
    config = APIConfig(host="127.0.0.1", port=8080)

    mock_gateway = MagicMock()
    mock_gateway.is_connected.return_value = True
    mock_gateway.send_packet = AsyncMock(side_effect=Exception("Gateway error"))

    server = APIServer(config, mock_gateway)

    # Mock session
    mock_session = MagicMock()
    mock_session.check_rate_limit = AsyncMock(return_value=True)
    mock_session.update_activity = MagicMock()
    mock_session.send = AsyncMock()
    mock_session.has_permission = MagicMock(return_value=True)

    # Create tell message that will cause gateway error
    tell_message = {
        "jsonrpc": "2.0",
        "method": "tell",
        "params": {"target_mud": "OtherMUD", "target_user": "alice", "message": "Hello!"},
        "id": "123",
    }

    # Mock the handler to use real implementation that will hit the gateway
    from src.api.handlers.communication import CommunicationHandler

    handler = CommunicationHandler(mock_gateway)

    with patch.object(server, "_get_handler", return_value=handler.tell):
        await server.process_message(mock_session, json.dumps(tell_message))

        # Verify error response was sent
        mock_session.send.assert_called_once()
        sent_response = json.loads(mock_session.send.call_args[0][0])
        assert "error" in sent_response
        assert sent_response["error"]["code"] == -32603  # Internal error


@pytest.mark.asyncio
async def test_rate_limiting_integration():
    """Test rate limiting integration."""
    config = APIConfig(host="127.0.0.1", port=8080)

    server = APIServer(config)

    # Mock session with rate limiting
    mock_session = MagicMock()
    mock_session.check_rate_limit = AsyncMock(return_value=False)  # Rate limited
    mock_session.update_activity = MagicMock()
    mock_session.send = AsyncMock()

    # Create message
    message = {
        "jsonrpc": "2.0",
        "method": "tell",
        "params": {"target_mud": "OtherMUD", "target_user": "alice", "message": "Hello!"},
        "id": "123",
    }

    await server.process_message(mock_session, json.dumps(message))

    # Verify rate limit error was sent
    mock_session.send.assert_called_once()
    sent_response = json.loads(mock_session.send.call_args[0][0])
    assert "error" in sent_response
    assert "Rate limit exceeded" in sent_response["error"]["message"]


@pytest.mark.asyncio
async def test_permission_checking_integration():
    """Test permission checking integration."""
    config = APIConfig(host="127.0.0.1", port=8080)

    mock_gateway = MagicMock()
    server = APIServer(config, mock_gateway)

    # Mock session without tell permission
    mock_session = MagicMock()
    mock_session.check_rate_limit = AsyncMock(return_value=True)
    mock_session.update_activity = MagicMock()
    mock_session.send = AsyncMock()
    mock_session.has_permission = MagicMock(return_value=False)  # No permission

    # Create tell message
    tell_message = {
        "jsonrpc": "2.0",
        "method": "tell",
        "params": {"target_mud": "OtherMUD", "target_user": "alice", "message": "Hello!"},
        "id": "123",
    }

    # Mock the handler
    from src.api.handlers.communication import CommunicationHandler

    handler = CommunicationHandler(mock_gateway)

    with patch.object(server, "_get_handler", return_value=handler.tell):
        await server.process_message(mock_session, json.dumps(tell_message))

        # Verify permission error was sent
        mock_session.send.assert_called_once()
        sent_response = json.loads(mock_session.send.call_args[0][0])
        assert "error" in sent_response


@pytest.mark.asyncio
async def test_concurrent_sessions():
    """Test handling multiple concurrent sessions."""
    config = APIConfig(host="127.0.0.1", port=8080)

    session_manager = SessionManager(config)

    # Mock authentication for multiple sessions
    with patch.object(session_manager.auth, "authenticate") as mock_auth:
        mock_auth.return_value = {"mud_name": "TestMUD", "permissions": {"tell", "channel"}}

        # Create multiple sessions
        sessions = []
        for i in range(5):
            session = await session_manager.authenticate(f"test-credential-{i}")
            sessions.append(session)

        # Verify all sessions are tracked
        assert len(session_manager.sessions) == 5

        # Verify each session is unique
        session_ids = [s.session_id for s in sessions]
        assert len(set(session_ids)) == 5  # All unique

        # Test cleanup of all sessions
        await session_manager.cleanup()
        assert len(session_manager.sessions) == 0
