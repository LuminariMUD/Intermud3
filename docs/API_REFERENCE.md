# Intermud3 Gateway API reference

This is the canonical reference for the API implemented by
`src/api/server.py`, `src/api/tcp_server.py`, and
`src/api/api_handlers.py`.

## Transports

### WebSocket

Connect to:

```text
ws://HOST:8080/ws
```

Use `wss://` when TLS is terminated by a reverse proxy. The gateway’s built-in
listener is plain HTTP/WebSocket.

A WebSocket connection may authenticate with:

```http
X-API-Key: YOUR_API_KEY
```

or by sending `authenticate` as its first message.

### TCP

Connect to `HOST:8081`. The server first emits a `welcome` JSON-RPC
notification. Every client request and server response/event is one compact
UTF-8 JSON object followed by a newline:

```text
{"jsonrpc":"2.0","id":1,"method":"authenticate","params":{"api_key":"YOUR_API_KEY"}}\n
```

Do not use HTTP framing on the TCP port. A partial line remains buffered until
the newline arrives.

### One request per message

Send one JSON-RPC request per WebSocket text frame or TCP line. The protocol
parser contains batch data structures, but the active WebSocket/TCP dispatch
path does not process JSON-RPC batch arrays; batch requests are not part of the
supported API.

Client requests should include an `id`. Server-originated events omit `id`.

## Authentication and identity

The server matches an API key against `api.auth.api_keys` in
`config/config.yaml`. A successful match creates a session with the configured
`mud_name`, permissions, and optional rate-limit override.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "authenticate",
  "params": {"api_key": "YOUR_API_KEY"}
}
```

WebSocket result:

```json
{"jsonrpc":"2.0","id":1,"result":{"status":"authenticated","mud_name":"YourMUD"}}
```

TCP also includes `session_id`.

API-key permissions are currently used when filtering outbound events. The
monolithic method dispatcher does not apply a separate per-method permission
check, so network access to ports 8080/8081 and API-key distribution remain
important trust boundaries.

Rate limiting is a per-session token bucket. The default comes from
`api.rate_limits.default`; an API key can specify `rate_limit_override`.
The `by_method` configuration mapping is present in the schema but is not
applied by the active session limiter.

## Request and response shape

Request:

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "method": "METHOD",
  "params": {}
}
```

Success:

```json
{"jsonrpc":"2.0","id":42,"result":{}}
```

Error:

```json
{
  "jsonrpc": "2.0",
  "id": 42,
  "error": {
    "code": -32601,
    "message": "Unknown method: METHOD"
  }
}
```

## Methods at a glance

| Method | Required parameters | Result behavior |
|---|---|---|
| `authenticate` | `api_key` | Establishes the session |
| `tell` | `target_mud`, `target_user`, `message` | Immediate acceptance result |
| `emoteto` | `target_mud`, `target_user`, `emote` | Immediate acceptance result |
| `channel_send` | `channel`, `message` | Immediate acceptance result |
| `channel_emote` | `channel`, `emote` | Immediate acceptance result |
| `channel_join` | `channel` | Subscribes locally and normally sends `channel-listen` |
| `channel_leave` | `channel` | Unsubscribes locally and sends `channel-listen` off |
| `channel_list` | none | Returns cached router channels |
| `channel_who` | `channel` | Sends a query and returns cached membership |
| `channel_history` | `channel` | Returns local stored history; persistence is not implemented |
| `who` | `target_mud` | Sends request; answer is `who_reply` event |
| `finger` | `target_mud`, `target_user` | Sends request; answer is `finger_reply` event |
| `locate` | `target_user` | Broadcasts request; answers are `locate_reply` events |
| `mudlist` | none | Returns cached router mudlist |
| `presence_sync` | `users` | Replaces this MUD’s current local-player snapshot |
| `ping` | none | Local API round-trip |
| `status` | none | Router and session status |
| `stats` | none | Current state counts |
| `reconnect` | none | Requests an upstream reconnect |
| `heartbeat` | none | Updates the client/API liveness exchange |

## Communication methods

### `tell`

Parameters:

| Name | Type | Required | Meaning |
|---|---|---|---|
| `target_mud` | string | yes | Exact remote MUD name |
| `target_user` | string | yes | Remote player; encoded lowercase on I3 |
| `message` | string | yes | Tell text |
| `from_user` | string | no | Local player; defaults to `Someone` |

