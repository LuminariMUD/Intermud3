"""Tests for JSON-RPC protocol implementation."""

import json
import pytest
from unittest.mock import MagicMock

from src.api.protocol import (
    JSONRPCProtocol,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    JSONRPCParseError,
    JSONRPCInvalidRequestError,
    JSONRPCMethodNotFoundError,
    JSONRPCInvalidParamsError,
    JSONRPCInternalError
)


class TestJSONRPCRequest:
    """Test JSONRPCRequest class."""
    
    def test_request_creation(self):
        """Test creating a JSON-RPC request."""
        request = JSONRPCRequest(
            method="tell",
            params={"target_user": "alice", "message": "hello"},
            id="123"
        )
        
        assert request.method == "tell"
        assert request.params["target_user"] == "alice"
        assert request.id == "123"
    
    def test_request_to_dict(self):
        """Test converting request to dictionary."""
        request = JSONRPCRequest(
            method="tell",
            params={"target_user": "alice", "message": "hello"},
            id="123"
        )
        
        data = request.to_dict()
        
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "tell"
        assert data["params"]["target_user"] == "alice"
        assert data["id"] == "123"
    
    def test_request_to_json(self):
        """Test converting request to JSON string."""
        request = JSONRPCRequest(
            method="tell",
            params={"target_user": "alice", "message": "hello"},
            id="123"
        )
        
        json_str = request.to_json()
        data = json.loads(json_str)
        
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "tell"
        assert data["params"]["target_user"] == "alice"
        assert data["id"] == "123"
    
    def test_notification_request(self):
        """Test creating a notification (no id)."""
        request = JSONRPCRequest(
            method="heartbeat",
            params={}
        )
        
        assert request.id is None
        assert request.is_notification()
        
        data = request.to_dict()
        assert "id" not in data


class TestJSONRPCResponse:
    """Test JSONRPCResponse class."""
    
    def test_success_response(self):
        """Test creating a success response."""
        response = JSONRPCResponse(
            result={"status": "sent"},
            id="123"
        )
        
        assert response.result == {"status": "sent"}
        assert response.error is None
        assert response.id == "123"
    
    def test_error_response(self):
        """Test creating an error response."""
        error = JSONRPCError(
            code=-32600,
            message="Invalid Request",
            data={"extra": "info"}
        )
        response = JSONRPCResponse(
            error=error,
            id="123"
        )
        
        assert response.result is None
        assert response.error.code == -32600
        assert response.error.message == "Invalid Request"
        assert response.id == "123"
    
    def test_response_to_dict(self):
        """Test converting response to dictionary."""
        response = JSONRPCResponse(
            result={"status": "sent"},
            id="123"
        )
        
        data = response.to_dict()
        
        assert data["jsonrpc"] == "2.0"
        assert data["result"]["status"] == "sent"
        assert data["id"] == "123"
        assert "error" not in data
    
    def test_error_response_to_dict(self):
        """Test converting error response to dictionary."""
        error = JSONRPCError(
            code=-32600,
            message="Invalid Request"
        )
        response = JSONRPCResponse(
            error=error,
            id="123"
        )
        
        data = response.to_dict()
        
        assert data["jsonrpc"] == "2.0"
        assert data["error"]["code"] == -32600
        assert data["error"]["message"] == "Invalid Request"
        assert data["id"] == "123"
        assert "result" not in data


class TestJSONRPCError:
    """Test JSONRPCError class."""
    
    def test_error_creation(self):
        """Test creating an error."""
        error = JSONRPCError(
            code=-32600,
            message="Invalid Request",
            data={"detail": "Missing required field"}
        )
        
        assert error.code == -32600
        assert error.message == "Invalid Request"
        assert error.data["detail"] == "Missing required field"
    
    def test_error_to_dict(self):
        """Test converting error to dictionary."""
        error = JSONRPCError(
            code=-32600,
            message="Invalid Request",
            data={"detail": "Missing required field"}
        )
        
        data = error.to_dict()
        
        assert data["code"] == -32600
        assert data["message"] == "Invalid Request"
        assert data["data"]["detail"] == "Missing required field"
    
    def test_error_without_data(self):
        """Test error without data field."""
        error = JSONRPCError(
            code=-32600,
            message="Invalid Request"
        )
        
        data = error.to_dict()
        
        assert data["code"] == -32600
        assert data["message"] == "Invalid Request"
        assert "data" not in data
    
    def test_predefined_error_codes(self):
        """Test predefined error code constants."""
        assert JSONRPCError.PARSE_ERROR == -32700
        assert JSONRPCError.INVALID_REQUEST == -32600
        assert JSONRPCError.METHOD_NOT_FOUND == -32601
        assert JSONRPCError.INVALID_PARAMS == -32602
        assert JSONRPCError.INTERNAL_ERROR == -32603


