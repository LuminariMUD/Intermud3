"""JSON-RPC 2.0 protocol implementation.

This module handles JSON-RPC message parsing, validation, and formatting
according to the JSON-RPC 2.0 specification.
"""

import json
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Union

from src.utils.logging import get_logger


logger = get_logger(__name__)


class JSONRPCError(IntEnum):
    """Standard JSON-RPC 2.0 error codes."""

    PARSE_ERROR = -32700  # Invalid JSON was received
    INVALID_REQUEST = -32600  # The JSON sent is not a valid Request object
    METHOD_NOT_FOUND = -32601  # The method does not exist or is not available
    INVALID_PARAMS = -32602  # Invalid method parameter(s)
    INTERNAL_ERROR = -32603  # Internal JSON-RPC error

    # Implementation-specific errors
    NOT_AUTHENTICATED = -32000  # Client not authenticated
    RATE_LIMIT_EXCEEDED = -32001  # Rate limit exceeded
    PERMISSION_DENIED = -32002  # Permission denied for this method
    SESSION_EXPIRED = -32003  # Session has expired
    GATEWAY_ERROR = -32004  # Gateway communication error


@dataclass
class JSONRPCRequest:
    """Parsed JSON-RPC request."""

    jsonrpc: str
    method: str
    params: Optional[Union[Dict[str, Any], List[Any]]] = None
    id: Optional[Union[str, int]] = None

    def is_notification(self) -> bool:
        """Check if this is a notification (no response expected)."""
        return self.id is None


@dataclass
class JSONRPCResponse:
    """JSON-RPC response."""

    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    def to_json(self) -> str:
        """Convert to JSON string."""
        data = {"jsonrpc": self.jsonrpc}

        if self.id is not None:
            data["id"] = self.id

        if self.error is not None:
            data["error"] = self.error
        elif self.result is not None:
            data["result"] = self.result
        else:
            data["result"] = None

        return json.dumps(data)


@dataclass
class JSONRPCBatch:
    """Batch of JSON-RPC requests."""

    requests: List[JSONRPCRequest] = field(default_factory=list)

    def add_request(self, request: JSONRPCRequest):
        """Add a request to the batch."""
        self.requests.append(request)

    def is_empty(self) -> bool:
        """Check if batch is empty."""
        return len(self.requests) == 0


