# Intermud-3 protocol reference

These pages document I3v3 packet shapes, services, support packets, MudMode
transport, and router concepts used by Intermud3 Gateway.

## Read this context first

The original I3v3 document is a historical proposal, not a complete conformance
suite. Deployed routers resolved some ambiguities differently over time.
Accordingly:

- the original specification explains intent and vocabulary;
- current router/operator references describe deployed practice;
- this repository’s packet models and regression tests define what the gateway
  sends and accepts;
- [live validation](../VALIDATION.md) establishes interoperability.

This avoids two opposite mistakes: assuming the proposal alone proves router
compatibility, or assuming a modern non-LPC implementation cannot be compatible
because the proposal was written for MudOS.

## Reference map

- [Overview and provenance](overview.md)
- [Logical network layout](architecture.md)
- [Packet format](packet-format.md)
- [MudMode and OOB protocols](protocols.md)
- [Support packets](support-packets.md)
- [Router design](router-design.md)
- [Packet and error reference](reference.md)
- [Service matrix](services/README.md)
- [Tell/emoteto `visname` layout](VISNAME_CLARIFICATION.md)

## Current external references

- [Way of the Force I3 network](https://wotf.org/i3/)
- [Original I3v3 proposal](https://wotf.org/specs/i3.html)
- [MudMode transport specification](https://wotf.org/specs/mudmode.html)
- [MUD Standards I3 reference](https://mudstandards.org/intermud/intermud3/)

## Gateway scope versus protocol scope

These pages include services that are part of the wider I3 protocol even when
the gateway does not advertise or implement them. The authoritative gateway
status is the [service matrix](services/README.md). In particular, mail, news,
file transfer, ucache, and I3 OOB authentication are protocol references today,
not shipped gateway services.

