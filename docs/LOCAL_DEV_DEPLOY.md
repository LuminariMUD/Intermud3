# Local development

These steps work on Linux and WSL2 and keep the gateway API local by default.

## Manual setup

```bash
git clone https://github.com/LuminariMUD/Intermud3.git
cd Intermud3

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

cp .env.example .env
```

Edit `.env` and replace example values. The checked-in YAML expects
`API_KEY_LUMINARI`, so add that exact variable even though the older environment
template also contains `API_KEY_YOURMUD`:

```dotenv
MUD_NAME=YourDevelopmentMUD
MUD_PORT=4000
MUD_ADMIN_EMAIL=admin@yourmud.example

I3_ROUTER_NAME=*wir
I3_ROUTER_HOST=136.144.155.250
I3_ROUTER_PORT=3004

I3_GATEWAY_SECRET=replace-me
API_KEY_LUMINARI=replace-me-too

API_HOST=127.0.0.1
API_PORT=8080
```

`*wir` is the designated router for experimental client work. Use the
production `*i4` endpoint only for an established MUD identity and ordinary
interoperability use.

Validate and run:

```bash
python -m src --dry-run
python -m src --log-level DEBUG
```

In another terminal:

```bash
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8080/health/ready
curl http://127.0.0.1:8080/api/info
```

The WebSocket URL is `ws://127.0.0.1:8080/ws`; the `/ws` path is required.

## Connect a local MUD

Prefer TCP for a C/CircleMUD-style process:

```text
host: 127.0.0.1
port: 8081
framing: one JSON object plus newline
first method: authenticate
```

Prefer WebSocket for Python, JavaScript, or browser-capable development:

```text
ws://127.0.0.1:8080/ws
```

Follow [API.md](API.md) for the first request and test one local `ping` before
sending network traffic.

## Development helper script

`scripts/deploy-local.sh` can create a `venv`, update dependencies, start the
gateway in the background, and optionally start configured ngrok tunnels:

```bash
./scripts/deploy-local.sh
./scripts/deploy-local.sh --status
./scripts/deploy-local.sh --stop
```

The script is convenience automation, not a service manager. It checks and
clears configured ports before startup and may terminate an existing process
using them. Review its output and use the manual path when those ports belong
to another development service.

It writes:

- gateway log: `logs/gateway.log`
- ngrok log: `logs/ngrok.log`
- PID files: `.pids/`

## Optional ngrok exposure

ngrok is not needed for the I3 router connection; that connection is outbound.
Use a tunnel only when a remote MUD must reach your local JSON-RPC API.

The checked-in `ngrok.yml` defines:

- HTTP/WebSocket tunnel to local port 8080;
- raw TCP tunnel to local port 8081;
- local inspector on port 4042.

Set:

```dotenv
NGROK_AUTHTOKEN=...
NGROK_DOMAIN=your-reserved-domain.example
NGROK_INSPECTOR_PORT=4042
```

Then:

```bash
ngrok start --all --config ngrok.yml
```

Treat a public tunnel as internet exposure:

- keep API authentication enabled;
- use unique short-lived development keys;
- never use demo keys;
- close the tunnel when testing finishes;
- do not expose `/metrics` or logs unnecessarily;
- prefer the HTTPS/WSS ngrok endpoint over plaintext.

## Run checks

```bash
python -m pytest --collect-only -q -o addopts=''
pytest
ruff check src tests
black --check src tests
mypy src
npm --prefix clients/javascript run lint
```

The configured `pytest` command includes coverage and an 80% threshold. Use
`-o addopts=''` only for focused debugging when you intentionally do not want
the repository-wide coverage gate.

## Reset development state

The state directory contains the router password for the configured MUD name.
Do not delete `state/router-password` merely to get a “clean” run. A router may
reject the same identity when its issued password is lost.

Safe disposable state requires a disposable MUD name registered on the test
router. Keep production and test identities in separate state directories.

## Common WSL2 notes

- A Windows client can normally reach a WSL2 listener bound to `127.0.0.1` via
  Windows localhost forwarding; if not, use the current WSL IP and bind
  deliberately to `0.0.0.0`.
- Windows firewall rules affect access from outside the host.
- CRLF characters in hand-edited dotenv values can break boolean validation.
  If an error shows a value such as `true\r`, convert the file to LF endings.
- `localhost` inside a container is the container, not the WSL host. Put the
  MUD and gateway on the same Compose network or use an explicit host route.

