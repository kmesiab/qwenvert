.PHONY: help install install-dev clean lint format typecheck test test-unit test-integration coverage check-all benchmark build publish-test publish release venv check-venv

PYTHON ?= python3

# Default target
help:
	@echo "qwenvert - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make venv             Create virtual environment at .venv/"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install development dependencies (requires venv)"
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
	@echo "Performance:"
	@echo "  make benchmark        Run performance benchmarks"
	@echo ""
	@echo "Publishing:"
	@echo "  make build            Build distribution packages"
	@echo "  make publish-test     Publish to TestPyPI"
	@echo "  make publish          Publish to PyPI (requires version tag)"
	@echo "  make release          Create GitHub release and publish to PyPI"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            Remove build artifacts and cache"

# Installation
install:
	$(PYTHON) -m pip install -e .

install-dev: check-venv
	$(PYTHON) -m pip install -e ".[dev]"

# Virtual environment helpers
venv:
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv .venv
	@echo "✓ Virtual environment created at .venv/"
	@echo ""
	@echo "Activate it with:"
	@echo "  source .venv/bin/activate      # bash/zsh"
	@echo "  source .venv/bin/activate.fish # fish"
	@echo ""
	@echo "Then install dependencies:"
	@echo "  make install-dev"

check-venv:
	@if [ -n "$$CI" ]; then \
		: ; \
	elif $(PYTHON) -c "import sys; exit(0 if sys.prefix != sys.base_prefix else 1)" 2>/dev/null; then \
		: ; \
	else \
		echo "⚠️  Warning: Not in a virtual environment!"; \
		echo ""; \
		echo "Create one with:"; \
		echo "  make venv"; \
		echo ""; \
		echo "Or use conda/poetry if preferred."; \
		echo ""; \
		echo "Then activate and retry:"; \
		echo "  source .venv/bin/activate"; \
		echo "  make install-dev"; \
		exit 1; \
	fi

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

# Performance benchmarks
benchmark:
	@echo "Running performance benchmarks..."
	@echo "Make sure qwenvert is running (qwenvert start)"
	$(PYTHON) benchmarks/run_benchmarks.py
	@echo "✓ Benchmarks complete"

# Publishing
build: clean
	@echo "Building distribution packages..."
	$(PYTHON) -m pip install --upgrade build twine
	$(PYTHON) -m build
	@echo "Checking package metadata..."
	$(PYTHON) -m twine check dist/*
	@echo "✓ Build complete"
	@echo ""
	@echo "Built packages:"
	@ls -lh dist/

publish-test: build
	@echo "Publishing to TestPyPI..."
	@echo "⚠️  Make sure TEST_PYPI_API_TOKEN is set in environment or ~/.pypirc"
	$(PYTHON) -m twine upload --repository testpypi dist/*
	@echo "✓ Published to TestPyPI: https://test.pypi.org/project/qwenvert/"
	@echo ""
	@echo "Test installation with:"
	@echo "  pip install --index-url https://test.pypi.org/simple/ qwenvert"

publish: build check-all
	@echo "Publishing to PyPI..."
	@echo "⚠️  This will publish to PRODUCTION PyPI!"
	@echo "⚠️  Make sure PYPI_API_TOKEN is set in environment or ~/.pypirc"
	@echo ""
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ]
	$(PYTHON) -m twine upload dist/*
	@echo "✓ Published to PyPI: https://pypi.org/project/qwenvert/"
	@echo ""
	@echo "Verify installation with:"
	@echo "  pip install --upgrade qwenvert"
	@echo "  qwenvert --version"

release:
	@echo "Creating release..."
	@echo ""
	@# Get version from pyproject.toml
	@VERSION=$$($(PYTHON) -c "import tomllib; f=open('pyproject.toml','rb'); print(tomllib.load(f)['project']['version'])"); \
	echo "Version: $$VERSION"; \
	echo "Tag: v$$VERSION"; \
	echo ""; \
	read -p "Create release v$$VERSION? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ]; \
	git tag -a "v$$VERSION" -m "Release v$$VERSION"; \
	git push origin "v$$VERSION"; \
	gh release create "v$$VERSION" \
	  --title "qwenvert v$$VERSION" \
	  --generate-notes \
	  --draft
	@echo ""
	@echo "✓ Draft release created on GitHub"
	@echo "📝 Edit the release notes, then publish to trigger PyPI upload"

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
