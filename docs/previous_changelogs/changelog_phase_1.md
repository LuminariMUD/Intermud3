# CHANGELOG.md

All notable changes to the Intermud3 Gateway Service will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2024-01-19

### Fixed - Critical Protocol Compliance Issues

#### Packet Protocol Fixes
- **TellPacket**: Added missing `visname` field (visual name) at correct position
  - Field order now matches protocol: `[type, ttl, orig_mud, orig_user, target_mud, target_user, visname, message]`
  - Visname defaults to originator_user if not specified
  - Target username properly lowercased for routing

- **StartupPacket**: Corrected field order to match I3 protocol specification
  - Fixed field sequence after password: `old_mudlist_id, old_chanlist_id, player_port, imud_tcp_port, imud_udp_port`
  - Renamed fields to match protocol documentation (player_port instead of mud_port)
  - Total field count corrected to 20

- **Field Value Handling**: Fixed 0 vs empty string handling per protocol
  - Empty strings now properly convert to integer 0 for network transmission
  - 0 values correctly convert back to empty strings when receiving
  - Broadcast packets properly use 0 for target_mud/target_user

#### New Packet Types
- **EmotetoPacket**: Added support for emote messages (similar structure to tell)
- **LocatePacket**: Implemented locate-req/locate-reply for player search
- **StartupReplyPacket**: Added router response packet for startup sequence

#### Testing
- Created comprehensive test suite for all protocol fixes
- Added tests for visname field handling
- Verified correct field ordering in all packets
- Tested 0 vs empty string conversion
- Validated all new packet types

### Changed
- Updated PacketFactory to handle new packet types
- Modified packet validation to enforce protocol requirements
- Enhanced from_lpc_array methods to handle 0 values correctly

## [0.1.0] - 2024-01-19

### Added - Phase 1: Foundation Infrastructure 

#### Network Layer
- Implemented complete LPC encoder/decoder for all data types (null, string, integer, float, array, mapping, buffer)
- Created MudMode binary protocol handler with 4-byte length prefix framing
- Built connection manager with automatic reconnection and exponential backoff
- Added router failover support with priority-based selection
- Implemented connection pooling architecture for multiple router support

#### Data Models
- Created comprehensive I3 packet models:
  - TellPacket for private messages
  - ChannelPacket for channel messages (m/e/t variants)
  - WhoPacket for player queries
  - FingerPacket for player information
  - StartupPacket for router authentication
  - MudlistPacket for MUD directory updates
  - ErrorPacket for protocol errors
- Implemented packet factory with automatic type detection
- Added packet validation with detailed error messages
- Created connection state models (MudInfo, ChannelInfo, UserSession)

#### State Management
- Built state manager with in-memory storage and optional persistence
- Implemented TTL caching system for performance optimization
- Added automatic cleanup tasks for expired sessions and cache entries
- Created MUD list synchronization with incremental updates
- Implemented channel membership tracking

#### Service Framework
- Designed extensible BaseService abstract class
- Created ServiceRegistry for packet routing
- Implemented ServiceManager with queue-based processing
- Added metrics collection for performance monitoring
- Built service lifecycle management (initialize/shutdown)

#### Gateway Integration
- Integrated all components in main I3Gateway class
- Implemented packet processing pipeline with async queue
- Added connection state machine handling
- Created statistics API for monitoring
- Built graceful shutdown mechanism

#### Testing
- Comprehensive test suite for LPC encoder/decoder
  - String encoding with Unicode support
  - Integer/float encoding with proper byte order
  - Nested array and mapping structures
  - Buffer/bytes handling
  - Roundtrip conversion tests
  - Edge cases and error conditions
- Complete packet model tests
  - Packet validation rules
  - LPC array conversion
  - Factory pattern tests
  - All packet types covered

### Technical Achievements
- **Async/Await Architecture**: Full asyncio implementation for non-blocking I/O
- **Type Safety**: Complete type hints throughout codebase
- **Error Resilience**: Automatic recovery from network failures
- **Performance**: Efficient packet processing with caching
- **Modularity**: Clean separation of concerns with dependency injection
- **Extensibility**: Plugin-based service architecture

### Changed
- Updated gateway.py to use new component architecture
- Refactored configuration to use Settings model

### Dependencies
- Python 3.9+ required for asyncio features
- structlog for structured logging
- pyyaml for configuration
- pytest for testing framework

## [0.0.1] - 2024-01-18

### Added
- Initial project structure
- Basic configuration system
- Project documentation (README, HIGH_LEVEL_PLAN)
- Development environment setup

---

## Upcoming Releases

### [0.2.0] - Phase 2: Gateway Core Services
- Tell service implementation
- Channel service with variants (m/e/t)
- Who service for player listings
- Finger service for player information
- Locate service for player search
- Router integration completion
- Service integration tests

### [0.3.0] - Phase 3: Gateway API Protocol
- JSON-RPC server implementation
- WebSocket support
- Client SDK
- API documentation

### [0.4.0] - Phase 4: Advanced Features
- OOB services (mail, news, file)
- Admin dashboard
- Performance optimizations
- Security enhancements