"""Pytest configuration and fixtures for I3 Gateway tests."""

import asyncio
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import pytest_asyncio

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for Windows compatibility."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.get_event_loop_policy()


@pytest.fixture
def event_loop(event_loop_policy):
    """Create an event loop for async tests."""
    loop = event_loop_policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_i3_connection():
    """Mock I3 network connection."""
    connection = AsyncMock()
    connection.connected = True
    connection.send_packet = AsyncMock(return_value=True)
    connection.receive_packet = AsyncMock()
    connection.close = AsyncMock()
    return connection


@pytest.fixture
def mock_i3_router():
    """Mock I3 router for testing."""
    router = MagicMock()
    router.host = "test.router.i3"
    router.port = 8080
    router.password = 0
    router.mudlist = {}
    return router


@pytest.fixture
def sample_i3_packet():
    """Sample I3 packet for testing."""
    return {
        "type": "tell",
        "ttl": 200,
        "originator_mudname": "TestMUD",
        "originator_username": "testuser",
        "target_mudname": "OtherMUD",
        "target_username": "targetuser",
        "message": "Test message",
    }


@pytest.fixture
def sample_mudmode_packet():
    """Sample MudMode encoded packet for testing."""
    # This would be the actual encoded binary data
    # For now, returning a placeholder
    return b"\x00\x00\x00\x10test_packet_data"


@pytest_asyncio.fixture
async def mock_gateway_config():
    """Mock gateway configuration."""
    return {
        "mud": {
            "name": "TestMUD",
            "port": 4000,
            "admin_email": "admin@testmud.com",
            "mudlib": "TestLib",
            "base_mudlib": "TestBase",
            "driver": "TestDriver",
            "mud_type": "LP",
            "open_status": "open",
            "services": {
                "tell": 1,
                "channel": 1,
                "who": 1,
                "finger": 1,
                "locate": 1,
            }
        },
        "router": {
            "primary": {
                "host": "204.209.44.3",
                "port": 8080,
            },
            "fallback": [
                {"host": "backup.router.i3", "port": 8080},
            ]
        },
        "gateway": {
            "host": "localhost",
            "port": 4001,
            "max_packet_size": 65536,
            "timeout": 30,
            "retry_attempts": 3,
            "retry_delay": 5,
        },
        "logging": {
            "level": "DEBUG",
            "format": "json",
            "file": "logs/i3-gateway.log",
        }
    }


@pytest.fixture
def mock_mud_connection():
    """Mock MUD connection for testing."""
    connection = MagicMock()
    connection.connected = True
    connection.send_message = Mock(return_value=True)
    connection.receive_message = Mock()
    return connection


@pytest_asyncio.fixture
async def mock_service_registry():
    """Mock service registry for testing."""
    registry = AsyncMock()
    registry.register = AsyncMock()
    registry.unregister = AsyncMock()
    registry.get_service = AsyncMock()
    registry.handle_packet = AsyncMock()
    return registry


@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary state directory for testing."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def temp_config_file(tmp_path):
    """Create temporary config file for testing."""
    import yaml
    
    config_file = tmp_path / "config.yaml"
    config_data = {
        "mud": {
            "name": "TestMUD",
            "port": 4000,
        },
        "router": {
            "primary": {
                "host": "test.router.i3",
                "port": 8080,
            }
        }
    }
    
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    return config_file


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset any singleton instances between tests."""
    # Add any singleton reset logic here
    yield
    # Cleanup after test


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    logger = MagicMock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.critical = Mock()
    return logger


# Markers for test organization
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests that don't require external resources"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests that may require external resources"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take a long time to run"
    )
    config.addinivalue_line(
        "markers", "network: Tests that require network access"
    )
    config.addinivalue_line(
        "markers", "asyncio: Asynchronous tests"
    )