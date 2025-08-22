# TODO.md

## Minor Issues to Fix

- `channel_list` has a missing method (`get_channel_subscriptions` in SubscriptionManager) - easy fix
- `finger` needs parameter name adjustment (expects `target_user` not `username`)
- Mudlist/who data may need time to populate from I3 network

## To Verify Full Integration

From your LuminariMUD, you should:
1. Check if you're receiving tell messages sent to your MUD
2. Join a channel like `imud_gossip` and see if you receive messages
3. Try sending tells/channel messages from your MUD

