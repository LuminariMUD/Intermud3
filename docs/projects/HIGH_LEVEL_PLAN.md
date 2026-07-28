# High-level project plan

The gateway isolates I3 protocol complexity from a MUD engine:

```text
MUD client -- JSON-RPC/WebSocket or TCP -- gateway -- I3v3/MudMode -- router
```

## Goals

- speak the deployed I3v3/MudMode protocol correctly;
- keep router credentials and synchronized network state outside the game;
- expose a small language-neutral local API;
- survive ordinary disconnects without blocking a MUD game loop;
- make every interoperability and performance claim reproducible.

## Phase map

| Phase | Scope | Current reading |
|---|---|---|
| 1 | LPC serialization, MudMode framing, configuration, packet models | Implemented; live list decoding observed |
| 2 | Router startup/state plus tell, channel, who, finger, and locate services | Core paths implemented; advanced services remain partial |
| 3 | JSON-RPC, WebSocket/TCP sessions, events, health, and metrics | Implemented as a beta API |
| 4 | Live interoperability, client completion, security boundaries, clean quality gates, and operational evidence | In progress |

The original week-by-week estimates and achieved throughput/coverage figures
were planning artifacts, not reproducible evidence, and have been retired.
Current priorities are maintained in [Roadmap](../ROADMAP.md), while achieved
and missing validation is maintained in
[Validation and interoperability](../VALIDATION.md).

## Architectural boundaries

- `src/network/` owns LPC, framing, and router connections.
- `src/models/` owns packet and connection data models.
- `src/services/` owns I3 service behavior.
- `src/state/` owns persisted and short-lived network/player state.
- `src/api/` owns local JSON-RPC transports, authentication, sessions, events,
  queues, health, and metrics.
- `clients/` contains integrations with different maturity levels; it is not a
  single uniformly supported SDK.

OOB mail/news/file transfer and a full I3 router implementation are outside the
current gateway product. The protocol reference documents them for context but
the gateway does not advertise them as implemented services.
