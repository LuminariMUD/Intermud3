# Production resilience and high-availability plan

- **Status:** Proposed
- **Priority:** High
- **Last updated:** 2026-07-29

**Target:** A production deployment that recovers automatically from expected
process, network, and host failures, with measurable detection, recovery, and
operator evidence.

## Outcome

Intermud3 Gateway should recover without manual intervention from a crashed
process, a restarted Docker daemon, a server reboot, and a lost or half-open
router connection. Operators should be alerted when recovery does not complete,
and persistent router identity must survive every tested recovery path.

This plan distinguishes self-healing from high availability:

- **Single-host self-healing** restores service after a failure and necessarily
  includes a short outage.
- **Multi-host high availability** is an optional later phase for surviving a
  complete host failure. It requires active-passive coordination because two
  gateways must not simultaneously claim the same I3 MUD identity.

No deployment should be described as "never down." Availability claims must be
based on measured recovery tests and a published service objective.

## Current baseline

The repository already has:

- Docker restart policies and a systemd unit;
- graceful `SIGTERM`/`SIGINT` shutdown;
- router reconnect, exponential backoff, and fallback-router machinery;
- HTTP liveness/readiness endpoints;
- persistent Docker volumes for state and logs;
- immediate atomic persistence of the router-issued password;
- Prometheus, Alertmanager, and alert-rule scaffolding.

The following gaps prevent a complete production-resilience claim:

| Area | Current gap |
|---|---|
| Router keepalive | The scheduled keepalive task sends no packet and does not detect a silent or half-open connection. |
| Configuration | Router timeout, keepalive, and reconnect settings are not fully wired into the active connection manager. |
| Readiness | Readiness accepts a raw TCP connection before `startup-reply` confirms a ready I3 session. |
| Container health | Compose probes `/health`, which reports the local API as healthy without checking router state. |
| Automatic remediation | Docker marks a failed health check as unhealthy but the current stack has no mechanism that terminates or replaces an unhealthy-but-running gateway. |
| Task supervision | Critical background tasks can fail without a top-level watchdog forcing process recovery. |
| Monitoring | The optional monitoring profile references missing services, mounts, and metrics. |
| Persistence | Periodic saves and configured backups are not active; mud/channel state writes are not atomic. |
| Validation | Reconnect tests and the configured full test/coverage gate are not green, and no controlled failover soak report exists. |
| Host failure | The deployment has one gateway on one host and no fenced standby. |

## Availability targets

These are engineering acceptance targets, not a public SLA:

- A crashed process or killed container restarts automatically and becomes
  locally live within 60 seconds.
- After a normal server reboot, the gateway becomes I3-ready within five
  minutes of network availability when a configured router is reachable.
- A half-open router connection is detected within 90 seconds by default.
- When any configured router is reachable, a disconnected gateway returns to
  `READY` within two minutes of detection, excluding a deliberately configured
  longer backoff.
- Router reconnect attempts continue indefinitely in production with bounded,
  jittered backoff and no busy loop.
- Router-password recovery point objective is zero after the password has been
  acknowledged and persisted.
- An external monitor alerts within five minutes when liveness is down,
  readiness remains down, the gateway flaps, or recovery exceeds its target.
- A restore exercise proves that credentials and required state can be restored
  on a clean host.

Targets must become configuration values where operators reasonably need to
tune them. Test assertions should use accelerated values rather than weakening
production defaults.

## Design rules

1. **Readiness failure is not automatically a process failure.** A remote router
   outage should keep the process alive and reconnecting; repeatedly restarting
   the gateway would add load without repairing the dependency.
2. **Liveness is local.** It should fail only when the process or a critical
   internal task cannot make progress.
3. **Readiness is protocol-aware.** It should pass only after TCP connection,
   successful startup negotiation, and entry into `ConnectionState.READY`.
4. **One supervisor owns each process.** Use either the documented Docker
   deployment or the native systemd deployment; do not run the same gateway
   under both.
5. **Recovery preserves identity.** Never delete or replace
   `state/router-password` as an automated recovery action.
6. **No active-active identity without protocol evidence.** A standby must be
   fenced until it is safe for it to claim the configured MUD name.
7. **Claims follow evidence.** Configuration and test inventory alone do not
   prove an availability objective.

## Workstream 1: router connection lifecycle

