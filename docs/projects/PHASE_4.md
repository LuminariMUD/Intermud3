# Phase 4: interoperability and hardening

Phase 4 is active. It is an evidence and completion phase, not a blanket
"advanced features" promise.

## Completed

- live `*i4` startup and state synchronization recorded;
- router credential persistence verified;
- local LuminariMUD TCP authentication observed;
- command-derived regression tests added;
- public player-presence snapshots connected to who/finger/locate replies;
- documentation split into current capability, historical context, and
  protocol reference.

## Remaining gates

- repair the full automated test gate and publish its result;
- publish controlled live round trips for tell, channel, who, finger, and
  locate;
- exercise and record disconnect/reconnect/fallback against the test router;
- align the Python and JavaScript helpers with asynchronous query/event
  semantics and request parameter names;
- complete or explicitly retire the stubbed CircleMUD C paths;
- enforce advertised authorization, payload-size, and connection-limit
  controls at runtime;
- resolve Compose monitoring-port conflicts and activate hosted CI under
  `.github/workflows/`;
- publish a repeatable soak/fault-injection report before making reliability
  or capacity claims.

The maintained priority list is [Roadmap](../ROADMAP.md). The maintained
evidence table is [Validation and interoperability](../VALIDATION.md).
