# Router Design

## Overview

Routers form the backbone of the Intermud-3 network, maintaining connectivity between all muds and handling packet routing.

## Router Connectivity

### Inter-Router Network
- Routers create, open, and maintain MUD mode TCP sessions with each other router
- Forms a fully connected network (every router connects to every other router)
- Each router maintains status of all inter-router links
- Link information used for routing around failed links until reestablishment

### Router State Management
Each router maintains:
- Complete list of all muds on the Intermud
- Information associated with each mud
- Up/down/rebooting state for each mud
- Which router each mud is connected to
- Complete channel list and membership information

## List Synchronization

Routers synchronize two primary lists: mudlist and channel list.

### Token-Based Synchronization
- Each list state has a unique token
- Routers can provide deltas between tokens or complete lists
- Tokens guarantee uniqueness using current time

### Token Generation
```
new_token = max(old_token + 1, time())
```

This ensures:
- Tokens are unique even if generated within the same second
- Tokens always increase monotonically
- Time-based ordering is maintained

### Conflict Resolution

When two routers generate deltas simultaneously:

1. **Token Ordering**: If tokens t1 and t2 exist where t1 < t2
   - Final token = max(t1, t2)
   
2. **Receipt Order Issues**:
   - If router receives t1 before t2: Normal operation
   - If router receives t2 before t1: Conflict resolution needed

3. **Alter-Token Protocol**:
   - Conflicting delta gets new token = t2 + 1
   - Recirculated through router network
   - Duplicates ignored based on altered-token origin

## Synchronization Packets

### List Delta
```lpc
({
    "XXXlist-delta",      // XXX = mud or chan
    5,
    originator_mudname,   // Router
    0,
    "*",                  // Router broadcast
    0,
    token,
    list_delta_info
})
```

### List Altered
```lpc
({
    "XXXlist-altered",    // XXX = mud or chan
    5,
    originator_mudname,   // Router
    0,
    "*",                  // Router broadcast
    0,
    altered_token,
    list_delta_info
})
```

## Packet Routing

### Routing Rules
Routing based entirely on originator/target fields:
- No knowledge of packet types required
- Provides flexibility for extensions
- Likely increases routing speed

### Routing Algorithm
Based on `target_mudname`:
1. If target is connected to this router: Deliver directly
2. If target is connected to another router: Forward to that router
3. If target is the router itself: Pass to router processes
4. If target is broadcast (0): Deliver to all connected muds

### Failed Link Handling
When inter-router link fails:
- Router detects failed link
- Updates routing tables to route around failure
- Attempts to reestablish connection
- Updates other routers about link status

## Channel Management

Routers maintain three channel lists:
1. Unfiltered selective admission channels
2. Unfiltered selective banning channels
3. Filtered selective admission channels

For each channel, routers store:
- Channel type (admission/banning/filtered)
- Owning mud
- List of admitted/banned muds
- Current listeners by mud

### Channel Message Routing
1. Mud sends channel message to router
2. Router determines recipient muds based on:
   - Channel membership lists
   - Current listener status
3. For filtered channels:
   - Route to host mud for filtering
   - Receive filtered message back
   - Distribute to recipients
4. Forward messages to appropriate muds

## Performance Considerations

### Efficiency Features
- Routing based solely on target fields (fast lookup)
- Delta updates minimize data transfer
- Caching of routing information
- Direct inter-router links avoid hop delays

### Load Balancing
- Muds can be reassigned to different routers
- Preferred router can be changed programmatically
- Distributes connection load across router network

## Reliability Features

### Failover Support
- Multiple routers provide redundancy
- Muds store complete router list
- Automatic failover to backup routers
- Graceful handling of router failures

### State Persistence
- Muds maintain mudlist_id across connections
- Muds maintain chanlist_id across connections
- Routers can provide appropriate deltas on reconnection

## Security

### Authentication
- Password-based mud authentication
- New muds receive random passwords from routers
- Passwords validate mud identity across connections
- Prevents mud impersonation

### Validation
- Packet format validation
- Source mud verification
- Channel permission enforcement
- Service availability checking

## Implementation Notes

- Routers must support all protocol versions
- Translation between protocol versions as needed
- Error packets for unsupported operations
- Maintains backward compatibility