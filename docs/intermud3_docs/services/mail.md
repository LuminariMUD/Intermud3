# Service: mail

Propagate mail items between muds.

## Network Type
Out-of-band (OOB) - Uses direct TCP connections

## Authentication
This service employs the auth service for authentication.

## Mail Packet

Delivered over the OOB network to the target mud's out-of-band TCP port:

```lpc
({
    "mail",
    id,                    // (int) Unique mail ID
    orig_user,             // (string) Originating user
    to_list,               // (mapping) To recipients
    cc_list,               // (mapping) CC recipients
    bcc_list,              // (string *) BCC recipients
    send_time,             // (int) Unix timestamp
    subject,               // (string) Mail subject
    contents               // (string) Mail body
})
```

## Recipient List Format

`to_list` and `cc_list` are mappings with the following format:

```lpc
([
    "MUD-A": ({ "user-1", "user-2" }),
    "MUD-B": ({ "user-1", "user-2" })
])
```

`bcc_list` is an array of users at the target mud only.

## Mail Acknowledgment: mail-ack

```lpc
({
    "mail-ack",
    ack_list               // (mapping) Acknowledgments
})
```

`ack_list` is a mapping where:
- Keys: Mail IDs that have been acknowledged
- Values: Arrays of delivery failures

## Example

### Sending Mail

```lpc
({
    "mail",
    12345,
    "johndoe",
    ([ 
        "TargetMud": ({ "janedoe", "bobsmith" }),
        "OtherMud": ({ "alice" })
    ]),
    ([ "ThirdMud": ({ "charlie" }) ]),
    ({ "secretuser" }),
    1642334400,
    "Meeting Tomorrow",
    "Don't forget about our meeting at 3pm tomorrow."
})
```

### Acknowledgment

```lpc
({
    "mail-ack",
    ([
        12345: ({ }),                    // Successful delivery
        12346: ({ "unknown-user" })      // Failed for one user
    ])
})
```

## Protocol Flow

1. Originator requests auth token via in-band network
2. Originator connects to target's OOB port
3. Originator authenticates using auth token
4. Originator sends mail packet
5. Target processes mail and sends mail-ack
6. Connection closes or continues for more mail

## Error Handling

- Errors must be sent via the OOB network
- Failed deliveries are reported in the ack_list
- Authentication failures close the connection

## Notes

- Mail is normally delivered via OOB TCP port
- SMTP interface may be available as an extended service
- Multiple mail items can be sent over a single connection