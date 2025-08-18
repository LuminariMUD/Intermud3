# Service: ucache

Cache information about remote users to maintain up-to-date user data across the Intermud network.

## Purpose
The ucache service maintains user information caches within the Intermud network. Muds cache information received from `chan-user-req` packets and keep it updated through ucache-update broadcasts.

## Network Type
In-band (fast response)

## Update Packet: ucache-update

Broadcast whenever user information changes:

```lpc
({
    "ucache-update",
    5,
    originator_mudname,
    0,
    0,                     // Broadcast to all muds
    0,
    username,
    visname,
    gender                 // 0 = male, 1 = female, 2 = neuter
})
```

## When to Send Updates

Send a ucache-update packet whenever the contents of a `chan-user-reply` packet would change:
- User's visual name changes
- User's gender changes
- Any other cached user data modifications

## Packet Contents

The packet contains the same information as `chan-user-reply`:
- **username** (string): The user's login name (lowercase)
- **visname** (string): The user's visual/display name
- **gender** (int): Gender for pronoun selection
  - `0`: Male
  - `1`: Female
  - `2`: Neuter

## Router Filtering

The router filters delivery of ucache-update packets to only those muds that support the ucache service. This reduces unnecessary network traffic.

## Implementation Guidelines

### For Sending Muds
1. Monitor changes to user information
2. Send ucache-update when changes occur
3. Broadcast updates even if unsure who has cached the data

### For Receiving Muds
1. Maintain a cache of remote user information
2. Update cache when ucache-update packets arrive
3. Use cached data to avoid repeated chan-user-req queries

## Example

User "johndoe" changes their title, which affects their visual name:

```lpc
({
    "ucache-update",
    5,
    "OriginMud",
    0,
    0,
    0,
    "johndoe",
    "JohnDoe the Mighty",
    0                      // Male
})
```

## Benefits

- Reduces network traffic by avoiding repeated user info queries
- Provides more responsive channel operations
- Maintains consistency across the Intermud network
- Allows efficient targeted emotes on channels

## Notes

- Only muds that declare ucache service support receive updates
- Updates are broadcast to ensure all caching muds stay synchronized
- Gender values are used for proper pronoun selection in messages