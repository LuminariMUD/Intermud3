# Intermud3 Gateway

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![I3 protocol](https://img.shields.io/badge/Intermud--3-v3-6f42c1)](docs/intermud3_docs/README.md)
[![License: Unlicense](https://img.shields.io/badge/License-Unlicense-2ea44f)](LICENSE)

Intermud3 Gateway is a modern Python sidecar that connects any MUD engine to the
live Intermud-3 network. It owns MudMode framing, LPC serialization, router
registration, packet routing, and network state; a local MUD gets a compact
JSON-RPC 2.0 interface over WebSocket or newline-delimited TCP.

The useful distinction is simple:

```text
your MUD  <-- JSON-RPC -->  Intermud3 Gateway  <-- MudMode/I3v3 -->  I3 router
```

That lets Diku/CircleMUD derivatives, custom engines, web services, and other
non-LPC systems participate without embedding an LPC parser or I3 router state
machine in the game.

## Verified interoperability

This is not documentation-only protocol compatibility. On 2026-07-28, the
current gateway established a live session with `*i4` at
`204.209.44.3:8080`, completed `startup-req-3`/`startup-reply`, persisted the
router-issued password, reached the ready state, and synchronized:

- 164 MUD records at mudlist ID `73041485`
- 169 channel records
- an authenticated local TCP API session from LuminariMUD

The snapshot, commands, automated coverage, and the boundary between verified
and not-yet-asserted behavior are recorded in
[Validation and interoperability](docs/VALIDATION.md). Dynamic network counts
are evidence from that run, not permanent size claims.

## What is implemented

| Area | Current capability |
|---|---|
| Router transport | Persistent TCP, 4-byte big-endian MudMode framing, NUL-terminated LPC text, fragmented-frame buffering |
| Router lifecycle | I3v3 startup, router password persistence, mudlist and chanlist synchronization, reconnect/fallback machinery |
| Core services | `tell`, `emoteto`, channel messages/emotes/listen, `who`, `finger`, and `locate` |
| Local API | 20 JSON-RPC methods over WebSocket (`/ws`) and newline-delimited TCP |
| Events | Incoming tells, emotes, channel traffic, query replies, router errors, and connection notifications |
| State | Persisted mud/channel state; in-memory API sessions and short-lived local player-presence snapshots; channel-history API is currently a placeholder |
| Operations | Health, liveness, readiness, Prometheus-text metrics, structured logs, Docker and systemd assets |
| Integrations | Python and JavaScript clients/examples plus a CircleMUD-oriented C reference integration |

The release is currently `0.4.7-beta`. "Beta" describes the evolving local API
and client packaging; it does not mean the gateway has never spoken to a real
router. See the [service matrix](docs/intermud3_docs/services/README.md) for
packet-level scope and [client status](#client-status) for the exact maturity of
each bundled integration.

## Quick start

### 1. Install

```bash
git clone https://github.com/LuminariMUD/Intermud3.git
cd Intermud3

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Python 3.12, 3.13, and 3.14 are declared as supported.

### 2. Configure

```bash
cp .env.example .env
```

At minimum, set a unique MUD identity and replace every example secret:

```dotenv
MUD_NAME=YourMUD
MUD_PORT=4000
MUD_ADMIN_EMAIL=admin@yourmud.example

I3_ROUTER_NAME=*i4
I3_ROUTER_HOST=204.209.44.3
I3_ROUTER_PORT=8080

I3_GATEWAY_SECRET=replace-with-a-random-secret
API_KEY_LUMINARI=replace-with-a-random-api-key
```

`config/config.yaml` currently reads the exact variable
`API_KEY_LUMINARI` for its primary API credential. If you rename that entry in
the YAML, set the matching variable instead. Do not deploy the example API keys
from the checked-in configuration.

Validate the merged YAML/environment configuration without opening sockets:

```bash
python -m src --dry-run
```

### 3. Run and verify

```bash
python -m src --log-level INFO
```

The default local surfaces are:

| Surface | Address |
|---|---|
| WebSocket JSON-RPC | `ws://127.0.0.1:8080/ws` |
| TCP JSON-RPC | `127.0.0.1:8081` |
| Health | `http://127.0.0.1:8080/health` |
| Router-aware readiness | `http://127.0.0.1:8080/health/ready` |
| Metrics | `http://127.0.0.1:8080/metrics` |

```bash
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8080/health/ready
```

`/health` proves that the local API is alive. `/health/ready` returns HTTP 200
only when the upstream I3 router is connected.

## JSON-RPC in 30 seconds

WebSocket clients may authenticate with an `X-API-Key` handshake header or as
their first request:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "authenticate",
  "params": {"api_key": "your-api-key"}
}
```

Then send a tell:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tell",
  "params": {
    "target_mud": "OtherMUD",
    "target_user": "friend",
    "from_user": "Alyx",
    "message": "Hello from YourMUD!"
  }
}
```

Remote `who`, `finger`, and `locate` calls are asynchronous: the immediate
response confirms that the request was sent, and the network answer arrives as
a `who_reply`, `finger_reply`, or `locate_reply` event. This mirrors I3 packet
semantics and avoids blocking a game loop on another MUD.

See [API reference](docs/API_REFERENCE.md) for all methods, parameters, events,
transport rules, and error codes.

## Client status

The repository intentionally ships integrations at different levels rather
than pretending every language binding has identical maturity.

| Integration | Best use today | Documentation |
|---|---|---|
| Raw WebSocket/TCP | Canonical, smallest integration surface | [API reference](docs/API_REFERENCE.md) |
| Python | Async WebSocket client and integration starting point | [Python client](clients/python/README.md) |
| JavaScript/Node.js | Promise/callback WebSocket client with TypeScript declarations | [JavaScript client](clients/javascript/README.md) |
| Python examples | Bots, bridges, and a small MUD-shaped example | [Examples](clients/examples/README.md) |
| CircleMUD C | Reference code for embedding the TCP API in a CircleMUD-style loop; review the documented implemented subset before adopting | [C client status](clients/circlemud/CIRCLEMUD_CLIENT_AUDIT.md) |

The gateway protocol is language-neutral. A client only needs to authenticate,
send JSON-RPC objects, consume server events, and-in TCP mode-terminate each
JSON object with `\n`.

## Docker

Build and start the gateway service:

```bash
docker compose up --build -d i3-gateway
docker compose logs -f i3-gateway
```

The Compose file persists `state/` and `logs/`. Router credentials are stored
under the state directory; protect that volume as a secret-bearing asset.
Prometheus and Grafana are optional profile scaffolding, not a validated
monitoring stack. The checked-in Compose file maps host port `9090` for both
the gateway and Prometheus, so change or remove the gateway's unused
`9090:9090` mapping before enabling that profile:

```bash
docker compose --profile monitoring up -d
```

The Prometheus configuration also references services not defined by the base
Compose file, and the Grafana provisioning directories are not checked in.
Review the deployment guide before relying on the profile.

For host, systemd, reverse-proxy, and production configuration guidance, use
the [deployment guide](docs/DEPLOYMENT.md).

## Documentation

- [Documentation index](docs/README.md)
- [Validation and interoperability](docs/VALIDATION.md)
- [API reference](docs/API_REFERENCE.md)
- [Integration guide](docs/INTEGRATION_GUIDE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Performance testing and tuning](docs/PERFORMANCE_TUNING.md)
- [I3 protocol reference](docs/intermud3_docs/README.md)
- [Roadmap](docs/ongoing-projects/ROADMAP.md)
- [Changelog](docs/CHANGELOG.md)

## Development

```bash
python -m pip install -e ".[dev]"
pytest
ruff check src tests
black --check src tests
mypy src
```

The test tree covers codec/framing, packet models, router state, services, API
sessions/events, integration paths, regression cases found during live
interoperability work, and performance harnesses. Current, reproducible results
belong in [docs/VALIDATION.md](docs/VALIDATION.md), not in a hand-maintained
badge.

Read [CONTRIBUTING.md](docs/CONTRIBUTING.md) before submitting changes and
follow the [Code of Conduct](docs/CODE_OF_CONDUCT.md).

## License

The repository's [LICENSE](LICENSE) contains the Unlicense/public-domain
dedication. `pyproject.toml` currently declares MIT instead, so package
metadata is inconsistent and should be corrected before publishing a
distribution.
