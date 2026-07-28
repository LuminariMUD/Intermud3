# Testing

This page records the test surface and its current reproducible status. It does
not infer pass counts from collection or preserve old coverage estimates.

## Current snapshot

Observed on 2026-07-28 with Python 3.12.3 at code commit `c5ffd8e`:

```bash
./venv/bin/python -m src --dry-run
```

Result: configuration valid; CLI reported `0.4.5-beta`.

```bash
./venv/bin/python -m pytest --collect-only -q -o addopts=''
```

Result: **940 tests collected** in 0.40 seconds.

Collection proves inventory only. It does not prove those tests pass.

The live-command regression file was also run directly:

```bash
./venv/bin/python -m pytest \
  tests/regression/test_i3_command_regressions.py \
  -q -o addopts=''
```

Result: **8 passed**, with deprecation warnings, in 0.26 seconds.

## Full-gate status

The full `pytest` gate is **not green in the audited environment** and must not
be represented as such.

Observed blockers include:

- API end-to-end tests that bind fixed port 8080 and use an async teardown
  pattern that is not awaited by the current aiohttp/pytest stack, causing the
  next test to collide with the first server;
- mock-gateway integration setup that starts the gateway before its mock router
  is listening;
- router-service expectations that differ from current forwarding behavior;
- connection-manager/fallback lifecycle expectation failures;
- multiple connection-pool timeout, cleanup, and statistics failures;
- legacy LPC tests that still expect the abandoned binary type-tag format
  instead of deployed LPC text.

A focused run across regression, services, network units, and packet-model
tests produced **420 passes and 12 failures**. These numbers are a dated
diagnostic result, not a release badge.

## Suite layout

| Path | Scope |
|---|---|
| `tests/unit/` | Packet models, codecs, network/state utilities, and API components |
| `tests/services/` | I3 service request/reply/routing behavior |
| `tests/api/` | Authentication and event-system behavior |
| `tests/integration/` | Mock-router and local API composition |
| `tests/regression/` | Regressions derived from live command auditing |
| `tests/performance/` | Synthetic throughput, stress, and latency harnesses |

The current protocol boundary also has a split result:

```bash
./venv/bin/python -m pytest \
  tests/unit/network/test_mudmode.py \
  tests/unit/test_packet.py \
  tests/unit/test_packet_fixed.py \
  tests/regression/test_i3_command_regressions.py \
  -q -o addopts=''
```

Result: **55 passed** with deprecation warnings in 0.28 seconds.

By contrast, `tests/unit/test_lpc.py` still asserts the retired binary
type-tagged codec. The running implementation correctly uses deployed LPC
text, so that legacy file currently contributes 11 failures and must be
rewritten rather than used as evidence for binary behavior.

## Commands

Run the configured test and coverage gate:

```bash
pytest
```

Run a focused suite without repository-wide coverage options:

```bash
python -m pytest tests/regression -q -o addopts=''
python -m pytest tests/unit/network -q -o addopts=''
python -m pytest tests/integration -q -o addopts=''
```

Use `-o addopts=''` only to accelerate diagnosis. The default configuration
enables source coverage and requires 80% line coverage. Until `pytest` exits
successfully with that configuration, the coverage gate is not satisfied.

## Evidence rules

- Record the command, environment, commit, exit status, and warnings.
- Separate mock-router, test-router, and production-router observations.
- Do not call a performance threshold a production SLA.
- Do not describe an unrun test file as coverage.
- Keep known failures visible until a clean rerun replaces this snapshot.