### 1.1 Wire active configuration

- Pass `router.connection.timeout`, `keepalive_interval`, reconnect delay, and
  retry policy from validated settings into `ConnectionManager`.
- Define `max_reconnect_attempts: 0` as unlimited, or replace the field with a
  clearer production-safe model. Production must not stop retrying permanently.
- Reject impossible combinations during configuration validation.
- Log the effective non-secret connection policy once at startup.

### 1.2 Implement dead-peer detection

- Track monotonic timestamps for the last inbound packet, outbound packet,
  successful keepalive response, TCP connection, and `startup-reply`.
- Enable operating-system TCP keepalive with documented Linux defaults for
  idle time, probe interval, and probe count.
- Select an I3 protocol-safe application probe using the test router before
  enabling it against a production router.
- Require a correlated response or other protocol-valid evidence of peer
  activity. Sending traffic without checking a response is not a watchdog.
- Close the transport and enter the reconnect path after the configured
  dead-peer threshold.
- Add jitter so multiple gateways do not probe or reconnect in lockstep.

The application probe must be approved against `*wir` or a controlled mock
router. If no safe request/reply probe exists, use TCP keepalive plus an inbound
activity deadline and document the resulting detection limits.

### 1.3 Make reconnection deterministic

- Ensure only one reconnect task and one keepalive task can exist per manager.
- Observe and log unexpected task termination.
- Use one calculated backoff deadline per router attempt instead of
  recalculating random jitter during eligibility checks.
- Reset failure counters only after the intended success boundary is reached.
- Re-run I3 startup negotiation after every new transport connection.
- Confirm password reuse, list refresh, channel resubscription, and
  duplicate-free event delivery after reconnect.
- Define client behavior during an upstream outage: fail fast with a clear
  retryable error or use a bounded queue with an explicit TTL. Do not silently
  discard accepted messages.

### 1.4 Connection acceptance tests

- Initial router unavailable, then becomes available.
- Primary router refuses connections while a valid fallback is reachable.
- Router sends FIN.
- Router sends RST.
- Network becomes a silent black hole with no FIN/RST.
- DNS lookup, connect timeout, and authentication/startup negotiation fail.
- Connection flaps repeatedly.
- Shutdown occurs during backoff and during a keepalive probe.
- Reconnect succeeds after reaching maximum backoff.
- No orphan tasks, duplicate startup packets, or duplicate subscriptions remain.

## Workstream 2: health, watchdogs, and metrics

### 2.1 Define endpoint contracts

- `/health/live` returns 200 only while the event loop and all critical
  background-task heartbeats are progressing.
- `/health/ready` returns 200 only in `ConnectionState.READY`; include the
  selected router and state age without exposing credentials.
- `/health` returns a summary suitable for operators and may report
  `healthy`, `degraded`, or `unhealthy`.
- Keep health endpoints fast, side-effect free, bounded by short timeouts, and
  available without normal API authentication only on a protected interface.
- Consolidate or remove the unused health-checking implementation so there is
  one authoritative health model.

Readiness may later require fresh mudlist/chanlist synchronization, but that
must be a documented decision. It must never pass merely because a TCP socket
was opened.

### 2.2 Supervise critical tasks

- Register packet processing, reconnect, keepalive, event dispatch, queue
  processing, session cleanup, and TCP/WebSocket server tasks with a task
  supervisor.
- Capture task exceptions and expose task status in health and metrics.
- Restart a safely restartable task in place with bounded retry.
- Exit non-zero when a critical, non-recoverable task fails so the outer
  supervisor can restart the process.
- Add a process watchdog capable of detecting an event-loop stall. Select and
  document one implementation for each supported deployment:
  - systemd `WatchdogSec` with `sd_notify`, or
  - a Docker-compatible watchdog/remediation mechanism that does not confuse
    router unavailability with process failure.

### 2.3 Export actionable metrics

At minimum, export:

- gateway build/version information;
- process start time and uptime;
- current connection state;
- seconds since last inbound router packet;
- seconds since last successful keepalive;
- reconnect attempts and outcomes by router;
- current backoff duration;
- startup negotiation failures;
- critical task status and task restarts;
- packet queue depth and dropped/expired messages;
- API connection/session counts and request errors;
- process memory, CPU, file-descriptor, and disk-space indicators where the
  platform does not already provide them.

