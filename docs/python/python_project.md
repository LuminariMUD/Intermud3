# Intermud3 Gateway - Python Project Structure

## Project Overview

The Intermud3 Gateway is a standalone Python service that bridges MUDs to the global Intermud-3 network, handling protocol complexity while exposing comprehensive WebSocket and TCP APIs. The project implements full I3 protocol support with event-driven architecture, session management, and real-time communication capabilities.

## Current Project Structure

```
Intermud3/
├── clients/                    # Client implementations
│   ├── circlemud/              # CircleMUD integration
│   ├── examples/               # Example client implementations
│   ├── javascript/             # JavaScript client library
│   └── python/                 # Python client library
├── config/                     # Gateway configuration
│   └── config.yaml
├── docs/                       # Documentation
│   ├── ai_tools/               # AI development tools docs
│   ├── intermud3_docs/         # I3 protocol documentation
│   ├── previous_changelogs/    # Historical changes
│   ├── projects/               # Project planning docs
│   ├── python/                 # Python project docs
│   ├── API.md
│   ├── API_REFERENCE.md
│   ├── ARCHITECTURE.md
│   ├── CHANGELOG.md
│   ├── DEPLOYMENT.md
│   ├── INTEGRATION_GUIDE.md
│   ├── PERFORMANCE_TUNING.md
│   ├── TODO.md
│   └── TROUBLESHOOTING.md
├── src/                        # Source code
│   ├── __init__.py
│   ├── __main__.py             # Entry point
│   ├── gateway.py              # Main gateway class
│   ├── api/                    # API layer
│   │   ├── auth.py             # Authentication
│   │   ├── event_bridge.py     # Event distribution
│   │   ├── events.py           # Event definitions
│   │   ├── handlers/           # API request handlers
│   │   ├── health.py           # Health checks
│   │   ├── protocol.py         # Protocol handlers
│   │   ├── queue.py            # Message queuing
│   │   ├── server.py           # WebSocket server
│   │   ├── session.py          # Session management
│   │   ├── state.py            # State management
│   │   ├── subscriptions.py    # Event subscriptions
│   │   └── tcp_server.py       # TCP server
│   ├── config/                 # Configuration module
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   └── models.py
│   ├── models/                 # Data models
│   │   ├── connection.py       # Connection models
│   │   └── packet.py           # Packet models
│   ├── network/                # Network layer
│   │   ├── connection_pool.py  # Connection pooling
│   │   ├── connection.py       # Network connections
│   │   ├── lpc.py              # LPC protocol support
│   │   └── mudmode.py          # MUD mode handling
│   ├── services/               # I3 services
│   │   ├── base.py             # Base service class
│   │   ├── channel.py          # Channel service
│   │   ├── finger.py           # Finger service
│   │   ├── locate.py           # Locate service
│   │   ├── router.py           # Router service
│   │   ├── tell.py             # Tell service
│   │   └── who.py              # Who service
│   ├── state/                  # State management
│   │   └── manager.py          # State manager
│   ├── utils/                  # Utilities
│   │   ├── circuit_breaker.py  # Circuit breaker pattern
│   │   ├── logging.py          # Logging utilities
│   │   ├── retry.py            # Retry logic
│   │   └── shutdown.py         # Graceful shutdown
│   └── py.typed                # Type checking marker
├── tests/                      # Test suite (1200+ tests)
│   ├── api/                    # API tests
│   ├── conftest.py             # Pytest fixtures
│   ├── fixtures/               # Test data
│   ├── integration/            # Integration tests
│   ├── performance/            # Performance tests
│   ├── services/               # Service tests
│   └── unit/                   # Unit tests
├── .editorconfig               # Editor configuration
├── .gitignore                  # Git ignore rules
├── .pre-commit-config.yaml     # Pre-commit hooks
├── .ruff.toml                  # Ruff linter configuration
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── Dockerfile                  # Container definition
├── docker-compose.yml          # Multi-container setup
├── docker-compose.override.yml # Development overrides
├── docker-compose.prod.yml     # Production setup
├── LICENSE.md
├── Makefile                    # Build automation
├── MANIFEST.in                 # Package manifest
├── pyproject.toml              # Project configuration
├── README.md
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Development dependencies
└── setup.cfg                   # Additional setup configuration
```

## Active Configuration

### 1. **Project Definition (pyproject.toml)**

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "i3-gateway"
version = "0.1.0"
description = "Intermud3 Protocol Gateway - A standalone Python service for MUD-to-I3 network bridging"
readme = "README.md"
requires-python = ">=3.9"
license = {text = "MIT"}

dependencies = [
    "pyyaml>=6.0",
    "structlog>=23.0",
    "aiohttp>=3.9.0",
    "pydantic>=2.0",
    "python-dotenv>=1.0.0",
    "click>=8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "pytest-mock>=3.11",
    "black>=23.0",
    "ruff>=0.1.0",
    "mypy>=1.5",
    "pre-commit>=3.3",
    "types-pyyaml>=6.0",
]
docs = [
    "sphinx>=7.0",
    "sphinx-rtd-theme>=1.3",
    "autodoc>=0.5",
]
security = [
    "bandit>=1.7",
    "safety>=2.3",
    "pip-audit>=2.6",
]

[project.scripts]
i3-gateway = "src.__main__:main"
```

### 2. **Code Quality Configuration**

#### **Ruff - Fast Python Linter**
```toml
[tool.ruff]
line-length = 100
target-version = "py39"

