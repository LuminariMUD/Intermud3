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
├── LICENSE
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
requires = ["setuptools>=83.0.0", "wheel>=0.47.0"]
build-backend = "setuptools.build_meta"

[project]
name = "i3-gateway"
version = "0.1.0"
description = "Intermud3 Protocol Gateway - A standalone Python service for MUD-to-I3 network bridging"
readme = "README.md"
requires-python = ">=3.12"
license = "MIT"
license-files = ["LICENSE"]

dependencies = [
    "pyyaml>=6.0.3",
    "structlog>=26.1.0",
    "aiohttp>=3.14.3",
    "pydantic>=2.13.4",
    "python-dotenv>=1.2.2",
    "click>=8.4.2",
    "psutil>=7.2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.1.1",
    "pytest-asyncio>=1.4.0",
    "pytest-cov>=7.1.0",
    "pytest-mock>=3.15.1",
    "black>=26.5.1",
    "ruff>=0.16.0",
    "mypy>=2.3.0",
    "pre-commit>=4.6.1",
    "types-pyyaml>=6.0.12.20260724",
]
docs = [
    "sphinx>=9.1.0",
    "sphinx-rtd-theme>=3.1.0",
]
security = [
    "bandit>=1.9.4",
    "safety>=3.8.1",
    "pip-audit>=2.10.1",
]

[project.scripts]
i3-gateway = "src.__main__:main"
```

### 2. **Code Quality Configuration**

#### **Ruff - Fast Python Linter (.ruff.toml)**
```toml
target-version = "py312"
line-length = 100

[lint]
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
    "RUF",         # Ruff-specific rules
    "N",           # pep8-naming
    "D",           # pydocstyle
    "ANN",         # flake8-annotations
    "S",           # flake8-bandit
    "ASYNC",       # flake8-async
    "T20",         # flake8-print
    "RET",         # flake8-return
    "SLF",         # flake8-self
    "RSE",         # flake8-raise
    "PL",          # pylint
    "ERA",         # flake8-eradicate
    "ICN",         # flake8-import-conventions
    "PIE",         # flake8-pie
    "Q",           # flake8-quotes
    "DTZ",         # flake8-datetimez
    "EM",          # flake8-errmsg
    "FA",          # flake8-future-annotations
    "G",           # flake8-logging-format
    "INP",         # flake8-no-pep420
    "T10",         # flake8-debugger
    "YTT",         # flake8-2020
]

ignore = [
    "D100", "D104", "D107",  # Missing docstrings
    "D203", "D212",          # Docstring formatting
    "ANN101", "ANN102",      # Missing type annotations for self/cls
    "ANN401",                # Dynamically typed expressions
    "PLR0913", "PLR0915",    # Too many arguments/statements
    "PLR0912", "PLR2004",    # Too many branches/magic values
    "S101",                  # Use of assert detected
    "S311",                  # Standard pseudo-random generators
    "EM101", "EM102",        # Exception message formatting
    "G004",                  # Logging statement uses f-string
    "INP001",                # Implicit namespace package
]

[lint.per-file-ignores]
"tests/**/*.py" = ["S101", "ARG", "D", "ANN", "PLR2004", "PLR0913", "PLR0915", "S311", "SLF001"]
"**/__init__.py" = ["F401", "D104"]
"src/__main__.py" = ["T20"]
"clients/examples/*.py" = ["T20", "S101"]
```

#### **Black - Code Formatter**
```toml
[tool.black]
line-length = 100
target-version = ['py312', 'py313', 'py314']
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
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
follow_imports = "normal"
ignore_missing_imports = true
pretty = true
show_column_numbers = true
show_error_codes = true
show_error_context = true
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
    rev: v6.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: check-json
      - id: check-toml
      - id: check-merge-conflict
      - id: debug-statements
      - id: detect-private-key
      - id: check-case-conflict
      - id: check-docstring-first
      - id: mixed-line-ending
        args: ['--fix=lf']
      - id: check-executables-have-shebangs
      - id: check-shebang-scripts-are-executable

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.0
    hooks:
      - id: ruff-check
        name: "Ruff linter"
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format
        name: "Ruff formatter"

  - repo: https://github.com/psf/black
    rev: 26.5.1
    hooks:
      - id: black
        name: "Format Python code with Black"

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v2.3.0
    hooks:
      - id: mypy
        name: "Type check with MyPy"
        additional_dependencies:
          - types-pyyaml>=6.0.12.20260724
          - types-setuptools>=83.0.0.20260724
          - pydantic>=2.13.4
          - aiohttp>=3.14.3
          - structlog>=26.1.0
          - click>=8.4.2
        args: [--ignore-missing-imports, --strict, --show-error-codes]
        exclude: ^tests/

  - repo: https://github.com/PyCQA/bandit
    rev: 1.9.4
    hooks:
      - id: bandit
        name: "Security check with Bandit"
        args: [-ll, -r, src/, --skip, B101]
        exclude: ^tests/

  - repo: https://github.com/commitizen-tools/commitizen
    rev: v4.16.5
    hooks:
      - id: commitizen
        name: "Check commit message format"
      - id: commitizen-branch
        name: "Check branch naming convention"
        stages: [pre-push]

  - repo: https://github.com/pycqa/isort
    rev: 8.0.1
    hooks:
      - id: isort
        name: "Sort imports with isort"
        args: ["--profile", "black", "--line-length", "100"]

  - repo: https://github.com/python-poetry/poetry
    rev: 2.4.1
    hooks:
      - id: poetry-check
        name: "Validate pyproject.toml"
        files: pyproject.toml

  - repo: https://github.com/PyCQA/docformatter
    rev: v1.7.8
    hooks:
      - id: docformatter
        name: "Format docstrings"
        args: [--in-place, --wrap-summaries, "100", --wrap-descriptions, "100"]
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
# Dockerfile (Active) - Multi-stage production build
FROM python:3.14.6-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.14.6-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 i3gateway && \
    mkdir -p /app/logs /app/state /app/config && \
    chown -R i3gateway:i3gateway /app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=i3gateway:i3gateway src/ src/
