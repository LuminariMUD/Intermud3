# Intermud-3 Services

There are eleven services covered by the Intermud-3 protocol:

## Communication Services
- [tell](tell.md) - Send a message to a user on a remote mud
- [emoteto](emoteto.md) - Send an emote to a user on a remote mud
- [channel](channel.md) - Send a string/emote/soul between muds

## Information Services
- [who](who.md) - Get a list of users on a remote mud
- [finger](finger.md) - Get information about a particular user on a remote mud
- [locate](locate.md) - Locate a player on remote mud(s)

## Data Transfer Services
- [news](news.md) - Propagate news posts between muds
- [mail](mail.md) - Propagate mail items between muds  
- [file](file.md) - Transfer files between muds

## System Services
- [auth](auth.md) - Perform mud or user authentication
- [ucache](ucache.md) - Cache information about remote users

## Service Availability

Services are declared in the `startup-req-3` packet's services mapping. Standard services have a value of 1:

```lpc
([
    "tell": 1,
    "emoteto": 1,
    "who": 1,
    "finger": 1,
    "locate": 1,
    "channel": 1,
    "news": 1,
    "mail": 1,
    "file": 1,
    "auth": 1,
    "ucache": 1
])
```

## Extended Services

Non-standard services may also be specified with service-specific information:

- **smtp**: port-number - SMTP mail interface port
- **ftp**: port-number - FTP service port
- **nntp**: port-number - NNTP news server port
- **http**: port-number - WWW server (httpd) port
- **rcp**: port-number - Remote Creator server port
- **amcp**: version-string - AMCP support with version

## Network Usage

Services use different network types:
- **In-band**: Fast response messages (tell, emoteto, who, finger, locate, channel, auth, ucache)
- **Out-of-band (OOB)**: Large data transfers (news, mail, file)