[tool.ruff.lint]
select = [
    "E", "W",      # pycodestyle
    "F",           # pyflakes
    "I",           # isort
    "B",           # flake8-bugbear
    "C4",          # flake8-comprehensions
    "UP",          # pyupgrade
    "ARG",         # flake8-unused-arguments
    "SIM",         # flake8-simplify
    "PTH",         # flake8-use-pathlib
    "ERA",         # flake8-eradicate
    "RUF",         # Ruff-specific rules
]
ignore = [
    "E501",        # Line too long (handled by black)
    "B008",        # Function calls in argument defaults
    "B904",        # raise without from inside except
    "SIM108",      # Use ternary operator
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "ARG001", "ARG002"]
"**/__init__.py" = ["F401"]
```

#### **Black - Code Formatter**
```toml
[tool.black]
line-length = 100
target-version = ['py39', 'py310', 'py311']
include = '\.pyi?$'
extend-exclude = '''
/(
    \.eggs | \.git | \.mypy_cache | \.venv | build | dist
)/
'''
```

#### **MyPy - Type Checker**
```toml
[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
show_error_codes = true
pretty = true
```

### 3. **Testing Configuration**

#### **Pytest Settings**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--verbose",
    "--cov=src",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-report=xml",
    "--cov-fail-under=80",
    "--strict-markers",
    "--tb=short",
]
asyncio_mode = "auto"
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow tests",
    "network: Tests requiring network access",
]

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/__init__.py", "*/conftest.py"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

### 4. **Pre-commit Hooks (Active)**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-json
      - id: check-toml
      - id: check-merge-conflict
      - id: debug-statements

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]

  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-pyyaml]
```

### 5. **Makefile Commands (Active)**

The project includes a comprehensive Makefile with these commands:

```makefile
make help            # Show all available commands
make install         # Install production dependencies
make install-dev     # Install development dependencies
make test            # Run all tests
make test-unit       # Run unit tests only
make test-integration # Run integration tests only
make test-coverage   # Run tests with coverage report
make lint            # Run linting checks
make format          # Format code with Black and Ruff
make type-check      # Run type checking with MyPy
make clean           # Clean up generated files
make run             # Run the I3 Gateway
make dev             # Run in development mode with auto-reload
make docker-build    # Build Docker image
make docker-run      # Run Docker container
make pre-commit      # Run pre-commit hooks on all files
make security        # Run security checks
make check           # Run all checks (lint, type-check, test)
make setup           # Complete development setup
```

### 6. **Docker Configuration**

```dockerfile
# Dockerfile (Active)
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY config/ config/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Run the gateway
CMD ["python", "-m", "src"]
```

```yaml
# docker-compose.yml (Active)
version: '3.8'

services:
  i3-gateway:
    build: .
    container_name: i3-gateway
    ports:
      - "4001:4001"
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    environment:
      - LOG_LEVEL=INFO
      - I3_ROUTER_HOST=204.209.44.3
      - I3_ROUTER_PORT=8080
    restart: unless-stopped
```

### 7. **VS Code Settings**

```json
// .vscode/settings.json (Active)
{
    "python.defaultInterpreter": "venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"],
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter"
    }
}
```

### 8. **Environment Configuration**

```ini
# .env.example (Template for local development)
# I3 Router Settings
I3_ROUTER_HOST=204.209.44.3
I3_ROUTER_PORT=8080
I3_ROUTER_PASSWORD=your_password_here

# Gateway Settings
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=4001

# MUD Settings
MUD_NAME=YourMUD
MUD_PORT=4000

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Security
GATEWAY_SECRET=your_secret_key
```

## Development Workflow

### Initial Setup
```bash
# Clone repository
git clone <repository-url>
cd Intermud3

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
make install-dev

# Copy environment template
cp .env.example .env
# Edit .env with your settings

# Run tests to verify setup
make test
```

### Daily Development
```bash
# Activate virtual environment
source venv/bin/activate

# Run linting and formatting
make format
make lint

# Run tests
make test-unit       # Quick unit tests
make test-coverage   # Full test suite with coverage

# Run the gateway
make dev            # Development mode with debug logging
```

### Before Committing
```bash
# Run all checks
make check

# Or manually run pre-commit
pre-commit run --all-files
```

## Project Status

Currently in **Phase 1-2** of development (see docs/HIGH_LEVEL_PLAN.md):
- ✅ Project structure and configuration
- ✅ Development environment setup
- 🚧 Core network protocol implementation
- 🚧 Basic service handlers
- ⏳ JSON-RPC API implementation
- ⏳ Advanced features and OOB services

## Key Dependencies

### Production
- **aiohttp**: Async HTTP client/server framework
- **pydantic**: Data validation using Python type annotations
- **pyyaml**: YAML configuration parsing
- **structlog**: Structured logging
- **click**: Command-line interface creation
- **python-dotenv**: Load environment variables from .env

### Development
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **pytest-cov**: Coverage reporting
- **black**: Code formatter
- **ruff**: Fast Python linter
- **mypy**: Static type checker
- **pre-commit**: Git hook framework

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on:
- Code style and formatting
- Testing requirements
- Pull request process
- Issue reporting

## License

MIT License - see [LICENSE.md](../LICENSE.md) for details
