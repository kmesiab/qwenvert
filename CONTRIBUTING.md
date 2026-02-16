# Contributing to Qwenvert

Thank you for your interest in contributing to qwenvert! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers get started
- Assume good intentions

## How to Contribute

### Reporting Issues

**Before creating an issue:**
- Search existing issues to avoid duplicates
- Check if the issue exists in the latest version

**When creating an issue, include:**
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- System information (Mac model, RAM, macOS version)
- Python version (`python3 --version`)
- Qwenvert version (`qwenvert --version`)
- Relevant logs or error messages

**Example:**
```
**Problem:** qwenvert init fails to download model

**Steps to reproduce:**
1. Run `qwenvert init`
2. Model download starts but hangs at 50%

**Expected:** Model downloads completely
**Actual:** Download hangs, no error message

**System:**
- Mac: M1 Pro, 16GB RAM
- macOS: 14.2
- Python: 3.11.6
- Qwenvert: 0.1.0

**Error:**
(paste error message or logs)
```

### Suggesting Features

**Good feature requests include:**
- Clear use case or problem it solves
- Expected behavior
- Why existing features don't solve the problem
- Willingness to contribute implementation (optional but appreciated)

## Development Workflow

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/qwenvert.git
cd qwenvert

# Add upstream remote
git remote add upstream https://github.com/kmesiab/qwenvert.git
```

### 2. Set Up Development Environment

**macOS Python 3.11+ Users:** Modern macOS uses system-protected Python (PEP 668). Always use a virtual environment for development.

#### Quick Setup (Recommended)

```bash
# Create and activate virtual environment
make venv
source .venv/bin/activate

# Install qwenvert in editable mode + dev dependencies
make install-dev

# Verify installation
qwenvert --version
```

#### Manual Setup (Alternative)

```bash
# Create virtual environment manually
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux

# Install development dependencies (includes qwenvert)
pip install -e ".[dev]"
```

**Verify your environment:**
```bash
# Should show .venv Python, not system Python
which python3

# Should show "pip" from .venv
which pip
```

**Note:** The virtual environment is gitignored (`.venv/` in `.gitignore`).

### 3. Create a Feature Branch

**Branch naming conventions:**
- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation changes
- `test/description` - Test additions/improvements
- `refactor/description` - Code refactoring

**Example:**
```bash
# Sync with upstream first
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/add-mlx-backend
```

### 4. Make Changes

**Code style:**
- Follow PEP 8 conventions
- Use type hints where appropriate
- Add docstrings for public functions/classes
- Keep functions focused and small
- Use descriptive variable names

**Example:**
```python
def download_model(
    model: Model,
    force: bool = False,
) -> Path:
    """
    Download a model from HuggingFace.

    Args:
        model: Model configuration with HuggingFace repo info
        force: Force re-download even if file exists

    Returns:
        Path to downloaded model file

    Raises:
        ValueError: If model doesn't have HuggingFace repo info
        RuntimeError: If download fails
    """
    # Implementation...
```

**Format code before committing:**
```bash
# Format with black
black qwenvert/ tests/

# Sort imports
isort qwenvert/ tests/

# Type check (optional but recommended)
mypy qwenvert/
```

### 5. Write Tests

**Test requirements:**
- Add tests for new features
- Ensure existing tests pass
- Aim for >80% code coverage

**Test organization:**
- `tests/unit/` - Fast, isolated unit tests
- `tests/integration/` - Integration tests with mocked backends
- `tests/security/` - Security and isolation tests
- `tests/e2e/` - End-to-end tests (require real backends)

**Example test:**
```python
import pytest
from qwenvert.models import Model, ModelSelector

def test_model_selector_chooses_q4_for_8gb():
    """Test that ModelSelector picks Q4 model for 8GB Mac."""
    hardware = HardwareInfo(total_memory_gb=8, ...)
    selector = ModelSelector(registry)

    model = selector.select_default(hardware)

    assert model.quantization == "Q4_K_M"
    assert model.min_ram_gb <= 8
```

**Run tests:**
```bash
# Run all tests
pytest

# Run specific test category
pytest -m unit
pytest -m integration
pytest -m security

# Run with coverage
pytest --cov=qwenvert --cov-report=html

# Run specific test file
pytest tests/unit/test_models.py

# Run specific test
pytest tests/unit/test_models.py::test_model_selector_chooses_q4_for_8gb
```

### 6. Commit Changes

**Commit message format:**
```
Short summary (50 chars or less)

Detailed explanation of changes (wrap at 72 chars):
- What changed
- Why it changed
- Any breaking changes
- References to issues

