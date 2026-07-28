# Performance testing and tuning

Performance claims are useful only when they name the workload, hardware,
configuration, and revision. This project therefore treats the included
benchmarks as regression tools, not as a deployment SLA.

## Run the included harnesses

Install the development dependencies first:

```bash
python -m pip install -e ".[dev]"
```

Focused benchmark runs can omit the repository-wide coverage gate:

```bash
python -m pytest tests/performance/test_benchmarks.py -q -s -o addopts=''
python -m pytest tests/performance/api/test_api_throughput.py -q -s -o addopts=''
python -m pytest tests/performance/test_stress.py -q -s -o addopts=''
```

The thresholds in those tests are regression floors for their synthetic
workloads. They do not demonstrate a particular production message rate,
concurrent-player count, or soak duration. Run the normal `pytest` command as
well before publishing a release; it applies the configured coverage gate.

When publishing a result, record:

- the Git commit and Python version;
- CPU, memory, operating system, and container limits;
- test name, duration, concurrency, packet size, and warm-up policy;
- whether the router and local API were real or mocked;
- latency percentiles, errors, reconnects, and queue growth-not just throughput.

## Settings that affect the running service

These configuration values are currently wired into runtime behavior:

| Setting | Effect |
|---|---|
| `api.host`, `api.port` | WebSocket/HTTP bind address |
| `api.tcp.host`, `api.tcp.port` | TCP API bind address |
| `api.tcp.max_connections` | Concurrent TCP connection limit |
| `api.websocket.ping_interval` | WebSocket keepalive cadence |
| `api.rate_limit.*` | Session/request rate limiting |

Some schema fields are accepted but are not yet complete tuning controls. In
particular, do not assume that `gateway.max_packet_size`, WebSocket
`max_connections`/frame/compression fields, TCP `buffer_size`, state backup
fields, router connection/retry fields, or every per-method rate-limit entry
changes the corresponding runtime path. The gateway currently constructs its
router manager with a 30-second connection timeout and 60-second keepalive
interval; backoff is hard-coded in `RouterInfo`, `max_reconnect_attempts` is not
enforced, and the keepalive task does not send a packet. Confirm a setting at
its call site before using it as a capacity or security control.

## Tuning order

1. Establish a reproducible baseline with default settings.
2. Watch error rate, event-loop lag, memory, API queues, and reconnects.
3. Change one application setting at a time and repeat the same workload.
4. Raise OS file-descriptor or socket limits only after measuring an actual
   limit.
5. Repeat with representative local-MUD traffic and realistic packet sizes.

The gateway exposes health and Prometheus-text metrics on the API HTTP port.
Use `/health/ready` for router-aware readiness and `/metrics` for the currently
implemented counters. The metrics surface is intentionally modest; use process
and host telemetry for CPU, resident memory, file descriptors, and network I/O.

## Live-network testing

Do not run load, malformed-packet, or disconnect testing against production I3
routers. Way of the Force lists `*wir` at `136.144.155.250:3004` as the test
router. Coordinate disruptive tests with its operator, rate-limit the workload,
and remove player or message content from published traces.

Current evidence and unclaimed validation gaps are maintained in
[Validation and interoperability](VALIDATION.md).
