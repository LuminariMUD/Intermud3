# I3 Gateway Client for JavaScript/Node.js

A comprehensive JavaScript/Node.js client library for connecting to the Intermud3 Gateway API. This library provides both Promise-based and callback interfaces for MUD integration and works in both Node.js and browser environments.

## Features

- **Cross-platform compatibility**: Works in Node.js and modern browsers
- **WebSocket connection management**: Automatic reconnection with exponential backoff
- **JSON-RPC protocol implementation**: Full support for the I3 Gateway API
- **Event handling system**: Real-time event notifications from the I3 network
- **Multiple API styles**: Both Promise-based and callback interfaces
- **TypeScript support**: Complete type definitions included
- **Robust error handling**: Proper error propagation and connection resilience
- **Modern ES6+ features**: Clean, readable code using modern JavaScript

## Installation

### Node.js

```bash
npm install i3-gateway-client
```

### Browser

You can include the library directly in your HTML:

```html
<script src="path/to/i3-client.js"></script>
```

Or use it with a module bundler like webpack or rollup.

## Quick Start

### Promise-based API (Recommended)

```javascript
const { I3Client } = require('i3-gateway-client'); // Node.js
// or
import { I3Client } from 'i3-gateway-client'; // ES modules

async function main() {
    // Create client instance
    const client = new I3Client(
        'ws://localhost:8080',  // Gateway URL
        'your-api-key',         // API key (load from secure source)
        'YourMUD'              // Your MUD's name
    );

    // Register event handlers
    client.on('tell_received', (data) => {
        console.log(`Tell from ${data.from_user}@${data.from_mud}: ${data.message}`);
    });

    client.on('channel_message', (data) => {
        console.log(`[${data.channel}] ${data.from_user}@${data.from_mud}: ${data.message}`);
    });

    try {
        // Connect to gateway
        await client.connect();
        console.log('Connected to I3 Gateway!');

        // Send a tell
        await client.tell('OtherMUD', 'PlayerName', 'Hello from JavaScript!');

        // Join a channel
        await client.channelJoin('chat');

        // Send channel message
        await client.channelSend('chat', 'Hello everyone!');

        // Get who list
        const users = await client.who('OtherMUD');
        console.log('Users online:', users);

        // Keep the connection alive
        process.on('SIGINT', async () => {
            await client.disconnect();
            process.exit();
        });

    } catch (error) {
        console.error('Error:', error);
    }
}

main();
```

### Callback-based API

```javascript
const { CallbackI3Client } = require('i3-gateway-client');

const client = new CallbackI3Client('ws://localhost:8080', 'your-api-key', 'YourMUD');

// Connect
client.connect((error) => {
    if (error) {
        console.error('Connection failed:', error);
        return;
    }

    console.log('Connected!');

    // Send a tell
    client.tell('OtherMUD', 'PlayerName', 'Hello!', (error, result) => {
        if (error) {
            console.error('Tell failed:', error);
        } else {
            console.log('Tell sent:', result);
        }
    });
});
```

### Browser Usage

```html
<!DOCTYPE html>
<html>
<head>
    <script src="i3-client.js"></script>
</head>
<body>
    <script>
        const client = new I3Client('wss://your-gateway.com', 'your-api-key', 'YourMUD');
        
        client.on('connected', () => {
            console.log('Connected to I3 Gateway!');
        });

        client.connect().then(() => {
            return client.channelJoin('chat');
        }).then(() => {
            return client.channelSend('chat', 'Hello from the browser!');
        }).catch(console.error);
    </script>
</body>
</html>
```

## API Reference

### Constructor

#### `new I3Client(url, apiKey, mudName, options)`