class TestJSONRPCExceptions:
    """Test JSON-RPC exception classes."""
    
    def test_parse_error(self):
        """Test JSONRPCParseError."""
        error = JSONRPCParseError("Invalid JSON syntax")
        
        assert error.code == JSONRPCError.PARSE_ERROR
        assert error.message == "Parse error"
        assert error.data == "Invalid JSON syntax"
    
    def test_invalid_request_error(self):
        """Test JSONRPCInvalidRequestError."""
        error = JSONRPCInvalidRequestError("Missing method field")
        
        assert error.code == JSONRPCError.INVALID_REQUEST
        assert error.message == "Invalid Request"
        assert error.data == "Missing method field"
    
    def test_method_not_found_error(self):
        """Test JSONRPCMethodNotFoundError."""
        error = JSONRPCMethodNotFoundError("unknown_method")
        
        assert error.code == JSONRPCError.METHOD_NOT_FOUND
        assert error.message == "Method not found"
        assert error.data == "unknown_method"
    
    def test_invalid_params_error(self):
        """Test JSONRPCInvalidParamsError."""
        error = JSONRPCInvalidParamsError("Missing required parameter: target_user")
        
        assert error.code == JSONRPCError.INVALID_PARAMS
        assert error.message == "Invalid params"
        assert error.data == "Missing required parameter: target_user"
    
    def test_internal_error(self):
        """Test JSONRPCInternalError."""
        error = JSONRPCInternalError("Database connection failed")
        
        assert error.code == JSONRPCError.INTERNAL_ERROR
        assert error.message == "Internal error"
        assert error.data == "Database connection failed"


