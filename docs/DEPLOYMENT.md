# Deployment guide

Intermud3 Gateway is an asyncio service with one outbound TCP connection to an
I3 router and two optional local API listeners. A production deployment should
protect three things:

1. the local JSON-RPC API;
2. API keys and the gateway secret;
3. the router password persisted under `state/`.

## Supported runtime

- Python 3.12 or newer
- Linux is the primary service/container target
- outbound TCP to the selected I3 router
- local ports 8080 (HTTP/WebSocket) and, when enabled, 8081 (TCP)

No inbound connection from an I3 router is required for core in-band services.

## Configuration model

Configuration is loaded in this order:

1. `-e/--env-file` is loaded with python-dotenv;
2. `-c/--config` YAML is read;
3. scalar YAML values of the exact form `${NAME:default}` are expanded;
4. the result is validated by `src.config.models.Settings`;
5. `--debug` and `--log-level` apply CLI overrides.

Validate without opening sockets:

```bash
python -m src --config config/config.yaml --env-file .env --dry-run
```

### Required identity and secrets

For the checked-in YAML:

```dotenv
MUD_NAME=YourMUD
MUD_PORT=4000
MUD_ADMIN_EMAIL=admin@yourmud.example

I3_ROUTER_NAME=*i4
I3_ROUTER_HOST=204.209.44.3
I3_ROUTER_PORT=8080

I3_GATEWAY_SECRET=generate-a-strong-random-value
API_KEY_LUMINARI=generate-a-separate-strong-random-value
```

Generate secrets without copying them into shell history:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Run that command separately for each value, then place the results in a
root/service-user-readable environment file.

`API_KEY_LUMINARI` is the variable referenced by the primary API-key entry in
the checked-in `config/config.yaml`; its name does not force the MUD name to be
LuminariMUD. Rename the YAML entry if a deployment-specific variable name is
preferred.

The checked-in demo/admin values are examples, not deployment credentials.

### Environment-template caveats

`.env.example` contains several legacy names that the current YAML does not
reference. Environment variables affect settings only where
`config/config.yaml` contains the matching `${NAME:default}` expression.

| Legacy/template name | Current behavior |
|---|---|
| `API_KEY_YOURMUD` | Ignored by the checked-in key entry; use `API_KEY_LUMINARI` or edit YAML |
| `API_WS_HOST`, `API_WS_PORT` | Ignored; use `API_HOST`, `API_PORT` |
| `API_TCP_HOST`, `API_TCP_PORT` | Ignored; TCP host/port are literal YAML values until edited |
| `I3_ROUTER_FALLBACK_HOST`, `I3_ROUTER_FALLBACK_PORT` | Ignored; YAML references `I3_FALLBACK_ROUTER_HOST` and `I3_FALLBACK_ROUTER_PORT` |
| `MAX_QUEUE_SIZE`, `HEARTBEAT_INTERVAL` | Ignored by the current YAML/runtime path |
| `CONNECTION_TIMEOUT`, `KEEPALIVE_INTERVAL`, `RECONNECT_DELAY` | Parsed into router settings, but the gateway currently constructs its connection manager with fixed values and a no-op keepalive sender |
| `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_BURST` | Ignored; edit `api.rate_limits.default` in YAML |

Use `python -m src --dry-run` to validate expansion, but remember that a valid
unused environment variable is still unused.

### Router selection

The current default is:

```yaml
router:
  primary:
    name: "*i4"
    host: 204.209.44.3
    port: 8080
    password: 0
```

A first registration sends password zero. The router assigns a credential in
`startup-reply`; the gateway persists it to
`<state.directory>/router-password` and reuses it on restart. Do not set a
different password in the environment after registration unless the router
operator instructs you to.

Use `*wir` at `136.144.155.250:3004` for experimental client testing. See
[router guidance](gateway_list.md).

### API binding

The built-in listener is not a TLS server. For a same-host MUD, prefer:

```yaml
api:
  host: 127.0.0.1
  port: 8080
  tcp:
    enabled: true
    port: 8081
```

If WebSocket clients are remote, keep the backend private and publish it
through a TLS reverse proxy. Disable TCP unless a local integration uses it.

## Source deployment with systemd

The following layout keeps code, configuration, state, and logs owned by a
dedicated account:

```bash
sudo useradd --system --create-home --home-dir /opt/intermud3 \
  --shell /usr/sbin/nologin intermud3
sudo install -d -o intermud3 -g intermud3 \
  /opt/intermud3/app /var/lib/intermud3 /var/log/intermud3
sudo -u intermud3 git clone \
  https://github.com/LuminariMUD/Intermud3.git /opt/intermud3/app
sudo -u intermud3 python3 -m venv /opt/intermud3/app/.venv
sudo -u intermud3 /opt/intermud3/app/.venv/bin/pip install \
  --upgrade pip
sudo -u intermud3 /opt/intermud3/app/.venv/bin/pip install \
  /opt/intermud3/app
```

Create `/etc/intermud3.env` with mode 600:

```bash
sudo install -m 600 -o root -g root /dev/null /etc/intermud3.env
sudoedit /etc/intermud3.env
```

Use a deployment-specific service:

```ini
[Unit]
Description=Intermud3 Gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=intermud3
Group=intermud3
WorkingDirectory=/opt/intermud3/app
EnvironmentFile=/etc/intermud3.env
ExecStart=/opt/intermud3/app/.venv/bin/python -m src \
  --config /opt/intermud3/app/config/config.yaml \
  --env-file /dev/null
Restart=on-failure
RestartSec=10
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/intermud3 /var/log/intermud3

[Install]
WantedBy=multi-user.target
```

