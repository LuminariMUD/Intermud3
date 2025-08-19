"""Channel management handlers for join, leave, list, and history.

This module implements handlers for channel-related API methods.
"""

from typing import Any, Dict, List, Optional

from src.api.handlers.base import BaseHandler
from src.api.session import Session
from src.models.packet import (
    ChannelListRequestPacket,
    ChannelWhoRequestPacket,
    ChannelAddPacket,
    ChannelRemovePacket
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ChannelJoinHandler(BaseHandler):
    """Handler for joining a channel."""
    
    def get_required_params(self) -> list[str]:
        """Get required parameters."""
        return ["channel"]
    
    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["listen_only", "user_name"]
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate channel join parameters."""
        if not self.validate_base_params(params):
            return False
        
        # Validate channel name
        if not params.get("channel"):
            logger.warning("Channel name is empty")
            return False
        
        # Validate channel name format
        channel = params["channel"]
        if len(channel) > 32:
            logger.warning("Channel name too long")
            return False
        
        return True
    
    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle channel join request.
        
        Args:
            session: Client session
            params: Request parameters
            
        Returns:
            Response data
        """
        # Check permission
        if not self.check_permission(session, "channel"):
            raise PermissionError("No permission for channel operations")
        
        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")
        
        channel = params["channel"]
        listen_only = params.get("listen_only", False)
        user_name = params.get("user_name", "System")
        
        # Check if already subscribed
        if channel in session.subscriptions:
            return {
                "status": "already_joined",
                "channel": channel,
                "message": f"Already subscribed to channel {channel}"
            }
        
        # Subscribe to channel
        session.subscribe(channel)
        
        # Send channel add packet if not listen-only
        if not listen_only and self.gateway:
            packet = ChannelAddPacket(
                channel=channel,
                originator_mud=session.mud_name,
                originator_user=user_name
            )
            
            success = await self.gateway.join_channel(channel, user_name)
            
            # Log request
            await self.log_request(
                session, "channel_join", params, success,
                None if success else "Failed to join channel"
            )
            
            if success:
                return {
                    "status": "success",
                    "channel": channel,
                    "message": f"Joined channel {channel}",
                    "listen_only": listen_only
                }
        
        # Listen-only or gateway not available
        return {
            "status": "success",
            "channel": channel,
            "message": f"Subscribed to channel {channel}",
            "listen_only": True
        }


class ChannelLeaveHandler(BaseHandler):
    """Handler for leaving a channel."""
    
    def get_required_params(self) -> list[str]:
        """Get required parameters."""
        return ["channel"]
    
    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["user_name"]
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate channel leave parameters."""
        if not self.validate_base_params(params):
            return False
        
        # Validate channel name
        if not params.get("channel"):
            logger.warning("Channel name is empty")
            return False
        
        return True
    
    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle channel leave request.
        
        Args:
            session: Client session
            params: Request parameters
            
        Returns:
            Response data
        """
        # Check permission
        if not self.check_permission(session, "channel"):
            raise PermissionError("No permission for channel operations")
        
        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")
        
        channel = params["channel"]
        user_name = params.get("user_name", "System")
        
        # Check if subscribed
        if channel not in session.subscriptions:
            return {
                "status": "not_joined",
                "channel": channel,
                "message": f"Not subscribed to channel {channel}"
            }
        
        # Unsubscribe from channel
        session.unsubscribe(channel)
        
        # Send channel remove packet
        if self.gateway:
            packet = ChannelRemovePacket(
                channel=channel,
                originator_mud=session.mud_name,
                originator_user=user_name
            )
            
            success = await self.gateway.leave_channel(channel, user_name)
            
            # Log request
            await self.log_request(
                session, "channel_leave", params, success,
                None if success else "Failed to leave channel"
            )
            
            if success:
                return {
                    "status": "success",
                    "channel": channel,
                    "message": f"Left channel {channel}"
                }
        
        # Gateway not available
        return {
            "status": "success",
            "channel": channel,
            "message": f"Unsubscribed from channel {channel}"
        }


class ChannelListHandler(BaseHandler):
    """Handler for listing available channels."""
    
    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["refresh", "filter"]
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate channel list parameters."""
        # No required params
        if params is None:
            return True
        
        # Validate filter if provided
        if "filter" in params:
            filter_opts = params["filter"]
            if not isinstance(filter_opts, dict):
                logger.warning("Filter must be a dictionary")
                return False
        
        return True
    
    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle channel list request.
        
        Args:
            session: Client session
            params: Request parameters
            
        Returns:
            Response data with channel list
        """
        # Check permission
        if not self.check_permission(session, "channel"):
            raise PermissionError("No permission for channel operations")
        
        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")
        
        params = params or {}
        refresh = params.get("refresh", False)
        
        # Get channel list
        if self.gateway:
            if refresh:
                # Request fresh channel list from router
                channels = await self.gateway.request_channel_list()
            else:
                # Get cached channel list
                channels = self.gateway.get_channel_list()
            
            # Log request
            await self.log_request(
                session, "channel_list", params, channels is not None,
                None if channels is not None else "Failed to get channel list"
            )
            
            if channels is not None:
                # Apply filters if provided
                if "filter" in params:
                    channels = self._apply_channel_filters(channels, params["filter"])
                
                # Add subscription status
                channel_info = []
                for channel_name, info in channels.items():
                    channel_data = {
                        "name": channel_name,
                        "type": info.get("type", 0),
                        "owner": info.get("owner", ""),
                        "subscribed": channel_name in session.subscriptions,
                        "member_count": info.get("member_count", 0)
                    }
                    channel_info.append(channel_data)
                
                return {
                    "status": "success",
                    "channels": channel_info,
                    "count": len(channel_info),
                    "refreshed": refresh,
                    "subscribed_channels": list(session.subscriptions)
                }
            else:
                return {
                    "status": "failed",
                    "message": "Could not retrieve channel list"
                }
        
        # Return default channels if gateway not available
        return {
            "status": "limited",
            "channels": [
                {"name": "intermud", "type": 0, "subscribed": "intermud" in session.subscriptions},
                {"name": "chat", "type": 0, "subscribed": "chat" in session.subscriptions},
                {"name": "dev", "type": 0, "subscribed": "dev" in session.subscriptions}
            ],
            "message": "Gateway not connected, showing default channels"
        }
    
    def _apply_channel_filters(
        self,
        channels: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply filters to channel list.
        
        Args:
            channels: Dictionary of channels
            filters: Filters to apply
            
        Returns:
            Filtered channel list
        """
        filtered = {}
        
        for channel_name, info in channels.items():
            include = True
            
            # Filter by type (0=public, 1=private)
            if "type" in filters:
                channel_type = filters["type"]
                if info.get("type", 0) != channel_type:
                    include = False
            
            # Filter by owner
            if "owner" in filters and include:
                owner = filters["owner"]
                if info.get("owner", "") != owner:
                    include = False
            
            # Filter by minimum members
            if "min_members" in filters and include:
                min_members = filters["min_members"]
                if info.get("member_count", 0) < min_members:
                    include = False
            
            if include:
                filtered[channel_name] = info
        
        return filtered


class ChannelWhoHandler(BaseHandler):
    """Handler for listing channel members."""
    
    def get_required_params(self) -> list[str]:
        """Get required parameters."""
        return ["channel"]
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate channel who parameters."""
        if not self.validate_base_params(params):
            return False
        
        # Validate channel name
        if not params.get("channel"):
            logger.warning("Channel name is empty")
            return False
        
        return True
    
    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle channel who request.
        
        Args:
            session: Client session
            params: Request parameters
            
        Returns:
            Response data with channel members
        """
        # Check permission
        if not self.check_permission(session, "channel"):
            raise PermissionError("No permission for channel operations")
        
        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")
        
        channel = params["channel"]
        
        # Create channel who request packet
        packet = ChannelWhoRequestPacket(
            originator_mud=session.mud_name,
            originator_user="",
            channel=channel
        )
        
        # Send via gateway
        if self.gateway:
            members = await self.gateway.get_channel_members(channel)
            
            # Log request
            await self.log_request(
                session, "channel_who", params, members is not None,
                None if members is not None else "Failed to get channel members"
            )
            
            if members is not None:
                return {
                    "status": "success",
                    "channel": channel,
                    "members": members,
                    "count": len(members),
                    "subscribed": channel in session.subscriptions
                }
            else:
                return {
                    "status": "failed",
                    "message": f"Could not retrieve members for channel {channel}"
                }
        
        return {
            "status": "unavailable",
            "message": "Gateway not connected"
        }


class ChannelHistoryHandler(BaseHandler):
    """Handler for getting channel message history."""
    
    def get_required_params(self) -> list[str]:
        """Get required parameters."""
        return ["channel"]
    
    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["limit", "before", "after"]
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate channel history parameters."""
        if not self.validate_base_params(params):
            return False
        
        # Validate channel name
        if not params.get("channel"):
            logger.warning("Channel name is empty")
            return False
        
        # Validate limit if provided
        if "limit" in params:
            limit = params["limit"]
            if not isinstance(limit, int) or limit < 1 or limit > 100:
                logger.warning("Invalid limit value")
                return False
        
        return True
    
    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle channel history request.
        
        Args:
            session: Client session
            params: Request parameters
            
        Returns:
            Response data with channel history
        """
        # Check permission
        if not self.check_permission(session, "channel"):
            raise PermissionError("No permission for channel operations")
        
        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")
        
        channel = params["channel"]
        limit = params.get("limit", 50)
        before = params.get("before")
        after = params.get("after")
        
        # Get history from gateway or state
        if self.gateway:
            history = await self.gateway.get_channel_history(
                channel,
                limit=limit,
                before=before,
                after=after
            )
            
            # Log request
            await self.log_request(
                session, "channel_history", params, history is not None,
                None if history is not None else "Failed to get channel history"
            )
            
            if history is not None:
                return {
                    "status": "success",
                    "channel": channel,
                    "messages": history,
                    "count": len(history),
                    "limit": limit,
                    "subscribed": channel in session.subscriptions
                }
            else:
                return {
                    "status": "failed",
                    "message": f"Could not retrieve history for channel {channel}"
                }
        
        return {
            "status": "unavailable",
            "message": "Gateway not connected"
        }