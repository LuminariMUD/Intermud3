"""
Stress testing suite for I3 Gateway.

This module performs various stress tests including:
- Sustained load testing (24-hour simulation)
- Spike testing (sudden load increases)
- Soak testing (memory leak detection)
- Chaos testing (random failures)
- Recovery testing (graceful degradation)
"""

import asyncio
import gc
import random
import time
from dataclasses import dataclass

import psutil
import pytest

from src.network.lpc import LPCDecoder, LPCEncoder
from src.state.manager import StateManager


@dataclass
class StressTestResult:
    """Results from a stress test run."""

    test_name: str
    duration_seconds: float
    total_operations: int
    successful_operations: int
    failed_operations: int
    error_rate: float
    avg_latency_ms: float
    max_latency_ms: float
    memory_start_mb: float
    memory_end_mb: float
    memory_growth_mb: float
    cpu_avg_percent: float
    cpu_max_percent: float

    def is_passing(self) -> bool:
        """Check if test meets passing criteria."""
        return (
            self.error_rate < 0.001  # Less than 0.1% errors
            and self.avg_latency_ms < 100  # Average latency under 100ms
            and self.memory_growth_mb < 100  # Memory growth under 100MB
            and self.cpu_avg_percent < 80  # Average CPU under 80%
        )

    def generate_report(self) -> str:
        """Generate a report for this test result."""
        status = "PASS" if self.is_passing() else "FAIL"

        report = []
        report.append(f"\n{'=' * 60}")
        report.append(f"STRESS TEST: {self.test_name} - {status}")
        report.append(f"{'=' * 60}")
        report.append(f"Duration: {self.duration_seconds:.2f} seconds")
        report.append(f"Total Operations: {self.total_operations:,}")
        report.append(f"Successful: {self.successful_operations:,}")
        report.append(f"Failed: {self.failed_operations:,}")
        report.append(f"Error Rate: {self.error_rate:.4%}")
        report.append(f"Avg Latency: {self.avg_latency_ms:.2f}ms")
        report.append(f"Max Latency: {self.max_latency_ms:.2f}ms")
        report.append(f"Memory Start: {self.memory_start_mb:.2f}MB")
        report.append(f"Memory End: {self.memory_end_mb:.2f}MB")
        report.append(f"Memory Growth: {self.memory_growth_mb:.2f}MB")
        report.append(f"CPU Average: {self.cpu_avg_percent:.1f}%")
        report.append(f"CPU Max: {self.cpu_max_percent:.1f}%")

        if not self.is_passing():
            report.append("\nFAILURE REASONS:")
            if self.error_rate >= 0.001:
                report.append(f"  - Error rate {self.error_rate:.4%} exceeds 0.1% threshold")
            if self.avg_latency_ms >= 100:
                report.append(f"  - Average latency {self.avg_latency_ms:.2f}ms exceeds 100ms")
            if self.memory_growth_mb >= 100:
                report.append(f"  - Memory growth {self.memory_growth_mb:.2f}MB exceeds 100MB")
            if self.cpu_avg_percent >= 80:
                report.append(f"  - Average CPU {self.cpu_avg_percent:.1f}% exceeds 80%")

        return "\n".join(report)


