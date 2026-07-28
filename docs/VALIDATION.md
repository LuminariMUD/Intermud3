# Validation and interoperability

This page records evidence for the current gateway rather than relying on
marketing labels. It distinguishes a live observation, an automated test, and
a future acceptance gate.

## Live-network snapshot

**Observed:** 2026-07-28 (Asia/Jerusalem)

**Gateway release metadata:** `0.4.5-beta`

**Code revision:** `c5ffd8e` (52 reachable commits at the snapshot)

**Router:** `*i4` (`204.209.44.3:8080`)

The running gateway demonstrated:

| Check | Evidence | Result |
|---|---|---|
| Router TCP transport | Established process socket to `204.209.44.3:8080` | Pass |
| I3 startup negotiation | `startup-reply` accepted and connection entered ready state | Pass |
| Router credential lifecycle | Non-zero router password persisted to `state/router-password` with owner-only permissions | Pass |
| Mudlist synchronization | Mudlist ID `73041485`, 164 records persisted | Pass |
| Chanlist synchronization | 169 channel records persisted | Pass |
| HTTP health | `GET /health` returned HTTP 200 | Pass |
| Router-aware readiness | `GET /health/ready` returned HTTP 200 with `{"status":"ready"}` | Pass |
| Local MUD API | LuminariMUD held an authenticated TCP session on `127.0.0.1:8081` | Pass |

MUD and channel totals change as the network changes. They are included to
prove that the gateway parsed real router payloads, not to promise a fixed
network size.

The commit and test counts establish that older repository-size summaries are
stale, but counts alone are not quality evidence. The live handshake/state
results and targeted regressions establish real interoperability; the open
matrix and non-green full test gate prevent that evidence from being inflated
into an unsupported production-readiness or soak claim.

## Reproduce the non-invasive checks

With the gateway running:

```bash
curl --fail --silent http://127.0.0.1:8080/health
curl --fail --silent http://127.0.0.1:8080/health/ready
curl --fail --silent http://127.0.0.1:8080/metrics
ss -tnp | grep '204.209.44.3:8080'
```

Inspect synchronized state without exposing the router password:

```bash
jq '{mudlist_id, mud_count: (.muds | length)}' state/mudlist.json
jq 'length' state/channels.json
stat -c '%a %n' state/router-password
```

Expected password-file mode is `600`. Never paste its contents into an issue,
test transcript, or packet capture.

## Automated validation

The repository contains separate test layers:

- codec and packet-model tests, including fragmented MudMode frames, malformed
  LPC input, escaping, numeric types, and nested values;
- service tests for tell/emoteto, channels, who, finger, locate, and router
  behavior;
- API tests for authentication, sessions, JSON-RPC, events, subscriptions,
  queues, WebSocket/TCP coordination, and health endpoints;
- integration tests with mock routers and end-to-end API fixtures;
- regression tests derived from live in-game command auditing;
- performance and stress harnesses with explicit thresholds.

### Audited test status

Observed on 2026-07-28 with Python 3.12.3 at code commit `c5ffd8e`:

| Command/scope | Result |
|---|---|
| `python -m src --dry-run` | Configuration valid; reported `0.4.5-beta` |
| `pytest --collect-only -q -o addopts=''` | 940 tests collected in 0.40 seconds |
| `tests/regression/test_i3_command_regressions.py` | 8 passed with deprecation warnings in 0.26 seconds |
| MudMode + packet models + live-command regressions | 55 passed with deprecation warnings in 0.28 seconds |
| regression + services + network units + packet models | 420 passed, 12 failed |
| configured full `pytest` gate | Not green in the audited environment |

Collection is an inventory, not a pass. Current failures include fixed-port and
async-teardown problems in API end-to-end tests, mock-router startup ordering,
router-service expectation drift, connection lifecycle assertions, and
connection-pool timeout/cleanup/statistics cases. A legacy LPC unit file also
expects the retired binary type-tag format and fails against the deployed text
codec. See
[Testing](projects/TESTING.md) for the commands and failure categories.

Collect the exact current inventory:

```bash
python -m pytest --collect-only -q -o addopts=''
```

Run the configured quality gate:

```bash
pytest
```

`pyproject.toml` enables source coverage and requires at least 80% line
coverage. Until this command exits successfully, neither a green suite nor the
coverage threshold should be claimed. The dated collection count is kept here,
not duplicated in a README badge.

Targeted suites are useful while iterating:

```bash
python -m pytest tests/unit tests/services tests/regression -q -o addopts=''
python -m pytest tests/integration -q -o addopts=''
python -m pytest tests/performance -q -o addopts=''
```

## Interoperability acceptance matrix

This matrix prevents "the code exists" from being confused with "the behavior
was observed on a live network."

| Capability | Automated evidence | Live evidence | Current claim |
|---|---|---|---|
| MudMode framing and LPC round-trip | MudMode/packet subset passes; legacy binary-codec LPC tests need replacement | Real `*i4` lists decoded | Live verified; automated gate partial |
| Startup and router password persistence | Unit/regression tests | `startup-reply` and persisted credential observed | Verified |
| Mudlist and chanlist acquisition | Unit/regression tests | Full live snapshots observed | Verified |
| WebSocket and TCP authentication | API/integration tests | TCP session from LuminariMUD observed | Verified |
| Tell/channel/who/finger/locate packet paths | Service, integration, and live-audit regressions | Record command transcript before claiming a complete live round trip | Automated; live transcript pending publication |
| Disconnect/reconnect | Tests exist, but the current connection/integration gate includes failures | Controlled live router-cycle transcript not yet published | Machinery present; validation incomplete |
| Malformed/adversarial input | Fragmentation/malformed cases exist, but the full codec gate is not green | No independent fuzz campaign published | Partial cases; not a fuzzing claim |
| Sustained load | Performance/stress harnesses | No 24-hour live soak report published | Harness available |
| Cross-implementation packet diff | Packet-shape tests | No public packet-capture comparison published | Not asserted |

The deliberately narrow wording is a strength: reviewers can see exactly which
conclusions the evidence supports. A missing live transcript is a validation
task, not evidence that router compatibility is unknown.

## Test-router policy

Way of the Force designates `*wir` at `136.144.155.250:3004` for testing new I3
clients and routers. Use it for experimental packet shapes or disruptive
failure testing. The snapshot above used `*i4` because it validated an
established LuminariMUD identity against the live network; it was not a fuzz or
load run.

Current router references:

- [Way of the Force I3 network and test-router guidance](https://wotf.org/i3/)
- [MUD Standards I3 reference](https://mudstandards.org/intermud/intermud3/)
- [MudMode transport specification](https://wotf.org/specs/mudmode.html)

## Publishing new evidence

When updating this page:

1. Record the date, release/commit, router, and exact command.
2. Redact API keys, router passwords, player credentials, IP addresses that are
   not already public router endpoints, and private message content.
3. Separate mock-router results from live-router results.
4. Report failures as failures; do not convert targets into achieved metrics.
5. Keep dynamic counts in dated snapshots rather than badges.
