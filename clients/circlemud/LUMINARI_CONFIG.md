# LuminariMUD I3 Gateway Configuration

## Gateway Connection Details

### TCP Connection (Recommended for CircleMUD/tbaMUD)
- **Host**: localhost (or gateway server IP)
- **Port**: 8081
- **Protocol**: JSON-RPC 2.0 over TCP (line-delimited)

### Authentication
- **API Key**: `luminari-i3-gateway-2025`
- **MUD Name**: LuminariMUD
- **Permissions**: Full access (all I3 services)

## Configuration for your MUD

Add this to your MUD's I3 configuration file:

```c
// For C-based MUDs (Circle/tba)
#define I3_GATEWAY_HOST "localhost"
#define I3_GATEWAY_PORT 8081
#define I3_API_KEY "luminari-i3-gateway-2025"
```

## Authentication Sequence

Your MUD should:

1. Connect to TCP port 8081
2. Receive welcome message (JSON)
3. Send authentication:
```json
{"jsonrpc":"2.0","method":"authenticate","params":{"api_key":"luminari-i3-gateway-2025"},"id":1}
```
4. Receive authentication confirmation:
```json
{"jsonrpc":"2.0","id":1,"result":{"status":"authenticated","mud_name":"LuminariMUD","session_id":"..."}}
```

## Available Methods (once implemented)

After authentication, you can call:
- `tell` - Send tell to player on another MUD
- `channel_send` - Send message to I3 channel
- `channel_list` - Get list of available channels
- `who` - Get who list from another MUD
- `finger` - Get player info from another MUD
- `locate` - Find a player across all MUDs
- `mudlist` - Get list of all connected MUDs

## Example Tell Message

```json
{
  "jsonrpc": "2.0",
  "method": "tell",
  "params": {
    "from_user": "PlayerName",
    "to_user": "TargetPlayer",
    "to_mud": "TargetMUD",
    "message": "Hello from LuminariMUD!"
  },
  "id": 2
}
```

## Notes

- All messages must end with a newline character (\n)
- The gateway handles all I3 protocol complexity
- Your MUD just needs to send/receive JSON-RPC messages
- The session persists until disconnection
- Rate limit: 500 requests per minute (override configured)