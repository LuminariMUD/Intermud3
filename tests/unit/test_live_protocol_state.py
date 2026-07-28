"""Regression tests derived from live Intermud-3 router traffic."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.api_handlers import APIHandlers
from src.api.event_bridge import EventBridge
from src.api.events import EventType
from src.api.protocol import JSONRPCProtocol
from src.api.session import Session
from src.models.connection import MudInfo, MudStatus
from src.models.packet import (
    ChanlistReplyPacket,
    PacketFactory,
    PacketType,
    WhoPacket,
)
from src.network.lpc import LPCDecoder
from src.state.manager import StateManager


def mudlist_entry(state: int, address: str, port: int) -> list:
    """Build one protocol-correct mudlist entry."""
    return [
        state,
        address,
        port,
        0,
        0,
        "TestLib",
        "BaseLib",
        "TestDriver",
        "LP",
        "open",
        "admin@example.com",
        {"tell": 1, "channel": 1},
        {"extra": "value"},
    ]


def test_mud_info_uses_protocol_field_order() -> None:
    """Mudlist state precedes address and port in the I3 wire format."""
    mud = MudInfo(name="RemoteMUD", address="", player_port=0)

    mud.update_from_mudlist(mudlist_entry(-1, "192.0.2.10", 4100))

    assert mud.status == MudStatus.UP
    assert mud.address == "192.0.2.10"
    assert mud.player_port == 4100
    assert mud.mudlib == "TestLib"
    assert mud.services == {"tell": 1, "channel": 1}


@pytest.mark.asyncio
async def test_mudlist_updates_are_incremental_and_zero_deletes() -> None:
    """A delta must not mark omitted MUDs down, and zero deletes an entry."""
    manager = StateManager()
    await manager.update_mudlist(
        {
            "FirstMUD": mudlist_entry(-1, "192.0.2.1", 4001),
            "SecondMUD": mudlist_entry(-1, "192.0.2.2", 4002),
        },
        1,
    )

    await manager.update_mudlist(
        {"FirstMUD": mudlist_entry(0, "192.0.2.1", 4001)},
        2,
    )

    assert manager.mudlist["FirstMUD"].status == MudStatus.DOWN
    assert manager.mudlist["SecondMUD"].status == MudStatus.UP

    await manager.update_mudlist({"FirstMUD": 0}, 3)

    assert "FirstMUD" not in manager.mudlist
    assert (await manager.get_mudlist())[0]["status"] == "up"
    assert (await manager.get_stats())["online_muds"] == 1


@pytest.mark.asyncio
async def test_chanlist_wire_arrays_and_deletions() -> None:
    """Channel entries arrive as [owner, type], while zero deletes them."""
    manager = StateManager()
    await manager.update_chanlist({"intermud": ["RouterMUD", 1]}, 10)

    channel = await manager.get_channel("intermud")
    assert channel is not None
    assert channel.owner == "RouterMUD"
    assert channel.type == 1

    await manager.update_chanlist({"intermud": 0}, 11)
    assert await manager.get_channel("intermud") is None


def test_packet_factory_parses_chanlist_reply() -> None:
    """The packet factory must not discard the router's initial chanlist."""
    packet = PacketFactory.create_packet(
        [
            "chanlist-reply",
            5,
            "*router",
            0,
            "LuminariMUD",
            0,
            42,
            {"intermud": ["RouterMUD", 0]},
        ]
    )

    assert isinstance(packet, ChanlistReplyPacket)
    assert packet.packet_type == PacketType.CHANLIST_REPLY
    assert packet.chanlist_id == 42


def test_lpc_decoder_accepts_legacy_single_byte_text() -> None:
    """Legacy I3 strings may contain Latin-1 bytes instead of UTF-8."""
    encoded = b'({"tell",5,"Caf' + bytes([0xE9]) + b'MUD",0,"LuminariMUD",0,})\x00'
    decoded = LPCDecoder().decode(encoded)

    assert decoded[2] == "Caf\u00e9MUD"


def test_api_handlers_share_gateway_state() -> None:
    """API mudlist/channel calls must use the router-populated state manager."""
    state_manager = StateManager()
    gateway = SimpleNamespace(state_manager=state_manager)

    handlers = APIHandlers(gateway=gateway)

    assert handlers.state_manager is state_manager


def test_parameterless_request_defaults_to_empty_params() -> None:
    """Omitted JSON-RPC params must be safe for parameterless API handlers."""
    request = JSONRPCProtocol().parse_request('{"jsonrpc":"2.0","method":"mudlist","id":2}')

    assert request.params == {}


@pytest.mark.asyncio
async def test_tcp_session_send_writes_json_notification() -> None:
    """TCP sessions must actually write event notifications to the client."""
    connection = SimpleNamespace(closed=False, send_json=AsyncMock())
    session = Session(
        session_id="session",
        mud_name="LuminariMUD",
        api_key="test",
        connected_at=datetime.now(),
        last_activity=datetime.now(),
        tcp_connection=connection,
    )

    sent = await session.send('{"jsonrpc":"2.0","method":"tell_received","params":{}}')

    assert sent is True
    connection.send_json.assert_awaited_once_with(
        {"jsonrpc": "2.0", "method": "tell_received", "params": {}}
    )


@pytest.mark.asyncio
async def test_information_request_preserves_requesting_user() -> None:
    """The remote reply must carry enough context to reach the requesting player."""
    state_manager = StateManager()
    gateway = SimpleNamespace(
        state_manager=state_manager,
        send_packet=AsyncMock(return_value=True),
    )
    handlers = APIHandlers(gateway=gateway)
    session = Session(
        session_id="session",
        mud_name="LuminariMUD",
        api_key="test",
        connected_at=datetime.now(),
        last_activity=datetime.now(),
    )

    result = await handlers.handle_who(
        session,
        {"target_mud": "RemoteMUD", "from_user": "Tester"},
    )

    assert result == {"status": "requested", "mud_name": "RemoteMUD"}
    packet = gateway.send_packet.await_args.args[0]
    assert packet.packet_type == PacketType.WHO_REQ
    assert packet.originator_user == "Tester"
    assert packet.target_mud == "RemoteMUD"


@pytest.mark.asyncio
async def test_who_reply_becomes_targeted_api_event(monkeypatch) -> None:
    """A router who reply must be delivered as a targeted JSON-RPC notification."""
    bridge = EventBridge()
    bridge.start()
    dispatch = AsyncMock()
    monkeypatch.setattr("src.api.event_bridge.event_dispatcher.dispatch", dispatch)
    packet = WhoPacket(
        packet_type=PacketType.WHO_REPLY,
        ttl=5,
        originator_mud="RemoteMUD",
        originator_user="",
        target_mud="LuminariMUD",
        target_user="Tester",
        who_data=[{"name": "RemotePlayer", "idle": 0}],
    )

    await bridge.process_incoming_packet(packet)

    event = dispatch.await_args.args[0]
    assert event.type == EventType.WHO_REPLY
    assert event.data["to_mud"] == "LuminariMUD"
    assert event.data["to_user"] == "Tester"
    assert event.data["users"][0]["name"] == "RemotePlayer"
    bridge.stop()