Token usage: ~XXk tokens
Estimated cost: $X.XX (Model name)

Co-Authored-By: Your Name <your.email@example.com>
```

**Example:**
```
Add MLX backend support for Apple Silicon optimization

Implements MLX backend as alternative to Ollama/llama.cpp:
- Add MLXBackend class with generate() and generate_stream()
- Integrate with BackendRouter
- Add MLX-specific model configurations
- Update CLI to support --backend mlx

Breaking changes: None

Fixes #42

Token usage: ~45k tokens
Estimated cost: $0.23 (Sonnet 4.5)

Co-Authored-By: Jane Developer <jane@example.com>
```

**Commit best practices:**
- Make atomic commits (one logical change per commit)
- Write clear, descriptive commit messages
- Reference issues when applicable
- Include token usage for AI-assisted commits

### 7. Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/add-mlx-backend

# Create PR on GitHub
```

**PR template:**
```markdown
## Summary
Brief description of changes

## Changes
- Change 1
- Change 2
- Change 3

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Documentation updated

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added for new features
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Commit messages are clear
```

## Code Style Guidelines

### Python Style

**Follow PEP 8 with these preferences:**
- Line length: 100 characters (not 79)
- Use double quotes for strings
- Use trailing commas in multi-line structures
- Use f-strings for formatting

**Import order:**
```python
# Standard library
import os
from pathlib import Path

# Third-party
import httpx
from rich.console import Console

# Local
from qwenvert.config import Config
from qwenvert.models import Model
```

### Naming Conventions

- **Classes:** `PascalCase` (e.g., `ModelSelector`, `HardwareDetector`)
- **Functions/methods:** `snake_case` (e.g., `select_default`, `detect_hardware`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `DEFAULT_PORT`, `MAX_RETRIES`)
- **Private methods:** `_leading_underscore` (e.g., `_validate_config`)

### Documentation

**Docstrings:**
- Use Google-style docstrings
- Include type hints in function signatures
- Document exceptions
- Add usage examples for complex functions

**Comments:**
- Explain *why*, not *what*
- Keep comments up-to-date with code changes
- Use TODO/FIXME/NOTE markers appropriately

## Areas for Contribution

### High Priority

- **Model support** - Add Qwen3-Coder models, other model families
- **Backend support** - MLX, vLLM, TensorRT-LLM implementations
- **Documentation** - Tutorials, examples, troubleshooting guides
- **Testing** - More edge cases, hardware configurations

### Medium Priority

- **Performance** - Optimization for specific Mac models
- **Monitoring** - Enhanced telemetry and observability
- **CLI improvements** - Better error messages, help text
- **Configuration** - More tuning options

### Nice to Have

- **Benchmarking** - Automated performance testing
- **CI/CD** - GitHub Actions workflows
- **PyPI packaging** - Distribution improvements
- **Homebrew formula** - Mac-native installation

## Review Process

1. **Automated checks** - Tests, linting, type checking must pass
2. **Code review** - Maintainer reviews code, provides feedback
3. **Discussion** - Address questions, make requested changes
4. **Approval** - Maintainer approves PR
5. **Merge** - PR merged to main branch

**Review criteria:**
- Code quality and style
- Test coverage
- Documentation completeness
- Breaking changes justified
- Performance impact considered

## GitHub Actions & Secrets

### Security Scanning

This repository uses the [SafetyCLI Self-Healing Action](https://github.com/kmesiab/safetycli-self-healing-action) to automatically scan Python dependencies for security vulnerabilities.

**Workflow:** `.github/workflows/security.yml`
- **Schedule:** Runs daily at 3am PST (11am UTC)
- **Manual:** Can be triggered via workflow_dispatch
- **Action:** Scans dependencies, creates GitHub issues for vulnerabilities, and assigns them to GitHub Copilot for automated remediation

**Required Secret:**
- `SAFETY_API_KEY` - API key for Safety CLI vulnerability scanning
  - Get your free API key at [Safety Platform](https://platform.safetycli.com/cli/auth)
  - Add it to repository secrets: Settings → Secrets and variables → Actions → New repository secret

### Other Workflows

- **CI** (`.github/workflows/ci.yml`) - Code quality checks and tests on push/PR
- **Publish** (`.github/workflows/publish.yml`) - Publishes package to PyPI on release

## Getting Help

- **GitHub Issues** - Ask questions, report problems
- **Discussions** - General questions, feature ideas
- **README** - Getting started, troubleshooting

## License

By contributing to qwenvert, you agree that your contributions will be licensed under the Apache 2.0 License.

---

**Thank you for contributing to qwenvert!** 🚀