class TestJSONRPCProtocol:
    """Test JSONRPCProtocol class."""
    
    @pytest.fixture
    def protocol(self):
        """Create protocol instance for testing."""
        return JSONRPCProtocol()
    
    def test_parse_valid_request(self, protocol):
        """Test parsing a valid JSON-RPC request."""
        json_str = json.dumps({
            "jsonrpc": "2.0",
            "method": "tell",
            "params": {"target_user": "alice", "message": "hello"},
            "id": "123"
        })
        
        request = protocol.parse_request(json_str)
        
        assert request.method == "tell"
        assert request.params["target_user"] == "alice"
        assert request.id == "123"
    
    def test_parse_notification(self, protocol):
        """Test parsing a notification (no id)."""
        json_str = json.dumps({
            "jsonrpc": "2.0",
            "method": "heartbeat",
            "params": {}
        })
        
        request = protocol.parse_request(json_str)
        
        assert request.method == "heartbeat"
        assert request.id is None
        assert request.is_notification()
    
    def test_parse_invalid_json(self, protocol):
        """Test parsing invalid JSON."""
        with pytest.raises(JSONRPCParseError):
            protocol.parse_request("{'invalid': json}")
    
    def test_parse_missing_jsonrpc(self, protocol):
        """Test parsing request without jsonrpc field."""
        json_str = json.dumps({
            "method": "tell",
            "params": {},
            "id": "123"
        })
        
        with pytest.raises(JSONRPCInvalidRequestError):
            protocol.parse_request(json_str)
    
    def test_parse_wrong_jsonrpc_version(self, protocol):
        """Test parsing request with wrong jsonrpc version."""
        json_str = json.dumps({
            "jsonrpc": "1.0",
            "method": "tell",
            "params": {},
            "id": "123"
        })
        
        with pytest.raises(JSONRPCInvalidRequestError):
            protocol.parse_request(json_str)
    
    def test_parse_missing_method(self, protocol):
        """Test parsing request without method field."""
        json_str = json.dumps({
            "jsonrpc": "2.0",
            "params": {},
            "id": "123"
        })
        
        with pytest.raises(JSONRPCInvalidRequestError):
            protocol.parse_request(json_str)
    
    def test_parse_invalid_method_type(self, protocol):
        """Test parsing request with non-string method."""
        json_str = json.dumps({
            "jsonrpc": "2.0",
            "method": 123,
            "params": {},
            "id": "123"
        })
        
        with pytest.raises(JSONRPCInvalidRequestError):
            protocol.parse_request(json_str)
    
    def test_format_success_response(self, protocol):
        """Test formatting a success response."""
        response_json = protocol.format_response("123", {"status": "sent"})
        data = json.loads(response_json)
        
        assert data["jsonrpc"] == "2.0"
        assert data["result"]["status"] == "sent"
        assert data["id"] == "123"
        assert "error" not in data
    
    def test_format_error_response(self, protocol):
        """Test formatting an error response."""
        response_json = protocol.format_error(
            "123",
            JSONRPCError.INVALID_PARAMS,
            "Missing required parameter"
        )
        data = json.loads(response_json)
        
        assert data["jsonrpc"] == "2.0"
        assert data["error"]["code"] == JSONRPCError.INVALID_PARAMS
        assert data["error"]["message"] == "Missing required parameter"
        assert data["id"] == "123"
        assert "result" not in data
    
    def test_format_error_with_data(self, protocol):
        """Test formatting an error response with additional data."""
        response_json = protocol.format_error(
            "123",
            JSONRPCError.INVALID_PARAMS,
            "Validation failed",
            {"field": "target_user", "reason": "required"}
        )
        data = json.loads(response_json)
        
        assert data["error"]["data"]["field"] == "target_user"
        assert data["error"]["data"]["reason"] == "required"
    
    def test_format_notification_response(self, protocol):
        """Test that notifications don't generate responses."""
        # This should not generate a response
        response_json = protocol.format_response(None, {"status": "ok"})
        assert response_json is None
    
    def test_create_request(self, protocol):
        """Test creating a JSON-RPC request."""
        request_json = protocol.create_request(
            "tell",
            {"target_user": "alice", "message": "hello"},
            "123"
        )
        data = json.loads(request_json)
        
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "tell"
        assert data["params"]["target_user"] == "alice"
        assert data["id"] == "123"
    
    def test_create_notification(self, protocol):
        """Test creating a JSON-RPC notification."""
        notification_json = protocol.create_notification(
            "heartbeat",
            {"timestamp": 123456}
        )
        data = json.loads(notification_json)
        
        assert data["jsonrpc"] == "2.0"
        assert data["method"] == "heartbeat"
        assert data["params"]["timestamp"] == 123456
        assert "id" not in data
    
    def test_batch_requests(self, protocol):
        """Test handling batch requests."""
        batch_json = json.dumps([
            {
                "jsonrpc": "2.0",
                "method": "tell",
                "params": {"target_user": "alice", "message": "hello"},
                "id": "1"
            },
            {
                "jsonrpc": "2.0",
                "method": "who",
                "params": {"target_mud": "TestMUD"},
                "id": "2"
            }
        ])
        
        requests = protocol.parse_batch_request(batch_json)
        
        assert len(requests) == 2
        assert requests[0].method == "tell"
        assert requests[1].method == "who"
        assert requests[0].id == "1"
        assert requests[1].id == "2"
    
    def test_empty_batch_request(self, protocol):
        """Test handling empty batch request."""
        with pytest.raises(JSONRPCInvalidRequestError):
            protocol.parse_batch_request("[]")
    
    def test_validate_params_valid(self, protocol):
        """Test parameter validation with valid params."""
        schema = {
            "type": "object",
            "properties": {
                "target_user": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["target_user", "message"]
        }
        
        params = {"target_user": "alice", "message": "hello"}
        
        # Should not raise
        protocol.validate_params(params, schema)
    
    def test_validate_params_invalid(self, protocol):
        """Test parameter validation with invalid params."""
        schema = {
            "type": "object",
            "properties": {
                "target_user": {"type": "string"},
                "message": {"type": "string"}
            },
            "required": ["target_user", "message"]
        }
        
        params = {"target_user": "alice"}  # Missing message
        
        with pytest.raises(JSONRPCInvalidParamsError):
            protocol.validate_params(params, schema)
    
    def test_validate_params_wrong_type(self, protocol):
        """Test parameter validation with wrong parameter type."""
        schema = {
            "type": "object",
            "properties": {
                "target_user": {"type": "string"},
                "count": {"type": "integer"}
            },
            "required": ["target_user", "count"]
        }
        
        params = {"target_user": "alice", "count": "not_a_number"}
        
        with pytest.raises(JSONRPCInvalidParamsError):
            protocol.validate_params(params, schema)