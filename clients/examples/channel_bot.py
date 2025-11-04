#!/usr/bin/env python3
"""
I3 Channel Bot Example

This example demonstrates how to create a bot that connects to I3 channels
and responds to messages. It shows:

- Automated channel monitoring
- Command parsing and response
- Bot personality and behaviors
- Error handling and resilience
- Rate limiting and abuse prevention

This can serve as a template for creating utility bots, help systems,
or automated services that interact with the I3 network.
"""

import asyncio
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

# Add the parent directory to the Python path to import the client library
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
from i3_client import I3Client, RPCError


class ChannelBot:
    """
    An intelligent I3 channel bot that can respond to commands and engage in conversation.
    
    Features:
    - Command system with help
    - Rate limiting to prevent spam
    - Channel management
    - Simple AI responses
    - Logging and monitoring
    """
    
    def __init__(self):
        # Configuration from environment
        self.bot_name = os.getenv('BOT_NAME', 'HelpBot')
        self.mud_name = os.getenv('BOT_MUD_NAME', 'BotMUD')
        self.gateway_url = os.getenv('I3_GATEWAY_URL', 'ws://localhost:8080')
        self.api_key = os.getenv('I3_API_KEY')
        
        # Validate configuration
        if not self.api_key:
            raise ValueError("I3_API_KEY environment variable is required")
        
        # Bot configuration
        self.command_prefix = os.getenv('BOT_PREFIX', '!')
        self.admin_users = set(os.getenv('BOT_ADMINS', '').split(',') if os.getenv('BOT_ADMINS') else [])
        self.max_response_length = 200
        
        # Rate limiting
        self.rate_limit_window = 60  # seconds
        self.max_messages_per_window = 10
        self.user_message_times: Dict[str, List[float]] = {}
        
        # Bot state
        self.channels: Set[str] = set()
        self.running = False
        self.start_time = datetime.utcnow()
        self.message_count = 0
        self.command_count = 0
        
        # I3 client
        self.i3_client: Optional[I3Client] = None
        
        # Commands registry
        self.commands = {}
        self._register_commands()
        
        # Responses and personality
        self.greetings = [
            "Hello there!",
            "Hi! How can I help?",
            "Greetings!",
            "Hey there!",
            "Hello! Nice to see you!"
        ]
        
        self.farewells = [
            "Goodbye!",
            "See you later!",
            "Take care!",
            "Until next time!",
            "Farewell!"
        ]
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('ChannelBot')
    
    def _register_commands(self):
        """Register bot commands."""
        self.commands = {
            'help': self._cmd_help,
            'about': self._cmd_about,
            'status': self._cmd_status,
            'time': self._cmd_time,
            'uptime': self._cmd_uptime,
            'channels': self._cmd_channels,
            'mudlist': self._cmd_mudlist,
            'who': self._cmd_who,
            'ping': self._cmd_ping,
            'join': self._cmd_join,
            'leave': self._cmd_leave,
            'say': self._cmd_say,
            'emote': self._cmd_emote,
            'joke': self._cmd_joke,
            'fact': self._cmd_fact,
            'fortune': self._cmd_fortune,
        }
        
        # Admin-only commands
        if self.admin_users:
            self.commands.update({
                'shutdown': self._cmd_shutdown,
                'reload': self._cmd_reload,
                'stats': self._cmd_stats,
                'kick': self._cmd_kick,
            })
    
    async def start(self):
        """Start the bot and connect to I3."""
        self.logger.info(f"Starting {self.bot_name}...")
        
        # Initialize I3 client
        self.i3_client = I3Client(
            url=self.gateway_url,
            api_key=self.api_key,
            mud_name=self.mud_name,
            auto_reconnect=True,
            reconnect_interval=5.0,
            max_reconnect_attempts=20
        )
        
        # Register event handlers
        self._register_handlers()
        
        try:
            # Connect to I3
            await self.i3_client.connect()
            self.logger.info("Connected to I3 Gateway")
            
            # Join default channels
            await self._join_default_channels()
            
            self.running = True
            self.logger.info(f"{self.bot_name} is now active!")
            
            # Send startup message
            await self._announce_startup()
            
            # Keep running
            await self._run_main_loop()
            
        except Exception as e:
            self.logger.error(f"Failed to start bot: {e}")
            raise
    
    # ... Additional methods would continue here
    # (The full implementation is quite long, this shows the structure)

    async def _cmd_help(self, channel: str, user: str, mud: str, args: List[str]):
        """Show available commands."""
        help_text = self._generate_help_text()
        await self._send_channel_message(channel, help_text)
    
    def _generate_help_text(self) -> str:
        """Generate help text."""
        commands = list(self.commands.keys())
        # Remove admin commands for non-admins
        public_commands = [cmd for cmd in commands if cmd not in ['shutdown', 'reload', 'stats', 'kick']]
        
        help_text = f"Available commands (prefix: {self.command_prefix}): " + ", ".join(public_commands[:8])
        if len(public_commands) > 8:
            help_text += " (and more)"
        
        return help_text


if __name__ == '__main__':
    # Check required environment variables
    if not os.getenv('I3_API_KEY'):
        print("Error: I3_API_KEY environment variable is required")
        print()
        print("Please set the following environment variables:")
        print("  export I3_API_KEY='your-gateway-api-key'")
        print("  export BOT_NAME='YourBot'  # Optional, defaults to 'HelpBot'")
        print("  export BOT_MUD_NAME='YourMUD'  # Optional, defaults to 'BotMUD'")
        print("  export BOT_PREFIX='!'  # Optional, defaults to '!'")
        print("  export BOT_ADMINS='user1@mud1,user2@mud2'  # Optional, comma-separated")
        print("  export I3_GATEWAY_URL='ws://localhost:8080'  # Optional")
        print()
        print("Example:")
        print("  export I3_API_KEY='abc123-def456-ghi789'")
        print("  export BOT_NAME='HelpBot'")
        print("  export BOT_ADMINS='admin@MyMUD'")
        print("  python channel_bot.py")
        sys.exit(1)
    
    # Run the bot
    try:
        bot = ChannelBot()
        exit_code = asyncio.run(bot.start())
        sys.exit(exit_code)
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        sys.exit(1)
