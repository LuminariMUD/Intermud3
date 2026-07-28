# JavaScript/Node.js WebSocket client

This directory contains a CommonJS client, TypeScript declarations, and an
example for the gateway's WebSocket JSON-RPC API. It is source bundled with the
repository; the documentation does not assume that
`i3-gateway-client` is published to npm.

## Install locally

The package metadata currently requires Node.js 24 or newer.

```bash
cd clients/javascript
npm install
export I3_API_KEY='replace-with-a-configured-key'
export I3_GATEWAY_URL='ws://127.0.0.1:8080/ws'
node example.js
```

`npm test` is presently a placeholder that exits with failure. `npm run lint`
is the available source check.

## Minimal use

```javascript
const { I3Client } = require('./i3-client.js');

const client = new I3Client(
  'ws://127.0.0.1:8080/ws',
  process.env.I3_API_KEY,
  'YourMUD'
);

async function main() {
  client.on('tell_received', (event) => {
    console.log(`${event.from_user}@${event.from_mud}: ${event.message}`);
  });

  client.on('who_reply', (event) => {
    console.log(event);
  });

  await client.connect();
  await client.tell('OtherMUD', 'friend', 'Hello', 'Alyx');
  await client.sendRequest('who', { target_mud: 'OtherMUD' });
}

main().catch(console.error);
```

Node.js can supply the `X-API-Key` WebSocket header. Browsers cannot set
arbitrary WebSocket handshake headers, so browser use needs a trusted
same-origin proxy or an explicit first-message authentication flow. The current
client tries header authentication and should not be described as a
drop-in browser authentication solution.

## API shape

`I3Client` provides Promise methods; `CallbackI3Client` wraps a smaller subset.
Connection and gateway events are exposed through `on`, `off`, and `once`.
`sendRequest(method, params)` is the escape hatch for canonical API calls.

## Known contract differences

- The internal default URL and checked-in example omit `/ws`; always pass
  `ws://HOST:PORT/ws` explicitly.
- `emoteto()` and `channelEmote()` send `message`; the gateway requires
  `emote`.
- `who()` and `locate()` expect data in the immediate result. The gateway
  returns request status, then emits `who_reply` or `locate_reply`.
- `finger()` also completes asynchronously through `finger_reply`.
- Several event constants in the type declarations describe planned events,
  not events guaranteed by the current gateway.
- Package homepage, repository, funding, and bug URLs in `package.json` still
  contain placeholder organization names.

Use a direct request for affected methods:

```javascript
await client.sendRequest('channel_emote', {
  channel: 'intermud',
  from_user: 'Alyx',
  emote: '$N waves.'
});

client.on('locate_reply', console.log);
await client.sendRequest('locate', { target_user: 'friend' });
```

The [API reference](../../docs/API_REFERENCE.md) is authoritative when this
client or its `.d.ts` file differs.
