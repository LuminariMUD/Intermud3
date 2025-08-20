.PHONY: help install install-dev test test-unit test-integration test-coverage lint format type-check clean run dev docker-build docker-run pre-commit security docs

# Variables
PYTHON := python3
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
BLACK := $(PYTHON) -m black
RUFF := $(PYTHON) -m ruff
MYPY := $(PYTHON) -m mypy
BANDIT := $(PYTHON) -m bandit

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo '$(GREEN)Available commands:$(NC)'
	@echo ''
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Install production dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	pre-commit install

test: ## Run all tests
	$(PYTEST) tests/ -v

test-unit: ## Run unit tests only
	$(PYTEST) tests/unit/ -v -m unit

test-integration: ## Run integration tests only
	$(PYTEST) tests/integration/ -v -m integration

test-coverage: ## Run tests with coverage report
	$(PYTEST) tests/ -v --cov=src --cov-report=term-missing --cov-report=html

lint: ## Run linting checks
	@echo "$(YELLOW)Running Ruff...$(NC)"
	$(RUFF) check src/ tests/
	@echo "$(YELLOW)Checking Black formatting...$(NC)"
	$(BLACK) --check src/ tests/
	@echo "$(GREEN)Linting passed!$(NC)"

format: ## Format code with Black and Ruff
	@echo "$(YELLOW)Formatting with Black...$(NC)"
	$(BLACK) src/ tests/
	@echo "$(YELLOW)Fixing with Ruff...$(NC)"
	$(RUFF) check --fix src/ tests/
	@echo "$(GREEN)Formatting complete!$(NC)"

type-check: ## Run type checking with MyPy
	$(MYPY) src/

clean: ## Clean up generated files
	@echo "$(YELLOW)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)Clean complete!$(NC)"

run: ## Run the I3 Gateway
	$(PYTHON) -m src

dev: ## Run in development mode with auto-reload
	LOG_LEVEL=DEBUG $(PYTHON) -m src --debug

docker-build: ## Build Docker image
	docker build -t i3-gateway:latest .

docker-run: ## Run Docker container
	docker run -it --rm \
		-p 4001:4001 \
		-v $(PWD)/config:/app/config \
		-v $(PWD)/logs:/app/logs \
		--env-file .env \
		i3-gateway:latest

docker-compose-up: ## Start services with docker-compose
	docker-compose up -d

docker-compose-down: ## Stop services with docker-compose
	docker-compose down

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

pre-commit-update: ## Update pre-commit hooks
	pre-commit autoupdate

security: ## Run security checks
	@echo "$(YELLOW)Running Bandit security scan...$(NC)"
	$(BANDIT) -r src/ -ll
	@echo "$(YELLOW)Running Safety check...$(NC)"
	-safety check
	@echo "$(YELLOW)Running pip-audit...$(NC)"
	-pip-audit
	@echo "$(GREEN)Security checks complete!$(NC)"

docs: ## Build documentation with Sphinx
	cd docs && make html
	@echo "$(GREEN)Documentation built! Open docs/_build/html/index.html$(NC)"

docs-serve: ## Serve documentation locally
	cd docs/_build/html && $(PYTHON) -m http.server 8000

update-requirements: ## Update requirements files
	@echo "$(YELLOW)Requirements files should be manually maintained$(NC)"
	@echo "$(YELLOW)See requirements.txt and requirements-dev.txt$(NC)"

check: lint type-check test ## Run all checks (lint, type-check, test)
	@echo "$(GREEN)All checks passed!$(NC)"

setup: install-dev ## Complete development setup
	@echo "$(GREEN)Development environment setup complete!$(NC)"
	@echo "$(YELLOW)Don't forget to activate your virtual environment:$(NC)"
	@echo "  source venv/bin/activate  # On Linux/Mac"
	@echo "  venv\\Scripts\\activate     # On Windows"

.DEFAULT_GOAL := help
