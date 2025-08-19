# Intermud3 Protocol Compliance Fixes

## Summary
Fixed critical protocol compliance issues in Phase 1 implementation to ensure proper communication with I3 routers.

## Issues Fixed

### 1. ✅ TellPacket - Missing visname Field
**Problem**: Tell packets were missing the required `visname` (visual name) field
**Fix**: Added `visname` field at correct position (index 6) in packet structure
- Field order: `[type, ttl, orig_mud, orig_user, target_mud, target_user, visname, message]`
- Visname defaults to originator_user if not specified
- Target username is now properly lowercased for routing

### 2. ✅ StartupPacket - Incorrect Field Order  
**Problem**: Startup packet fields were in wrong order after password field
**Fix**: Corrected field order to match protocol specification
- Old (incorrect): `password, mud_port, tcp_port, udp_port...`
- New (correct): `password, old_mudlist_id, old_chanlist_id, player_port, imud_tcp_port, imud_udp_port...`
- Field names now match protocol documentation

### 3. ✅ Added Missing Packet Types
**Problem**: Several required packet types were missing
**Fix**: Implemented missing packet types:
- `EmotetoPacket` - Similar to tell but for emotes
- `LocatePacket` - For locate-req/locate-reply
- `StartupReplyPacket` - Router response to startup

### 4. ✅ Field Value Handling (0 vs empty string)
**Problem**: Protocol uses integer 0 for null/broadcast, implementation used empty strings
**Fix**: Updated all packets to properly handle 0 values
- Empty strings now convert to 0 in `to_lpc_array()`
- 0 values convert back to empty strings in `from_lpc_array()`
- Broadcast packets use 0 for target_mud/target_user

## Protocol Compliance Details

### Packet Structure Requirements
All I3 packets must follow this base structure:
```python
[type, ttl, originator_mud, originator_user, target_mud, target_user, ...payload]
```

### Special Values
- `0` (integer) = null/broadcast/not applicable
- Empty string = converted to/from 0 for protocol
- Usernames must be lowercased for routing
- Visual names preserve capitalization

### Startup Sequence
Correct startup-req-3 packet structure (20 fields total):
1. "startup-req-3"
2. ttl
3. originator_mud
4. 0 (originator_user)
5. router_name (target_mud)
6. 0 (target_user)
7. password
8. old_mudlist_id
9. old_chanlist_id
10. player_port
11. imud_tcp_port
12. imud_udp_port
13. mudlib
14. base_mudlib
15. driver
16. mud_type
17. open_status
18. admin_email
19. services (mapping)
20. other_data (mapping or 0)

## Testing
Created comprehensive test suite in `tests/unit/test_packet_fixed.py` covering:
- Visname field handling
- Correct field ordering
- 0 vs empty string conversion
- All new packet types
- Protocol compliance validation

## Impact
These fixes ensure the gateway can:
- Successfully connect to I3 routers
- Exchange messages with other MUDs
- Properly handle broadcasts
- Maintain protocol compatibility

## Next Steps
With these protocol fixes, Phase 1 is now fully compliant with the Intermud3 specification and ready for Phase 2 implementation (router connection and service handlers).