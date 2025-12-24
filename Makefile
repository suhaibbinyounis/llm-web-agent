.PHONY: install install-dev test lint format type-check clean run help

# Default Python interpreter
PYTHON := python3

# Virtual environment
VENV := .venv
VENV_BIN := $(VENV)/bin

help:  ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install:  ## Install the package
	$(PYTHON) -m pip install -e .

install-dev:  ## Install the package with dev dependencies
	$(PYTHON) -m pip install -e ".[all]"
	playwright install chromium

venv:  ## Create virtual environment
	$(PYTHON) -m venv $(VENV)
	@echo "Virtual environment created. Activate with: source $(VENV)/bin/activate"

test:  ## Run tests
	pytest tests/ -v --cov=src/llm_web_agent --cov-report=term-missing

test-unit:  ## Run unit tests only
	pytest tests/unit/ -v

test-integration:  ## Run integration tests only
	pytest tests/integration/ -v

lint:  ## Run linter (ruff)
	ruff check src/ tests/

lint-fix:  ## Run linter and fix issues
	ruff check src/ tests/ --fix

format:  ## Format code with black
	black src/ tests/

format-check:  ## Check code formatting
	black src/ tests/ --check

type-check:  ## Run type checker (mypy)
	mypy src/llm_web_agent --ignore-missing-imports

check-all: lint format-check type-check  ## Run all checks

clean:  ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf src/*.egg-info
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:  ## Run the CLI
	$(PYTHON) -m llm_web_agent

run-example:  ## Run a basic example
	$(PYTHON) examples/basic_navigation.py
