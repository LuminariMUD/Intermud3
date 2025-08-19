"""State management for Intermud3 Gateway.

This module manages gateway state including MUD lists, channel state,
user sessions, and caching.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Callable
from datetime import datetime, timedelta
from dataclasses import asdict
import uuid

from ..models.connection import MudInfo, ChannelInfo, UserSession, MudStatus


class TTLCache:
    """Simple TTL cache implementation."""
    
    def __init__(self, default_ttl: float = 300.0):
        """Initialize TTL cache.
        
        Args:
            default_ttl: Default TTL in seconds for cached items
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get item from cache if not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if expired/missing
        """
        async with self._lock:
            if key not in self._cache:
                return None
            
            value, expiry = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
            
            return value
    
    async def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Set item in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (uses default if None)
        """
        ttl = ttl or self.default_ttl
        expiry = time.time() + ttl
        
        async with self._lock:
            self._cache[key] = (value, expiry)
    
    async def delete(self, key: str):
        """Delete item from cache.
        
        Args:
            key: Cache key
        """
        async with self._lock:
            self._cache.pop(key, None)
    
    async def clear(self):
        """Clear all cached items."""
        async with self._lock:
            self._cache.clear()
    
    async def cleanup(self):
        """Remove expired items from cache."""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, expiry) in self._cache.items()
                if current_time > expiry
            ]
            for key in expired_keys:
                del self._cache[key]


