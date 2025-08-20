# Intermud3 Gateway API Reference

## Overview

The Intermud3 Gateway provides a JSON-RPC 2.0 API that allows MUD servers to integrate with the global Intermud-3 network. The API supports both WebSocket and TCP connections, enabling real-time bidirectional communication between MUDs and the I3 network.

**Current Status**: Phase 3 Complete (2025-08-20) - Full implementation with 78% test coverage, 1200+ tests, achieving 1000+ msg/sec throughput with <100ms latency.

## Table of Contents

1. [Connection and Authentication](#connection-and-authentication)
2. [Transport Protocols](#transport-protocols)
3. [Message Format](#message-format)
4. [Error Handling](#error-handling)
5. [API Methods](#api-methods)
6. [Events and Notifications](#events-and-notifications)
7. [Rate Limiting](#rate-limiting)
8. [Session Management](#session-management)

## Connection and Authentication

### WebSocket Connection

Connect to the WebSocket endpoint:
```
ws://localhost:8080/ws
```

### TCP Connection

Connect to the TCP socket:
```
localhost:8081
```

### Authentication

All connections require authentication using an API key. Authentication can be done in two ways:

#### 1. Header Authentication (WebSocket only)
```http
X-API-Key: your-api-key-here
```

#### 2. Method Authentication (Both protocols)
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "authenticate",
  "params": {
    "api_key": "your-api-key-here"
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "authenticated",
    "mud_name": "YourMUD",
    "session_id": "unique-session-id"
  }
}
```

## Transport Protocols

### WebSocket (Recommended)

- **URL**: `ws://host:port/ws`
- **Protocol**: JSON-RPC 2.0 over WebSocket frames
- **Benefits**: Real-time bidirectional communication, automatic reconnection support
- **Message Format**: JSON objects sent as WebSocket text frames

### TCP Socket

- **Host/Port**: Configured in gateway settings (default: port 8081)
- **Protocol**: Line-delimited JSON-RPC 2.0
- **Message Format**: JSON objects terminated by newline (`\n`)
- **Benefits**: Compatibility with older systems, simple implementation

## Message Format

All messages follow the JSON-RPC 2.0 specification:

### Request Format
```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "method": "method_name",
  "params": {
    "parameter1": "value1",
    "parameter2": "value2"
  }
}
```

### Response Format
```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "result": {
    "status": "success",
    "data": "response_data"
  }
}
```

### Notification Format (Events)
```json
{
  "jsonrpc": "2.0",
  "method": "event_name",
  "params": {
    "event_data": "value"
  }
}
```

## Error Handling

### Standard Error Codes

| Code | Name | Description |
|------|------|-------------|
| -32700 | Parse Error | Invalid JSON received |
| -32600 | Invalid Request | JSON is not a valid request object |
| -32601 | Method Not Found | Method does not exist |
| -32602 | Invalid Params | Invalid method parameters |
| -32603 | Internal Error | Internal JSON-RPC error |

### Custom Error Codes

| Code | Name | Description |
|------|------|-------------|
| -32000 | Not Authenticated | Client not authenticated |
| -32001 | Rate Limit Exceeded | Rate limit exceeded |
| -32002 | Permission Denied | Permission denied for method |
| -32003 | Session Expired | Session has expired |
| -32004 | Gateway Error | Gateway communication error |

### Error Response Format
```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "field": "target_mud",
      "reason": "MUD not found in network"
    }
  }
}
```

## API Methods

### Communication Methods

#### tell
Send a direct message to a user on another MUD.

**Parameters:**
- `target_mud` (string, required): Name of the target MUD
- `target_user` (string, required): Name of the target user
- `message` (string, required): Message to send (max 2048 characters)
- `from_user` (string, optional): Sender's username

**Example:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tell",
  "params": {
    "target_mud": "OtherMUD",
    "target_user": "PlayerName",
    "message": "Hello from our MUD!",
    "from_user": "MyPlayer"
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "status": "success",
    "message": "Tell sent successfully"
  }
}
```

#### emoteto
Send an emote to a specific user.

**Parameters:**
- `target_mud` (string, required): Name of the target MUD
- `target_user` (string, required): Name of the target user
- `emote` (string, required): Emote text (max 1024 characters)
- `from_user` (string, optional): Sender's username

**Example:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "emoteto",
  "params": {
    "target_mud": "OtherMUD",
    "target_user": "PlayerName",
    "emote": "waves enthusiastically",
    "from_user": "MyPlayer"
  }
}
```

#### channel_send
Send a message to a channel.

**Parameters:**
- `channel` (string, required): Channel name
- `message` (string, required): Message to send (max 2048 characters)
- `from_user` (string, optional): Sender's username
- `visname` (string, optional): Visible name for sender

**Example:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "channel_send",
  "params": {
    "channel": "intermud",
    "message": "Hello everyone!",
    "from_user": "MyPlayer"
  }
}
```

#### channel_emote
Send an emote to a channel.

**Parameters:**
- `channel` (string, required): Channel name
- `emote` (string, required): Emote text (max 1024 characters)
- `from_user` (string, optional): Sender's username
- `visname` (string, optional): Visible name for sender

### Information Methods

#### who
List users on a MUD.

**Parameters:**
- `target_mud` (string, required): Name of the target MUD
- `filters` (object, optional): Filtering options
  - `min_level` (number): Minimum user level
  - `max_level` (number): Maximum user level
  - `race` (string): Filter by race
  - `guild` (string): Filter by guild

**Example:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "who",
  "params": {
    "target_mud": "OtherMUD",
    "filters": {
      "min_level": 10,
      "race": "human"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "status": "success",
    "mud_name": "OtherMUD",
    "users": [
      {
        "name": "Player1",
        "level": 15,
        "race": "human",
        "guild": "warriors",
        "idle_time": 120
      }
    ],
    "count": 1
  }
}
```

#### finger
Get detailed information about a user.

**Parameters:**
- `target_mud` (string, required): Name of the target MUD
- `target_user` (string, required): Name of the target user

**Example:**
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "finger",
  "params": {
    "target_mud": "OtherMUD",
    "target_user": "PlayerName"
  }
}
```

#### locate
Find a user on the network.

**Parameters:**
- `target_user` (string, required): Name of the user to locate

**Example:**
```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "locate",
  "params": {
    "target_user": "PlayerName"
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "result": {
    "status": "success",
    "user_name": "PlayerName",
    "locations": [
      {
        "mud_name": "MUD1",
        "status": "online",
        "idle_time": 300
      }
    ],
    "found": true,
    "count": 1
  }
}
```

#### mudlist
Get list of MUDs on the network.

**Parameters:**
- `refresh` (boolean, optional): Force refresh from router (default: false)
- `filter` (object, optional): Filtering options
  - `status` (string): Filter by status ("up" or "down")
  - `driver` (string): Filter by driver type
  - `has_service` (string): Filter by service availability

**Example:**
```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "mudlist",
  "params": {
    "refresh": false,
    "filter": {
      "status": "up",
      "has_service": "tell"
    }
  }
}
```

### Channel Management Methods

#### channel_join
Join a channel.

**Parameters:**
- `channel` (string, required): Channel name (max 32 characters)
- `listen_only` (boolean, optional): Join in listen-only mode (default: false)
- `user_name` (string, optional): Username for channel (default: "System")

**Example:**
```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "method": "channel_join",
  "params": {
    "channel": "intermud",
    "listen_only": false,
    "user_name": "MyPlayer"
  }
}
```

#### channel_leave
Leave a channel.

**Parameters:**
- `channel` (string, required): Channel name
- `user_name` (string, optional): Username for channel

#### channel_list
List available channels.

**Parameters:**
- `refresh` (boolean, optional): Force refresh from router
- `filter` (object, optional): Filtering options
  - `type` (number): Channel type (0=public, 1=private)
  - `owner` (string): Filter by owner
  - `min_members` (number): Minimum member count

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 9,
  "result": {
    "status": "success",
    "channels": [
      {
        "name": "intermud",
        "type": 0,
        "owner": "",
        "subscribed": true,
        "member_count": 25
      }
    ],
    "count": 1,
    "subscribed_channels": ["intermud"]
  }
}
```

#### channel_who
List members of a channel.

**Parameters:**
- `channel` (string, required): Channel name

#### channel_history
Get channel message history.

**Parameters:**
- `channel` (string, required): Channel name
- `limit` (number, optional): Number of messages (1-100, default: 50)
- `before` (string, optional): Get messages before timestamp
- `after` (string, optional): Get messages after timestamp

### Administrative Methods

#### ping
Health check and heartbeat.

**Example:**
```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "method": "ping"
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 10,
  "result": {
    "pong": true,
    "timestamp": 1642678800.123
  }
}
```

#### status
Get gateway status and session information.

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 11,
  "result": {
    "connected": true,
    "mud_name": "YourMUD",
    "session_id": "unique-session-id",
    "uptime": 3600.5
  }
}
```

## Events and Notifications

The gateway sends events as JSON-RPC notifications (no response expected).

### Communication Events

#### tell_received
Received when a tell arrives for a user.

```json
{
  "jsonrpc": "2.0",
  "method": "tell_received",
  "params": {
    "from_mud": "RemoteMUD",
    "from_user": "SenderName",
    "to_user": "RecipientName",
    "message": "Hello there!",
    "timestamp": "2025-01-20T10:30:00Z"
  }
}
```

#### emoteto_received
Received when an emote is sent to a user.

```json
{
  "jsonrpc": "2.0",
  "method": "emoteto_received",
  "params": {
    "from_mud": "RemoteMUD",
    "from_user": "SenderName",
    "to_user": "RecipientName",
    "emote": "waves at you",
    "timestamp": "2025-01-20T10:30:00Z"
  }
}
```

#### channel_message
Received when a message is sent to a subscribed channel.

```json
{
  "jsonrpc": "2.0",
  "method": "channel_message",
  "params": {
    "channel": "intermud",
    "from_mud": "RemoteMUD",
    "from_user": "SenderName",
    "message": "Hello channel!",
    "visname": "SenderName",
    "timestamp": "2025-01-20T10:30:00Z"
  }
}
```

#### channel_emote
Received when an emote is sent to a subscribed channel.

### System Events

#### mud_online
Notifies when a MUD comes online.

```json
{
  "jsonrpc": "2.0",
  "method": "mud_online",
  "params": {
    "mud_name": "NewMUD",
    "info": {
      "driver": "FluffOS",
      "mud_type": "LP",
      "services": ["tell", "channel", "who"],
      "admin_email": "admin@newmud.com"
    }
  }
}
```

#### mud_offline
Notifies when a MUD goes offline.

#### channel_joined
Notifies when successfully joined a channel.

#### channel_left
Notifies when left a channel.

#### error_occurred
Notifies of system errors.

#### gateway_reconnected
Notifies when gateway reconnects to router.

## Rate Limiting

### Default Limits
- **Per session**: 100 requests per minute
- **Burst allowance**: 20 requests
- **By method**: Specific limits per method type

### Method-Specific Limits
- `tell`: 30 per minute
- `channel_send`: 50 per minute
- `who`: 10 per minute
- `mudlist`: 5 per minute

### Rate Limit Headers (WebSocket only)
Rate limit information is included in error responses:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32001,
    "message": "Rate limit exceeded",
    "data": {
      "retry_after": 60,
      "limit": 100,
      "remaining": 0
    }
  }
}
```

## Session Management

### Session Lifecycle
1. **Connection**: Client connects via WebSocket or TCP
2. **Authentication**: Client provides API key
3. **Session Creation**: Server creates session with unique ID
4. **Activity Tracking**: Server tracks all client activity
5. **Timeout**: Session expires after inactivity (default: 1 hour)
6. **Cleanup**: Server cleans up expired sessions

### Session Persistence
- Sessions persist across reconnections using session ID
- Message queue maintains offline messages (max 1000, TTL 5 minutes)
- Channel subscriptions are restored on reconnection

### Session Metrics
Each session tracks:
- Messages sent/received
- Method call counts
- Error counts
- Connection duration
- Last activity timestamp

## Configuration

### API Server Settings
```yaml
api:
  host: "0.0.0.0"
  port: 8080
  
  websocket:
    enabled: true
    max_connections: 1000
    ping_interval: 30
    
  tcp:
    enabled: true
    port: 8081
    max_connections: 500
    
  auth:
    enabled: true
    api_keys:
      - key: "your-api-key"
        mud_name: "YourMUD"
        permissions: ["tell", "channel", "info"]
```

### Rate Limiting Configuration
```yaml
api:
  rate_limits:
    default:
      per_minute: 100
      burst: 20
    by_method:
      tell: 30
      channel_send: 50
```

## Health Endpoints

### Health Check
```
GET /health
```

Response:
```json
{
  "status": "healthy",
  "service": "i3-gateway-api",
  "websocket_connections": 42,
  "active_sessions": 38
}
```

### Liveness Probe
```
GET /health/live
```

### Readiness Probe
```
GET /health/ready
```

### Metrics
```
GET /metrics
```

Returns Prometheus-format metrics.

## Best Practices

### Connection Management
- Use WebSocket for real-time applications
- Implement reconnection logic with exponential backoff
- Handle session restoration gracefully
- Monitor connection health with ping/pong

### Error Handling
- Always check for error responses
- Implement retry logic for transient errors
- Log all errors for debugging
- Handle rate limiting gracefully

### Performance
- Batch related operations when possible
- Use appropriate rate limits
- Monitor session metrics
- Implement message queuing for offline handling

### Security
- Keep API keys secure
- Use TLS in production
- Implement proper input validation
- Monitor for abuse patterns

## Examples

### Basic Tell Implementation
```python
import asyncio
import websockets
import json

async def send_tell():
    uri = "ws://localhost:8080/ws"
    
    async with websockets.connect(uri) as websocket:
        # Authenticate
        auth_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "authenticate",
            "params": {"api_key": "your-api-key"}
        }
        await websocket.send(json.dumps(auth_msg))
        response = await websocket.recv()
        print("Auth response:", response)
        
        # Send tell
        tell_msg = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tell",
            "params": {
                "target_mud": "OtherMUD",
                "target_user": "Player",
                "message": "Hello!",
                "from_user": "MyPlayer"
            }
        }
        await websocket.send(json.dumps(tell_msg))
        response = await websocket.recv()
        print("Tell response:", response)

asyncio.run(send_tell())
```

### Event Handling
```python
async def handle_events():
    uri = "ws://localhost:8080/ws"
    
    async with websockets.connect(uri) as websocket:
        # Authenticate first...
        
        # Listen for events
        async for message in websocket:
            data = json.loads(message)
            
            if data.get("method") == "tell_received":
                params = data["params"]
                print(f"Tell from {params['from_user']}@{params['from_mud']}: {params['message']}")
            
            elif data.get("method") == "channel_message":
                params = data["params"]
                print(f"[{params['channel']}] {params['from_user']}: {params['message']}")
```

This API reference provides a complete guide to integrating with the Intermud3 Gateway. For additional examples and integration guides, see the accompanying documentation files.