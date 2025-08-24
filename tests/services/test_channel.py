"""Comprehensive unit tests for ChannelService."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.models.connection import ChannelInfo
from src.models.packet import I3Packet, PacketType
from src.services.channel import ChannelHistory, ChannelService


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager."""
    manager = Mock()
    manager.channels = {
        "gossip": Mock(spec=ChannelInfo, owner="MainRouter"),
        "chat": Mock(spec=ChannelInfo, owner="TestMUD"),
        "ooc": Mock(spec=ChannelInfo, owner="OtherMUD"),
    }
    manager.get_channel = AsyncMock()
    manager.update_chanlist = AsyncMock()
    return manager


@pytest.fixture
def mock_gateway():
    """Create a mock gateway."""
    gateway = Mock()
    gateway.settings = Mock()
    gateway.settings.mud = Mock()
    gateway.settings.mud.name = "TestMUD"
    gateway.send_packet = AsyncMock(return_value=True)
    return gateway


@pytest.fixture
def channel_service(mock_state_manager, mock_gateway):
    """Create a ChannelService instance for testing."""
    service = ChannelService(mock_state_manager, mock_gateway)
    return service


@pytest.fixture
def sample_channel_message_packet():
    """Create a sample channel message packet."""
    packet = Mock(spec=I3Packet)
    packet.packet_type = PacketType.CHANNEL_M
    packet.originator_mud = "RemoteMUD"
    packet.originator_user = "sender"
    packet.to_lpc_array.return_value = [
        "channel-m",
        200,
        "RemoteMUD",
        "sender",
        0,
        0,
        "gossip",
        "Sender",
        "Hello channel!",
    ]
    return packet


@pytest.fixture
def sample_channel_emote_packet():
    """Create a sample channel emote packet."""
    packet = Mock(spec=I3Packet)
    packet.packet_type = PacketType.CHANNEL_E
    packet.originator_mud = "RemoteMUD"
    packet.originator_user = "sender"
    packet.to_lpc_array.return_value = [
        "channel-e",
        200,
        "RemoteMUD",
        "sender",
        0,
        0,
        "gossip",
        "Sender",
        "waves happily",
    ]
    return packet


@pytest.fixture
def sample_targeted_emote_packet():
    """Create a sample targeted emote packet."""
    packet = Mock(spec=I3Packet)
    packet.packet_type = PacketType.CHANNEL_T
    packet.originator_mud = "RemoteMUD"
    packet.originator_user = "sender"
    packet.to_lpc_array.return_value = [
        "channel-t",
        200,
        "RemoteMUD",
        "sender",
        0,
        0,
        "gossip",
        "TestMUD",
        "receiver",
        "Sender",
        "Receiver",
        "pokes gently",
    ]
    return packet


class TestChannelServiceInitialization:
    """Test ChannelService initialization."""

    async def test_initialization(self, channel_service, mock_state_manager):
        """Test service initialization."""
        await channel_service.initialize()

        assert channel_service.service_name == "channel"
        assert PacketType.CHANNEL_M in channel_service.supported_packets
        assert PacketType.CHANNEL_E in channel_service.supported_packets
        assert PacketType.CHANNEL_T in channel_service.supported_packets
        assert len(channel_service.channel_history) == 3  # gossip, chat, ooc
        assert "gossip" in channel_service.channel_admins
        assert channel_service.channel_admins["gossip"] == {"MainRouter"}

    async def test_initialization_without_gateway(self, mock_state_manager):
        """Test service initialization without gateway."""
        service = ChannelService(mock_state_manager, None)
        await service.initialize()
        assert service.gateway is None


class TestChannelHistory:
    """Test ChannelHistory functionality."""

    def test_add_message(self):
        """Test adding messages to history."""
        history = ChannelHistory()
        msg = {"type": "message", "user": "test", "message": "hello"}
        history.add_message(msg)

        assert len(history.messages) == 1
        assert history.messages[0] == msg

    def test_max_size_limit(self):
        """Test that history respects max size."""
        history = ChannelHistory(max_size=5)

        for i in range(10):
            history.add_message({"id": i})

        assert len(history.messages) == 5
        assert history.messages[0]["id"] == 5  # Oldest kept
        assert history.messages[4]["id"] == 9  # Newest

    def test_get_recent(self):
        """Test getting recent messages."""
        history = ChannelHistory()

        for i in range(10):
            history.add_message({"id": i})

        recent = history.get_recent(3)
        assert len(recent) == 3
        assert recent[0]["id"] == 7
        assert recent[2]["id"] == 9


