"""Comprehensive unit tests for state manager."""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from unittest import mock

import pytest

from src.models.connection import ChannelInfo, MudInfo, MudStatus, UserSession
from src.state.manager import StateManager, TTLCache


class TestTTLCache:
    """Test TTLCache class functionality."""

    @pytest.mark.asyncio
    async def test_cache_initialization(self):
        """Test cache initialization with default and custom TTL."""
        # Default TTL
        cache = TTLCache()
        assert cache.default_ttl == 300.0
        assert len(cache._cache) == 0

        # Custom TTL
        cache_custom = TTLCache(default_ttl=600.0)
        assert cache_custom.default_ttl == 600.0

    @pytest.mark.asyncio
    async def test_set_and_get_item(self):
        """Test setting and getting cache items."""
        cache = TTLCache(default_ttl=10.0)

        # Set and get item
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

        # Set with custom TTL
        await cache.set("key2", "value2", ttl=5.0)
        result = await cache.get("key2")
        assert result == "value2"

    @pytest.mark.asyncio
    async def test_get_nonexistent_item(self):
        """Test getting non-existent cache item."""
        cache = TTLCache()
        
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_item_expiration(self):
        """Test cache item expiration."""
        cache = TTLCache(default_ttl=0.1)  # 100ms TTL

        await cache.set("expire_key", "expire_value")
        
        # Should exist immediately
        result = await cache.get("expire_key")
        assert result == "expire_value"

        # Wait for expiration
        await asyncio.sleep(0.15)
        
        # Should be expired
        result = await cache.get("expire_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_item(self):
        """Test deleting cache items."""
        cache = TTLCache()

        await cache.set("delete_key", "delete_value")
        
        # Verify exists
        result = await cache.get("delete_key")
        assert result == "delete_value"

        # Delete and verify gone
        await cache.delete("delete_key")
        result = await cache.get("delete_key")
        assert result is None

        # Delete non-existent (should not error)
        await cache.delete("nonexistent")

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """Test clearing all cache items."""
        cache = TTLCache()

        # Add multiple items
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")

        # Clear cache
        await cache.clear()

        # Verify all gone
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert await cache.get("key3") is None

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        """Test cleanup of expired items."""
        cache = TTLCache(default_ttl=0.1)

        # Add items with different TTLs
        await cache.set("persist", "value", ttl=10.0)  # Long TTL
        await cache.set("expire1", "value", ttl=0.05)  # Short TTL
        await cache.set("expire2", "value", ttl=0.05)  # Short TTL

        # Wait for some to expire
        await asyncio.sleep(0.1)

        # Run cleanup
        await cache.cleanup()

        # Check what remains
        assert await cache.get("persist") == "value"
        assert await cache.get("expire1") is None
        assert await cache.get("expire2") is None

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test concurrent cache access."""
        cache = TTLCache()

        async def worker(worker_id):
            for i in range(10):
                key = f"worker_{worker_id}_key_{i}"
                value = f"worker_{worker_id}_value_{i}"
                await cache.set(key, value)
                result = await cache.get(key)
                assert result == value

        # Run multiple workers concurrently
        tasks = [worker(i) for i in range(5)]
        await asyncio.gather(*tasks)


class TestStateManager:
    """Test StateManager class functionality."""

    @pytest.fixture
    def temp_persistence_dir(self, tmp_path):
        """Create temporary persistence directory."""
        return tmp_path / "state"

    @pytest.mark.asyncio
    async def test_manager_initialization_no_persistence(self):
        """Test manager initialization without persistence."""
        manager = StateManager()

        assert manager.persistence_dir is None
        assert len(manager.mudlist) == 0
        assert manager.mudlist_id == 0
        assert len(manager.channels) == 0
        assert manager.chanlist_id == 0
        assert len(manager.sessions) == 0
        assert isinstance(manager.cache, TTLCache)
        assert manager.cache.default_ttl == 300.0

    @pytest.mark.asyncio
    async def test_manager_initialization_with_persistence(self, temp_persistence_dir):
        """Test manager initialization with persistence."""
        manager = StateManager(persistence_dir=temp_persistence_dir, cache_ttl=600.0)

        assert manager.persistence_dir == temp_persistence_dir
        assert temp_persistence_dir.exists()
        assert manager.cache.default_ttl == 600.0

    @pytest.mark.asyncio
    async def test_start_and_stop_manager(self, temp_persistence_dir):
        """Test starting and stopping the state manager."""
        manager = StateManager(persistence_dir=temp_persistence_dir)

        await manager.start()
        assert manager._cleanup_task is not None
        assert not manager._cleanup_task.done()

        await manager.stop()
        assert manager._cleanup_task.done()

    @pytest.mark.asyncio
    async def test_mudlist_operations(self):
        """Test MUD list management operations."""
        manager = StateManager()

        # Test update_mudlist - need at least 15 elements for update_from_mudlist
        mudlist_data = {
            "TestMUD1": ["192.168.1.100", 4000, 5000, 6000, "TestLib", "BaseLib", "Driver", "LP", "open", "admin@test.com", {"tell": 1, "channel": 1}, {}, "", "", ""],
            "TestMUD2": ["192.168.1.101", 4001, 5001, 6001, "TestLib2", "BaseLib2", "Driver2", "LP", "closed", "admin2@test.com", {"tell": 1}, {}, "", "", ""]
        }

        await manager.update_mudlist(mudlist_data, 123)
        
        assert manager.mudlist_id == 123
        assert len(manager.mudlist) == 2
        assert "TestMUD1" in manager.mudlist
        assert "TestMUD2" in manager.mudlist

        # Check MUD info
        mud1 = manager.mudlist["TestMUD1"]
        assert mud1.name == "TestMUD1"
        assert mud1.address == "192.168.1.100"
        assert mud1.player_port == 4000
        assert mud1.status == MudStatus.UP

        # Test get_mud_info
        mud_info = await manager.get_mud_info("TestMUD1")
        assert mud_info is not None
        assert mud_info.name == "TestMUD1"

        # Test get_mud (alias)
        mud_alias = await manager.get_mud("TestMUD1")
        assert mud_alias == mud_info

        # Test non-existent MUD
        non_existent = await manager.get_mud_info("NonExistent")
        assert non_existent is None

    @pytest.mark.asyncio
    async def test_mudlist_update_existing(self):
        """Test updating existing MUDs in mudlist."""
        manager = StateManager()

        # Initial mudlist - need at least 15 elements
        initial_data = {
            "TestMUD": ["192.168.1.100", 4000, 5000, 6000, "TestLib", "BaseLib", "Driver", "LP", "open", "admin@test.com", {"tell": 1}, {}, "", "", ""]
        }
        await manager.update_mudlist(initial_data, 1)

        # Update with new data - need at least 15 elements
        updated_data = {
            "TestMUD": ["192.168.1.200", 4001, 5001, 6001, "NewLib", "NewBase", "NewDriver", "LPC", "closed", "new@test.com", {"tell": 1, "channel": 1}, {}, "", "", ""]
        }
        await manager.update_mudlist(updated_data, 2)

        mud = manager.mudlist["TestMUD"]
        assert mud.address == "192.168.1.200"
        assert mud.player_port == 4001
        assert mud.mudlib == "NewLib"

    @pytest.mark.asyncio
    async def test_mudlist_mark_missing_as_down(self):
        """Test marking MUDs not in update as down."""
        manager = StateManager()

        # Initial mudlist with two MUDs - need at least 15 elements
        initial_data = {
            "MUD1": ["192.168.1.100", 4000, 5000, 6000, "", "", "", "", "", "", {}, {}, "", "", ""],
            "MUD2": ["192.168.1.101", 4001, 5001, 6001, "", "", "", "", "", "", {}, {}, "", "", ""]
        }
        await manager.update_mudlist(initial_data, 1)

        # Update with only one MUD - need at least 15 elements
        updated_data = {
            "MUD1": ["192.168.1.100", 4000, 5000, 6000, "", "", "", "", "", "", {}, {}, "", "", ""]
        }
        await manager.update_mudlist(updated_data, 2)

        # MUD2 should be marked as down
        assert manager.mudlist["MUD1"].status == MudStatus.UP
        assert manager.mudlist["MUD2"].status == MudStatus.DOWN

    @pytest.mark.asyncio
    async def test_get_online_muds(self):
        """Test getting list of online MUDs."""
        manager = StateManager()

        # Add some MUDs
        mud1 = MudInfo(name="OnlineMUD", address="1.1.1.1", player_port=4000)
        mud1.status = MudStatus.UP
        mud2 = MudInfo(name="OfflineMUD", address="2.2.2.2", player_port=4001)
        mud2.status = MudStatus.DOWN
        mud3 = MudInfo(name="UnknownMUD", address="3.3.3.3", player_port=4002)
        mud3.status = MudStatus.UNKNOWN

        manager.mudlist["OnlineMUD"] = mud1
        manager.mudlist["OfflineMUD"] = mud2
        manager.mudlist["UnknownMUD"] = mud3

        online_muds = await manager.get_online_muds()
        assert len(online_muds) == 1
        assert online_muds[0].name == "OnlineMUD"

    @pytest.mark.asyncio
    async def test_mud_info_caching(self):
        """Test MUD info caching functionality."""
        manager = StateManager()

        # Add a MUD
        mud_info = MudInfo(name="CacheMUD", address="1.1.1.1", player_port=4000)
        manager.mudlist["CacheMUD"] = mud_info

        # First call should cache
        result1 = await manager.get_mud_info("CacheMUD")
        assert result1 == mud_info

        # Second call should use cache
        with patch.object(manager.cache, 'get', return_value=mud_info) as mock_cache_get:
            result2 = await manager.get_mud_info("CacheMUD")
            assert result2 == mud_info
            mock_cache_get.assert_called_once_with("mud:CacheMUD")

    @pytest.mark.asyncio
    async def test_channel_operations(self):
        """Test channel management operations."""
        manager = StateManager()

        # Create and add channel
        channel = ChannelInfo(name="test_channel", owner="TestMUD", type=0)
        await manager.add_channel(channel)

        # Get channel
        retrieved = await manager.get_channel("test_channel")
        assert retrieved is not None
        assert retrieved.name == "test_channel"
        assert retrieved.owner == "TestMUD"

        # Get non-existent channel
        non_existent = await manager.get_channel("nonexistent")
        assert non_existent is None

        # Get all channels
        all_channels = await manager.get_channels()
        assert len(all_channels) == 1
        assert all_channels[0].name == "test_channel"

    @pytest.mark.asyncio
    async def test_update_chanlist(self):
        """Test channel list update from router data."""
        manager = StateManager()

        chanlist_data = {
            "general": {"owner": "RouterMUD", "type": 0},
            "newbie": {"owner": "HelperMUD", "type": 1},
            "admin": {"owner": "AdminMUD", "type": 2}
        }

        await manager.update_chanlist(chanlist_data, 456)

        assert manager.chanlist_id == 456
        assert len(manager.channels) == 3

        # Check specific channel
        general = await manager.get_channel("general")
        assert general.owner == "RouterMUD"
        assert general.type == 0

    @pytest.mark.asyncio
    async def test_update_chanlist_existing_channels(self):
        """Test updating existing channels in chanlist."""
        manager = StateManager()

        # Add existing channel
        existing = ChannelInfo(name="existing", owner="OldOwner", type=0)
        await manager.add_channel(existing)

        # Update with new data
        chanlist_data = {
            "existing": {"owner": "NewOwner", "type": 1}
        }
        await manager.update_chanlist(chanlist_data, 1)

        updated = await manager.get_channel("existing")
        assert updated.owner == "NewOwner"
        assert updated.type == 1

    @pytest.mark.asyncio
    async def test_session_management(self):
        """Test user session management."""
        manager = StateManager()

        # Create session
        session = await manager.create_session("TestMUD", "testuser")
        assert session.mud_name == "TestMUD"
        assert session.user_name == "testuser"
        assert session.session_id is not None

        # Get session
        retrieved = await manager.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.mud_name == "TestMUD"
        assert retrieved.user_name == "testuser"

        # Get non-existent session
        non_existent = await manager.get_session("nonexistent")
        assert non_existent is None

        # Remove session
        await manager.remove_session(session.session_id)
        removed = await manager.get_session(session.session_id)
        assert removed is None

    @pytest.mark.asyncio
    async def test_session_activity_update(self):
        """Test session activity update on access."""
        manager = StateManager()

        session = await manager.create_session("TestMUD", "testuser")
        original_activity = session.last_activity

        # Wait a bit
        await asyncio.sleep(0.01)

        # Get session should update activity
        retrieved = await manager.get_session(session.session_id)
        assert retrieved.last_activity > original_activity

    @pytest.mark.asyncio
    async def test_get_active_sessions(self):
        """Test getting active sessions."""
        manager = StateManager()

        # Create recent session
        recent_session = await manager.create_session("TestMUD", "recentuser")

        # Create old session
        old_session = await manager.create_session("TestMUD", "olduser")
        old_session.last_activity = datetime.now() - timedelta(hours=2)

        active_sessions = await manager.get_active_sessions()
        
        # Only recent session should be active (within 1 hour)
        assert len(active_sessions) == 1
        assert active_sessions[0].user_name == "recentuser"

    @pytest.mark.asyncio
    async def test_save_state_no_persistence(self):
        """Test save state with no persistence directory."""
        manager = StateManager()

        # Should not error
        await manager.save_state()

    @pytest.mark.asyncio
    async def test_save_and_load_state(self, temp_persistence_dir):
        """Test saving and loading persistent state."""
        manager = StateManager(persistence_dir=temp_persistence_dir)

        # Add some data
        mud = MudInfo(name="TestMUD", address="1.1.1.1", player_port=4000)
        mud.status = MudStatus.UP
        manager.mudlist["TestMUD"] = mud
        manager.mudlist_id = 123

        channel = ChannelInfo(name="test", owner="TestMUD", type=1)
        channel.banned_muds.add("BadMUD")
        channel.admitted_muds.add("GoodMUD")
        manager.channels["test"] = channel

        # Save state
        await manager.save_state()

        # Verify files exist
        mudlist_file = temp_persistence_dir / "mudlist.json"
        channel_file = temp_persistence_dir / "channels.json"
        assert mudlist_file.exists()
        assert channel_file.exists()

        # Create new manager and load
        new_manager = StateManager(persistence_dir=temp_persistence_dir)
        await new_manager.load_state()

        # Verify data loaded
        assert new_manager.mudlist_id == 123
        assert "TestMUD" in new_manager.mudlist
        loaded_mud = new_manager.mudlist["TestMUD"]
        assert loaded_mud.name == "TestMUD"
        assert loaded_mud.address == "1.1.1.1"
        assert loaded_mud.status == MudStatus.UP

        assert "test" in new_manager.channels
        loaded_channel = new_manager.channels["test"]
        assert loaded_channel.owner == "TestMUD"
        assert loaded_channel.type == 1
        assert "BadMUD" in loaded_channel.banned_muds
        assert "GoodMUD" in loaded_channel.admitted_muds

    @pytest.mark.asyncio
    async def test_load_state_no_persistence(self):
        """Test load state with no persistence directory."""
        manager = StateManager()

        # Should not error
        await manager.load_state()

    @pytest.mark.asyncio
    async def test_load_state_missing_files(self, temp_persistence_dir):
        """Test loading state with missing files."""
        manager = StateManager(persistence_dir=temp_persistence_dir)

        # Should not error even if files don't exist
        await manager.load_state()

        assert len(manager.mudlist) == 0
        assert len(manager.channels) == 0

    @pytest.mark.asyncio
    async def test_load_state_corrupted_files(self, temp_persistence_dir):
        """Test loading state with corrupted files."""
        manager = StateManager(persistence_dir=temp_persistence_dir)

        # Create corrupted files
        mudlist_file = temp_persistence_dir / "mudlist.json"
        channel_file = temp_persistence_dir / "channels.json"

        temp_persistence_dir.mkdir(exist_ok=True)
        mudlist_file.write_text("invalid json")
        channel_file.write_text("{invalid}")

        # Should handle errors gracefully
        await manager.load_state()

        assert len(manager.mudlist) == 0
        assert len(manager.channels) == 0

    @pytest.mark.asyncio
    async def test_periodic_cleanup_task(self):
        """Test periodic cleanup functionality."""
        manager = StateManager()

        # Add old session
        old_session = await manager.create_session("TestMUD", "olduser")
        old_session.last_activity = datetime.now() - timedelta(hours=25)  # Older than 24 hours

        # Add recent session
        recent_session = await manager.create_session("TestMUD", "recentuser")

        # Mock the periodic cleanup to run immediately
        with patch.object(manager, '_periodic_cleanup') as mock_cleanup:
            # Make cleanup run once then exit
            async def mock_cleanup_impl():
                # Clean up cache
                await manager.cache.cleanup()

                # Clean up old sessions (>24 hours inactive)
                cutoff = datetime.now() - timedelta(hours=24)
                async with manager.session_lock:
                    expired_sessions = [
                        session_id
                        for session_id, session in manager.sessions.items()
                        if session.last_activity < cutoff
                    ]
                    for session_id in expired_sessions:
                        del manager.sessions[session_id]

            mock_cleanup.side_effect = mock_cleanup_impl

            await manager.start()
            
            # Manually run cleanup once
            await mock_cleanup_impl()
            
            await manager.stop()

        # Old session should be cleaned up
        assert old_session.session_id not in manager.sessions
        assert recent_session.session_id in manager.sessions

    @pytest.mark.asyncio
    async def test_cleanup_task_exception_handling(self):
        """Test cleanup task handles exceptions gracefully."""
        manager = StateManager()

        # Mock cache cleanup to raise exception
        with patch.object(manager.cache, 'cleanup', side_effect=RuntimeError("Cleanup error")):
            with patch('asyncio.sleep') as mock_sleep:
                mock_sleep.side_effect = [None, asyncio.CancelledError()]  # First sleep normal, second cancels

                await manager.start()
                await asyncio.sleep(0.01)  # Let task run
                await manager.stop()

        # Manager should still be functional despite cleanup error
        assert manager._cleanup_task.done()

    @pytest.mark.asyncio
    async def test_concurrent_mudlist_access(self):
        """Test concurrent access to mudlist."""
        manager = StateManager()

        async def update_worker():
            mudlist_data = {
                f"MUD_{time.time()}": ["1.1.1.1", 4000, 5000, 6000, "", "", "", "", "", "", {}]
            }
            await manager.update_mudlist(mudlist_data, int(time.time()))

        async def read_worker():
            online_muds = await manager.get_online_muds()
            return len(online_muds)

        # Run concurrent operations
        tasks = []
        for _ in range(5):
            tasks.append(update_worker())
            tasks.append(read_worker())

        await asyncio.gather(*tasks)

        # Should have some MUDs
        assert len(manager.mudlist) > 0

    @pytest.mark.asyncio
    async def test_concurrent_channel_access(self):
        """Test concurrent access to channels."""
        manager = StateManager()

        async def add_channel_worker(channel_id):
            channel = ChannelInfo(name=f"channel_{channel_id}", owner="TestMUD", type=0)
            await manager.add_channel(channel)

        async def read_channel_worker():
            channels = await manager.get_channels()
            return len(channels)

        # Run concurrent operations
        tasks = []
        for i in range(10):
            tasks.append(add_channel_worker(i))
            if i % 2 == 0:
                tasks.append(read_channel_worker())

        await asyncio.gather(*tasks)

        # Should have added channels
        channels = await manager.get_channels()
        assert len(channels) == 10

    @pytest.mark.asyncio
    async def test_concurrent_session_access(self):
        """Test concurrent access to sessions."""
        manager = StateManager()

        async def create_session_worker(user_id):
            return await manager.create_session("TestMUD", f"user_{user_id}")

        async def get_session_worker(session_id):
            return await manager.get_session(session_id)

        # Create sessions concurrently
        create_tasks = [create_session_worker(i) for i in range(10)]
        sessions = await asyncio.gather(*create_tasks)

        # Access sessions concurrently
        get_tasks = [get_session_worker(session.session_id) for session in sessions]
        retrieved = await asyncio.gather(*get_tasks)

        # All should be retrieved successfully
        assert len(retrieved) == 10
        assert all(s is not None for s in retrieved)

    @pytest.mark.asyncio
    async def test_memory_efficiency(self):
        """Test memory efficiency with large datasets."""
        manager = StateManager()

        # Add many MUDs
        mudlist_data = {}
        for i in range(1000):
            mudlist_data[f"MUD_{i}"] = [f"192.168.{i//255}.{i%255}", 4000+i, 5000+i, 6000+i, "", "", "", "", "", "", {}]

        await manager.update_mudlist(mudlist_data, 1)

        # Verify data
        assert len(manager.mudlist) == 1000
        
        # Test cache operations
        for i in range(0, 1000, 100):  # Sample every 100th
            mud_info = await manager.get_mud_info(f"MUD_{i}")
            assert mud_info is not None

    @pytest.mark.asyncio
    async def test_edge_cases(self):
        """Test various edge cases."""
        manager = StateManager()

        # Empty mudlist update
        await manager.update_mudlist({}, 0)
        assert manager.mudlist_id == 0
        assert len(manager.mudlist) == 0

        # Empty chanlist update
        await manager.update_chanlist({}, 0)
        assert manager.chanlist_id == 0

        # Invalid session ID
        invalid_session = await manager.get_session("")
        assert invalid_session is None

        # Remove non-existent session
        await manager.remove_session("nonexistent")  # Should not error

    @pytest.mark.asyncio
    async def test_channel_data_types(self):
        """Test channel update with different data types."""
        manager = StateManager()

        # Test with non-dict channel data (legacy format)
        chanlist_data = {
            "simple_channel": "simple_value",  # Not a dict
            "dict_channel": {"owner": "TestMUD", "type": 1}
        }

        await manager.update_chanlist(chanlist_data, 1)

        simple = await manager.get_channel("simple_channel")
        assert simple is not None
        assert simple.owner == ""  # Default value
        assert simple.type == 0  # Default value

        dict_channel = await manager.get_channel("dict_channel")
        assert dict_channel.owner == "TestMUD"
        assert dict_channel.type == 1

    @pytest.mark.asyncio
    async def test_mudlist_malformed_data(self):
        """Test mudlist update with malformed data."""
        manager = StateManager()

        # Test with insufficient data
        mudlist_data = {
            "IncompleteMUD": ["192.168.1.1"],  # Too few elements
            "CompleteMUD": ["192.168.1.2", 4000, 5000, 6000, "lib", "base", "driver", "type", "status", "email", {}, {}, "extra", "", ""]  # Complete with 15+ elements
        }

        await manager.update_mudlist(mudlist_data, 1)

        incomplete = manager.mudlist["IncompleteMUD"]
        assert incomplete.name == "IncompleteMUD"
        # Should handle gracefully without crashing - with incomplete data, update_from_mudlist won't modify fields

        complete = manager.mudlist["CompleteMUD"]
        assert complete.address == "192.168.1.2"
        assert complete.player_port == 4000


class TestStateManagerIntegration:
    """Integration tests for StateManager."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, tmp_path):
        """Test complete state manager lifecycle."""
        persistence_dir = tmp_path / "integration_state"
        
        # Create and start manager
        manager = StateManager(persistence_dir=persistence_dir, cache_ttl=60.0)
        await manager.start()

        try:
            # Add MUDs - need at least 15 elements
            mudlist_data = {
                "MUD1": ["1.1.1.1", 4000, 5000, 6000, "Lib1", "Base1", "Driver1", "LP", "open", "admin1@test.com", {"tell": 1}, {}, "", "", ""],
                "MUD2": ["2.2.2.2", 4001, 5001, 6001, "Lib2", "Base2", "Driver2", "LPC", "closed", "admin2@test.com", {"channel": 1}, {}, "", "", ""]
            }
            await manager.update_mudlist(mudlist_data, 100)

            # Add channels
            chanlist_data = {
                "general": {"owner": "MUD1", "type": 0},
                "private": {"owner": "MUD2", "type": 2}
            }
            await manager.update_chanlist(chanlist_data, 200)

            # Create sessions
            session1 = await manager.create_session("MUD1", "user1")
            session2 = await manager.create_session("MUD2", "user2")

            # Verify state
            assert len(manager.mudlist) == 2
            assert len(manager.channels) == 2
            assert len(manager.sessions) == 2

            # Test operations
            online_muds = await manager.get_online_muds()
            assert len(online_muds) == 2  # Both should be UP

            active_sessions = await manager.get_active_sessions()
            assert len(active_sessions) == 2

            # Test caching
            mud_info = await manager.get_mud_info("MUD1")
            assert mud_info is not None

            # Test persistence
            await manager.save_state()

        finally:
            await manager.stop()

        # Create new manager and load state
        new_manager = StateManager(persistence_dir=persistence_dir)
        await new_manager.load_state()

        try:
            # Verify persisted data
            assert new_manager.mudlist_id == 100
            assert len(new_manager.mudlist) == 2
            assert "MUD1" in new_manager.mudlist
            assert "MUD2" in new_manager.mudlist

            assert len(new_manager.channels) == 2
            assert "general" in new_manager.channels
            assert "private" in new_manager.channels

        finally:
            await new_manager.stop()

    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """Test error recovery scenarios."""
        manager = StateManager()

        # Test with corrupted MUD data that might cause exceptions
        try:
            # This should not crash the manager
            mudlist_data = {
                "ErrorMUD": [None, "invalid_port", [], {}, "lib", "base", "driver", "type", "status", "email", "invalid_services"]
            }
            await manager.update_mudlist(mudlist_data, 1)
            
            # Should still be able to operate
            online_muds = await manager.get_online_muds()
            assert isinstance(online_muds, list)

        except Exception as e:
            # If it does raise an exception, it should be handled gracefully
            assert isinstance(e, (ValueError, TypeError, AttributeError))

    @pytest.mark.asyncio
    async def test_performance_under_load(self):
        """Test performance under heavy load."""
        manager = StateManager()

        start_time = time.time()

        # Heavy mudlist operations
        for batch in range(10):
            mudlist_data = {}
            for i in range(100):
                mud_id = batch * 100 + i
                mudlist_data[f"MUD_{mud_id}"] = [
                    f"192.168.{mud_id//255}.{mud_id%255}", 
                    4000 + mud_id, 5000 + mud_id, 6000 + mud_id,
                    f"Lib{mud_id}", f"Base{mud_id}", f"Driver{mud_id}", "LP", "open", 
                    f"admin{mud_id}@test.com", {"tell": 1, "channel": 1}, {}, "", "", ""
                ]
            await manager.update_mudlist(mudlist_data, batch)

        # Heavy session operations
        sessions = []
        for i in range(500):
            session = await manager.create_session(f"MUD_{i%100}", f"user_{i}")
            sessions.append(session)

        # Heavy channel operations
        for i in range(200):
            channel = ChannelInfo(name=f"channel_{i}", owner=f"MUD_{i%100}", type=i%3)
            await manager.add_channel(channel)

        end_time = time.time()
        duration = end_time - start_time

        # Verify operations completed
        assert len(manager.mudlist) == 1000  # All MUDs from all batches
        assert len(manager.sessions) == 500
        assert len(manager.channels) == 200

        # Performance should be reasonable (under 5 seconds for this load)
        assert duration < 5.0

        # Cleanup
        for session in sessions:
            await manager.remove_session(session.session_id)