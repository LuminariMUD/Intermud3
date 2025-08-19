# Phase 3: Gateway API Protocol Implementation Plan

## Executive Summary

Phase 3 focuses on implementing the JSON-RPC API layer that serves as the bridge between MUD servers and the I3 Gateway. This phase builds upon the robust foundation from Phase 1 (protocol implementation, data models, state management) and the complete core services from Phase 2 (tell, channel, who, finger, locate, router). The API layer will enable any MUD, regardless of codebase or language, to integrate with the Intermud-3 network through a simple, well-documented protocol.

**Duration**: 12 days (2-3 weeks)
**Priority**: Critical - Required for MUD integration
**Risk Level**: Medium - API design must balance simplicity with functionality

## Status: IN PROGRESS (2025-01-20)

Phase 3 implementation has begun, building on the successful completion of Phases 1 and 2.

## Phase 3 Objectives

### Primary Goals
1. **JSON-RPC Server Implementation** - Complete API server accepting WebSocket and TCP connections
2. **MUD Client Protocol** - Bidirectional communication protocol for seamless MUD integration
3. **Authentication & Session Management** - Secure client connections with persistent session tracking
4. **Event Distribution System** - Real-time event delivery to connected MUDs
5. **Client Libraries & Examples** - Reference implementations for popular MUD codebases

### Secondary Goals
- Performance optimization for high-throughput scenarios
- Comprehensive error handling and recovery
- Extensive documentation and integration guides
- Load testing and benchmarking suite

## Technical Architecture

### System Overview
```
+----------------------------------------------------------+
|                    MUD Server                            |
|  (CircleMUD, TinyMUD, LPMud, Custom, etc.)              |
+----------------------------------------------------------+
                         |
                    JSON-RPC 2.0
                    (WebSocket/TCP)
                         |
+----------------------------------------------------------+
|                  API Gateway Layer                       |
|  +--------------------------------------------------+    |
|  |  WebSocket Server    |    TCP Server            |    |
|  +--------------------------------------------------+    |
|  |  JSON-RPC Handler    |    Protocol Validator    |    |
|  +--------------------------------------------------+    |
|  |  Session Manager     |    Auth Middleware       |    |
|  +--------------------------------------------------+    |
|  |  Request Router      |    Event Dispatcher      |    |
|  +--------------------------------------------------+    |
+----------------------------------------------------------+
                         |
                    Internal API
                         |
+----------------------------------------------------------+
|              Core I3 Services (Phase 2)                  |
|  (Tell, Channel, Who, Finger, Locate, Router)           |
+----------------------------------------------------------+
                         |
                    I3 Protocol
                    (MudMode/LPC)
                         |
+----------------------------------------------------------+
|              Global Intermud-3 Network                   |
+----------------------------------------------------------+
```

### API Protocol Design

#### Transport Layer
- **Primary**: WebSocket for real-time bidirectional communication
- **Fallback**: TCP Socket for compatibility with older systems
- **Encoding**: UTF-8 JSON messages
- **Framing**: Line-delimited for TCP, WebSocket frames for WS

#### Message Format
```json
// Request (MUD -> Gateway)
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "method": "tell",
  "params": {
    "target_mud": "OtherMUD",
    "target_user": "PlayerName",
    "message": "Hello from our MUD!"
  }
}

// Response (Gateway -> MUD)
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "result": {
    "status": "success",
    "message": "Tell delivered successfully"
  }
}

// Event (Gateway -> MUD)
{
  "jsonrpc": "2.0",
  "method": "tell_received",
  "params": {
    "from_mud": "RemoteMUD",
    "from_user": "Sender",
    "message": "Hello back!",
    "timestamp": "2025-01-20T10:30:00Z"
  }
}

// Error Response
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
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

### Session Management Architecture

```python
class Session:
    session_id: str
    mud_name: str
    api_key: str
    connected_at: datetime
    last_activity: datetime
    subscriptions: Set[str]  # Channel subscriptions
    message_queue: Queue      # Offline message buffer
    rate_limiter: RateLimiter
    metrics: SessionMetrics