class StateManager:
    """Manages gateway state and caching."""
    
    def __init__(self, 
                 persistence_dir: Optional[Path] = None,
                 cache_ttl: float = 300.0):
        """Initialize state manager.
        
        Args:
            persistence_dir: Directory for persistent state storage
            cache_ttl: Default cache TTL in seconds
        """
        self.persistence_dir = persistence_dir
        if persistence_dir:
            persistence_dir.mkdir(parents=True, exist_ok=True)
        
        # MUD information
        self.mudlist: Dict[str, MudInfo] = {}
        self.mudlist_id: int = 0
        self.mudlist_lock = asyncio.Lock()
        
        # Channel information
        self.channels: Dict[str, ChannelInfo] = {}
        self.channel_lock = asyncio.Lock()
        
        # User sessions
        self.sessions: Dict[str, UserSession] = {}
        self.session_lock = asyncio.Lock()
        
        # Caching
        self.cache = TTLCache(default_ttl=cache_ttl)
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the state manager and load persistent state."""
        # Load persistent state if available
        if self.persistence_dir:
            await self.load_state()
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def stop(self):
        """Stop the state manager and save state."""
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Save state if persistence is enabled
        if self.persistence_dir:
            await self.save_state()
    
    async def update_mudlist(self, mudlist_data: Dict[str, List[Any]], mudlist_id: int):
        """Update the MUD list from router data.
        
        Args:
            mudlist_data: Mudlist data from router (mud_name -> info array)
            mudlist_id: Mudlist ID from router
        """
        async with self.mudlist_lock:
            self.mudlist_id = mudlist_id
            
            # Update existing MUDs and add new ones
            for mud_name, mud_data in mudlist_data.items():
                if mud_name in self.mudlist:
                    self.mudlist[mud_name].update_from_mudlist(mud_data)
                else:
                    mud_info = MudInfo(
                        name=mud_name,
                        address="",
                        player_port=0
                    )
                    mud_info.update_from_mudlist(mud_data)
                    self.mudlist[mud_name] = mud_info
            
            # Mark MUDs not in update as down
            for mud_name in self.mudlist:
                if mud_name not in mudlist_data:
                    self.mudlist[mud_name].status = MudStatus.DOWN
    
    async def get_mud_info(self, mud_name: str) -> Optional[MudInfo]:
        """Get information about a specific MUD.
        
        Args:
            mud_name: Name of the MUD
            
        Returns:
            MUD information or None if not found
        """
        # Check cache first
        cached = await self.cache.get(f"mud:{mud_name}")
        if cached:
            return cached
        
        # Get from mudlist
        async with self.mudlist_lock:
            mud_info = self.mudlist.get(mud_name)
            if mud_info:
                # Cache the result
                await self.cache.set(f"mud:{mud_name}", mud_info, ttl=60)
            return mud_info
    
    async def get_online_muds(self) -> List[MudInfo]:
        """Get list of online MUDs.
        
        Returns:
            List of online MUD information
        """
        async with self.mudlist_lock:
            return [
                mud for mud in self.mudlist.values()
                if mud.is_online()
            ]
    
    async def add_channel(self, channel: ChannelInfo):
        """Add or update a channel.
        
        Args:
            channel: Channel information
        """
        async with self.channel_lock:
            self.channels[channel.name] = channel
    
    async def get_channel(self, channel_name: str) -> Optional[ChannelInfo]:
        """Get information about a channel.
        
        Args:
            channel_name: Name of the channel
            
        Returns:
            Channel information or None if not found
        """
        async with self.channel_lock:
            return self.channels.get(channel_name)
    
    async def get_channels(self) -> List[ChannelInfo]:
        """Get list of all channels.
        
        Returns:
            List of channel information
        """
        async with self.channel_lock:
            return list(self.channels.values())
    
    async def create_session(self, mud_name: str, user_name: str) -> UserSession:
        """Create a new user session.
        
        Args:
            mud_name: Name of the MUD
            user_name: Name of the user
            
        Returns:
            New user session
        """
        session_id = str(uuid.uuid4())
        session = UserSession(
            session_id=session_id,
            mud_name=mud_name,
            user_name=user_name
        )
        
        async with self.session_lock:
            self.sessions[session_id] = session
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a user session.
        
        Args:
            session_id: Session ID
            
        Returns:
            User session or None if not found
        """
        async with self.session_lock:
            session = self.sessions.get(session_id)
            if session:
                session.update_activity()
            return session
    
    async def remove_session(self, session_id: str):
        """Remove a user session.
        
        Args:
            session_id: Session ID
        """
        async with self.session_lock:
            self.sessions.pop(session_id, None)
    
    async def get_active_sessions(self) -> List[UserSession]:
        """Get list of active sessions.
        
        Returns:
            List of active user sessions
        """
        cutoff = datetime.now() - timedelta(hours=1)
        
        async with self.session_lock:
            return [
                session for session in self.sessions.values()
                if session.last_activity > cutoff
            ]
    
    async def save_state(self):
        """Save persistent state to disk."""
        if not self.persistence_dir:
            return
        
        # Save mudlist
        async with self.mudlist_lock:
            mudlist_data = {
                'mudlist_id': self.mudlist_id,
                'muds': {
                    name: {
                        'name': mud.name,
                        'address': mud.address,
                        'player_port': mud.player_port,
                        'tcp_port': mud.tcp_port,
                        'services': mud.services,
                        'status': mud.status.value,
                    }
                    for name, mud in self.mudlist.items()
                }
            }
            
            mudlist_file = self.persistence_dir / 'mudlist.json'
            with open(mudlist_file, 'w') as f:
                json.dump(mudlist_data, f, indent=2)
        
        # Save channels
        async with self.channel_lock:
            channel_data = {
                name: {
                    'name': channel.name,
                    'owner': channel.owner,
                    'type': channel.type,
                    'banned_muds': list(channel.banned_muds),
                    'admitted_muds': list(channel.admitted_muds),
                }
                for name, channel in self.channels.items()
            }
            
            channel_file = self.persistence_dir / 'channels.json'
            with open(channel_file, 'w') as f:
                json.dump(channel_data, f, indent=2)
    
    async def load_state(self):
        """Load persistent state from disk."""
        if not self.persistence_dir:
            return
        
        # Load mudlist
        mudlist_file = self.persistence_dir / 'mudlist.json'
        if mudlist_file.exists():
            try:
                with open(mudlist_file, 'r') as f:
                    mudlist_data = json.load(f)
                
                async with self.mudlist_lock:
                    self.mudlist_id = mudlist_data.get('mudlist_id', 0)
                    
                    for mud_name, mud_data in mudlist_data.get('muds', {}).items():
                        mud = MudInfo(
                            name=mud_data['name'],
                            address=mud_data['address'],
                            player_port=mud_data['player_port'],
                            tcp_port=mud_data.get('tcp_port', 0),
                            services=mud_data.get('services', {}),
                            status=MudStatus(mud_data.get('status', 'unknown'))
                        )
                        self.mudlist[mud_name] = mud
            except Exception as e:
                # Log error but continue
                print(f"Error loading mudlist: {e}")
        
        # Load channels
        channel_file = self.persistence_dir / 'channels.json'
        if channel_file.exists():
            try:
                with open(channel_file, 'r') as f:
                    channel_data = json.load(f)
                
                async with self.channel_lock:
                    for channel_name, data in channel_data.items():
                        channel = ChannelInfo(
                            name=data['name'],
                            owner=data.get('owner', ''),
                            type=data.get('type', 0),
                            banned_muds=set(data.get('banned_muds', [])),
                            admitted_muds=set(data.get('admitted_muds', []))
                        )
                        self.channels[channel_name] = channel
            except Exception as e:
                # Log error but continue
                print(f"Error loading channels: {e}")
    
    async def _periodic_cleanup(self):
        """Periodically clean up expired cache entries and sessions."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Clean up cache
                await self.cache.cleanup()
                
                # Clean up old sessions (>24 hours inactive)
                cutoff = datetime.now() - timedelta(hours=24)
                
                async with self.session_lock:
                    expired_sessions = [
                        session_id for session_id, session in self.sessions.items()
                        if session.last_activity < cutoff
                    ]
                    for session_id in expired_sessions:
                        del self.sessions[session_id]
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue
                print(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)  # Wait before retrying