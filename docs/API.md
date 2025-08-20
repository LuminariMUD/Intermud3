# Intermud3 Gateway API Documentation

## Overview

The Intermud3 Gateway provides a JSON-RPC 2.0 API over TCP/WebSocket for MUD servers to integrate with the global Intermud-3 network. This document describes the available methods, their parameters, and expected responses.

## Connection

### Endpoint
- **Default Port**: 4001
- **Protocol**: JSON-RPC 2.0 over TCP or WebSocket
- **Encoding**: UTF-8

### Authentication
```json
{
  "jsonrpc": "2.0",
  "method": "authenticate",
  "params": {
    "mud_name": "YourMUD",
    "secret": "shared-secret-key"
  },
  "id": 1
}
```

## Core Methods

### Communication

#### send_tell
Send a private message to a user on another MUD.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "send_tell",
  "params": {
    "from_user": "sender",
    "to_mud": "TargetMUD",
    "to_user": "recipient",
    "message": "Hello there!"
  },
  "id": 2
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "sent",
    "timestamp": 1642345678
  },
  "id": 2
}
```

#### send_emoteto
Send an emote to a user on another MUD.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "send_emoteto",
  "params": {
    "from_user": "sender",
    "to_mud": "TargetMUD",
    "to_user": "recipient",
    "emote": "waves cheerfully"
  },
  "id": 3
}
```

### Channels

#### channel_list
Get list of available I3 channels.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "channel_list",
  "id": 4
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "channels": [
      {
        "name": "chat",
        "type": "public",
        "owner": "RouterMUD"
      },
      {
        "name": "code",
        "type": "public",
        "owner": "DevMUD"
      }
    ]
  },
  "id": 4
}
```

#### channel_join
Join an I3 channel.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "channel_join",
  "params": {
    "channel": "chat",
    "user": "player"
  },
  "id": 5
}
```

#### channel_leave
Leave an I3 channel.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "channel_leave",
  "params": {
    "channel": "chat",
    "user": "player"
  },
  "id": 6
}
```

#### channel_send
Send a message to a channel.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "channel_send",
  "params": {
    "channel": "chat",
    "user": "player",
    "message": "Hello everyone!"
  },
  "id": 7
}
```

### Information Queries

#### who
Get list of users on a specific MUD.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "who",
  "params": {
    "target_mud": "SomeMUD"
  },
  "id": 8
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "mud": "SomeMUD",
    "users": [
      {"name": "player1", "idle": 0, "level": 50},
      {"name": "player2", "idle": 300, "level": 25}
    ]
  },
  "id": 8
}
```

#### finger
Get detailed information about a user.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "finger",
  "params": {
    "target_mud": "SomeMUD",
    "target_user": "player"
  },
  "id": 9
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "user": "player",
    "mud": "SomeMUD",
    "title": "the Adventurer",
    "real_name": "John",
    "email": "player@example.com",
    "last_on": 1642345678,
    "idle": 0,
    "level": 50
  },
  "id": 9
}
```

#### locate
Find a user across the entire I3 network.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "locate",
  "params": {
    "user": "player"
  },
  "id": 10
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "found": true,
    "mud": "SomeMUD",
    "user": "player",
    "idle": 0,
    "status": "active"
  },
  "id": 10
}
```

#### mudlist
Get list of all MUDs on the I3 network.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "mudlist",
  "id": 11
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "muds": [
      {
        "name": "MUD1",
        "type": "LP",
        "status": "up",
        "address": "mud1.example.com",
        "port": 4000,
        "players": 25
      },
      {
        "name": "MUD2",
        "type": "Circle",
        "status": "up",
        "address": "mud2.example.com", 
        "port": 5000,
        "players": 10
      }
    ]
  },
  "id": 11
}
```

## Events (Gateway to MUD)

The gateway sends events to the MUD when messages or data are received from the I3 network.

### tell_received
Received when another user sends a tell to a player on your MUD.

```json
{
  "jsonrpc": "2.0",
  "method": "event",
  "params": {
    "type": "tell_received",
    "data": {
      "from_user": "sender",
      "from_mud": "RemoteMUD",
      "to_user": "recipient",
      "message": "Hello!",
      "timestamp": 1642345678
    }
  }
}
```

### channel_message
Received when a message is sent to a joined channel.