Result:

```json
{"status":"sent","message_id":"tell_YourMUD_1785250000.123"}
```

This is not a remote delivery receipt. Router errors are asynchronous.

### `emoteto`

Parameters are `target_mud`, `target_user`, `emote`, and optional
`from_user`. The key is `emote`, not `message`.

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "emoteto",
  "params": {
    "target_mud": "OtherMUD",
    "target_user": "friend",
    "from_user": "Alyx",
    "emote": "$N waves."
  }
}
```

Result has `status: "sent"` and a generated `message_id`.

## Channel methods

### `channel_send`

Parameters: `channel`, `message`, optional `from_user`, optional `visname`.

### `channel_emote`

Parameters: `channel`, `emote`, optional `from_user`, optional `visname`.
The key is `emote`.

### `channel_join`

| Name | Type | Default | Meaning |
|---|---|---|---|
| `channel` | string | required | Channel name |
| `listen_only` | boolean | `false` | Subscribe only inside the gateway; skip upstream `channel-listen` |

`user_name` is accepted by older clients but is not used by the active
handler. The subscription belongs to the authenticated MUD session.

Result:

```json
{"status":"joined","channel":"intergossip"}
```

### `channel_leave`

Requires `channel`; returns `{"status":"left","channel":"..."}`.

### `channel_list`

Optional `filter` members:

- `type`: exact numeric channel type;
- `owner`: exact owner MUD;
- `min_members`: minimum cached member count.

Result:

```json
{
  "status": "success",
  "channels": [
    {"name":"intergossip","owner":"SomeMUD","type":0,"member_count":0}
  ],
  "count": 1,
  "subscribed_channels": ["intergossip"]
}
```

`refresh` is accepted for compatibility but the current handler reads the
router-synchronized cache; it does not force a new chanlist request.

### `channel_who`

Requires `channel`. It emits an upstream request and returns currently cached
membership as:

```json
{"status":"success","channel":"intergossip","members":[]}
```

### `channel_history`

Parameters: `channel`, optional `limit` (default 50, maximum 100), `before`,
and `after`.

The state-manager method currently returns an empty list. Do not treat this
method as durable channel logging.

## Information methods

### `who`

Parameters: `target_mud`, optional `from_user`, optional `filters`.

```json
{"status":"requested","mud_name":"OtherMUD"}
```

If the router send fails immediately, the handler returns `status: "failed"`.
The remote answer is a `who_reply` event.

### `finger`

Parameters: `target_mud`, `target_user`, optional `from_user`.

```json
{"status":"requested","mud_name":"OtherMUD","user_name":"friend"}
```

The answer is a `finger_reply` event.

### `locate`

Parameters: `target_user`, optional `from_user`.

```json
{"status":"requested","user_name":"friend"}
```

The request is broadcast; zero or more `locate_reply` events may follow.

### `mudlist`

Returns the current synchronized cache:

```json
{
  "status": "success",
  "muds": [
    {
      "name": "OtherMUD",
      "host": "203.0.113.10",
      "port": 4000,
      "tcp_port": 0,
      "udp_port": 0,
      "driver": "FluffOS",
      "mudlib": "ExampleLib",
      "mud_type": "LP",
      "status": "up",
      "services": {"tell":1,"channel":1},
      "open_status": "open",
      "admin_email": "admin@example.invalid"
    }
  ],
  "count": 1
}
```

Optional `filter` members:

- `status`: exact status such as `up`;
- `driver`: exact driver string;
- `has_service`: require a service key.

`refresh` is accepted but the current handler returns the synchronized cache.

### `presence_sync`

Replaces the authenticated MUD’s complete public online-player snapshot.
Omitting a previously present player marks that player absent.

Constraints:

- maximum 512 users;
- every user is an object with a non-empty, unique `name`;
- string values must be printable, trimmed, and within their limits;
- `level` is an integer from 0 through 1000;
- `idle` is an integer from 0 through 31,536,000 seconds;
- `login_time` is a non-negative Unix number or a string of at most 64
  characters.

Accepted string fields:

| Field | Maximum length |
|---|---:|
| `name` | 128 |
| `title` | 256 |
| `race` | 128 |
| `guild` | 128 |
| `location` | 256 |
| `status` | 256 |

Result:

```json
{"status":"synchronized","mud_name":"YourMUD","count":1}
```

Presence is current for 30 seconds. Publish a full snapshot more frequently
than that if the gateway should answer inbound who/finger/locate requests.

## Administrative methods

### `ping`

```json
{"pong":true,"timestamp":"2026-07-28T17:00:00.000000"}
```

### `heartbeat`

```json
{"status":"ok","timestamp":"2026-07-28T17:00:00.000000"}
```

### `status`

```json
{
  "connected": true,
  "mud_name": "YourMUD",
  "session_id": "UUID",
  "uptime": 123.45
}
```

### `stats`

Includes:

- `mud_count`
- `online_muds`
- `channel_count`
- `session_count`
- `mudlist_id`
- `chanlist_id`
- `gateway_connected`
- `packets_sent`
- `packets_received`

The last two gateway fields currently fall back to zero unless the gateway
publishes those attributes directly; connection-manager counters are separate.

### `reconnect`

Requests a disconnect/connect cycle and returns `{"status":"reconnecting"}`.
Restrict API network access: the active method dispatcher does not currently
enforce an admin permission for this call.

## Server events

Events are JSON-RPC notifications:

```json
{
  "jsonrpc": "2.0",
  "method": "EVENT_NAME",
  "params": {"timestamp":"2026-07-28T17:00:00.000000Z"}
}
```

Implemented event names:

| Category | Events |
|---|---|
| Communication | `tell_received`, `emoteto_received`, `channel_message`, `channel_emote`, `who_reply`, `finger_reply`, `locate_reply` |
| Network/system | `mud_online`, `mud_offline`, `error_occurred`, `gateway_reconnected` |
| Channel/user | `channel_joined`, `channel_left`, `user_joined_channel`, `user_left_channel`, `user_status_changed` |
| Administrative | `maintenance_scheduled`, `shutdown_warning`, `rate_limit_warning` |

Only events created by an active gateway path will be emitted. The enum also
serves as a stable vocabulary for future producers.

### Communication payloads

`tell_received`:

```json
{
  "from_mud": "OtherMUD",
  "from_user": "friend",
  "to_user": "Alyx",
  "visname": "Friend",
  "message": "Hello!"
}
```

`channel_message` / `channel_emote`:

```json
{
  "channel": "intergossip",
  "from_mud": "OtherMUD",
  "from_user": "friend",
  "visname": "Friend",
  "message": "Hello!"
}
```

`who_reply`, `finger_reply`, and `locate_reply` carry decoded remote response
data plus addressing fields. Consumers should ignore unknown fields for
forward compatibility.

## Error codes

The protocol defines:

| Code | Name |
|---:|---|
| `-32700` | Parse error |
| `-32600` | Invalid request |
| `-32601` | Method not found |
| `-32602` | Invalid parameters |
| `-32603` | Internal error |
| `-32000` | Not authenticated |
| `-32001` | Rate limit exceeded |
| `-32002` | Permission denied |
| `-32003` | Session expired |
| `-32004` | Gateway error |

The WebSocket and TCP wrappers differ in a few error-mapping details. In
particular, exceptions raised inside active method handlers are currently
reported as internal errors. Clients should branch primarily on the numeric
code and retain the message for diagnostics.

## HTTP operational endpoints

All are served on the API HTTP port (default 8080):

| Path | Meaning |
|---|---|
| `/health` | Local API health and current WebSocket/session counts |
| `/health/live` | Process liveness |
| `/health/ready` | HTTP 200 only when the upstream router is connected |
| `/metrics` | Prometheus-text gauges for WebSocket connections and active API sessions |
| `/api/info` | API protocol/transport metadata |

The current `/api/info` payload contains a reserved `/api/docs` value, but the
server does not register that route. This Markdown file is the documentation
endpoint.

## Security and deployment

- Bind the API to loopback or a private network unless remote access is
  required.
- Terminate TLS at a maintained reverse proxy and use `wss://` externally.
- Replace all example keys and do not log authentication payloads.
- Treat `state/router-password` as a credential.
- Do not infer method authorization from configured permission labels until the
  dispatcher enforces it; use network controls and separate credentials.
- Apply input and output limits at the proxy as defense in depth.

See [Deployment](DEPLOYMENT.md) and [Architecture](ARCHITECTURE.md) for trust
boundaries and operating guidance.

