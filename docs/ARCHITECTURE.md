# Intermud3 Gateway architecture

Intermud3 Gateway is a single-process asynchronous bridge with two protocol
boundaries:

```text
+-------------------- local/private side --------------------+
|                                                            |
|   MUD process -- WebSocket JSON-RPC or TCP JSON-RPC --+    |
|                                                       |    |
|   admin/monitor -- HTTP health + metrics -------------+    |
|                                                       v    |
|             API server, sessions, events, rate limits      |
+---------------------------+--------------------------------+
                            | typed gateway operations
                            v
               services, packet models, state
                            |
                            v
             MudMode framing + LPC serialization
                            | persistent TCP
+---------------------------v--------------------------------+
|                    Intermud-3 router                       |
+-------------------- public/upstream side ------------------+
```

The local MUD never parses LPC and the router never sees local JSON-RPC.

## Runtime components

### Entrypoint and configuration

`src/__main__.py` loads an optional dotenv file, expands `${NAME:default}`
expressions in `config/config.yaml`, validates the result with Pydantic, sets up
logging, and owns the event loop and signal-driven shutdown.

`python -m src --dry-run` exercises configuration loading without opening
network sockets.

### `I3Gateway`

`src/gateway.py` composes the process:

- `StateManager`
- `ServiceManager` and registered I3 services
- `ConnectionManager`
- inbound packet queue
- optional `APIServer`

It translates connection state into I3 startup behavior, handles support
packets (`startup-reply`, `mudlist`, `chanlist-reply`, and `error`), routes core
packets to services, and forwards relevant packets to the event bridge.

### Router transport

`src/network/mudmode.py` implements stream framing:

1. four-byte unsigned big-endian payload length;
2. LPC text payload;
3. trailing NUL included in the advertised length.

It retains incomplete frames across TCP reads and can extract multiple frames
from one read. `src/network/lpc.py` maps Python strings, integers, floats,
lists/tuples, dictionaries, booleans, bytes, and `None` to the deployed
MudMode/LPC representation.

`ConnectionManager` selects configured routers by priority, tracks connection
state/counters, applies per-router exponential backoff with jitter, and
schedules reconnection after a lost transport. The current gateway passes
fixed connection/keepalive intervals rather than the router settings model, and
the keepalive task wakes but does not transmit a packet. Treat the transport's
automatic reconnect as implemented machinery, not a completed keepalive or
bounded-retry guarantee.

### Packet models

`src/models/packet.py` gives each known I3 packet a validated Python model and
an LPC-array conversion. `PacketFactory` selects a concrete model from the
packet-type field.

The generic six-field header is:

```text
[type, ttl, origin_mud, origin_user, target_mud, target_user, ...payload]
```

I3 uses integer zero for many absent/system address fields. Models normalize
those values to convenient Python strings on input and restore protocol zeroes
where required on output.

### Services

Registered service classes consume typed packets:

- `TellService`: tell and emoteto
- `ChannelService`: channel traffic and selected channel-control packets
- `WhoService`: who requests/replies
- `FingerService`: finger requests/replies
- `LocateService`: locate requests/replies
- `RouterService`: routing/support behavior used directly by the gateway

Services may produce a response packet. The gateway sends that response once;
ordinary inbound broadcasts are consumed and exposed locally, never reflected
back to the router.

See [the service matrix](intermud3_docs/services/README.md) for the difference
between full, partial, and reference-only protocol areas.

### State

`StateManager` owns lock-protected:

- incremental mudlist state and version;
- incremental channel-list state and version;
- local public-player presence;
- short-lived query caches;
- API-related user-session data used by I3 responders.

Mud and channel snapshots are loaded on start and written on orderly shutdown
when a state directory is configured. The router password is managed separately
by `I3Gateway`: it is read at startup and written atomically with mode `0600`
when a `startup-reply` assigns a new value.

The configured `state.save_interval` and backup fields are schema values but
are not currently used for periodic snapshot writes. Operators should not
describe them as active scheduled backups.

### Local API

`APIServer` runs:

- an aiohttp HTTP/WebSocket listener;
- an optional asyncio TCP JSON-RPC listener;
- session/authentication management;
- event dispatch and queues;
- channel subscriptions;
- background session cleanup and WebSocket ping tasks.

The handler registry exposes 20 methods. Remote I3 queries are asynchronous:
the call emits an I3 request, while the reply returns later through the event
bridge. This keeps the local connection responsive across network latency and
remote-MUD availability.

## Startup sequence

```text
load dotenv/YAML
  -> validate settings
  -> load persisted mud/channel state
  -> register enabled core services
  -> connect router TCP
  -> connection callback sends startup-req-3
  -> start the local API after the initial connect attempt
  -> receive startup-reply and enter I3 READY state
  -> persist assigned router password
  -> receive mudlist/chanlist data
```

The API listener starts even when the first router connection fails, allowing
health inspection while connection machinery works. `/health` therefore means
the local API is alive. `/health/ready` tests whether the router TCP transport
is connected; it can become 200 before startup acceptance and list
synchronization complete, so it is not a full protocol-synchronization gate.

## Incoming data flow

```text
router bytes
  -> frame buffer
  -> LPC decoder
  -> PacketFactory
  -> gateway packet queue
  +- support packet -> gateway/state
  +- service packet -> service registry
       +- optional response -> router
       +- event bridge -> filtered API sessions
```

Malformed frames or packets are rejected/logged at the earliest layer that has
enough context. An unknown packet type is not silently treated as a supported
service.

## Outgoing data flow

```text
authenticated API request
  -> method handler
  -> typed packet
  -> LPC array
  -> LPC text + NUL
  -> length-prefixed frame
  -> current router TCP transport
```

The authenticated session supplies `originator_mud`; callers supply the local
player identity (`from_user`) and destination fields.

## Trust boundaries

### Local API

API keys authenticate MUD identities. TLS is not provided by the built-in
listener; bind privately or terminate TLS at a reverse proxy. Configuration
permissions currently filter events but are not a complete per-method
authorization layer. Network policy is therefore part of the security model.

### Upstream router

The router-issued password is a credential. Protect the state directory,
exclude it from diagnostics/backups shared with third parties, and never put
the password in command lines or documentation.

### Payloads

I3 content is untrusted remote input. A local MUD should escape content for its
own color/markup system and enforce game-specific policy even after protocol
parsing succeeds.

## Deployment topology

The normal topology is one gateway identity per MUD:

```text
private host/network
+-- MUD process
+-- Intermud3 Gateway
+-- optional reverse proxy / metrics collector
        |
        +-- outbound TCP to one I3 router
```

The process does not require inbound public access from the I3 router. Only the
gateway's outbound router connection is needed unless external local-API
clients are intentionally supported.

## Explicit non-claims

The current architecture does not imply:

- an implemented GraphQL or REST command API;
- built-in TLS termination;
- active/active clustered gateway state;
- a database-backed or durable event queue;
- implemented OOB mail/news/file services;
- durable channel-history storage;
- automatic use of every tuning field present in the configuration schema.

Those boundaries keep the documented system aligned with the running code and
the [roadmap](ROADMAP.md).
