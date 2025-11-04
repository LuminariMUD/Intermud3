"""Health check endpoints for monitoring gateway status.

Provides comprehensive health monitoring including:
- Basic liveness checks
- Readiness checks
- Detailed component health
- Performance metrics
- Dependency checks
"""

import asyncio
import logging
import platform
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import psutil

from src.network.connection_pool import get_pool_manager
from src.state.manager import StateManager
from src.utils.circuit_breaker import get_circuit_breaker_manager
from src.utils.retry import get_retry_manager


logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"  # Everything working normally
    DEGRADED = "degraded"  # Working but with issues
    UNHEALTHY = "unhealthy"  # Not working properly
    UNKNOWN = "unknown"  # Status cannot be determined


@dataclass
class ComponentHealth:
    """Health status of a component."""

    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float | None = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }


@dataclass
class SystemMetrics:
    """System resource metrics."""

    cpu_percent: float
    memory_percent: float
    memory_mb: float
    disk_percent: float
    network_connections: int
    open_files: int
    threads: int
    uptime_seconds: float

    @classmethod
    def collect(cls) -> "SystemMetrics":
        """Collect current system metrics."""
        process = psutil.Process()

        # Get CPU usage
        cpu_percent = process.cpu_percent(interval=0.1)

        # Get memory info
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        memory_percent = process.memory_percent()

        # Get disk usage
        disk_usage = psutil.disk_usage("/")
        disk_percent = disk_usage.percent

        # Get connection count
        try:
            connections = len(process.connections())
        except:
            connections = 0

        # Get open files
        try:
            open_files = len(process.open_files())
        except:
            open_files = 0

        # Get thread count
        threads = process.num_threads()

        # Calculate uptime
        create_time = process.create_time()
        uptime_seconds = time.time() - create_time

        return cls(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_mb=memory_mb,
            disk_percent=disk_percent,
            network_connections=connections,
            open_files=open_files,
            threads=threads,
            uptime_seconds=uptime_seconds,
        )


