# Contributing

Contributions to Intermud3 Gateway are welcome. The project combines a
network-facing protocol implementation with two local JSON-RPC transports, so
changes should be small enough to review and accompanied by evidence at the
appropriate layer.

## Development setup

Python 3.12 or newer is required.

```bash
git clone https://github.com/LuminariMUD/Intermud3.git
cd Intermud3
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Validate configuration without opening network sockets:

```bash
cp .env.example .env
python -m src --dry-run
```

The example configuration includes placeholder API credentials. Replace them
before starting a shared or internet-reachable instance. The primary checked-in
API entry reads `API_KEY_LUMINARI`; `API_KEY_YOURMUD` in `.env.example` is not
consumed unless the YAML is changed to reference it.

## Checks

Run focused tests while developing, then the configured gate:

```bash
python -m pytest tests/regression -q -o addopts=''
python -m pytest tests/unit tests/services -q -o addopts=''
pytest
ruff check src tests
black --check src tests
mypy src
```

`-o addopts=''` deliberately bypasses repository-wide coverage options for a
focused run. It must not be presented as the full quality gate.

The repository also includes Make targets, but the direct commands above show
exactly which tool is being invoked. At the time of writing, `.github/ci.yml`
contains the intended GitHub Actions jobs but is not under
`.github/workflows/`; do not claim a green hosted-CI run without a link to an
actual check.

## Testing expectations

- Codec or framing changes need round-trip, fragmented-input, malformed-input,
  and size-boundary cases.
- Packet changes need exact serialized array-shape assertions.
- Service changes need request, reply, error, and unsupported-peer behavior.
- API changes need both WebSocket and newline-delimited TCP coverage where the
  transports differ.
- Router lifecycle changes need deterministic mock-router tests. Use the
  designated test router for disruptive live work.
- A live observation must identify the date, commit, router, command, and
  redactions. Do not convert it into a timeless benchmark.

The current test inventory and known gate status are recorded in
[Testing](projects/TESTING.md).

## Code and documentation style

- Use type annotations for new Python APIs.
- Keep async work non-blocking and make ownership of background tasks explicit.
- Treat router packets and local API input as untrusted.
- Never commit API keys, router passwords, player credentials, private
  messages, state snapshots, logs, or packet captures containing them.
- Update the API reference, service matrix, configuration caveats, and
  validation matrix when behavior changes.
- Avoid unsupported adjectives such as "complete," "production-ready," or
  "battle-tested." State what was exercised and what remains unverified.

## Pull requests

Explain the problem, the behavior change, the checks run, and any known
limitations. Keep unrelated cleanup out of the same change. If a test is
skipped or failing, name it and explain why; a test count without a result is
not proof.

All contributors must follow the [Code of Conduct](CODE_OF_CONDUCT.md).
