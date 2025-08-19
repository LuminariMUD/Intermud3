# Phase 1: Foundation Infrastructure Implementation Plan

## Executive Summary

Phase 1 establishes the core foundation for the Intermud3 Gateway Service. This phase focuses on building the essential infrastructure components including the network layer, data models, configuration system, and base service framework. By the end of Phase 1, we will have a robust foundation capable of handling MudMode protocol communication, LPC data serialization, and extensible service architecture.

**Duration**: Week 1 (5-7 business days)
**Priority**: Critical - All subsequent phases depend on this foundation
**Risk Level**: Medium - Core protocol implementation requires careful attention to detail

## Phase 1 Objectives

### Primary Goals
1. Implement complete MudMode protocol handling with LPC serialization
2. Establish async network architecture with connection management
3. Create extensible data models for I3 packets and state management
4. Build configuration system with validation and hot-reload capability
5. Set up comprehensive logging and error handling framework
6. Implement base service registry and handler architecture

### Deliverables
- Functional network layer capable of encoding/decoding I3 packets
- Configuration management system with YAML support
- Base service framework ready for Phase 2 service implementations
- Unit test suite covering all foundation components
- Developer documentation for core modules

## Milestone Breakdown

### Day 1-2: Network Layer Implementation

#### Tasks
1. **MudMode Protocol Handler** (`src/network/mudmode.py`)
   - Binary protocol implementation with 4-byte length prefix
   - Packet framing and buffering logic
   - Connection state management

2. **LPC Serialization** (`src/network/lpc.py`)
   - Encode/decode LPC data structures (arrays, mappings, strings, integers)
   - Handle nested structures and special types
   - Implement type validation and error recovery

3. **Connection Manager** (`src/network/connection.py`)
   - Async TCP client with keepalive support
   - Automatic reconnection with exponential backoff
   - Connection pooling for multiple router support

#### Code Structure
```python
# src/network/mudmode.py
class MudModeProtocol:
    """Handles MudMode binary protocol communication"""
    
    def encode_packet(self, packet: I3Packet) -> bytes:
        """Encode I3 packet to MudMode binary format"""
        lpc_data = self.to_lpc_array(packet)
        encoded = self.lpc_encoder.encode(lpc_data)
        length = struct.pack('>I', len(encoded))
        return length + encoded
    
    def decode_packet(self, data: bytes) -> Optional[I3Packet]:
        """Decode MudMode binary data to I3 packet"""
        if len(data) < 4:
            return None
        length = struct.unpack('>I', data[:4])[0]
        if len(data) < 4 + length:
            return None
        lpc_data = self.lpc_encoder.decode(data[4:4+length])
        return self.from_lpc_array(lpc_data)

# src/network/lpc.py
class LPCEncoder:
    """LPC data structure serialization"""
    
    TYPE_STRING = 0x00
    TYPE_INTEGER = 0x01
    TYPE_ARRAY = 0x02
    TYPE_MAPPING = 0x03
    
    def encode(self, obj: Any) -> bytes:
        """Encode Python object to LPC binary format"""
        
    def decode(self, data: bytes) -> Any:
        """Decode LPC binary data to Python object"""
```

### Day 2-3: Data Models and State Management

#### Tasks
1. **Packet Models** (`src/models/packet.py`)
   - I3Packet base class with validation
   - Specific packet types (tell, channel, who, etc.)
   - Packet factory and registry

2. **Connection State** (`src/models/connection.py`)
   - ConnectionState enumeration
   - RouterInfo dataclass
   - MudInfo dataclass with capabilities

3. **State Management** (`src/state/manager.py`)
   - In-memory state store with persistence
   - MUD list caching with TTL
   - Channel membership tracking
   - User session management

