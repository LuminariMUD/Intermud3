# MUD integration guide

This guide connects a MUD process to Intermud3 Gateway's local JSON-RPC API.
The gateway owns the upstream router session; the MUD owns player identity,
permissions, display, and game-loop safety.

## Integration contract

Your MUD must:

1. maintain one authenticated WebSocket or TCP connection;
2. publish a current player-presence snapshot if it wants the gateway to answer
   inbound who/finger/locate requests;
3. turn local commands into JSON-RPC calls;
4. consume asynchronous events without blocking the game loop;
5. sanitize remote text for the MUD's display system;
6. reconnect and restore channel subscriptions after a local API disconnect.

The gateway handles:

- I3 router registration and credentials;
- MudMode framing and LPC serialization;
- typed I3 packets and service routing;
- mudlist/chanlist state;
- conversion between I3 packets and local JSON events.

## Choose a transport

| Transport | Use it when | Framing |
|---|---|---|
| WebSocket | Python, JavaScript, browser, or an engine with a WebSocket library | one JSON-RPC object per text frame |
| TCP | C/C++, CircleMUD/tbaMUD, or a simple socket-based game loop | one UTF-8 JSON object followed by `\n` |

Default endpoints:

```text
ws://127.0.0.1:8080/ws
127.0.0.1:8081
```

The `/ws` path is required. TCP port 8081 is not HTTP.

## Provision identity

Each API key maps to a MUD identity:

```yaml
api:
  auth:
    enabled: true
    api_keys:
      - key: ${API_KEY_LUMINARI:replace-me}
        mud_name: ${MUD_NAME:YourMUD}
        permissions: ["*"]
        rate_limit_override: 500
```

Store the real key outside source control. The `mud_name` attached to that key
becomes the origin MUD for outbound I3 packets. A caller cannot override it in
request parameters.

Bind the API to loopback when the MUD and gateway share a host. If the
connection crosses hosts, use a private network or TLS-terminated `wss://`.

## Connection lifecycle

### WebSocket

Send the key in the upgrade request:

```http
GET /ws HTTP/1.1
Host: gateway.example
Upgrade: websocket
Connection: Upgrade
X-API-Key: YOUR_KEY
```

or authenticate in the first frame:

```json
{"jsonrpc":"2.0","id":1,"method":"authenticate","params":{"api_key":"YOUR_KEY"}}
```

### TCP

Read the server's `welcome` line, then write:

```json
{"jsonrpc":"2.0","id":1,"method":"authenticate","params":{"api_key":"YOUR_KEY"}}
```

followed by a newline.

### Local readiness

Before enabling player commands:

1. authenticate the local connection;
2. call `status`;
3. require `result.connected == true`, or independently require HTTP 200 from
   `/health/ready`;
4. join configured channels;
5. publish presence.

Keep local API connectivity distinct from router readiness. A MUD can be
connected to port 8081 while the gateway is reconnecting upstream.
`/health/ready` and `status.connected` report router transport connectivity,
not completion of startup/list synchronization. After a cold start, wait for
the startup reply or populated synchronized state before assuming every remote
operation is available.

## JSON-RPC request discipline

- Use a unique string or integer `id` for every request.
- Keep a pending-request map keyed by `id`.
- Apply a local timeout; a lost local response must not stall the game loop.
- Treat server messages without `id` as events.
- Send one request per WebSocket frame or TCP line.
- Do not send JSON-RPC batch arrays.

Successful local response:

```json
{"jsonrpc":"2.0","id":12,"result":{"pong":true,"timestamp":"..."}}
```

Server event:

```json
{"jsonrpc":"2.0","method":"tell_received","params":{...}}
```

## Publish local player presence

Presence allows the gateway to build I3 who/finger/locate replies from your
game's authoritative state.

Send a complete snapshot, not a delta:

```json
{
  "jsonrpc": "2.0",
  "id": 20,
  "method": "presence_sync",
  "params": {
    "users": [
      {
        "name": "Alyx",
        "title": "the Cartographer",
        "level": 42,
        "idle": 3,
        "race": "Human",
        "guild": "Explorers",
        "location": "Market Square",
        "status": "online",
        "login_time": 1785250000
      }
    ]
  }
}
```

Rules:

- at most 512 players;
- names are case-insensitively unique;
- `name` is required;
- send an empty `users` array when nobody is online;
- refresh more often than the 30-second presence TTL;
- expose only fields appropriate for public cross-MUD queries.

IP addresses are not returned in gateway finger replies. Avoid publishing
private staff/player metadata merely because the protocol supports a field.

## Map local commands

### Tell

Local syntax:

```text
i3tell friend@OtherMUD Hello there
```

Request:

```json
{
  "jsonrpc": "2.0",
  "id": 30,
  "method": "tell",
  "params": {
    "target_mud": "OtherMUD",
    "target_user": "friend",
    "from_user": "Alyx",
    "message": "Hello there"
  }
}
```

The immediate `status: sent` result is acceptance by the handler, not a remote
read receipt. Surface a later `error_occurred` event to the originating player
when `to_user` identifies them.

### Emoteto

Use the parameter name `emote`:

```json
{
  "jsonrpc": "2.0",
  "id": 31,
  "method": "emoteto",
  "params": {
    "target_mud": "OtherMUD",
    "target_user": "friend",
    "from_user": "Alyx",
    "emote": "$N waves."
  }
}
```

### Channel join and leave

```json
{"jsonrpc":"2.0","id":32,"method":"channel_join","params":{"channel":"intergossip"}}
{"jsonrpc":"2.0","id":33,"method":"channel_leave","params":{"channel":"intergossip"}}
```

