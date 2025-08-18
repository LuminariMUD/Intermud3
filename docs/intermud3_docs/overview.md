# Intermud-3: A Proposal for The Future

## Overview

This document details a proposal for a future generation of Intermud protocols. It is designed to use the high level communication facilities provided by the MudOS LP driver. Other drivers may be capable of handling the communication protocol, but this proposal does not focus on them.

## Initial Protocol Design

The initial protocol was designed by:
- **Greg Stein** (gstein@svpal.org)
- **John Viega** (rust@virginia.edu)  
- **Tim Hollebeek** (tim@handel.princeton.edu)

For discussion, please forward to the Intermud mailing list at intermud@imaginary.com. You may subscribe by mailing majordomo@imaginary.com with "subscribe intermud" in the body.

## Contributors

The core designers of this protocol were:
- **Deathblade** - Greg Stein (gstein@svpal.org)
- **Rust** - John Viega (rust@virginia.edu)
- **Beek** - Tim Hollebeek (tim@handel.princeton.edu)

### Additional Contributors

- **Descartes** - George Reese (borg@imaginary.com)
  - Contributed in numerous areas, particularly as one of the pioneer implementors after the initial development by the Lima Mudlib team.

- **Deathknight** - Jesse McClusky (thought@weblink.org)
  - Original contributor of the central router-based, backbone design of the current I3 system.

Many other contributors offered input both at the conference in February '95 and on the intermud mailing list.

## Implementations

### Lima Mudlib
Contains an implementation of the Intermud-3 system written by Deathblade. This was the first implementation to exist and is one of the few that is readily and publicly available for use by other systems. It was implemented for the MudOS v22 driver.
- Available at: ftp://ftp.imaginary.com/lib/LIMA

### Nightmare Object Library
Contains an implementation of the Intermud-3 system written by Descartes. This implementation is also one of the oldest around, originating soon after the Lima version and first appearing in the release of Nightmare IV. The Intermud-3 system for Nightmare (and Foundation) has also been pulled out into its own package.
- Available at: ftp://ftp.imaginary.com/pub/LPC/etc/Intermud3.tar.gz

### Terry's Implementations
Terry Penn (aurora@openix.com) has created two implementations:
- One for Shadow's Edge running LPMUD 3.2.1@122
- Another for MudOS v22a18
- Both running on custom mudlibs (not generally available)

### Logic's Implementation
Edward Marshall (logic@common.net) has written an implementation for LPmud 3.2.1 for the private mudlib EOTSlib. Potential plans for a public release of the I3 package.

### Skylight & Hanzou Implementation
Patrick Li (pli@shell.portal.com) and James Donald Jr. (hanzou@echeque.com) have written a version for LPmud 3.2.1@98 (or later). The package is primarily aimed for 2.4.5 mudlibs.
- Available at: ftp://ftp.netcom.com/pub/ja/jamesd/lpmud/amylaar-intermud3-latest.tar.gz

### Router Implementation
Deathblade and Cowl (Hal Schechner, cowl@orion.tyler.net) designed and implemented the Intermud-3 router currently in use at athens.imaginary.com.

## Documentation Structure

This documentation is organized into the following sections:
- [Architecture](architecture.md) - Network layout and naming conventions
- [Packet Format](packet-format.md) - Basic format of all packets
- [Services](services/README.md) - Available services
- [Support Packets](support-packets.md) - Additional packet types for maintenance
- [OOB Protocols](protocols.md) - Out-of-band communication protocols
- [Router Design](router-design.md) - Router architecture and design
- [Reference](reference.md) - Error codes and packet types summary
- [Change Log](changelog.md) - Recent changes to the specification