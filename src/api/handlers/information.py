"""Information handlers for who, finger, locate, and mudlist.

This module implements handlers for information query API methods.
"""

from typing import Any, Dict, List

from src.api.handlers.base import BaseHandler
from src.api.session import Session
from src.models.packet import FingerPacket, LocatePacket, WhoPacket
from src.utils.logging import get_logger


logger = get_logger(__name__)


class WhoHandler(BaseHandler):
    """Handler for listing users on a MUD."""

    def get_required_params(self) -> list[str]:
        """Get required parameters."""
        return ["target_mud"]

    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["filters"]

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate who parameters."""
        if not self.validate_base_params(params):
            return False

        # Validate target MUD
        if not params.get("target_mud"):
            logger.warning("Target MUD name is empty")
            return False

        # Validate filters if provided
        if "filters" in params:
            filters = params["filters"]
            if not isinstance(filters, dict):
                logger.warning("Filters must be a dictionary")
                return False

        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle who request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data with user list
        """
        # Check permission
        if not self.check_permission(session, "info"):
            raise PermissionError("No permission for who queries")

        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")

        target_mud = params["target_mud"]

        # Check if querying self
        if target_mud == session.mud_name:
            # Return local user list if available
            return {
                "status": "success",
                "mud_name": target_mud,
                "users": [],  # Would be populated from local state
                "message": "Local MUD query",
            }

        # Create who request packet
        packet = WhoPacket(originator_mud=session.mud_name, target_mud=target_mud)

        # Send via gateway
        if self.gateway:
            users = await self.gateway.send_who_request(target_mud)

            # Log request
            await self.log_request(
                session,
                "who",
                params,
                users is not None,
                None if users is not None else "Failed to get user list",
            )

            if users is not None:
                # Apply filters if provided
                if "filters" in params:
                    users = self._apply_who_filters(users, params["filters"])

                return {
                    "status": "success",
                    "mud_name": target_mud,
                    "users": users,
                    "count": len(users),
                }
            return {
                "status": "failed",
                "message": f"Could not retrieve user list from {target_mud}",
            }

        return {"status": "unavailable", "message": "Gateway not connected"}

    def _apply_who_filters(
        self, users: List[Dict[str, Any]], filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply filters to user list.

        Args:
            users: List of users
            filters: Filters to apply

        Returns:
            Filtered user list
        """
        filtered = users

        # Filter by minimum level
        if "min_level" in filters:
            min_level = filters["min_level"]
            filtered = [u for u in filtered if u.get("level", 0) >= min_level]

        # Filter by maximum level
        if "max_level" in filters:
            max_level = filters["max_level"]
            filtered = [u for u in filtered if u.get("level", 999) <= max_level]

        # Filter by race
        if "race" in filters:
            race = filters["race"].lower()
            filtered = [u for u in filtered if u.get("race", "").lower() == race]

        # Filter by guild
        if "guild" in filters:
            guild = filters["guild"].lower()
            filtered = [u for u in filtered if u.get("guild", "").lower() == guild]

        return filtered


class FingerHandler(BaseHandler):
    """Handler for getting user information."""

    def get_required_params(self) -> list[str]:
        """Get required parameters."""
        return ["target_mud"]  # target_user or username checked in validate_params

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate finger parameters."""
        if not self.validate_base_params(params):
            return False

        # Validate target MUD
        if not params.get("target_mud"):
            logger.warning("Target MUD name is empty")
            return False

        # Accept both 'target_user' and 'username' for backward compatibility
        if not params.get("target_user") and not params.get("username"):
            logger.warning("Target user name is empty")
            return False

        # Normalize to target_user
        if "username" in params and "target_user" not in params:
            params["target_user"] = params["username"]

        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle finger request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data with user information
        """
        # Check permission
        if not self.check_permission(session, "info"):
            raise PermissionError("No permission for finger queries")

        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")

        target_mud = params["target_mud"]
        target_user = params["target_user"]

        # Create finger request packet
        packet = FingerPacket(
            originator_mud=session.mud_name,
            originator_user="",
            target_mud=target_mud,
            target_user=target_user,
        )

        # Send via gateway
        if self.gateway:
            info = await self.gateway.send_finger_request(target_mud, target_user)

            # Log request
            await self.log_request(
                session,
                "finger",
                params,
                info is not None,
                None if info is not None else "Failed to get user info",
            )

            if info is not None:
                return {
                    "status": "success",
                    "mud_name": target_mud,
                    "user_name": target_user,
                    "info": info,
                }
            return {
                "status": "failed",
                "message": f"Could not retrieve info for {target_user}@{target_mud}",
            }

        return {"status": "unavailable", "message": "Gateway not connected"}


class LocateHandler(BaseHandler):
    """Handler for locating a user on the network."""

    def get_required_params(self) -> list[str]:
        """Get required parameters."""
        return ["target_user"]

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate locate parameters."""
        if not self.validate_base_params(params):
            return False

        # Validate target user
        if not params.get("target_user"):
            logger.warning("Target user name is empty")
            return False

        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle locate request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data with user location
        """
        # Check permission
        if not self.check_permission(session, "info"):
            raise PermissionError("No permission for locate queries")

        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")

        target_user = params["target_user"]

        # Create locate request packet
        packet = LocatePacket(
            originator_mud=session.mud_name, originator_user="", target_user=target_user
        )

        # Send via gateway
        if self.gateway:
            locations = await self.gateway.send_locate_request(target_user)

            # Log request
            await self.log_request(
                session,
                "locate",
                params,
                locations is not None,
                None if locations is not None else "Failed to locate user",
            )

            if locations is not None:
                if locations:
                    return {
                        "status": "success",
                        "user_name": target_user,
                        "locations": locations,
                        "found": True,
                        "count": len(locations),
                    }
                return {
                    "status": "success",
                    "user_name": target_user,
                    "locations": [],
                    "found": False,
                    "message": f"User {target_user} not found on network",
                }
            return {"status": "failed", "message": f"Could not complete locate for {target_user}"}

        return {"status": "unavailable", "message": "Gateway not connected"}


class MudListHandler(BaseHandler):
    """Handler for getting list of MUDs on the network."""

    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["refresh", "filter"]

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate mudlist parameters."""
        # No required params for mudlist
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
        """Handle mudlist request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data with MUD list
        """
        # Check permission
        if not self.check_permission(session, "info"):
            raise PermissionError("No permission for mudlist queries")

        # Validate parameters
        if not self.validate_params(params):
            raise ValueError("Invalid parameters")

        params = params or {}
        refresh = params.get("refresh", False)

        # Get MUD list from gateway or state
        if self.gateway:
            if refresh:
                # Request fresh mudlist from router
                mudlist = await self.gateway.request_mudlist()
            else:
                # Get cached mudlist
                mudlist = self.gateway.get_mudlist()

            # Log request
            await self.log_request(
                session,
                "mudlist",
                params,
                mudlist is not None,
                None if mudlist is not None else "Failed to get MUD list",
            )

            if mudlist is not None:
                # Apply filters if provided
                if "filter" in params:
                    mudlist = self._apply_mudlist_filters(mudlist, params["filter"])

                # Convert to list format
                mud_info = []
                for mud_name, info in mudlist.items():
                    mud_data = {
                        "name": mud_name,
                        "status": info.get("status", "unknown"),
                        "driver": info.get("driver", "unknown"),
                        "mud_type": info.get("mud_type", "unknown"),
                        "open_status": info.get("open_status", "unknown"),
                        "admin_email": info.get("admin_email", ""),
                        "services": info.get("services", {}),
                    }
                    mud_info.append(mud_data)

                return {
                    "status": "success",
                    "muds": mud_info,
                    "count": len(mud_info),
                    "refreshed": refresh,
                }
            return {"status": "failed", "message": "Could not retrieve MUD list"}

        return {"status": "unavailable", "message": "Gateway not connected"}

    def _apply_mudlist_filters(
        self, mudlist: Dict[str, Any], filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply filters to MUD list.

        Args:
            mudlist: Dictionary of MUDs
            filters: Filters to apply

        Returns:
            Filtered MUD list
        """
        filtered = {}

        for mud_name, info in mudlist.items():
            include = True

            # Filter by status
            if "status" in filters:
                status = filters["status"]
                if info.get("status", "down") != status:
                    include = False

            # Filter by driver
            if "driver" in filters and include:
                driver = filters["driver"].lower()
                if info.get("driver", "").lower() != driver:
                    include = False

            # Filter by service availability
            if "has_service" in filters and include:
                service = filters["has_service"]
                services = info.get("services", {})
                if not services.get(service, 0):
                    include = False

            if include:
                filtered[mud_name] = info

        return filtered
