"""Comprehensive unit tests for BaseService, ServiceRegistry, and ServiceManager."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.models.packet import I3Packet, PacketType
from src.services.base import BaseService, ServiceManager, ServiceMetrics, ServiceRegistry
from src.state.manager import StateManager


class MockService(BaseService):
    """Mock service implementation for testing."""

    service_name = "mock"
    supported_packets = [PacketType.TELL, PacketType.WHO_REQ]
    requires_auth = False

    def __init__(self, state_manager):
        super().__init__(state_manager)
        self.handled_packets = []
        self.validation_results = {}

    async def handle_packet(self, packet: I3Packet) -> I3Packet | None:
        """Mock packet handler."""
        self.handled_packets.append(packet)
        return None

    async def validate_packet(self, packet: I3Packet) -> bool:
        """Mock packet validator."""
        return self.validation_results.get(packet.packet_type, True)


class FailingService(BaseService):
    """Service that always fails for testing error handling."""

    service_name = "failing"
    supported_packets = [PacketType.EMOTETO]
    requires_auth = False

    async def handle_packet(self, packet: I3Packet) -> I3Packet | None:
        """Always raises an exception."""
        raise Exception("Service failure")

    async def validate_packet(self, packet: I3Packet) -> bool:
        """Always returns False."""
        return False


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager."""
    manager = Mock(spec=StateManager)
    return manager


@pytest.fixture
def mock_packet():
    """Create a mock packet."""
    packet = Mock(spec=I3Packet)
    packet.packet_type = PacketType.TELL
    packet.to_lpc_array.return_value = ["tell", 200, "mud1", "user1", "mud2", "user2"]
    return packet


class TestServiceMetrics:
    """Test ServiceMetrics functionality."""

    def test_initial_metrics(self):
        """Test initial metrics state."""
        metrics = ServiceMetrics()
        assert metrics.packets_handled == 0
        assert metrics.packets_failed == 0
        assert metrics.total_processing_time == 0.0
        assert metrics.average_processing_time == 0.0

    def test_average_processing_time_with_zero_packets(self):
        """Test average processing time with no packets."""
        metrics = ServiceMetrics()
        assert metrics.average_processing_time == 0.0

    def test_average_processing_time_calculation(self):
        """Test average processing time calculation."""
        metrics = ServiceMetrics()
        metrics.packets_handled = 5
        metrics.total_processing_time = 2.5
        assert metrics.average_processing_time == 0.5


