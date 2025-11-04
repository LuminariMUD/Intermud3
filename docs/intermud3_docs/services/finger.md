# Service: finger

Get information about a particular user on a remote mud.

## Network Type
In-band (fast response)

## Request Packet: finger-req

```lpc
({
    "finger-req",
    5,
    originator_mudname,
    originator_username,
    target_mudname,
    0,                    // Not targeted to the user
    username              // User to query about
})
```

Note: We use a separate field for the username rather than `target_username` to avoid implying the packet is destined for that user - we're only querying information about them.

## Reply Packet: finger-reply

```lpc
({
    "finger-reply",
    5,
    originator_mudname,
    0,
    target_mudname,
    target_username,
    visname,
    title,
    real_name,
    e_mail,
    loginout_time,
    idle_time,
    ip_name,
    level,
    extra              // e.g., .plan file or other info
})
```

## Field Descriptions

- **visname** (string): User's visual name
- **title** (string): User's title or description
- **real_name** (string): Real name (if provided)
- **e_mail** (string): Email address (if provided)
- **loginout_time** (string): Local time of login (if online) or logout
  - `0` indicates no information available
- **idle_time** (int): Idle time in seconds
  - `-1` indicates user is not currently logged in
- **ip_name** (string): IP address or hostname
- **level** (string): User level/rank
- **extra** (string): Additional information (e.g., .plan file)
  - Should be terminated with a carriage return if provided

## Privacy Considerations

A mud may return `0` for any field to keep information private. It is suggested that information about players (as opposed to wizards) be kept confidential.

## Example Reply

```lpc
({
    "finger-reply",
    5,
    "OriginMud",
    0,
    "TargetMud",
    "seeker",
    "JohnDoe",
    "the Wandering Wizard",
    "John Smith",
    "john@example.com",
    "Mon Jan 15 14:30:00 2024",
    300,
    "example.com",
    "Wizard",
    "Currently working on the new quest system.\n"
})
```

## Error Handling

Error packets may be returned with codes:
- `unk-dst`: Unknown destination mud
- `unk-user`: Unknown target user

## Notes

- Privacy settings may limit available information
- Player information is typically more restricted than wizard information
- The `loginout_time` string format is mud-specific