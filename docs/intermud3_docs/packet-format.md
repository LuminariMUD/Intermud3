# Packet Format

## Basic Structure

Transmissions are LPC arrays with a predefined set of six initial elements:

```lpc
({
    type,                // Packet type identifier
    ttl,                 // Time To Live
    originator_mudname,  // Originating mud
    originator_username, // Originating user
    target_mudname,      // Target mud (0 for broadcast)
    target_username,     // Target user (0 for mud-level)
    ...                  // Additional packet-specific data
})
```

## Field Descriptions

### type (string)
Describes the type of the packet. See [Packet Types](reference.md#packet-types) for a complete list.

### ttl (int)
The packet's Time To Live (TTL). Similar to an IP packet's TTL, it specifies the number of hops left to a packet. This provides a mechanism to handle cases where routers mis-route a packet into an endless loop - eventually it will time out and be removed from the network.

### originator_mudname (string)
Indicates the mud where the packet originated. If the packet cannot be delivered for some reason, this mud will be notified if possible.

### originator_username (string)
Indicates the user that triggered the delivery of the packet. 
- Use `0` if the mud itself sent the packet (e.g., mail delivery or shutdown notification)
- Should be in lower-case

### target_mudname (string)
Used to route the packet to the appropriate destination mud.
- Use `0` to indicate broadcast packets

### target_username (string)  
Used to route the packet to a particular user on a remote mud.
- May be `0` if the packet is targeted for the mud itself rather than a specific user
- Should always be in lower-case
- The target mud will attempt to find the user with appropriate means

## Special Fields

### visname
Many packets specify a `visname` - a user's "visible" name. This is the name which should be displayed to other users.
- Typically equivalent to the username with altered capitalization
- May be quite arbitrary with respect to the username
- Used for display purposes while username is used for routing

## Example Packets

### Tell Packet
```lpc
({
    "tell",
    5,
    "OriginMud",
    "johndoe",
    "TargetMud", 
    "janedoe",
    "JohnDoe",      // visname
    "Hello there!"  // message
})
```

### Broadcast Locate Request
```lpc
({
    "locate-req",
    5,
    "OriginMud",
    "seeker",
    0,              // broadcast to all muds
    0,              // no specific target user
    "lostuser"      // user being located
})
```

## Important Notes

1. All usernames should be lower-cased for routing purposes
2. Visual names (visname) preserve capitalization for display
3. Broadcast packets use `0` for target_mudname
4. Mud-level packets use `0` for target_username
5. The TTL prevents infinite routing loops
6. Packet format must be strictly followed for proper routing