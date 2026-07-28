# Phase 1 record: protocol foundation

> Historical milestone record. Current behavior and evidence are authoritative
> in [Architecture](../ARCHITECTURE.md) and
> [Validation](../VALIDATION.md).

Phase 1 established:

- LPC text serialization and parsing;
- 4-byte big-endian MudMode framing with buffered fragmented input;
- I3 packet models;
- validated YAML/environment configuration;
- asynchronous router connection abstractions;
- the service registry and state-manager foundations.

An early design draft described a binary type-tagged LPC codec. That was not
compatible with deployed MudMode. The current implementation serializes LPC
text and terminates the payload with NUL inside the length-prefixed frame.

Current validation includes round-trip and malformed-input tests plus live
decoding of production-router mudlist and chanlist payloads. This milestone
does not imply independent fuzzing, a published soak run, or a throughput SLA.
