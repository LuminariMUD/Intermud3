# Intermud-3 overview and provenance

Intermud-3 (I3) is a router-mediated protocol for communication among MUDs. It
originated in the mid-1990s LP/MudOS community, but deployed implementations
now include other drivers and non-LPC gateways such as this project.

The historical proposal is valuable for packet vocabulary, service intent, and
network architecture. It is not a complete modern conformance suite:

- some sections describe proposed behavior rather than universal deployed
  practice;
- old mailing-list and FTP locations are archival and may no longer exist;
- implementations accumulated compatibility conventions not captured by one
  normative document;
- router operator policy and endpoints can change independently of the
  protocol text.

The proposal credits Greg Stein (Deathblade), John Viega (Rust), Tim Hollebeek
(Beek), and other early implementors and contributors. This repository does not
attempt to rewrite that history; it separates historical specification from
current gateway evidence.

## How to use this reference

1. Use the [original I3v3 proposal](https://wotf.org/specs/i3.html) for
   historical protocol intent.
2. Use the [MudMode specification](https://wotf.org/specs/mudmode.html) for the
   router-facing frame transport.
3. Use current operator references such as
   [Way of the Force](https://wotf.org/i3/) and
   [MUD Standards](https://mudstandards.org/intermud/intermud3/) for deployed
   endpoints and community context.
4. Use this repository's [service matrix](services/README.md), packet models,
   tests, and [validation record](../VALIDATION.md) for claims about the
   gateway.

## Reference map

- [Logical architecture](architecture.md)
- [Packet envelope](packet-format.md)
- [Support packets](support-packets.md)
- [Service reference and implementation matrix](services/README.md)
- [OOB protocol reference](protocols.md)
- [Router design reference](router-design.md)
- [Packet/error catalog](reference.md)
- [Tell and emoteto `visname`](VISNAME_CLARIFICATION.md)