class HealthChecker:
    """Main health checker for the gateway."""

    def __init__(self, state_manager: StateManager | None = None):
        """Initialize health checker."""
        self.state_manager = state_manager
        self.start_time = time.time()
        self._checks: dict[str, callable] = {}
        self._thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 90.0,
            "disk_percent": 95.0,
            "response_time_ms": 1000.0,
            "error_rate": 0.01,
        }

    def register_check(self, name: str, check_func: callable):
        """Register a custom health check."""
        self._checks[name] = check_func

    async def check_liveness(self) -> tuple[HealthStatus, dict[str, Any]]:
        """Basic liveness check - is the service running?

        Returns:
            Tuple of (status, details)
        """
        try:
            # Basic check - can we allocate memory and run code?
            test_data = list(range(100))
            result = sum(test_data)

            return HealthStatus.HEALTHY, {
                "status": "alive",
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": time.time() - self.start_time,
            }

        except Exception as e:
            logger.error(f"Liveness check failed: {e}")
            return HealthStatus.UNHEALTHY, {"status": "dead", "error": str(e)}

    async def check_readiness(self) -> tuple[HealthStatus, dict[str, Any]]:
        """Readiness check - is the service ready to handle requests?

        Returns:
            Tuple of (status, details)
        """
        checks = []
        overall_status = HealthStatus.HEALTHY

        # Check state manager
        if self.state_manager:
            state_health = await self._check_state_manager()
            checks.append(state_health)
            if state_health.status != HealthStatus.HEALTHY:
                overall_status = HealthStatus.DEGRADED

        # Check circuit breakers
        breaker_health = await self._check_circuit_breakers()
        checks.append(breaker_health)
        if breaker_health.status == HealthStatus.UNHEALTHY:
            overall_status = HealthStatus.UNHEALTHY
        elif breaker_health.status == HealthStatus.DEGRADED:
            overall_status = HealthStatus.DEGRADED

        # Check connection pools
        pool_health = await self._check_connection_pools()
        checks.append(pool_health)
        if pool_health.status != HealthStatus.HEALTHY:
            overall_status = HealthStatus.DEGRADED

        # Check system resources
        resource_health = await self._check_system_resources()
        checks.append(resource_health)
        if resource_health.status == HealthStatus.UNHEALTHY:
            overall_status = HealthStatus.UNHEALTHY
        elif resource_health.status == HealthStatus.DEGRADED:
            overall_status = HealthStatus.DEGRADED

        return overall_status, {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": [check.to_dict() for check in checks],
        }

    async def check_detailed(self) -> dict[str, Any]:
        """Detailed health check with all component statuses.

        Returns:
            Comprehensive health report
        """
        # Collect all health information
        liveness_status, liveness_details = await self.check_liveness()
        readiness_status, readiness_details = await self.check_readiness()

        # Collect metrics
        metrics = SystemMetrics.collect()

        # Get component statuses
        components = {
            "circuit_breakers": get_circuit_breaker_manager().get_status(),
            "retry_handlers": get_retry_manager().get_stats(),
            "connection_pools": get_pool_manager().get_status(),
        }

        # Run custom checks
        custom_checks = {}
        for name, check_func in self._checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    custom_checks[name] = await check_func()
                else:
                    custom_checks[name] = check_func()
            except Exception as e:
                custom_checks[name] = {"status": "error", "error": str(e)}

        # Build comprehensive report
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service": "i3-gateway",
            "version": "1.0.0",  # TODO: Get from config
            "environment": platform.node(),
            "liveness": {"status": liveness_status.value, "details": liveness_details},
            "readiness": {"status": readiness_status.value, "details": readiness_details},
            "metrics": asdict(metrics),
            "components": components,
            "custom_checks": custom_checks,
            "thresholds": self._thresholds,
        }

    async def _check_state_manager(self) -> ComponentHealth:
        """Check state manager health."""
        try:
            start = time.perf_counter()

            # Check if we can access state
            mud_count = len(self.state_manager.mud_list)
            channel_count = len(self.state_manager.channel_list)

            latency = (time.perf_counter() - start) * 1000

            return ComponentHealth(
                name="state_manager",
                status=HealthStatus.HEALTHY,
                message=f"Managing {mud_count} MUDs, {channel_count} channels",
                latency_ms=latency,
                metadata={"mud_count": mud_count, "channel_count": channel_count},
            )

        except Exception as e:
            return ComponentHealth(
                name="state_manager",
                status=HealthStatus.UNHEALTHY,
                message=f"State manager error: {e}",
            )

    async def _check_circuit_breakers(self) -> ComponentHealth:
        """Check circuit breaker health."""
        try:
            manager = get_circuit_breaker_manager()
            all_healthy, status = await manager.check_health()

            if all_healthy:
                return ComponentHealth(
                    name="circuit_breakers",
                    status=HealthStatus.HEALTHY,
                    message="All circuits closed",
                    metadata=status,
                )
            open_circuits = [name for name, info in status.items() if info["state"] == "open"]

            if len(open_circuits) > len(status) / 2:
                health_status = HealthStatus.UNHEALTHY
            else:
                health_status = HealthStatus.DEGRADED

            return ComponentHealth(
                name="circuit_breakers",
                status=health_status,
                message=f"Open circuits: {', '.join(open_circuits)}",
                metadata=status,
            )

        except Exception as e:
            return ComponentHealth(
                name="circuit_breakers", status=HealthStatus.UNKNOWN, message=f"Check failed: {e}"
            )

    async def _check_connection_pools(self) -> ComponentHealth:
        """Check connection pool health."""
        try:
            manager = get_pool_manager()
            pool_status = manager.get_status()

            if not pool_status:
                return ComponentHealth(
                    name="connection_pools",
                    status=HealthStatus.HEALTHY,
                    message="No pools configured",
                )

            # Check utilization
            total_utilization = 0
            pool_count = 0

            for name, status in pool_status.items():
                if "utilization" in status:
                    total_utilization += status["utilization"]
                    pool_count += 1

            if pool_count > 0:
                avg_utilization = total_utilization / pool_count

                if avg_utilization > 0.9:
                    health_status = HealthStatus.UNHEALTHY
                    message = f"High pool utilization: {avg_utilization:.1%}"
                elif avg_utilization > 0.7:
                    health_status = HealthStatus.DEGRADED
                    message = f"Moderate pool utilization: {avg_utilization:.1%}"
                else:
                    health_status = HealthStatus.HEALTHY
                    message = f"Normal pool utilization: {avg_utilization:.1%}"

                return ComponentHealth(
                    name="connection_pools",
                    status=health_status,
                    message=message,
                    metadata=pool_status,
                )
            return ComponentHealth(
                name="connection_pools",
                status=HealthStatus.HEALTHY,
                message="Pools healthy",
                metadata=pool_status,
            )

        except Exception as e:
            return ComponentHealth(
                name="connection_pools", status=HealthStatus.UNKNOWN, message=f"Check failed: {e}"
            )

    async def _check_system_resources(self) -> ComponentHealth:
        """Check system resource usage."""
        try:
            metrics = SystemMetrics.collect()

            issues = []

            # Check CPU
            if metrics.cpu_percent > self._thresholds["cpu_percent"]:
                issues.append(f"High CPU: {metrics.cpu_percent:.1f}%")

            # Check memory
            if metrics.memory_percent > self._thresholds["memory_percent"]:
                issues.append(f"High memory: {metrics.memory_percent:.1f}%")

            # Check disk
            if metrics.disk_percent > self._thresholds["disk_percent"]:
                issues.append(f"High disk: {metrics.disk_percent:.1f}%")

            if not issues:
                health_status = HealthStatus.HEALTHY
                message = "Resources normal"
            elif len(issues) == 1:
                health_status = HealthStatus.DEGRADED
                message = issues[0]
            else:
                health_status = HealthStatus.UNHEALTHY
                message = "; ".join(issues)

            return ComponentHealth(
                name="system_resources",
                status=health_status,
                message=message,
                metadata=asdict(metrics),
            )

        except Exception as e:
            return ComponentHealth(
                name="system_resources", status=HealthStatus.UNKNOWN, message=f"Check failed: {e}"
            )