class TestBaseService:
    """Test BaseService functionality."""

    async def test_initialization(self, mock_state_manager):
        """Test service initialization."""
        service = MockService(mock_state_manager)
        assert service.state_manager == mock_state_manager
        assert isinstance(service.metrics, ServiceMetrics)
        assert not service._initialized

    async def test_initialize_method(self, mock_state_manager):
        """Test service initialize method."""
        service = MockService(mock_state_manager)
        await service.initialize()
        assert service._initialized

    async def test_shutdown_method(self, mock_state_manager):
        """Test service shutdown method."""
        service = MockService(mock_state_manager)
        await service.initialize()
        assert service._initialized

        await service.shutdown()
        assert not service._initialized

    async def test_supports_packet_type(self, mock_state_manager):
        """Test packet type support checking."""
        service = MockService(mock_state_manager)
        assert service.supports_packet_type(PacketType.TELL)
        assert service.supports_packet_type(PacketType.WHO_REQ)
        assert not service.supports_packet_type(PacketType.CHANNEL_M)

    async def test_get_metrics(self, mock_state_manager):
        """Test getting service metrics."""
        service = MockService(mock_state_manager)
        metrics = service.get_metrics()
        assert isinstance(metrics, ServiceMetrics)
        assert metrics.packets_handled == 0

    async def test_process_packet_success(self, mock_state_manager, mock_packet):
        """Test successful packet processing."""
        service = MockService(mock_state_manager)
        await service.initialize()

        result = await service.process_packet(mock_packet)
        assert result is None
        assert service.metrics.packets_handled == 1
        assert service.metrics.packets_failed == 0
        assert service.metrics.total_processing_time > 0
        assert len(service.handled_packets) == 1

    async def test_process_packet_not_initialized(self, mock_state_manager, mock_packet):
        """Test packet processing when service not initialized."""
        service = MockService(mock_state_manager)
        # Don't initialize

        result = await service.process_packet(mock_packet)
        assert result is None
        assert service.metrics.packets_handled == 0
        assert service.metrics.packets_failed == 0
        assert len(service.handled_packets) == 0

    async def test_process_packet_validation_failure(self, mock_state_manager, mock_packet):
        """Test packet processing with validation failure."""
        service = MockService(mock_state_manager)
        service.validation_results[PacketType.TELL] = False
        await service.initialize()

        result = await service.process_packet(mock_packet)
        assert result is None
        assert service.metrics.packets_handled == 0
        assert service.metrics.packets_failed == 1
        assert len(service.handled_packets) == 0

    async def test_process_packet_handler_exception(self, mock_state_manager, mock_packet):
        """Test packet processing with handler exception."""
        service = FailingService(mock_state_manager)
        await service.initialize()

        result = await service.process_packet(mock_packet)
        assert result is None
        assert service.metrics.packets_handled == 0
        assert service.metrics.packets_failed == 1

    async def test_process_packet_timing(self, mock_state_manager, mock_packet):
        """Test that packet processing times are recorded."""
        service = MockService(mock_state_manager)
        await service.initialize()

        # Add delay to handler
        original_handler = service.handle_packet

        async def delayed_handler(packet):
            await asyncio.sleep(0.01)  # 10ms delay
            return await original_handler(packet)

        service.handle_packet = delayed_handler

        await service.process_packet(mock_packet)
        assert service.metrics.total_processing_time >= 0.01
        assert service.metrics.average_processing_time >= 0.01


