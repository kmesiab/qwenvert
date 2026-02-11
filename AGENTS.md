# Qwenvert Agent Guide

Privacy-focused HTTP adapter for Claude Code → local Qwen models. **All inference is localhost-only.**

## Critical Security Rules

**security.py is the most important file** - validates all URLs/hosts are localhost-only:
- Uses `urllib.parse.urlparse()` to prevent subdomain/query bypasses
- `validate_localhost_url(url)` - Required before ANY HTTP call
- `validate_adapter_host(host)` - Blocks 0.0.0.0 binding

**Before modifying security.py, router.py, launcher.py, adapter.py, telemetry.py:**
1. Run `pytest tests/security/ -v` (92 tests must pass)
2. Use qwenvert-security-auditor agent for review
3. Never use substring matching for URLs - always use urllib.parse

## File Modification Rules

| File | Requirements |
|------|-------------|
| security.py | Security review + all 92 security tests pass |
| router.py, launcher.py, adapter.py | Security tests + unit tests |
| config.py | Config validation tests (validates on load) |
| telemetry.py, monitoring.py | Security review (can leak data) |

## Specialized Agents

**qwenvert-security-auditor** (Sonnet) - Use after ANY network/config/telemetry change
**qwenvert-reviewer** (Sonnet) - Use before PRs, after implementations
**qwenvert-perf-analyzer** (Sonnet) - Performance/memory/thermal analysis
**test-runner** (Haiku) - Run tests after code changes
**code-simplifier** (Sonnet) - Simplify complex code
**doc-maintainer** (Sonnet) - Update docs after feature changes
**worktree-coordinator** (Sonnet) - Parallel development with worktrees

## Key Files

1. `qwenvert/security.py` - Localhost validation (100% coverage)
2. `tests/security/` - 92 security tests
3. `qwenvert/router.py` - Backend routing (validates backend_url)
4. `qwenvert/launcher.py` - Server lifecycle (validates adapter_host)
5. `qwenvert/config.py` - Config management (validates on load)

## Critical Gotchas

1. Always validate URLs with `validate_localhost_url()` before HTTP calls
2. Never bind to 0.0.0.0 (only 127.0.0.1, localhost, ::1)
3. Never commit if security tests fail
4. Never use substring matching for URL validation
5. Never skip security-auditor for network/config changes

## Testing Hierarchy

```bash
pytest tests/security/ -v    # MUST pass (no exceptions)
pytest tests/unit/ -v        # Should pass
pytest tests/integration/ -v # Optional (needs backends)
```

## Code Style

- Python 3.9-3.12, type hints required
- Format: `black qwenvert/ tests/`
- Lint: `ruff check qwenvert/ tests/`
- Commit prefix: `Security:`, `Fix:`, `Add:`, `Test:`
