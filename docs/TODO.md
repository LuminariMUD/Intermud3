# TODO.md

## Project Status

Phase 3 Complete (2025-08-20) - Core gateway functional with API servers

## Issues Encountered During First Deployment (2025-08-20)

### Bugs Fixed During Deployment

1. **Virtual environment was corrupted**
   - venv/bin/pip couldn't execute
   - Had to recreate venv from scratch

2. **Missing .env file caused immediate crash**
   - Application expects .env but only .env.example exists
   - Error: "Invalid value for '-e' / '--env-file': Path '.env' does not exist"

3. **Import error for version**
   - Line 88 in __main__.py: `__import__("i3_gateway").__version__`
   - Module "i3_gateway" doesn't exist, should be "src"

4. **Settings path error in gateway.py**
   - Line 199 accessed `self.settings.services` 
   - Correct path is `self.settings.mud.services`

5. **API Server never started**
   - APIServer class exists but was never instantiated or started
   - Had to add initialization in gateway.__init__ and start/stop calls

6. **Pydantic model access error**
   - SessionManager tried `key_config["key"]` on APIKeyConfig object
   - Should use `key_config.key` for Pydantic models

7. **Event loop scope error**
   - Variable 'loop' not accessible in finally block
   - UnboundLocalError when exception occurred

### Missing Functionality Discovered

1. **No API methods implemented**
   - Tried to call "get_status", "mudlist" - all return "Unknown method"
   - Only "authenticate" works
   - API server runs but can't actually do anything
   - Methods return {"echo": ...} placeholder responses

2. **TCP server wasn't starting** (FIXED)
   - Config had TCP disabled by default (`enabled: false`)
   - Fixed by enabling in config and properly integrating TCPServer class

3. **No config.yaml file**
   - Only config.yaml.example exists
   - Had to rely on defaults in code

### Additional Issues Fixed After Initial Deployment

8. **TCP server not integrated**
   - TCP server class existed but wasn't being started
   - Fixed by importing TCPServer and calling start/stop methods

9. **API key format mismatch for LuminariMUD**
   - MUD was sending "API_KEY_LUMINARI:luminari-i3-gateway-2025"
   - Gateway expected just "luminari-i3-gateway-2025"
   - Workaround: Updated .env to accept full string

10. **TCP timeout too short**
    - TCP connections timed out after 5 minutes
    - Increased to 1 hour to prevent disconnections

### Observations

- WebSocket server starts and accepts connections ✓
- TCP server now starts and accepts connections ✓
- Authentication with API keys works ✓
- Health and metrics endpoints work ✓
- Gateway connects to I3 router successfully ✓
- LuminariMUD successfully connects and authenticates ✓
- But no actual I3 functionality exposed through API (methods not implemented)