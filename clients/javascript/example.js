#!/usr/bin/env node

/**
 * Example usage of the I3 Gateway Client Library
 * 
 * This example demonstrates basic functionality including:
 * - Connecting to the I3 Gateway
 * - Handling events
 * - Sending tells and channel messages
 * - Getting information from other MUDs
 * - Channel management
 * 
 * To run this example:
 * 1. Set your API key: export I3_API_KEY="your-api-key"
 * 2. Run: node example.js
 */

const { I3Client, EventType, RPCError } = require('./i3-client.js');

// Configuration
const CONFIG = {
    gateway_url: process.env.I3_GATEWAY_URL || 'ws://localhost:8080',
    api_key: process.env.I3_API_KEY || '',
    mud_name: process.env.I3_MUD_NAME || 'ExampleMUD',
    auto_reconnect: true,
    reconnect_interval: 5000,
    max_reconnect_attempts: 5
};

class I3Example {
    constructor() {
        // Validate configuration
        if (!CONFIG.api_key) {
            console.error('Error: I3_API_KEY environment variable is required');
            console.error('Set it with: export I3_API_KEY="your-api-key"');
            process.exit(1);
        }

        // Create client
        this.client = new I3Client(CONFIG.gateway_url, CONFIG.api_key, CONFIG.mud_name, {
            autoReconnect: CONFIG.auto_reconnect,
            reconnectInterval: CONFIG.reconnect_interval,
            maxReconnectAttempts: CONFIG.max_reconnect_attempts
        });

        // Set up event handlers
        this.setupEventHandlers();

        // Handle graceful shutdown
        this.setupShutdownHandlers();
    }

    /**
     * Set up event handlers for I3 events
     */
    setupEventHandlers() {
        // Connection events
        this.client.on(EventType.CONNECTED, () => {
            console.log('✅ Connected to I3 Gateway');
            this.onConnected();
        });

        this.client.on(EventType.DISCONNECTED, () => {
            console.log('❌ Disconnected from I3 Gateway');
        });

        // Communication events
        this.client.on(EventType.TELL_RECEIVED, (data) => {
            console.log(`📞 Tell from ${data.from_user}@${data.from_mud}: ${data.message}`);
        });

        this.client.on(EventType.EMOTETO_RECEIVED, (data) => {
            console.log(`🎭 Emote from ${data.from_user}@${data.from_mud}: ${data.message}`);
        });

        this.client.on(EventType.CHANNEL_MESSAGE, (data) => {
            console.log(`[${data.channel}] ${data.from_user}@${data.from_mud}: ${data.message}`);
        });

        this.client.on(EventType.CHANNEL_EMOTE, (data) => {
            console.log(`[${data.channel}] * ${data.from_user}@${data.from_mud} ${data.message}`);
        });

        // System events
        this.client.on(EventType.MUD_ONLINE, (data) => {
            console.log(`🟢 MUD ${data.mud_name} came online`);
        });

        this.client.on(EventType.MUD_OFFLINE, (data) => {
            console.log(`🔴 MUD ${data.mud_name} went offline`);
        });

        this.client.on(EventType.CHANNEL_JOINED, (data) => {
            console.log(`✅ Joined channel: ${data.channel}`);
        });

        this.client.on(EventType.CHANNEL_LEFT, (data) => {
            console.log(`❌ Left channel: ${data.channel}`);
        });

        // Error events
        this.client.on(EventType.ERROR_OCCURRED, (data) => {
            console.error(`⚠️  Gateway error: ${data.message}`);
        });

        this.client.on(EventType.GATEWAY_RECONNECTED, (data) => {
            console.log('🔄 Gateway reconnected to I3 router');
        });
    }

    /**
     * Set up graceful shutdown handlers
     */
    setupShutdownHandlers() {
        const shutdown = async (signal) => {
            console.log(`\n🛑 Received ${signal}, shutting down gracefully...`);
            try {
                await this.client.disconnect();
                console.log('👋 Disconnected successfully');
                process.exit(0);
            } catch (error) {
                console.error('Error during shutdown:', error);
                process.exit(1);
            }
        };

        process.on('SIGINT', () => shutdown('SIGINT'));
        process.on('SIGTERM', () => shutdown('SIGTERM'));
    }

    /**
     * Actions to perform after successful connection
     */
    async onConnected() {
        try {
            // Demo sequence
            await this.demoBasicFunctionality();
            
            // Keep the example running to receive events
            console.log('\n📡 Listening for I3 events... (Press Ctrl+C to exit)');
            
        } catch (error) {
            console.error('Error in demo:', error);
        }
    }

