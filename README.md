# qwenvert

[![CI](https://github.com/kmesiab/qwenvert/actions/workflows/ci.yml/badge.svg)](https://github.com/kmesiab/qwenvert/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/kmesiab/qwenvert/branch/main/graph/badge.svg)](https://codecov.io/gh/kmesiab/qwenvert)
[![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

One-click local LLM inference for Claude Code on Mac M1/M2/M3/M4.

## Features

- 🚀 **Apple Silicon Optimized** - Leverages MLX for maximum performance on M-series chips
- 🧠 **Hardware Detection** - Automatically detects your Mac's capabilities and optimizes accordingly
- 🔧 **Zero Configuration** - Works out of the box with sensible defaults
- 📊 **Smart Resource Management** - Adapts to your system's memory and thermal constraints
- 🎯 **Claude Code Integration** - Seamlessly integrates with Claude Code for local inference

## Requirements

- macOS with Apple Silicon (M1, M1 Pro, M1 Max, M1 Ultra, M2, M2 Pro, M2 Max, M2 Ultra, M3, M3 Pro, M3 Max, M4)
- Python 3.9 - 3.12
- 8GB+ RAM (16GB+ recommended)

## Installation

```bash
# Clone the repository
git clone https://github.com/kmesiab/qwenvert.git
cd qwenvert

# Install with pip
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

## Usage

```python
from qwenvert import detect_hardware

# Detect your hardware
profile = detect_hardware()
print(profile)
# Output: M1 Pro | 16GB RAM | 16 GPU cores | Active Cooling
```

## Development

### Quick Start

```bash
# Install development dependencies
make install-dev

# Run all quality checks
make check-all
```

### Available Commands

#### Setup
- `make install` - Install production dependencies
- `make install-dev` - Install development dependencies

#### Code Quality
- `make format` - Format code with black and ruff
- `make lint` - Run all linters (ruff)
- `make typecheck` - Run type checking with mypy
- `make check-all` - Run all checks (format, lint, typecheck, test)

#### Testing
- `make test` - Run all tests with coverage
- `make test-unit` - Run unit tests only
- `make test-integration` - Run integration tests only
- `make coverage` - Generate coverage report

#### Maintenance
- `make clean` - Remove build artifacts and cache

### Code Quality Standards

This project enforces strict code quality standards:

- **Formatting**: Black (line length 88)
- **Linting**: Ruff with comprehensive rule sets enabled
- **Type Checking**: MyPy in strict mode
- **Test Coverage**: Minimum 80% coverage required

All checks must pass before merging. Run `make check-all` to verify.

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please ensure:

1. All tests pass (`make test`)
2. Code is formatted (`make format`)
3. Linting passes (`make lint`)
4. Type checking passes (`make typecheck`)
5. Coverage remains above 80%

Run `make check-all` to verify all requirements.

## Author

Kyle Mesiab ([@kmesiab](https://github.com/kmesiab))
