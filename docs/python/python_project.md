Here's a comprehensive guide to everything you need for a professional Python project:

## Essential Python Project Infrastructure

### 1. **Project Management & Dependencies**

```toml
# pyproject.toml (Modern Python project config)
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "i3-gateway"
version = "0.1.0"
description = "Intermud3 Protocol Gateway"
readme = "README.md"
requires-python = ">=3.9"
dependencies = [
    "asyncio",
    "pyyaml>=6.0",
    "structlog>=23.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "black>=23.0",
    "ruff>=0.1.0",
    "mypy>=1.5",
    "pre-commit>=3.3",
]
```

**Poetry Alternative** (Many prefer this):
```bash
poetry init
poetry add pyyaml structlog
poetry add --group dev pytest black ruff mypy
```

### 2. **Code Quality Tools**

#### **Linting - Ruff (Fast, replaces Flake8/Pylint)**
```toml
# ruff.toml or pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py39"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "ARG", # flake8-unused-arguments
    "SIM", # flake8-simplify
]
ignore = ["E501", "B008"]  # Line length, function calls in defaults

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]  # Allow assert in tests
```

#### **Code Formatting - Black**
```toml
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py39']
include = '\.pyi?$'
```

#### **Type Checking - MyPy**
```toml
# pyproject.toml
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
```

### 3. **Testing Framework**

#### **Pytest + Coverage**
```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --verbose
    --cov=src
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=80
asyncio_mode = auto
```

```python
# tests/conftest.py (Pytest fixtures)
import pytest
import asyncio

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def mock_i3_server():
    """Mock I3 server for testing"""
    # Your mock implementation
```

### 4. **Pre-commit Hooks**

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
        additional_dependencies: [types-all]
```

Install with:
```bash
pre-commit install
pre-commit run --all-files  # Run on all files
```

### 5. **Documentation Tools**

#### **Docstrings - Google Style**
```python
def send_packet(self, packet: I3Packet, timeout: float = 30.0) -> bool:
    """Send an I3 packet to the router.

    Args:
        packet: The I3 packet to send
        timeout: Maximum time to wait for send completion

    Returns:
        True if packet was sent successfully

    Raises:
        ConnectionError: If not connected to router
        TimeoutError: If send times out

    Example:
        >>> gateway.send_packet(tell_packet, timeout=10.0)
        True
    """
```

#### **Sphinx Documentation**
```bash
pip install sphinx sphinx-rtd-theme autodoc
sphinx-quickstart docs/
```

### 6. **Logging & Debugging**

```python
# src/utils/logging.py
import logging
import structlog

def setup_logging(level: str = "INFO", json: bool = False):
    """Configure structured logging"""

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.set_exc_info,
    ]

    if json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level)
        ),
    )
```

### 7. **Environment Management**

```ini
# .env (for local development)
I3_ROUTER_HOST=204.209.44.3
I3_ROUTER_PORT=8080
LOG_LEVEL=DEBUG
GATEWAY_PORT=4000
```

```python
# src/config.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    """Application settings with validation"""

    i3_router_host: str
    i3_router_port: int = 8080
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
```

### 8. **CI/CD - GitHub Actions**

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11"]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        pip install -e ".[dev]"

    - name: Lint with ruff
      run: ruff check .

    - name: Format with black
      run: black --check .

    - name: Type check with mypy
      run: mypy src/

    - name: Test with pytest
      run: pytest --cov=src --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### 9. **Security Tools**

```bash
# Security scanning
pip install bandit safety pip-audit

# Run security checks
bandit -r src/
safety check
pip-audit
```

### 10. **Performance Profiling**

```python
# Profile async code
import cProfile
import pstats
from line_profiler import LineProfiler

# Memory profiling
from memory_profiler import profile

@profile
def memory_intensive_function():
    # Your code
```

### 11. **Project Structure**

```
i3-gateway/
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── conf.py
│   └── index.rst
├── src/
│   └── i3_gateway/
│       ├── __init__.py
│       ├── __main__.py      # Entry point
│       ├── network/
│       ├── services/
│       └── utils/
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
├── README.md
└── requirements.txt         # Generated from pyproject.toml
```

### 12. **Makefile for Common Tasks**

```makefile
# Makefile
.PHONY: help install test lint format clean

help:
	@echo "Available commands:"
	@echo "  install    Install dependencies"
	@echo "  test       Run tests"
	@echo "  lint       Run linting"
	@echo "  format     Format code"
	@echo "  clean      Clean up files"

install:
	pip install -e ".[dev]"
	pre-commit install

test:
	pytest

lint:
	ruff check .
	mypy src/

format:
	black .
	ruff check --fix .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov dist build *.egg-info
```

### 13. **Docker Setup**

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install -e .

COPY src/ src/

CMD ["python", "-m", "i3_gateway"]
```

### 14. **VS Code Configuration**

```json
// .vscode/settings.json
{
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    }
}
```

### 15. **Essential .gitignore**

```gitignore
# .gitignore
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv
.env
.pytest_cache/
.coverage
htmlcov/
dist/
build/
*.egg-info/
.mypy_cache/
.ruff_cache/
.DS_Store
*.log
```

## Quick Setup Commands

```bash
# Create project
mkdir i3-gateway && cd i3-gateway
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Initialize project
pip install --upgrade pip
pip install poetry  # or use pip with pyproject.toml

# Install everything
poetry install  # or pip install -e ".[dev]"

# Set up pre-commit
pre-commit install

# Run all checks
make lint
make test
make format

# Start development
python -m i3_gateway
```

## Priority Order for Implementation

1. **First (Essential)**
   - Virtual environment
   - pyproject.toml / requirements.txt
   - Basic project structure
   - Git + .gitignore

2. **Second (Quality)**
   - Pytest for testing
   - Black for formatting
   - Ruff for linting
   - Pre-commit hooks

3. **Third (Professional)**
   - MyPy for type checking
   - Coverage reporting
   - CI/CD with GitHub Actions
   - Logging with structlog

4. **Fourth (Polish)**
   - Documentation with Sphinx
   - Docker setup
   - Makefile
   - Security scanning

This comprehensive setup ensures your Python project follows industry best practices and is ready for production deployment!