Metric names used in alert rules must exist in `/metrics` and have tests.

## Workstream 3: deployment supervision

### 3.1 Make one Docker Compose stack deployable

- Keep `restart: always` in the production overlay.
- Probe `/health/live` for container liveness; monitor `/health/ready`
  separately for router availability.
- Add an explicit unhealthy-container remediation design. Document its trust
  boundary if it needs access to the Docker socket.
- Remove the unused gateway `9090:9090` mapping or assign non-conflicting
  monitoring ports.
- Add `stop_grace_period` based on measured shutdown time.
- Verify memory/CPU limits and expected OOM restart behavior.
- Add a production preflight command that verifies:
  - required bind directories exist and are owned by container UID 1000;
  - secrets are present without printing them;
  - configuration validates;
  - the merged Compose configuration is valid;
  - required outbound router endpoints are reachable.
- Pin deployable image versions or digests instead of relying on mutable
  `latest` for rollback.
- Document Docker daemon boot enablement and verify the effective restart policy
  with `docker inspect`.

### 3.2 Harden the native systemd alternative

- Replace layout-specific paths with an install template or clearly generated
  unit.
- Use a root-owned environment file and dedicated unprivileged account.
- Retain filesystem hardening and restrict writable paths.
- Add watchdog notification if systemd is the selected supervisor.
- Set restart rate limits deliberately and document how to clear a throttled
  unit after correcting configuration.
- Use journald or a tested external rotation policy rather than unbounded
  append-only files.
- Add `ExecStartPre` configuration and permission validation.
- Verify `systemctl enable` and boot recovery on a clean test host.

## Workstream 4: monitoring and alerting

- Add the missing Alertmanager, node-exporter, alert-rule mount, and Grafana
  provisioning required by the monitoring profile, or remove unsupported
  references.
- Correct every alert expression to use metrics actually emitted by the
  gateway or platform exporters.
- Add an external black-box probe from outside the gateway host. Host-local
  Prometheus alone cannot report that the entire host disappeared.
- Alert separately for:
  - liveness down;
  - readiness down beyond the reconnect objective;
  - repeated restarts or reconnect flapping;
  - stale router traffic/keepalive;
  - queue drops or sustained backlog;
  - disk, memory, CPU, or file-descriptor exhaustion;
  - backup failure and stale backups;
  - certificate expiration when a TLS proxy is used.
- Route a test alert to the real operator destination without committing SMTP
  or notification credentials.
- Add dashboards for availability, router state, recovery duration, traffic,
  resources, and backup age.
- Write a short runbook link into each actionable alert.

## Workstream 5: state, backup, and restore

- Preserve the immediate atomic router-password write and add failure metrics.
- Make mudlist and channel snapshot writes atomic.
- Implement the configured periodic save interval or remove the inactive
  setting.
- Decide whether configuration-managed `backup_enabled` and `backup_count`
  should be implemented in-process. Prefer a documented external backup job
  when operational separation is available.
- Back up the complete state directory with restrictive permissions and
  encryption appropriate to the router credential.
- Define retention, off-host storage, backup-age monitoring, and restore
  ownership.
- Test restore onto a clean host without displaying the router password.
- Verify that a restored gateway reuses its credential and reaches `READY`.
- Record recovery point and recovery time from the exercise.
- Document rollback rules so application rollback does not roll back the router
  password independently from current state.

## Workstream 6: automated and live validation

### 6.1 Restore the quality gate

- Fix connection-manager, connection-pool, mock-router, fixed-port, and
  asynchronous teardown failures.
- Replace stale tests that assert retired behavior.
- Add unit tests for effective settings, keepalive timing, dead-peer detection,
  readiness transitions, watchdog behavior, and task supervision.
- Add integration fault injection for process and network failures.
- Keep the configured repository-wide coverage threshold green in CI.
- Move the intended workflow under `.github/workflows/` and retain hosted
  results for the tested revision.

### 6.2 Recovery drills

Automate or retain a redacted transcript for each drill:

1. Send `SIGKILL` to the gateway process.
2. Kill the container.
3. Restart the Docker daemon.
4. Reboot the host.
5. Refuse the router connection.
6. Drop router packets without closing TCP.
7. Restore network access.
8. Exhaust disk space in an isolated test environment.
9. Corrupt a non-credential state snapshot and prove safe recovery.
10. Restore state and secrets onto a clean host.

