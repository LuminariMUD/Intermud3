# I3 routers

This page is a configuration aid, not a live-status monitor. Router operators
can change addresses or policy; verify the primary sources before a new
deployment.

## Published routers

As checked on 2026-07-28, Way of the Force and MUD Standards publish these I3
router endpoints:

| Router | Address | Port | Intended use |
|---|---:|---:|---|
| `*i4` | `204.209.44.3` | `8080` | Production I3 network |
| `*wpr` | `136.144.155.250` | `8080` | Production I3 network |
| `*dalet` | `97.107.133.86` | `8787` | Production I3 network |
| `*Kelly` | `150.101.219.57` | `8080` | Production I3 network |
| `*wir` | `136.144.155.250` | `3004` | Testing new clients and routers |

Sources:

- [Way of the Force I3 network](https://wotf.org/i3/)
- [MUD Standards I3 reference](https://mudstandards.org/intermud/intermud3/)

DNS names, approximate MUD totals, "primary" rankings, and availability
percentages are intentionally omitted because this repository does not operate
or continuously monitor those routers.

## Choosing a router

Use `*wir` for malformed-packet tests, reconnect cycling, load tests, or new
protocol implementations. Coordinate disruptive work with the operator. A
normal established MUD may connect to a production router, but should still
rate-limit requests and preserve the credential returned by `startup-reply`.

The gateway was observed completing startup against `*i4` on 2026-07-28; see
[Validation and interoperability](VALIDATION.md). That observation is not an
uptime guarantee or an endorsement of one operator over another.

## Configuration

Set the router name as well as its endpoint:

```dotenv
I3_ROUTER_NAME=*i4
I3_ROUTER_HOST=204.209.44.3
I3_ROUTER_PORT=8080
```

Equivalent YAML:

```yaml
router:
  primary:
    name: "*i4"
    host: "204.209.44.3"
    port: 8080
    password: 0
```

On first registration, a password of `0` asks the router for a credential. The
gateway stores the returned value in `state/router-password` and reuses it.
Back up and protect that file; deleting it can make the same MUD identity look
like a new registration.

Fallback endpoints can be listed in YAML, but the current runtime assigns
internal names such as `fallback-0` to them. Treat failover as an automated-test
capability until a controlled live failover transcript is published.

## I3 is not IMC2

This gateway speaks I3v3 over MudMode. An IMC2 endpoint or client cannot be used
as a drop-in I3 router connection even if an operator offers bridging services.
Use the protocol and port documented for the network you intend to join.
