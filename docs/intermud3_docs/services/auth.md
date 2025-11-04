# Service: auth

Perform mud-level authentication for OOB communications.

## Purpose
Authentication is used to verify that an incoming OOB connection request actually originates from the mud that claims to be making the request. In-band communication is always authenticated at mud-level through the router network.

## Network Type
In-band for token exchange, OOB for authenticated services

## Authentication Flow

### Step 1: Request Authentication Token

Before making an OOB connection, the originator sends this packet over the in-band network:

```lpc
({
    "auth-mud-req",
    5,
    originator_mudname,
    0,
    target_mudname,
    0
})
```

### Step 2: Receive Authentication Token

The target mud:
1. Generates a unique integer key
2. Associates the key with the originating mud
3. Returns the key over the in-band network:

```lpc
({
    "auth-mud-reply",
    5,
    originator_mudname,
    0,
    target_mudname,
    0,
    session_key            // (int) Unique session key
})
```

### Step 3: Use Token for OOB Connection

The originator contacts the target mud through the OOB port using the `session_key` to authenticate.

## Session Key Management

### Validity
- Session keys remain valid for **10 minutes** from receipt of auth-mud-req
- After 10 minutes, the key may be discarded and connections rejected

### Multiple Requests
- If multiple auth-mud-req packets are received before establishing OOB connection:
  - Only the last request and session_key need to be remembered
  - Keys from prior requests may be discarded

### One-Time Use
- After successful OOB connection, the target mud may discard the key
- Keys should be interpreted as one-time use tokens

## OOB Authentication

When establishing an OOB connection, use the oob-begin packet:

```lpc
({
    "oob-begin",
    originator_mudname,
    auth_type,             // 1 for auth-mud-req authentication
    auth_token             // The session_key received
})
```

Auth types:
- `0`: No authentication used
- `1`: auth-mud-req used

## Example Flow

```
1. MudA → Router → MudB: auth-mud-req
2. MudB → Router → MudA: auth-mud-reply (key: 42789)
3. MudA connects to MudB's OOB port
4. MudA → MudB: oob-begin with auth_token=42789
5. MudB validates token and allows connection
6. Authenticated OOB communication proceeds
```

## Security Considerations

- Keys should be cryptographically random
- Keys should be unique per session
- Old keys should be invalidated after use or timeout
- Failed authentication attempts should close the connection immediately

## Notes

- This service is required for secure OOB communications
- Services like mail, news, and file transfers require authentication
- The auth service itself uses the in-band network for token exchange