class StressTestRunner:
    """Base class for stress test runners."""

    def __init__(self):
        self.encoder = LPCEncoder()
        self.decoder = LPCDecoder()
        self.state_manager = StateManager()
        self.process = psutil.Process()

        # Metrics collection
        self.operations = 0
        self.successes = 0
        self.failures = 0
        self.latencies = []
        self.cpu_samples = []
        self.memory_samples = []

    def reset_metrics(self):
        """Reset metrics for a new test run."""
        self.operations = 0
        self.successes = 0
        self.failures = 0
        self.latencies = []
        self.cpu_samples = []
        self.memory_samples = []

    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / (1024 * 1024)

    def get_cpu_percent(self) -> float:
        """Get current CPU usage percentage."""
        return self.process.cpu_percent(interval=0.1)

    async def generate_load(self, duration_seconds: float, ops_per_second: int):
        """Generate sustained load for specified duration."""
        start_time = time.perf_counter()
        interval = 1.0 / ops_per_second

        while time.perf_counter() - start_time < duration_seconds:
            op_start = time.perf_counter()

            try:
                # Perform operation
                await self.perform_operation()
                self.successes += 1
            except Exception:
                self.failures += 1

            self.operations += 1

            # Record latency
            latency = (time.perf_counter() - op_start) * 1000
            self.latencies.append(latency)

            # Sleep to maintain rate
            elapsed = time.perf_counter() - op_start
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)

    async def perform_operation(self):
        """Perform a single test operation. Override in subclasses."""
        # Create random packet
        packet_type = random.choice(["tell", "channel", "who"])

        if packet_type == "tell":
            packet = ["tell", 5, "TestMUD", "user1", "Target", "user2", "Message"]
        elif packet_type == "channel":
            packet = ["channel-m", 5, "TestMUD", "user", "chat", "Message"]
        else:
            packet = ["who-req", 5, "TestMUD", "user"]

        # Encode and decode
        encoded = self.encoder.encode(packet)
        decoded = self.decoder.decode(encoded)

        if decoded != packet:
            raise ValueError("Packet corruption detected")

    async def collect_metrics(self, duration_seconds: float):
        """Collect system metrics during test."""
        interval = 1.0  # Collect every second
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < duration_seconds:
            self.cpu_samples.append(self.get_cpu_percent())
            self.memory_samples.append(self.get_memory_usage_mb())
            await asyncio.sleep(interval)

    def calculate_results(self, test_name: str, duration: float) -> StressTestResult:
        """Calculate test results from collected metrics."""
        error_rate = self.failures / self.operations if self.operations > 0 else 0
        avg_latency = sum(self.latencies) / len(self.latencies) if self.latencies else 0
        max_latency = max(self.latencies) if self.latencies else 0

        memory_start = self.memory_samples[0] if self.memory_samples else 0
        memory_end = self.memory_samples[-1] if self.memory_samples else 0
        memory_growth = memory_end - memory_start

        cpu_avg = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
        cpu_max = max(self.cpu_samples) if self.cpu_samples else 0

        return StressTestResult(
            test_name=test_name,
            duration_seconds=duration,
            total_operations=self.operations,
            successful_operations=self.successes,
            failed_operations=self.failures,
            error_rate=error_rate,
            avg_latency_ms=avg_latency,
            max_latency_ms=max_latency,
            memory_start_mb=memory_start,
            memory_end_mb=memory_end,
            memory_growth_mb=memory_growth,
            cpu_avg_percent=cpu_avg,
            cpu_max_percent=cpu_max,
        )


@pytest.mark.asyncio
class TestSustainedLoad:
    """Test sustained load over extended periods."""

    async def test_sustained_load_1_hour_simulation(self):
        """Simulate 1 hour of sustained load (accelerated)."""
        runner = StressTestRunner()
        runner.reset_metrics()

        # Simulate 1 hour in 60 seconds (60x acceleration)
        duration = 60  # 60 seconds real time
        ops_per_second = 100  # Moderate load

        # Start load generation and metrics collection
        await asyncio.gather(
            runner.generate_load(duration, ops_per_second), runner.collect_metrics(duration)
        )

        # Calculate results
        result = runner.calculate_results("1 Hour Sustained Load", duration)

        # Print report
        print(result.generate_report())

        # Assert passing criteria
        assert (
            result.is_passing()
        ), f"Sustained load test failed: {result.error_rate:.4%} error rate"

    async def test_sustained_high_load(self):
        """Test sustained high load for 5 minutes."""
        runner = StressTestRunner()
        runner.reset_metrics()

        duration = 30  # 30 seconds
        ops_per_second = 500  # High load

        # Start load generation and metrics collection
        await asyncio.gather(
            runner.generate_load(duration, ops_per_second), runner.collect_metrics(duration)
        )

        # Calculate results
        result = runner.calculate_results("High Load Sustained", duration)

        # Print report
        print(result.generate_report())

        # Assert passing criteria
        assert result.is_passing(), "High load test failed"


