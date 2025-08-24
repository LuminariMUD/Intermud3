"""
API method handlers for the I3 Gateway.

Implements all JSON-RPC methods for MUD communication.
"""

from datetime import datetime
from typing import Any, Dict

import structlog

from src.api.session import Session
from src.api.subscriptions import subscription_manager
from src.models.packet import (
    ChannelMessagePacket,
    ChannelPacket,
    EmotetoPacket,
    FingerPacket,
    LocatePacket,
    PacketType,
    TellPacket,
    WhoPacket,
)
from src.state.manager import StateManager


logger = structlog.get_logger(__name__)


class APIHandlers:
    """Handles all API method calls."""

    def __init__(self, gateway=None, state_manager=None):
        """Initialize API handlers.

        Args:
            gateway: Gateway instance for I3 network communication
            state_manager: State manager instance
        """
        self.gateway = gateway
        self.state_manager = state_manager or StateManager()

        # Method registry
        self.methods = {
            # Authentication
            "authenticate": self.handle_authenticate,
            # Communication
            "tell": self.handle_tell,
            "emoteto": self.handle_emoteto,
            # Channels
            "channel_send": self.handle_channel_send,
            "channel_emote": self.handle_channel_emote,
            "channel_join": self.handle_channel_join,
            "channel_leave": self.handle_channel_leave,
            "channel_list": self.handle_channel_list,
            "channel_who": self.handle_channel_who,
            "channel_history": self.handle_channel_history,
            # Information queries
            "who": self.handle_who,
            "finger": self.handle_finger,
            "locate": self.handle_locate,
            "mudlist": self.handle_mudlist,
            # Administrative
            "ping": self.handle_ping,
            "status": self.handle_status,
            "stats": self.handle_stats,
            "reconnect": self.handle_reconnect,
            "heartbeat": self.handle_heartbeat,
        }

    def get_handler(self, method: str):
        """Get handler for a method.

        Args:
            method: Method name

        Returns:
            Handler function or None
        """
        return self.methods.get(method)

    # Authentication Methods

    async def handle_authenticate(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle authentication - but this is usually done at connection level."""
        return {"status": "success", "mud_name": session.mud_name, "session_id": session.session_id}

    # Communication Methods

    async def handle_tell(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a direct message to a user on another MUD.

        Args:
            session: Client session
            params: {target_mud, target_user, message, from_user?}

        Returns:
            {status, message_id}
        """
        target_mud = params.get("target_mud")
        target_user = params.get("target_user")
        message = params.get("message")
        from_user = params.get("from_user", "Someone")

        if not all([target_mud, target_user, message]):
            raise ValueError("Missing required parameters: target_mud, target_user, message")

        # Create tell packet
        packet = TellPacket(
            ttl=5,
            originator_mud=session.mud_name,
            originator_user=from_user,
            target_mud=target_mud,
            target_user=target_user,
            visname=from_user,
            message=message,
        )

        # Send through gateway
        if self.gateway:
            await self.gateway.send_packet(packet)

        # Generate message ID for tracking
        message_id = f"tell_{session.mud_name}_{datetime.utcnow().timestamp()}"

        logger.info(
            "tell_sent",
            from_mud=session.mud_name,
            from_user=from_user,
            target_mud=target_mud,
            target_user=target_user,
            message_id=message_id,
        )

        return {"status": "sent", "message_id": message_id}

    async def handle_emoteto(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send an emote to a specific user.

        Args:
            session: Client session
            params: {target_mud, target_user, emote, from_user?}

        Returns:
            {status, message_id}
        """
        target_mud = params.get("target_mud")
        target_user = params.get("target_user")
        emote = params.get("emote")
        from_user = params.get("from_user", "Someone")

        if not all([target_mud, target_user, emote]):
            raise ValueError("Missing required parameters: target_mud, target_user, emote")

        # Create emoteto packet
        packet = EmotetoPacket(
            ttl=5,
            originator_mud=session.mud_name,
            originator_user=from_user,
            target_mud=target_mud,
            target_user=target_user,
            visname=from_user,
            message=emote,
        )

        # Send through gateway
        if self.gateway:
            await self.gateway.send_packet(packet)

        # Generate message ID
        message_id = f"emoteto_{session.mud_name}_{datetime.utcnow().timestamp()}"

        logger.info(
            "emoteto_sent",
            from_mud=session.mud_name,
            from_user=from_user,
            target_mud=target_mud,
            target_user=target_user,
            message_id=message_id,
        )

        return {"status": "sent", "message_id": message_id}

    # Channel Methods

    async def handle_channel_send(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to a channel.

        Args:
            session: Client session
            params: {channel, message, from_user?, visname?}

        Returns:
            {status, message_id}
        """
        channel = params.get("channel")
        message = params.get("message")
        from_user = params.get("from_user", "Someone")
        visname = params.get("visname", from_user)

        if not all([channel, message]):
            raise ValueError("Missing required parameters: channel, message")

        # Create channel message packet
        packet = ChannelMessagePacket(
            ttl=5,
            originator_mud=session.mud_name,
            originator_user=from_user,
            target_mud="*",
            target_user="*",
            channel=channel,
            visname=visname,
            message=message,
        )

        # Send through gateway
        if self.gateway:
            await self.gateway.send_packet(packet)

        # Generate message ID
        message_id = f"channel_{channel}_{datetime.utcnow().timestamp()}"

        logger.info(
            "channel_message_sent",
            channel=channel,
            from_mud=session.mud_name,
            from_user=from_user,
            message_id=message_id,
        )

        return {"status": "sent", "message_id": message_id}

    async def handle_channel_emote(
        self, session: Session, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send an emote to a channel.

        Args:
            session: Client session
            params: {channel, emote, from_user?, visname?}

        Returns:
            {status, message_id}
        """
        channel = params.get("channel")
        emote = params.get("emote")
        from_user = params.get("from_user", "Someone")
        visname = params.get("visname", from_user)

        if not all([channel, emote]):
            raise ValueError("Missing required parameters: channel, emote")

        # Create channel emote packet
        packet = ChannelMessagePacket(
            ttl=5,
            originator_mud=session.mud_name,
            originator_user=from_user,
            target_mud="*",
            target_user="*",
            channel=channel,
            visname=visname,
            message=emote,
        )
        # Set packet type to channel emote after creation
        packet.packet_type = PacketType.CHANNEL_E

        # Send through gateway
        if self.gateway:
            await self.gateway.send_packet(packet)

        # Generate message ID
        message_id = f"channel_emote_{channel}_{datetime.utcnow().timestamp()}"

        logger.info(
            "channel_emote_sent",
            channel=channel,
            from_mud=session.mud_name,
            from_user=from_user,
            message_id=message_id,
        )

        return {"status": "sent", "message_id": message_id}

    async def handle_channel_join(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Join a channel (subscribe to messages).

        Args:
            session: Client session
            params: {channel, listen_only?, user_name?}

        Returns:
            {status, channel}
        """
        channel = params.get("channel")
        listen_only = params.get("listen_only", False)
        user_name = params.get("user_name")

        if not channel:
            raise ValueError("Missing required parameter: channel")

        # Subscribe session to channel
        subscription_manager.subscribe_channel(session.session_id, channel)

        # Send channel listen packet if not listen-only
        if not listen_only and self.gateway:
            packet = ChannelPacket(
                packet_type=PacketType.CHANNEL_LISTEN,
                ttl=5,
                originator_mud=session.mud_name,
                originator_user=user_name or "*",
                target_mud="*",
                target_user="*",
                channel=channel,
                message=str(1),  # 1 = join, 0 = leave
            )
            await self.gateway.send_packet(packet)

        logger.info(
            "channel_joined", channel=channel, mud_name=session.mud_name, listen_only=listen_only
        )

        return {"status": "joined", "channel": channel}

    async def handle_channel_leave(
        self, session: Session, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Leave a channel (unsubscribe from messages).

        Args:
            session: Client session
            params: {channel, user_name?}

        Returns:
            {status, channel}
        """
        channel = params.get("channel")
        user_name = params.get("user_name")

        if not channel:
            raise ValueError("Missing required parameter: channel")

        # Unsubscribe session from channel
        subscription_manager.unsubscribe_channel(session.session_id, channel)

        # Send channel listen packet to leave
        if self.gateway:
            packet = ChannelPacket(
                packet_type=PacketType.CHANNEL_LISTEN,
                ttl=5,
                originator_mud=session.mud_name,
                originator_user=user_name or "*",
                target_mud="*",
                target_user="*",
                channel=channel,
                message=str(0),  # 0 = leave
            )
            await self.gateway.send_packet(packet)

        logger.info("channel_left", channel=channel, mud_name=session.mud_name)

        return {"status": "left", "channel": channel}

    async def handle_channel_list(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get list of available channels.

        Args:
            session: Client session
            params: {refresh?, filter?}

        Returns:
            {status, channels[], count, subscribed_channels[]}
        """
        refresh = params.get("refresh", False)
        filter_opts = params.get("filter", {})

        # Get channels from state manager
        channels = await self.state_manager.get_channels()

        # Apply filters if provided
        if filter_opts:
            filtered = []
            for channel in channels:
                if "type" in filter_opts and channel.get("type") != filter_opts["type"]:
                    continue
                if "owner" in filter_opts and channel.get("owner") != filter_opts["owner"]:
                    continue
                if (
                    "min_members" in filter_opts
                    and channel.get("member_count", 0) < filter_opts["min_members"]
                ):
                    continue
                filtered.append(channel)
            channels = filtered

        # Get subscribed channels for this session
        subscribed = subscription_manager.get_channel_subscriptions(session.session_id)

        return {
            "status": "success",
            "channels": channels,
            "count": len(channels),
            "subscribed_channels": list(subscribed),
        }

    async def handle_channel_who(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """List members of a channel.

        Args:
            session: Client session
            params: {channel}

        Returns:
            {status, channel, members[]}
        """
        channel = params.get("channel")

        if not channel:
            raise ValueError("Missing required parameter: channel")

        # Send channel who request
        if self.gateway:
            packet = ChannelPacket(
                packet_type=PacketType.CHAN_WHO_REQ,
                ttl=5,
                originator_mud=session.mud_name,
                originator_user="*",
                target_mud="*",
                target_user="*",
                channel=channel,
                message="",
            )
            await self.gateway.send_packet(packet)

        # For now return cached data if available
        channel_info = await self.state_manager.get_channel(channel)
        members = channel_info.get("members", []) if channel_info else []

        return {"status": "success", "channel": channel, "members": members}

    async def handle_channel_history(
        self, session: Session, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get channel message history.

        Args:
            session: Client session
            params: {channel, limit?, before?, after?}

        Returns:
            {status, messages[], count}
        """
        channel = params.get("channel")
        limit = min(params.get("limit", 50), 100)  # Max 100 messages
        before = params.get("before")
        after = params.get("after")

        if not channel:
            raise ValueError("Missing required parameter: channel")

        # Get message history from state manager
        messages = await self.state_manager.get_channel_history(
            channel, limit=limit, before=before, after=after
        )

        return {"status": "success", "messages": messages, "count": len(messages)}

    # Information Query Methods

    async def handle_who(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """List users on a MUD.

        Args:
            session: Client session
            params: {target_mud, filters?}

        Returns:
            {status, mud_name, users[], count}
        """
        target_mud = params.get("target_mud")
        filters = params.get("filters", {})

        if not target_mud:
            raise ValueError("Missing required parameter: target_mud")

        # Send who request
        if self.gateway:
            packet = WhoPacket(
                packet_type=PacketType.WHO_REQ,
                ttl=5,
                originator_mud=session.mud_name,
                originator_user="*",
                target_mud=target_mud,
                target_user="*",
                filter_criteria=filters,
            )
            await self.gateway.send_packet(packet)

        # Return cached data if available
        who_data = await self.state_manager.get_who_data(target_mud)
        users = who_data.get("users", []) if who_data else []

        return {"status": "success", "mud_name": target_mud, "users": users, "count": len(users)}

    async def handle_finger(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about a user.

        Args:
            session: Client session
            params: {target_mud, target_user}

        Returns:
            {status, user_info}
        """
        target_mud = params.get("target_mud")
        target_user = params.get("target_user")

        if not all([target_mud, target_user]):
            raise ValueError("Missing required parameters: target_mud, target_user")

        # Send finger request
        if self.gateway:
            packet = FingerPacket(
                packet_type=PacketType.FINGER_REQ,
                ttl=5,
                originator_mud=session.mud_name,
                originator_user="*",
                target_mud=target_mud,
                target_user="*",
                username=target_user,
            )
            await self.gateway.send_packet(packet)

        # Return cached data if available
        finger_data = await self.state_manager.get_finger_data(target_mud, target_user)

        return {"status": "success", "user_info": finger_data or {}}

    async def handle_locate(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Find a user on the network.

        Args:
            session: Client session
            params: {target_user}

        Returns:
            {status, user_name, locations[], found, count}
        """
        target_user = params.get("target_user")

        if not target_user:
            raise ValueError("Missing required parameter: target_user")

        # Send locate request
        if self.gateway:
            packet = LocatePacket(
                packet_type=PacketType.LOCATE_REQ,
                ttl=5,
                originator_mud=session.mud_name,
                originator_user="*",
                target_mud="*",
                target_user="*",
                user_to_locate=target_user,
            )
            await self.gateway.send_packet(packet)

        # Return cached data if available
        locate_data = await self.state_manager.get_locate_data(target_user)
        locations = locate_data.get("locations", []) if locate_data else []

        return {
            "status": "success",
            "user_name": target_user,
            "locations": locations,
            "found": len(locations) > 0,
            "count": len(locations),
        }

    async def handle_mudlist(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get list of MUDs on the network.

        Args:
            session: Client session
            params: {refresh?, filter?}

        Returns:
            {status, muds[], count}
        """
        refresh = params.get("refresh", False)
        filter_opts = params.get("filter", {})

        # Get mudlist from state manager
        muds = await self.state_manager.get_mudlist()

        # Apply filters if provided
        if filter_opts:
            filtered = []
            for mud in muds:
                if "status" in filter_opts and mud.get("status") != filter_opts["status"]:
                    continue
                if "driver" in filter_opts and mud.get("driver") != filter_opts["driver"]:
                    continue
                if "has_service" in filter_opts:
                    service = filter_opts["has_service"]
                    if service not in mud.get("services", {}):
                        continue
                filtered.append(mud)
            muds = filtered

        return {"status": "success", "muds": muds, "count": len(muds)}

    # Administrative Methods

    async def handle_ping(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Health check and heartbeat.

        Args:
            session: Client session
            params: {}

        Returns:
            {pong: true, timestamp}
        """
        return {"pong": True, "timestamp": datetime.utcnow().isoformat()}

    async def handle_status(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get gateway status and session information.

        Args:
            session: Client session
            params: {}

        Returns:
            {connected, mud_name, session_id, uptime}
        """
        connected = self.gateway.is_connected() if self.gateway else False
        uptime = (datetime.utcnow() - session.connected_at).total_seconds()

        return {
            "connected": connected,
            "mud_name": session.mud_name,
            "session_id": session.session_id,
            "uptime": uptime,
        }

    async def handle_stats(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get gateway statistics.

        Args:
            session: Client session
            params: {}

        Returns:
            Statistics information
        """
        stats = await self.state_manager.get_stats() if self.state_manager else {}

        # Add gateway-specific stats
        if self.gateway:
            stats.update(
                {
                    "gateway_connected": self.gateway.is_connected(),
                    "packets_sent": getattr(self.gateway, "packets_sent", 0),
                    "packets_received": getattr(self.gateway, "packets_received", 0),
                }
            )

        return stats

    async def handle_reconnect(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Force gateway to reconnect to I3 router.

        Args:
            session: Client session
            params: {}

        Returns:
            {status}
        """
        if self.gateway:
            await self.gateway.reconnect()
            return {"status": "reconnecting"}
        return {"status": "no_gateway"}

    async def handle_heartbeat(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle heartbeat/keepalive from client.

        Args:
            session: Client session
            params: {}

        Returns:
            {status, timestamp}
        """
        return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