```json
{
  "jsonrpc": "2.0",
  "method": "event",
  "params": {
    "type": "channel_message",
    "data": {
      "channel": "chat",
      "user": "speaker",
      "mud": "RemoteMUD",
      "message": "Hello channel!",
      "timestamp": 1642345678
    }
  }
}
```

### who_reply
Response to a who request.

```json
{
  "jsonrpc": "2.0",
  "method": "event",
  "params": {
    "type": "who_reply",
    "data": {
      "request_id": 8,
      "mud": "QueriedMUD",
      "users": [...]
    }
  }
}
```

### finger_reply
Response to a finger request.

```json
{
  "jsonrpc": "2.0",
  "method": "event",
  "params": {
    "type": "finger_reply",
    "data": {
      "request_id": 9,
      "user_info": {...}
    }
  }
}
```

### locate_reply
Response to a locate request.

```json
{
  "jsonrpc": "2.0",
  "method": "event",
  "params": {
    "type": "locate_reply",
    "data": {
      "request_id": 10,
      "found": true,
      "location": {...}
    }
  }
}
```

## Error Responses

The gateway returns standard JSON-RPC error responses:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": "Missing required parameter: to_user"
  },
  "id": 2
}
```

### Error Codes
- `-32700`: Parse error
- `-32600`: Invalid request
- `-32601`: Method not found
- `-32602`: Invalid params
- `-32603`: Internal error
- `1000`: Authentication required
- `1001`: Not authorized
- `1002`: Target not found
- `1003`: Service unavailable
- `1004`: Rate limit exceeded

## Status and Monitoring

### status
Get gateway connection status.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "status",
  "id": 100
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "connected": true,
    "router": "*i3",
    "uptime": 3600,
    "messages_sent": 1234,
    "messages_received": 5678,
    "channels_joined": ["chat", "code"],
    "version": "0.2.0"
  },
  "id": 100
}
```

### ping
Test gateway connectivity.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "ping",
  "id": 101
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "result": "pong",
  "id": 101
}
```

## Rate Limiting

The gateway implements rate limiting to prevent abuse:

- **Tells**: 10 per minute per user
- **Channel messages**: 20 per minute per channel
- **Who requests**: 5 per minute
- **Finger requests**: 10 per minute
- **Locate requests**: 5 per minute

Exceeding these limits will result in error code `1004`.

## Example Integration

### Python Client Example

```python
import json
import socket

class I3GatewayClient:
    def __init__(self, host='localhost', port=4001):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))
        self.request_id = 0
    
    def send_request(self, method, params=None):
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        if params:
            request["params"] = params
        
        message = json.dumps(request) + '\n'
        self.socket.send(message.encode('utf-8'))
        
        response = self.socket.recv(4096).decode('utf-8')
        return json.loads(response)
    
    def send_tell(self, from_user, to_mud, to_user, message):
        return self.send_request("send_tell", {
            "from_user": from_user,
            "to_mud": to_mud,
            "to_user": to_user,
            "message": message
        })

# Usage
client = I3GatewayClient()
result = client.send_tell("player", "OtherMUD", "friend", "Hello!")
print(result)
```

## Best Practices

1. **Persistent Connections**: Maintain a persistent connection to the gateway rather than connecting for each request
2. **Event Handling**: Implement async event handling for incoming messages
3. **Error Recovery**: Implement automatic reconnection on connection loss
4. **Rate Limiting**: Implement client-side rate limiting to avoid hitting server limits
5. **Logging**: Log all I3 communication for debugging and audit purposes
6. **Security**: Use the shared secret authentication and validate all incoming data

## Version History

- **0.2.0**: Phase 2 Complete - Core services implemented (tell, channel, who, finger, locate)
  - Full test coverage for all services (60% overall)
  - Circuit breakers and retry mechanisms
  - Connection pooling and health checks
  - Performance benchmarks and stress testing
- **0.3.0**: Phase 3 Complete (2025-08-19) - Gateway API Protocol
  - Full JSON-RPC 2.0 implementation
  - WebSocket and TCP support
  - Client libraries (Python, JavaScript/Node.js)
  - Comprehensive documentation
  - Authentication and state management
  - Event distribution system
- **0.4.0**: OOB services and advanced features (planned)