Point the YAML state/log paths at the writable directories, for example:

```yaml
state:
  directory: /var/lib/intermud3

logging:
  file: /var/log/intermud3/gateway.log
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now intermud3
sudo systemctl status intermud3
journalctl -u intermud3 -f
```

The repository's `i3-gateway.service` is a concrete example with
`/home/intermud3/Intermud3` paths. Copying it unchanged is correct only when
that exact layout exists.

## Docker

### Build

```bash
docker build --tag i3-gateway:0.4.6-beta .
```

### Compose gateway service

```bash
cp .env.example .env
# Edit .env and add the exact API_KEY_LUMINARI variable used by config.yaml.
docker compose config
docker compose up --build -d i3-gateway
docker compose logs -f i3-gateway
```

The base Compose service:

- exposes WebSocket/HTTP on 8080;
- exposes TCP JSON-RPC on 8081;
- mounts configuration read-only;
- persists logs and state on host bind mounts;
- uses `/health` for container health.

The gateway serves metrics on its HTTP port at `:8080/metrics`. Its `9090:9090`
mapping is not a separate gateway metrics listener. The optional Prometheus
service also uses host port 9090, so remove or change the gateway's unused 9090
mapping before enabling the monitoring profile.

The profile is scaffolding rather than a complete monitored deployment:
`monitoring/prometheus.yml` references Alertmanager, node-exporter, Docker
daemon metrics, and an alerts directory that the base Compose file does not
define, while the Grafana provisioning paths mounted by Compose are not
checked in. Remove those targets or add the corresponding services and
provisioning before treating the stack as healthy.

The production overlay uses host bind locations under `/var/lib/i3-gateway`
and `/var/log/i3-gateway`; create them with ownership compatible with container
UID 1000 before startup.

### Container secrets

The provided Compose files use environment variables and a bind-mounted `.env`
for convenience. For a serious deployment, use the platform's secret mechanism
or a root-owned environment file and ensure secrets do not appear in images,
Compose source, or support bundles.

## Reverse proxy with TLS

Example nginx location for WebSocket:

```nginx
server {
    listen 443 ssl http2;
    server_name i3-api.example.net;

    ssl_certificate /etc/letsencrypt/live/i3-api.example.net/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/i3-api.example.net/privkey.pem;

    location /ws {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }

    location ~ ^/(health|metrics|api/info) {
        allow 127.0.0.1;
        deny all;
        proxy_pass http://127.0.0.1:8080;
    }
}
```

Protect metrics and detailed status rather than exposing them by default.
Apply request/header/time limits at the proxy.

## Health and monitoring

```bash
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8080/health/live
curl --fail http://127.0.0.1:8080/health/ready
curl --fail http://127.0.0.1:8080/metrics
```

Use:

- `/health/live` for process restart decisions;
- `/health/ready` for router-dependent traffic;
- logs for startup replies, list IDs, connection changes, and service errors.

`/health` always reports the local API as healthy when its handler runs. It
does not replace `/health/ready`. Readiness is connection-oriented: it can
return 200 after router TCP connection but before `startup-reply` and fresh
list synchronization, so cold-start smoke tests should also inspect startup
logs or list state.

The current metrics endpoint exposes API WebSocket and active-session gauges.
Do not configure dashboards for packet/latency series that the endpoint does
not emit.

The logging schema contains `max_size` and `backup_count`, but the active
logging setup uses a plain file handler and does not rotate it. Configure
`logrotate`, journald retention, or the container platform's log policy.

## State, backup, and recovery

Persistent files:

| File | Purpose | Sensitivity |
|---|---|---|
| `mudlist.json` | Last synchronized MUD snapshot | low |
| `channels.json` | Last synchronized channel snapshot | low |
| `router-password` | Router-issued identity credential | high |

State snapshots are saved on orderly shutdown. The router password is written
immediately and atomically when assigned.

Backup the state directory with restrictive permissions. Restoring the router
password is important: losing it while reusing the same MUD name can require
router-operator assistance. A stale mud/channel snapshot is less serious
because startup requests a fresh list.

The `save_interval`, `backup_enabled`, and `backup_count` configuration fields
do not currently schedule backups. Use an external backup job.

## Upgrade procedure

1. Back up the state directory and secret configuration.
2. Read [CHANGELOG.md](CHANGELOG.md).
3. Install/build the new revision in a staging location.
4. Run `python -m src --dry-run`.
5. Run the project tests appropriate to the change.
6. Stop the old process cleanly so state is saved.
7. Start the new process.
8. Verify `/health/ready`, mudlist/chanlist counts, and one non-destructive API
   query.
9. Keep the previous image/venv available for rollback; do not roll back the
   newly issued router password separately from state.

## Production checklist

- [ ] Exact MUD name and public metadata reviewed
- [ ] Router endpoint/name pair reviewed
- [ ] Unique gateway secret and API keys installed
- [ ] Example API keys removed or replaced
- [ ] API bound to loopback/private network or protected by TLS proxy
- [ ] TCP API disabled if unused
- [ ] State directory persistent and mode-restricted
- [ ] Router password included in protected backup
- [ ] `/health/ready` used for router-aware monitoring
- [ ] External log rotation/retention configured
- [ ] Firewall allows only required inbound API clients and outbound router TCP
- [ ] Live command smoke test completed
- [ ] Restore and rollback procedures exercised