class JSONRPCProtocol:
    """JSON-RPC 2.0 protocol implementation."""

    def __init__(self):
        """Initialize protocol handler."""
        self.supported_version = "2.0"

    def parse_request(self, data: str) -> Union[JSONRPCRequest, JSONRPCBatch]:
        """Parse and validate JSON-RPC request.

        Args:
            data: Raw JSON string

        Returns:
            JSONRPCRequest or JSONRPCBatch

        Raises:
            ValueError: If request is invalid
        """
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        # Check if it's a batch request
        if isinstance(parsed, list):
            return self._parse_batch(parsed)

        return self._parse_single(parsed)

    def _parse_single(self, data: Dict[str, Any]) -> JSONRPCRequest:
        """Parse a single JSON-RPC request.

        Args:
            data: Parsed JSON object

        Returns:
            JSONRPCRequest

        Raises:
            ValueError: If request is invalid
        """
        # Validate required fields
        if not isinstance(data, dict):
            raise ValueError("Request must be a JSON object")

        # Check JSON-RPC version
        jsonrpc = data.get("jsonrpc")
        if jsonrpc != self.supported_version:
            raise ValueError(f"Invalid JSON-RPC version: {jsonrpc}")

        # Validate method
        method = data.get("method")
        if not method or not isinstance(method, str):
            raise ValueError("Method must be a non-empty string")

        if method.startswith("rpc."):
            raise ValueError("Reserved method name")

        # Validate params (optional)
        params = data.get("params")
        if params is not None:
            if not isinstance(params, (dict, list)):
                raise ValueError("Params must be an object or array")

        # Validate id (optional for notifications)
        request_id = data.get("id")
        if request_id is not None:
            if not isinstance(request_id, (str, int, type(None))):
                raise ValueError("ID must be a string, number, or null")

        return JSONRPCRequest(jsonrpc=jsonrpc, method=method, params=params, id=request_id)

    def _parse_batch(self, data: List[Any]) -> JSONRPCBatch:
        """Parse a batch of JSON-RPC requests.

        Args:
            data: List of request objects

        Returns:
            JSONRPCBatch

        Raises:
            ValueError: If batch is invalid
        """
        if len(data) == 0:
            raise ValueError("Batch request cannot be empty")

        batch = JSONRPCBatch()

        for item in data:
            try:
                request = self._parse_single(item)
                batch.add_request(request)
            except ValueError as e:
                # In batch processing, individual errors are handled separately
                logger.warning(f"Invalid request in batch: {e}")
                # Add a placeholder for error response
                batch.add_request(
                    JSONRPCRequest(
                        jsonrpc="2.0",
                        method="__error__",
                        id=item.get("id") if isinstance(item, dict) else None,
                    )
                )

        return batch

    def format_response(self, request_id: Optional[Union[str, int]], result: Any) -> str:
        """Format a successful JSON-RPC response.

        Args:
            request_id: Request ID (None for notifications)
            result: Result data

        Returns:
            JSON string
        """
        if request_id is None:
            # No response for notifications
            return ""

        response = JSONRPCResponse(id=request_id, result=result)
        return response.to_json()

    def format_error(
        self,
        request_id: Optional[Union[str, int]],
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> str:
        """Format an error JSON-RPC response.

        Args:
            request_id: Request ID
            code: Error code
            message: Error message
            data: Additional error data

        Returns:
            JSON string
        """
        error = {"code": code, "message": message}

        if data is not None:
            error["data"] = data

        response = JSONRPCResponse(id=request_id, error=error)
        return response.to_json()

    def format_batch_response(self, responses: List[JSONRPCResponse]) -> str:
        """Format a batch of JSON-RPC responses.

        Args:
            responses: List of response objects

        Returns:
            JSON string
        """
        # Filter out empty responses (from notifications)
        valid_responses = [json.loads(r.to_json()) for r in responses if r.id is not None]

        if not valid_responses:
            return ""  # No response for all-notification batch

        return json.dumps(valid_responses)

    def validate_params(
        self, params: Optional[Union[Dict[str, Any], List[Any]]], schema: Dict[str, Any]
    ) -> bool:
        """Validate parameters against a schema.

        Args:
            params: Parameters to validate
            schema: Schema definition

        Returns:
            True if valid, False otherwise
        """
        if not schema:
            return True  # No schema means any params are valid

        required = schema.get("required", [])
        properties = schema.get("properties", {})

        if params is None:
            return len(required) == 0

        if isinstance(params, dict):
            # Check required fields
            for field in required:
                if field not in params:
                    return False

            # Check field types
            for field, value in params.items():
                if field in properties:
                    field_schema = properties[field]
                    if not self._validate_type(value, field_schema):
                        return False

        return True

    def _validate_type(self, value: Any, schema: Dict[str, Any]) -> bool:
        """Validate a value against a type schema.

        Args:
            value: Value to validate
            schema: Type schema

        Returns:
            True if valid, False otherwise
        """
        expected_type = schema.get("type")

        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "number":
            return isinstance(value, (int, float))
        if expected_type == "integer":
            return isinstance(value, int)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "array":
            return isinstance(value, list)
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "null":
            return value is None

        return True  # Unknown type, allow it

    def create_notification(self, method: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Create a JSON-RPC notification (no response expected).

        Args:
            method: Method name
            params: Optional parameters

        Returns:
            JSON string
        """
        notification = {"jsonrpc": "2.0", "method": method}

        if params is not None:
            notification["params"] = params

        return json.dumps(notification)

    def create_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        request_id: Optional[Union[str, int]] = None,
    ) -> str:
        """Create a JSON-RPC request.

        Args:
            method: Method name
            params: Optional parameters
            request_id: Optional request ID (auto-generated if None)

        Returns:
            JSON string
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        request = {"jsonrpc": "2.0", "method": method, "id": request_id}

        if params is not None:
            request["params"] = params

        return json.dumps(request)