#### Code Structure
```python
# src/models/packet.py
@dataclass
class I3Packet:
    """Base I3 packet structure"""
    packet_type: str
    ttl: int
    originator_mud: str
    originator_user: str
    target_mud: str
    target_user: str
    payload: List[Any]
    
    def validate(self) -> bool:
        """Validate packet structure and content"""
        if self.ttl <= 0 or self.ttl > 200:
            raise ValueError(f"Invalid TTL: {self.ttl}")
        if not self.packet_type:
            raise ValueError("Packet type required")
        return True

# src/state/manager.py
class StateManager:
    """Manages gateway state and caching"""
    
    def __init__(self):
        self.mudlist: Dict[str, MudInfo] = {}
        self.channels: Dict[str, ChannelInfo] = {}
        self.sessions: Dict[str, Session] = {}
        self.cache = TTLCache(maxsize=1000, ttl=300)
    
    async def update_mudlist(self, mudlist: Dict) -> None:
        """Update cached MUD list from router"""
    
    async def get_mud_info(self, mud_name: str) -> Optional[MudInfo]:
        """Get MUD information with caching"""
```

### Day 3-4: Configuration and Service Framework

#### Tasks
1. **Configuration System** (`src/config/`)
   - YAML configuration loader with schema validation
   - Environment variable override support
   - Configuration hot-reload capability
   - Secure secret management

2. **Service Registry** (`src/services/base.py`)
   - Abstract base service class
   - Service registration and discovery
   - Message routing to service handlers
   - Service lifecycle management

3. **Logging Framework** (`src/utils/logging.py`)
   - Structured logging with context
   - Log rotation and archival
   - Performance metrics collection
   - Debug mode with packet tracing

#### Code Structure
```python
# src/config/models.py
@dataclass
class GatewayConfig:
    """Gateway configuration model"""
    host: str = "localhost"
    port: int = 4000
    max_connections: int = 100
    
@dataclass
class RouterConfig:
    """Router connection configuration"""
    primary: str = "*i3"
    address: str = "204.209.44.3"
    port: int = 8080
    fallback: Optional[List[str]] = None
    
@dataclass
class Config:
    """Main configuration container"""
    gateway: GatewayConfig
    router: RouterConfig
    mud: MudConfig
    services: ServicesConfig
    
    @classmethod
    def from_yaml(cls, path: str) -> 'Config':
        """Load configuration from YAML file"""

# src/services/base.py
class BaseService(ABC):
    """Abstract base class for I3 services"""
    
    service_name: str
    supported_packets: List[str]
    
    @abstractmethod
    async def handle_packet(self, packet: I3Packet) -> Optional[I3Packet]:
        """Handle incoming packet"""
        pass
    
    @abstractmethod
    async def validate_packet(self, packet: I3Packet) -> bool:
        """Validate packet for this service"""
        pass

class ServiceRegistry:
    """Service registration and routing"""
    
    def register(self, service: BaseService) -> None:
        """Register a service handler"""
    
    def route_packet(self, packet: I3Packet) -> Optional[BaseService]:
        """Route packet to appropriate service"""
```

### Day 4-5: Integration and Testing

#### Tasks
1. **Integration Points**
   - Wire up all components in gateway.py
   - Implement main event loop
   - Add graceful shutdown handling
   - Create health check endpoint

2. **Unit Test Suite**
   - Test LPC encoding/decoding with edge cases
   - Test packet validation and parsing
   - Test connection state transitions
   - Test configuration loading and validation
   - Test service registration and routing

3. **Documentation**
   - API documentation for core modules
   - Configuration reference guide
   - Developer quickstart guide
   - Architecture decision records

#### Test Structure
```python
# tests/unit/test_lpc.py
class TestLPCEncoder:
    def test_encode_string(self):
        """Test string encoding"""
        
    def test_encode_integer(self):
        """Test integer encoding with byte order"""
        
    def test_encode_array(self):
        """Test array encoding with nested structures"""
        
    def test_encode_mapping(self):
        """Test mapping encoding"""
        
    def test_roundtrip(self):
        """Test encode/decode roundtrip"""

# tests/unit/test_packet.py
class TestI3Packet:
    def test_packet_validation(self):
        """Test packet validation rules"""
        
    def test_packet_factory(self):
        """Test packet creation from raw data"""
        
    def test_packet_serialization(self):
        """Test packet to LPC conversion"""
```

## Technical Implementation Details

### Network Architecture
```
+-------------------+
|   Event Loop      |
|   (asyncio)       |
+--------+----------+
         |
+--------v----------+
|  Connection Pool  |
|  - Primary Router |
|  - Fallback List  |
+--------+----------+
         |
+--------v----------+
| Protocol Handler  |
| - Frame Assembly  |
| - LPC Codec       |
+--------+----------+
         |
+--------v----------+
|  Packet Router    |
| - Validation      |
| - Service Lookup  |
+--------+----------+
         |
+--------v----------+
| Service Handlers  |
| - Tell, Channel   |
| - Who, Finger     |
+-------------------+
```