    /**
     * Demonstrate basic I3 functionality
     */
    async demoBasicFunctionality() {
        console.log('\n🎯 Starting I3 functionality demo...\n');

        try {
            // 1. Get gateway status
            console.log('1️⃣  Getting gateway status...');
            const status = await this.client.status();
            console.log(`   Gateway connected to router: ${status.router || 'Unknown'}`);
            console.log(`   Services available: ${status.services ? status.services.join(', ') : 'Unknown'}`);

            // 2. Test ping
            console.log('\n2️⃣  Testing ping...');
            const pingTime = await this.client.ping();
            console.log(`   Ping: ${pingTime}ms`);

            // 3. Get MUD list
            console.log('\n3️⃣  Getting MUD list...');
            const muds = await this.client.mudlist();
            const onlineMuds = muds.filter(mud => mud.status === 'online');
            console.log(`   Total MUDs: ${muds.length}, Online: ${onlineMuds.length}`);
            
            if (onlineMuds.length > 0) {
                console.log('   Online MUDs:');
                onlineMuds.slice(0, 5).forEach(mud => {
                    console.log(`     - ${mud.name} (${mud.driver || 'Unknown driver'})`);
                });
                if (onlineMuds.length > 5) {
                    console.log(`     ... and ${onlineMuds.length - 5} more`);
                }
            }

            // 4. Get channel list
            console.log('\n4️⃣  Getting channel list...');
            const channels = await this.client.channelList();
            console.log(`   Available channels: ${channels.length}`);
            if (channels.length > 0) {
                console.log(`   Channels: ${channels.slice(0, 10).join(', ')}`);
            }

            // 5. Join a channel (if available)
            if (channels.length > 0) {
                const channelToJoin = channels.find(ch => 
                    ['chat', 'gossip', 'newbie', 'test'].includes(ch.toLowerCase())
                ) || channels[0];
                
                console.log(`\n5️⃣  Joining channel: ${channelToJoin}`);
                await this.client.channelJoin(channelToJoin);
                console.log(`   Successfully joined ${channelToJoin}`);

                // Send a test message
                await this.sleep(1000); // Wait a moment
                console.log(`\n6️⃣  Sending test message to ${channelToJoin}...`);
                await this.client.channelSend(channelToJoin, 
                    'Hello from the I3 JavaScript client example! 👋');
                console.log(`   Test message sent`);
            }

            // 7. Try to get who list from a MUD
            if (onlineMuds.length > 0) {
                const targetMud = onlineMuds[0].name;
                console.log(`\n7️⃣  Getting who list from ${targetMud}...`);
                try {
                    const users = await this.client.who(targetMud);
                    console.log(`   Users online at ${targetMud}: ${users.length}`);
                    if (users.length > 0) {
                        console.log('   Sample users:');
                        users.slice(0, 3).forEach(user => {
                            console.log(`     - ${user.name}${user.level ? ` (Level ${user.level})` : ''}`);
                        });
                    }
                } catch (error) {
                    if (error instanceof RPCError) {
                        console.log(`   Who request failed: ${error.rpcMessage}`);
                    } else {
                        console.log(`   Who request failed: ${error.message}`);
                    }
                }
            }

            // 8. Try to locate a user (this might not find anyone)
            console.log(`\n8️⃣  Searching for user 'admin'...`);
            try {
                const locations = await this.client.locate('admin');
                if (locations.length > 0) {
                    console.log(`   Found 'admin' on ${locations.length} MUD(s):`);
                    locations.forEach(loc => {
                        console.log(`     - ${loc.name}`);
                    });
                } else {
                    console.log(`   User 'admin' not found on any MUD`);
                }
            } catch (error) {
                console.log(`   Locate request failed: ${error.message}`);
            }

            // 9. Get client statistics
            console.log(`\n9️⃣  Client statistics:`);
            const stats = this.client.getClientStats();
            console.log(`   Messages sent: ${stats.messagesSent}`);
            console.log(`   Messages received: ${stats.messagesReceived}`);
            console.log(`   Events received: ${stats.eventsReceived}`);
            console.log(`   Errors: ${stats.errors}`);
            console.log(`   Connected at: ${stats.connectedAt}`);

            console.log('\n✨ Demo completed successfully!');

        } catch (error) {
            console.error('\n❌ Demo failed:', error);
            if (error instanceof RPCError) {
                console.error(`   RPC Error ${error.code}: ${error.rpcMessage}`);
                if (error.data) {
                    console.error(`   Additional data:`, error.data);
                }
            }
        }
    }

