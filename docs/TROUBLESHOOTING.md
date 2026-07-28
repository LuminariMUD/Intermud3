# Troubleshooting

Start with the smallest failing boundary:

```text
local MUD/client -> JSON-RPC API -> gateway state -> I3 router -> remote MUD
```

## Collect a safe baseline

```bash
python -m src --dry-run
curl -i http://127.0.0.1:8080/health
curl -i http://127.0.0.1:8080/health/ready
ss -ltnp | grep -E ':8080|:8081'
tail -n 100 logs/i3-gateway.log
```

Redact API keys, `state/router-password`, private messages, player credentials,
and non-public addresses before sharing output.

## Configuration will not load

- Run `python -m src --dry-run` and read the first validation error.
- Check YAML indentation and environment substitutions in
  `config/config.yaml`.
- Ensure the file uses normal LF line endings if an error contains unexpected
  carriage returns.
- Set a non-empty `I3_GATEWAY_SECRET` when gateway authentication is enabled.
- The primary checked-in API key entry reads `API_KEY_LUMINARI`.
  `API_KEY_YOURMUD` from `.env.example` has no effect unless you edit the YAML
  reference.

## Health is green but readiness is not

`/health` reports that the local API process is alive. `/health/ready` requires
an established upstream router session.

Check:

1. `I3_ROUTER_NAME`, host, and port;
2. outbound TCP reachability to that endpoint;
3. startup or LPC parse errors in the log;
4. whether the router rejected an identity or credential;
5. permissions and contents **metadata only** for `state/router-password`.

Do not delete the router-password file as a first diagnostic step. It is the
credential assigned to the configured MUD name.

## The gateway does not reconnect

Look for transitions through `connecting`, `connected`, `error`, and
`disconnected`. Reconnect and fallback code and tests exist, but the current
connection test gate includes failures and a controlled live failover
transcript has not been published. Use `*wir` for disruptive testing and
capture timestamps, selected endpoint, backoff delays, and the final state.

## Mudlist or channel list is empty

Lists arrive after successful startup and may not be immediate. Confirm
readiness, then inspect persisted state without printing message or credential
content:

```bash
jq '{mudlist_id, mud_count: (.muds | length)}' state/mudlist.json
jq 'length' state/channels.json
```

If the files stay empty, search for `mudlist`, `chanlist`, `LPC`, and packet
parse errors. A dated live snapshot is shown in
[Validation and interoperability](VALIDATION.md).

## WebSocket returns 404 or fails its handshake

The WebSocket endpoint is `/ws`, not the HTTP root:

```text
ws://127.0.0.1:8080/ws
```

Use `X-API-Key` during the handshake or send `authenticate` as the first
JSON-RPC request. A normal HTTP client such as `curl` cannot complete a
WebSocket upgrade.

The bundled JavaScript client defaults to a root URL internally, so always pass
the explicit `/ws` URL.

## TCP connects but nothing happens

TCP JSON-RPC listens on port 8081 by default. Every JSON object must be on one
line and terminated with `\n`. The server sends a welcome object first; the
client must authenticate before other methods.

```json
{"jsonrpc":"2.0","id":1,"method":"authenticate","params":{"api_key":"REDACTED"}}
```

Do not send MudMode or LPC data to the local TCP port. MudMode is used only on
the router-facing connection.

## "Not authenticated" or permission problems

- Confirm the key exists in `api.auth.api_keys`.
- Confirm the YAML entry maps it to the expected MUD name.
- Do not include whitespace around an environment-provided key.
- Authentication can use a WebSocket header, a first WebSocket method, or the
  first TCP method.

Permission lists are used by event filtering, but not every monolithic request
handler currently enforces per-method authorization. They must not be treated
as a complete tenant-security boundary.

## A remote query returned only "requested"

`who`, `finger`, and `locate` are asynchronous. The immediate JSON-RPC result
confirms that a packet was sent. Consume the later `who_reply`,
`finger_reply`, or `locate_reply` event.

No reply can also mean the remote MUD is offline, does not advertise the
service, rejects the name, or simply does not answer. Record the target MUD,
request ID, outgoing packet log, and any later `error` event.

## Incoming who/finger/locate answers are empty

The local MUD supplies public player data with `presence_sync`. Snapshots
expire after 30 seconds, so refresh them regularly and send an empty `users`
array when no players are visible. The gateway accepts at most 512 records per
snapshot.

## Channel messages are missing

Verify all three layers:

1. the local client called `channel_join`;
2. the gateway sent `channel-listen`;
3. the session is subscribed to the corresponding channel event.

Channel names are network-defined and case-sensitive in some implementations.
Start with a channel present in `channel_list`; do not assume generic names
such as `chat` exist on every router.

The advanced channel administration/filter/`chan-who` paths are only partial;
see the [service matrix](intermud3_docs/services/README.md).

## Docker monitoring profile fails

The current Compose file maps host port `9090` for both the gateway and
Prometheus. Gateway health and metrics actually share API port 8080. Remove or
change the gateway's unused `9090:9090` mapping before enabling the monitoring
profile.

Also verify that `monitoring/prometheus.yml` points at the gateway's reachable
container address and `/metrics`. The checked-in file also references
Alertmanager, node-exporter, Docker daemon metrics, and alert rules that the
base Compose stack does not provide; remove those jobs or add the missing
services. Grafana provisioning directories mounted by Compose are not
currently checked in.

## Tests fail or hang

Collecting tests is not the same as passing them:

```bash
python -m pytest --collect-only -q -o addopts=''
pytest
```

The current known status is in [Testing](projects/TESTING.md). In particular,
some API end-to-end tests bind fixed port 8080 and use teardown patterns that
are incompatible with the current aiohttp/pytest stack; a running gateway also
causes an immediate bind error. Stop local services before testing and do not
publish a pass count from a collection-only run.

## Reporting an issue

Include:

- commit and Python version;
- operating system or container runtime;
- redacted configuration relevant to the failing boundary;
- exact command and complete error;
- health/readiness status;
- whether the router was mocked, `*wir`, or a production router.

Do not attach the full `.env`, state directory, logs containing private
messages, or router credential.
