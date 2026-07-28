# Intermud3 Gateway documentation

This index separates current product documentation, upstream protocol
reference, and historical planning records. Pages in the first two sections
describe the current repository; archived changelogs are retained as historical
records and are not current capability statements.

## Start here

| Document | Use it for |
|---|---|
| [Project README](../README.md) | Overview, verified status, quick start, and client choices |
| [Validation and interoperability](VALIDATION.md) | Reproducible automated and live-network evidence |
| [API reference](API_REFERENCE.md) | Canonical JSON-RPC transports, methods, events, and errors |
| [Integration guide](INTEGRATION_GUIDE.md) | Connecting a MUD and handling asynchronous I3 traffic |
| [Deployment guide](DEPLOYMENT.md) | Source, Docker, systemd, TLS, secrets, and operations |
| [Troubleshooting](TROUBLESHOOTING.md) | Diagnosis by symptom and observable state |

## Design and operation

| Document | Use it for |
|---|---|
| [Architecture](ARCHITECTURE.md) | Runtime components, data flow, state, and trust boundaries |
| [Local development](LOCAL_DEV_DEPLOY.md) | A compact local setup, including optional ngrok exposure |
| [Performance](PERFORMANCE_TUNING.md) | Running the included benchmarks and tuning real settings |
| [Python project map](python/python_project.md) | Package layout and developer tooling |
| [Router list](gateway_list.md) | Production/test router endpoints and registration rules |

## Project governance

| Document | Use it for |
|---|---|
| [Contributing](CONTRIBUTING.md) | Development workflow and review expectations |
| [Code of Conduct](CODE_OF_CONDUCT.md) | Community standards |
| [Roadmap](ongoing-projects/ROADMAP.md) | Prioritized work that is not yet represented as shipped |
| [Production resilience plan](ongoing-projects/PRODUCTION_RESILIENCE_PLAN.md) | Self-healing, monitoring, recovery, and optional host-failover work |
| [Changelog](CHANGELOG.md) | Current release history |

## Intermud-3 protocol reference

The [protocol reference index](intermud3_docs/README.md) explains how the
historical I3v3 proposal relates to deployed behavior and to this gateway's
implemented service matrix. The original proposal is useful but incomplete in
places; project capability claims come from code and validation evidence, not
from the proposal alone.

## Historical records

The [historical changelogs](previous_changelogs/README.md) and
[project records](projects/README.md) preserve earlier release notes and implementation
plans. Each historical page is labeled accordingly. Dates, estimates, targets,
and test counts in those records describe what was written at the time; use
`VALIDATION.md`, `ongoing-projects/ROADMAP.md`, and the current source tree for
present status.

## Client documentation

- [Python client](../clients/python/README.md)
- [JavaScript/Node.js client](../clients/javascript/README.md)
- [Python examples](../clients/examples/README.md)
- [CircleMUD C reference status](../clients/circlemud/CIRCLEMUD_CLIENT_AUDIT.md)
