# Changelog

All notable changes to qwenvert will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Publishing infrastructure (PyPI + Homebrew)
- Automated GitHub Actions workflow for releases
- Comprehensive publishing documentation

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

[Unreleased]: https://github.com/kmesiab/qwenvert/compare/v0.2.3...HEAD
[0.2.3]: https://github.com/kmesiab/qwenvert/compare/v0.1.0...v0.2.3
[0.1.0]: https://github.com/kmesiab/qwenvert/releases/tag/v0.1.0