- `url` (string): WebSocket URL of the I3 Gateway (ws:// or wss://)
- `apiKey` (string): API authentication key
- `mudName` (string): Your MUD's name
- `options` (object, optional): Additional configuration options

#### `new I3Client(config)`

- `config` (object): Configuration object with all options

### Configuration Options

```javascript
const options = {
    autoReconnect: true,           // Auto-reconnect on disconnect
    reconnectInterval: 5000,       // Base reconnect interval (ms)
    maxReconnectAttempts: 10,      // Max reconnection attempts
    pingInterval: 30000,           // Ping interval (ms)
    pingTimeout: 10000,            // Ping timeout (ms)
    queueSize: 1000,              // Message queue size
    requestTimeout: 30000,         // Request timeout (ms)
    sslVerify: true               // SSL certificate verification
};
```

### Connection Methods

#### `connect()`
Connect to the I3 Gateway.
- Returns: `Promise<void>`

#### `disconnect()`
Disconnect from the I3 Gateway.
- Returns: `Promise<void>`

#### `isConnected()`
Check if client is connected.
- Returns: `boolean`

### Communication Methods

#### `tell(targetMud, targetUser, message, fromUser?)`
Send a tell to a user on another MUD.
- Returns: `Promise<object>`

#### `emoteto(targetMud, targetUser, message, fromUser?)`
Send an emote to a user on another MUD.
- Returns: `Promise<object>`

#### `channelSend(channel, message, fromUser?)`
Send a message to a channel.
- Returns: `Promise<object>`

#### `channelEmote(channel, message, fromUser?)`
Send an emote to a channel.
- Returns: `Promise<object>`

### Information Methods

#### `who(targetMud, filters?)`
Get list of users on a MUD.
- `filters` (object, optional): Filter criteria (min_level, max_level, race, guild)
- Returns: `Promise<Array<UserInfo>>`

#### `finger(targetMud, targetUser)`
Get detailed information about a user.
- Returns: `Promise<UserInfo>`

#### `locate(targetUser)`
Locate a user on the network.
- Returns: `Promise<Array<MudInfo>>`

#### `mudlist(refresh?, filter?)`
Get list of MUDs on the network.
- `refresh` (boolean): Force refresh from router
- `filter` (object): Filter criteria
- Returns: `Promise<Array<MudInfo>>`

### Channel Management

#### `channelJoin(channel, listenOnly?)`
Join a channel.
- Returns: `Promise<object>`

#### `channelLeave(channel)`
Leave a channel.
- Returns: `Promise<object>`

#### `channelList()`
Get list of available channels.
- Returns: `Promise<Array<string>>`

#### `channelWho(channel)`
Get list of users on a channel.
- Returns: `Promise<Array<UserInfo>>`

#### `channelHistory(channel, limit?)`
Get channel message history.
- Returns: `Promise<Array<ChannelMessage>>`

### Administrative Methods

#### `status()`
Get gateway connection status.
- Returns: `Promise<object>`

#### `getStats()`
Get gateway statistics.
- Returns: `Promise<object>`

#### `ping()`
Ping the gateway.
- Returns: `Promise<number>` (round-trip time in ms)

#### `reconnectRouter()`
Force gateway to reconnect to I3 router.
- Returns: `Promise<object>`

### Event Handling

The client emits various events that you can listen to:

```javascript
// Connection events
client.on('connected', () => console.log('Connected'));
client.on('disconnected', () => console.log('Disconnected'));

// Communication events
client.on('tell_received', (data) => {
    console.log(`Tell from ${data.from_user}@${data.from_mud}: ${data.message}`);
});

client.on('channel_message', (data) => {
    console.log(`[${data.channel}] ${data.from_user}@${data.from_mud}: ${data.message}`);
});

// System events
client.on('mud_online', (data) => {
    console.log(`MUD ${data.mud_name} came online`);
});

client.on('error_occurred', (data) => {
    console.error('Gateway error:', data.message);
});
```

### Event Types

- **Communication Events**: `tell_received`, `emoteto_received`, `channel_message`, `channel_emote`
- **System Events**: `mud_online`, `mud_offline`, `channel_joined`, `channel_left`, `error_occurred`, `gateway_reconnected`
- **User Events**: `user_joined_channel`, `user_left_channel`, `user_status_changed`
- **Administrative Events**: `maintenance_scheduled`, `shutdown_warning`, `rate_limit_warning`

## Error Handling

The library provides comprehensive error handling:

```javascript
try {
    await client.tell('NonexistentMUD', 'Player', 'Hello');
} catch (error) {
    if (error instanceof RPCError) {
        console.error(`RPC Error ${error.code}: ${error.rpcMessage}`);
        if (error.data) {
            console.error('Additional data:', error.data);
        }
    } else {
        console.error('Network or other error:', error.message);
    }
}
```

## TypeScript Support

The library includes complete TypeScript definitions:

```typescript
import { I3Client, EventType, UserInfo, MudInfo } from 'i3-gateway-client';

const client = new I3Client('ws://localhost:8080', 'api-key', 'MyMUD');

client.on(EventType.TELL_RECEIVED, (data: any) => {
    // TypeScript will provide autocomplete and type checking
});

const users: UserInfo[] = await client.who('OtherMUD');
```

## Examples

### Basic MUD Integration

```javascript
const { I3Client } = require('i3-gateway-client');

class MudI3Integration {
    constructor(mudName, apiKey) {
        this.client = new I3Client('ws://localhost:8080', apiKey, mudName);
        this.setupEventHandlers();
    }

    setupEventHandlers() {
        this.client.on('tell_received', this.handleTell.bind(this));
        this.client.on('channel_message', this.handleChannelMessage.bind(this));
        this.client.on('connected', () => this.joinDefaultChannels());
    }

    async start() {
        await this.client.connect();
        console.log('I3 integration started');
    }

    async stop() {
        await this.client.disconnect();
        console.log('I3 integration stopped');
    }

    handleTell(data) {
        // Forward tell to appropriate player in your MUD
        this.mudSendToPlayer(data.target_user, 
            `${data.from_user}@${data.from_mud} tells you: ${data.message}`);
    }

    handleChannelMessage(data) {
        // Broadcast channel message to subscribed players
        this.mudBroadcastToChannel(data.channel,
            `[${data.channel}] ${data.from_user}@${data.from_mud}: ${data.message}`);
    }

    async joinDefaultChannels() {
        const channels = ['chat', 'newbie', 'gossip'];
        for (const channel of channels) {
            await this.client.channelJoin(channel);
        }
    }

    // Your MUD-specific implementation methods
    mudSendToPlayer(player, message) {
        // Implement based on your MUD's player messaging system
    }

    mudBroadcastToChannel(channel, message) {
        // Implement based on your MUD's channel system
    }
}
```

### Channel Bot

```javascript
const { I3Client } = require('i3-gateway-client');

class ChannelBot {
    constructor() {
        this.client = new I3Client('ws://localhost:8080', process.env.I3_API_KEY, 'ChannelBot');
        this.commands = new Map([
            ['!time', this.handleTimeCommand.bind(this)],
            ['!who', this.handleWhoCommand.bind(this)],
            ['!mudlist', this.handleMudlistCommand.bind(this)]
        ]);
    }

    async start() {
        this.client.on('channel_message', this.handleChannelMessage.bind(this));
        await this.client.connect();
        await this.client.channelJoin('chat');
        console.log('Channel bot started');
    }

    async handleChannelMessage(data) {
        const message = data.message.trim();
        const command = message.split(' ')[0];
        
        if (this.commands.has(command)) {
            await this.commands.get(command)(data);
        }
    }

    async handleTimeCommand(data) {
        const timeString = new Date().toISOString();
        await this.client.channelSend(data.channel, `Current time: ${timeString}`);
    }

    async handleWhoCommand(data) {
        const args = data.message.split(' ');
        const mudName = args[1] || 'YourDefaultMUD';
        
        try {
            const users = await this.client.who(mudName);
            const userList = users.map(u => u.name).join(', ');
            await this.client.channelSend(data.channel, 
                `Users on ${mudName}: ${userList || 'None'}`);
        } catch (error) {
            await this.client.channelSend(data.channel, 
                `Error getting who list: ${error.message}`);
        }
    }

    async handleMudlistCommand(data) {
        try {
            const muds = await this.client.mudlist();
            const onlineMuds = muds.filter(m => m.status === 'online');
            await this.client.channelSend(data.channel, 
                `Online MUDs: ${onlineMuds.length}`);
        } catch (error) {
            await this.client.channelSend(data.channel, 
                `Error getting MUD list: ${error.message}`);
        }
    }
}

const bot = new ChannelBot();
bot.start().catch(console.error);
```

## Security Considerations

1. **API Key Management**: Never hard-code API keys. Use environment variables or secure configuration files.

```javascript
const apiKey = process.env.I3_API_KEY || 
    require('fs').readFileSync('/etc/mud/i3-key.txt', 'utf8').trim();
```

2. **Input Validation**: Always validate user input before sending to the I3 network.

3. **Rate Limiting**: Implement rate limiting to avoid overwhelming the gateway.

4. **SSL/TLS**: Use secure WebSocket connections (wss://) in production.

## Browser Compatibility

The library works in modern browsers that support:
- WebSocket API
- ES6 features (Promises, Classes, Arrow functions)
- JSON API

For older browsers, consider using polyfills or transpiling with Babel.

## Node.js Compatibility

- Node.js 12.0.0 or higher
- Requires the `ws` package for WebSocket support

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- GitHub Issues: [Repository Issues](https://github.com/your-org/intermud3-gateway/issues)
- Documentation: [API Documentation](https://your-org.github.io/intermud3-gateway/)

## Changelog

### 1.0.0
- Initial release
- Full I3 Gateway API support
- Cross-platform compatibility
- TypeScript definitions
- Comprehensive error handling
- Event system implementation