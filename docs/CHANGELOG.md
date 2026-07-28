# Changelog

This file summarizes user-visible changes. The repository currently has no Git
tags, so release numbers below refer to package metadata and the corresponding
commits rather than signed release artifacts.

## Unreleased

No changes recorded.

## 0.4.7-beta - 2026-07-29

### Documentation

- Moved the active roadmap under `docs/ongoing-projects` and repaired its
  inbound and relative links.
- Added a phased production resilience and high-availability plan covering
  router keepalive, supervision, monitoring, backup/restore, recovery drills,
  soak testing, and optional active-passive host failover.

## 0.4.6-beta - 2026-07-28

### Documentation

- Replaced stale phase plans, fixed test totals, throughput claims, and
  "production-ready" labels with reproducible validation evidence.
- Documented the live `*i4` interoperability snapshot, client maturity,
  protocol-service scope, operational caveats, and known test-gate failures.

## 0.4.5-beta - 2026-07-28

- Added local-player presence synchronization used to answer remote `who`,
  `finger`, and `locate` requests.
- Repaired packet shapes and event delivery found during live command auditing.
- Added regression coverage for the audited command paths.
- Confirmed a live router startup, password persistence, mudlist/chanlist
  synchronization, health/readiness, and an authenticated local TCP client.

## 0.4.4-beta - 2026-07-28

- Preserved incoming I3 channel message and emote payloads while parsing.

## 0.4.3-beta - 2026-07-28

- Persisted router-issued credentials and derived the local API identity from
  the configured MUD name.
- Repaired live I3 state and reply handling around startup, lists, and core
  services.

## 0.4.2-beta - 2026-07-28

- Corrected live startup and protocol-state handling.

## 0.4.1-beta - 2026-01-18

- Added local deployment automation and environment-based ngrok configuration.

## 0.4.0-beta - 2026-01-01

- Marked the combined router gateway and local JSON-RPC API as beta.

## 0.2.0 - 2026-01-01

- Added local-development deployment guidance and repaired LPC/MudMode
  interoperability details.

Older development narratives are retained as explicitly historical records in
[previous changelogs](previous_changelogs/README.md). Current capability claims
belong in [Validation and interoperability](VALIDATION.md), not in this file.
