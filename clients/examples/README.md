# Python integration examples

These scripts are prototypes built on `clients/python/i3_client.py`. They are
useful for studying event wiring and application structure, but they inherit
the Python client's documented contract differences and are not maintained as
standalone production services.

## Common setup

From the repository root:

```bash
python -m pip install -e .
export I3_API_KEY='replace-with-a-configured-key'
export I3_GATEWAY_URL='ws://127.0.0.1:8080/ws'
```

The scripts add `clients/python` to their import path themselves. Always
override `I3_GATEWAY_URL`: their source defaults currently omit `/ws`.

## Scripts

| Script | What it demonstrates | Additional dependencies/cautions |
|---|---|---|
| `simple_mud.py` | A MUD-shaped event loop, local players, tells, and channels | Simulated game state; not an engine adapter |
| `channel_bot.py` | Channel commands and simple bot rate limiting | Do not run unsolicited on public channels |
| `relay_bridge.py` | I3-to-Discord/IRC bridge structure | Integration sections are prototypes; review tokens, loop prevention, platform APIs, and dependencies |
| `web_client.py` | FastAPI-shaped browser/admin surface | Default web auth token and permissive CORS are unsafe; configure before any shared bind |

Run the smallest example:

```bash
python clients/examples/simple_mud.py
```

The web and relay examples import optional third-party packages that are not
part of the gateway's core dependencies. Inspect each script's imports and
install only the integrations you intend to use.

## Semantics to preserve

- One authenticated API session represents the MUD named by the configured API
  key.
- Use `/ws` in the WebSocket URL.
- Remote `who`, `finger`, and `locate` answers arrive as events.
- Send `presence_sync` at least every 30 seconds if the gateway should answer
  remote player-information queries for a real MUD.
- Treat channel names and remote MUD names as live network data.
- Never embed API keys, Discord tokens, IRC passwords, or web admin tokens in
  source.

For a new integration, begin with the
[raw API contract](../../docs/API_REFERENCE.md) and then borrow only the
example pieces you need.