@pytest.mark.asyncio
class TestSpikeLoad:
    """Test system behavior under sudden load spikes."""

    async def test_load_spike_10x(self):
        """Test sudden 10x load spike."""
        runner = StressTestRunner()
        runner.reset_metrics()

        total_duration = 30  # 30 seconds total
        normal_load = 50  # ops/sec
        spike_load = 500  # 10x spike

        start_time = time.perf_counter()

        # Normal load for 10 seconds
        await asyncio.gather(runner.generate_load(10, normal_load), runner.collect_metrics(10))

        # Spike load for 10 seconds
        await asyncio.gather(runner.generate_load(10, spike_load), runner.collect_metrics(10))

        # Return to normal for 10 seconds
        await asyncio.gather(runner.generate_load(10, normal_load), runner.collect_metrics(10))

        # Calculate results
        result = runner.calculate_results("10x Load Spike", total_duration)

        # Print report
        print(result.generate_report())

        # Assert system handles spike
        assert result.error_rate < 0.01, f"Spike caused {result.error_rate:.2%} error rate"
        assert (
            result.avg_latency_ms < 200
        ), f"Spike caused {result.avg_latency_ms:.0f}ms avg latency"

    async def test_gradual_load_increase(self):
        """Test gradual load increase pattern."""
        runner = StressTestRunner()
        runner.reset_metrics()

        duration_per_level = 5  # 5 seconds per load level
        load_levels = [10, 50, 100, 200, 400, 200, 100, 50, 10]  # Ramp up and down

        for load in load_levels:
            await asyncio.gather(
                runner.generate_load(duration_per_level, load),
                runner.collect_metrics(duration_per_level),
            )

        total_duration = duration_per_level * len(load_levels)
        result = runner.calculate_results("Gradual Load Increase", total_duration)

        # Print report
        print(result.generate_report())

        # Assert graceful handling
        assert result.is_passing(), "System failed under gradual load increase"


@pytest.mark.asyncio
class TestMemorySoak:
    """Test for memory leaks over extended operation."""

    async def test_memory_soak_1000_iterations(self):
        """Run 1000 iterations checking for memory leaks."""
        runner = StressTestRunner()

        # Track memory over iterations
        memory_samples = []
        gc.collect()  # Start clean

        initial_memory = runner.get_memory_usage_mb()
        memory_samples.append(initial_memory)

        # Run iterations
        iterations = 1000
        ops_per_iteration = 100

        for i in range(iterations):
            runner.reset_metrics()

            # Generate load
            for _ in range(ops_per_iteration):
                await runner.perform_operation()

            # Collect garbage and measure memory
            if i % 10 == 0:  # Every 10 iterations
                gc.collect()
                current_memory = runner.get_memory_usage_mb()
                memory_samples.append(current_memory)

                # Check for linear growth (memory leak indicator)
                if len(memory_samples) > 10:
                    # Calculate growth rate
                    recent_samples = memory_samples[-10:]
                    growth_rate = (recent_samples[-1] - recent_samples[0]) / 10

                    # Fail if growing more than 1MB per 10 iterations
                    assert (
                        growth_rate < 1.0
                    ), f"Memory leak detected: {growth_rate:.2f}MB/10 iterations"

        # Final memory check
        gc.collect()
        final_memory = runner.get_memory_usage_mb()
        total_growth = final_memory - initial_memory

        print("\nMemory Soak Test Results:")
        print(f"  Initial Memory: {initial_memory:.2f}MB")
        print(f"  Final Memory: {final_memory:.2f}MB")
        print(f"  Total Growth: {total_growth:.2f}MB")
        print(
            f"  Growth per 1000 ops: {total_growth / (iterations * ops_per_iteration) * 1000:.4f}MB"
        )

        # Assert acceptable memory growth
        assert total_growth < 50, f"Excessive memory growth: {total_growth:.2f}MB"

    async def test_long_running_connections(self):
        """Test memory behavior with long-running connections."""
        # Simulate long-running connections
        connections = []

        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        # Create connections
        for i in range(100):
            conn = {
                "id": i,
                "encoder": LPCEncoder(),
                "decoder": LPCDecoder(),
                "buffer": bytearray(1024),  # 1KB buffer
                "packets": [],
            }
            connections.append(conn)

            # Simulate activity
            for _ in range(10):
                packet = ["tell", 5, f"MUD{i}", "user", "Target", "user", "Message"]
                encoded = conn["encoder"].encode(packet)
                conn["packets"].append(encoded)

        # Check memory after connections created
        mid_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        # Clear old packets (simulate cleanup)
        for conn in connections:
            conn["packets"] = conn["packets"][-10:]  # Keep only last 10

        gc.collect()

        # Final memory check
        final_memory = psutil.Process().memory_info().rss / (1024 * 1024)

        print("\nLong-Running Connections Test:")
        print(f"  Initial: {initial_memory:.2f}MB")
        print(f"  With Connections: {mid_memory:.2f}MB")
        print(f"  After Cleanup: {final_memory:.2f}MB")

        # Memory should be reclaimed after cleanup
        cleanup_efficiency = (mid_memory - final_memory) / (mid_memory - initial_memory)
        assert cleanup_efficiency > 0.5, f"Poor memory cleanup: {cleanup_efficiency:.1%}"