The gateway subscription belongs to the authenticated MUD session. Decide
inside the MUD which players can hear or speak on each channel.

### Channel message and emote

```json
{
  "jsonrpc": "2.0",
  "id": 34,
  "method": "channel_send",
  "params": {
    "channel": "intergossip",
    "from_user": "Alyx",
    "visname": "Alyx",
    "message": "Hello, network!"
  }
}
```

For `channel_emote`, use `emote` instead of `message`.

### Mud and channel lists

`mudlist` and `channel_list` are local cached reads. They become populated after
router startup/list synchronization.

```json
{"jsonrpc":"2.0","id":35,"method":"mudlist","params":{"filter":{"status":"up"}}}
{"jsonrpc":"2.0","id":36,"method":"channel_list","params":{}}
```

Do not treat an empty result during startup as proof that the I3 network is
empty; check readiness and retry.

### Who, finger, and locate

These are two-stage operations:

```json
{"jsonrpc":"2.0","id":37,"method":"who","params":{"target_mud":"OtherMUD","from_user":"Alyx"}}
```

Immediate response:

```json
{"jsonrpc":"2.0","id":37,"result":{"status":"requested","mud_name":"OtherMUD"}}
```

Later event:

```json
{
  "jsonrpc": "2.0",
  "method": "who_reply",
  "params": {
    "from_mud": "OtherMUD",
    "to_mud": "YourMUD",
    "to_user": "Alyx",
    "users": [],
    "timestamp": "..."
  }
}
```

`finger` requires `target_mud` and `target_user`; its event contains
`user_info`. `locate` requires `target_user`; multiple `locate_reply` events
may arrive because the request is broadcast.

Use `from_user` to correlate the eventual I3 reply with the player who issued
the command.

## Consume events

### Direct messages

`tell_received` and `emoteto_received` include:

```text
from_mud, from_user, to_mud, to_user, visname, message, timestamp
```

Check that `to_user` is currently valid in the MUD before delivery. Do not
trust remote display names as command input.

### Channel traffic

`channel_message` and `channel_emote` include:

```text
channel, from_mud, from_user, visname, message, timestamp
```

Apply local channel policy, ignore/mute lists, color escaping, and flood
controls. Network admission and local player admission are separate.

### Router errors

`error_occurred` includes:

```text
error_code, error_message, from_mud, to_mud, to_user, context, timestamp
```

Common I3 codes include `unk-dst`, `unk-user`, `unk-channel`, `bad-pkt`,
`bad-proto`, and `not-allowed`.

### Connection events

On `gateway_reconnected`:

1. call `status`;
2. rejoin desired channels;
3. republish the full presence snapshot;
4. avoid replaying non-idempotent tells/channel sends automatically.

## Non-blocking game-loop pattern

For a single-threaded MUD:

```text
network thread/task:
  read complete JSON messages
  correlate responses by id
  enqueue events in a bounded thread-safe queue

main game tick:
  drain at most N events
  validate destination/player/channel
  escape remote text
  deliver through normal game messaging
```

Never call player-output functions directly from a background socket thread
unless the MUD engine explicitly makes them thread-safe.

Use bounded queues. When overloaded, preserve direct messages and errors ahead
of channel chatter, log dropped counts, and recover without unbounded memory
growth.

## Minimal raw Python client

This example uses the installed aiohttp dependency and the canonical wire
contract rather than a convenience wrapper:

```python
import asyncio
import json
import os

import aiohttp


async def main() -> None:
    url = os.getenv("I3_GATEWAY_URL", "ws://127.0.0.1:8080/ws")
    api_key = os.environ["I3_API_KEY"]

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url, headers={"X-API-Key": api_key}) as ws:
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "ping",
                    "params": {},
                }
            )

            async for message in ws:
                if message.type != aiohttp.WSMsgType.TEXT:
                    continue
                data = json.loads(message.data)
                if "id" in data:
                    print("response", data)
                else:
                    print("event", data["method"], data.get("params", {}))


asyncio.run(main())
```

## Bundled client guidance

- The raw contract in [API_REFERENCE.md](API_REFERENCE.md) is canonical.
- The Python and JavaScript clients are useful integration starting points.
  Verify convenience-method parameter names and asynchronous query semantics
  against the API reference when upgrading.
- The CircleMUD C files are reference integration code, not a drop-in patch for
  every CircleMUD derivative. Review
  [its current status](../clients/circlemud/CIRCLEMUD_CLIENT_AUDIT.md).

## Integration test sequence

Use the test router for new client behavior:

1. connect and authenticate locally;
2. verify `ping` and `status`;
3. wait for router readiness;
4. inspect non-empty mudlist and channel list;
5. publish one test player in `presence_sync`;
6. join a designated test channel;
7. send and receive a uniquely tagged channel message;
8. exchange a tell with a cooperating remote MUD;
9. run who/finger/locate and consume their events;
10. disconnect/reconnect the local API and restore state;
11. perform a controlled gateway/router reconnect;
12. publish redacted evidence in [VALIDATION.md](VALIDATION.md).

Do not fuzz or load-test production routers.

## Go-live checklist

- [ ] API key maps to the exact intended MUD name
- [ ] API is private or TLS-protected
- [ ] Local connection/authentication retry is bounded with backoff
- [ ] Router readiness gates player commands
- [ ] Presence refresh runs more often than every 30 seconds
- [ ] Request IDs and asynchronous query replies are correlated
- [ ] Channel subscriptions restore after reconnect
- [ ] Remote text is escaped for the MUD renderer
- [ ] Event queue is bounded and drained on the main game loop
- [ ] Secrets and private content are redacted from logs
- [ ] Test-router command matrix passes
- [ ] Router password/state directory is backed up securely
