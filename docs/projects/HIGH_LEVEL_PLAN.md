# Intermud3 Gateway High-Level Implementation Plan

## Executive Summary

This document outlines the implementation plan for an Intermud3 (I3) gateway service that will act as a standalone protocol handler for the global Intermud network. The gateway is built in Python and provides a simple text-based API that any MUD can integrate with, regardless of their codebase language.

## Project Goals

### Primary Objectives
- Create a standalone I3 protocol gateway service
- Maintain complete isolation between I3 protocol complexity and MUD implementations
- Provide a simple, well-documented API for MUD integration
- Enable seamless intermud communication capabilities

### Design Principles
- **Separation of Concerns**: I3 protocol handling completely separate from game logic
- **Language Agnostic**: Any MUD can integrate via simple TCP protocol
- **Fault Tolerance**: Gateway failures don't affect MUD operation
- **Maintainability**: Clean interfaces and modular design
- **Performance**: Minimal latency for message delivery
- **Security**: Input validation and sandboxing of network data

## System Architecture

```
+----------------------------------------------------------+
|                  Global I3 Network                       |
|         (Other MUDs, Routers, Services)                  |
+------------------------+---------------------------------+
                         |
                         | mudmode protocol
                         | (LPC data structures)
                         |
+------------------------v---------------------------------+
|              I3 Gateway Service (Python)                 |
|  +----------------------------------------------------+  |
|  | - Router Connection Manager                       |  |
|  | - Packet Router & Dispatcher                      |  |
|  | - Service Implementations                         |  |
|  | - State Management & Caching                      |  |
|  | - OOB Connection Handler                          |  |
|  +----------------------------------------------------+  |
+------------------------+---------------------------------+
                         |
                         | Simple text protocol
                         | (JSON-RPC over TCP)
                         |
+------------------------v---------------------------------+
|              MUD Server (Any Language)                   |
|  +----------------------------------------------------+  |
|  | - Gateway client implementation                   |  |
|  | - Command parsing                                 |  |
|  | - Message display                                 |  |
|  | - Event handling                                  |  |
|  +----------------------------------------------------+  |
+------------------------+---------------------------------+
                         |
+------------------------v---------------------------------+
|                    MUD Players                           |
+----------------------------------------------------------+
```

## Implementation Phases

### Phase 1: Foundation Infrastructure (Week 1) COMPLETED

#### 1.1 Project Structure
```
Intermud3/
├── src/
│   ├── __init__.py
│   ├── __main__.py
│   ├── gateway.py
│   ├── network/
│   │   ├── __init__.py
│   │   ├── mudmode.py
│   │   ├── connection.py
│   │   └── packet.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── tell.py
│   │   ├── channel.py
│   │   └── who.py
│   ├── models/
│   │   └── __init__.py
│   ├── state/
│   │   └── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   └── models.py
│   └── utils/
│       ├── __init__.py
│       └── logging.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── config/
│   └── config.yaml
├── docs/
│   ├── HIGH_LEVEL_PLAN.md
│   ├── TODO.md
│   └── intermud3_docs/
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── Makefile
└── docker-compose.yml
```

#### 1.2 Core Components

**Network Layer**
- MudOS "mudmode" protocol implementation
- LPC data structure serialization/deserialization
- Binary packet handling with proper byte ordering
- TCP connection management with keepalive

**Data Structures**
```python
class I3Packet:
    packet_type: str
    ttl: int
    originator_mud: str
    originator_user: str
    target_mud: str
    target_user: str
    payload: List[Any]
```

**Configuration Management**
```yaml
# config.yaml
gateway:
  host: localhost
  port: 4000
  
router:
  primary: "*i3"
  address: "204.209.44.3"
  port: 8080
  
mud:
  name: "Luminari"
  port: 4100
  admin_email: "admin@luminari.com"
  
services:
  tell: enabled
  channel: enabled
  who: enabled
```

### Phase 2: Gateway Core Services (Week 1-2) ✅ COMPLETE

#### 2.1 Router Connection Management

