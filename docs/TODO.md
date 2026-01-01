# TODO.md

## Completed Fixes (Jan 2026)

### LPC Protocol Fix
- **Problem**: Gateway connected but received no responses from routers
- **Root Cause**: LPC encoder was using binary type-tagged format instead of MudMode text format
- **Fix**: Rewrote `src/network/lpc.py` encoder/decoder to use text-based LPC serialization:
  - Arrays: `({"elem1","elem2",})`
  - Mappings: `(["key":value,])`
  - Added NUL terminator to MudMode packets

### Buffer Handling Fix
- **Problem**: Fragmented TCP data caused `message_count: 0` on most chunks
- **Root Cause**: `feed_data()` in mudmode.py overwrote buffer on partial reads
- **Fix**: Use `seek(0, 2)` before writes, `getvalue()` for buffer access

### Router Configuration
- Made router name configurable via `I3_ROUTER_NAME` env var
- Added `name` field to `RouterHostConfig` in config/models.py
- Set `old_mudlist_id=0` in startup to force fresh list request

## Minor Issues to Fix

- `channel_list` has a missing method (`get_channel_subscriptions` in SubscriptionManager) - easy fix
- `finger` needs parameter name adjustment (expects `target_user` not `username`)
- Mudlist/who data may need time to populate from I3 network
- Minor: Some mudlist delta packets cause "object of type 'int' has no len()" (non-blocking)

## To Verify Full Integration

From your LuminariMUD, you should:
1. Check if you're receiving tell messages sent to your MUD
2. Join a channel like `imud_gossip` and see if you receive messages
3. Try sending tells/channel messages from your MUD

