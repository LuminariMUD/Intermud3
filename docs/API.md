# Intermud3 Gateway API

The gateway exposes JSON-RPC 2.0 over two transports:

- WebSocket: `ws://HOST:8080/ws`
- TCP: `HOST:8081`, one UTF-8 JSON object per line

The canonical, complete documentation is
[API_REFERENCE.md](API_REFERENCE.md). This page is the integration cheat sheet.

## Authenticate

For WebSocket, send `X-API-Key` during the upgrade handshake or authenticate as
the first JSON-RPC call. TCP clients authenticate with the first call:

```json
{"jsonrpc":"2.0","id":1,"method":"authenticate","params":{"api_key":"YOUR_KEY"}}
```

The authenticated MUD name comes from the matching `api.auth.api_keys` entry in
`config/config.yaml`; clients cannot select an arbitrary origin MUD in a
request.

## Send a tell

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tell",
  "params": {
    "target_mud": "OtherMUD",
    "target_user": "friend",
    "from_user": "Alyx",
    "message": "Hello!"
  }
}
```

The immediate result means the gateway accepted the operation. I3 has no
end-to-end delivery receipt for a normal tell; a router/remote-MUD failure may
arrive later as `error_occurred`.

## Join and use a channel

```json
{"jsonrpc":"2.0","id":3,"method":"channel_join","params":{"channel":"intergossip"}}
{"jsonrpc":"2.0","id":4,"method":"channel_send","params":{"channel":"intergossip","from_user":"Alyx","message":"Hello, network!"}}
```

Incoming traffic is a server notification:

```json
{
  "jsonrpc": "2.0",
  "method": "channel_message",
  "params": {
    "channel": "intergossip",
    "from_mud": "OtherMUD",
    "from_user": "friend",
    "visname": "Friend",
    "message": "Welcome!",
    "timestamp": "2026-07-28T17:00:00.000000Z"
  }
}
```

## Remote queries are asynchronous

```json
{"jsonrpc":"2.0","id":5,"method":"who","params":{"target_mud":"OtherMUD","from_user":"Alyx"}}
```

The response is `{"status":"requested",...}`. The remote answer arrives later
as a `who_reply` notification. `finger`/`finger_reply` and
`locate`/`locate_reply` follow the same pattern.

## Publish local player presence

An authenticated MUD can replace its public online-player snapshot:

```json
{
  "jsonrpc": "2.0",
  "id": 6,
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

Send a complete snapshot at least every 30 seconds while players are online.
The gateway uses current presence to answer inbound I3 `who`, `finger`, and
`locate` requests.

## Discover current state

```json
{"jsonrpc":"2.0","id":7,"method":"mudlist","params":{"filter":{"status":"up","has_service":"tell"}}}
{"jsonrpc":"2.0","id":8,"method":"channel_list","params":{}}
{"jsonrpc":"2.0","id":9,"method":"status","params":{}}
```

## Health without JSON-RPC

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/health/live
curl http://127.0.0.1:8080/health/ready
curl http://127.0.0.1:8080/metrics
curl http://127.0.0.1:8080/api/info
```

Use `/health/ready` for traffic readiness because it includes upstream-router
connectivity.

