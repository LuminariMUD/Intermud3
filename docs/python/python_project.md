# Python project map

Intermud3 Gateway is a Python 3.12+ application installed from
`pyproject.toml`. The `src` package is the service; bundled clients are source
examples and are not included as separately published packages.

```text
src/
+-- api/       local JSON-RPC, sessions, events, health, and transports
+-- config/    Pydantic settings and YAML/environment loading
+-- models/    I3 packet and connection models
+-- network/   LPC, MudMode, router connections, and connection pooling
+-- services/  tell, channel, who, finger, locate, and router behavior
+-- state/     persisted network state and presence snapshots
+-- utils/     logging, retry, circuit-breaker, and shutdown utilities
+-- gateway.py composition and lifecycle
+-- __main__.py CLI

clients/
+-- python/      async WebSocket client source
+-- javascript/ CommonJS client and TypeScript declarations
+-- examples/   integration prototypes
+-- circlemud/  C reference integration

tests/
+-- api/
+-- integration/
+-- performance/
+-- regression/
+-- services/
+-- unit/
```

## Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m src --dry-run
python -m src --log-level INFO
```

The package also installs the `i3-gateway` console script. Reinstall the
editable project after a version change or that script can report stale
installed metadata. In environments that contain multiple distributions
exposing a top-level package named `src`, `python -m src --version` can confuse
Click's distribution lookup. Use the version in `pyproject.toml` or the
`python -m src --dry-run` startup record as source-level evidence.

Before publishing to a package index, correct the placeholder project URLs and
author address in `pyproject.toml` and reconcile its MIT declaration with the
repository's Unlicense text. Its `Development Status :: 3 - Alpha` classifier
also differs from the `0.4.6-beta` version label.

## Source of truth

- [Architecture](../ARCHITECTURE.md) explains runtime ownership.
- [API reference](../API_REFERENCE.md) defines the local contract.
- [Testing](../projects/TESTING.md) records current test status.
- [Client documentation](../../README.md#client-status) explains which
  integrations are complete enough for which use.

Do not infer support from a filename alone. In particular, protocol reference
pages cover services the gateway does not implement, configuration models
contain fields not wired into every runtime path, and the bundled clients do
not all mirror the canonical API perfectly.
