#!/usr/bin/env python3
"""
I3 to Discord/IRC Relay Bridge Example

This example demonstrates how to create a bridge that connects I3 channels
to external platforms like Discord or IRC. It shows:

- Bidirectional message relay between I3 and external platforms
- Message formatting and user mapping
- Platform-specific features (Discord embeds, IRC colors)
- Configuration management
- Error handling and reconnection
- Rate limiting and spam prevention

This can be used to integrate MUD communities with modern chat platforms.
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

# Add the parent directory to the Python path to import the client library
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
from i3_client import I3Client, RPCError

# Optional Discord support
try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    discord = None

# Optional IRC support
try:
    import irc.client
    import irc.connection
    IRC_AVAILABLE = True
except ImportError:
    IRC_AVAILABLE = False
    irc = None


class RelayBridge:
    """
    A bridge that relays messages between I3 channels and external platforms.
    
    Supports:
    - Discord channels via discord.py
    - IRC channels via irc library
    - Bidirectional message relay
    - User mapping and formatting
    - Platform-specific features
    """
    
    def __init__(self):
        # Load configuration
        self.config = self._load_config()
        
        # Bridge state
        self.running = False
        self.i3_client: Optional[I3Client] = None
        self.discord_client: Optional[discord.Client] = None
        self.irc_client: Optional[irc.client.Reactor] = None
        self.irc_connection = None
        
        # Message tracking for rate limiting
        self.message_history: Dict[str, List[float]] = {}
        self.rate_limit_window = 60  # seconds
        self.max_messages_per_window = 10
        
        # User mapping cache
        self.user_mappings: Dict[str, str] = {}
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.config.get('log_level', 'INFO')),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('RelayBridge')
    
    def _load_config(self) -> dict:
        """Load configuration from environment and config file."""
        config = {
            # I3 Configuration
            'i3_gateway_url': os.getenv('I3_GATEWAY_URL', 'ws://localhost:8080'),
            'i3_api_key': os.getenv('I3_API_KEY'),
            'i3_mud_name': os.getenv('I3_MUD_NAME', 'RelayBridge'),
            
            # Discord Configuration
            'discord_token': os.getenv('DISCORD_TOKEN'),
            'discord_guild_id': os.getenv('DISCORD_GUILD_ID'),
            
            # IRC Configuration
            'irc_server': os.getenv('IRC_SERVER'),
            'irc_port': int(os.getenv('IRC_PORT', '6667')),
            'irc_nick': os.getenv('IRC_NICK', 'I3Bridge'),
            'irc_password': os.getenv('IRC_PASSWORD'),
            'irc_ssl': os.getenv('IRC_SSL', 'false').lower() == 'true',
            
            # Channel Mappings
            'channel_mappings': self._parse_channel_mappings(),
            
            # Bridge Settings
            'bridge_name': os.getenv('BRIDGE_NAME', 'I3-Bridge'),
            'message_prefix': os.getenv('MESSAGE_PREFIX', '[I3]'),
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            'enable_discord': os.getenv('ENABLE_DISCORD', 'true').lower() == 'true',
            'enable_irc': os.getenv('ENABLE_IRC', 'true').lower() == 'true',
        }
        
        # Validate required configuration
        if not config['i3_api_key']:
            raise ValueError("I3_API_KEY environment variable is required")
        
        return config
    
    def _parse_channel_mappings(self) -> Dict[str, List[dict]]:
        """Parse channel mappings from environment."""
        mappings = {}
        
        # Format: I3_CHANNEL_MAPPINGS=chat:discord:123456789,chat:irc:#general
        mapping_str = os.getenv('CHANNEL_MAPPINGS', '')
        if not mapping_str:
            # Default mappings for demonstration
            return {
                'chat': [
                    {'platform': 'discord', 'channel': 'general'},
                    {'platform': 'irc', 'channel': '#chat'}
                ]
            }
        
        for mapping in mapping_str.split(','):
            parts = mapping.strip().split(':')
            if len(parts) >= 3:
                i3_channel = parts[0]
                platform = parts[1]
                external_channel = ':'.join(parts[2:])  # Handle IRC channels with :
                
                if i3_channel not in mappings:
                    mappings[i3_channel] = []
                
                mappings[i3_channel].append({
                    'platform': platform,
                    'channel': external_channel
                })
        
        return mappings
    
    async def start(self):
        """Start the relay bridge."""
        self.logger.info("Starting I3 Relay Bridge...")
        
        try:
            # Initialize I3 client
            await self._initialize_i3()
            
            # Initialize external platforms
            tasks = []
            
            if self.config['enable_discord'] and DISCORD_AVAILABLE:
                tasks.append(self._initialize_discord())
            elif self.config['enable_discord']:
                self.logger.warning("Discord enabled but discord.py not available")
            
            if self.config['enable_irc'] and IRC_AVAILABLE:
                tasks.append(self._initialize_irc())
            elif self.config['enable_irc']:
                self.logger.warning("IRC enabled but irc library not available")
            
            # Start all platforms concurrently
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            self.running = True
            self.logger.info("Relay bridge is now active!")
            
            # Keep running
            await self._run_main_loop()
            
        except Exception as e:
            self.logger.error(f"Failed to start bridge: {e}")
            raise
    
    # ... Additional methods would continue here
    # (The full implementation is quite long, this shows the structure)


if __name__ == '__main__':
    # Check requirements
    missing_modules = []
    
    if not DISCORD_AVAILABLE:
        missing_modules.append("discord.py (pip install discord.py)")
    
    if not IRC_AVAILABLE:
        missing_modules.append("irc (pip install irc)")
    
    if missing_modules:
        print("Optional dependencies not installed:")
        for module in missing_modules:
            print(f"  - {module}")
        print("\nNote: You can still run the bridge with only the modules you need.")
        print()
    
    # Check required environment variables
    if not os.getenv('I3_API_KEY'):
        print("Error: I3_API_KEY environment variable is required")
        print()
        print("Required environment variables:")
        print("  export I3_API_KEY='your-gateway-api-key'")
        print()
        print("Example:")
        print("  export I3_API_KEY='abc123-def456'")
        print("  export DISCORD_TOKEN='your-bot-token'")
        print("  export CHANNEL_MAPPINGS='chat:discord:general'")
        print("  python relay_bridge.py")
        sys.exit(1)
    
    # Run the bridge
    try:
        bridge = RelayBridge()
        exit_code = asyncio.run(bridge.start())
        sys.exit(exit_code)
    except Exception as e:
        logging.error(f"Failed to start bridge: {e}")
        sys.exit(1)