For every drill, capture failure time, detection time, restart/reconnect time,
`READY` time, alerts delivered, credential reuse, state outcome, and operator
action required.

Disruptive protocol testing must use a mock router or the designated `*wir`
test router, not the production router.

### 6.3 Soak test

- Run at least 24 hours of representative traffic with scheduled reconnects
  before initial production acceptance.
- Extend to 72 hours before publishing a stronger availability claim.
- Include TCP and WebSocket clients, periodic presence synchronization, core I3
  services, fallback-router attempts, and state saves.
- Fail the soak on unbounded resource growth, orphan tasks, duplicate delivery,
  permanent reconnect loss, credential changes, or unexplained queue loss.
- Publish the revision, environment, workload, fault schedule, and results in
  `../VALIDATION.md`.

## Workstream 7: optional multi-host failover

This phase is required only when a complete host failure must recover
automatically.

- Choose an active-passive topology.
- Add leader election and fencing so only one gateway can claim the MUD
  identity.
- Replicate the router password and required configuration securely, with
  auditable access and no split-brain window.
- Decide how local MUD clients find the active gateway: virtual IP, service
  discovery, or controlled DNS failover.
- Keep monitoring and alert delivery outside both gateway hosts.
- Exercise primary-host power loss, network partition, standby promotion,
  primary recovery, and failback.
- Confirm with the router operator that failover behavior is protocol-safe.
- Do not call the design highly available until the partition and fencing tests
  pass.

## Delivery sequence

| Phase | Deliverable | Depends on |
|---|---|---|
| 0 | Record supervisor choice, health contracts, keepalive strategy, and availability targets | None |
| 1 | Config-driven connection lifecycle and dead-peer detection | Phase 0 |
| 2 | Correct health endpoints, task supervision, watchdog, and metrics | Phase 1 |
| 3 | Hardened canonical deployment with boot and unhealthy-process recovery | Phase 2 |
| 4 | Working external monitoring, alerts, dashboards, and runbooks | Phases 2-3 |
| 5 | Atomic state, backup job, and proven clean-host restore | Phase 3 |
| 6 | Green CI, recovery drills, and 24/72-hour soak evidence | Phases 1-5 |
| 7 | Fenced active-passive host failover, if required | Phase 6 |

Phases 1 and 5 may proceed in parallel after Phase 0. Phase 7 must not delay the
single-host self-healing baseline unless host-level availability is a launch
requirement.

## Production acceptance checklist

- [ ] Effective router resilience settings are validated and logged.
- [ ] A protocol-safe keepalive or documented equivalent detects half-open TCP.
- [ ] Reconnect continues indefinitely with bounded backoff.
- [ ] `/health/live` reflects local ability to make progress.
- [ ] `/health/ready` requires a completed I3 startup negotiation.
- [ ] Critical background tasks are supervised.
- [ ] A stuck or fatally degraded process is replaced automatically.
- [ ] Docker or systemd starts the gateway after a clean host reboot.
- [ ] Persistent state and router identity survive `SIGKILL`, container
      replacement, Docker restart, and host reboot.
- [ ] The production monitoring stack deploys without missing targets or rules.
- [ ] External monitoring detects complete host loss.
- [ ] Every critical alert reaches an operator and links to a runbook.
- [ ] Backup age is monitored and a clean-host restore has passed.
- [ ] The configured full test and coverage gate is green in CI.
- [ ] Controlled router disconnect and black-hole tests pass.
- [ ] A 24-hour soak passes; a 72-hour soak is published before stronger claims.
- [ ] Rollback, credential recovery, and restore procedures are exercised.
- [ ] If multi-host failover is required, fencing and partition tests pass.

## Required documentation updates

As implementation lands:

- update `../DEPLOYMENT.md` with the canonical production install and preflight;
- update `../TROUBLESHOOTING.md` with health, watchdog, reconnect, and restore
  procedures;
- replace incomplete monitoring caveats only after the stack is deployable;
- append dated recovery and soak evidence to `../VALIDATION.md`;
- record user-visible changes in `../CHANGELOG.md`;
- keep this plan and `ROADMAP.md` synchronized until all acceptance items are
  complete.
