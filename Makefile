.PHONY: help install install-dev clean lint format typecheck test test-unit test-integration coverage check-all

PYTHON ?= python3

# Default target
help:
	@echo "qwenvert - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install development dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  make format           Format code with black and ruff"
	@echo "  make lint             Run all linters (ruff)"
	@echo "  make typecheck        Run type checking with mypy"
	@echo "  make check-all        Run all checks (format-check, lint, typecheck, test)"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests with coverage"
	@echo "  make test-unit        Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make coverage         Generate coverage report"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            Remove build artifacts and cache"

# Installation
install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -m pip install pytest pytest-asyncio pytest-cov black ruff mypy

# Code formatting
format:
	@echo "Running black..."
	$(PYTHON) -m black qwenvert tests
	@echo "Running ruff fix..."
	$(PYTHON) -m ruff check --fix qwenvert tests
	@echo "✓ Formatting complete"

format-check:
	@echo "Checking black formatting..."
	$(PYTHON) -m black --check qwenvert tests
	@echo "✓ Format check passed"

# Linting
lint:
	@echo "Running ruff linter..."
	$(PYTHON) -m ruff check qwenvert tests
	@echo "✓ Lint check passed"

# Type checking
typecheck:
	@echo "Running mypy..."
	$(PYTHON) -m mypy qwenvert
	@echo "✓ Type check passed"

# Testing
test:
	@echo "Running tests with coverage..."
	$(PYTHON) -m pytest
	@echo "✓ Tests passed"

test-unit:
	@echo "Running unit tests..."
	$(PYTHON) -m pytest -m unit
	@echo "✓ Unit tests passed"

test-integration:
	@echo "Running integration tests..."
	$(PYTHON) -m pytest -m integration
	@echo "✓ Integration tests passed"

coverage:
	@echo "Generating coverage report..."
	$(PYTHON) -m pytest --cov=qwenvert --cov-report=html --cov-report=term
	@echo "✓ Coverage report generated in htmlcov/"

# Run all checks (CI equivalent)
check-all: format-check lint typecheck test
	@echo "✓ All checks passed!"

# Cleanup
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✓ Cleanup complete"
