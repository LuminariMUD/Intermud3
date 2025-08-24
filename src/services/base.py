"""Base service framework for I3 services.

This module provides the abstract base class for all I3 services
and the service registry for routing packets.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..models.packet import I3Packet, PacketType
from ..state.manager import StateManager


logger = logging.getLogger(__name__)


@dataclass
class ServiceMetrics:
    """Metrics for service performance tracking."""

    packets_handled: int = 0
    packets_failed: int = 0
    total_processing_time: float = 0.0

    @property
    def average_processing_time(self) -> float:
        """Calculate average processing time per packet."""
        if self.packets_handled == 0:
            return 0.0
        return self.total_processing_time / self.packets_handled


class BaseService(ABC):
    """Abstract base class for I3 services."""

    # Service metadata (to be overridden by subclasses)
    service_name: str = ""
    supported_packets: list[PacketType] = []
    requires_auth: bool = False

    def __init__(self, state_manager: StateManager):
        """Initialize the service.

        Args:
            state_manager: State manager instance
        """
        self.state_manager = state_manager
        self.metrics = ServiceMetrics()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the service.

        This method is called once when the service is registered.
        Override to perform service-specific initialization.
        """
        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown the service.

        This method is called when the service is being stopped.
        Override to perform service-specific cleanup.
        """
        self._initialized = False

    @abstractmethod
    async def handle_packet(self, packet: I3Packet) -> I3Packet | None:
        """Handle an incoming packet.

        Args:
            packet: The incoming I3 packet

        Returns:
            Optional response packet to send back
        """

    @abstractmethod
    async def validate_packet(self, packet: I3Packet) -> bool:
        """Validate a packet for this service.

        Args:
            packet: The packet to validate

        Returns:
            True if the packet is valid for this service
        """

    async def process_packet(self, packet: I3Packet) -> I3Packet | None:
        """Process a packet with validation and metrics.

        Args:
            packet: The incoming packet

        Returns:
            Optional response packet
        """
        import time

        if not self._initialized:
            logger.error(f"Service {self.service_name} not initialized")
            return None

        # Start timing
        start_time = time.time()

        try:
            # Validate packet
            if not await self.validate_packet(packet):
                logger.warning(
                    f"Invalid packet for service {self.service_name}: {packet.packet_type}"
                )
                self.metrics.packets_failed += 1
                return None

            # Handle packet
            response = await self.handle_packet(packet)

            # Update metrics
            self.metrics.packets_handled += 1
            self.metrics.total_processing_time += time.time() - start_time

            return response

        except Exception as e:
            logger.error(f"Error processing packet in {self.service_name}: {e}")
            self.metrics.packets_failed += 1
            return None

    def supports_packet_type(self, packet_type: PacketType) -> bool:
        """Check if this service supports a packet type.

        Args:
            packet_type: The packet type to check

        Returns:
            True if supported
        """
        return packet_type in self.supported_packets

    def get_metrics(self) -> ServiceMetrics:
        """Get service metrics.

        Returns:
            Service performance metrics
        """
        return self.metrics


class ServiceRegistry:
    """Registry for managing I3 services."""

    def __init__(self, state_manager: StateManager):
        """Initialize the service registry.

        Args:
            state_manager: State manager instance
        """
        self.state_manager = state_manager
        self._services: dict[str, BaseService] = {}
        self._packet_handlers: dict[PacketType, list[BaseService]] = {}
        self._lock = asyncio.Lock()

    async def register(self, service_class: type[BaseService]) -> BaseService:
        """Register a service.

        Args:
            service_class: The service class to register

        Returns:
            The instantiated service

        Raises:
            ValueError: If service is already registered
        """
        async with self._lock:
            # Instantiate the service
            service = service_class(self.state_manager)

            # Check if already registered
            if service.service_name in self._services:
                raise ValueError(f"Service {service.service_name} already registered")

            # Initialize the service
            await service.initialize()

            # Register the service
            self._services[service.service_name] = service

            # Register packet handlers
            for packet_type in service.supported_packets:
                if packet_type not in self._packet_handlers:
                    self._packet_handlers[packet_type] = []
                self._packet_handlers[packet_type].append(service)

            logger.info(f"Registered service: {service.service_name}")
            return service

    async def unregister(self, service_name: str) -> None:
        """Unregister a service.

        Args:
            service_name: Name of the service to unregister
        """
        async with self._lock:
            service = self._services.get(service_name)
            if not service:
                return

            # Shutdown the service
            await service.shutdown()

            # Remove from packet handlers
            for packet_type in service.supported_packets:
                if packet_type in self._packet_handlers:
                    self._packet_handlers[packet_type] = [
                        s
                        for s in self._packet_handlers[packet_type]
                        if s.service_name != service_name
                    ]
                    if not self._packet_handlers[packet_type]:
                        del self._packet_handlers[packet_type]

            # Remove from registry
            del self._services[service_name]

            logger.info(f"Unregistered service: {service_name}")

    async def route_packet(self, packet: I3Packet) -> I3Packet | None:
        """Route a packet to the appropriate service.

        Args:
            packet: The packet to route

        Returns:
            Optional response packet
        """
        handlers = self._packet_handlers.get(packet.packet_type, [])

        if not handlers:
            logger.warning(f"No handlers for packet type: {packet.packet_type}")
            return None

        # Try each handler until one succeeds
        for handler in handlers:
            try:
                response = await handler.process_packet(packet)
                if response:
                    return response
            except Exception as e:
                logger.error(f"Error in handler {handler.service_name}: {e}")

        return None

    def get_service(self, service_name: str) -> BaseService | None:
        """Get a registered service.

        Args:
            service_name: Name of the service

        Returns:
            The service instance or None
        """
        return self._services.get(service_name)

    def get_services(self) -> list[BaseService]:
        """Get all registered services.

        Returns:
            List of all services
        """
        return list(self._services.values())

    def get_supported_packets(self) -> set[PacketType]:
        """Get all supported packet types.

        Returns:
            Set of supported packet types
        """
        return set(self._packet_handlers.keys())

    async def shutdown_all(self) -> None:
        """Shutdown all registered services."""
        async with self._lock:
            # Shutdown all services
            shutdown_tasks = [service.shutdown() for service in self._services.values()]
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)

            # Clear registries
            self._services.clear()
            self._packet_handlers.clear()

            logger.info("All services shut down")


class ServiceManager:
    """High-level manager for I3 services."""

    def __init__(self, state_manager: StateManager):
        """Initialize the service manager.

        Args:
            state_manager: State manager instance
        """
        self.state_manager = state_manager
        self.registry = ServiceRegistry(state_manager)
        self._packet_queue: asyncio.Queue = asyncio.Queue()
        self._processing_task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the service manager."""
        if self._running:
            return

        self._running = True
        self._processing_task = asyncio.create_task(self._process_packets())
        logger.info("Service manager started")

    async def stop(self) -> None:
        """Stop the service manager."""
        if not self._running:
            return

        self._running = False

        # Cancel processing task
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        # Shutdown all services
        await self.registry.shutdown_all()

        logger.info("Service manager stopped")

    async def queue_packet(self, packet: I3Packet) -> None:
        """Queue a packet for processing.

        Args:
            packet: The packet to process
        """
        if not self._running:
            logger.warning("Service manager not running, dropping packet")
            return

        await self._packet_queue.put(packet)

    async def _process_packets(self) -> None:
        """Process packets from the queue."""
        while self._running:
            try:
                # Get packet from queue with timeout
                packet = await asyncio.wait_for(self._packet_queue.get(), timeout=1.0)

                # Route to appropriate service
                response = await self.registry.route_packet(packet)

                # If there's a response, it should be sent back
                # This would be handled by the gateway layer
                if response:
                    # TODO: Send response through gateway
                    pass

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing packet: {e}")

    def get_metrics(self) -> dict[str, ServiceMetrics]:
        """Get metrics for all services.

        Returns:
            Dictionary of service name to metrics
        """
        return {
            service.service_name: service.get_metrics() for service in self.registry.get_services()
        }
