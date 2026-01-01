# I3 Router & Gateway List

> **Last Updated**: January 2026
> **Live Status**: https://router.wotf.org/mud/mudlist

This document lists all known active Intermud-3 (I3) routers and gateways for connecting MUDs to the I3 network.

## Active Production Routers

All production routers are interconnected (IRN - Inter-Router Network) and share the same MUD list and channels.

| Router | IP Address | Port | Operator | Notes |
|--------|------------|------|----------|-------|
| **\*i4** | `204.209.44.3` | `8080` | Cratylus | Primary router, recommended for new connections |
| **\*dalet** | `97.107.133.86` | `8787` | Cratylus | Also supports IMC2 clients |
| **\*wpr** | `136.144.155.250` | `8080` | Way of the Force | Hosted in Europe (AMSIX), added Oct 2008 |
| **\*Kelly** | `150.101.219.57` | `8080` | adam@themud.org | Added Feb 2018 |

### Current Network Statistics (approx.)
- **Total registered MUDs**: ~300+
- **Currently online**: ~70-100 at any time
- MUD list is synchronized across all routers

## Test Router

**Do NOT use production routers for testing new client code!**

| Router | IP Address | Port | Purpose |
|--------|------------|------|---------|
| **\*wir** | `136.144.155.250` | `3004` | Testing new I3 clients and routers |

## IMC2 Server

For Diku-derivative MUDs using IMC2 protocol:

| Server | IP Address | Port | Protocol |
|--------|------------|------|----------|
| **Dalet** | `97.107.133.86` | `8787` | IMC2 |

> **Note**: You cannot connect to I3 with an IMC2 client or vice versa. The Dalet server bridges IMC2 clients to the I3 network.

## Connecting a New MUD

### For I3 Protocol (LP MUDs)

1. **Choose a router** - `*i4` at `204.209.44.3:8080` is recommended
2. **Send startup-req-3 packet** with `password = 0` for new MUDs
3. **Router assigns password** via `startup-reply` - **save this password!**
4. **Reconnect using assigned password** on subsequent connections

### Startup Packet Requirements

```lpc
({
    "startup-req-3",
    5,                          // TTL
    "YourMUDName",              // originator_mudname
    0,                          // originator_user (0 for system)
    "*i4",                      // target router name
    0,                          // target_user (0 for router)
    0,                          // password (0 = new MUD)
    0,                          // old_mudlist_id (0 = request full list)
    0,                          // old_chanlist_id (0 = request full list)
    4100,                       // player_port
    0,                          // imud_tcp_port (OOB, 0 if not used)
    0,                          // imud_udp_port (OOB, 0 if not used)
    "YourMudlib",               // mudlib name
    "BaseMudlib",               // base mudlib (e.g., "FluffOS", "LDMud")
    "DriverName",               // driver
    "LP",                       // mud_type (LP, Diku, MOO, etc.)
    "open for public",          // open_status
    "admin@yourmud.com",        // admin_email (strongly recommended!)
    ([ "tell": 1, "who": 1 ]),  // services mapping
    0                           // other_data
})
```

### For IMC2 Protocol (Diku MUDs)

1. Connect to **Dalet** at `97.107.133.86:8787`
2. Use IMC2 Freedom client or equivalent
3. Follow IMC2 protocol handshake

## Recommended Router Configuration

For production MUDs, configure multiple routers for failover:

```yaml
# Primary router
router:
  primary:
    name: "*i4"
    host: 204.209.44.3
    port: 8080

  # Fallback routers (in priority order)
  fallback:
    - name: "*wpr"
      host: 136.144.155.250
      port: 8080
    - name: "*dalet"
      host: 97.107.133.86
      port: 8787
    - name: "*Kelly"
      host: 150.101.219.57
      port: 8080
```

## Password Management

- **New MUDs**: Send `password = 0` in startup-req-3
- **Router Response**: Assigns a new password in startup-reply
- **Persistence**: You MUST save this password and use it for all future connections
- **Password Mismatch**: Router will reject connection if password doesn't match

## Getting Help

### Support Channels

| Resource | URL |
|----------|-----|
| LPMuds.net Forum | http://lpmuds.net/forum/ (post on Intermud topic) |
| I3 Information | https://mud.wotf.org/i3/ |
| Live Router Status | https://router.wotf.org/mud/mudlist |
| Protocol Specification | http://wl.mud.de/mud/doc/misc/intermud3.html |

### Router Administrators

- **Cratylus** - Operates *i4 and *dalet (primary network admin)
- **Way of the Force** - Operates *wpr and *wir (test router)
- **adam@themud.org** - Operates *Kelly

## Historical Routers (Deprecated)

These routers are no longer operational:

| Router | Status | Notes |
|--------|--------|-------|
| **\*yatmim** | Deprecated | Replaced by *i4 |
| **\*gjs** | Offline | Original intermud.org router, permanently failed |
| **\*adsr** | Offline | No longer available |

## Protocol Notes

### MudMode Connection

I3 uses "MudMode" binary protocol over TCP:
- 4-byte big-endian length prefix
- LPC-encoded data payload
- Persistent TCP connection maintained

### Keepalive

- Routers expect activity to maintain connection
- Graceful shutdown: send `shutdown` packet
- Ungraceful disconnect: router waits 5 minutes before marking MUD down
- MUD removed after 7 days of being down

### Router Failover

If your primary router is down:
1. Router list is provided in `startup-reply`
2. First router in list is preferred
3. Connect to next available router in list
4. Same MUD list and channels available on all routers

## Quick Reference

### Test Connection (using this gateway)

```bash
# Local development
I3_GATEWAY_URL=ws://localhost:8080
I3_ROUTER_HOST=204.209.44.3
I3_ROUTER_PORT=8080

# Check health
curl http://localhost:8080/health
```

### Verify Router Reachability

```bash
# Test TCP connection to *i4
nc -zv 204.209.44.3 8080

# Test TCP connection to *wpr
nc -zv 136.144.155.250 8080

# Test TCP connection to *dalet
nc -zv 97.107.133.86 8787
```

---

## Sources

- [LPMuds.net Intermud](http://lpmuds.net/intermud.html)
- [Way of the Force I3](https://mud.wotf.org/i3/)
- [IRN Specification v1](https://wotf.org/i3/irn/v1/)
- [Intermud-3 Specification](http://wl.mud.de/mud/doc/misc/intermud3.html)
- [MUDs Wiki - InterMUD](https://muds.fandom.com/wiki/InterMUD)
- [Router Status Monitor](https://router.wotf.org/mud/mudlist)