class TestServiceRegistry:
    """Test ServiceRegistry functionality."""

    async def test_initialization(self, mock_state_manager):
        """Test registry initialization."""
        registry = ServiceRegistry(mock_state_manager)
        assert registry.state_manager == mock_state_manager
        assert len(registry._services) == 0
        assert len(registry._packet_handlers) == 0

    async def test_register_service(self, mock_state_manager):
        """Test service registration."""
        registry = ServiceRegistry(mock_state_manager)

        service = await registry.register(MockService)
        assert isinstance(service, MockService)
        assert service._initialized
        assert "mock" in registry._services
        assert PacketType.TELL in registry._packet_handlers
        assert PacketType.WHO_REQ in registry._packet_handlers

    async def test_register_duplicate_service(self, mock_state_manager):
        """Test registering duplicate service raises error."""
        registry = ServiceRegistry(mock_state_manager)

        await registry.register(MockService)

        with pytest.raises(ValueError, match="already registered"):
            await registry.register(MockService)

    async def test_unregister_service(self, mock_state_manager):
        """Test service unregistration."""
        registry = ServiceRegistry(mock_state_manager)

        service = await registry.register(MockService)
        assert "mock" in registry._services

        await registry.unregister("mock")
        assert "mock" not in registry._services
        assert not service._initialized

    async def test_unregister_nonexistent_service(self, mock_state_manager):
        """Test unregistering nonexistent service does nothing."""
        registry = ServiceRegistry(mock_state_manager)

        # Should not raise an error
        await registry.unregister("nonexistent")

    async def test_route_packet_success(self, mock_state_manager, mock_packet):
        """Test successful packet routing."""
        registry = ServiceRegistry(mock_state_manager)
        service = await registry.register(MockService)

        result = await registry.route_packet(mock_packet)
        assert result is None
        assert len(service.handled_packets) == 1

    async def test_route_packet_no_handlers(self, mock_state_manager):
        """Test routing packet with no handlers."""
        registry = ServiceRegistry(mock_state_manager)

        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.CHANNEL_M

        result = await registry.route_packet(packet)
        assert result is None

    async def test_route_packet_handler_failure(self, mock_state_manager, mock_packet):
        """Test routing packet when handler fails."""
        registry = ServiceRegistry(mock_state_manager)
        await registry.register(FailingService)

        # Create packet for failing service
        packet = Mock(spec=I3Packet)
        packet.packet_type = PacketType.EMOTETO

        result = await registry.route_packet(packet)
        assert result is None

    async def test_get_service(self, mock_state_manager):
        """Test getting registered service."""
        registry = ServiceRegistry(mock_state_manager)
        service = await registry.register(MockService)

        retrieved = registry.get_service("mock")
        assert retrieved == service

        not_found = registry.get_service("nonexistent")
        assert not_found is None

    async def test_get_services(self, mock_state_manager):
        """Test getting all services."""
        registry = ServiceRegistry(mock_state_manager)
        service = await registry.register(MockService)

        services = registry.get_services()
        assert len(services) == 1
        assert services[0] == service

    async def test_get_supported_packets(self, mock_state_manager):
        """Test getting supported packet types."""
        registry = ServiceRegistry(mock_state_manager)
        await registry.register(MockService)

        packets = registry.get_supported_packets()
        assert PacketType.TELL in packets
        assert PacketType.WHO_REQ in packets

    async def test_shutdown_all(self, mock_state_manager):
        """Test shutting down all services."""
        registry = ServiceRegistry(mock_state_manager)
        service1 = await registry.register(MockService)

        # Create another service class
        class MockService2(BaseService):
            service_name = "mock2"
            supported_packets = [PacketType.FINGER_REQ]
            requires_auth = False

            async def handle_packet(self, packet):
                return None

            async def validate_packet(self, packet):
                return True

        service2 = await registry.register(MockService2)

        assert service1._initialized
        assert service2._initialized
        assert len(registry._services) == 2

        await registry.shutdown_all()

        assert not service1._initialized
        assert not service2._initialized
        assert len(registry._services) == 0
        assert len(registry._packet_handlers) == 0


