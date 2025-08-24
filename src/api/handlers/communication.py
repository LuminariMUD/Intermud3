"""Communication handlers for tell, emoteto, and channel messages.

This module implements handlers for all communication-related API methods.
"""

from typing import Any, Dict

from src.api.handlers.base import BaseHandler
from src.api.session import Session
from src.models.packet import ChannelMessagePacket, ChannelPacket, EmotetoPacket, TellPacket
from src.utils.logging import get_logger


logger = get_logger(__name__)


class TellHandler(BaseHandler):
    """Handler for sending direct messages (tells)."""

    def get_required_params(self) -> list[str]:
        """Get required parameters."""
        return ["target_mud", "target_user", "message"]

    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["from_user", "reply_to"]

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate tell parameters."""
        if not self.validate_base_params(params):
            return False

        # Validate message length
        if len(params.get("message", "")) > 2048:
            logger.warning("Tell message exceeds maximum length")
            return False

        # Validate target MUD name
        if not params.get("target_mud"):
            logger.warning("Target MUD name is empty")
            return False

        # Validate target user name
        if not params.get("target_user"):
            logger.warning("Target user name is empty")
            return False

        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tell request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data
        """
        # Check permission
        if not self.check_permission(session, "tell"):
            raise PermissionError("No permission for tell")

        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")

        # Create tell packet
        packet = TellPacket(
            originator_mud=session.mud_name,
            originator_user=params.get("from_user", "System"),
            target_mud=params["target_mud"],
            target_user=params["target_user"],
            message=params["message"],
        )

        # Send via gateway
        if self.gateway:
            success = await self.gateway.send_tell(
                packet.target_mud, packet.target_user, packet.originator_user, packet.message
            )

            # Log request
            await self.log_request(
                session, "tell", params, success, None if success else "Failed to send tell"
            )

            if success:
                return {"status": "success", "message": "Tell sent successfully"}
            return {"status": "failed", "message": "Failed to deliver tell"}

        # Gateway not available
        return {"status": "queued", "message": "Tell queued for delivery"}


class EmoteToHandler(BaseHandler):
    """Handler for sending emotes to specific users."""

    def get_required_params(self) -> list[str]:
        """Get required parameters."""
        return ["target_mud", "target_user", "emote"]

    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["from_user"]

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate emoteto parameters."""
        if not self.validate_base_params(params):
            return False

        # Validate emote length
        if len(params.get("emote", "")) > 1024:
            logger.warning("Emote exceeds maximum length")
            return False

        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle emoteto request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data
        """
        # Check permission
        if not self.check_permission(session, "emoteto"):
            raise PermissionError("No permission for emoteto")

        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")

        # Create emoteto packet
        packet = EmotetoPacket(
            originator_mud=session.mud_name,
            originator_user=params.get("from_user", "System"),
            target_mud=params["target_mud"],
            target_user=params["target_user"],
            emote=params["emote"],
        )

        # Send via gateway
        if self.gateway:
            success = await self.gateway.send_emoteto(
                packet.target_mud, packet.target_user, packet.originator_user, packet.emote
            )

            # Log request
            await self.log_request(
                session, "emoteto", params, success, None if success else "Failed to send emote"
            )

            if success:
                return {"status": "success", "message": "Emote sent successfully"}
            return {"status": "failed", "message": "Failed to deliver emote"}

        return {"status": "queued", "message": "Emote queued for delivery"}


class ChannelSendHandler(BaseHandler):
    """Handler for sending channel messages."""

    def get_required_params(self) -> list[str]:
        """Get required parameters."""
        return ["channel", "message"]

    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["from_user", "visname"]

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate channel send parameters."""
        if not self.validate_base_params(params):
            return False

        # Validate message length
        if len(params.get("message", "")) > 2048:
            logger.warning("Channel message exceeds maximum length")
            return False

        # Validate channel name
        if not params.get("channel"):
            logger.warning("Channel name is empty")
            return False

        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle channel send request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data
        """
        # Check permission
        if not self.check_permission(session, "channel"):
            raise PermissionError("No permission for channel messages")

        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")

        # Check if subscribed to channel
        channel = params["channel"]
        if channel not in session.subscriptions:
            # Auto-subscribe if not subscribed
            session.subscribe(channel)

        # Create channel message packet
        packet = ChannelMessagePacket(
            channel=channel,
            originator_mud=session.mud_name,
            originator_user=params.get("from_user", "System"),
            message=params["message"],
            visname=params.get("visname", params.get("from_user", "System")),
        )

        # Send via gateway
        if self.gateway:
            success = await self.gateway.send_channel_message(
                packet.channel, packet.originator_user, packet.message
            )

            # Log request
            await self.log_request(
                session,
                "channel_send",
                params,
                success,
                None if success else "Failed to send channel message",
            )

            if success:
                return {"status": "success", "message": "Channel message sent", "channel": channel}
            return {"status": "failed", "message": "Failed to send channel message"}

        return {"status": "queued", "message": "Channel message queued"}


class ChannelEmoteHandler(BaseHandler):
    """Handler for sending channel emotes."""

    def get_required_params(self) -> list[str]:
        """Get required parameters."""
        return ["channel", "emote"]

    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["from_user", "visname"]

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate channel emote parameters."""
        if not self.validate_base_params(params):
            return False

        # Validate emote length
        if len(params.get("emote", "")) > 1024:
            logger.warning("Channel emote exceeds maximum length")
            return False

        # Validate channel name
        if not params.get("channel"):
            logger.warning("Channel name is empty")
            return False

        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle channel emote request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data
        """
        # Check permission
        if not self.check_permission(session, "channel"):
            raise PermissionError("No permission for channel emotes")

        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")

        # Check if subscribed to channel
        channel = params["channel"]
        if channel not in session.subscriptions:
            # Auto-subscribe if not subscribed
            session.subscribe(channel)

        # Create channel emote packet
        packet = ChannelPacket(
            channel=channel,
            originator_mud=session.mud_name,
            originator_user=params.get("from_user", "System"),
            emote=params["emote"],
            visname=params.get("visname", params.get("from_user", "System")),
        )

        # Send via gateway
        if self.gateway:
            success = await self.gateway.send_channel_emote(
                packet.channel, packet.originator_user, packet.emote
            )

            # Log request
            await self.log_request(
                session,
                "channel_emote",
                params,
                success,
                None if success else "Failed to send channel emote",
            )

            if success:
                return {"status": "success", "message": "Channel emote sent", "channel": channel}
            return {"status": "failed", "message": "Failed to send channel emote"}

        return {"status": "queued", "message": "Channel emote queued"}