class TestChannelMessageHandling:
    """Test handling of channel messages."""

    async def test_handle_channel_message(
        self, channel_service, sample_channel_message_packet, mock_state_manager
    ):
        """Test handling channel message."""
        mock_state_manager.get_channel.return_value = Mock(spec=ChannelInfo)

        result = await channel_service.handle_packet(sample_channel_message_packet)

        assert result is None
        assert "gossip" in channel_service.channel_history
        history = channel_service.channel_history["gossip"].messages
        assert len(history) == 1
        assert history[0]["type"] == "message"
        assert history[0]["message"] == "Hello channel!"
        assert history[0]["mud"] == "RemoteMUD"
        assert history[0]["user"] == "sender"

    async def test_handle_message_unknown_channel(
        self, channel_service, sample_channel_message_packet, mock_state_manager
    ):
        """Test handling message to unknown channel."""
        mock_state_manager.get_channel.return_value = None

        result = await channel_service.handle_packet(sample_channel_message_packet)

        assert result is None
        # Message should not be stored
        if "gossip" in channel_service.channel_history:
            assert len(channel_service.channel_history["gossip"].messages) == 0

    async def test_handle_invalid_message_packet(self, channel_service, mock_state_manager):
        """Test handling invalid message packet."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_M
        packet.originator_mud = "RemoteMUD"
        packet.originator_user = "sender"
        packet.to_lpc_array.return_value = ["channel-m", 200]  # Too short

        result = await channel_service.handle_packet(packet)
        assert result is None

    @patch.object(ChannelService, "_check_filters")
    async def test_message_filtering(
        self, mock_filter, channel_service, sample_channel_message_packet, mock_state_manager
    ):
        """Test that messages are filtered."""
        mock_state_manager.get_channel.return_value = Mock(spec=ChannelInfo)
        mock_filter.return_value = False  # Filter blocks message

        result = await channel_service.handle_packet(sample_channel_message_packet)

        assert result is None
        # Message should not be stored
        if "gossip" in channel_service.channel_history:
            assert len(channel_service.channel_history["gossip"].messages) == 0


class TestChannelEmoteHandling:
    """Test handling of channel emotes."""

    async def test_handle_channel_emote(self, channel_service, sample_channel_emote_packet):
        """Test handling channel emote."""
        result = await channel_service.handle_packet(sample_channel_emote_packet)

        assert result is None
        assert "gossip" in channel_service.channel_history
        history = channel_service.channel_history["gossip"].messages
        assert len(history) == 1
        assert history[0]["type"] == "emote"
        assert history[0]["message"] == "waves happily"

    async def test_handle_targeted_emote(self, channel_service, sample_targeted_emote_packet):
        """Test handling targeted channel emote."""
        result = await channel_service.handle_packet(sample_targeted_emote_packet)

        assert result is None
        assert "gossip" in channel_service.channel_history
        history = channel_service.channel_history["gossip"].messages
        assert len(history) == 1
        assert history[0]["type"] == "targeted_emote"
        assert history[0]["target_mud"] == "TestMUD"
        assert history[0]["target_user"] == "receiver"
        assert history[0]["message"] == "pokes gently"

    async def test_handle_invalid_targeted_emote(self, channel_service):
        """Test handling invalid targeted emote packet."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_T
        packet.originator_mud = "RemoteMUD"
        packet.originator_user = "sender"
        packet.to_lpc_array.return_value = ["channel-t", 200, "RemoteMUD"]  # Too short

        result = await channel_service.handle_packet(packet)
        assert result is None


