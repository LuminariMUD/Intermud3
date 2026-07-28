# CircleMUD C integration status

The C files in this directory are a reference for embedding the gateway's
newline-delimited TCP JSON-RPC API into a CircleMUD/tbaMUD-style server. They
are not a complete drop-in client and have no repository build target or
automated C test suite.

## What the files contain

- connection, reconnect, authentication, and outbound-command scaffolding;
- a queue and background-thread design;
- JSON-C-based request/response handling;
- command handlers for common I3 operations;
- configuration constants and integration hooks for a CircleMUD-style codebase.

The 2026-07-28 live observation of LuminariMUD holding an authenticated TCP
session proves the gateway's local TCP interoperability with a C MUD. It does
not prove that these exact reference files compile unchanged or implement
every in-game command.

## Incomplete paths

Source review currently shows:

- incoming tell and channel parsing explicitly disabled;
- event delivery to the game thread marked TODO;
- multiple command bodies left as TODO stubs;
- mud/channel list parsing and counts incomplete;
- no maintained build recipe showing the host MUD headers, JSON-C flags, and
  threading flags needed for a specific tree;
- no sanitizer, unit, or integration test target for this directory.

Because inbound network data crosses into a long-running C process, complete
those paths with strict length/type validation and a main-thread handoff before
using them for player-visible traffic.

## Recommended integration sequence

1. Implement the raw TCP contract in an isolated module: connect to port 8081,
   read the welcome line, authenticate, and frame one JSON object per newline.
2. Keep socket I/O off the game loop but mutate game state only on the game
   thread.
3. Add bounded queues and define overflow behavior.
4. Map gateway events to copied, owned C data; do not retain JSON-C pointers
   after freeing their parent object.
5. Add tests for partial reads, multiple lines per read, oversized lines,
   malformed JSON, disconnect during write, reconnect, and shutdown.
6. Run ASan/UBSan and ThreadSanitizer where the host build permits.
7. Exercise against a local gateway and mock router before using `*wir`.

The canonical method names, parameters, response shapes, and events are in the
[API reference](../../docs/API_REFERENCE.md). In particular, remote
`who`/`finger`/`locate` replies are asynchronous, and `emoteto` plus
`channel_emote` require an `emote` parameter.

## Adoption decision

Use these files as design material unless you are prepared to own the missing
parsers, game-thread integration, build plumbing, and C-level testing. A new
small adapter tailored to the target MUD's descriptor/event architecture may
be less work than completing every generic stub.
