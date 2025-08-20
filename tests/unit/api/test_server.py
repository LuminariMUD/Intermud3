"""Tests for the main API server."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from aiohttp import web, WSMsgType
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from src.api.server import APIServer
from src.api.session import Session
from src.config.models import APIConfig, WebSocketConfig, TCPConfig
from src.api.protocol import JSONRPCError


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        self.closed = False
        self.sent_messages = []
        self.exception_value = None
    
    async def close(self, code=None, message=None):
        self.closed = True
    
    async def send_str(self, data):
        self.sent_messages.append(data)
    
    async def ping(self):
        if self.closed:
            raise ConnectionError("WebSocket closed")
    
    def exception(self):
        return self.exception_value


@pytest.fixture
def api_config():
    """Create API configuration for testing."""
    return APIConfig(
        host="127.0.0.1",
        port=8080,
        websocket=WebSocketConfig(
            enabled=True,
            ping_interval=30
        ),
        tcp=TCPConfig(
            enabled=False,
            host="127.0.0.1",
            port=8081
        )
    )


@pytest.fixture
def mock_gateway():
    """Create mock gateway for testing."""
    gateway = MagicMock()
    gateway.is_connected.return_value = True
    return gateway


@pytest.fixture
def server(api_config, mock_gateway):
    """Create API server for testing."""
    return APIServer(api_config, mock_gateway)


class TestAPIServer:
    """Test APIServer class."""
    
    @pytest.mark.asyncio
    async def test_server_initialization(self, api_config, mock_gateway):
        """Test server initialization."""
        server = APIServer(api_config, mock_gateway)
        
        assert server.config == api_config
        assert server.gateway == mock_gateway
        assert server.app is None
        assert server.runner is None
        assert server.site is None
        assert len(server._websockets) == 0
    
    @pytest.mark.asyncio
    @patch('src.api.server.event_dispatcher')
    @patch('src.api.server.message_queue_manager')
    @patch('src.api.server.event_bridge')
    async def test_server_start_stop(self, mock_bridge, mock_queue, mock_dispatcher, server):
        """Test starting and stopping the server."""
        # Mock the event system components
        mock_dispatcher.start = AsyncMock()
        mock_dispatcher.stop = AsyncMock()
        mock_queue.start = AsyncMock()
        mock_queue.stop = AsyncMock()
        mock_bridge.start = MagicMock()
        mock_bridge.stop = MagicMock()
        
        # Mock aiohttp components
        with patch('aiohttp.web.AppRunner') as mock_runner_class, \
             patch('aiohttp.web.TCPSite') as mock_site_class:
            
            mock_runner = AsyncMock()
            mock_site = AsyncMock()
            mock_runner_class.return_value = mock_runner
            mock_site_class.return_value = mock_site
            
            # Start server
            await server.start()
            
            # Verify event system started
            mock_dispatcher.start.assert_called_once()
            mock_queue.start.assert_called_once()
            mock_bridge.start.assert_called_once()
            
            # Verify aiohttp components started
            mock_runner.setup.assert_called_once()
            mock_site.start.assert_called_once()
            
            # Stop server
            await server.stop()
            
            # Verify cleanup
            mock_site.stop.assert_called_once()
            mock_runner.cleanup.assert_called_once()
            mock_bridge.stop.assert_called_once()
            mock_dispatcher.stop.assert_called_once()
            mock_queue.stop.assert_called_once()
    
    def test_setup_routes(self, server):
        """Test route setup."""
        server.app = web.Application()
        server._setup_routes()
        
        # Check that routes were added
        route_paths = [resource.canonical for resource in server.app.router.resources()]
        
        assert "/ws" in route_paths
        assert "/health" in route_paths
        assert "/health/live" in route_paths
        assert "/health/ready" in route_paths
        assert "/metrics" in route_paths
        assert "/api/info" in route_paths
    
    def test_setup_middleware(self, server):
        """Test middleware setup."""
        server.app = web.Application()
        server._setup_middleware()
        
        # Check that middleware was added
        assert len(server.app.middlewares) == 1
    
    @pytest.mark.asyncio
    async def test_websocket_authentication_via_header(self, server):
        """Test WebSocket authentication via header."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "test-api-key"
        
        mock_session = MagicMock(spec=Session)
        mock_session.mud_name = "TestMUD"
        
        # Mock WebSocket
        mock_ws = MockWebSocket()
        
        # Mock message iteration (empty - connection closes immediately)
        async def mock_aiter():
            return
            yield  # unreachable
        mock_ws.__aiter__ = mock_aiter
        
        with patch('aiohttp.web.WebSocketResponse', return_value=mock_ws), \
             patch.object(server.session_manager, 'authenticate', return_value=mock_session) as mock_auth, \
             patch('src.api.server.event_dispatcher') as mock_dispatcher:
            
            mock_dispatcher.register_session = MagicMock()
            mock_dispatcher.unregister_session = MagicMock()
            
            result = await server.handle_websocket(mock_request)
            
            assert result == mock_ws
            mock_auth.assert_called_once_with("test-api-key")
            mock_dispatcher.register_session.assert_called_once_with(mock_session)
    
    @pytest.mark.asyncio
    async def test_websocket_authentication_via_message(self, server):
        """Test WebSocket authentication via first message."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None  # No header auth
        
        mock_session = MagicMock(spec=Session)
        mock_session.mud_name = "TestMUD"
        
        # Mock WebSocket
        mock_ws = MockWebSocket()
        
        # Mock authentication message
        auth_msg = MagicMock()
        auth_msg.type = WSMsgType.TEXT
        auth_msg.data = json.dumps({
            "jsonrpc": "2.0",
            "method": "authenticate",
            "params": {"api_key": "test-api-key"},
            "id": "1"
        })
        
        # Mock message iteration
        async def mock_aiter():
            yield auth_msg
        mock_ws.__aiter__ = mock_aiter
        
        with patch('aiohttp.web.WebSocketResponse', return_value=mock_ws), \
             patch.object(server.session_manager, 'authenticate', return_value=mock_session) as mock_auth, \
             patch('src.api.server.event_dispatcher') as mock_dispatcher:
            
            mock_dispatcher.register_session = MagicMock()
            mock_dispatcher.unregister_session = MagicMock()
            
            result = await server.handle_websocket(mock_request)
            
            assert result == mock_ws
            mock_auth.assert_called_once_with("test-api-key")
            
            # Check that success response was sent
            assert len(mock_ws.sent_messages) == 1
            response_data = json.loads(mock_ws.sent_messages[0])
            assert response_data["result"]["status"] == "authenticated"
    
    @pytest.mark.asyncio
    async def test_websocket_authentication_failure(self, server):
        """Test WebSocket authentication failure."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        
        # Mock WebSocket
        mock_ws = MockWebSocket()
        
        # Mock authentication message with missing api_key
        auth_msg = MagicMock()
        auth_msg.type = WSMsgType.TEXT
        auth_msg.data = json.dumps({
            "jsonrpc": "2.0",
            "method": "authenticate",
            "params": {},
            "id": "1"
        })
        
        # Mock message iteration
        async def mock_aiter():
            yield auth_msg
        mock_ws.__aiter__ = mock_aiter
        
        with patch('aiohttp.web.WebSocketResponse', return_value=mock_ws):
            result = await server.handle_websocket(mock_request)
            
            assert result == mock_ws
            
            # Check that error response was sent
            assert len(mock_ws.sent_messages) == 1
            response_data = json.loads(mock_ws.sent_messages[0])
            assert response_data["error"]["code"] == JSONRPCError.INVALID_PARAMS
    
    @pytest.mark.asyncio
    async def test_websocket_unauthenticated_request(self, server):
        """Test WebSocket request without authentication."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        
        # Mock WebSocket
        mock_ws = MockWebSocket()
        
        # Mock unauthenticated request
        request_msg = MagicMock()
        request_msg.type = WSMsgType.TEXT
        request_msg.data = json.dumps({
            "jsonrpc": "2.0",
            "method": "tell",
            "params": {"target_user": "alice", "message": "hello"},
            "id": "1"
        })
        
        # Mock message iteration
        async def mock_aiter():
            yield request_msg
        mock_ws.__aiter__ = mock_aiter
        
        with patch('aiohttp.web.WebSocketResponse', return_value=mock_ws):
            result = await server.handle_websocket(mock_request)
            
            assert result == mock_ws
            
            # Check that error response was sent
            assert len(mock_ws.sent_messages) == 1
            response_data = json.loads(mock_ws.sent_messages[0])
            assert response_data["error"]["code"] == JSONRPCError.INVALID_REQUEST
            assert "Not authenticated" in response_data["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_websocket_invalid_json(self, server):
        """Test WebSocket with invalid JSON."""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        
        # Mock WebSocket
        mock_ws = MockWebSocket()
        
        # Mock invalid JSON message
        invalid_msg = MagicMock()
        invalid_msg.type = WSMsgType.TEXT
        invalid_msg.data = "invalid json {"
        
        # Mock message iteration
        async def mock_aiter():
            yield invalid_msg
        mock_ws.__aiter__ = mock_aiter
        
        with patch('aiohttp.web.WebSocketResponse', return_value=mock_ws):
            result = await server.handle_websocket(mock_request)
            
            assert result == mock_ws
            
            # Check that parse error response was sent
            assert len(mock_ws.sent_messages) == 1
            response_data = json.loads(mock_ws.sent_messages[0])
            assert response_data["error"]["code"] == JSONRPCError.PARSE_ERROR
    
    @pytest.mark.asyncio
    async def test_process_message_rate_limit(self, server):
        """Test message processing with rate limiting."""
        mock_session = MagicMock(spec=Session)
        mock_session.check_rate_limit = AsyncMock(return_value=False)
        mock_session.send = AsyncMock()
        
        with patch.object(server.protocol, 'parse_request') as mock_parse:
            mock_request = MagicMock()
            mock_request.method = "tell"
            mock_request.id = "123"
            mock_parse.return_value = mock_request
            
            await server.process_message(mock_session, '{"test": "message"}')
            
            # Should send rate limit error
            mock_session.send.assert_called_once()
            call_args = mock_session.send.call_args[0][0]
            response_data = json.loads(call_args)
            assert response_data["error"]["message"] == "Rate limit exceeded"
    
    @pytest.mark.asyncio
    async def test_process_message_unknown_method(self, server):
        """Test message processing with unknown method."""
        mock_session = MagicMock(spec=Session)
        mock_session.check_rate_limit = AsyncMock(return_value=True)
        mock_session.send = AsyncMock()
        mock_session.update_activity = MagicMock()
        
        with patch.object(server.protocol, 'parse_request') as mock_parse:
            mock_request = MagicMock()
            mock_request.method = "unknown_method"
            mock_request.id = "123"
            mock_parse.return_value = mock_request
            
            await server.process_message(mock_session, '{"test": "message"}')
            
            # Should send method not found error
            mock_session.send.assert_called_once()
            call_args = mock_session.send.call_args[0][0]
            response_data = json.loads(call_args)
            assert response_data["error"]["code"] == JSONRPCError.METHOD_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_process_message_success(self, server):
        """Test successful message processing."""
        mock_session = MagicMock(spec=Session)
        mock_session.check_rate_limit = AsyncMock(return_value=True)
        mock_session.send = AsyncMock()
        mock_session.update_activity = MagicMock()
        
        # Mock handler
        async def mock_handler(session, params):
            return {"status": "success"}
        
        with patch.object(server.protocol, 'parse_request') as mock_parse, \
             patch.object(server, '_get_handler', return_value=mock_handler):
            
            mock_request = MagicMock()
            mock_request.method = "ping"
            mock_request.params = {}
            mock_request.id = "123"
            mock_parse.return_value = mock_request
            
            await server.process_message(mock_session, '{"test": "message"}')
            
            # Should send success response
            mock_session.send.assert_called_once()
            call_args = mock_session.send.call_args[0][0]
            response_data = json.loads(call_args)
            assert response_data["result"]["status"] == "success"
    
    def test_get_handler(self, server):
        """Test handler retrieval."""
        ping_handler = server._get_handler("ping")
        assert ping_handler is not None
        
        status_handler = server._get_handler("status")
        assert status_handler is not None
        
        unknown_handler = server._get_handler("unknown")
        assert unknown_handler is None
    
    @pytest.mark.asyncio
    async def test_ping_handler(self, server):
        """Test ping handler."""
        mock_session = MagicMock(spec=Session)
        
        result = await server._handle_ping(mock_session, {})
        
        assert result["pong"] is True
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_status_handler(self, server):
        """Test status handler."""
        mock_session = MagicMock(spec=Session)
        mock_session.mud_name = "TestMUD"
        mock_session.session_id = "test-session-123"
        mock_session.connected_at.timestamp.return_value = 1000.0
        
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.time.return_value = 2000.0
            
            result = await server._handle_status(mock_session, {})
            
            assert result["connected"] is True
            assert result["mud_name"] == "TestMUD"
            assert result["session_id"] == "test-session-123"
            assert result["uptime"] == 1000.0
    
    @pytest.mark.asyncio
    async def test_cleanup_sessions_task(self, server):
        """Test session cleanup background task."""
        server.session_manager.cleanup_expired = AsyncMock()
        server._shutdown_event.set()  # Stop the loop immediately
        
        await server._cleanup_sessions()
        
        # Should have called cleanup at least once
        server.session_manager.cleanup_expired.assert_called()
    
    @pytest.mark.asyncio
    async def test_ping_websockets_task(self, server):
        """Test WebSocket ping background task."""
        mock_ws1 = MockWebSocket()
        mock_ws2 = MockWebSocket()
        mock_ws2.closed = True  # This one will fail ping
        
        server._websockets.add(mock_ws1)
        server._websockets.add(mock_ws2)
        
        server._shutdown_event.set()  # Stop the loop immediately
        
        await server._ping_websockets()
        
        # Working WebSocket should remain
        assert mock_ws1 in server._websockets
        # Failed WebSocket should be removed
        assert mock_ws2 not in server._websockets
    
    @pytest.mark.asyncio
    async def test_process_event_queues_task(self, server):
        """Test event queue processing background task."""
        mock_session = MagicMock(spec=Session)
        mock_session.is_connected.return_value = True
        mock_session.message_queue = MagicMock()
        mock_session.flush_queue = AsyncMock()
        
        server.session_manager.get_all_sessions = MagicMock(return_value=[mock_session])
        server._shutdown_event.set()  # Stop the loop immediately
        
        await server._process_event_queues()
        
        # Should have called flush_queue
        mock_session.flush_queue.assert_called()
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, server):
        """Test health check endpoint."""
        mock_request = MagicMock()
        server.session_manager.get_active_count = MagicMock(return_value=5)
        
        response = await server.handle_health(mock_request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert data["status"] == "healthy"
        assert data["service"] == "i3-gateway-api"
        assert data["active_sessions"] == 5
    
    @pytest.mark.asyncio
    async def test_liveness_endpoint(self, server):
        """Test liveness probe endpoint."""
        mock_request = MagicMock()
        
        response = await server.handle_liveness(mock_request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert data["status"] == "alive"
    
    @pytest.mark.asyncio
    async def test_readiness_endpoint_ready(self, server):
        """Test readiness probe when gateway is connected."""
        mock_request = MagicMock()
        server.gateway.is_connected.return_value = True
        
        response = await server.handle_readiness(mock_request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert data["status"] == "ready"
    
    @pytest.mark.asyncio
    async def test_readiness_endpoint_not_ready(self, server):
        """Test readiness probe when gateway is not connected."""
        mock_request = MagicMock()
        server.gateway.is_connected.return_value = False
        
        response = await server.handle_readiness(mock_request)
        
        assert response.status == 503
        data = json.loads(response.text)
        assert data["status"] == "not_ready"
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, server):
        """Test metrics endpoint."""
        mock_request = MagicMock()
        server.session_manager.get_active_count = MagicMock(return_value=3)
        
        response = await server.handle_metrics(mock_request)
        
        assert response.status == 200
        assert response.content_type == "text/plain"
        assert "api_websocket_connections 0" in response.text
        assert "api_active_sessions 3" in response.text
    
    @pytest.mark.asyncio
    async def test_api_info_endpoint(self, server):
        """Test API info endpoint."""
        mock_request = MagicMock()
        
        response = await server.handle_api_info(mock_request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert data["version"] == "1.0.0"
        assert data["protocol"] == "JSON-RPC 2.0"
        assert "websocket" in data["transports"]
        assert data["authentication"] == "api_key"


class TestAPIServerIntegration(AioHTTPTestCase):
    """Integration tests for API server."""
    
    async def get_application(self):
        """Create application for testing."""
        config = APIConfig(
            host="127.0.0.1",
            port=8080,
            websocket=WebSocketConfig(enabled=True)
        )
        
        self.server = APIServer(config)
        
        # Mock event system components
        with patch('src.api.server.event_dispatcher'), \
             patch('src.api.server.message_queue_manager'), \
             patch('src.api.server.event_bridge'):
            
            await self.server.start()
            return self.server.app
    
    async def tearDown(self):
        """Clean up after tests."""
        await self.server.stop()
        await super().tearDown()
    
    @unittest_run_loop
    async def test_health_endpoint_integration(self):
        """Test health endpoint integration."""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["status"] == "healthy"
    
    @unittest_run_loop
    async def test_liveness_endpoint_integration(self):
        """Test liveness endpoint integration."""
        resp = await self.client.request("GET", "/health/live")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["status"] == "alive"
    
    @unittest_run_loop
    async def test_metrics_endpoint_integration(self):
        """Test metrics endpoint integration."""
        resp = await self.client.request("GET", "/metrics")
        assert resp.status == 200
        assert resp.content_type == "text/plain"
        
        text = await resp.text()
        assert "api_websocket_connections" in text
        assert "api_active_sessions" in text