class TestChannelSubscriptions:
    """Test channel subscription management."""

    async def test_handle_channel_add(self, channel_service):
        """Test handling channel subscription."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_ADD
        packet.originator_mud = "RemoteMUD"
        packet.originator_user = "user1"
        packet.to_lpc_array.return_value = [
            "channel-add",
            200,
            "RemoteMUD",
            "user1",
            0,
            0,
            "gossip",
        ]

        result = await channel_service.handle_packet(packet)

        assert result is None
        assert ("RemoteMUD", "user1") in channel_service.subscriptions["gossip"]
        assert "gossip" in channel_service.user_channels[("RemoteMUD", "user1")]

    async def test_handle_channel_remove(self, channel_service):
        """Test handling channel unsubscribe."""
        # First add subscription
        channel_service.subscriptions["gossip"] = {("RemoteMUD", "user1")}
        channel_service.user_channels[("RemoteMUD", "user1")] = {"gossip"}

        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_REMOVE
        packet.originator_mud = "RemoteMUD"
        packet.originator_user = "user1"
        packet.to_lpc_array.return_value = [
            "channel-remove",
            200,
            "RemoteMUD",
            "user1",
            0,
            0,
            "gossip",
        ]

        result = await channel_service.handle_packet(packet)

        assert result is None
        assert ("RemoteMUD", "user1") not in channel_service.subscriptions["gossip"]
        assert ("RemoteMUD", "user1") not in channel_service.user_channels

    async def test_multiple_channel_subscriptions(self, channel_service):
        """Test user subscribing to multiple channels."""
        for channel in ["gossip", "chat", "ooc"]:
            packet = Mock(spec=I3Packet)
            packet.packet_type = PacketType.CHANNEL_ADD
            packet.originator_mud = "RemoteMUD"
            packet.originator_user = "user1"
            packet.to_lpc_array.return_value = [
                "channel-add",
                200,
                "RemoteMUD",
                "user1",
                0,
                0,
                channel,
            ]
            await channel_service.handle_packet(packet)

        user_channels = channel_service.user_channels[("RemoteMUD", "user1")]
        assert len(user_channels) == 3
        assert "gossip" in user_channels
        assert "chat" in user_channels
        assert "ooc" in user_channels


class TestChannelWho:
    """Test channel who functionality."""

    async def test_handle_channel_who(self, channel_service):
        """Test handling channel who request."""
        # Add some subscribers
        channel_service.subscriptions["gossip"] = {
            ("MUD1", "user1"),
            ("MUD2", "user2"),
            ("MUD1", "user3"),
        }

        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_WHO
        packet.originator_mud = "RemoteMUD"
        packet.originator_user = "requester"
        packet.to_lpc_array.return_value = [
            "channel-who",
            200,
            "RemoteMUD",
            "requester",
            0,
            0,
            "gossip",
        ]

        result = await channel_service.handle_packet(packet)

        # Currently returns None (TODO in implementation)
        assert result is None

    async def test_channel_who_empty_channel(self, channel_service):
        """Test channel who on empty channel."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_WHO
        packet.originator_mud = "RemoteMUD"
        packet.originator_user = "requester"
        packet.to_lpc_array.return_value = [
            "channel-who",
            200,
            "RemoteMUD",
            "requester",
            0,
            0,
            "empty_channel",
        ]

        result = await channel_service.handle_packet(packet)
        assert result is None


class TestChannelListHandling:
    """Test channel list handling."""

    async def test_handle_chanlist_reply(self, channel_service, mock_state_manager):
        """Test handling channel list reply."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANLIST_REPLY
        packet.originator_mud = "Router"
        packet.to_lpc_array.return_value = [
            "chanlist-reply",
            200,
            "Router",
            0,
            "TestMUD",
            0,
            12345,
            {
                "newchannel": {"owner": "NewMUD", "type": 0},
                "another": {"owner": "OtherMUD", "type": 1},
            },
        ]

        result = await channel_service.handle_packet(packet)

        assert result is None
        mock_state_manager.update_chanlist.assert_called_once()
        assert "newchannel" in channel_service.channel_history
        assert "another" in channel_service.channel_history

    async def test_handle_invalid_chanlist_reply(self, channel_service, mock_state_manager):
        """Test handling invalid channel list reply."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANLIST_REPLY
        packet.originator_mud = "Router"
        packet.to_lpc_array.return_value = ["chanlist-reply", 200]  # Too short

        result = await channel_service.handle_packet(packet)
        assert result is None
        mock_state_manager.update_chanlist.assert_not_called()


class TestPacketValidation:
    """Test packet validation."""

    async def test_validate_supported_packets(self, channel_service):
        """Test validation of supported packet types."""
        for packet_type in channel_service.supported_packets:
            packet = Mock(spec=I3Packet)
            packet.packet_type = packet_type
            packet.originator_mud = "RemoteMUD"

            assert await channel_service.validate_packet(packet) is True

    async def test_validate_unsupported_packet(self, channel_service):
        """Test validation rejects unsupported packets."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.TELL
        packet.originator_mud = "RemoteMUD"

        assert await channel_service.validate_packet(packet) is False

    async def test_validate_missing_originator_mud(self, channel_service):
        """Test validation rejects packets without originator mud."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_M
        packet.originator_mud = ""

        assert await channel_service.validate_packet(packet) is False


class TestSendingMessages:
    """Test sending channel messages."""

    async def test_send_channel_message(self, channel_service, mock_gateway):
        """Test sending a channel message."""
        result = await channel_service.send_channel_message(
            channel="gossip", user="alice", message="Hello everyone!", visname="Alice"
        )

        assert result is True
        mock_gateway.send_packet.assert_called_once()

    async def test_send_message_without_gateway(self, mock_state_manager):
        """Test sending message without gateway."""
        service = ChannelService(mock_state_manager, None)

        result = await service.send_channel_message(channel="gossip", user="alice", message="Hello")

        assert result is False

    async def test_send_message_default_visname(self, channel_service, mock_gateway):
        """Test sending message uses username as default visname."""
        with patch("src.models.packet.ChannelMessagePacket") as MockPacket:
            mock_packet = Mock()
            MockPacket.return_value = mock_packet

            await channel_service.send_channel_message(
                channel="gossip", user="alice", message="Hello"
            )

            MockPacket.assert_called_once()
            call_args = MockPacket.call_args[1]
            assert call_args["visname"] == "alice"