COPY --chown=i3gateway:i3gateway config/ config/
COPY --chown=i3gateway:i3gateway clients/ clients/

# Switch to non-root user
USER i3gateway

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose ports: WebSocket API, TCP API, Metrics/Health
EXPOSE 8080 8081 9090

# Run the application
CMD ["python", "-m", "src"]
```

```yaml
# docker-compose.yml (Active) - Full production setup
version: '3.8'

services:
  i3-gateway:
    build:
      context: .
      dockerfile: Dockerfile
    image: i3-gateway:latest
    container_name: i3-gateway
    restart: unless-stopped
    ports:
      - "8080:8080"  # WebSocket API port
      - "8081:8081"  # TCP API port
      - "9090:9090"  # Metrics/health port
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
      - ./state:/app/state
      - ./.env:/app/.env:ro
    environment:
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - MUD_NAME=${MUD_NAME}
      - MUD_PORT=${MUD_PORT}
      - I3_ROUTER_HOST=${I3_ROUTER_HOST:-204.209.44.3}
      - I3_ROUTER_PORT=${I3_ROUTER_PORT:-8080}
      - API_WS_HOST=0.0.0.0
      - API_WS_PORT=8080
      - API_TCP_HOST=0.0.0.0
      - API_TCP_PORT=8081
      - I3_GATEWAY_SECRET=${I3_GATEWAY_SECRET}
    networks:
      - i3-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

networks:
  i3-network:
    driver: bridge
```

### 7. **Environment Configuration**

```ini
# Environment variables for I3 Gateway (create .env file from this template)

# I3 Router Settings
I3_ROUTER_HOST=204.209.44.3
I3_ROUTER_PORT=8080
I3_ROUTER_PASSWORD=your_password_here

# API Server Settings
API_WS_HOST=0.0.0.0
API_WS_PORT=8080
API_TCP_HOST=0.0.0.0
API_TCP_PORT=8081

# MUD Settings
MUD_NAME=YourMUD
MUD_PORT=4000

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=structured

# Security
I3_GATEWAY_SECRET=your_secret_key_here

# Development
DEBUG=false
ENABLE_METRICS=true
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

# Create environment file
# Copy and edit environment variables as needed

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

**Phase 3 COMPLETE** (December 2024) - Full API implementation:
- ✅ Project structure and configuration
- ✅ Development environment setup
- ✅ Core network protocol implementation
- ✅ Complete I3 service handlers (channel, tell, who, finger, locate)
- ✅ WebSocket and TCP API servers
- ✅ Event-driven architecture with event bridge
- ✅ Session management and authentication
- ✅ Comprehensive error handling and circuit breakers
- ✅ Health checks and monitoring
- ✅ Production-ready Docker deployment
- ✅ 1200+ tests with ~75-78% coverage
- 🚧 Performance optimizations and monitoring dashboard
- ⏳ Advanced OOB services and protocol extensions

## Key Dependencies

### Production
- **aiohttp**: Async HTTP client/server framework for WebSocket and TCP APIs
- **pydantic**: Data validation and serialization using Python type annotations
- **pyyaml**: YAML configuration file parsing
- **structlog**: Structured logging with JSON output support
- **click**: Command-line interface creation toolkit
- **python-dotenv**: Environment variable loading from .env files
- **psutil**: System and process monitoring utilities

### Development
- **pytest**: Testing framework with async support
- **pytest-asyncio**: Async test execution support
- **pytest-cov**: Code coverage reporting and analysis
- **pytest-mock**: Mock object utilities for testing
- **black**: Opinionated Python code formatter
- **ruff**: Ultra-fast Python linter and formatter
- **mypy**: Static type checking for Python
- **pre-commit**: Git hook framework for code quality
- **bandit**: Security vulnerability scanner
- **safety**: Dependency vulnerability scanner

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on:
- Code style and formatting
- Testing requirements
- Pull request process
- Issue reporting

## License

MIT License - see [LICENSE](../../LICENSE) for details
