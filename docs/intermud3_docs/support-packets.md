# Support Packets

Support packets handle maintenance, connection management, and error reporting within the Intermud-3 network.

## error

Returns error information when conditions arise.

```lpc
({
    "error",
    5,
    originator_mudname,
    0,
    target_mudname,
    target_username,
    error_code,            // Standardized error code
    error_message,         // Human-readable message
    error_packet           // Original packet that caused error (or 0)
})
```

See [Error Codes](reference.md#error-codes) for standardized error codes.

## startup-req-3

Delivered to router when mud first establishes connection.

```lpc
({
    "startup-req-3",
    5,
    originator_mudname,
    0,
    target_mudname,        // Router name
    0,
    
    password,              // (int) 0 for new muds
    old_mudlist_id,        // (int) Current mudlist version
    old_chanlist_id,       // (int) Current channel list version
    
    // Mud information
    player_port,           // (int) Player connection port
    imud_tcp_port,         // (int) OOB TCP port
    imud_udp_port,         // (int) OOB UDP port  
    mudlib,                // (string) Mudlib name
    base_mudlib,           // (string) Base mudlib
    driver,                // (string) Driver version
    mud_type,              // (string) Mud type (LP, MOO, etc.)
    open_status,           // (string) Current status
    admin_email,           // (string) Admin contact
    services,              // (mapping) Supported services
    other_data             // (mapping) Additional data
})
```

### Protocol Version
The `-3` suffix indicates Protocol Version 3. Routers must support all protocol versions and translate between them.

### Required Fields
All fields are required except:
- Port numbers (may be 0 if not applicable)
- other_data (may be 0)

### open_status Values
Strongly encouraged values:
- `"mudlib development"`
- `"beta testing"`
- `"open for public"`
- `"restricted access"`

### mud_type Examples
- `"LP"`
- `"MOO"`
- `"Diku"`

## startup-reply

Sent by router in response to startup-req or when router configuration changes.

```lpc
({
    "startup-reply",
    5,
    originator_mudname,    // Router
    0,
    target_mudname,
    0,
    router_list,           // (string *) Ordered router list
    password               // (int) Assigned password
})
```

### router_list Format
Array of arrays, each containing:
```lpc
({ router_name, "ip.address port" })
```

Example:
```lpc
({ "*nightmare", "199.199.122.10 9000" })
```

The first router is the mud's preferred router. If different from current connection, mud should reconnect.

## shutdown

Graceful shutdown notification.

```lpc
({
    "shutdown",
    5,
    originator_mudname,
    0,
    target_mudname,        // Router
    0,
    restart_delay          // (int) Seconds until restart
})
```

### restart_delay Values
- `0`: Unknown/indefinite
- `1`: Immediate restart
- `< 300`: Router waits normally
- `> 300`: Mud marked down immediately
- `> 604800` (7 days): Mud deleted from Intermud

## mudlist

Updates mud's list of all muds on the network.

```lpc
({
    "mudlist",
    5,
    originator_mudname,    // Router
    0,
    target_mudname,
    0,
    mudlist_id,            // (int) List version
    info_mapping           // (mapping) Mud information
})
```

### info_mapping Format
Keys are mud names, values are arrays:
```lpc
({
    state,                 // (int) Connection state
    ip_addr,               // (string) IP address
    player_port,           // (int) Player port
    imud_tcp_port,         // (int) OOB TCP port
    imud_udp_port,         // (int) OOB UDP port
    mudlib,                // (string) Mudlib
    base_mudlib,           // (string) Base mudlib
    driver,                // (string) Driver
    mud_type,              // (string) Type
    open_status,           // (string) Status
    admin_email,           // (string) Admin email
    services,              // (mapping) Services
    other_data             // (mapping) Other data
})
```

Value of `0` indicates mud has been deleted.

### state Values
- `-1`: Mud is up
- `0`: Mud is down
- `n`: Mud will be down for n seconds

## oob-req

Request to establish OOB connection (when auth service not available).

```lpc
({
    "oob-req",
    5,
    originator_mudname,
    0,
    target_mudname,
    0
})
```

Connection must be made within 10 minutes.

## oob-begin

Used over OOB link to specify authorization.

```lpc
({
    "oob-begin",
    originator_mudname,
    auth_type,             // 0 = none, 1 = auth-mud-req
    auth_token             // Session key if auth_type = 1
})
```

Note: Does not follow standard packet format (OOB packet).

## oob-end

Signals completion of OOB packet delivery.

```lpc
({
    "oob-end",
    mudname                // Mud completing delivery
})
```

Note: Does not follow standard packet format (OOB packet).

## Notes

- Muds should remember mudlist_id and chanlist_id across reconnections
- Passwords are randomly generated by routers for new muds
- Router list order determines failover sequence
- Support packets are critical for network maintenance and stability