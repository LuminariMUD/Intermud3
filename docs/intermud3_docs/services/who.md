# Service: who

Get a list of users on a remote mud.

## Network Type
In-band (fast response)

## Request Packet: who-req

```lpc
({
    "who-req",
    5,
    originator_mudname,
    originator_username,
    target_mudname,
    0                    // No specific target user
})
```

## Reply Packet: who-reply

```lpc
({
    "who-reply",
    5,
    originator_mudname,
    0,
    target_mudname,
    target_username,
    who_data
})
```

## who_data Format

An array containing an array for each user on the mud:

```lpc
({
    user_visname,    // (string) User's visual name
    idle_time,       // (int) Idle time in seconds
    xtra_info        // (string) Extra information
})
```

## Example who_data

```lpc
({
    ({ "JohnDoe", 30, "Level 50 Wizard" }),
    ({ "JaneSmith", 120, "AFK" }),
    ({ "BobJones", 0, "Questing in the Dark Forest" })
})
```

## Behavior

1. Originator sends `who-req` packet to target mud via router
2. Router routes the packet to target mud
3. Target mud compiles list of online users
4. Target mud returns `who-reply` with user data
5. Originator receives and displays the user list

## Fields

- **user_visname**: The user's display name
- **idle_time**: Measured in seconds
- **xtra_info**: Additional information as a string (level, location, status, etc.)

## Error Handling

If the router fails to deliver the packet, it will return an error packet with appropriate error codes:
- `unk-dst`: Unknown destination mud

## Notes

- This service provides a snapshot of users at the time of request
- The format of `xtra_info` is mud-specific
- Some muds may limit information shown based on user privacy settings