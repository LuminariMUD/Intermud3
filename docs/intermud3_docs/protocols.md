# OOB Protocols

Out-of-band (OOB) protocols handle large data transfers and services that require direct mud-to-mud connections, separate from the main router network.

## OOB Connection Flow

### Step 1: Authentication Setup
Originator uses target's auth service to fetch necessary authorization tokens. If authorization is not needed, an `oob-req` packet is sent. This step operates over the in-band network.

### Step 2: TCP Connection
Originator connects to target's OOB port.

### Step 3: Begin Handshake
Originator delivers an `oob-begin` packet containing authorization tokens over the OOB link:

```lpc
({
    "oob-begin",
    originator_mudname,
    auth_type,             // 0 = none, 1 = auth-mud-req
    auth_token             // Session key if authenticated
})
```

### Step 4: Validation
Target mud validates the authorization tokens. If validation fails, target closes the connection.

### Step 5: Acknowledgment
Target returns an `oob-begin` packet (with empty authorization) to signal readiness:

```lpc
({
    "oob-begin",
    target_mudname,
    0,                     // No auth needed for reply
    0                      // No token
})
```

### Step 6: Data Transfer (Originator → Target)
Originator delivers all queued packets to target. Target responds with replies and acknowledgments during this process. Target is not yet allowed to actively send new packets.

### Step 7: Originator Completion
Originator delivers an `oob-end` packet signaling completion:

```lpc
({
    "oob-end",
    originator_mudname
})
```

### Step 8: Data Transfer (Target → Originator)
If target has packets to deliver in its outbound queue for the originator:
1. Target performs deliveries
2. Originator responds with replies and acknowledgments

### Step 9: Target Completion
Target delivers an `oob-end` packet upon completion:

```lpc
({
    "oob-end",
    target_mudname
})
```

### Step 10: Additional Transfers
If originator has further packets (possibly queued during the process), return to Step 6.

### Step 11: Connection Termination
Originator drops the connection.

## Connection Management

### Timeouts
- Target may close connection after 10 minutes of inactivity
- Authentication tokens valid for 10 minutes
- Connection attempts must occur within 10 minutes of `oob-req`

### Connection Reuse
- Single OOB connection can handle multiple packet exchanges
- Connection remains open until explicitly closed
- Reduces overhead for multiple transfers

## OOB Services

Services using OOB connections:
- **Mail**: Large mail messages with attachments
- **News**: News post retrieval and submission
- **File**: File transfers between muds

## Packet Format

OOB packets don't follow standard in-band packet format:
- No TTL field needed (direct connection)
- No routing fields (point-to-point)
- Service-specific formats allowed

## Security Considerations

### Authentication Requirements
- Most OOB services require authentication
- Auth tokens are one-time use
- Tokens expire after successful connection or timeout

### Connection Security
- Direct TCP connections between muds
- No intermediate routing (reduces attack surface)
- Muds validate source before accepting data

## Error Handling

### Connection Failures
- Failed authentication closes connection immediately
- Network errors abort transfer
- Incomplete transfers not acknowledged

### Error Reporting
- Errors during OOB transfer sent via OOB connection
- Connection-level errors may trigger in-band error packets
- Services define specific error responses

## Implementation Notes

### Buffer Management
- Large transfers may require streaming
- Services should handle partial transfers
- Memory limits affect maximum transfer size

### Concurrency
- Multiple OOB connections may be active simultaneously
- Different services can use separate connections
- Proper locking required for shared resources

### Network Considerations
- OOB bypasses router network (reduces router load)
- Direct connections may have firewall implications
- NAT traversal may be required

## Example: Mail Delivery

```
1. MudA → Router → MudB: auth-mud-req
2. MudB → Router → MudA: auth-mud-reply (key: 12345)
3. MudA connects to MudB:OOB_PORT
4. MudA → MudB: oob-begin("MudA", 1, 12345)
5. MudB validates token
6. MudB → MudA: oob-begin("MudB", 0, 0)
7. MudA → MudB: mail packet
8. MudB → MudA: mail-ack
9. MudA → MudB: oob-end("MudA")
10. MudB → MudA: oob-end("MudB")
11. MudA closes connection
```

## Future Considerations

- UDP-based OOB services (currently none defined)
- Encrypted OOB connections
- Compression for large transfers
- Streaming protocols for very large files