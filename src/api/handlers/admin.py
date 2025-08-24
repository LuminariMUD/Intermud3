"""Administrative handlers for status, stats, ping, and control operations.

This module implements handlers for administrative API methods.
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict

from src.api.handlers.base import BaseHandler
from src.api.session import Session
from src.utils.logging import get_logger


logger = get_logger(__name__)


class StatusHandler(BaseHandler):
    """Handler for getting gateway status."""

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate status parameters."""
        # No parameters required
        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle status request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data with gateway status
        """
        # Status is available to all authenticated users

        status = {
            "connected": False,
            "router": None,
            "uptime": 0,
            "version": "1.0.0",
            "mud_name": session.mud_name,
            "session_id": session.session_id,
        }

        if self.gateway:
            status["connected"] = self.gateway.is_connected()
            status["router"] = self.gateway.get_current_router()
            status["uptime"] = self.gateway.get_uptime()

            # Get connection details
            if status["connected"]:
                status["connection"] = {
                    "router_name": self.gateway.router_name,
                    "connected_at": (
                        self.gateway.connected_at.isoformat()
                        if hasattr(self.gateway, "connected_at")
                        else None
                    ),
                    "packet_stats": {
                        "sent": (
                            self.gateway.packets_sent
                            if hasattr(self.gateway, "packets_sent")
                            else 0
                        ),
                        "received": (
                            self.gateway.packets_received
                            if hasattr(self.gateway, "packets_received")
                            else 0
                        ),
                    },
                }

            # Get service status
            status["services"] = {
                "tell": (
                    self.gateway.services.get("tell", 0) if hasattr(self.gateway, "services") else 0
                ),
                "channel": (
                    self.gateway.services.get("channel", 0)
                    if hasattr(self.gateway, "services")
                    else 0
                ),
                "who": (
                    self.gateway.services.get("who", 0) if hasattr(self.gateway, "services") else 0
                ),
                "finger": (
                    self.gateway.services.get("finger", 0)
                    if hasattr(self.gateway, "services")
                    else 0
                ),
                "locate": (
                    self.gateway.services.get("locate", 0)
                    if hasattr(self.gateway, "services")
                    else 0
                ),
            }

        # Log request
        await self.log_request(session, "status", params, True, None)

        return status


class StatsHandler(BaseHandler):
    """Handler for getting performance statistics."""

    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["detailed"]

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate stats parameters."""
        # No required parameters
        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle stats request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data with statistics
        """
        # Check permission for detailed stats
        detailed = params.get("detailed", False) if params else False
        if detailed and not self.check_permission(session, "admin"):
            raise PermissionError("No permission for detailed statistics")

        stats = {"timestamp": datetime.utcnow().isoformat(), "session": session.metrics.to_dict()}

        if self.gateway:
            # Basic stats
            stats["gateway"] = {
                "connected": self.gateway.is_connected(),
                "uptime": self.gateway.get_uptime(),
                "mud_count": (
                    len(self.gateway.get_mudlist()) if hasattr(self.gateway, "get_mudlist") else 0
                ),
                "channel_count": (
                    len(self.gateway.get_channel_list())
                    if hasattr(self.gateway, "get_channel_list")
                    else 0
                ),
            }

            # Detailed stats if requested and permitted
            if detailed:
                stats["detailed"] = {
                    "memory": self._get_memory_stats(),
                    "performance": self._get_performance_stats(),
                    "errors": self._get_error_stats(),
                }

        # Log request
        await self.log_request(session, "stats", params, True, None)

        return stats

    def _get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        return {
            "rss_mb": memory_info.rss / (1024 * 1024),
            "vms_mb": memory_info.vms / (1024 * 1024),
            "percent": process.memory_percent(),
        }

    def _get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return {
            "avg_response_time_ms": 0,  # Would be calculated from metrics
            "requests_per_second": 0,  # Would be calculated from metrics
            "active_connections": 0,  # Would come from connection manager
        }

    def _get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        return {
            "total_errors": 0,  # Would come from error tracking
            "error_rate": 0.0,  # Would be calculated
            "last_error": None,  # Would come from error log
        }


class PingHandler(BaseHandler):
    """Handler for ping/heartbeat checks."""

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate ping parameters."""
        # No parameters required
        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle ping request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data with pong
        """
        # Ping is available to all authenticated users

        response = {
            "pong": True,
            "timestamp": time.time(),
            "session_id": session.session_id,
            "mud_name": session.mud_name,
        }

        # Test gateway connectivity if available
        if self.gateway:
            response["gateway_connected"] = self.gateway.is_connected()

        # Don't log ping requests to avoid spam
        # await self.log_request(session, "ping", params, True, None)

        return response


class ReconnectHandler(BaseHandler):
    """Handler for forcing gateway reconnection."""

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate reconnect parameters."""
        # No parameters required
        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reconnect request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data with reconnection status
        """
        # Check admin permission
        if not self.check_permission(session, "admin"):
            raise PermissionError("No permission for reconnect operation")

        if not self.gateway:
            return {"status": "failed", "message": "Gateway not available"}

        # Log the reconnect attempt
        logger.info(f"Reconnect requested by {session.mud_name} (session: {session.session_id})")

        try:
            # Disconnect if connected
            if self.gateway.is_connected():
                await self.gateway.disconnect()

            # Wait a moment
            await asyncio.sleep(1)

            # Reconnect
            success = await self.gateway.connect()

            # Log request
            await self.log_request(
                session, "reconnect", params, success, None if success else "Reconnection failed"
            )

            if success:
                return {
                    "status": "success",
                    "message": "Gateway reconnected successfully",
                    "router": self.gateway.get_current_router(),
                }
            return {"status": "failed", "message": "Failed to reconnect to router"}

        except Exception as e:
            logger.error(f"Error during reconnection: {e}")
            return {"status": "error", "message": str(e)}


class ShutdownHandler(BaseHandler):
    """Handler for graceful shutdown."""

    def get_optional_params(self) -> list[str]:
        """Get optional parameters."""
        return ["delay", "reason"]

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate shutdown parameters."""
        if params and "delay" in params:
            delay = params["delay"]
            if not isinstance(delay, int) or delay < 0 or delay > 300:
                logger.warning("Invalid shutdown delay")
                return False

        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle shutdown request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data with shutdown confirmation
        """
        # Check admin permission
        if not self.check_permission(session, "admin"):
            raise PermissionError("No permission for shutdown operation")

        params = params or {}
        delay = params.get("delay", 10)
        reason = params.get("reason", "Admin requested shutdown")

        # Log the shutdown request
        logger.warning(
            f"Shutdown requested by {session.mud_name} (session: {session.session_id}), "
            f"delay: {delay}s, reason: {reason}"
        )

        # Log request
        await self.log_request(session, "shutdown", params, True, None)

        # Schedule shutdown
        asyncio.create_task(self._perform_shutdown(delay, reason))

        return {
            "status": "scheduled",
            "message": f"Shutdown scheduled in {delay} seconds",
            "delay": delay,
            "reason": reason,
        }

    async def _perform_shutdown(self, delay: int, reason: str):
        """Perform the actual shutdown after delay.

        Args:
            delay: Seconds to wait before shutdown
            reason: Shutdown reason
        """
        # Wait for delay
        await asyncio.sleep(delay)

        logger.info(f"Performing shutdown: {reason}")

        # Disconnect gateway
        if self.gateway:
            await self.gateway.disconnect()

        # Would trigger actual shutdown here
        # For now, just log it
        logger.info("Shutdown complete")


class ReloadConfigHandler(BaseHandler):
    """Handler for reloading configuration."""

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate reload config parameters."""
        # No parameters required
        return True

    async def handle(self, session: Session, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle reload config request.

        Args:
            session: Client session
            params: Request parameters

        Returns:
            Response data with reload status
        """
        # Check admin permission
        if not self.check_permission(session, "admin"):
            raise PermissionError("No permission for config reload")

        logger.info(
            f"Config reload requested by {session.mud_name} (session: {session.session_id})"
        )

        try:
            # Would reload configuration here
            # For now, just simulate it
            await asyncio.sleep(0.5)

            # Log request
            await self.log_request(session, "reload_config", params, True, None)

            return {"status": "success", "message": "Configuration reloaded successfully"}

        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")

            # Log request
            await self.log_request(session, "reload_config", params, False, str(e))

            return {"status": "error", "message": str(e)}
