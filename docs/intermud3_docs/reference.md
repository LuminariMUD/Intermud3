# Reference

## Error Codes

### Router Error Codes

Standard error codes returned by routers:

| Code | Description |
|------|-------------|
| `unk-dst` | Unknown destination mud |
| `not-imp` | Feature not yet implemented |
| `unk-type` | Unknown packet type (also sent by muds) |
| `unk-src` | Unknown source of packet (unregistered mud) |
| `bad-pkt` | Bad packet format (also sent by muds) |
| `bad-proto` | Protocol violation (packet used incorrectly) |
| `not-allowed` | Operation not allowed (e.g., channel bans) |

### Mud Error Codes

Standard error codes that a mud may return:

| Code | Description |
|------|-------------|
| `unk-type` | Unknown packet type (also sent by router) |
| `unk-user` | Unknown target user |
| `unk-channel` | Unknown channel name |
| `bad-pkt` | Bad packet format (also sent by router) |

## Packet Types

### Communication Services

| Packet | Description |
|--------|-------------|
| `tell` | Send a message to a remote user |
| `emoteto` | Send an emote to a remote user |

### Information Services

| Packet | Description |
|--------|-------------|
| `who-req` | Request a list of users on a remote mud |
| `who-reply` | Reply with a list of users |
| `finger-req` | Request finger information for a remote user |
| `finger-reply` | Reply with finger information |
| `locate-req` | Request the location of a user |
| `locate-reply` | Reply with the location of a user |

### Channel Services

| Packet | Description |
|--------|-------------|
| `chanlist-reply` | Reply with/update the list of available channels |
| `channel-m` | Send a message over a channel |
| `channel-e` | Send an emote over a channel |
| `channel-t` | Send a targeted emote over a channel |
| `channel-add` | Register a new channel |
| `channel-remove` | Remove a channel from databases |
| `channel-admin` | Administrate channel participants |
| `chan-filter-req` | Filter a channel message |
| `chan-filter-reply` | Return filtered channel messages |
| `chan-who-req` | Request who list for a channel |
| `chan-who-reply` | Return requested channel who list |
| `channel-listen` | Tune mud into or out of a channel |
| `chan-user-req` | Request channel user's info |
| `chan-user-reply` | Reply with channel user's info |

### Data Transfer Services

| Packet | Description |
|--------|-------------|
| `news-read-req` | Retrieve a news post from OOB server |
| `news-post-req` | Post news to OOB server |
| `news-grplist-req` | Request list of newsgroups |
| `mail` | Deliver an item of mail |
| `mail-ack` | Acknowledge mail receipt |
| `file-list-req` | Request file list from remote mud |
| `file-list-reply` | Reply with file list |
| `file-put` | Send file to remote mud |
| `file-put-ack` | Acknowledge file-put |
| `file-get-req` | Get file from remote mud |
| `file-get-reply` | Reply with requested file |

### System Services

| Packet | Description |
|--------|-------------|
| `auth-mud-req` | Request mud-level authorization token |
| `auth-mud-reply` | Reply with mud-level authorization token |
| `ucache-update` | Update cached user information |

### Support Packets

| Packet | Description |
|--------|-------------|
| `error` | Provide error information |
| `startup-req-3` | Provide startup information to router |
| `startup-reply` | Reply with/update startup information |
| `shutdown` | Gracefully indicate shutdown |
| `mudlist` | Reply with/update list of available muds |
| `oob-req` | Request setup for OOB connection |
| `oob-begin` | Begin OOB communication |
| `oob-end` | End one side of OOB process |

## Compressed Mode

**Note**: Specification to be filled in with specifics.

Generally, many fields will be replaced with numbers rather than full strings. Some fields can be paired using combined keys. For example:
- `originator_mudname` can be omitted (inferred from TCP session at router)
- Request/reply pairs can use request keys rather than usernames
- User association maintained on originating mud with request key

## Other Drivers/Mudlibs

### Reference Implementations
Two reference implementations exist for the mudlib side of the protocol. These can be ported/used to create implementations for:
- Alternate mudlibs
- MudOS pre-v21 drivers

### Driver Compatibility

#### TCP without MUD-mode
Drivers with TCP but not MUD-mode need to parse incoming transmissions. MUD-mode effectively combines `save_variable()` with standard TCP socket.

#### Without TCP Sockets
Drivers without TCP sockets require a gateway to:
- Hook into the router network
- Gateway protocol between MUD-mode TCP and UDP

### Non-LP Muds
Gateways can be used for non-LP based muds:
- MOO
- MUCK
- Diku
- Others

### Protocol Evolution
Router network protocol can evolve independently of mud protocol, potentially moving away from MUD-mode style communication.