class TestServiceManager:
    """Test ServiceManager functionality."""

    async def test_initialization(self, mock_state_manager):
        """Test manager initialization."""
        manager = ServiceManager(mock_state_manager)
        assert manager.state_manager == mock_state_manager
        assert isinstance(manager.registry, ServiceRegistry)
        assert not manager._running
        assert manager._processing_task is None

    async def test_start_stop(self, mock_state_manager):
        """Test starting and stopping the service manager."""
        manager = ServiceManager(mock_state_manager)

        assert not manager._running

        await manager.start()
        assert manager._running
        assert manager._processing_task is not None

        await manager.stop()
        assert not manager._running
        # Task may be cancelled but not None immediately after cancellation
        assert manager._processing_task.cancelled() or manager._processing_task.done()

    async def test_start_when_already_running(self, mock_state_manager):
        """Test starting when already running does nothing."""
        manager = ServiceManager(mock_state_manager)

        await manager.start()
        task1 = manager._processing_task

        await manager.start()  # Should do nothing
        task2 = manager._processing_task

        assert task1 == task2

        await manager.stop()

    async def test_stop_when_not_running(self, mock_state_manager):
        """Test stopping when not running does nothing."""
        manager = ServiceManager(mock_state_manager)

        # Should not raise an error
        await manager.stop()

    async def test_queue_packet_when_running(self, mock_state_manager, mock_packet):
        """Test queuing packet when manager is running."""
        manager = ServiceManager(mock_state_manager)
        await manager.start()

        # Queue should be empty initially
        assert manager._packet_queue.qsize() == 0

        await manager.queue_packet(mock_packet)
        assert manager._packet_queue.qsize() == 1

        await manager.stop()

    async def test_queue_packet_when_not_running(self, mock_state_manager, mock_packet):
        """Test queuing packet when manager is not running."""
        manager = ServiceManager(mock_state_manager)

        # Should not queue packet
        await manager.queue_packet(mock_packet)
        assert manager._packet_queue.qsize() == 0

    async def test_packet_processing(self, mock_state_manager, mock_packet):
        """Test that queued packets are processed."""
        manager = ServiceManager(mock_state_manager)
        service = await manager.registry.register(MockService)

        await manager.start()
        await manager.queue_packet(mock_packet)

        # Give processing loop time to handle packet
        await asyncio.sleep(0.1)

        assert len(service.handled_packets) == 1
        assert service.handled_packets[0] == mock_packet

        await manager.stop()

    async def test_get_metrics(self, mock_state_manager):
        """Test getting metrics from all services."""
        manager = ServiceManager(mock_state_manager)
        service = await manager.registry.register(MockService)

        metrics = manager.get_metrics()
        assert "mock" in metrics
        assert isinstance(metrics["mock"], ServiceMetrics)

    async def test_processing_task_exception_handling(self, mock_state_manager):
        """Test that processing task handles exceptions gracefully."""
        manager = ServiceManager(mock_state_manager)

        # Mock the registry to raise an exception
        manager.registry.route_packet = AsyncMock(side_effect=Exception("Test error"))

        await manager.start()

        # Queue a packet that will cause the exception
        packet = Mock(spec=I3Packet)
        await manager.queue_packet(packet)

        # Give time for processing and error handling
        await asyncio.sleep(0.1)

        # Manager should still be running despite the exception
        assert manager._running

        await manager.stop()

    async def test_processing_timeout_handling(self, mock_state_manager):
        """Test that processing task handles timeouts correctly."""
        manager = ServiceManager(mock_state_manager)

        await manager.start()

        # Don't queue any packets - should timeout and continue
        await asyncio.sleep(0.1)

        assert manager._running

        await manager.stop()


class TestIntegration:
    """Integration tests for service components."""

    async def test_full_service_lifecycle(self, mock_state_manager, mock_packet):
        """Test complete service lifecycle."""
        # Create manager
        manager = ServiceManager(mock_state_manager)

        # Register service
        service = await manager.registry.register(MockService)
        assert service._initialized

        # Start manager
        await manager.start()

        # Process packet
        await manager.queue_packet(mock_packet)
        await asyncio.sleep(0.1)

        assert len(service.handled_packets) == 1
        assert service.metrics.packets_handled == 1

        # Get metrics
        metrics = manager.get_metrics()
        assert metrics["mock"].packets_handled == 1

        # Stop manager
        await manager.stop()
        assert not service._initialized

    async def test_multiple_services_packet_routing(self, mock_state_manager):
        """Test packet routing between multiple services."""
        registry = ServiceRegistry(mock_state_manager)

        # Register multiple services
        service1 = await registry.register(MockService)

        class MockService2(BaseService):
            service_name = "mock2"
            supported_packets = [PacketType.CHANNEL_M]
            requires_auth = False

            def __init__(self, state_manager):
                super().__init__(state_manager)
                self.handled_packets = []

            async def handle_packet(self, packet):
                self.handled_packets.append(packet)

            async def validate_packet(self, packet):
                return True

        service2 = await registry.register(MockService2)

        # Create packets for different services
        packet1 = Mock(spec=I3Packet)
        packet1.packet_type = PacketType.TELL

        packet2 = Mock(spec=I3Packet)
        packet2.packet_type = PacketType.CHANNEL_M

        # Route packets
        await registry.route_packet(packet1)
        await registry.route_packet(packet2)

        # Check routing
        assert len(service1.handled_packets) == 1
        assert len(service2.handled_packets) == 1
        assert service1.handled_packets[0] == packet1
        assert service2.handled_packets[0] == packet2