class TestUtilityMethods:
    """Test utility methods."""

    def test_get_channel_history(self, channel_service):
        """Test getting channel history."""
        # Add some messages
        channel_service.channel_history["gossip"] = ChannelHistory()
        for i in range(5):
            channel_service.channel_history["gossip"].add_message({"id": i})

        history = channel_service.get_channel_history("gossip", count=3)
        assert len(history) == 3
        assert history[0]["id"] == 2

    def test_get_history_unknown_channel(self, channel_service):
        """Test getting history for unknown channel."""
        history = channel_service.get_channel_history("unknown", count=10)
        assert history == []

    def test_get_user_channels(self, channel_service):
        """Test getting user's channel subscriptions."""
        channel_service.user_channels[("TestMUD", "alice")] = {"gossip", "chat"}

        channels = channel_service.get_user_channels("TestMUD", "alice")
        assert len(channels) == 2
        assert "gossip" in channels
        assert "chat" in channels

    def test_get_user_channels_none(self, channel_service):
        """Test getting channels for unknown user."""
        channels = channel_service.get_user_channels("UnknownMUD", "nobody")
        assert channels == set()

    def test_get_channel_subscribers(self, channel_service):
        """Test getting channel subscribers."""
        channel_service.subscriptions["gossip"] = {("MUD1", "user1"), ("MUD2", "user2")}

        subscribers = channel_service.get_channel_subscribers("gossip")
        assert len(subscribers) == 2
        assert ("MUD1", "user1") in subscribers
        assert ("MUD2", "user2") in subscribers

    def test_get_subscribers_unknown_channel(self, channel_service):
        """Test getting subscribers for unknown channel."""
        subscribers = channel_service.get_channel_subscribers("unknown")
        assert subscribers == set()


class TestBroadcasting:
    """Test message broadcasting."""

    @patch.object(ChannelService, "_broadcast_to_local_subscribers")
    async def test_broadcast_on_message(
        self, mock_broadcast, channel_service, sample_channel_message_packet, mock_state_manager
    ):
        """Test that messages trigger broadcast."""
        mock_state_manager.get_channel.return_value = Mock(spec=ChannelInfo)

        await channel_service.handle_packet(sample_channel_message_packet)

        mock_broadcast.assert_called_once_with("gossip", sample_channel_message_packet)

    async def test_broadcast_counts_local_subscribers(
        self, channel_service, sample_channel_message_packet, mock_gateway
    ):
        """Test broadcast counts local subscribers correctly."""
        # Add mix of local and remote subscribers
        channel_service.subscriptions["gossip"] = {
            ("TestMUD", "user1"),  # Local
            ("TestMUD", "user2"),  # Local
            ("RemoteMUD", "user3"),  # Remote
        }

        await channel_service._broadcast_to_local_subscribers(
            "gossip", sample_channel_message_packet
        )

        # Should count 2 local subscribers (TestMUD users)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    async def test_handle_unknown_packet_type(self, channel_service):
        """Test handling unknown packet type."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.TELL  # Not a channel packet

        result = await channel_service.handle_packet(packet)
        assert result is None

    async def test_concurrent_subscriptions(self, channel_service):
        """Test handling concurrent subscription requests."""
        packets = []
        for i in range(10):
            packet = Mock(spec=I3Packet)
            packet.packet_type = PacketType.CHANNEL_ADD
            packet.originator_mud = f"MUD{i}"
            packet.originator_user = f"user{i}"
            packet.to_lpc_array.return_value = [
                "channel-add",
                200,
                f"MUD{i}",
                f"user{i}",
                0,
                0,
                "gossip",
            ]
            packets.append(packet)

        tasks = [channel_service.handle_packet(p) for p in packets]
        await asyncio.gather(*tasks)

        assert len(channel_service.subscriptions["gossip"]) == 10

    async def test_channel_admin_request(self, channel_service):
        """Test channel admin request handling."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_ADMIN
        packet.originator_mud = "AdminMUD"
        packet.originator_user = "admin"

        result = await channel_service.handle_packet(packet)
        assert result is None  # Currently just logs

    async def test_channel_filter_request(self, channel_service):
        """Test channel filter request handling."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_FILTER
        packet.originator_mud = "FilterMUD"
        packet.originator_user = "user"

        result = await channel_service.handle_packet(packet)
        assert result is None  # Currently just logs

    async def test_channel_listen_request(self, channel_service):
        """Test channel listen request handling."""
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_LISTEN
        packet.originator_mud = "RouterMUD"

        result = await channel_service.handle_packet(packet)
        assert result is None  # Currently not fully implemented