```

## Implementation Milestones

### Milestone 1: API Server Foundation (Days 1-2)

#### Tasks
1. **WebSocket Server Implementation** (`src/api/server.py`)
   - aiohttp-based WebSocket server
   - Connection lifecycle management
   - Heartbeat/ping-pong mechanism
   - Graceful shutdown handling

2. **TCP Socket Server** (`src/api/tcp_server.py`)
   - Async TCP server for legacy support
   - Line-delimited JSON protocol
   - Connection pooling

3. **Protocol Handler** (`src/api/protocol.py`)
   - JSON-RPC 2.0 parsing and validation
   - Request/response correlation
   - Batch request support
   - Error formatting

4. **Base Infrastructure** (`src/api/__init__.py`)
   - Server initialization
   - Configuration loading
   - Logging setup

#### Code Structure
```python
# src/api/server.py
class APIServer:
    """Main API server coordinating WebSocket and TCP servers."""
    
    async def start(self):
        """Start both WebSocket and TCP servers."""
        
    async def handle_websocket(self, request):
        """Handle WebSocket connection."""
        
    async def process_message(self, session, message):
        """Process incoming JSON-RPC message."""

# src/api/protocol.py
class JSONRPCProtocol:
    """JSON-RPC 2.0 protocol implementation."""
    
    def parse_request(self, data: str) -> JSONRPCRequest:
        """Parse and validate JSON-RPC request."""
        
    def format_response(self, result: Any) -> str:
        """Format JSON-RPC response."""
        
    def format_error(self, code: int, message: str) -> str:
        """Format JSON-RPC error response."""
```

### Milestone 2: Request Handlers (Days 3-4)

#### Tasks
1. **Communication Handlers** (`src/api/handlers/communication.py`)
   - `tell`: Send direct message
   - `emoteto`: Send emote
   - `channel_send`: Send channel message
   - `channel_emote`: Send channel emote

2. **Information Handlers** (`src/api/handlers/information.py`)
   - `who`: List users on MUD
   - `finger`: Get user information
   - `locate`: Find user on network
   - `mudlist`: Get list of connected MUDs

3. **Channel Management** (`src/api/handlers/channels.py`)
   - `channel_join`: Join a channel
   - `channel_leave`: Leave a channel
   - `channel_list`: List available channels
   - `channel_who`: List channel members
   - `channel_history`: Get channel message history

4. **Administrative Handlers** (`src/api/handlers/admin.py`)
   - `status`: Gateway connection status
   - `stats`: Performance statistics
   - `ping`: Heartbeat check
   - `reconnect`: Force router reconnection

#### Handler Interface
```python
# src/api/handlers/base.py
class BaseHandler:
    """Base class for API handlers."""
    
    @abstractmethod
    async def handle(self, session: Session, params: Dict) -> Any:
        """Handle API request."""
        
    @abstractmethod
    def validate_params(self, params: Dict) -> bool:
        """Validate request parameters."""

# Example implementation
class TellHandler(BaseHandler):
    async def handle(self, session: Session, params: Dict) -> Dict:
        # Validate parameters
        if not self.validate_params(params):
            raise InvalidParamsError()
        
        # Create I3 packet
        packet = TellPacket(
            originator_mud=session.mud_name,
            originator_user=params.get("from_user", ""),
            target_mud=params["target_mud"],
            target_user=params["target_user"],
            message=params["message"]
        )
        
        # Send via gateway
        await self.gateway.send_packet(packet)
        
        return {"status": "success", "message": "Tell sent"}
```

### Milestone 3: Event Distribution System (Days 5-6)

#### Tasks
1. **Event Dispatcher** (`src/api/events.py`)
   - Event registration and routing
   - Subscription management
   - Event filtering and transformation
   - Priority queue for events

2. **Event Types Implementation**
   ```python
   # Communication Events
   - tell_received
   - emoteto_received
   - channel_message
   - channel_emote
   
   # System Events
   - mud_online
   - mud_offline
   - channel_joined
   - channel_left
   - error_occurred
   - gateway_reconnected
   ```

3. **Subscription Management** (`src/api/subscriptions.py`)
   - Channel subscription tracking
   - Event filtering rules
   - Subscription persistence
   - Rate limiting per subscription

4. **Event Queue** (`src/api/queue.py`)
   - Message buffering for offline clients
   - Queue overflow handling
   - Message TTL and cleanup
   - Priority message support

#### Event System Architecture
```python
# src/api/events.py
class EventDispatcher:
    """Manages event distribution to connected clients."""
    
    async def dispatch(self, event: Event):
        """Dispatch event to subscribed sessions."""
        for session in self.get_subscribers(event.type):
            if self.should_send(session, event):
                await self.send_event(session, event)
    
    async def send_event(self, session: Session, event: Event):
        """Send event to specific session."""
        message = self.format_event(event)
        
        if session.is_connected:
            await session.send(message)
        else:
            await session.queue_message(message)
