# Intermud3 Gateway Troubleshooting Guide

## Overview

This guide helps you diagnose and resolve common issues when integrating with the Intermud3 Gateway. It covers connection problems, authentication issues, message delivery failures, performance problems, and provides debugging techniques.

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Connection Issues](#connection-issues)
3. [Authentication Problems](#authentication-problems)
4. [Message Delivery Issues](#message-delivery-issues)
5. [Performance Problems](#performance-problems)
6. [Event Handling Issues](#event-handling-issues)
7. [Configuration Problems](#configuration-problems)
8. [Debugging Techniques](#debugging-techniques)
9. [Error Code Reference](#error-code-reference)
10. [Common Solutions](#common-solutions)

## Quick Diagnostics

### Health Check Checklist

Before diving into specific issues, run through this quick checklist:

```bash
# 1. Check if gateway is running
curl http://localhost:8080/health

# 2. Test basic connectivity
telnet localhost 8080

# 3. Check WebSocket endpoint
websocat ws://localhost:8080/ws

# 4. Verify configuration
cat config/config.yaml | grep -A 10 api

# 5. Check logs
tail -f logs/i3-gateway.log

# 6. Test with demo API key
echo '{"jsonrpc":"2.0","id":1,"method":"authenticate","params":{"api_key":"demo-key-123"}}' | websocat ws://localhost:8080/ws
```

### System Status Commands

```bash
# Check process status
ps aux | grep i3-gateway

# Check port usage
netstat -tulpn | grep :8080
lsof -i :8080

# Check system resources
free -h
df -h
top -p $(pgrep python)

# Check network connectivity
ping localhost
curl -I http://localhost:8080/health
```

## Connection Issues

### Problem: Cannot Connect to Gateway

**Symptoms:**
- Connection refused errors
- Timeout when connecting
- WebSocket handshake failures

**Diagnosis:**
```bash
# Check if gateway is running
systemctl status i3-gateway
# or
ps aux | grep i3-gateway

# Check if port is open
netstat -tulpn | grep :8080
ss -tulpn | grep :8080

# Test network connectivity
curl http://localhost:8080/health
telnet localhost 8080
```

**Solutions:**

1. **Gateway Not Running:**
   ```bash
   # Start the gateway
   python -m src -c config/config.yaml
   
   # Or use systemd
   systemctl start i3-gateway
   systemctl enable i3-gateway
   ```

2. **Port Conflicts:**
   ```bash
   # Find process using port
   lsof -i :8080
   
   # Kill conflicting process
   kill $(lsof -t -i:8080)
   
   # Or change gateway port in config
   ```

3. **Firewall Issues:**
   ```bash
   # Check firewall rules
   iptables -L
   ufw status
   
   # Allow port 8080
   ufw allow 8080
   iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
   ```

4. **Configuration Issues:**
   ```yaml
   # config/config.yaml
   api:
     host: "0.0.0.0"  # Make sure it's not 127.0.0.1 for remote access
     port: 8080
     websocket:
       enabled: true
   ```

### Problem: WebSocket Connection Drops

**Symptoms:**
- Frequent disconnections
- WebSocket closes unexpectedly
- Connection timeouts

**Diagnosis:**
```python
# Add connection monitoring
import time

class ConnectionMonitor:
    def __init__(self):
        self.last_ping = time.time()
        self.disconnect_count = 0
    
    async def on_disconnect(self):
        self.disconnect_count += 1
        print(f"Disconnection #{self.disconnect_count} at {time.time()}")
    
    async def ping_check(self):
        if time.time() - self.last_ping > 60:
            print("No ping received in 60 seconds")
```

**Solutions:**

1. **Implement Ping/Pong:**
   ```python
   async def ping_handler(self):
       while self.connected:
           try:
               await self.websocket.ping()
               await asyncio.sleep(30)
           except:
               await self.reconnect()
   ```

2. **Increase Timeouts:**
   ```yaml
   api:
     websocket:
       ping_interval: 30
       ping_timeout: 10
   ```

3. **Add Reconnection Logic:**
   ```python
   async def auto_reconnect(self):
       while True:
           try:
               if not self.connected:
                   await self.connect()
               await asyncio.sleep(5)
           except Exception as e:
               print(f"Reconnection failed: {e}")
               await asyncio.sleep(30)
   ```

### Problem: TCP Connection Issues

**Symptoms:**
- TCP socket errors
- Connection resets
- Data corruption

**Solutions:**

1. **Proper Message Framing:**
   ```python
   # Ensure newline-delimited messages
   message = json.dumps(data) + "\n"
   socket.send(message.encode('utf-8'))
   ```

2. **Handle Partial Reads:**
   ```python
   buffer = ""
   while True:
       data = socket.recv(1024).decode('utf-8')
       buffer += data
       
       while '\n' in buffer:
           line, buffer = buffer.split('\n', 1)
           if line.strip():
               handle_message(json.loads(line))
   ```

3. **Connection Pooling:**
   ```python
   class TCPConnectionPool:
       def __init__(self, max_connections=5):
           self.pool = []
           self.max_connections = max_connections
       
       async def get_connection(self):
           if self.pool:
               return self.pool.pop()
           return await self.create_connection()
   ```

## Authentication Problems

### Problem: Authentication Failed

**Symptoms:**
- "Not authenticated" errors
- Invalid API key messages
- Permission denied responses

**Diagnosis:**
```python
# Test API key validity
import requests

response = requests.get('http://localhost:8080/api/info')
print("API Info:", response.json())

# Test authentication
auth_test = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "authenticate",
    "params": {"api_key": "your-api-key"}
}
```

**Solutions:**

1. **Verify API Key:**
   ```bash
   # Check configuration
   grep -A 5 "api_keys:" config/config.yaml
   
   # Test with demo key
   echo '{"jsonrpc":"2.0","id":1,"method":"authenticate","params":{"api_key":"demo-key-123"}}' | websocat ws://localhost:8080/ws
   ```

2. **Check Permissions:**
   ```yaml
   api:
     auth:
       api_keys:
         - key: "your-api-key"
           mud_name: "YourMUD"
           permissions: ["tell", "channel", "info"]  # Add required permissions
   ```

3. **Session Management:**
   ```python
   class SessionManager:
       def __init__(self):
           self.session_id = None
           self.authenticated = False
       
       async def authenticate(self, api_key):
           # Store session info for reconnection
           response = await self.send_auth_request(api_key)
           if response["result"]["status"] == "authenticated":
               self.session_id = response["result"]["session_id"]
               self.authenticated = True
   ```

### Problem: Session Expires

**Symptoms:**
- "Session expired" errors
- Need to re-authenticate frequently
- Lost session state

**Solutions:**

1. **Session Persistence:**
   ```python
   async def restore_session(self):
       if self.session_id:
           # Try to restore existing session
           restore_msg = {
               "jsonrpc": "2.0",
               "id": 1,
               "method": "restore_session",
               "params": {"session_id": self.session_id}
           }
           await self.send_message(restore_msg)
   ```

2. **Activity Tracking:**
   ```python
   async def keep_alive(self):
       while self.authenticated:
           await self.ping()
           await asyncio.sleep(300)  # Every 5 minutes
   ```

3. **Configuration Adjustment:**
   ```yaml
   api:
     session:
       timeout: 7200  # Increase to 2 hours
   ```

## Message Delivery Issues

### Problem: Messages Not Delivered

**Symptoms:**
- No response to API calls
- Events not received
- Tell/channel messages lost

**Diagnosis:**
```python
# Add message tracking
class MessageTracker:
    def __init__(self):
        self.sent_messages = {}
        self.received_count = 0
    
    async def send_tracked_message(self, message):
        msg_id = message["id"]
        self.sent_messages[msg_id] = {
            "timestamp": time.time(),
            "message": message
        }
        await self.send_message(message)
    
    async def check_delivery(self):
        current_time = time.time()
        for msg_id, info in list(self.sent_messages.items()):
            if current_time - info["timestamp"] > 30:  # 30 second timeout
                print(f"Message {msg_id} not acknowledged")
                del self.sent_messages[msg_id]
```

**Solutions:**

1. **Check Gateway Connection:**
   ```python
   async def verify_gateway_connection(self):
       response = await self.ping()
       if not response:
           print("Gateway not responding to ping")
           await self.reconnect()
   ```

2. **Validate Message Format:**
   ```python
   def validate_message(self, message):
       required_fields = ["jsonrpc", "method"]
       if "id" not in message and message.get("method") != "authenticate":
           required_fields.append("id")
       
       for field in required_fields:
           if field not in message:
               raise ValueError(f"Missing required field: {field}")
       
       if message["jsonrpc"] != "2.0":
           raise ValueError("Invalid JSON-RPC version")
   ```

3. **Handle Rate Limiting:**
   ```python
   class RateLimitHandler:
       def __init__(self):
           self.request_times = []
       
       async def send_with_rate_limit(self, message):
           now = time.time()
           # Remove old requests (older than 1 minute)
           self.request_times = [t for t in self.request_times if now - t < 60]
           
           if len(self.request_times) >= 100:  # Rate limit
               wait_time = 60 - (now - self.request_times[0])
               await asyncio.sleep(wait_time)
           
           self.request_times.append(now)
           await self.send_message(message)
   ```

### Problem: Duplicate Messages

**Symptoms:**
- Same message received multiple times
- Duplicate events
- Message loop issues

**Solutions:**

1. **Message Deduplication:**
   ```python
   class MessageDeduplicator:
       def __init__(self, max_size=1000):
           self.seen_messages = set()
           self.max_size = max_size
       
       def is_duplicate(self, message):
           msg_hash = self.hash_message(message)
           if msg_hash in self.seen_messages:
               return True
           
           self.seen_messages.add(msg_hash)
           if len(self.seen_messages) > self.max_size:
               # Remove oldest (simple FIFO)
               self.seen_messages = set(list(self.seen_messages)[-self.max_size//2:])
           
           return False
       
       def hash_message(self, message):
           # Create hash from key fields
           key_fields = ["method", "from_user", "from_mud", "message", "timestamp"]
           key_data = {k: message.get(k) for k in key_fields if k in message}
           return hash(json.dumps(key_data, sort_keys=True))
   ```

2. **Idempotent Message Handling:**
   ```python
   async def handle_tell_received(self, params):
       # Check if already processed
       message_id = f"{params['from_mud']}:{params['from_user']}:{params['timestamp']}"
       if message_id in self.processed_tells:
           return
       
       # Process message
       await self.deliver_tell(params)
       self.processed_tells.add(message_id)
   ```

## Performance Problems

### Problem: High Latency

**Symptoms:**
- Slow message delivery
- High response times
- Delayed events

**Diagnosis:**
```python
import time

class LatencyMonitor:
    def __init__(self):
        self.request_times = {}
    
    async def send_timed_request(self, message):
        start_time = time.time()
        self.request_times[message["id"]] = start_time
        await self.send_message(message)
    
    async def handle_response(self, response):
        if response["id"] in self.request_times:
            latency = time.time() - self.request_times[response["id"]]
            print(f"Request {response['id']} latency: {latency:.3f}s")
            del self.request_times[response["id"]]
```

**Solutions:**

1. **Connection Optimization:**
   ```python
   # Use connection pooling
   import aiohttp
   
   async def create_optimized_session():
       connector = aiohttp.TCPConnector(
           limit=100,
           limit_per_host=30,
           keepalive_timeout=30
       )
       return aiohttp.ClientSession(connector=connector)
   ```

2. **Message Batching:**
   ```python
   class MessageBatcher:
       def __init__(self, batch_size=10, timeout=1.0):
           self.batch = []
           self.batch_size = batch_size
           self.timeout = timeout
           self.last_send = time.time()
       
       async def add_message(self, message):
           self.batch.append(message)
           
           if (len(self.batch) >= self.batch_size or 
               time.time() - self.last_send >= self.timeout):
               await self.send_batch()
       
       async def send_batch(self):
           if self.batch:
               await self.send_json_rpc_batch(self.batch)
               self.batch = []
               self.last_send = time.time()
   ```

3. **Async Processing:**
   ```python
   import asyncio
   from asyncio import Queue
   
   class AsyncMessageProcessor:
       def __init__(self, max_workers=10):
           self.queue = Queue()
           self.workers = []
           self.max_workers = max_workers
       
       async def start_workers(self):
           for i in range(self.max_workers):
               worker = asyncio.create_task(self.worker())
               self.workers.append(worker)
       
       async def worker(self):
           while True:
               message = await self.queue.get()
               try:
                   await self.process_message(message)
               except Exception as e:
                   print(f"Worker error: {e}")
               finally:
                   self.queue.task_done()
   ```

### Problem: Memory Leaks

**Symptoms:**
- Increasing memory usage
- Eventually running out of memory
- Slow garbage collection

**Solutions:**

1. **Connection Cleanup:**
   ```python
   class ConnectionManager:
       def __init__(self):
           self.connections = {}
       
       async def cleanup_connection(self, connection_id):
           if connection_id in self.connections:
               conn = self.connections[connection_id]
               if hasattr(conn, 'close'):
                   await conn.close()
               del self.connections[connection_id]
       
       async def periodic_cleanup(self):
           while True:
               # Clean up old connections
               current_time = time.time()
               to_remove = []
               
               for conn_id, conn in self.connections.items():
                   if current_time - conn.last_activity > 3600:  # 1 hour
                       to_remove.append(conn_id)
               
               for conn_id in to_remove:
                   await self.cleanup_connection(conn_id)
               
               await asyncio.sleep(300)  # Every 5 minutes
   ```

2. **Message Queue Limits:**
   ```python
   from collections import deque
   
   class BoundedMessageQueue:
       def __init__(self, maxsize=1000):
           self.queue = deque(maxlen=maxsize)
       
       def add_message(self, message):
           if len(self.queue) >= self.queue.maxlen:
               dropped = self.queue.popleft()
               print(f"Dropped message due to queue full: {dropped}")
           
           self.queue.append(message)
   ```

## Event Handling Issues

### Problem: Events Not Received

**Symptoms:**
- Missing tell notifications
- Channel messages not appearing
- System events ignored

**Solutions:**

1. **Event Registration:**
   ```python
   class EventHandler:
       def __init__(self):
           self.handlers = {}
       
       def register_handler(self, event_type, handler):
           if event_type not in self.handlers:
               self.handlers[event_type] = []
           self.handlers[event_type].append(handler)
       
       async def handle_event(self, event_type, params):
           if event_type in self.handlers:
               for handler in self.handlers[event_type]:
                   try:
                       await handler(params)
                   except Exception as e:
                       print(f"Event handler error: {e}")
   ```

2. **Subscription Management:**
   ```python
   async def ensure_subscriptions(self):
       # Re-subscribe to channels on reconnection
       for channel in self.subscribed_channels:
           await self.channel_join(channel)
   ```

### Problem: Event Processing Errors

**Symptoms:**
- Event handlers crashing
- Events being dropped
- Error messages in logs

**Solutions:**

1. **Error Handling:**
   ```python
   async def safe_event_handler(self, event_type, params):
       try:
           await self.handlers[event_type](params)
       except KeyError:
           print(f"No handler for event type: {event_type}")
       except Exception as e:
           print(f"Error handling {event_type}: {e}")
           # Log to file for debugging
           self.log_error(event_type, params, str(e))
   ```

2. **Event Validation:**
   ```python
   def validate_event(self, event_type, params):
       required_fields = {
           "tell_received": ["from_mud", "from_user", "to_user", "message"],
           "channel_message": ["channel", "from_mud", "from_user", "message"],
           "mud_online": ["mud_name", "info"]
       }
       
       if event_type in required_fields:
           for field in required_fields[event_type]:
               if field not in params:
                   raise ValueError(f"Missing required field: {field}")
   ```

## Configuration Problems

### Problem: Invalid Configuration

**Symptoms:**
- Gateway won't start
- Configuration parsing errors
- Missing required settings

**Solutions:**

1. **Configuration Validation:**
   ```python
   import yaml
   from jsonschema import validate
   
   def validate_config(config_file):
       schema = {
           "type": "object",
           "required": ["api", "gateway"],
           "properties": {
               "api": {
                   "type": "object",
                   "required": ["host", "port"],
                   "properties": {
                       "host": {"type": "string"},
                       "port": {"type": "integer", "minimum": 1, "maximum": 65535}
                   }
               }
           }
       }
       
       with open(config_file, 'r') as f:
           config = yaml.safe_load(f)
       
       validate(config, schema)
       return config
   ```

2. **Environment Variable Handling:**
   ```bash
   # Check environment variables
   env | grep I3_
   env | grep API_
   
   # Set required variables
   export I3_GATEWAY_SECRET="your-secret"
   export API_KEY_YOURMUD="your-api-key"
   ```

3. **Configuration Templates:**
   ```yaml
   # minimal-config.yaml
   api:
     host: "localhost"
     port: 8080
     websocket:
       enabled: true
     auth:
       enabled: false  # For testing only
   
   gateway:
     host: "localhost"
     port: 4001
   
   logging:
     level: "DEBUG"
   ```

## Debugging Techniques

### Enable Debug Logging

```python
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('i3_debug.log'),
        logging.StreamHandler()
    ]
)

# Log all messages
class DebugI3Client(I3Client):
    async def send_message(self, message):
        logging.debug(f"SEND: {json.dumps(message, indent=2)}")
        await super().send_message(message)
    
    async def handle_message(self, message):
        logging.debug(f"RECV: {json.dumps(message, indent=2)}")
        await super().handle_message(message)
```

### Network Debugging

```bash
# Capture network traffic
tcpdump -i lo -A -s 0 port 8080

# Monitor WebSocket traffic
websocat -v ws://localhost:8080/ws

# Test with curl
curl -H "Upgrade: websocket" \
     -H "Connection: Upgrade" \
     -H "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" \
     -H "Sec-WebSocket-Version: 13" \
     http://localhost:8080/ws
```

### Message Tracing

```python
class MessageTracer:
    def __init__(self):
        self.trace_file = open('message_trace.log', 'w')
    
    def trace_send(self, message):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.trace_file.write(f"[{timestamp}] SEND: {json.dumps(message)}\n")
        self.trace_file.flush()
    
    def trace_receive(self, message):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        self.trace_file.write(f"[{timestamp}] RECV: {json.dumps(message)}\n")
        self.trace_file.flush()
```

### Performance Profiling

```python
import cProfile
import pstats

def profile_function(func):
    """Decorator to profile function performance."""
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = func(*args, **kwargs)
        pr.disable()
        
        stats = pstats.Stats(pr)
        stats.sort_stats('cumulative')
        stats.print_stats(10)  # Top 10 functions
        
        return result
    return wrapper

@profile_function
async def process_messages(self):
    # Your message processing code
    pass
```

## Error Code Reference

### JSON-RPC Standard Errors

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| -32700 | Parse Error | Invalid JSON | Check message formatting |
| -32600 | Invalid Request | Not valid JSON-RPC | Verify required fields |
| -32601 | Method Not Found | Unknown method | Check method name spelling |
| -32602 | Invalid Params | Wrong parameters | Validate parameter types |
| -32603 | Internal Error | Server error | Check server logs |

### Gateway-Specific Errors

| Code | Name | Description | Solution |
|------|------|-------------|----------|
| -32000 | Not Authenticated | Missing/invalid auth | Check API key |
| -32001 | Rate Limit Exceeded | Too many requests | Implement rate limiting |
| -32002 | Permission Denied | Insufficient permissions | Check permissions config |
| -32003 | Session Expired | Session timeout | Re-authenticate |
| -32004 | Gateway Error | I3 network issue | Check I3 connection |

## Common Solutions

### Restart Gateway Safely

```bash
# Graceful restart
systemctl reload i3-gateway

# Or with signal
kill -USR1 $(pgrep -f i3-gateway)

# Force restart if needed
systemctl restart i3-gateway
```

### Reset Gateway State

```bash
# Clear state directory
rm -rf state/*

# Reset logs
truncate -s 0 logs/i3-gateway.log

# Restart with clean state
systemctl restart i3-gateway
```

### Emergency Debugging Mode

```yaml
# debug-config.yaml
logging:
  level: "DEBUG"
  components:
    network: "DEBUG"
    api: "DEBUG"
    services: "DEBUG"

api:
  auth:
    enabled: false  # Disable auth for debugging
  rate_limits:
    default:
      per_minute: 10000  # Remove rate limits

development:
  debug: true
  profile: true
```

### Connection Recovery Script

```python
#!/usr/bin/env python3
"""
Emergency connection recovery script
"""
import asyncio
import json
import sys

async def test_connection():
    """Test basic connection to gateway."""
    try:
        import websockets
        
        uri = "ws://localhost:8080/ws"
        async with websockets.connect(uri) as ws:
            # Send ping
            ping_msg = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "ping"
            }
            await ws.send(json.dumps(ping_msg))
            
            # Wait for response
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get("result", {}).get("pong"):
                print("✓ Gateway is responding")
                return True
            else:
                print("✗ Gateway not responding correctly")
                return False
                
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

async def main():
    """Main recovery function."""
    print("Testing I3 Gateway connection...")
    
    if await test_connection():
        print("Gateway appears to be working correctly")
        sys.exit(0)
    else:
        print("Gateway connection failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
```

## Getting Help

### Information to Collect

When reporting issues, include:

1. **Gateway version and configuration**
2. **Complete error messages and stack traces**
3. **Network topology and firewall settings**
4. **System resource usage (CPU, memory, disk)**
5. **Steps to reproduce the issue**
6. **Message traces and logs**

### Log Collection Script

```bash
#!/bin/bash
# collect_logs.sh - Collect diagnostic information

LOGDIR="i3_diagnostics_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOGDIR"

echo "Collecting I3 Gateway diagnostics..."

# System information
uname -a > "$LOGDIR/system_info.txt"
free -h > "$LOGDIR/memory.txt"
df -h > "$LOGDIR/disk.txt"
ps aux | grep i3 > "$LOGDIR/processes.txt"

# Network information
netstat -tulpn > "$LOGDIR/network.txt"
ss -tulpn > "$LOGDIR/sockets.txt"

# Gateway logs
cp logs/i3-gateway.log "$LOGDIR/" 2>/dev/null || echo "No log file found"
cp config/config.yaml "$LOGDIR/" 2>/dev/null || echo "No config file found"

# Test connectivity
curl -s http://localhost:8080/health > "$LOGDIR/health_check.txt" 2>&1
curl -s http://localhost:8080/metrics > "$LOGDIR/metrics.txt" 2>&1

echo "Diagnostics collected in $LOGDIR/"
tar -czf "${LOGDIR}.tar.gz" "$LOGDIR"
echo "Archive created: ${LOGDIR}.tar.gz"
```

This troubleshooting guide covers the most common issues you'll encounter when integrating with the Intermud3 Gateway. Use the diagnostic techniques and solutions provided to quickly identify and resolve problems. For complex issues, the debugging techniques and log collection tools will help you gather the information needed for further investigation.