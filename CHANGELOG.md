# Changelog

All notable changes to qwenvert will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Publishing infrastructure (PyPI + Homebrew)
- Automated GitHub Actions workflow for releases
- Comprehensive publishing documentation

## [0.2.6] - 2026-02-13

### Added
- Dependency auto-installation via Homebrew - PR #50
  - `--auto-install` flag for `qwenvert start` command
  - Interactive and non-interactive installation modes
  - Whitelist validation for allowed dependencies (ollama, llama.cpp)
  - 5-minute timeout and shell injection protection
- Request-id tracing for API compatibility - PR #58
  - Anthropic-compatible `request-id` and `x-request-id` headers
  - Unique request identifiers for end-to-end tracing
  - Improves Claude Code CLI compatibility

### Fixed
- Suppressed noisy health check endpoint logs - PR #56
  - Filters `/health` requests from uvicorn access logs
  - Reduces log noise during normal operation
- Enhanced dependency error handling - PR #50
  - Clean, formatted error messages without Python tracebacks
  - Interactive prompts for dependency installation

## [0.2.5] - 2026-02-13

### Fixed
- Display actual version in CLI and startup message - PR #54
  - `qwenvert --version` now shows correct version instead of hardcoded "0.1.0"
  - Version displayed in startup message
  - Dynamic version used in telemetry
- Clean error message when port is already in use - PR #53
  - Socket-based port availability check before server bind
  - User-friendly error message with 3 solutions for port conflicts
  - Replaces ugly uvicorn traceback with helpful guidance

## [0.2.4] - 2026-02-13

### Added
- Model-aware context window management - PR #51
  - Per-model `max_output_tokens` limits (8K-16K based on model size)
  - Dynamic token capping based on active model
  - Comprehensive test suite with edge cases

### Fixed
- Claude Code compatibility improvements - PR #51
  - System field normalization (accepts both string and array formats)
  - Handles `cache_control` objects in system prompts
  - Prevents 422 errors for oversized `max_tokens` requests
  - Caps requests to model-appropriate limits with warning logs

## [0.2.3] - 2026-02-11

### Added
- Model cleanup command (`qwenvert models clean`) for removing downloaded models
  - Interactive selection with numbered menu
  - Delete specific models by filename (`--model-id` flag)
  - Delete all models with confirmation (`--all` flag)
  - Dry-run preview mode (`--dry-run` flag)
  - Disk usage statistics before/after cleanup

### Fixed
- Model selection now prioritizes already-downloaded models, preventing unnecessary re-downloads
  - `qwenvert init` checks for compatible downloaded models before selecting new ones
  - Saves bandwidth and setup time for users with models already downloaded
  - Particularly helpful for users with smaller models (1.5B, 3B) already on disk
- One-click workflow now uses local GGUF files instead of downloading from registry
  - Ollama Modelfile generated with local file path instead of model name
  - Prevents redundant downloads when local model exists

### Security
- Added Modelfile injection attack prevention
  - Validates model_path to reject newlines, control characters, and directive injection
  - 14 comprehensive security tests for path validation

## [0.1.0] - 2026-02-10

### Added
- Initial alpha release
- Anthropic API adapter for local LLMs
- Support for Ollama backend
- Support for llama.cpp backend
- Hardware detection for Apple Silicon (M1/M2/M3)
- Model registry with Qwen2.5-Coder models
- Thermal monitoring and pacing for fanless Macs
- CLI with commands: init, start, status, hardware, models
- 93 security tests validating localhost-only operation
- OpenTelemetry integration for observability
- Dashboard for monitoring adapter performance
- Python 3.9-3.12 compatibility

### Security
- All network operations restricted to localhost/127.0.0.1
- URL validation prevents external network calls
- No data exfiltration - code and prompts stay local
- Comprehensive security test suite (93 tests)

### Documentation
- README with installation and usage instructions
- Architecture documentation
- API documentation
- Contributing guidelines
- Security policy

---

## Release Template

Copy this for new releases:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes to existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security improvements
```

---

[Unreleased]: https://github.com/kmesiab/qwenvert/compare/v0.2.6...HEAD
[0.2.6]: https://github.com/kmesiab/qwenvert/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/kmesiab/qwenvert/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/kmesiab/qwenvert/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/kmesiab/qwenvert/compare/v0.1.0...v0.2.3
[0.1.0]: https://github.com/kmesiab/qwenvert/releases/tag/v0.1.0
