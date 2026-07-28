# I3 service reference and gateway matrix

The protocol pages in this directory cover more of I3 than this gateway
implements. "Documented" and "advertised at startup" are not synonyms.

## Current gateway scope

| Service | Router packets | Gateway status |
|---|---|---|
| [tell](tell.md) / [emoteto](emoteto.md) | `tell`, `emoteto` | Implemented by the tell service; local receive/send events and regressions exist |
| [channel](channel.md) | `channel-m`, `channel-e`, listen/list traffic; partial `channel-t`/control paths | Core message, emote, listen, and chanlist paths implemented; targeted emote, admin, filter, and chan-who behavior is partial |
| [who](who.md) | `who-req`, `who-reply` | Implemented; remote requests can be answered from fresh `presence_sync` state |
| [finger](finger.md) | `finger-req`, `finger-reply` | Implemented; reply fields come from the public presence snapshot |
| [locate](locate.md) | `locate-req`, `locate-reply` | Implemented; local match and remote reply paths exist |
| [auth](auth.md) | `auth-mud-*` | Protocol reference only; no registered gateway service |
| [ucache](ucache.md) | `ucache-update` and related packets | Protocol reference only; no registered gateway service |
| [mail](mail.md) | OOB mail packets | Protocol reference only; no OOB transport/handler |
| [news](news.md) | OOB news packets | Protocol reference only; no OOB transport/handler |
| [file](file.md) | OOB file packets | Protocol reference only; no OOB transport/handler |

The startup builder currently advertises enabled `tell`, `channel`, `who`,
`finger`, and `locate` services. `emoteto` is handled by the tell service rather
than advertised as a separate entry. Optional mail/news/file settings can make
the startup packet advertise those names even though handlers do not exist, so
leave those settings disabled.

Configuration models also contain auth, ucache, chanlist, and chan-who flags
that the current startup builder does not advertise independently. Presence of
a config field is not evidence of runtime support.

## Evidence level

Core service packet paths have automated tests and regressions. The
2026-07-28 live snapshot proves router startup and real list decoding, while a
published end-to-end live transcript for each message/query service remains an
open acceptance item. See [Validation](../../VALIDATION.md).

## Network types

- Tell, channel, who, finger, locate, auth, and ucache are described as
  in-band services carried through I3 routers.
- Mail, news, and file are historical OOB services using separate direct
  connections.

This gateway currently implements only the in-band core listed as implemented
above.