**Startup Sequence**
1. Connect to primary router
2. Send startup-req-3 packet
3. Process startup-reply 
4. Handle mudlist updates
5. Maintain heartbeat

**Connection States**
```python
class ConnectionState(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    AUTHENTICATING = 2
    CONNECTED = 3
    RECONNECTING = 4
```

#### 2.2 Packet Processing Pipeline

```python
class PacketProcessor:
    def process(self, raw_data: bytes) -> None:
        packet = self.decode(raw_data)
        self.validate(packet)
        self.route(packet)
    
    def route(self, packet: I3Packet) -> None:
        handler = self.handlers.get(packet.packet_type)
        if handler:
            handler.handle(packet)
```

#### 2.3 Service Registry

**Core Services Implementation Priority**
1. tell - Direct messaging (Critical)
2. channel - Channel communication (Critical)
3. who - User listings (Important)
4. finger - User information (Important)
5. locate - User search (Important)
6. emoteto - Emotes (Nice to have)

### Phase 3: Gateway API Protocol (Week 2) 🔄 IN PROGRESS (60% Complete)

#### 3.1 Gateway Protocol Specification

The gateway exposes a simple JSON-RPC protocol over TCP that any MUD can connect to.

**Command Format (MUD to Gateway)**
```json
{
  "id": 1,
  "method": "tell",
  "params": {
    "target_user": "player",
    "target_mud": "OtherMUD",
    "message": "Hello there!"
  }
}
```

**Response Format (Gateway to MUD)**
```json
{
  "id": 1,
  "result": "success",
  "data": null
}
```

**Event Format (Gateway to MUD)**
```json
{
  "event": "tell_received",
  "data": {
    "from_user": "sender",
    "from_mud": "RemoteMUD",
    "message": "Hello back!"
  }
}
```

#### 3.2 MUD Integration Interface

The gateway provides these methods for MUD servers to call:

**Connection Methods**
- connect() - Establish connection to gateway
- disconnect() - Close gateway connection
- ping() - Check connection status

**Communication Methods**
- tell(target_mud, target_user, message) - Send direct message
- emoteto(target_mud, target_user, emote) - Send emote
- channel_send(channel, message) - Send to channel

**Information Methods**
- who(target_mud) - List users on a mud
- finger(target_mud, target_user) - Get user info
- locate(username) - Find user on network
- mudlist() - Get list of all muds

**Channel Methods**
- channel_list() - List available channels
- channel_join(channel) - Join a channel
- channel_leave(channel) - Leave a channel

#### 3.3 Expected MUD Commands

MUDs implementing gateway integration typically expose these commands to players:

```
i3 tell <user>@<mud> <message>    - Send a tell to a remote user
i3 who <mud>                      - List users on a remote mud
i3 finger <user>@<mud>            - Get info about a remote user
i3 locate <user>                  - Find a user on the network
i3 channel <channel> <message>    - Send message to channel
i3 channel list                   - List available channels
i3 channel join <channel>         - Join a channel
i3 channel leave <channel>        - Leave a channel
```

### Phase 4: Advanced Features (Week 3)

#### 4.1 OOB Services (Optional for MVP)

**Mail Service**
- Store-and-forward mail system
- Attachment support
- Delivery receipts

**News Service**
- Newsgroup synchronization
- Post distribution
- Moderation support

**File Transfer**
- Direct mud-to-mud transfers
- Resume capability
- Integrity checking

#### 4.2 Administration Features

**Monitoring Commands**
```
admin status         - Show gateway connection status
admin stats          - Display statistics
admin reconnect      - Force reconnection
admin blacklist      - Manage blocked muds/users
```

**Channel Administration**
```
admin channel create <name>     - Create new channel
admin channel delete <name>     - Delete channel
admin channel moderate <name>   - Set moderation
```

#### 4.3 Security Implementation

**Input Validation**
- Sanitize all incoming data
- Enforce message length limits
- Validate packet structure

**Rate Limiting**
```python
class RateLimiter:
    def check_rate(self, user: str, action: str) -> bool:
        # Max 10 tells per minute
        # Max 5 who requests per minute
        # Max 20 channel messages per minute
```

