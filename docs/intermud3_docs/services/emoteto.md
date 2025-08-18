# Service: emoteto

Send an emote to a user on a remote mud.

## Network Type
In-band (fast response)

## Packet Format

```lpc
({
    "emoteto",
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
- **message** (string): The emote message with $N token
- **target_username**: Should be lower-cased by the originating mud

## Token Substitution

The message contains `$N` tokens that represent where the originator's name should be substituted.

### Name Format
```lpc
sprintf("%s@%s", orig_visname, originator_mudname)
```

## Example

Message: `"$N smiles at you."`

Output: `"Joe@PutzMud smiles at you."`

## Behavior

At the target mud:
1. The message is delivered to `target_username` with appropriate formatting
2. `$N` tokens are replaced with the originator's formatted name
3. The final message is displayed to the target user

## Error Handling

If the router or target mud fails to deliver the packet, it will return an error packet with appropriate error codes:
- `unk-dst`: Unknown destination mud
- `unk-user`: Unknown target user

## Notes

- Target username must be in lowercase for proper routing
- The message should not be preformatted before delivery
- Individual muds can define their own display formatting