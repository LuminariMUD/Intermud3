# Service: tell

Send a message to a user on a remote mud.

## Network Type
In-band (fast response)

## Packet Format

```lpc
({
    "tell",
    5,
    originator_mudname,
    originator_username,
    target_mudname,
    target_username,
    orig_visname,
    message
})
```

## Fields

- **orig_visname** (string): Visual name of the originator
- **message** (string): The message to deliver
- **target_username**: Should be lower-cased by the originating mud

## Behavior

At the target mud, the message is delivered to `target_username`. The `orig_visname` indicates who sent the message and is usually combined with the `originator_mudname`.

### Suggested Display Format
```
sprintf("%s@%s tells you: %s", orig_visname, originator_mudname, message)
```

Example output:
```
John@Doe Mud tells you: Hello there!
```

## Error Handling

If the router fails to deliver the packet for some reason, it will return an error packet with appropriate error codes:
- `unk-dst`: Unknown destination mud
- `unk-user`: Unknown target user

## Notes

- The message should not be preformatted before delivery
- Individual muds can define their own display semantics
- Target username must be in lowercase for proper routing