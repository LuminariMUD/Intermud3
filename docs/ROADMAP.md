# Roadmap

Intermud3 Gateway already provides the core router bridge and local JSON-RPC
API. This roadmap lists work that is useful but must not be described elsewhere
as shipped until its acceptance evidence exists.

## Current priorities

### Restore a green quality gate

- Repair fixed-port and async-teardown behavior in API end-to-end tests.
- Start mock routers before gateway connection attempts in integration
  fixtures.
- Resolve router-service, connection-manager, and connection-pool expectation
  failures.
- Wire router timeout/retry settings into the connection manager and implement
  an actual protocol-safe keepalive or remove the inactive setting.
- Move the intended GitHub Actions file under `.github/workflows/`, then link
  hosted results rather than inferring them from configuration.
- Reconcile `pyproject.toml` license metadata with the repository's Unlicense
  text, and its Alpha classifier with the beta version label, before publishing
  a distribution.
- Replace the dated failure snapshot in
  [Testing](projects/TESTING.md) only after the configured `pytest` gate exits
  successfully.

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

Historical phase plans live in the [project records](projects/README.md). They are retained
for provenance, not used as the current roadmap.