class HealthEndpoints:
    """HTTP endpoints for health checks."""

    def __init__(self, health_checker: HealthChecker):
        """Initialize health endpoints."""
        self.health_checker = health_checker

    async def handle_liveness(self) -> tuple[int, dict[str, Any]]:
        """Handle liveness probe request.

        Returns:
            Tuple of (status_code, response_body)
        """
        status, details = await self.health_checker.check_liveness()

        if status == HealthStatus.HEALTHY:
            return 200, details
        return 503, details

    async def handle_readiness(self) -> tuple[int, dict[str, Any]]:
        """Handle readiness probe request.

        Returns:
            Tuple of (status_code, response_body)
        """
        status, details = await self.health_checker.check_readiness()

        if status == HealthStatus.HEALTHY:
            return 200, details
        if status == HealthStatus.DEGRADED:
            return 200, details  # Still ready but degraded
        return 503, details

    async def handle_health(self) -> tuple[int, dict[str, Any]]:
        """Handle detailed health check request.

        Returns:
            Tuple of (status_code, response_body)
        """
        details = await self.health_checker.check_detailed()

        # Determine overall status code
        readiness_status = details["readiness"]["status"]
        if readiness_status == "healthy" or readiness_status == "degraded":
            return 200, details
        return 503, details

    async def handle_metrics(self) -> tuple[int, str]:
        """Handle metrics request (Prometheus format).

        Returns:
            Tuple of (status_code, metrics_text)
        """
        metrics = SystemMetrics.collect()

        # Format as Prometheus metrics
        lines = []
        lines.append("# HELP i3_gateway_cpu_percent CPU usage percentage")
        lines.append("# TYPE i3_gateway_cpu_percent gauge")
        lines.append(f"i3_gateway_cpu_percent {metrics.cpu_percent}")

        lines.append("# HELP i3_gateway_memory_mb Memory usage in MB")
        lines.append("# TYPE i3_gateway_memory_mb gauge")
        lines.append(f"i3_gateway_memory_mb {metrics.memory_mb}")

        lines.append("# HELP i3_gateway_memory_percent Memory usage percentage")
        lines.append("# TYPE i3_gateway_memory_percent gauge")
        lines.append(f"i3_gateway_memory_percent {metrics.memory_percent}")

        lines.append("# HELP i3_gateway_connections Active network connections")
        lines.append("# TYPE i3_gateway_connections gauge")
        lines.append(f"i3_gateway_connections {metrics.network_connections}")

        lines.append("# HELP i3_gateway_threads Active threads")
        lines.append("# TYPE i3_gateway_threads gauge")
        lines.append(f"i3_gateway_threads {metrics.threads}")

        lines.append("# HELP i3_gateway_uptime_seconds Service uptime in seconds")
        lines.append("# TYPE i3_gateway_uptime_seconds counter")
        lines.append(f"i3_gateway_uptime_seconds {metrics.uptime_seconds}")

        # Add circuit breaker metrics
        breaker_manager = get_circuit_breaker_manager()
        breaker_status = breaker_manager.get_status()

        for name, status in breaker_status.items():
            safe_name = name.replace(".", "_").replace("-", "_")

            lines.append(
                f"# HELP i3_gateway_circuit_{safe_name}_state Circuit breaker state (0=closed, 1=open, 2=half_open)"
            )
            lines.append(f"# TYPE i3_gateway_circuit_{safe_name}_state gauge")
            state_value = {"closed": 0, "open": 1, "half_open": 2}.get(status["state"], -1)
            lines.append(f"i3_gateway_circuit_{safe_name}_state {state_value}")

            lines.append(
                f"# HELP i3_gateway_circuit_{safe_name}_error_rate Circuit breaker error rate"
            )
            lines.append(f"# TYPE i3_gateway_circuit_{safe_name}_error_rate gauge")
            lines.append(f"i3_gateway_circuit_{safe_name}_error_rate {status['error_rate']}")

        return 200, "\n".join(lines)


# Create global health checker
_health_checker: HealthChecker | None = None


def get_health_checker(state_manager: StateManager | None = None) -> HealthChecker:
    """Get or create the global health checker."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker(state_manager)
    return _health_checker


def get_health_endpoints() -> HealthEndpoints:
    """Get health endpoints."""
    return HealthEndpoints(get_health_checker())
