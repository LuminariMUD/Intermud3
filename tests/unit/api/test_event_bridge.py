"""Tests for the event bridge system."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.event_bridge import EventBridge, event_bridge
from src.api.events import EventType
from src.models.packet import (
    ChannelMessagePacket,
    ChannelPacket,
    EmotetoPacket,
    ErrorPacket,
    PacketType,
    TellPacket,
)


@pytest.fixture
def bridge():
    """Create event bridge for testing."""
    return EventBridge()


@pytest.fixture
def mock_dispatcher():
    """Create mock event dispatcher."""
    dispatcher = MagicMock()
    dispatcher.create_event = MagicMock()
    dispatcher.dispatch = AsyncMock()
    return dispatcher


class TestEventBridge:
    """Test EventBridge class."""

    def test_bridge_initialization(self, bridge):
        """Test event bridge initialization."""
        assert bridge.enabled is False
        assert bridge.stats["packets_processed"] == 0
        assert bridge.stats["events_generated"] == 0
        assert bridge.stats["errors"] == 0

    def test_start_stop(self, bridge):
        """Test starting and stopping the bridge."""
        assert bridge.enabled is False

        bridge.start()
        assert bridge.enabled is True

        bridge.stop()
        assert bridge.enabled is False

    @pytest.mark.asyncio
    async def test_process_packet_disabled(self, bridge):
        """Test processing packet when bridge is disabled."""
        packet_data = {
            "ttl": 200,
            "originator_mud": "OtherMUD",
            "originator_user": "alice",
            "target_mud": "TestMUD",
            "target_user": "bob",
        }

        packet = TellPacket(**packet_data, visname="Alice", message="Hello")

        # Bridge is disabled by default
        await bridge.process_incoming_packet(packet)

        # Stats should not change
        assert bridge.stats["packets_processed"] == 0
        assert bridge.stats["events_generated"] == 0

    @pytest.mark.asyncio
    async def test_process_tell_packet(self, bridge):
        """Test processing tell packet."""
        bridge.start()

        packet_data = {
            "ttl": 200,
            "originator_mud": "OtherMUD",
            "originator_user": "alice",
            "target_mud": "TestMUD",
            "target_user": "bob",
        }

        packet = TellPacket(**packet_data, visname="Alice", message="Hello")

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock()

            await bridge.process_incoming_packet(packet)

            # Verify event was created and dispatched
            mock_dispatcher.create_event.assert_called_once_with(
                EventType.TELL_RECEIVED,
                {
                    "from_mud": "OtherMUD",
                    "from_user": "alice",
                    "to_user": "bob",
                    "message": "Hello",
                    "visname": "Alice",
                },
                priority=3,
                ttl=300,
            )
            mock_dispatcher.dispatch.assert_called_once_with(mock_event)

            # Verify stats updated
            assert bridge.stats["packets_processed"] == 1
            assert bridge.stats["events_generated"] == 1

    @pytest.mark.asyncio
    async def test_process_emoteto_packet(self, bridge):
        """Test processing emoteto packet."""
        bridge.start()

        packet_data = {
            "ttl": 200,
            "originator_mud": "OtherMUD",
            "originator_user": "alice",
            "target_mud": "TestMUD",
            "target_user": "bob",
        }

        packet = EmotetoPacket(**packet_data, visname="Alice", message="waves at $N")

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock()

            await bridge.process_incoming_packet(packet)

            # Verify event was created and dispatched
            mock_dispatcher.create_event.assert_called_once_with(
                EventType.EMOTETO_RECEIVED,
                {
                    "from_mud": "OtherMUD",
                    "from_user": "alice",
                    "to_user": "bob",
                    "message": "waves at $N",
                    "visname": "Alice",
                },
                priority=3,
                ttl=300,
            )
            mock_dispatcher.dispatch.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_process_channel_message_packet(self, bridge):
        """Test processing channel message packet."""
        bridge.start()

        packet_data = {
            "ttl": 200,
            "originator_mud": "OtherMUD",
            "originator_user": "alice",
            "target_mud": "0",
            "target_user": "",
        }

        packet = ChannelMessagePacket(
            **packet_data, channel="chat", visname="Alice", message="Hello everyone!"
        )

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock()

            await bridge.process_incoming_packet(packet)

            # Verify event was created and dispatched
            mock_dispatcher.create_event.assert_called_once_with(
                EventType.CHANNEL_MESSAGE,
                {
                    "channel": "chat",
                    "from_mud": "OtherMUD",
                    "from_user": "alice",
                    "message": "Hello everyone!",
                    "visname": "Alice",
                },
                priority=5,
                ttl=60,
            )
            mock_dispatcher.dispatch.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_process_channel_emote_packet(self, bridge):
        """Test processing channel emote packet."""
        bridge.start()

        packet_data = {
            "packet_type": PacketType.CHANNEL_E,
            "ttl": 200,
            "originator_mud": "OtherMUD",
            "originator_user": "alice",
            "target_mud": "0",
            "target_user": "",
        }

        packet = ChannelPacket(**packet_data, channel="chat", message="waves to everyone")

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock()

            await bridge.process_incoming_packet(packet)

            # Verify event was created and dispatched
            mock_dispatcher.create_event.assert_called_once_with(
                EventType.CHANNEL_EMOTE,
                {
                    "channel": "chat",
                    "from_mud": "OtherMUD",
                    "from_user": "alice",
                    "message": "waves to everyone",
                    "visname": "alice",  # Falls back to originator_user
                },
                priority=5,
                ttl=60,
            )
            mock_dispatcher.dispatch.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_process_error_packet(self, bridge):
        """Test processing error packet."""
        bridge.start()

        packet_data = {
            "ttl": 200,
            "originator_mud": "RouterMUD",
            "originator_user": "",
            "target_mud": "TestMUD",
            "target_user": "",
        }

        packet = ErrorPacket(
            **packet_data, error_code="unk-user", error_message="Unknown user", bad_packet=[]
        )

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock()

            await bridge.process_incoming_packet(packet)

            # Verify event was created and dispatched
            mock_dispatcher.create_event.assert_called_once_with(
                EventType.ERROR_OCCURRED,
                {
                    "error_code": "unk-user",
                    "error_message": "Unknown user",
                    "from_mud": "RouterMUD",
                    "context": "i3_packet_error",
                },
                priority=2,
                ttl=600,
            )
            mock_dispatcher.dispatch.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_process_unknown_packet_type(self, bridge):
        """Test processing unknown packet type."""
        bridge.start()

        packet_data = {
            "packet_type": PacketType.MUDLIST,  # Not handled by bridge
            "ttl": 200,
            "originator_mud": "RouterMUD",
            "originator_user": "",
            "target_mud": "TestMUD",
            "target_user": "",
        }

        # Create a mock packet with unknown type
        packet = MagicMock()
        packet.packet_type = PacketType.MUDLIST

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_dispatcher.create_event = MagicMock()
            mock_dispatcher.dispatch = AsyncMock()

            await bridge.process_incoming_packet(packet)

            # Should process packet but not create events
            assert bridge.stats["packets_processed"] == 1
            assert bridge.stats["events_generated"] == 0
            mock_dispatcher.create_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_packet_error_handling(self, bridge):
        """Test error handling during packet processing."""
        bridge.start()

        packet_data = {
            "ttl": 200,
            "originator_mud": "OtherMUD",
            "originator_user": "alice",
            "target_mud": "TestMUD",
            "target_user": "bob",
        }

        packet = TellPacket(**packet_data, visname="Alice", message="Hello")

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_dispatcher.create_event.side_effect = Exception("Test error")

            # Should not raise, but increment error count
            await bridge.process_incoming_packet(packet)

            assert bridge.stats["packets_processed"] == 1
            assert bridge.stats["events_generated"] == 0
            assert bridge.stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_notify_mud_status_online(self, bridge):
        """Test notifying about MUD coming online."""
        bridge.start()

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock()

            await bridge.notify_mud_status("NewMUD", True, {"port": 4000})

            # Verify event was created and dispatched
            mock_dispatcher.create_event.assert_called_once_with(
                EventType.MUD_ONLINE,
                {"mud_name": "NewMUD", "status": "online", "info": {"port": 4000}},
                priority=6,
                ttl=300,
            )
            mock_dispatcher.dispatch.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_notify_mud_status_offline(self, bridge):
        """Test notifying about MUD going offline."""
        bridge.start()

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock()

            await bridge.notify_mud_status("OldMUD", False)

            # Verify event was created and dispatched
            mock_dispatcher.create_event.assert_called_once_with(
                EventType.MUD_OFFLINE,
                {"mud_name": "OldMUD", "status": "offline"},
                priority=6,
                ttl=300,
            )
            mock_dispatcher.dispatch.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_notify_channel_activity_joined(self, bridge):
        """Test notifying about user joining channel."""
        bridge.start()

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock()

            await bridge.notify_channel_activity("chat", "alice", "TestMUD", "joined")

            # Verify event was created and dispatched
            mock_dispatcher.create_event.assert_called_once_with(
                EventType.USER_JOINED_CHANNEL,
                {"channel": "chat", "user": "alice", "mud": "TestMUD", "action": "joined"},
                priority=7,
                ttl=60,
            )
            mock_dispatcher.dispatch.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_notify_channel_activity_left(self, bridge):
        """Test notifying about user leaving channel."""
        bridge.start()

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock()

            await bridge.notify_channel_activity("chat", "alice", "TestMUD", "left")

            # Verify event was created and dispatched
            mock_dispatcher.create_event.assert_called_once_with(
                EventType.USER_LEFT_CHANNEL,
                {"channel": "chat", "user": "alice", "mud": "TestMUD", "action": "left"},
                priority=7,
                ttl=60,
            )
            mock_dispatcher.dispatch.assert_called_once_with(mock_event)

    @pytest.mark.asyncio
    async def test_notify_gateway_reconnect(self, bridge):
        """Test notifying about gateway reconnection."""
        bridge.start()

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock()

            await bridge.notify_gateway_reconnect()

            # Verify event was created and dispatched
            mock_dispatcher.create_event.assert_called_once_with(
                EventType.GATEWAY_RECONNECTED,
                {"message": "Gateway reconnected to I3 router", "status": "connected"},
                priority=1,
                ttl=None,
            )
            mock_dispatcher.dispatch.assert_called_once_with(mock_event)

    def test_get_stats(self, bridge):
        """Test getting bridge statistics."""
        bridge.start()
        bridge.stats["packets_processed"] = 10
        bridge.stats["events_generated"] = 8
        bridge.stats["errors"] = 2

        stats = bridge.get_stats()

        assert stats["packets_processed"] == 10
        assert stats["events_generated"] == 8
        assert stats["errors"] == 2
        assert stats["enabled"] is True


class TestGlobalEventBridge:
    """Test global event bridge instance."""

    def test_global_instance_exists(self):
        """Test that global event bridge instance exists."""
        assert event_bridge is not None
        assert isinstance(event_bridge, EventBridge)

    def test_global_instance_initial_state(self):
        """Test global instance initial state."""
        # Reset to known state
        event_bridge.stop()

        assert event_bridge.enabled is False
        assert event_bridge.stats["packets_processed"] >= 0
        assert event_bridge.stats["events_generated"] >= 0
        assert event_bridge.stats["errors"] >= 0


class TestEventBridgeIntegration:
    """Integration tests for event bridge."""

    @pytest.mark.asyncio
    async def test_packet_processing_flow(self, bridge):
        """Test complete packet processing flow."""
        bridge.start()

        # Create various packet types
        tell_packet_data = {
            "ttl": 200,
            "originator_mud": "OtherMUD",
            "originator_user": "alice",
            "target_mud": "TestMUD",
            "target_user": "bob",
        }

        tell_packet = TellPacket(**tell_packet_data, visname="Alice", message="Hello")

        channel_packet_data = {
            "ttl": 200,
            "originator_mud": "OtherMUD",
            "originator_user": "alice",
            "target_mud": "0",
            "target_user": "",
        }

        channel_packet = ChannelMessagePacket(
            **channel_packet_data, channel="chat", visname="Alice", message="Hi all!"
        )

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock()

            # Process multiple packets
            await bridge.process_incoming_packet(tell_packet)
            await bridge.process_incoming_packet(channel_packet)

            # Verify stats
            assert bridge.stats["packets_processed"] == 2
            assert bridge.stats["events_generated"] == 2
            assert bridge.stats["errors"] == 0

            # Verify both events were created
            assert mock_dispatcher.create_event.call_count == 2
            assert mock_dispatcher.dispatch.call_count == 2

    @pytest.mark.asyncio
    async def test_error_resilience(self, bridge):
        """Test that bridge is resilient to errors."""
        bridge.start()

        packet_data = {
            "ttl": 200,
            "originator_mud": "OtherMUD",
            "originator_user": "alice",
            "target_mud": "TestMUD",
            "target_user": "bob",
        }

        packet = TellPacket(**packet_data, visname="Alice", message="Hello")

        with patch("src.api.event_bridge.event_dispatcher") as mock_dispatcher:
            # First call succeeds, second fails, third succeeds
            mock_event = MagicMock()
            mock_dispatcher.create_event.return_value = mock_event
            mock_dispatcher.dispatch = AsyncMock(side_effect=[None, Exception("Test error"), None])

            # Process packets - should handle error gracefully
            await bridge.process_incoming_packet(packet)  # Success
            await bridge.process_incoming_packet(packet)  # Error
            await bridge.process_incoming_packet(packet)  # Success

            # Verify stats reflect the error
            assert bridge.stats["packets_processed"] == 3
            assert bridge.stats["events_generated"] == 2  # Two successful
            assert bridge.stats["errors"] == 1  # One error
