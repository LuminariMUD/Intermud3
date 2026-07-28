# Python WebSocket client

`i3_client.py` is an async client and integration starting point for the
gateway's WebSocket JSON-RPC API. It is repository source, not a separately
published Python package.

## Use from this repository

Install the gateway package (which supplies aiohttp), then run from the
repository root:

```bash
python -m pip install -e .
export I3_API_KEY='replace-with-a-configured-key'
```

```python
import asyncio
import os

from clients.python.i3_client import I3Client


async def main() -> None:
    client = I3Client(
        url="ws://127.0.0.1:8080/ws",
        api_key=os.environ["I3_API_KEY"],
        mud_name="YourMUD",
    )

    client.on(
        "tell_received",
        lambda event: print(
            f"{event['from_user']}@{event['from_mud']}: {event['message']}"
        ),
    )
    client.on("who_reply", lambda event: print(event))

    await client.connect()
    try:
        print(await client.tell("OtherMUD", "friend", "Hello", "Alyx"))
        await client.send_request("who", {"target_mud": "OtherMUD"})
        await client.wait_closed()
    finally:
        await client.disconnect()


asyncio.run(main())
```

The key must map to the same MUD identity the client represents. The gateway
currently trusts its configured key-to-MUD mapping, not the `X-MUD-Name`
header, as the authenticated identity.

## Useful methods

The client wraps connection/reconnect, event callbacks, tells, channels,
mudlist, remote queries, status, stats, ping, and router reconnect. For methods
whose convenience wrapper is not aligned with the canonical contract, call
`send_request()` directly.

## Known contract differences

This source predates the current API semantics in several places:

- always pass the full `ws://HOST:PORT/ws` URL; older examples and docstrings
  omit `/ws`;
- `emoteto()` and `channel_emote()` send a parameter named `message`, while the
  gateway requires `emote`;
- `who()` and `locate()` try to return data from the immediate response, but
  the gateway returns only request status and later emits `who_reply` or
  `locate_reply`;
- `finger()` likewise returns request status; the data arrives as
  `finger_reply`;
- optional client filters and `mudlist(refresh=True)` do not force remote data
  refreshes in the current gateway;
- the synchronous wrapper is thin event-loop glue and is not suitable inside
  an already-running async application.

Correct calls for the emote and query cases:

```python
await client.send_request(
    "emoteto",
    {
        "target_mud": "OtherMUD",
        "target_user": "friend",
        "from_user": "Alyx",
        "emote": "$N waves.",
    },
)

client.on("locate_reply", lambda event: print(event))
await client.send_request("locate", {"target_user": "friend"})
```

Use the [canonical API reference](../../docs/API_REFERENCE.md) when the helper
and server differ.
