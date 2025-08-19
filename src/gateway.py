"""Main I3 Gateway implementation."""

import asyncio
from typing import Optional

import structlog

from .config.models import Settings


class I3Gateway:
    """Main I3 Gateway service."""
    
    def __init__(self, settings: Settings) -> None:
        """Initialize the I3 Gateway."""
        self.settings = settings
        self.logger = structlog.get_logger()
        self.running = False
        self._shutdown_event = asyncio.Event()
    
    async def start(self) -> None:
        """Start the I3 Gateway service."""
        self.logger.info(
            "Starting I3 Gateway",
            mud_name=self.settings.mud.name,
            router=self.settings.router.primary.host,
        )
        
        self.running = True
        
        # TODO: Initialize components
        # - Network connection to I3 router
        # - Service registry
        # - API server
        # - State manager
        
        self.logger.info("I3 Gateway started successfully")
    
    async def shutdown(self) -> None:
        """Shutdown the I3 Gateway service."""
        self.logger.info("Shutting down I3 Gateway...")
        self.running = False
        
        # TODO: Cleanup components
        
        self._shutdown_event.set()
        self.logger.info("I3 Gateway shutdown complete")
    
    async def wait_for_shutdown(self) -> None:
        """Wait for the gateway to shutdown."""
        await self._shutdown_event.wait()