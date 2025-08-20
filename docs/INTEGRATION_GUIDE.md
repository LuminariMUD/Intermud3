# Intermud3 Gateway Integration Guide

## Overview

This guide provides step-by-step instructions for integrating your MUD server with the Intermud3 Gateway. Whether you're running a CircleMUD, TinyMUD, LPMudlib, or custom codebase, this guide will help you connect to the global I3 network.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Detailed Integration Steps](#detailed-integration-steps)
4. [Client Implementation Patterns](#client-implementation-patterns)
5. [Testing Your Integration](#testing-your-integration)
6. [Production Deployment](#production-deployment)
7. [Common Integration Scenarios](#common-integration-scenarios)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements
- Network connectivity to the I3 Gateway
- Support for WebSocket or TCP socket connections
- JSON parsing capabilities
- Basic async/event handling (recommended)

### Gateway Requirements
- Running Intermud3 Gateway service
- Valid API key for your MUD
- Network access to gateway host/port

### Development Environment
- Text editor or IDE
- Testing tools (curl, websocat, or custom client)
- Access to MUD server code

## Quick Start

### 1. Get Your API Key

Contact your gateway administrator to obtain an API key. Your configuration will look like:

```yaml
api_keys:
  - key: "your-unique-api-key-here"
    mud_name: "YourMUD"
    permissions: ["tell", "channel", "info"]
```

### 2. Test Basic Connection

Using websocat (WebSocket testing tool):
```bash
# Install websocat
cargo install websocat

# Test connection
echo '{"jsonrpc":"2.0","id":1,"method":"authenticate","params":{"api_key":"your-api-key"}}' | websocat ws://localhost:8080/ws
```

Expected response:
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

### 3. Send Your First Tell

```bash
echo '{"jsonrpc":"2.0","id":2,"method":"tell","params":{"target_mud":"TestMUD","target_user":"TestUser","message":"Hello I3!"}}' | websocat ws://localhost:8080/ws
```

## Detailed Integration Steps

### Step 1: Choose Your Transport Protocol

#### Option A: WebSocket (Recommended)
- **Pros**: Real-time bidirectional communication, automatic reconnection
- **Cons**: Requires WebSocket library
- **Best for**: Modern MUDs, real-time applications

#### Option B: TCP Socket
- **Pros**: Simple implementation, universal compatibility
- **Cons**: Manual message framing, less efficient
- **Best for**: Legacy systems, simple integrations

### Step 2: Implement Basic Client

#### WebSocket Client Template (Python)

```python
import asyncio
import websockets
import json
import logging
from typing import Dict, Any, Optional, Callable

class I3Client:
    def __init__(self, gateway_url: str, api_key: str):
        self.gateway_url = gateway_url
        self.api_key = api_key
        self.websocket = None
        self.session_id = None
        self.authenticated = False
        self.handlers = {}
        self.request_id = 0
        
    async def connect(self):
        """Connect to the I3 Gateway."""
        try:
            self.websocket = await websockets.connect(self.gateway_url)
            await self.authenticate()
            
            # Start message handler
            asyncio.create_task(self.message_handler())
            
        except Exception as e:
            logging.error(f"Failed to connect: {e}")
            raise
    
    async def authenticate(self):
        """Authenticate with the gateway."""
        auth_request = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": "authenticate",
            "params": {"api_key": self.api_key}
        }
        
        await self.send_message(auth_request)
        
        # Wait for auth response
        response = await self.websocket.recv()
        data = json.loads(response)
        
        if data.get("result", {}).get("status") == "authenticated":
            self.authenticated = True
            self.session_id = data["result"]["session_id"]
            logging.info(f"Authenticated as {data['result']['mud_name']}")
        else:
            raise Exception("Authentication failed")
    
    async def send_message(self, message: Dict[str, Any]):
        """Send a message to the gateway."""
        if self.websocket:
            await self.websocket.send(json.dumps(message))
    
    async def message_handler(self):
        """Handle incoming messages."""
        async for message in self.websocket:
            try:
                data = json.loads(message)
                
                # Handle responses (have 'id' field)
                if "id" in data:
                    await self.handle_response(data)
                
                # Handle events/notifications (have 'method' field, no 'id')
                elif "method" in data:
                    await self.handle_event(data)
                    
            except Exception as e:
                logging.error(f"Error handling message: {e}")
    
    async def handle_response(self, data: Dict[str, Any]):
        """Handle method responses."""
        request_id = data["id"]
        
        if "result" in data:
            logging.info(f"Request {request_id} succeeded: {data['result']}")
        elif "error" in data:
            logging.error(f"Request {request_id} failed: {data['error']}")
    
    async def handle_event(self, data: Dict[str, Any]):
        """Handle incoming events."""
        method = data["method"]
        params = data.get("params", {})
        
        # Call registered handler
        if method in self.handlers:
            await self.handlers[method](params)
        else:
            logging.warning(f"No handler for event: {method}")
    
    def on(self, event_name: str, handler: Callable):
        """Register an event handler."""
        self.handlers[event_name] = handler
    
    def next_id(self) -> int:
        """Generate next request ID."""
        self.request_id += 1
        return self.request_id
    
    # API Methods
    async def tell(self, target_mud: str, target_user: str, message: str, from_user: str = "System"):
        """Send a tell."""
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": "tell",
            "params": {
                "target_mud": target_mud,
                "target_user": target_user,
                "message": message,
                "from_user": from_user
            }
        }
        await self.send_message(request)
    
    async def channel_send(self, channel: str, message: str, from_user: str = "System"):
        """Send a channel message."""
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": "channel_send",
            "params": {
                "channel": channel,
                "message": message,
                "from_user": from_user
            }
        }
        await self.send_message(request)
    
    async def channel_join(self, channel: str, user_name: str = "System"):
        """Join a channel."""
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": "channel_join",
            "params": {
                "channel": channel,
                "user_name": user_name
            }
        }
        await self.send_message(request)
    
    async def who(self, target_mud: str, filters: Optional[Dict] = None):
        """Get user list from a MUD."""
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": "who",
            "params": {
                "target_mud": target_mud
            }
        }
        if filters:
            request["params"]["filters"] = filters
        
        await self.send_message(request)

# Example usage
async def main():
    client = I3Client("ws://localhost:8080/ws", "your-api-key")
    
    # Register event handlers
    client.on("tell_received", handle_tell_received)
    client.on("channel_message", handle_channel_message)
    
    # Connect and authenticate
    await client.connect()
    
    # Join a channel
    await client.channel_join("intermud")
    
    # Send a test message
    await client.channel_send("intermud", "Hello from Python!")
    
    # Keep running
    await asyncio.Future()  # Run forever

async def handle_tell_received(params):
    print(f"Tell from {params['from_user']}@{params['from_mud']}: {params['message']}")

async def handle_channel_message(params):
    print(f"[{params['channel']}] {params['from_user']}: {params['message']}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### TCP Client Template (Python)

```python
import asyncio
import json
import logging
from typing import Dict, Any, Optional

class I3TCPClient:
    def __init__(self, host: str, port: int, api_key: str):
        self.host = host
        self.port = port
        self.api_key = api_key
        self.reader = None
        self.writer = None
        self.authenticated = False
        self.request_id = 0
    
    async def connect(self):
        """Connect to the TCP server."""
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        
        # Read welcome message
        welcome = await self.read_message()
        logging.info(f"Welcome: {welcome}")
        
        # Authenticate
        await self.authenticate()
        
        # Start message handler
        asyncio.create_task(self.message_handler())
    
    async def authenticate(self):
        """Authenticate with the gateway."""
        auth_request = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": "authenticate",
            "params": {"api_key": self.api_key}
        }
        
        await self.send_message(auth_request)
        
        # Wait for response
        response = await self.read_message()
        if response.get("result", {}).get("status") == "authenticated":
            self.authenticated = True
            logging.info("Authenticated successfully")
        else:
            raise Exception("Authentication failed")
    
    async def send_message(self, message: Dict[str, Any]):
        """Send a message over TCP."""
        data = json.dumps(message) + "\n"
        self.writer.write(data.encode('utf-8'))
        await self.writer.drain()
    
    async def read_message(self) -> Dict[str, Any]:
        """Read a message from TCP."""
        line = await self.reader.readline()
        return json.loads(line.decode('utf-8').strip())
    
    async def message_handler(self):
        """Handle incoming messages."""
        while True:
            try:
                message = await self.read_message()
                
                if "method" in message and "id" not in message:
                    # Event/notification
                    await self.handle_event(message)
                elif "id" in message:
                    # Response
                    await self.handle_response(message)
                    
            except Exception as e:
                logging.error(f"Error in message handler: {e}")
                break
    
    async def handle_event(self, message: Dict[str, Any]):
        """Handle incoming events."""
        method = message["method"]
        params = message.get("params", {})
        
        if method == "tell_received":
            print(f"Tell from {params['from_user']}@{params['from_mud']}: {params['message']}")
        elif method == "channel_message":
            print(f"[{params['channel']}] {params['from_user']}: {params['message']}")
    
    async def handle_response(self, message: Dict[str, Any]):
        """Handle method responses."""
        if "result" in message:
            logging.info(f"Success: {message['result']}")
        elif "error" in message:
            logging.error(f"Error: {message['error']}")
    
    def next_id(self) -> int:
        self.request_id += 1
        return self.request_id
    
    async def tell(self, target_mud: str, target_user: str, message: str):
        """Send a tell."""
        request = {
            "jsonrpc": "2.0",
            "id": self.next_id(),
            "method": "tell",
            "params": {
                "target_mud": target_mud,
                "target_user": target_user,
                "message": message
            }
        }
        await self.send_message(request)
```

### Step 3: Integrate with Your MUD

#### For CircleMUD (C)

```c
// i3_gateway.h
#ifndef I3_GATEWAY_H
#define I3_GATEWAY_H

typedef struct {
    int socket;
    char session_id[64];
    int authenticated;
} i3_connection_t;

// Function prototypes
int i3_connect(const char* host, int port, const char* api_key);
int i3_send_tell(const char* target_mud, const char* target_user, const char* message);
int i3_channel_send(const char* channel, const char* message);
void i3_handle_events(void);

#endif

// i3_gateway.c
#include "i3_gateway.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <json-c/json.h>

static i3_connection_t i3_conn = {0};

int i3_connect(const char* host, int port, const char* api_key) {
    // Create socket connection
    i3_conn.socket = socket(AF_INET, SOCK_STREAM, 0);
    
    // Connect to gateway
    struct sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, host, &addr.sin_addr);
    
    if (connect(i3_conn.socket, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        return -1;
    }
    
    // Authenticate
    json_object *auth_msg = json_object_new_object();
    json_object *jsonrpc = json_object_new_string("2.0");
    json_object *id = json_object_new_int(1);
    json_object *method = json_object_new_string("authenticate");
    json_object *params = json_object_new_object();
    json_object *api_key_obj = json_object_new_string(api_key);
    
    json_object_object_add(params, "api_key", api_key_obj);
    json_object_object_add(auth_msg, "jsonrpc", jsonrpc);
    json_object_object_add(auth_msg, "id", id);
    json_object_object_add(auth_msg, "method", method);
    json_object_object_add(auth_msg, "params", params);
    
    const char *json_string = json_object_to_json_string(auth_msg);
    char buffer[1024];
    snprintf(buffer, sizeof(buffer), "%s\n", json_string);
    
    send(i3_conn.socket, buffer, strlen(buffer), 0);
    
    // Read response
    char response[1024];
    recv(i3_conn.socket, response, sizeof(response), 0);
    
    // Parse response to check authentication
    json_object *resp_obj = json_tokener_parse(response);
    json_object *result;
    if (json_object_object_get_ex(resp_obj, "result", &result)) {
        json_object *status;
        if (json_object_object_get_ex(result, "status", &status)) {
            const char *status_str = json_object_get_string(status);
            if (strcmp(status_str, "authenticated") == 0) {
                i3_conn.authenticated = 1;
                return 0;
            }
        }
    }
    
    return -1;
}

int i3_send_tell(const char* target_mud, const char* target_user, const char* message) {
    if (!i3_conn.authenticated) return -1;
    
    json_object *tell_msg = json_object_new_object();
    json_object *jsonrpc = json_object_new_string("2.0");
    json_object *id = json_object_new_int(2);
    json_object *method = json_object_new_string("tell");
    json_object *params = json_object_new_object();
    
    json_object_object_add(params, "target_mud", json_object_new_string(target_mud));
    json_object_object_add(params, "target_user", json_object_new_string(target_user));
    json_object_object_add(params, "message", json_object_new_string(message));
    
    json_object_object_add(tell_msg, "jsonrpc", jsonrpc);
    json_object_object_add(tell_msg, "id", id);
    json_object_object_add(tell_msg, "method", method);
    json_object_object_add(tell_msg, "params", params);
    
    const char *json_string = json_object_to_json_string(tell_msg);
    char buffer[2048];
    snprintf(buffer, sizeof(buffer), "%s\n", json_string);
    
    return send(i3_conn.socket, buffer, strlen(buffer), 0);
}

// Integration with CircleMUD command system
ACMD(do_i3tell) {
    char target_mud[128], target_user[128], message[1024];
    
    if (!*argument) {
        send_to_char(ch, "Usage: i3tell <mud> <user> <message>\r\n");
        return;
    }
    
    sscanf(argument, "%s %s %[^\r\n]", target_mud, target_user, message);
    
    if (i3_send_tell(target_mud, target_user, message) > 0) {
        send_to_char(ch, "Tell sent.\r\n");
    } else {
        send_to_char(ch, "Failed to send tell.\r\n");
    }
}
```

#### For LPMudlib (LPC)

```lpc
// /adm/daemon/i3_gateway.c

#define I3_GATEWAY_HOST "localhost"
#define I3_GATEWAY_PORT 8081
#define API_KEY "your-api-key"

private int socket_fd;
private int authenticated;
private string session_id;

void create() {
    socket_fd = 0;
    authenticated = 0;
    call_out("connect_to_gateway", 1);
}

void connect_to_gateway() {
    socket_fd = socket_create(STREAM, "read_callback", "close_callback");
    
    if (socket_fd < 0) {
        call_out("connect_to_gateway", 60); // Retry in 60 seconds
        return;
    }
    
    if (socket_connect(socket_fd, I3_GATEWAY_HOST " " + I3_GATEWAY_PORT) < 0) {
        socket_close(socket_fd);
        call_out("connect_to_gateway", 60);
        return;
    }
    
    call_out("authenticate", 2);
}

void authenticate() {
    mapping auth_msg = ([
        "jsonrpc": "2.0",
        "id": 1,
        "method": "authenticate",
        "params": ([ "api_key": API_KEY ])
    ]);
    
    string json_msg = json_encode(auth_msg) + "\n";
    socket_write(socket_fd, json_msg);
}

void read_callback(int fd, mixed message) {
    string line;
    mapping data;
    
    if (sscanf(message, "%s\n", line) == 1) {
        data = json_decode(line);
        
        if (data["method"] && !data["id"]) {
            // Event/notification
            handle_event(data["method"], data["params"]);
        } else if (data["id"]) {
            // Response
            handle_response(data);
        }
    }
}

void handle_response(mapping data) {
    if (data["result"]) {
        if (data["result"]["status"] == "authenticated") {
            authenticated = 1;
            session_id = data["result"]["session_id"];
            write_log("I3", "Successfully authenticated with gateway");
            
            // Join default channels
            channel_join("intermud");
        }
    } else if (data["error"]) {
        write_log("I3", "Error: " + data["error"]["message"]);
    }
}

void handle_event(string method, mapping params) {
    switch(method) {
        case "tell_received":
            handle_tell_received(params);
            break;
        case "channel_message":
            handle_channel_message(params);
            break;
    }
}

void handle_tell_received(mapping params) {
    object user;
    string username = params["to_user"];
    
    user = find_player(username);
    if (user) {
        tell_object(user, sprintf("%%^CYAN%%^[I3 Tell] %s@%s tells you: %s%%^RESET%%^",
                                  params["from_user"], params["from_mud"], params["message"]));
    }
}

void handle_channel_message(mapping params) {
    object *users;
    string channel = params["channel"];
    
    users = filter_array(users(), (: living($1) && $1->query_env("i3_" + channel) :));
    
    foreach(object user in users) {
        tell_object(user, sprintf("%%^YELLOW%%^[%s] %s@%s: %s%%^RESET%%^",
                                  channel, params["from_user"], params["from_mud"], params["message"]));
    }
}

void send_tell(string target_mud, string target_user, string message, string from_user) {
    mapping tell_msg = ([
        "jsonrpc": "2.0",
        "id": random(10000),
        "method": "tell",
        "params": ([
            "target_mud": target_mud,
            "target_user": target_user,
            "message": message,
            "from_user": from_user
        ])
    ]);
    
    string json_msg = json_encode(tell_msg) + "\n";
    socket_write(socket_fd, json_msg);
}

void channel_send(string channel, string message, string from_user) {
    mapping channel_msg = ([
        "jsonrpc": "2.0",
        "id": random(10000),
        "method": "channel_send",
        "params": ([
            "channel": channel,
            "message": message,
            "from_user": from_user
        ])
    ]);
    
    string json_msg = json_encode(channel_msg) + "\n";
    socket_write(socket_fd, json_msg);
}

void channel_join(string channel) {
    mapping join_msg = ([
        "jsonrpc": "2.0",
        "id": random(10000),
        "method": "channel_join",
        "params": ([
            "channel": channel
        ])
    ]);
    
    string json_msg = json_encode(join_msg) + "\n";
    socket_write(socket_fd, json_msg);
}

// Command implementations
int cmd_i3tell(object me, string str) {
    string target_mud, target_user, message;
    
    if (!str || sscanf(str, "%s %s %s", target_mud, target_user, message) != 3) {
        notify_fail("Usage: i3tell <mud> <user> <message>\n");
        return 0;
    }
    
    send_tell(target_mud, target_user, message, me->query_name());
    write("Tell sent to " + target_user + "@" + target_mud + ".\n");
    return 1;
}

int cmd_i3chat(object me, string str) {
    if (!str) {
        notify_fail("Usage: i3chat <message>\n");
        return 0;
    }
    
    channel_send("intermud", str, me->query_name());
    write("Message sent to intermud channel.\n");
    return 1;
}
```

### Step 4: Handle Events

Event handling is crucial for a responsive I3 integration. Here's how to handle the most common events:

```python
async def handle_tell_received(params):
    """Handle incoming tells."""
    from_user = params['from_user']
    from_mud = params['from_mud']
    to_user = params['to_user']
    message = params['message']
    
    # Find the target player in your MUD
    player = find_player(to_user)
    if player:
        # Send the tell to the player
        send_to_player(player, f"[I3 Tell] {from_user}@{from_mud} tells you: {message}")
        
        # Log the tell
        log_tell(from_user, from_mud, to_user, message)
    else:
        # Player not found, optionally queue the message
        queue_offline_tell(to_user, from_user, from_mud, message)

async def handle_channel_message(params):
    """Handle channel messages."""
    channel = params['channel']
    from_user = params['from_user']
    from_mud = params['from_mud']
    message = params['message']
    
    # Find all players subscribed to this channel
    subscribers = get_channel_subscribers(channel)
    
    # Send message to all subscribers
    for player in subscribers:
        send_to_player(player, f"[{channel}] {from_user}@{from_mud}: {message}")

async def handle_mud_online(params):
    """Handle MUD coming online."""
    mud_name = params['mud_name']
    info = params['info']
    
    # Update MUD list
    update_mud_info(mud_name, info)
    
    # Notify administrators
    notify_admins(f"MUD {mud_name} has come online")

async def handle_error_occurred(params):
    """Handle system errors."""
    error_type = params.get('type', 'unknown')
    message = params.get('message', 'Unknown error')
    
    # Log the error
    log_error(f"I3 Gateway Error ({error_type}): {message}")
    
    # Notify administrators if critical
    if error_type in ['connection_lost', 'authentication_failed']:
        notify_admins(f"Critical I3 error: {message}")
```

## Testing Your Integration

### 1. Unit Tests

Create tests for your client implementation:

```python
import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from your_i3_client import I3Client

class TestI3Client(unittest.TestCase):
    def setUp(self):
        self.client = I3Client("ws://localhost:8080/ws", "test-api-key")
    
    async def test_authentication(self):
        """Test authentication flow."""
        # Mock WebSocket
        self.client.websocket = AsyncMock()
        
        # Mock authentication response
        auth_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "status": "authenticated",
                "mud_name": "TestMUD",
                "session_id": "test-session"
            }
        }
        
        self.client.websocket.recv.return_value = json.dumps(auth_response)
        
        # Test authentication
        await self.client.authenticate()
        
        self.assertTrue(self.client.authenticated)
        self.assertEqual(self.client.session_id, "test-session")
    
    async def test_tell_sending(self):
        """Test sending tells."""
        self.client.authenticated = True
        self.client.websocket = AsyncMock()
        
        await self.client.tell("TestMUD", "TestUser", "Hello!")
        
        # Verify message was sent
        self.client.websocket.send.assert_called_once()
        sent_message = json.loads(self.client.websocket.send.call_args[0][0])
        
        self.assertEqual(sent_message["method"], "tell")
        self.assertEqual(sent_message["params"]["target_mud"], "TestMUD")
        self.assertEqual(sent_message["params"]["message"], "Hello!")

if __name__ == "__main__":
    unittest.main()
```

### 2. Integration Tests

Test with a real gateway instance:

```bash
# Start test gateway
python -m src -c config/test-config.yaml

# Run integration tests
python tests/integration_test.py
```

```python
# tests/integration_test.py
import asyncio
import json
from your_i3_client import I3Client

async def test_full_integration():
    """Test complete integration flow."""
    
    # Connect to test gateway
    client = I3Client("ws://localhost:8080/ws", "demo-key-123")
    
    events_received = []
    
    # Register event handler
    async def event_handler(params):
        events_received.append(params)
    
    client.on("channel_message", event_handler)
    
    # Connect and authenticate
    await client.connect()
    assert client.authenticated
    
    # Join a channel
    await client.channel_join("test-channel")
    await asyncio.sleep(1)  # Wait for join to complete
    
    # Send a message
    await client.channel_send("test-channel", "Test message")
    await asyncio.sleep(1)  # Wait for message to be processed
    
    # Check if we received our own message back
    assert len(events_received) > 0
    assert events_received[-1]["message"] == "Test message"
    
    print("Integration test passed!")

if __name__ == "__main__":
    asyncio.run(test_full_integration())
```

### 3. Load Testing

Test your client under load:

```python
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

async def load_test():
    """Test multiple concurrent connections."""
    
    async def create_client(client_id):
        client = I3Client("ws://localhost:8080/ws", "demo-key-123")
        await client.connect()
        
        # Send 100 messages
        for i in range(100):
            await client.channel_send("test", f"Message {i} from client {client_id}")
            await asyncio.sleep(0.1)
    
    # Create 10 concurrent clients
    tasks = []
    start_time = time.time()
    
    for i in range(10):
        task = asyncio.create_task(create_client(i))
        tasks.append(task)
    
    await asyncio.gather(*tasks)
    
    end_time = time.time()
    print(f"Load test completed in {end_time - start_time:.2f} seconds")

asyncio.run(load_test())
```

## Production Deployment

### 1. Configuration Management

Create environment-specific configurations:

```yaml
# config/production.yaml
api:
  host: "0.0.0.0"
  port: 8080
  
  websocket:
    enabled: true
    max_connections: 10000
    ping_interval: 30
    
  auth:
    enabled: true
    require_tls: true
    
  rate_limits:
    default:
      per_minute: 1000
      burst: 100

# Environment variables
export I3_GATEWAY_SECRET="your-production-secret"
export API_KEY_YOURMUD="your-production-api-key"
export LOG_LEVEL="INFO"
```

### 2. Error Handling and Resilience

Implement robust error handling:

```python
class ResilientI3Client:
    def __init__(self, gateway_url, api_key):
        self.gateway_url = gateway_url
        self.api_key = api_key
        self.max_retries = 5
        self.retry_delay = 5
        self.connected = False
    
    async def connect_with_retry(self):
        """Connect with automatic retry."""
        for attempt in range(self.max_retries):
            try:
                await self.connect()
                self.connected = True
                return
            except Exception as e:
                logging.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise
    
    async def send_with_retry(self, method, params):
        """Send message with retry on failure."""
        for attempt in range(3):
            try:
                return await self.send_message({
                    "jsonrpc": "2.0",
                    "id": self.next_id(),
                    "method": method,
                    "params": params
                })
            except Exception as e:
                logging.warning(f"Send attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
                else:
                    raise
    
    async def health_check(self):
        """Periodic health check."""
        while True:
            try:
                if self.connected:
                    await self.ping()
                    await asyncio.sleep(30)
                else:
                    await self.connect_with_retry()
            except Exception as e:
                logging.error(f"Health check failed: {e}")
                self.connected = False
                await asyncio.sleep(60)
```

### 3. Monitoring and Logging

Implement comprehensive monitoring:

```python
import logging
import time
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class I3Metrics:
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    connection_time: float = 0
    last_activity: float = 0

class MonitoredI3Client(I3Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = I3Metrics()
        self.metrics.connection_time = time.time()
    
    async def send_message(self, message: Dict[str, Any]):
        """Send message with metrics tracking."""
        try:
            await super().send_message(message)
            self.metrics.messages_sent += 1
            self.metrics.last_activity = time.time()
        except Exception as e:
            self.metrics.errors += 1
            logging.error(f"Failed to send message: {e}")
            raise
    
    async def handle_event(self, data: Dict[str, Any]):
        """Handle event with metrics tracking."""
        try:
            await super().handle_event(data)
            self.metrics.messages_received += 1
            self.metrics.last_activity = time.time()
        except Exception as e:
            self.metrics.errors += 1
            logging.error(f"Failed to handle event: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        uptime = time.time() - self.metrics.connection_time
        return {
            "uptime": uptime,
            "messages_sent": self.metrics.messages_sent,
            "messages_received": self.metrics.messages_received,
            "errors": self.metrics.errors,
            "last_activity": self.metrics.last_activity,
            "messages_per_second": (self.metrics.messages_sent + self.metrics.messages_received) / uptime if uptime > 0 else 0
        }
```

### 4. Security Considerations

Implement security best practices:

```python
import ssl
import hashlib
import hmac

class SecureI3Client(I3Client):
    def __init__(self, gateway_url, api_key, use_tls=True):
        super().__init__(gateway_url, api_key)
        self.use_tls = use_tls
        self.message_nonce = 0
    
    async def connect(self):
        """Connect with TLS support."""
        if self.use_tls:
            ssl_context = ssl.create_default_context()
            self.websocket = await websockets.connect(
                self.gateway_url, 
                ssl=ssl_context
            )
        else:
            await super().connect()
    
    def sign_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Add message signature for integrity."""
        self.message_nonce += 1
        message["nonce"] = self.message_nonce
        
        # Create signature
        message_str = json.dumps(message, sort_keys=True)
        signature = hmac.new(
            self.api_key.encode(),
            message_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        message["signature"] = signature
        return message
    
    async def send_message(self, message: Dict[str, Any]):
        """Send signed message."""
        signed_message = self.sign_message(message)
        await super().send_message(signed_message)
```

## Common Integration Scenarios

### Scenario 1: Channel Bot

Create a bot that monitors channels and responds to commands:

```python
class ChannelBot(I3Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = {
            "!help": self.cmd_help,
            "!time": self.cmd_time,
            "!who": self.cmd_who
        }
    
    async def handle_channel_message(self, params):
        """Handle channel messages and respond to commands."""
        message = params["message"]
        channel = params["channel"]
        from_user = params["from_user"]
        from_mud = params["from_mud"]
        
        # Check for commands
        for command, handler in self.commands.items():
            if message.startswith(command):
                response = await handler(params)
                if response:
                    await self.channel_send(channel, response)
    
    async def cmd_help(self, params):
        """Help command."""
        return "Available commands: " + ", ".join(self.commands.keys())
    
    async def cmd_time(self, params):
        """Time command."""
        import datetime
        return f"Current time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    async def cmd_who(self, params):
        """Who command - get user count from a MUD."""
        from_mud = params["from_mud"]
        await self.who(from_mud)
        return f"Requesting user list from {from_mud}..."
```

### Scenario 2: Web Interface Bridge

Bridge between web interface and I3 network:

```python
from aiohttp import web, WSMsgType
import aiohttp_cors

class WebI3Bridge:
    def __init__(self, i3_client):
        self.i3_client = i3_client
        self.web_clients = set()
        self.app = web.Application()
        self.setup_routes()
    
    def setup_routes(self):
        """Setup web routes."""
        self.app.router.add_get('/ws', self.websocket_handler)
        self.app.router.add_static('/', 'web/static')
        
        # Setup CORS
        cors = aiohttp_cors.setup(self.app)
        cors.add(self.app.router.add_get('/api/channels', self.get_channels))
        cors.add(self.app.router.add_post('/api/send', self.send_message))
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections from web clients."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.web_clients.add(ws)
        
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                await self.handle_web_message(data)
            elif msg.type == WSMsgType.ERROR:
                print(f"WebSocket error: {ws.exception()}")
        
        self.web_clients.discard(ws)
        return ws
    
    async def handle_web_message(self, data):
        """Handle messages from web clients."""
        if data["type"] == "channel_send":
            await self.i3_client.channel_send(
                data["channel"],
                data["message"],
                data.get("from_user", "WebUser")
            )
    
    async def broadcast_to_web(self, data):
        """Broadcast I3 events to web clients."""
        message = json.dumps(data)
        for ws in list(self.web_clients):
            try:
                await ws.send_str(message)
            except:
                self.web_clients.discard(ws)
    
    async def get_channels(self, request):
        """API endpoint to get channel list."""
        # This would get channels from I3 client
        return web.json_response([
            {"name": "intermud", "members": 45},
            {"name": "chat", "members": 23}
        ])
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed troubleshooting guidance.

## Next Steps

1. **Review API Reference**: Read the complete API documentation
2. **Implement Core Features**: Start with tell and channel functionality
3. **Add Event Handling**: Implement all relevant event handlers
4. **Test Thoroughly**: Use provided test suites and create your own
5. **Deploy to Production**: Follow production deployment guidelines
6. **Monitor and Optimize**: Use monitoring tools and performance tuning

## Support

- **Documentation**: Read all provided documentation files
- **Examples**: Check the `clients/examples/` directory
- **Issues**: Report bugs and request features through proper channels
- **Community**: Join I3 development channels for support

This integration guide provides a comprehensive foundation for connecting your MUD to the Intermud3 network. Follow the steps carefully and adapt the examples to your specific MUD codebase and requirements.