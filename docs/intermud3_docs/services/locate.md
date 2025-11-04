# Service: locate

Locate a particular user on the Intermud system.

## Network Type
In-band (fast response)

## Request Packet: locate-req

```lpc
({
    "locate-req",
    5,
    originator_mudname,
    originator_username,
    0,                    // Broadcast to all muds
    0,                    // No specific target
    username              // User to locate
})
```

This packet is broadcast to all muds via the router network.

## Reply Packet: locate-reply

```lpc
({
    "locate-reply",
    5,
    originator_mudname,
    0,
    target_mudname,
    target_username,
    located_mudname,
    located_visname,
    idle_time,
    status
})
```

## Field Descriptions

- **located_mudname** (string): The mud where the user was found
- **located_visname** (string): Visual name of the located user
- **idle_time** (int): Idle time in seconds
- **status** (string): Special status of the user
  - `0` indicates no special status

## Predefined Status Values

These values indicate statuses that might affect Intermud transmissions:
- `"link-dead"` - User's connection is dead
- `"editing"` - User is in an editor
- `"inactive"` - User is inactive
- `"invisible"` - User is invisible
- `"hidden"` - User is hidden

### Multiple Statuses
Multiple attributes are specified with comma-space separation:
```
"editing, hidden"
```

### Custom Status
The status string is arbitrary and may contain custom values:
- `"afk for dinner"`
- `"taking a test"`

## Behavior

1. Originator sends `locate-req` broadcast packet
2. Router delivers to all muds
3. Each mud checks if the requested user is logged in
4. Muds with the user online send `locate-reply`
5. Originator receives all replies (may be multiple if user is on multiple muds)

## Example

Request:
```lpc
({ "locate-req", 5, "SeekMud", "finder", 0, 0, "lostwizard" })
```

Reply:
```lpc
({ 
    "locate-reply", 
    5, 
    "FoundMud", 
    0, 
    "SeekMud", 
    "finder",
    "FoundMud",
    "LostWizard",
    120,
    "editing"
})
```

## Notes

- Multiple muds may respond if the user is logged into multiple systems
- The located mud should not apply special formatting to the status string
- Display formatting is left to the receiving mud