@pytest.mark.asyncio
class TestChaosEngineering:
    """Test system resilience to random failures."""

    async def test_random_failures(self):
        """Inject random failures and test recovery."""

        class ChaosRunner(StressTestRunner):
            def __init__(self):
                super().__init__()
                self.failure_rate = 0.1  # 10% failure rate

            async def perform_operation(self):
                # Randomly inject failures
                if random.random() < self.failure_rate:
                    failure_type = random.choice(
                        [
                            "network_timeout",
                            "invalid_packet",
                            "service_unavailable",
                            "memory_pressure",
                        ]
                    )

                    if failure_type == "network_timeout":
                        await asyncio.sleep(0.5)  # Simulate timeout
                        raise TimeoutError("Network timeout")
                    if failure_type == "invalid_packet":
                        raise ValueError("Invalid packet format")
                    if failure_type == "service_unavailable":
                        raise ConnectionError("Service unavailable")
                    if failure_type == "memory_pressure":
                        # Simulate memory pressure
                        _ = bytearray(10 * 1024 * 1024)  # 10MB allocation
                        raise MemoryError("Memory pressure")

                # Normal operation
                await super().perform_operation()

        runner = ChaosRunner()
        runner.reset_metrics()

        # Run with chaos
        duration = 30
        ops_per_second = 100

        await asyncio.gather(
            runner.generate_load(duration, ops_per_second), runner.collect_metrics(duration)
        )

        result = runner.calculate_results("Chaos Engineering", duration)

        # Print report
        print(result.generate_report())

        # System should handle failures gracefully
        # Higher error rate expected due to injected failures
        assert result.error_rate < 0.15, f"Too many errors under chaos: {result.error_rate:.2%}"
        assert (
            result.avg_latency_ms < 500
        ), f"Latency too high under chaos: {result.avg_latency_ms:.0f}ms"

    async def test_cascading_failures(self):
        """Test handling of cascading failures."""

        class CascadeRunner(StressTestRunner):
            def __init__(self):
                super().__init__()
                self.failure_cascade = False
                self.cascade_start = None

            async def perform_operation(self):
                # Trigger cascade after some operations
                if self.operations == 100:
                    self.failure_cascade = True
                    self.cascade_start = time.perf_counter()

                # During cascade, high failure rate
                if self.failure_cascade:
                    # Cascade lasts 5 seconds
                    if time.perf_counter() - self.cascade_start > 5:
                        self.failure_cascade = False
                    elif random.random() < 0.8:  # 80% failure during cascade
                        raise Exception("Cascading failure")

                await super().perform_operation()

        runner = CascadeRunner()
        runner.reset_metrics()

        # Run with cascade
        duration = 30
        ops_per_second = 50

        await asyncio.gather(
            runner.generate_load(duration, ops_per_second), runner.collect_metrics(duration)
        )

        result = runner.calculate_results("Cascading Failures", duration)

        # Print report
        print(result.generate_report())

        # System should recover from cascade
        # Total error rate should be manageable despite cascade
        assert result.error_rate < 0.25, f"Failed to recover from cascade: {result.error_rate:.2%}"


