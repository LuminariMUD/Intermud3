# Tell and emoteto `visname`

The deployed I3 `tell` and `emoteto` packet shape contains eight array
elements:

| Index | Field |
|---:|---|
| 0 | packet type: `tell` or `emoteto` |
| 1 | TTL |
| 2 | originator MUD |
| 3 | originator user |
| 4 | target MUD |
| 5 | target user |
| 6 | originator display name (`visname`) |
| 7 | message/emote text |

`visname` is the player-facing form of the sender name. It is distinct from
the routing identity in `originator_user`, although implementations commonly
use the originator user as the default display name. Target user names are
normally normalized to lowercase for remote lookup.

Examples:

```lpc
({
    "tell", 5,
    "SourceMUD", "alyx",
    "TargetMUD", "friend",
    "Alyx", "Hello"
})
```

```lpc
({
    "emoteto", 5,
    "SourceMUD", "alyx",
    "TargetMUD", "friend",
    "Alyx", "$N waves."
})
```

The gateway's `TellPacket` and `EmotetoPacket` models emit and parse this
eight-field layout. The local JSON-RPC layer uses `message` for `tell` but
`emote` for `emoteto`; that local parameter distinction does not alter the
router packet's final text field.

For the broader packet envelope, see [Packet format](packet-format.md).
