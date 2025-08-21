# CHANGELOG.md

All notable changes to the Intermud3 Gateway Service will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.7] - 2025-08-21

### Fixed
- **CRITICAL**: Fixed API handler methods using abstract `I3Packet` class instead of concrete packet classes
  - All 11 handler methods now correctly instantiate proper packet types (TellPacket, EmotetoPacket, etc.)
  - Added imports for all concrete packet classes in `api_handlers.py`
  - Fixed packet field names to match concrete class attributes
  - Phase 3 is now fully complete with working I3 functionality through the API
- Fixed test suite to use `server.handlers.handle_*` instead of deprecated `server._handle_*` methods
- Fixed datetime mocking in status handler test for proper uptime calculation

### Changed
- API handlers now properly construct packets with correct type-specific fields
- Test architecture updated to match new APIHandlers class structure

## [0.3.6] - 2025-08-20

### Added
- Complete API method implementations via new `APIHandlers` class
  - Communication methods: `tell`, `emoteto`
  - Channel methods: `channel_send`, `channel_emote`, `channel_join`, `channel_leave`, `channel_list`, `channel_who`, `channel_history`
  - Information methods: `who`, `finger`, `locate`, `mudlist`
  - Administrative methods: `ping`, `status`, `stats`, `reconnect`
- State manager query methods for caching and data retrieval
  - `get_mudlist()`, `get_channel_history()`, `get_who_data()`
  - `get_finger_data()`, `get_locate_data()`, `get_stats()`
- Gateway helper methods: `is_connected()` and `reconnect()`

### Fixed
- Event loop scope error in `__main__.py` - initialized variables before try block
- TCP server syntax error - removed extra closing parenthesis
- Import conflict - renamed `handlers.py` to `api_handlers.py` to avoid directory conflict
- TCP server handler integration - now properly routes through APIHandlers
- State manager instantiation in API handlers

### Changed
- API methods now return proper responses instead of echo placeholders
- TCP and WebSocket servers share the same APIHandlers instance
- Improved error handling and response formatting in API methods

## [0.3.5] - 2025-08-20

### Fixed
- Fixed module import error in `__main__.py` - changed from `i3_gateway.__version__` to `src.__version__`
- Fixed settings attribute access in `gateway.py` - services are under `mud.services` not `settings.services`
- Fixed API server integration - added APIServer initialization and lifecycle management in gateway
- Fixed SessionManager Pydantic model access - changed from dictionary syntax to attribute access
- Fixed UnboundLocalError for event loop variable - moved loop initialization before try block
- Fixed OOB services configuration - properly separated regular services from OOB services
- Fixed TCP server not starting - enabled in config and integrated TCPServer class
- Fixed TCP server stub - replaced placeholder with actual TCPServer integration

### Changed
- Updated deployment documentation to reflect .env file requirement
- Simplified startup process - now just requires `python -m src` after configuration
- API server now starts automatically with the gateway when enabled

### Added
- API server integration into main gateway lifecycle
- Health check endpoint at `/health` returning JSON status
- Metrics endpoint at `/metrics` with Prometheus-compatible format
- TCP server now starts automatically alongside WebSocket (port 8081)
- TCP treated as equal option to WebSocket for MUD connections
- LuminariMUD API key configuration with full access permissions
- TCP connection timeout increased from 5 minutes to 1 hour
- Debug logging for TCP data reception