**Access Control**
- User-level blocking
- Mud-level blocking
- Channel access lists

### Phase 5: Testing & Quality Assurance (Week 3-4)

#### 5.1 Test Coverage

**Unit Tests**
- Packet encoding/decoding
- Service handlers
- State management
- Protocol compliance

**Integration Tests**
- End-to-end message flow
- Reconnection scenarios
- Error handling
- Load testing

**Test Scenarios**
```python
def test_tell_delivery():
    """Test successful tell delivery"""
    
def test_connection_recovery():
    """Test automatic reconnection"""
    
def test_malformed_packet():
    """Test handling of invalid packets"""
    
def test_rate_limiting():
    """Test rate limit enforcement"""
```

#### 5.2 Performance Targets

- **Latency**: < 100ms for tell delivery
- **Throughput**: 1000+ messages/second
- **Connections**: 100+ concurrent channels
- **Uptime**: 99.9% availability
- **Recovery**: < 30 seconds reconnection

### Phase 6: Deployment & Operations (Week 4)

#### 6.1 Deployment Configuration

**Systemd Service**
```ini
[Unit]
Description=I3 Gateway Service
After=network.target

[Service]
Type=simple
User=i3gateway
ExecStart=/usr/bin/python3 /opt/i3-gateway/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Docker Deployment** (Optional)
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/
CMD ["python", "src/main.py"]
```

#### 6.2 Monitoring & Logging

**Logging Strategy**
```python
logging.config = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'i3-gateway.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5
        }
    },
    'loggers': {
        'i3.network': {'level': 'INFO'},
        'i3.services': {'level': 'DEBUG'},
        'i3.state': {'level': 'WARNING'}
    }
}
```

**Metrics Collection**
- Connection uptime
- Message counts by type
- Error rates
- Response times
- Queue depths

#### 6.3 Documentation

**MUD Integration Documentation**
- API reference guide
- Protocol specification
- Example integration code (multiple languages)
- Troubleshooting guide

**Administrator Documentation**
- Installation guide
- Configuration reference
- Monitoring guide
- Backup procedures

**Developer Documentation**
- Gateway architecture
- Extension guide
- Contributing guidelines
- Testing procedures

## Risk Analysis & Mitigation

### Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Protocol complexity | High | Medium | Incremental implementation, extensive testing |
| Network instability | Medium | High | Retry logic, connection pooling, circuit breakers |
| Performance issues | Medium | Medium | Profiling, caching, async I/O |
| Security vulnerabilities | High | Low | Input validation, sandboxing, rate limiting |

### Project Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Scope creep | Medium | High | Strict MVP definition, phased delivery |
| Integration challenges | High | Medium | Clear API documentation, example code |
| Maintenance burden | Medium | Medium | Clean architecture, comprehensive docs |

## Success Criteria

### Minimum Viable Product (MVP)
- Stable connection to I3 network
- Tell service functional
- Channel service functional  
- Who service functional
- Basic error handling
- Automatic reconnection
- Simple TCP API for MUD integration

### Full Release
- All core services implemented
- OOB services (mail, news)
- Admin commands
- Security features
- Performance optimization
- Complete documentation
- Example integrations for multiple MUD codebases

## Timeline Summary

| Week | Phase | Deliverables | Status |
|------|-------|--------------|--------|
| 1 | Foundation | Project structure, network layer, core components | ✅ COMPLETE |
| 1-2 | Gateway Core | Router connection, packet processing, services | ✅ COMPLETE (60% test coverage) |
| 2 | Gateway API | Protocol specification, API implementation | 🔄 IN PROGRESS |
| 3 | Advanced Features | OOB services, admin tools | ⏳ PENDING |
| 3-4 | Testing & QA | Unit tests, integration tests, performance | ⏳ PENDING |
| 4 | Deployment | Docker, CI/CD, monitoring, documentation | ⏳ PENDING |

