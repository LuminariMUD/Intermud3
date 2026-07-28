"""Regression coverage for defects found by live in-game command auditing."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.api.api_handlers import APIHandlers
from src.api.session import Session
from src.api.subscriptions import subscription_manager
from src.config.models import MudConfig, RouterConfig, RouterHostConfig, Settings
from src.gateway import I3Gateway
from src.models.packet import (
    ChannelMessagePacket,
    ChannelPacket,
    ErrorPacket,
    FingerPacket,
    LocatePacket,
    PacketType,
    WhoPacket,
)
from src.services.finger import FingerService
from src.services.locate import LocateService
from src.services.who import WhoService
from src.state.manager import StateManager


@pytest.fixture
def gateway_settings(tmp_path):
    """Create a network-free gateway configuration."""
    return Settings(
        mud=MudConfig(
            name="TestLocalMUD",
            port=4000,
            admin_email="staff@example.invalid",
        ),
        router=RouterConfig(
            primary=RouterHostConfig(host="127.0.0.1", port=8099),
        ),
        gateway={"auth": {"enabled": False}},
        api={"enabled": False},
        state={"directory": str(tmp_path / "state")},
    )


@pytest.fixture
def api_session():
    """Create an authenticated MUD API session without a live socket."""
    now = datetime.utcnow()
    return Session(
        session_id="test-api-session",
        mud_name="TestLocalMUD",
        api_key="test-only",
        connected_at=now,
        last_activity=now,
        permissions={"*"},
    )


async def test_incoming_channel_packet_is_consumed_once_not_forwarded(
    gateway_settings,
):
    """An upstream channel broadcast must never be sent back to the router."""
    gateway = I3Gateway(gateway_settings)
    gateway.service_manager.registry.route_packet = AsyncMock(return_value=None)
    gateway.send_packet = AsyncMock(return_value=True)
    packet = ChannelMessagePacket(
        ttl=5,
        originator_mud="RemoteMUD",
        originator_user="Sender",
        target_mud="",
        target_user="",
        channel="I3testers",
        visname="Sender",
        message="one delivery",
    )

    with patch(
        "src.gateway.event_bridge.process_incoming_packet",
        new=AsyncMock(),
    ) as process_event:
        await gateway._process_packet(packet)

    gateway.service_manager.registry.route_packet.assert_awaited_once_with(packet)
    gateway.send_packet.assert_not_awaited()
    process_event.assert_awaited_once_with(packet)
    assert packet.ttl == 5


async def test_generated_service_reply_is_sent_once(gateway_settings):
    """A who/finger/locate service response must leave through the router."""
    gateway = I3Gateway(gateway_settings)
    request = WhoPacket(
        packet_type=PacketType.WHO_REQ,
        ttl=5,
        originator_mud="RemoteMUD",
        originator_user="Requester",
        target_mud="TestLocalMUD",
        target_user="",
        filter_criteria={},
    )
    response = WhoPacket(
        packet_type=PacketType.WHO_REPLY,
        ttl=200,
        originator_mud="TestLocalMUD",
        originator_user="",
        target_mud="RemoteMUD",
        target_user="Requester",
        who_data=[],
    )
    gateway.service_manager.registry.route_packet = AsyncMock(
        return_value=response
    )
    gateway.send_packet = AsyncMock(return_value=True)

    with patch(
        "src.gateway.event_bridge.process_incoming_packet",
        new=AsyncMock(),
    ):
        await gateway._process_packet(request)

    gateway.send_packet.assert_awaited_once_with(response)


async def test_router_error_is_forwarded_to_the_mud(gateway_settings):
    """Router errors should be visible to the in-game requester."""
    gateway = I3Gateway(gateway_settings)
    packet = ErrorPacket(
        ttl=5,
        originator_mud="*i4",
        originator_user="",
        target_mud="TestLocalMUD",
        target_user="Requester",
        error_code="unk-dst",
        error_message="Unknown destination",
        bad_packet=[],
    )

    with (
        patch.object(gateway, "_handle_error", new=AsyncMock()) as handle_error,
        patch(
            "src.gateway.event_bridge.process_incoming_packet",
            new=AsyncMock(),
        ) as process_event,
    ):
        await gateway._process_packet(packet)

    handle_error.assert_awaited_once_with(packet)
    process_event.assert_awaited_once_with(packet)


async def test_enabled_services_are_registered_with_gateway(gateway_settings):
    """Startup should install every service advertised to the I3 router."""
    gateway = I3Gateway(gateway_settings)

    await gateway._register_services()

    services = {
        service.service_name: service
        for service in gateway.service_manager.registry.get_services()
    }
    assert set(services) == {"tell", "channel", "who", "finger", "locate"}
    assert all(service.gateway is gateway for service in services.values())
    await gateway.service_manager.registry.shutdown_all()


async def test_channel_listen_packet_uses_protocol_zero_addresses(
    gateway_settings, api_session
):
    """Join/leave must emit the canonical channel-listen packet shape."""
    gateway = I3Gateway(gateway_settings)
    gateway.send_packet = AsyncMock(return_value=True)
    handlers = APIHandlers(gateway)

    try:
        await handlers.handle_channel_join(
            api_session, {"channel": "I3testers", "user_name": "Ignored"}
        )
        joined_packet = gateway.send_packet.await_args.args[0]
        assert joined_packet.to_lpc_array() == [
            "channel-listen",
            5,
            "TestLocalMUD",
            0,
            0,
            0,
            "I3testers",
            "1",
        ]

        gateway.send_packet.reset_mock()
        await handlers.handle_channel_leave(
            api_session, {"channel": "I3testers", "user_name": "Ignored"}
        )
        left_packet = gateway.send_packet.await_args.args[0]
        assert left_packet.to_lpc_array()[-5:] == [
            0,
            0,
            0,
            "I3testers",
            "0",
        ]
    finally:
        subscription_manager.cleanup_session(api_session.session_id)


async def test_presence_sync_drives_who_finger_and_locate(api_session):
    """One authenticated snapshot should answer all player-info commands."""
    state_manager = StateManager()
    handlers = APIHandlers(state_manager=state_manager)
    result = await handlers.handle_presence_sync(
        api_session,
        {
            "users": [
                {
                    "name": "Kohdee",
                    "level": 34,
                    "title": "the Game Master",
                    "race": "Human",
                    "idle": 7,
                    "status": "online",
                    "login_time": 1_700_000_000,
                }
            ]
        },
    )
    assert result == {
        "status": "synchronized",
        "mud_name": "TestLocalMUD",
        "count": 1,
    }

    class GatewayStub:
        settings = type(
            "SettingsStub",
            (),
            {"mud": type("MudStub", (), {"name": "TestLocalMUD"})()},
        )()

    gateway = GatewayStub()
    who = WhoService(state_manager, gateway)
    finger = FingerService(state_manager, gateway)
    locate = LocateService(state_manager, gateway)

    who_request = WhoPacket(
        packet_type=PacketType.WHO_REQ,
        ttl=5,
        originator_mud="RemoteMUD",
        originator_user="Requester",
        target_mud="TestLocalMUD",
        target_user="",
        filter_criteria={},
    )
    who_reply = await who.handle_packet(who_request)
    assert who_reply.who_data == [
        {
            "name": "Kohdee",
            "idle": pytest.approx(7, abs=1),
            "level": 34,
            "extra": "the Game Master",
            "race": "Human",
        }
    ]

    finger_request = FingerPacket(
        packet_type=PacketType.FINGER_REQ,
        ttl=5,
        originator_mud="RemoteMUD",
        originator_user="Requester",
        target_mud="TestLocalMUD",
        target_user="",
        username="kohdee",
    )
    finger_reply = await finger.handle_packet(finger_request)
    assert finger_reply.user_info["name"] == "Kohdee"
    assert finger_reply.user_info["level"] == 34
    assert finger_reply.user_info["title"] == "the Game Master"
    assert finger_reply.user_info["ip_address"] == ""

    locate_request = LocatePacket(
        packet_type=PacketType.LOCATE_REQ,
        ttl=5,
        originator_mud="RemoteMUD",
        originator_user="Requester",
        target_mud="",
        target_user="",
        user_to_locate="Kohdee",
    )
    locate_reply = await locate.handle_packet(locate_request)
    assert locate_reply.located_mud == "TestLocalMUD"
    assert locate_reply.located_user == "Kohdee"


async def test_presence_sync_rejects_invalid_snapshot_without_clearing_state(
    api_session,
):
    """Malformed updates cannot replace a previously valid snapshot."""
    state_manager = StateManager()
    handlers = APIHandlers(state_manager=state_manager)
    await handlers.handle_presence_sync(
        api_session, {"users": [{"name": "Kohdee", "level": 34}]}
    )

    with pytest.raises(ValueError, match="duplicate"):
        await handlers.handle_presence_sync(
            api_session,
            {"users": [{"name": "Kohdee"}, {"name": "kohdee"}]},
        )

    session = await state_manager.find_user_session("TestLocalMUD", "Kohdee")
    assert session is not None
    assert session.level == 34


def test_channel_packet_serializes_empty_addresses_as_zero():
    """Protocol address zeros must be numeric, not wildcards or empty strings."""
    packet = ChannelPacket(
        packet_type=PacketType.CHANNEL_LISTEN,
        ttl=5,
        originator_mud="TestLocalMUD",
        originator_user="",
        target_mud="",
        target_user="",
        channel="I3testers",
        message="1",
    )

    assert packet.to_lpc_array()[2:6] == ["TestLocalMUD", 0, 0, 0]