    /**
     * Utility method to sleep for a given number of milliseconds
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Start the example
     */
    async start() {
        console.log(`🚀 Starting I3 Gateway Client Example`);
        console.log(`   Gateway URL: ${CONFIG.gateway_url}`);
        console.log(`   MUD Name: ${CONFIG.mud_name}`);
        console.log(`   API Key: ${CONFIG.api_key ? '[SET]' : '[NOT SET]'}`);
        
        try {
            await this.client.connect();
        } catch (error) {
            console.error('❌ Failed to connect:', error.message);
            
            if (error.message.includes('401') || error.message.includes('403')) {
                console.error('   This might be an authentication error. Check your API key.');
            } else if (error.message.includes('ECONNREFUSED')) {
                console.error('   Connection refused. Is the I3 Gateway running?');
            }
            
            process.exit(1);
        }
    }
}

// Interactive CLI for testing specific functions
class InteractiveCLI {
    constructor(client) {
        this.client = client;
        this.readline = require('readline');
        this.rl = this.readline.createInterface({
            input: process.stdin,
            output: process.stdout
        });
    }

    start() {
        console.log('\n🎮 Interactive CLI mode started!');
        console.log('Available commands:');
        console.log('  tell <mud> <user> <message>  - Send a tell');
        console.log('  channel <channel> <message>  - Send channel message');
        console.log('  join <channel>               - Join a channel');
        console.log('  leave <channel>              - Leave a channel');
        console.log('  who <mud>                    - Get who list');
        console.log('  finger <mud> <user>          - Get user info');
        console.log('  locate <user>                - Locate user');
        console.log('  muds                         - List MUDs');
        console.log('  channels                     - List channels');
        console.log('  stats                        - Show statistics');
        console.log('  quit                         - Exit');
        console.log('');

        this.prompt();
    }

    prompt() {
        this.rl.question('I3> ', async (input) => {
            await this.handleCommand(input.trim());
            this.prompt();
        });
    }

    async handleCommand(input) {
        if (!input) return;

        const parts = input.split(' ');
        const command = parts[0].toLowerCase();
        const args = parts.slice(1);

        try {
            switch (command) {
                case 'tell':
                    if (args.length < 3) {
                        console.log('Usage: tell <mud> <user> <message>');
                        break;
                    }
                    await this.client.tell(args[0], args[1], args.slice(2).join(' '));
                    console.log('Tell sent');
                    break;

                case 'channel':
                    if (args.length < 2) {
                        console.log('Usage: channel <channel> <message>');
                        break;
                    }
                    await this.client.channelSend(args[0], args.slice(1).join(' '));
                    console.log('Channel message sent');
                    break;

                case 'join':
                    if (args.length < 1) {
                        console.log('Usage: join <channel>');
                        break;
                    }
                    await this.client.channelJoin(args[0]);
                    console.log(`Joined channel: ${args[0]}`);
                    break;

                case 'leave':
                    if (args.length < 1) {
                        console.log('Usage: leave <channel>');
                        break;
                    }
                    await this.client.channelLeave(args[0]);
                    console.log(`Left channel: ${args[0]}`);
                    break;

                case 'who':
                    if (args.length < 1) {
                        console.log('Usage: who <mud>');
                        break;
                    }
                    const users = await this.client.who(args[0]);
                    console.log(`Users on ${args[0]}: ${users.map(u => u.name).join(', ')}`);
                    break;

                case 'finger':
                    if (args.length < 2) {
                        console.log('Usage: finger <mud> <user>');
                        break;
                    }
                    const userInfo = await this.client.finger(args[0], args[1]);
                    console.log('User info:', JSON.stringify(userInfo, null, 2));
                    break;

                case 'locate':
                    if (args.length < 1) {
                        console.log('Usage: locate <user>');
                        break;
                    }
                    const locations = await this.client.locate(args[0]);
                    console.log(`User ${args[0]} found on: ${locations.map(l => l.name).join(', ')}`);
                    break;

                case 'muds':
                    const muds = await this.client.mudlist();
                    console.log(`MUDs (${muds.length}):`);
                    muds.forEach(mud => {
                        console.log(`  ${mud.name} (${mud.status})`);
                    });
                    break;

                case 'channels':
                    const channels = await this.client.channelList();
                    console.log(`Channels: ${channels.join(', ')}`);
                    break;

                case 'stats':
                    const stats = this.client.getClientStats();
                    console.log('Client statistics:', JSON.stringify(stats, null, 2));
                    break;

                case 'quit':
                    this.rl.close();
                    process.exit(0);
                    break;

                default:
                    console.log(`Unknown command: ${command}`);
            }
        } catch (error) {
            console.error('Command failed:', error.message);
        }
    }
}

// Main execution
async function main() {
    const example = new I3Example();
    await example.start();

    // Check if interactive mode is requested
    if (process.argv.includes('--interactive') || process.argv.includes('-i')) {
        const cli = new InteractiveCLI(example.client);
        cli.start();
    }
}

// Only run if this file is executed directly
if (require.main === module) {
    main().catch(error => {
        console.error('Fatal error:', error);
        process.exit(1);
    });
}

module.exports = { I3Example, InteractiveCLI };