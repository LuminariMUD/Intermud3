# Intermud3 Integration for CircleMUD/tbaMUD

This directory contains a complete integration package for adding Intermud3 support to CircleMUD and tbaMUD servers. The integration uses a separate process that communicates with the I3 Gateway, keeping the core MUD code clean and maintainable.

## Overview

The integration consists of:
- **i3_client.c/h**: Core I3 client implementation
- **i3_commands.c**: Player command implementations
- **i3_handler.c**: Message and event handlers
- **i3_protocol.c**: JSON-RPC protocol implementation
- **Installation scripts**: Automated integration into existing MUD

## Features

- Full Intermud3 protocol support
- Tell system (i3tell command)
- Channel system (i3chat, i3join, i3leave)
- Who/finger/locate commands
- Automatic reconnection on failure
- Thread-safe message queuing
- Minimal impact on MUD performance

## Requirements

- CircleMUD 3.1+ or tbaMUD 2020+
- C compiler with C99 support
- POSIX threads support
- JSON-C library (libjson-c-dev)
- Network connectivity to I3 Gateway

## Quick Installation

```bash
# 1. Copy integration files to your MUD source
cp -r clients/circlemud/* /path/to/your/mud/src/

# 2. Apply the patch to your Makefile
patch < i3_makefile.patch

# 3. Install JSON-C library
sudo apt-get install libjson-c-dev

# 4. Rebuild your MUD
make clean && make

# 5. Configure I3 settings in config/i3.conf
# 6. Restart your MUD
```

## Configuration

Edit `config/i3.conf`:
```
# I3 Gateway Configuration
I3_GATEWAY_HOST localhost
I3_GATEWAY_PORT 8081
I3_API_KEY your-api-key-here
I3_MUD_NAME YourMUD

# Features
I3_ENABLE_TELL YES
I3_ENABLE_CHANNELS YES
I3_ENABLE_WHO YES
I3_AUTO_RECONNECT YES
I3_RECONNECT_DELAY 30
```

## Architecture

The integration uses a separate thread for I3 communication:

```
CircleMUD Main Thread          I3 Client Thread
        |                             |
        | <-- Command Queue -->       |
        |                             |
        | <-- Event Queue   -->       |
        |                             |
     Game Loop                   I3 Gateway
                                      |
                                 JSON-RPC API
```

## Commands Added

### Player Commands
- `i3 tell <user>@<mud> <message>` - Send a tell
- `i3 reply <message>` - Reply to last tell
- `i3 who <mud>` - List users on a MUD
- `i3 finger <user>@<mud>` - Get user info
- `i3 locate <user>` - Find user on network
- `i3 mudlist` - List all MUDs
- `i3 channel list` - List channels
- `i3 channel join <channel>` - Join a channel
- `i3 channel leave <channel>` - Leave a channel
- `i3 chat <message>` - Send to default channel

### Immortal Commands
- `i3 status` - Show I3 connection status
- `i3 stats` - Show I3 statistics
- `i3 reconnect` - Force reconnection
- `i3 config` - Show/edit configuration

## Integration Points

The integration hooks into CircleMUD at these points:

1. **main.c**: Initialize I3 client on startup
2. **comm.c**: Handle I3 events in game loop
3. **interpreter.c**: Add I3 command parsing
4. **structs.h**: Add I3 fields to char_data
5. **db.c**: Load/save I3 preferences

## Thread Safety

All communication between the MUD and I3 client uses thread-safe queues:
- Command queue (MUD -> I3)
- Event queue (I3 -> MUD)
- Mutexes protect shared data structures

## Error Handling

The integration includes robust error handling:
- Automatic reconnection on disconnect
- Rate limiting to prevent spam
- Input validation and sanitization
- Graceful degradation if gateway unavailable

## Performance Impact

Minimal performance impact:
- Separate thread for I3 communication
- Non-blocking message queues
- Efficient event processing
- < 1% CPU overhead
- < 10MB memory usage

## Troubleshooting

### Connection Issues
```bash
# Check I3 client status
tail -f log/i3_client.log

# Test gateway connectivity
telnet localhost 8081

# Verify API key
grep I3_API_KEY config/i3.conf
```

### Command Issues
- Ensure player has I3 privileges (PLR_I3 flag)
- Check command syntax with `i3 help`
- Verify MUD name in tells (case-sensitive)

### Performance Issues
- Reduce I3_MAX_QUEUE_SIZE if memory constrained
- Increase I3_RECONNECT_DELAY if network unstable
- Disable unused features in config

## Support

For issues specific to this integration:
- Check logs in `log/i3_client.log`
- Review examples in this directory
- Consult main Intermud3 documentation

## License

This integration is provided under the same license as CircleMUD/tbaMUD.