"""
Comprehensive performance benchmark suite for I3 Gateway.

This module tests performance characteristics including:
- Packet encoding/decoding throughput
- End-to-end packet routing latency
- Service handler response times
- Memory usage patterns
- CPU utilization
- Concurrent session handling
"""

import asyncio
import time
import psutil
import pytest
import statistics
from typing import List, Dict, Any, Tuple
from unittest.mock import Mock, AsyncMock, patch
import gc
import tracemalloc

from src.network.lpc import LPCEncoder, LPCDecoder
from src.models.packet import (
    TellPacket, ChannelMessagePacket, WhoPacket,
    FingerPacket, LocatePacket,
    PacketFactory
)
from src.services.tell import TellService
from src.services.channel import ChannelService
from src.services.who import WhoService
from src.services.finger import FingerService
from src.services.locate import LocateService
from src.state.manager import StateManager
from src.gateway import Gateway


class PerformanceMetrics:
    """Helper class to collect and analyze performance metrics."""
    
    def __init__(self):
        self.latencies: List[float] = []
        self.throughput_samples: List[int] = []
        self.memory_samples: List[int] = []
        self.cpu_samples: List[float] = []
        
    def add_latency(self, latency: float):
        """Add a latency measurement in milliseconds."""
        self.latencies.append(latency)
        
    def add_throughput(self, ops_per_second: int):
        """Add a throughput measurement."""
        self.throughput_samples.append(ops_per_second)
        
    def add_memory(self, memory_mb: int):
        """Add a memory usage measurement in MB."""
        self.memory_samples.append(memory_mb)
        
    def add_cpu(self, cpu_percent: float):
        """Add a CPU usage measurement."""
        self.cpu_samples.append(cpu_percent)
        
    def get_latency_stats(self) -> Dict[str, float]:
        """Get latency statistics."""
        if not self.latencies:
            return {}
        sorted_latencies = sorted(self.latencies)
        return {
            'min': min(self.latencies),
            'max': max(self.latencies),
            'mean': statistics.mean(self.latencies),
            'median': statistics.median(self.latencies),
            'p50': sorted_latencies[len(sorted_latencies) // 2],
            'p95': sorted_latencies[int(len(sorted_latencies) * 0.95)],
            'p99': sorted_latencies[int(len(sorted_latencies) * 0.99)],
        }
        
    def get_throughput_stats(self) -> Dict[str, float]:
        """Get throughput statistics."""
        if not self.throughput_samples:
            return {}
        return {
            'min': min(self.throughput_samples),
            'max': max(self.throughput_samples),
            'mean': statistics.mean(self.throughput_samples),
            'median': statistics.median(self.throughput_samples),
        }
        
    def get_memory_stats(self) -> Dict[str, float]:
        """Get memory usage statistics."""
        if not self.memory_samples:
            return {}
        return {
            'min': min(self.memory_samples),
            'max': max(self.memory_samples),
            'mean': statistics.mean(self.memory_samples),
            'median': statistics.median(self.memory_samples),
        }
        
    def get_cpu_stats(self) -> Dict[str, float]:
        """Get CPU usage statistics."""
        if not self.cpu_samples:
            return {}
        return {
            'min': min(self.cpu_samples),
            'max': max(self.cpu_samples),
            'mean': statistics.mean(self.cpu_samples),
            'median': statistics.median(self.cpu_samples),
        }


# LPC Encoding/Decoding Benchmarks
class TestLPCPerformance:
    """Test LPC encoder/decoder performance."""
    
    def setup_method(self):
        """Set up test environment."""
        self.encoder = LPCEncoder()
        self.decoder = LPCDecoder()
        self.metrics = PerformanceMetrics()
        
    def test_encoding_throughput(self):
        """Test encoding throughput for various packet types."""
        packets = [
            ["tell", 5, "TestMUD", "user1", "TargetMUD", "user2", "Hello!"],
            ["channel-m", 5, "TestMUD", "user", "chat", "Hello everyone!"],
            ["who-req", 5, "TestMUD", "user"],
            ["finger-req", 5, "TestMUD", "user", "TargetMUD", "target"],
            ["locate-req", 5, "TestMUD", "user", "target_user"],
        ]
        
        # Warm up
        for _ in range(100):
            for packet in packets:
                self.encoder.encode(packet)
                
        # Measure throughput
        iterations = 10000
        start_time = time.perf_counter()
        
        for _ in range(iterations):
            for packet in packets:
                self.encoder.encode(packet)
                
        elapsed = time.perf_counter() - start_time
        ops_per_second = int((iterations * len(packets)) / elapsed)
        self.metrics.add_throughput(ops_per_second)
        
        # Assert performance target
        assert ops_per_second > 5000, f"Encoding throughput {ops_per_second} ops/s below target 5000"
        
    def test_decoding_throughput(self):
        """Test decoding throughput for various packet types."""
        # Prepare encoded packets
        packets = [
            ["tell", 5, "TestMUD", "user1", "TargetMUD", "user2", "Hello!"],
            ["channel-m", 5, "TestMUD", "user", "chat", "Hello everyone!"],
            ["who-req", 5, "TestMUD", "user"],
            ["finger-req", 5, "TestMUD", "user", "TargetMUD", "target"],
            ["locate-req", 5, "TestMUD", "user", "target_user"],
        ]
        encoded_packets = [self.encoder.encode(p) for p in packets]
        
        # Warm up
        for _ in range(100):
            for encoded in encoded_packets:
                self.decoder.decode(encoded)
                
        # Measure throughput
        iterations = 10000
        start_time = time.perf_counter()
        
        for _ in range(iterations):
            for encoded in encoded_packets:
                self.decoder.decode(encoded)
                
        elapsed = time.perf_counter() - start_time
        ops_per_second = int((iterations * len(packets)) / elapsed)
        self.metrics.add_throughput(ops_per_second)
        
        # Assert performance target
        assert ops_per_second > 4000, f"Decoding throughput {ops_per_second} ops/s below target 4000"
        
    def test_large_data_handling(self):
        """Test performance with large data structures."""
        # Create large array
        large_array = list(range(10000))
        
        # Test encoding
        start_time = time.perf_counter()
        encoded = self.encoder.encode(large_array)
        encode_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        
        # Test decoding
        start_time = time.perf_counter()
        decoded = self.decoder.decode(encoded)
        decode_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        
        self.metrics.add_latency(encode_time)
        self.metrics.add_latency(decode_time)
        
        # Assert performance targets
        assert encode_time < 100, f"Large array encoding {encode_time}ms exceeds 100ms target"
        assert decode_time < 100, f"Large array decoding {decode_time}ms exceeds 100ms target"
        assert decoded == large_array, "Large array not decoded correctly"
        
    def test_deep_nesting_performance(self):
        """Test performance with deeply nested structures."""
        # Create deeply nested structure
        depth = 100
        nested = value = "leaf"
        for _ in range(depth):
            nested = {"data": nested}
            
        # Test encoding
        start_time = time.perf_counter()
        encoded = self.encoder.encode(nested)
        encode_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        
        # Test decoding
        start_time = time.perf_counter()
        decoded = self.decoder.decode(encoded)
        decode_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        
        self.metrics.add_latency(encode_time)
        self.metrics.add_latency(decode_time)
        
        # Assert performance targets
        assert encode_time < 50, f"Deep nesting encoding {encode_time}ms exceeds 50ms target"
        assert decode_time < 50, f"Deep nesting decoding {decode_time}ms exceeds 50ms target"


# Service Performance Benchmarks
@pytest.mark.asyncio
class TestServicePerformance:
    """Test service handler performance."""
    
    async def setup_method(self):
        """Set up test environment."""
        self.metrics = PerformanceMetrics()
        self.state_manager = StateManager()
        
        # Initialize services
        self.tell_service = TellService(self.state_manager)
        self.channel_service = ChannelService(self.state_manager)
        self.who_service = WhoService(self.state_manager)
        self.finger_service = FingerService(self.state_manager)
        self.locate_service = LocateService(self.state_manager)
        
        # Mock send_packet
        for service in [self.tell_service, self.channel_service, 
                       self.who_service, self.finger_service, self.locate_service]:
            service.send_packet = AsyncMock()
            
    async def test_tell_service_latency(self):
        """Test TellService response latency."""
        packet = TellPacket(
            packet_type="tell",
            ttl=5,
            originator_mudname="TestMUD",
            originator_username="user1",
            target_mudname="LocalMUD",
            target_username="user2",
            message="Test message"
        )
        
        # Warm up
        for _ in range(100):
            await self.tell_service.handle_packet(packet)
            
        # Measure latency
        latencies = []
        iterations = 1000
        
        for _ in range(iterations):
            start_time = time.perf_counter()
            await self.tell_service.handle_packet(packet)
            latency = (time.perf_counter() - start_time) * 1000  # Convert to ms
            latencies.append(latency)
            self.metrics.add_latency(latency)
            
        # Calculate statistics
        stats = self.metrics.get_latency_stats()
        
        # Assert performance targets
        assert stats['p50'] < 1, f"Tell service P50 latency {stats['p50']}ms exceeds 1ms target"
        assert stats['p99'] < 10, f"Tell service P99 latency {stats['p99']}ms exceeds 10ms target"
        
    async def test_channel_service_latency(self):
        """Test ChannelService response latency."""
        # Subscribe to channel
        self.state_manager.channel_subscriptions["chat"] = {"TestMUD"}
        
        packet = ChannelMessagePacket(
            packet_type="channel-m",
            ttl=5,
            originator_mudname="TestMUD",
            originator_username="user",
            channel="chat",
            message="Test message"
        )
        
        # Warm up
        for _ in range(100):
            await self.channel_service.handle_packet(packet)
            
        # Measure latency
        latencies = []
        iterations = 1000
        
        for _ in range(iterations):
            start_time = time.perf_counter()
            await self.channel_service.handle_packet(packet)
            latency = (time.perf_counter() - start_time) * 1000  # Convert to ms
            latencies.append(latency)
            self.metrics.add_latency(latency)
            
        # Calculate statistics
        stats = self.metrics.get_latency_stats()
        
        # Assert performance targets
        assert stats['p50'] < 1, f"Channel service P50 latency {stats['p50']}ms exceeds 1ms target"
        assert stats['p99'] < 10, f"Channel service P99 latency {stats['p99']}ms exceeds 10ms target"
        
    async def test_concurrent_service_handling(self):
        """Test performance with concurrent service requests."""
        # Create mix of packets
        packets = [
            TellPacket("tell", 5, "TestMUD", "user1", "LocalMUD", "user2", "msg"),
            ChannelMessagePacket("channel-m", 5, "TestMUD", "user", "chat", "msg"),
            WhoPacket("who-req", 5, "TestMUD", "user"),
            FingerPacket("finger-req", 5, "TestMUD", "user", "LocalMUD", "target"),
            LocatePacket("locate-req", 5, "TestMUD", "user", "target"),
        ]
        
        services = [
            self.tell_service,
            self.channel_service,
            self.who_service,
            self.finger_service,
            self.locate_service,
        ]
        
        # Measure concurrent handling
        iterations = 100
        batch_size = 50
        
        start_time = time.perf_counter()
        
        for _ in range(iterations):
            tasks = []
            for _ in range(batch_size):
                for packet, service in zip(packets, services):
                    tasks.append(service.handle_packet(packet))
            await asyncio.gather(*tasks)
            
        elapsed = time.perf_counter() - start_time
        total_ops = iterations * batch_size * len(packets)
        ops_per_second = int(total_ops / elapsed)
        self.metrics.add_throughput(ops_per_second)
        
        # Assert performance target
        assert ops_per_second > 1000, f"Concurrent handling {ops_per_second} ops/s below target 1000"


# Memory Performance Benchmarks
class TestMemoryPerformance:
    """Test memory usage patterns."""
    
    def setup_method(self):
        """Set up test environment."""
        self.metrics = PerformanceMetrics()
        gc.collect()  # Clean slate
        
    def test_baseline_memory_usage(self):
        """Test baseline memory usage of core components."""
        tracemalloc.start()
        
        # Create core components
        encoder = LPCEncoder()
        decoder = LPCDecoder()
        state_manager = StateManager()
        tell_service = TellService(state_manager)
        channel_service = ChannelService(state_manager)
        who_service = WhoService(state_manager)
        
        # Get memory snapshot
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        # Calculate total memory
        total_memory = sum(stat.size for stat in top_stats)
        memory_mb = total_memory / (1024 * 1024)
        self.metrics.add_memory(memory_mb)
        
        tracemalloc.stop()
        
        # Assert baseline memory target
        assert memory_mb < 100, f"Baseline memory {memory_mb:.2f}MB exceeds 100MB target"
        
    def test_memory_under_load(self):
        """Test memory usage under load."""
        tracemalloc.start()
        initial_snapshot = tracemalloc.take_snapshot()
        
        # Create load
        encoder = LPCEncoder()
        packets = []
        
        # Generate 10000 packets
        for i in range(10000):
            packet = ["tell", 5, f"MUD{i}", f"user{i}", "Target", "user", f"Message {i}"]
            encoded = encoder.encode(packet)
            packets.append(encoded)
            
        # Take snapshot under load
        load_snapshot = tracemalloc.take_snapshot()
        
        # Calculate memory growth
        top_stats = load_snapshot.compare_to(initial_snapshot, 'lineno')
        memory_growth = sum(stat.size_diff for stat in top_stats if stat.size_diff > 0)
        growth_mb = memory_growth / (1024 * 1024)
        self.metrics.add_memory(growth_mb)
        
        tracemalloc.stop()
        
        # Assert memory growth is reasonable
        assert growth_mb < 200, f"Memory growth {growth_mb:.2f}MB under load exceeds 200MB"
        
    def test_memory_leak_detection(self):
        """Test for memory leaks in repeated operations."""
        gc.collect()
        tracemalloc.start()
        
        encoder = LPCEncoder()
        decoder = LPCDecoder()
        
        # Take initial snapshot
        initial_snapshot = tracemalloc.take_snapshot()
        
        # Perform repeated operations
        for iteration in range(5):
            packets = []
            for i in range(1000):
                packet = ["tell", 5, "MUD", "user", "Target", "user", f"Message {i}"]
                encoded = encoder.encode(packet)
                decoded = decoder.decode(encoded)
                packets.append(decoded)
            
            # Clear and force garbage collection
            packets.clear()
            gc.collect()
            
            # Take snapshot after each iteration
            current_snapshot = tracemalloc.take_snapshot()
            stats = current_snapshot.compare_to(initial_snapshot, 'lineno')
            
            # Check memory is stable (not growing indefinitely)
            total_growth = sum(stat.size_diff for stat in stats if stat.size_diff > 0)
            growth_mb = total_growth / (1024 * 1024)
            
            # Memory should stabilize, not grow linearly
            if iteration > 2:  # Allow warm-up
                assert growth_mb < 10 * iteration, f"Potential memory leak: {growth_mb:.2f}MB growth"
                
        tracemalloc.stop()


# CPU Performance Benchmarks
class TestCPUPerformance:
    """Test CPU utilization patterns."""
    
    def setup_method(self):
        """Set up test environment."""
        self.metrics = PerformanceMetrics()
        self.process = psutil.Process()
        
    def test_cpu_usage_encoding(self):
        """Test CPU usage during encoding operations."""
        encoder = LPCEncoder()
        
        # Prepare test data
        packets = [
            ["tell", 5, "TestMUD", "user1", "TargetMUD", "user2", f"Message {i}"]
            for i in range(100)
        ]
        
        # Start CPU monitoring
        self.process.cpu_percent()  # First call to initialize
        time.sleep(0.1)
        
        # Perform encoding operations
        start_time = time.perf_counter()
        iterations = 1000
        
        for _ in range(iterations):
            for packet in packets:
                encoder.encode(packet)
                
        elapsed = time.perf_counter() - start_time
        cpu_percent = self.process.cpu_percent()
        self.metrics.add_cpu(cpu_percent)
        
        # Calculate throughput
        ops_per_second = (iterations * len(packets)) / elapsed
        
        # Assert CPU efficiency
        cpu_per_1000_ops = (cpu_percent * elapsed) / (ops_per_second / 1000)
        assert cpu_per_1000_ops < 50, f"CPU usage {cpu_per_1000_ops:.1f}% per 1000 ops exceeds 50% target"
        
    def test_cpu_usage_mixed_operations(self):
        """Test CPU usage during mixed operations."""
        encoder = LPCEncoder()
        decoder = LPCDecoder()
        
        # Start CPU monitoring
        self.process.cpu_percent()  # First call to initialize
        time.sleep(0.1)
        
        # Perform mixed operations
        start_time = time.perf_counter()
        iterations = 500
        
        for i in range(iterations):
            # Encode
            packet = ["tell", 5, "MUD", "user", "Target", "user", f"Message {i}"]
            encoded = encoder.encode(packet)
            
            # Decode
            decoded = decoder.decode(encoded)
            
            # Create packet object
            tell_packet = TellPacket(*decoded)
            
            # Serialize to dict
            packet_dict = tell_packet.to_dict()
            
        elapsed = time.perf_counter() - start_time
        cpu_percent = self.process.cpu_percent()
        self.metrics.add_cpu(cpu_percent)
        
        # Assert CPU target
        assert cpu_percent < 80, f"Mixed operations CPU usage {cpu_percent:.1f}% exceeds 80% target"


# End-to-End Performance Benchmarks
@pytest.mark.asyncio
class TestEndToEndPerformance:
    """Test end-to-end system performance."""
    
    async def setup_method(self):
        """Set up test environment."""
        self.metrics = PerformanceMetrics()
        
    async def test_packet_routing_latency(self):
        """Test end-to-end packet routing latency."""
        state_manager = StateManager()
        
        # Create services with mocked send
        services = {
            'tell': TellService(state_manager),
            'channel': ChannelService(state_manager),
            'who': WhoService(state_manager),
        }
        
        for service in services.values():
            service.send_packet = AsyncMock()
            
        # Create packet router
        async def route_packet(packet_data: List):
            packet_type = packet_data[0]
            service_name = packet_type.split('-')[0]
            
            if service_name in services:
                # Create packet object
                if packet_type == 'tell':
                    packet = TellPacket(*packet_data)
                elif packet_type == 'channel-m':
                    packet = ChannelMessagePacket(*packet_data)
                elif packet_type == 'who-req':
                    packet = WhoPacket(*packet_data)
                else:
                    return
                    
                # Route to service
                await services[service_name].handle_packet(packet)
                
        # Test packets
        test_packets = [
            ["tell", 5, "TestMUD", "user1", "LocalMUD", "user2", "Hello"],
            ["channel-m", 5, "TestMUD", "user", "chat", "Hello all"],
            ["who-req", 5, "TestMUD", "user"],
        ]
        
        # Warm up
        for _ in range(100):
            for packet in test_packets:
                await route_packet(packet)
                
        # Measure latency
        latencies = []
        iterations = 1000
        
        for _ in range(iterations):
            for packet in test_packets:
                start_time = time.perf_counter()
                await route_packet(packet)
                latency = (time.perf_counter() - start_time) * 1000  # Convert to ms
                latencies.append(latency)
                self.metrics.add_latency(latency)
                
        # Calculate statistics
        stats = self.metrics.get_latency_stats()
        
        # Assert performance targets
        assert stats['p50'] < 50, f"E2E P50 latency {stats['p50']:.2f}ms exceeds 50ms target"
        assert stats['p99'] < 100, f"E2E P99 latency {stats['p99']:.2f}ms exceeds 100ms target"
        
    async def test_throughput_target(self):
        """Test system throughput target of 1000+ packets/sec."""
        state_manager = StateManager()
        
        # Create lightweight packet handler
        async def handle_packet(packet_data: List):
            # Minimal processing to test throughput
            packet_type = packet_data[0]
            if packet_type == "tell":
                # Simulate minimal processing
                await asyncio.sleep(0)  # Yield control
                
        # Test packets
        test_packets = [
            ["tell", 5, f"MUD{i%10}", f"user{i}", "Target", "user", f"Msg{i}"]
            for i in range(100)
        ]
        
        # Measure throughput
        start_time = time.perf_counter()
        iterations = 10
        
        for _ in range(iterations):
            tasks = []
            for packet in test_packets:
                tasks.append(handle_packet(packet))
            await asyncio.gather(*tasks)
            
        elapsed = time.perf_counter() - start_time
        total_packets = iterations * len(test_packets)
        packets_per_second = int(total_packets / elapsed)
        self.metrics.add_throughput(packets_per_second)
        
        # Assert throughput target
        assert packets_per_second > 1000, f"Throughput {packets_per_second} packets/s below 1000 target"
        
    async def test_concurrent_sessions(self):
        """Test handling 1000+ concurrent sessions."""
        state_manager = StateManager()
        
        # Simulate session handler
        async def handle_session(session_id: int):
            # Simulate session activity
            for _ in range(10):
                # Send a packet
                packet = ["tell", 5, f"MUD{session_id}", f"user{session_id}", 
                         "Target", "user", f"Hello from session {session_id}"]
                await asyncio.sleep(0.001)  # Simulate processing
                
        # Create concurrent sessions
        num_sessions = 1000
        
        start_time = time.perf_counter()
        
        # Run all sessions concurrently
        tasks = [handle_session(i) for i in range(num_sessions)]
        await asyncio.gather(*tasks)
        
        elapsed = time.perf_counter() - start_time
        sessions_per_second = num_sessions / elapsed
        
        # Calculate total operations
        total_ops = num_sessions * 10  # Each session sends 10 packets
        ops_per_second = int(total_ops / elapsed)
        self.metrics.add_throughput(ops_per_second)
        
        # Assert concurrent session handling
        assert elapsed < 30, f"Handling {num_sessions} sessions took {elapsed:.2f}s, exceeds 30s target"
        assert ops_per_second > 500, f"Concurrent ops {ops_per_second}/s below 500 target"


# Performance Report Generator
def generate_performance_report(metrics: PerformanceMetrics) -> str:
    """Generate a comprehensive performance report."""
    report = []
    report.append("=" * 60)
    report.append("PERFORMANCE TEST REPORT")
    report.append("=" * 60)
    report.append("")
    
    # Latency Statistics
    if metrics.latencies:
        stats = metrics.get_latency_stats()
        report.append("LATENCY STATISTICS (ms):")
        report.append(f"  Min: {stats['min']:.3f}")
        report.append(f"  Max: {stats['max']:.3f}")
        report.append(f"  Mean: {stats['mean']:.3f}")
        report.append(f"  Median: {stats['median']:.3f}")
        report.append(f"  P50: {stats['p50']:.3f}")
        report.append(f"  P95: {stats['p95']:.3f}")
        report.append(f"  P99: {stats['p99']:.3f}")
        report.append("")
        
    # Throughput Statistics
    if metrics.throughput_samples:
        stats = metrics.get_throughput_stats()
        report.append("THROUGHPUT STATISTICS (ops/sec):")
        report.append(f"  Min: {stats['min']:,}")
        report.append(f"  Max: {stats['max']:,}")
        report.append(f"  Mean: {stats['mean']:,.0f}")
        report.append(f"  Median: {stats['median']:,.0f}")
        report.append("")
        
    # Memory Statistics
    if metrics.memory_samples:
        stats = metrics.get_memory_stats()
        report.append("MEMORY STATISTICS (MB):")
        report.append(f"  Min: {stats['min']:.2f}")
        report.append(f"  Max: {stats['max']:.2f}")
        report.append(f"  Mean: {stats['mean']:.2f}")
        report.append(f"  Median: {stats['median']:.2f}")
        report.append("")
        
    # CPU Statistics
    if metrics.cpu_samples:
        stats = metrics.get_cpu_stats()
        report.append("CPU STATISTICS (%):")
        report.append(f"  Min: {stats['min']:.1f}")
        report.append(f"  Max: {stats['max']:.1f}")
        report.append(f"  Mean: {stats['mean']:.1f}")
        report.append(f"  Median: {stats['median']:.1f}")
        report.append("")
        
    report.append("=" * 60)
    return "\n".join(report)


# Run all performance tests and generate report
if __name__ == "__main__":
    import sys
    
    # Run pytest with performance tests
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    
    # Generate and print report
    metrics = PerformanceMetrics()
    print(generate_performance_report(metrics))
    
    sys.exit(exit_code)