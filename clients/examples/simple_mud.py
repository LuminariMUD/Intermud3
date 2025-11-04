#!/usr/bin/env python3
"""
Simple MUD Integration Example

This example demonstrates how a basic MUD server would integrate with the
Intermud3 Gateway. It shows the fundamental patterns for:

- Connecting to the gateway
- Authenticating securely
- Handling incoming messages
- Sending basic communications
- Managing player sessions
- Error handling and reconnection

This serves as a template for integrating I3 support into existing MUD servers.
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional, Set

# Add the parent directory to the Python path to import the client library
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
from i3_client import I3Client, RPCError, ConnectionState


class SimpleMUD:
    """
    A simplified MUD server that demonstrates I3 Gateway integration.
    
    In a real MUD, this would integrate with your existing player management,
    room system, and command parsing infrastructure.
    """
    
    def __init__(self):
        # Configuration from environment variables
        self.mud_name = os.getenv('MUD_NAME', 'ExampleMUD')
        self.gateway_url = os.getenv('I3_GATEWAY_URL', 'ws://localhost:8080')
        self.api_key = os.getenv('I3_API_KEY')
        
        # Validate required configuration
        if not self.api_key:
            raise ValueError(
                "I3_API_KEY environment variable is required. "
                "Please set it to your gateway authentication key."
            )
        
        # MUD state
        self.players: Dict[str, dict] = {}
        self.channels: Set[str] = set()
        self.running = False
        
        # I3 client
        self.i3_client: Optional[I3Client] = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('SimpleMUD')
    
    async def start(self):
        """Start the MUD server and connect to I3 Gateway."""
        self.logger.info(f"Starting {self.mud_name}...")
        
        # Initialize I3 client
        self.i3_client = I3Client(
            url=self.gateway_url,
            api_key=self.api_key,
            mud_name=self.mud_name,
            auto_reconnect=True,
            reconnect_interval=5.0,
            max_reconnect_attempts=10
        )
        
        # Register I3 event handlers
        self._register_i3_handlers()
        
        try:
            # Connect to I3 Gateway
            await self.i3_client.connect()
            self.logger.info("Connected to I3 Gateway successfully")
            
            # Join default channels
            await self._join_default_channels()
            
            # Start the MUD
            self.running = True
            self.logger.info(f"{self.mud_name} is now running!")
            
            # Simulate some MUD operations
            await self._run_simulation()
            
        except Exception as e:
            self.logger.error(f"Failed to start MUD: {e}")
            raise
    
    async def shutdown(self):
        """Gracefully shutdown the MUD."""
        self.logger.info("Shutting down MUD...")
        self.running = False
        
        if self.i3_client:
            # Leave all channels
            for channel in list(self.channels):
                try:
                    await self.i3_client.channel_leave(channel)
                    self.logger.info(f"Left channel: {channel}")
                except Exception as e:
                    self.logger.warning(f"Error leaving channel {channel}: {e}")
            
            # Disconnect from gateway
            await self.i3_client.disconnect()
            self.logger.info("Disconnected from I3 Gateway")
        
        self.logger.info("MUD shutdown complete")
    
    def _register_i3_handlers(self):
        """Register handlers for I3 events."""
        # Connection events
        self.i3_client.on('connected', self._on_i3_connected)
        self.i3_client.on('disconnected', self._on_i3_disconnected)
        
        # Communication events
        self.i3_client.on('tell_received', self._on_tell_received)
        self.i3_client.on('emoteto_received', self._on_emoteto_received)
        
        # Channel events
        self.i3_client.on('channel_message', self._on_channel_message)
        self.i3_client.on('channel_emote', self._on_channel_emote)
        self.i3_client.on('channel_join', self._on_channel_join)
        self.i3_client.on('channel_leave', self._on_channel_leave)
        
        # Information query events
        self.i3_client.on('who_request', self._on_who_request)
        self.i3_client.on('finger_request', self._on_finger_request)
    
    async def _join_default_channels(self):
        """Join default I3 channels."""
        default_channels = ['chat', 'newbie', 'code']
        
        for channel in default_channels:
            try:
                await self.i3_client.channel_join(channel)
                self.channels.add(channel)
                self.logger.info(f"Joined I3 channel: {channel}")
            except RPCError as e:
                if e.code == 1002:  # Channel not found
                    self.logger.warning(f"Channel '{channel}' not available")
                else:
                    self.logger.error(f"Failed to join channel '{channel}': {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error joining channel '{channel}': {e}")
    
    # I3 Event Handlers
    
    async def _on_i3_connected(self, data: dict):
        """Called when connected to I3 Gateway."""
        self.logger.info("I3 Gateway connection established")
    
    async def _on_i3_disconnected(self, data: dict):
        """Called when disconnected from I3 Gateway."""
        self.logger.warning("Lost connection to I3 Gateway")
        # In a real MUD, you might want to inform players about I3 being unavailable
    
    async def _on_tell_received(self, data: dict):
        """Handle incoming tell from another MUD."""
        from_user = data.get('from_user')
        from_mud = data.get('from_mud')
        to_user = data.get('to_user')
        message = data.get('message')
        
        self.logger.info(f"Tell from {from_user}@{from_mud} to {to_user}: {message}")
        
        # Check if target player is online
        if to_user in self.players:
            # In a real MUD, you would send this to the player's connection
            self.logger.info(f"Delivering tell to {to_user}: {from_user}@{from_mud} tells you: {message}")
            
            # Simulate player auto-reply for demonstration
            if from_user.lower() != 'system':
                await self._send_auto_reply(from_mud, from_user, to_user)
        else:
            self.logger.info(f"Player {to_user} not found or offline")
            # In a real MUD, you might log this to mail or a message board
    
    async def _on_emoteto_received(self, data: dict):
        """Handle incoming emote from another MUD."""
        from_user = data.get('from_user')
        from_mud = data.get('from_mud')
        to_user = data.get('to_user')
        emote = data.get('emote')
        
        self.logger.info(f"Emote from {from_user}@{from_mud} to {to_user}: {emote}")
        
        if to_user in self.players:
            # In a real MUD, you would send this to the player's connection
            self.logger.info(f"Delivering emote to {to_user}: {from_user}@{from_mud} {emote}")
    
    async def _on_channel_message(self, data: dict):
        """Handle incoming channel message."""
        channel = data.get('channel')
        user = data.get('user')
        mud = data.get('mud')
        message = data.get('message')
        
        self.logger.info(f"[{channel}] {user}@{mud}: {message}")
        
        # Broadcast to all players subscribed to this channel
        # In a real MUD, you would check each player's channel subscriptions
        for player_name in self.players:
            # Simulate broadcasting to player
            self.logger.debug(f"Broadcasting to {player_name}: [{channel}] {user}@{mud}: {message}")
    
    async def _on_channel_emote(self, data: dict):
        """Handle incoming channel emote."""
        channel = data.get('channel')
        user = data.get('user')
        mud = data.get('mud')
        emote = data.get('emote')
        
        self.logger.info(f"[{channel}] {user}@{mud} {emote}")
        
        # Broadcast to all players subscribed to this channel
        for player_name in self.players:
            self.logger.debug(f"Broadcasting to {player_name}: [{channel}] {user}@{mud} {emote}")
    
    async def _on_channel_join(self, data: dict):
        """Handle channel join notification."""
        channel = data.get('channel')
        user = data.get('user')
        mud = data.get('mud')
        
        self.logger.info(f"{user}@{mud} joined channel [{channel}]")
    
    async def _on_channel_leave(self, data: dict):
        """Handle channel leave notification."""
        channel = data.get('channel')
        user = data.get('user')
        mud = data.get('mud')
        
        self.logger.info(f"{user}@{mud} left channel [{channel}]")
    
    async def _on_who_request(self, data: dict):
        """Handle who request from another MUD."""
        from_mud = data.get('from_mud')
        request_id = data.get('request_id')
        
        self.logger.info(f"Who request from {from_mud}")
        
        # Build player list (in a real MUD, this would query your player database)
        user_list = []
        for player_name, player_data in self.players.items():
            user_list.append({
                'name': player_name,
                'title': player_data.get('title', 'the Player'),
                'level': player_data.get('level', 1),
                'idle': player_data.get('idle', 0),
                'class': player_data.get('class', 'Adventurer'),
                'race': player_data.get('race', 'Human')
            })
        
        # Send who reply (this would be implemented in the gateway API)
        # For now, just log what we would send
        self.logger.info(f"Would send who reply to {from_mud}: {len(user_list)} players online")
    
    async def _on_finger_request(self, data: dict):
        """Handle finger request from another MUD."""
        from_mud = data.get('from_mud')
        target_user = data.get('target_user')
        request_id = data.get('request_id')
        
        self.logger.info(f"Finger request from {from_mud} for {target_user}")
        
        if target_user in self.players:
            player_data = self.players[target_user]
            # In a real MUD, you would gather comprehensive player information
            finger_info = {
                'name': target_user,
                'title': player_data.get('title', 'the Player'),
                'real_name': player_data.get('real_name', 'Unknown'),
                'email': player_data.get('email'),
                'level': player_data.get('level', 1),
                'class': player_data.get('class', 'Adventurer'),
                'race': player_data.get('race', 'Human'),
                'last_login': player_data.get('last_login'),
                'idle': player_data.get('idle', 0),
                'plan': player_data.get('plan', 'No plan set.')
            }
            
            self.logger.info(f"Would send finger reply to {from_mud} for {target_user}")
        else:
            self.logger.info(f"Player {target_user} not found for finger request from {from_mud}")
    
    # Utility Methods
    
    async def _send_auto_reply(self, target_mud: str, target_user: str, our_user: str):
        """Send an automated reply to demonstrate tell functionality."""
        try:
            reply_message = f"Hello! This is an automated reply from {our_user} on {self.mud_name}. Thanks for your message!"
            
            await self.i3_client.tell(
                target_mud=target_mud,
                target_user=target_user,
                message=reply_message,
                from_user=our_user
            )
            
            self.logger.info(f"Sent auto-reply to {target_user}@{target_mud}")
            
        except Exception as e:
            self.logger.error(f"Failed to send auto-reply: {e}")
    
    async def _simulate_player_login(self, player_name: str):
        """Simulate a player logging in."""
        self.players[player_name] = {
            'title': f'{player_name} the Adventurer',
            'level': 25,
            'class': 'Warrior',
            'race': 'Human',
            'idle': 0,
            'last_login': datetime.utcnow().isoformat(),
            'real_name': f'Player {player_name}',
            'email': f'{player_name.lower()}@example.com',
            'plan': f'Currently exploring the world on {self.mud_name}!'
        }
        
        self.logger.info(f"Player {player_name} logged in")
        
        # Send a welcome message to a channel
        if 'chat' in self.channels:
            try:
                await self.i3_client.channel_send(
                    channel='chat',
                    message=f"Welcome {player_name} to {self.mud_name}!",
                    from_user='System'
                )
            except Exception as e:
                self.logger.error(f"Failed to send welcome message: {e}")
    
    async def _simulate_player_logout(self, player_name: str):
        """Simulate a player logging out."""
        if player_name in self.players:
            del self.players[player_name]
            self.logger.info(f"Player {player_name} logged out")
    
    async def _run_simulation(self):
        """Run a simulation of MUD activity for demonstration."""
        # Simulate some players logging in
        await self._simulate_player_login('Alice')
        await asyncio.sleep(2)
        await self._simulate_player_login('Bob')
        await asyncio.sleep(2)
        await self._simulate_player_login('Charlie')
        
        # Simulate some channel activity
        try:
            if 'chat' in self.channels:
                await self.i3_client.channel_send(
                    channel='chat',
                    message=f"Greetings from {self.mud_name}! We now have {len(self.players)} players online.",
                    from_user='System'
                )
        except Exception as e:
            self.logger.error(f"Failed to send system message: {e}")
        
        # Keep running until shutdown
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
    
    async def demo_i3_features(self):
        """Demonstrate various I3 features for educational purposes."""
        if not self.i3_client or not self.i3_client.is_connected():
            self.logger.error("I3 client not connected")
            return
        
        self.logger.info("=== I3 Features Demonstration ===")
        
        try:
            # 1. Get MUD list
            self.logger.info("Fetching MUD list...")
            muds = await self.i3_client.mudlist()
            self.logger.info(f"Found {len(muds)} MUDs on the network")
            for mud in muds[:3]:  # Show first 3
                self.logger.info(f"  - {mud.get('name')}: {mud.get('status')} ({mud.get('players', 0)} players)")
            
            # 2. Get channel list
            self.logger.info("Fetching channel list...")
            channels = await self.i3_client.channel_list()
            self.logger.info(f"Available channels: {', '.join(channels[:5])}")  # Show first 5
            
            # 3. Ping test
            self.logger.info("Testing ping...")
            ping_time = await self.i3_client.ping()
            self.logger.info(f"Gateway ping: {ping_time:.2f}ms")
            
            # 4. Gateway status
            self.logger.info("Checking gateway status...")
            status = await self.i3_client.status()
            self.logger.info(f"Gateway status: {status}")
            
        except Exception as e:
            self.logger.error(f"Error in I3 features demo: {e}")


async def main():
    """Main entry point."""
    # Setup signal handling for graceful shutdown
    mud = SimpleMUD()
    
    def signal_handler():
        asyncio.create_task(mud.shutdown())
    
    # Register signal handlers
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    
    try:
        await mud.start()
    except KeyboardInterrupt:
        print("\nReceived interrupt signal")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        return 1
    finally:
        await mud.shutdown()
    
    return 0


if __name__ == '__main__':
    # Example environment setup - these would normally be set in your environment
    if not os.getenv('I3_API_KEY'):
        print("Error: I3_API_KEY environment variable is required")
        print()
        print("Please set the following environment variables:")
        print("  export I3_API_KEY='your-gateway-api-key'")
        print("  export MUD_NAME='YourMUD'  # Optional, defaults to 'ExampleMUD'")
        print("  export I3_GATEWAY_URL='ws://localhost:8080'  # Optional, defaults to localhost")
        print()
        print("Example:")
        print("  export I3_API_KEY='abc123-def456-ghi789'")
        print("  python simple_mud.py")
        sys.exit(1)
    
    # Run the MUD
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        logging.error(f"Failed to start: {e}")
        sys.exit(1)
