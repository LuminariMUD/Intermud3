# Phase 3 record: local gateway API

> Historical milestone record. The canonical contract is the
> [API reference](../API_REFERENCE.md).

Phase 3 added the local integration surface:

- JSON-RPC 2.0 request and response envelopes;
- WebSocket `/ws` and newline-delimited TCP transports;
- API-key sessions and rate limiting;
- service methods, subscriptions, queues, and I3-derived events;
- liveness, router-aware readiness, API information, and metrics endpoints;
- Python, JavaScript, examples, and a CircleMUD-oriented C integration.

The API currently exposes 20 methods. Remote `who`, `finger`, and `locate`
results arrive as events, not in the immediate response. The bundled language
clients are useful starting points but have documented contract mismatches, and
the C integration contains unimplemented receive/command paths.

Earlier phase text labeled the system production-ready and attached fixed
connection, throughput, pass-rate, and coverage numbers. Those claims did not
identify reproducible runs and are no longer current. See
[Testing](TESTING.md) and [Performance](../PERFORMANCE_TUNING.md).