### Current Status (2025-01-20)
- **Phase 1**: ✅ Complete - Foundation infrastructure established
- **Phase 2**: ✅ Complete - Core services implemented with comprehensive testing
  - All 6 core services fully implemented (tell, channel, who, finger, locate, router)
  - 60% test coverage achieved with 198 comprehensive unit tests
  - Connection resilience with circuit breakers and retry logic
  - Performance benchmarks and stress testing frameworks
  - Health check endpoints and graceful shutdown
- **Phase 3**: 🔄 In Progress (60% Complete) - Gateway API Protocol
  - ✅ API Server Foundation (WebSocket & TCP servers)
  - ✅ JSON-RPC 2.0 protocol handler
  - ✅ Session management with rate limiting
  - ✅ All request handlers (communication, information, channels, admin)
  - ⏳ Event Distribution System (next priority)
  - ⏳ Client libraries and documentation
- **Next Steps**: Complete event distribution system for real-time bidirectional communication

## Conclusion

This plan provides a structured approach to implementing a standalone Intermud3 gateway service. The gateway architecture ensures complete separation from MUD implementations, allowing any MUD to integrate regardless of their codebase language or architecture.

The gateway acts as a protocol translator, handling all I3 complexity internally and exposing a simple JSON-RPC API that MUDs can easily integrate with. This approach maximizes compatibility and minimizes integration effort for MUD developers.

### Phase 3 Progress Update (2025-01-20)

**Phase 3 Completed Components:**
- ✅ **API Server Foundation**
  - WebSocket server with aiohttp for real-time bidirectional communication
  - TCP socket server for legacy MUD support (line-delimited JSON)
  - Full JSON-RPC 2.0 protocol implementation with batch support
  - Comprehensive session management with rate limiting and metrics
  
- ✅ **Request Handlers** (All 18 API methods implemented)
  - Communication: tell, emoteto, channel_send, channel_emote
  - Information: who, finger, locate, mudlist
  - Channels: join, leave, list, who, history
  - Administrative: status, stats, ping, reconnect, shutdown, reload_config

- ✅ **Configuration & Authentication**
  - API key-based authentication
  - Per-method and per-session rate limiting
  - Session persistence and reconnection support
  - Comprehensive configuration options

**Phase 3 Remaining Work:**
- ⏳ Event Distribution System for push notifications
- ⏳ Authentication middleware completion
- ⏳ Python client library with examples
- ⏳ Comprehensive test suite
- ⏳ API documentation generation

### Phase 2 Completion Summary (2025-01-20)

**Phase 2 Major Achievements:**
- ✅ All 6 core services fully implemented and tested
  - Tell Service: Private messaging with proper 7-field packet structure
  - Channel Service: Public channel communication with join/leave/send
  - Who Service: User listing and information queries
  - Finger Service: Detailed user profile queries
  - Locate Service: Network-wide user search
  - Router Service: Connection management and packet routing
- ✅ Comprehensive test coverage (60% overall, 98-100% for critical services)
- ✅ Reliability features implemented:
  - Circuit breakers for fault tolerance
  - Retry mechanisms with exponential backoff
  - Connection pooling for efficiency
  - Health check endpoints for monitoring
  - Graceful shutdown handling
- ✅ Performance testing infrastructure:
  - Benchmark suite for throughput testing
  - Stress testing framework
  - Load testing capabilities

## Next Steps - Phase 3

### Immediate Priorities
1. **JSON-RPC API Implementation** (Primary Focus)
   - Implement gateway API server accepting JSON-RPC requests
   - Create MUD-to-Gateway protocol handlers
   - Implement Gateway-to-MUD event dispatching
   - Add authentication and session management
   - Create example client libraries

2. **Integration Testing**
   - End-to-end tests with mock MUD clients
   - Protocol compliance verification
   - Performance benchmarks for API layer

3. **Documentation**
   - Complete API reference documentation
   - Create integration guides for popular MUD codebases
   - Add troubleshooting guides

### Future Phases
- **Phase 4**: Advanced Features (OOB services, admin tools)
- **Phase 5**: Production Deployment (Docker, Kubernetes, monitoring)
- **Phase 6**: Extended Services (mail, news, file transfer)