### Data Flow
1. **Inbound**: Raw bytes -> Frame assembly -> LPC decode -> Packet validation -> Service routing -> Handler execution
2. **Outbound**: Service response -> Packet creation -> LPC encode -> Frame wrapping -> Socket write

### Error Handling Strategy
- **Network Errors**: Automatic reconnection with exponential backoff
- **Protocol Errors**: Log and drop malformed packets, maintain connection
- **Service Errors**: Isolate failures, return error responses
- **Configuration Errors**: Fail fast with clear error messages

## Testing Strategy

### Unit Test Coverage Goals
- Network layer: 90% coverage
- LPC serialization: 95% coverage
- Data models: 85% coverage
- Configuration: 80% coverage
- Service framework: 85% coverage

### Test Categories
1. **Protocol Tests**: Verify correct MudMode/LPC implementation
2. **State Tests**: Verify state management and caching
3. **Integration Tests**: Verify component interaction
4. **Performance Tests**: Verify encoding/decoding speed
5. **Resilience Tests**: Verify error recovery

### Test Data
Create fixtures for:
- Sample I3 packets (all types)
- Binary MudMode frames
- Configuration files
- Mock router responses

## Success Criteria

### Functional Requirements
- [ ] Successfully encode/decode all I3 packet types
- [ ] Maintain stable TCP connection with keepalive
- [ ] Handle 1000+ packets/second encoding/decoding
- [ ] Configuration loads and validates correctly
- [ ] Service registry routes packets correctly
- [ ] All unit tests passing with >85% coverage

### Non-Functional Requirements
- [ ] Packet processing latency <10ms
- [ ] Memory usage <100MB for base system
- [ ] Zero memory leaks over 24-hour test
- [ ] Clean shutdown within 5 seconds
- [ ] Automatic reconnection within 30 seconds

### Documentation Requirements
- [ ] All public APIs documented
- [ ] Configuration schema documented
- [ ] Architecture diagrams created
- [ ] Developer guide written

## Risk Assessment

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| LPC encoding complexity | High | Extensive test cases, reference implementation review |
| Async architecture bugs | Medium | Careful event loop management, proper testing |
| Memory leaks | Medium | Regular profiling, proper cleanup handlers |
| Protocol ambiguities | High | Study existing implementations, ask community |

### Schedule Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Underestimated complexity | Medium | Buffer time built into schedule |
| Testing takes longer | Low | Automated test suite from day 1 |
| Documentation lag | Low | Document as we code |

## Dependencies and Prerequisites

### Development Environment
- Python 3.9+ with asyncio support
- Virtual environment setup
- Development dependencies installed

### External Dependencies
```python
# requirements.txt
aiohttp>=3.8.0
pyyaml>=6.0
structlog>=23.0
cachetools>=5.0
```

### Development Dependencies
```python
# requirements-dev.txt
pytest>=7.0
pytest-asyncio>=0.21
pytest-cov>=4.0
black>=23.0
ruff>=0.1.0
mypy>=1.0
```

## Next Steps

### Immediate Actions (Day 0)
1. Set up development environment
2. Install all dependencies
3. Create initial test fixtures
4. Review existing I3 implementations for reference

### Day 1 Start
1. Begin with LPC encoder implementation
2. Set up test-driven development workflow
3. Implement basic packet structures
4. Create initial unit tests

### Daily Checklist
- [ ] Morning: Review progress, adjust plan if needed
- [ ] Coding: Focus on day's milestone tasks
- [ ] Testing: Write tests for new code
- [ ] Documentation: Update docs as needed
- [ ] Evening: Commit code, update progress tracker

## Conclusion

Phase 1 establishes the critical foundation for the Intermud3 Gateway Service. By focusing on robust protocol implementation, clean architecture, and comprehensive testing, we ensure that subsequent phases can build confidently on this foundation. The modular design allows for parallel development in Phase 2 while maintaining system stability.

Success in Phase 1 is measured not just by functional completion but by the quality and maintainability of the codebase. With proper execution, we will have a solid platform ready for service implementation in Phase 2.