# Roadmap

Intermud3 Gateway already provides the core router bridge and local JSON-RPC
API. This roadmap lists work that is useful but must not be described elsewhere
as shipped until its acceptance evidence exists.

## Current priorities

### Publish the complete live command matrix

- Record redacted, repeatable round trips for tell, emoteto, channel
  send/receive, who, finger, and locate.
- Exercise a controlled router disconnect and confirm credential reuse,
  backoff, resubscription, and duplicate-free state.
- Add the results to [VALIDATION.md](VALIDATION.md).

### Harden protocol boundaries

- Enforce the configured maximum MudMode frame length before allocation.
- Expand malformed-input coverage to invalid escapes, hostile nesting depth,
  extreme numeric forms, and multiple corrupt frames followed by a valid frame.
- Run a reproducible fuzz campaign and retain its configuration and summary.

### Align bundled clients

- Keep Python and JavaScript convenience methods synchronized with the
  asynchronous gateway response/event contract.
- Replace the remaining CircleMUD C stubs or reduce its public API to the
  implemented subset.
- Add client-specific automated tests and package/release instructions only
  when a package is actually published.

### Operations evidence

- Publish a sustained soak report with reconnect cycling and representative
  traffic.
- Validate the Docker Compose monitoring profile as one deployable stack.
- Add an operator runbook for backup/restore of state and router credentials.

## Later opportunities

- Optional durable API event queues.
- Multiple active local MUD identities per gateway process.
- Additional I3/OOB services such as mail, news, and file transfer.
- A browser administration surface backed by the existing API.
- Structured protocol-trace export with automatic secret redaction.

## Completed foundation

- MudMode/LPC transport and packet models.
- I3v3 startup, router password persistence, mudlist, and chanlist state.
- Tell, emoteto, channel, who, finger, and locate service paths.
- WebSocket and TCP JSON-RPC servers with authentication, sessions, events,
  health, readiness, and metrics.
- Source, Docker, systemd, and local-development deployment assets.
- Live `*i4` registration and list synchronization.

Historical phase plans live under [`projects/`](projects/). They are retained
for provenance, not used as the current roadmap.

