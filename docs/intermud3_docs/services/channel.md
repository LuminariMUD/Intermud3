# Service: channel

Send strings, emotes, and targeted emotes between muds via channels.

## Channel Types

1. **Selective Admission**: Only admitted muds can use the channel
2. **Selective Banning**: All muds except banned ones can use the channel
3. **Filtered**: Channel messages are filtered by the host mud (admission only)

## Channel Administration

- All channels are owned by a particular mud
- Only the owning mud can administer the channel
- Filtered channels process messages through the host before distribution
- Channels become unavailable when the host mud is down

## Channel Lists

Routers maintain three channel lists:
1. Unfiltered selective admission channels
2. Unfiltered selective banning channels  
3. Filtered selective admission channels

Note: Filtered selective banning channels are not allowed.

## Packet Types

### Channel List Reply: chanlist-reply

```lpc
({
    "chanlist-reply",
    5,
    originator_mudname,     // Router
    0,
    target_mudname,
    0,
    chanlist_id,
    channel_list
})
```

`channel_list` is a mapping with channel names as keys and arrays as values:
- Value of `0`: Channel has been deleted
- Array format: `({ host_mud, channel_type })`

Channel types:
- `0`: Selectively banned
- `1`: Selectively admitted
- `2`: Filtered (selectively admitted)

### Standard Message: channel-m

```lpc
({
    "channel-m",
    5,
    originator_mudname,
    originator_username,
    0,
    0,
    channel_name,
    visname,
    message
})
```

Suggested display format:
```
[gwiz] John@Doe Mud: help me! I am a newbie!
```

### Emote: channel-e

```lpc
({
    "channel-e",
    5,
    originator_mudname,
    originator_username,
    0,
    0,
    channel_name,
    visname,
    message              // Contains $N token
})
```

The `$N` token represents the originator's name.

### Targeted Emote: channel-t

```lpc
({
    "channel-t",
    5,
    originator_mudname,
    originator_username,
    0,
    0,
    channel_name,
    targetted_mudname,
    targetted_username,
    message_others,
    message_target,
    originator_visname,
    target_visname
})
```

Tokens:
- `$N`: Originator's name
- `$O`: Target's name

## Channel Management

### Add Channel: channel-add

```lpc
({
    "channel-add",
    5,
    originator_mudname,
    originator_username,
    target_mudname,         // Router
    0,
    channel_name,
    channel_type
})
```

### Remove Channel: channel-remove

```lpc
({
    "channel-remove",
    5,
    originator_mudname,
    originator_username,
    target_mudname,         // Router
    0,
    channel_name
})
```

### Administer Channel: channel-admin

```lpc
({
    "channel-admin",
    5,
    originator_mudname,
    originator_username,
    target_mudname,         // Router
    0,
    channel_name,
    add_to_list,           // Array of muds to add
    remove_from_list       // Array of muds to remove
})
```

### Listen to Channel: channel-listen

```lpc
({
    "channel-listen",
    5,
    originator_mudname,
    0,
    target_mudname,         // Router
    0,
    channel_name,
    on_or_off              // 0 = off, 1 = on
})
```

## Channel Queries

### Who's Listening: chan-who-req / chan-who-reply

Request:
```lpc
({
    "chan-who-req",
    5,
    originator_mudname,
    originator_username,
    target_mudname,
    0,
    channel_name
})
```

Reply:
```lpc
({
    "chan-who-reply",
    5,
    originator_mudname,
    0,
    target_mudname,
    target_username,
    channel_name,
    user_list              // Array of visual names
})
```

### User Info: chan-user-req / chan-user-reply

Request:
```lpc
({
    "chan-user-req",
    5,
    originator_mudname,
    0,
    target_mudname,
    0,
    username
})
```

Reply:
```lpc
({
    "chan-user-reply",
    5,
    originator_mudname,
    0,
    target_mudname,
    0,
    username,
    visname,
    gender                 // 0 = male, 1 = female, 2 = neuter
})
```

## Filtering

### Filter Request: chan-filter-req

```lpc
({
    "chan-filter-req",
    5,
    originator_mudname,     // Router
    0,
    target_mudname,         // Channel host
    0,
    channel_name,
    packet_to_filter
})
```

### Filter Reply: chan-filter-reply

```lpc
({
    "chan-filter-reply",
    5,
    originator_mudname,     // Channel host
    0,
    target_mudname,         // Router
    0,
    channel_name,
    filtered_packet
})
```

## Notes

- Messages should not be terminated with newlines
- Target usernames should be lower-cased
- Muds should tune out channels when no users are listening
- Display formatting is mud-specific