```

### Milestone 4: Session & Authentication (Days 7-8)

#### Tasks
1. **Session Manager** (`src/api/session.py`)
   - Session creation and lifecycle
   - Session persistence across reconnects
   - Activity tracking and timeout
   - Metrics collection per session

2. **Authentication Middleware** (`src/api/auth.py`)
   - API key validation
   - Permission checking
   - Rate limiting enforcement
   - IP allowlist/blocklist

3. **State Management** (`src/api/state.py`)
   - Per-client state tracking
   - Channel membership state
   - Message history buffers
   - Statistics aggregation

4. **Security Implementation**
   ```python
   class AuthMiddleware:
       async def authenticate(self, request: Request) -> Session:
           """Authenticate incoming request."""
           api_key = request.headers.get("X-API-Key")
           
           if not api_key:
               raise AuthenticationError("API key required")
           
           session = await self.validate_api_key(api_key)
           
           # Check rate limits
           if not await self.rate_limiter.check(session):
               raise RateLimitError("Rate limit exceeded")
           
           return session
   ```

### Milestone 5: Client Libraries & Documentation (Days 9-10)

#### Tasks
1. **Python Client Library** (`clients/python/i3_client.py`)
   ```python
   class I3Client:
       """Python client for I3 Gateway API."""
       
       async def connect(self, url: str, api_key: str):
           """Connect to gateway."""
           
       async def tell(self, target_mud: str, target_user: str, message: str):
           """Send a tell."""
           
       def on_tell_received(self, callback: Callable):
           """Register tell received handler."""
   ```

2. **Example Implementations**
   - `clients/examples/simple_mud.py`: Basic integration
   - `clients/examples/channel_bot.py`: Channel bot example
   - `clients/examples/relay_bridge.py`: Discord/IRC bridge
   - `clients/examples/web_client.py`: Web interface

3. **Documentation Suite**
   - `docs/API_REFERENCE.md`: Complete API documentation
   - `docs/INTEGRATION_GUIDE.md`: Step-by-step integration
   - `docs/TROUBLESHOOTING.md`: Common issues and solutions
   - `docs/PERFORMANCE_TUNING.md`: Optimization guide

4. **Code Examples for Multiple Languages**
   ```javascript
   // JavaScript/Node.js example
   const I3Client = require('i3-gateway-client');
   
   const client = new I3Client({
     url: 'ws://localhost:8080',
     apiKey: 'your-api-key'
   });
   
   client.on('tell_received', (data) => {
     console.log(`Tell from ${data.from_user}@${data.from_mud}: ${data.message}`);
   });
   ```

### Milestone 6: Testing & Optimization (Days 11-12)

#### Tasks
1. **Unit Test Suite** (`tests/unit/`)
   - Protocol parsing tests
   - Handler validation tests
   - Session management tests
   - Event distribution tests

2. **Integration Tests** (`tests/integration/`)
   - End-to-end message flow
   - Multi-client scenarios
   - Reconnection handling
   - Error recovery

3. **Performance Testing** (`tests/performance/`)
   ```python
   class APIPerformanceTests:
       async def test_concurrent_connections(self):
           """Test with 1000+ concurrent connections."""
           
       async def test_message_throughput(self):
           """Test 5000+ messages/second."""
           
       async def test_event_latency(self):
           """Test event distribution <50ms."""
   ```

4. **Load Testing** (`tests/load/`)
   - Sustained load testing
   - Spike testing
   - Soak testing
   - Stress testing

## Configuration Schema

```yaml
# config/config.yaml - API section
api:
  enabled: true
  host: "0.0.0.0"
  port: 8080
  
  # WebSocket configuration
  websocket:
    enabled: true
    max_connections: 1000
    ping_interval: 30        # seconds
    ping_timeout: 10         # seconds
    max_frame_size: 65536    # bytes
    compression: true
    
  # TCP socket configuration  
  tcp:
    enabled: true
    port: 8081
    max_connections: 500
    buffer_size: 4096
    
  # Authentication settings
  auth:
    enabled: true
    require_tls: false
    api_keys:
      - key: "demo-key-123"
        mud_name: "DemoMUD"
        permissions: ["tell", "channel", "info"]
        rate_limit_override: 200  # messages/minute
      - key: "admin-key-456"
        mud_name: "AdminMUD"
        permissions: ["*"]  # All permissions
        
  # Rate limiting
  rate_limits:
    default:
      per_minute: 100
      burst: 20
    by_method:
      tell: 30
      channel_send: 50
      who: 10
      mudlist: 5
      
  # Session management
  session:
    timeout: 3600            # seconds (1 hour)
    max_queue_size: 1000     # messages
    queue_ttl: 300           # seconds
    cleanup_interval: 60     # seconds
    
  # Monitoring
  metrics:
    enabled: true
    export_interval: 60      # seconds
    include_details: true
