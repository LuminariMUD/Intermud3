# Intermud3 Gateway Architecture

## System Overview

The Intermud3 Gateway is a standalone service that bridges MUD servers with the global Intermud-3 network. It handles all I3 protocol complexity internally while exposing a simple JSON-RPC API for MUD integration.

**Current Status**: Phase 3 Complete (2025-08-19) - Full JSON-RPC API with WebSocket/TCP support, client libraries, and comprehensive documentation. Ready for production deployment.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Global I3 Network                        │
│                  (Routers, MUDs, Services)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    MudMode Protocol
                    (LPC over TCP)
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    I3 Gateway Service                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  Network Layer                          │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │   MudMode    │  │     LPC      │  │  Connection  │ │ │
│  │  │   Protocol   │  │  Encoder/    │  │   Manager    │ │ │
│  │  │              │  │   Decoder    │  │              │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   Service Layer                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │    Tell      │  │   Channel    │  │     Who      │ │ │
│  │  │   Service    │  │   Service    │  │   Service    │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │   Finger     │  │   Locate     │  │   Emoteto    │ │ │
│  │  │   Service    │  │   Service    │  │   Service    │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    Core Systems                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │    State     │  │   Service    │  │   Packet     │ │ │
│  │  │   Manager    │  │   Registry   │  │   Router     │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │   Config     │  │   Metrics    │  │    Cache     │ │ │
│  │  │   Manager    │  │  Collector   │  │   Manager    │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                     API Layer                          │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │ │
│  │  │  JSON-RPC    │  │  WebSocket   │  │    Event     │ │ │
│  │  │   Server     │  │   Server     │  │  Dispatcher  │ │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    JSON-RPC over TCP
                    (Simple Text Protocol)
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                      MUD Servers                             │
│                   (Any Language/Platform)                    │
└──────────────────────────────────────────────────────────────┘
```

## Component Details

### Network Layer

#### MudMode Protocol Handler
- Implements the binary MudMode protocol used by I3 routers
- Handles 4-byte length prefix framing
- Manages TCP socket communication
- Implements keepalive mechanism

#### LPC Encoder/Decoder
- Serializes/deserializes LPC data structures
- Supports all LPC types: null, string, integer, float, array, mapping, buffer
- Handles proper byte ordering (network/big-endian)
- UTF-8 string encoding support

#### Connection Manager
- Maintains persistent connection to I3 router
- Automatic reconnection with exponential backoff
- Router failover support
- Connection state tracking

### Service Layer

Each service implements a specific I3 protocol feature:

#### Tell Service
- Handles private messages between users
- Message routing and delivery
- Offline message queuing (optional)

#### Channel Service
- Public channel communication
- Channel membership management
- Message types: normal (m), emote (e), targeted (t)

#### Who Service
- User listing requests
- Formatted user information
- Idle time tracking

#### Finger Service
- Detailed user information queries
- Profile data management
- Last seen tracking

#### Locate Service
- Network-wide user search
- Multi-MUD query coordination
- Result aggregation

#### Emoteto Service
- Targeted emotes across MUDs
- Emote formatting
- Delivery confirmation

### Core Systems

#### State Manager
- In-memory state storage
- Optional persistence to disk
- Session management
- MUD list tracking
- Channel membership

#### Service Registry
- Dynamic service registration
- Packet type to service routing
- Service lifecycle management
- Dependency injection

#### Packet Router
- Incoming packet dispatch
- Outgoing packet queuing
- TTL management
- Error handling

#### Configuration Manager
- YAML configuration loading
- Environment variable support
- Dynamic reconfiguration
- Validation

#### Metrics Collector
- Performance metrics
- Message statistics
- Error tracking
- Health monitoring

#### Cache Manager
- TTL-based caching
- LRU eviction
- Memory management
- Cache statistics

### API Layer

#### JSON-RPC Server
- Request/response handling
- Method dispatch
- Parameter validation
- Error responses

#### WebSocket Server
- Persistent connections
- Real-time events
- Binary frame support
- Connection management

#### Event Dispatcher
- Event routing to connected clients
- Event filtering
- Broadcast support
- Queue management

## Data Flow

### Incoming Message Flow

```
1. I3 Router → TCP Socket
2. MudMode Protocol → Raw Bytes
3. LPC Decoder → Packet Object
4. Packet Router → Service Handler
5. Service Handler → Process Message
6. State Manager → Update State
7. Event Dispatcher → Connected MUDs
8. JSON-RPC → MUD Server
```

### Outgoing Message Flow

```
1. MUD Server → JSON-RPC Request
2. API Server → Validate Request
3. Service Handler → Create Packet
4. Packet Router → Queue Message
5. LPC Encoder → Binary Data
6. MudMode Protocol → Frame Data
7. TCP Socket → I3 Router
```

## Design Patterns

### Asynchronous I/O
- All network operations use asyncio
- Non-blocking socket operations
- Concurrent request handling
- Event-driven architecture

### Message Queue Pattern
- Separate inbound/outbound queues
- Priority-based processing
- Retry mechanism
- Dead letter queue

### Service Registry Pattern
- Loose coupling between services
- Dynamic service discovery
- Dependency injection
- Plugin architecture

### Observer Pattern
- Event-based communication
- Decoupled components
- Multiple event listeners
- Event filtering

### Factory Pattern
- Packet creation from type
- Service instantiation
- Connection creation
- Handler selection

## Scalability Considerations

### Horizontal Scaling
- Stateless service design
- External state storage
- Load balancer support
- Multiple gateway instances

### Performance Optimization
- Connection pooling
- Message batching
- Caching layer
- Compression support

### Resource Management
- Memory pooling
- Connection limits
- Rate limiting
- Circuit breakers

## Security Architecture

### Authentication
- Shared secret for MUD authentication
- Router authentication protocol
- Session management
- Token-based auth (future)

### Authorization
- Per-service access control
- User-level permissions
- Channel access lists
- Admin privileges

### Input Validation
- Packet structure validation
- Parameter sanitization
- Length limits
- Type checking

### Network Security
- TLS support (optional)
- IP whitelisting
- Rate limiting
- DDoS protection

## Fault Tolerance

### Connection Recovery
- Automatic reconnection
- Exponential backoff
- Router failover
- State recovery

### Error Handling
- Graceful degradation
- Error isolation
- Recovery procedures
- Audit logging

### Data Persistence
- State snapshots
- Transaction logs
- Backup/restore
- Data validation

## Monitoring and Observability

### Metrics
- Message throughput
- Latency percentiles
- Error rates
- Resource usage

### Logging
- Structured logging
- Log levels
- Log rotation
- Centralized logging

### Health Checks
- Liveness probe
- Readiness probe
- Dependency checks
- Performance metrics

### Tracing
- Request tracing
- Distributed tracing
- Performance profiling
- Debug mode

## Deployment Architecture

### Container Deployment
- Docker containerization
- Kubernetes support
- Health checks
- Resource limits

### Configuration Management
- Environment variables
- ConfigMaps
- Secrets management
- Feature flags

### Service Discovery
- DNS-based discovery
- Service mesh integration
- Load balancing
- Circuit breakers

## Development Workflow

### Module Structure
```
src/
├── network/       # Network protocol implementation
├── services/      # I3 service handlers
├── models/        # Data structures
├── state/         # State management
├── config/        # Configuration
├── api/           # API server
└── utils/         # Utilities
```

### Testing Strategy
- Unit tests for components
- Integration tests for services
- End-to-end tests for flows
- Performance tests
- Mock I3 router for testing

### Code Organization
- Clear separation of concerns
- Single responsibility principle
- Dependency injection
- Interface-based design

## Future Enhancements

### Planned Features
- WebRTC support for direct MUD-to-MUD communication
- GraphQL API alternative
- Admin web dashboard
- Kubernetes operator
- Multi-region support

### Performance Improvements
- Protocol buffer serialization
- Connection multiplexing
- Smart routing
- Predictive caching

### Extended Services
- OOB mail service
- News distribution
- File transfer
- Remote procedure calls
- Inter-MUD commerce