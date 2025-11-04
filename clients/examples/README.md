# I3 Gateway Client Examples

This directory contains comprehensive example implementations demonstrating how to use the I3 Gateway client library for various integration scenarios.

## Examples Overview

### 1. simple_mud.py - Basic MUD Integration
**Purpose**: Shows how a traditional MUD server would integrate with the I3 Gateway.

**Features**:
- Connection management and authentication
- Event handling for tells, channels, and info queries
- Player session simulation
- Error handling and reconnection
- Auto-reply functionality for demonstration

**Use Case**: Template for integrating I3 support into existing MUD codebases.

**Configuration**:
```bash
export I3_API_KEY='your-gateway-api-key'
export MUD_NAME='YourMUD'
export I3_GATEWAY_URL='ws://localhost:8080'
```

### 2. channel_bot.py - Intelligent Channel Bot
**Purpose**: Demonstrates automated bot functionality for I3 channels.

**Features**:
- Command system with help and administration
- Rate limiting and spam prevention
- Bot personality and responses
- Channel management
- Administrative controls
- Educational commands (jokes, facts, utilities)

**Use Case**: Creating utility bots, help systems, or automated channel services.

**Configuration**:
```bash
export I3_API_KEY='your-gateway-api-key'
export BOT_NAME='HelpBot'
export BOT_MUD_NAME='BotMUD'
export BOT_PREFIX='!'
export BOT_ADMINS='admin@YourMUD,user@OtherMUD'
```

### 3. relay_bridge.py - Multi-Platform Bridge
**Purpose**: Bridges I3 channels with modern chat platforms like Discord and IRC.

**Features**:
- Bidirectional message relay
- Platform-specific formatting (Discord embeds, IRC colors)
- User mapping and message cleaning
- Rate limiting and loop prevention
- Multi-platform support

**Use Case**: Connecting MUD communities with Discord servers or IRC networks.

**Dependencies**: `pip install discord.py irc`

**Configuration**:
```bash
export I3_API_KEY='your-gateway-api-key'
export DISCORD_TOKEN='your-discord-bot-token'
export DISCORD_GUILD_ID='your-server-id'
export IRC_SERVER='irc.libera.chat'
export IRC_NICK='I3Bridge'
export CHANNEL_MAPPINGS='chat:discord:123456789,chat:irc:#general'
```

### 4. web_client.py - Browser-Based Interface
**Purpose**: Provides a web-based interface for I3 Gateway operations.

**Features**:
- RESTful API for I3 operations
- Real-time WebSocket messaging
- Browser-based chat interface
- Authentication and rate limiting
- Responsive web UI

**Use Case**: Web-based MUD clients or administrative dashboards.

**Dependencies**: `pip install fastapi uvicorn`

**Configuration**:
```bash
export I3_API_KEY='your-gateway-api-key'
export WEB_AUTH_TOKEN='secure-web-token'
export WEB_HOST='0.0.0.0'
export WEB_PORT='8000'
```

## Installation and Setup

### 1. Install Dependencies
```bash
# Core requirements
pip install aiohttp

# Optional dependencies based on which examples you want to use
pip install -r requirements.txt
```

### 2. Setup I3 Gateway Client
The examples assume the I3 client library is available. Ensure the parent directory structure:
```
clients/
├── python/
│   └── i3_client.py
└── examples/
    ├── simple_mud.py
    ├── channel_bot.py
    ├── relay_bridge.py
    └── web_client.py
```

### 3. Configure Environment Variables
Each example requires specific environment variables. See the individual example sections above or run the scripts without configuration to see the required variables.

### 4. Run Examples
```bash
# Run the simple MUD example
python simple_mud.py

# Run the channel bot
python channel_bot.py

# Run the relay bridge
python relay_bridge.py

# Run the web client
python web_client.py
```

## Security Best Practices

1. **API Keys**: Never hardcode API keys. Always use environment variables or secure configuration files.

2. **Authentication Tokens**: Use strong, unique tokens for web interfaces and change them regularly.

3. **Rate Limiting**: All examples include rate limiting to prevent abuse and comply with gateway policies.

4. **Input Validation**: User inputs are validated and sanitized before processing.

5. **Error Handling**: Comprehensive error handling prevents crashes and information leakage.

## Development Guidelines

### Code Structure
- Each example is self-contained and well-documented
- Clear separation between configuration, logic, and handlers
- Consistent error handling and logging patterns
- Type hints for better code maintainability

### Event Handling
All examples demonstrate proper I3 event handling:
- Connection management (connect/disconnect)
- Message events (tells, channels, emotes)
- Information queries (who, finger, locate)
- Administrative events

### Best Practices Demonstrated
- Asynchronous programming with asyncio
- Proper resource cleanup and shutdown
- Configuration through environment variables
- Logging for debugging and monitoring
- Graceful error recovery

## Troubleshooting

### Common Issues

1. **Connection Failures**
   - Verify I3_GATEWAY_URL is correct
   - Check I3_API_KEY is valid
   - Ensure gateway is running and accessible

2. **Authentication Errors**
   - Confirm API key is correct
   - Check key has appropriate permissions
   - Verify MUD name is registered

3. **Missing Dependencies**
   - Install required packages: `pip install -r requirements.txt`
   - Check Python version compatibility (3.8+)

4. **Rate Limiting**
   - Respect gateway rate limits
   - Implement client-side rate limiting
   - Monitor usage patterns

### Debug Mode
Enable debug logging for troubleshooting:
```bash
export LOG_LEVEL=DEBUG
python your_example.py
```

## Contributing

When creating new examples:

1. Follow the established patterns for configuration and error handling
2. Include comprehensive documentation and comments
3. Demonstrate security best practices
4. Provide clear setup instructions
5. Test with various scenarios and edge cases

## Support

For questions about these examples:
1. Check the main I3 Gateway documentation
2. Review the client library source code
3. Examine the example code comments
4. Test with debug logging enabled

These examples serve as both working implementations and educational resources for integrating with the Intermud3 Gateway.