```

## API Method Reference

### Communication Methods

#### tell
Send a direct message to a user on another MUD.
```json
{
  "method": "tell",
  "params": {
    "target_mud": "string",
    "target_user": "string",
    "message": "string",
    "from_user": "string (optional)"
  }
}
```

#### channel_send
Send a message to a channel.
```json
{
  "method": "channel_send",
  "params": {
    "channel": "string",
    "message": "string",
    "from_user": "string (optional)"
  }
}
```

### Information Methods

#### who
List users on a MUD.
```json
{
  "method": "who",
  "params": {
    "target_mud": "string",
    "filters": {
      "min_level": "number (optional)",
      "max_level": "number (optional)",
      "race": "string (optional)",
      "guild": "string (optional)"
    }
  }
}
```

#### mudlist
Get list of all MUDs on the network.
```json
{
  "method": "mudlist",
  "params": {
    "refresh": "boolean (optional, default: false)",
    "filter": {
      "status": "string (optional: 'up', 'down')",
      "driver": "string (optional)",
      "has_service": "string (optional)"
    }
  }
}
```

### Channel Management

#### channel_join
Join a channel.
```json
{
  "method": "channel_join",
  "params": {
    "channel": "string",
    "listen_only": "boolean (optional, default: false)"
  }
}
```

## Event Reference

### Communication Events

#### tell_received
Received when a tell arrives for a user.
```json
{
  "method": "tell_received",
  "params": {
    "from_mud": "string",
    "from_user": "string",
    "to_user": "string",
    "message": "string",
    "timestamp": "ISO 8601 datetime"
  }
}
```

#### channel_message
Received when a message is sent to a subscribed channel.
```json
{
  "method": "channel_message",
  "params": {
    "channel": "string",
    "from_mud": "string",
    "from_user": "string",
    "message": "string",
    "timestamp": "ISO 8601 datetime"
  }
}
```

### System Events

#### mud_online
Notifies when a MUD comes online.
```json
{
  "method": "mud_online",
  "params": {
    "mud_name": "string",
    "info": {
      "driver": "string",
      "mud_type": "string",
      "services": ["array of strings"],
      "admin_email": "string"
    }
  }
}
```

## Performance Targets

### Latency Requirements
- **API Call Response**: <50ms (p99)
- **Event Distribution**: <30ms (p99)
- **Tell Delivery**: <100ms end-to-end
- **Channel Message**: <75ms to all subscribers

### Throughput Requirements
- **Messages/Second**: 5000+ sustained
- **Concurrent Connections**: 1000+ WebSocket
- **Events/Second**: 10000+ distribution
- **Requests/Second**: 2000+ API calls

### Resource Requirements
- **Memory**: <200MB for 1000 clients
- **CPU**: <70% single core at peak
- **Network**: <10Mbps for 1000 clients
- **Storage**: <1GB for message queues

## Testing Strategy

### Unit Test Coverage Goals
- API Server: 85% coverage
- Protocol Handler: 95% coverage
- Request Handlers: 90% coverage
- Event System: 85% coverage
- Session Management: 90% coverage
- Overall: >85% coverage

### Test Categories
1. **Protocol Tests**: JSON-RPC compliance
2. **Handler Tests**: Request processing logic
3. **Event Tests**: Distribution and filtering
4. **Session Tests**: Lifecycle and persistence
5. **Security Tests**: Auth and rate limiting
6. **Performance Tests**: Load and stress testing
7. **Integration Tests**: End-to-end flows

### Test Data
Create fixtures for:
- Sample API requests (all methods)
- WebSocket frames
- Event payloads
- Session states
- Error scenarios

## Security Considerations

### Authentication
- API key required for all connections
- Optional TLS/SSL support
- IP allowlist/blocklist capability
- Session tokens with expiration

### Authorization
- Per-method permission checking
- MUD-specific access controls
- Channel access restrictions
- Admin-only operations

### Rate Limiting
- Per-session rate limits
- Per-method rate limits
- Burst allowance
- Graceful degradation

### Input Validation
- JSON schema validation
- Parameter type checking
- Message length limits
- Injection prevention

## Success Criteria

### Functional Requirements
- [ ] WebSocket server operational
- [ ] TCP server operational
- [ ] JSON-RPC 2.0 compliant
- [ ] All core methods implemented
- [ ] Event distribution working
- [ ] Session persistence functional
- [ ] Authentication/authorization working
- [ ] Rate limiting enforced
- [ ] Client library functional
- [ ] Documentation complete

### Non-Functional Requirements
- [ ] API latency <50ms (p99)
- [ ] 5000+ msg/sec throughput
- [ ] 1000+ concurrent connections
- [ ] Memory usage <200MB
- [ ] CPU usage <70%
- [ ] Zero message loss
- [ ] 99.9% uptime
- [ ] <30s recovery time

### Documentation Requirements
- [ ] API reference complete
- [ ] Integration guide written
- [ ] Code examples provided
- [ ] Troubleshooting guide done
- [ ] Performance tuning guide
- [ ] Security best practices

## Risk Assessment

### Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| WebSocket incompatibility | High | Low | TCP fallback, compatibility testing |
| Performance bottlenecks | High | Medium | Early load testing, profiling |
| Memory leaks | High | Low | Regular profiling, cleanup handlers |
| Protocol ambiguities | Medium | Medium | Clear documentation, examples |
| Integration complexity | Medium | High | Simple examples, good docs |

### Schedule Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| API design iterations | Medium | High | Early feedback, prototyping |
| Testing takes longer | Low | Medium | Automated test suite |
| Documentation lag | Low | Low | Document as we code |
| Client library bugs | Medium | Medium | Extensive examples |

## Dependencies and Prerequisites

### External Dependencies
```python
# requirements.txt additions
aiohttp>=3.9.0      # WebSocket server
jsonschema>=4.0     # JSON validation
redis>=4.5.0        # Session storage (optional)
prometheus-client>=0.16.0  # Metrics export
```

### Development Dependencies
```python
# requirements-dev.txt additions
websocket-client>=1.5.0  # Testing WebSocket
locust>=2.0         # Load testing
pytest-benchmark>=4.0  # Performance testing
```

## Implementation Status

### Completed Components
- [ ] API server foundation
- [ ] JSON-RPC protocol handler
- [ ] Session management
- [ ] Authentication middleware
- [ ] Request handlers
- [ ] Event distribution
- [ ] Client library
- [ ] Documentation
- [ ] Unit tests
- [ ] Integration tests
- [ ] Load tests

### Current Focus
Starting with API server foundation and JSON-RPC protocol implementation.

## Next Steps

### Immediate Actions (Day 1)
1. Set up API server structure
2. Implement WebSocket handler
3. Create JSON-RPC parser
4. Write initial tests

### Day 2-3
1. Complete protocol handler
2. Implement session management
3. Add authentication
4. Create first handlers

### Daily Checklist
- [ ] Morning: Review progress, adjust plan
- [ ] Coding: Focus on current milestone
- [ ] Testing: Write tests for new code
- [ ] Documentation: Update as needed
- [ ] Evening: Commit, update progress

## Conclusion

Phase 3 represents the critical bridge between the robust I3 protocol implementation and actual MUD integration. By providing a clean, well-documented JSON-RPC API, we enable any MUD to join the Intermud-3 network regardless of their technology stack.

The emphasis on real-time event distribution, session persistence, and comprehensive client libraries ensures that MUD developers can integrate quickly and reliably. With strong testing and documentation, Phase 3 will deliver a production-ready API that can scale to support hundreds of MUDs and thousands of concurrent players.

Success in Phase 3 is measured not just by technical implementation but by the ease of integration for MUD developers. The goal is to make joining the I3 network as simple as possible while maintaining the robustness and reliability expected of critical game infrastructure.