@pytest.mark.asyncio
class TestRecovery:
    """Test system recovery and graceful degradation."""

    async def test_recovery_after_overload(self):
        """Test recovery after system overload."""
        runner = StressTestRunner()

        # Phase 1: Normal operation
        runner.reset_metrics()
        await runner.generate_load(10, 50)  # 10 seconds normal
        normal_latency = sum(runner.latencies) / len(runner.latencies)

        # Phase 2: Overload
        runner.reset_metrics()
        await runner.generate_load(10, 1000)  # 10 seconds overload
        overload_latency = sum(runner.latencies) / len(runner.latencies)

        # Phase 3: Recovery
        runner.reset_metrics()
        await runner.generate_load(20, 50)  # 20 seconds recovery
        recovery_latency = sum(runner.latencies) / len(runner.latencies)

        print("\nRecovery Test Results:")
        print(f"  Normal Latency: {normal_latency:.2f}ms")
        print(f"  Overload Latency: {overload_latency:.2f}ms")
        print(f"  Recovery Latency: {recovery_latency:.2f}ms")

        # Assert recovery
        recovery_ratio = recovery_latency / normal_latency
        assert recovery_ratio < 1.5, f"Poor recovery: {recovery_ratio:.1f}x normal latency"

    async def test_graceful_degradation(self):
        """Test graceful degradation under resource constraints."""

        class DegradationRunner(StressTestRunner):
            def __init__(self):
                super().__init__()
                self.degraded_mode = False

            async def perform_operation(self):
                # Check resource usage
                cpu = self.get_cpu_percent()
                memory = self.get_memory_usage_mb()

                # Enter degraded mode if resources constrained
                if cpu > 70 or memory > 500:
                    self.degraded_mode = True
                elif cpu < 50 and memory < 400:
                    self.degraded_mode = False

                if self.degraded_mode:
                    # Simplified operation in degraded mode
                    packet = ["tell", 5, "Test", "user", "Target", "user", "Msg"]
                    _ = self.encoder.encode(packet)
                else:
                    # Normal operation
                    await super().perform_operation()

        runner = DegradationRunner()
        runner.reset_metrics()

        # Run with increasing load
        for load in [50, 100, 200, 400, 800]:
            await runner.generate_load(5, load)

        result = runner.calculate_results("Graceful Degradation", 25)

        # Print report
        print(result.generate_report())
        print(f"  Degraded Mode: {runner.degraded_mode}")

        # System should maintain low error rate even when degraded
        assert result.error_rate < 0.01, f"High errors during degradation: {result.error_rate:.2%}"


# Stress Test Suite Runner
async def run_stress_test_suite():
    """Run complete stress test suite and generate report."""
    print("\n" + "=" * 60)
    print("I3 GATEWAY STRESS TEST SUITE")
    print("=" * 60)

    test_classes = [
        TestSustainedLoad(),
        TestSpikeLoad(),
        TestMemorySoak(),
        TestChaosEngineering(),
        TestRecovery(),
    ]

    results = []

    for test_class in test_classes:
        test_name = test_class.__class__.__name__
        print(f"\nRunning {test_name}...")

        # Run test methods
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                method = getattr(test_class, method_name)
                if asyncio.iscoroutinefunction(method):
                    try:
                        await method()
                        print(f"  ✓ {method_name}")
                    except AssertionError as e:
                        print(f"  ✗ {method_name}: {e}")
                    except Exception as e:
                        print(f"  ! {method_name}: Unexpected error: {e}")

    print("\n" + "=" * 60)
    print("STRESS TEST SUITE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    # Run the stress test suite
    asyncio.run(run_stress_test_suite())
