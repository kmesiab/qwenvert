# Test Coverage Improvement Plan

## Current State
- **Total Coverage: 25.83%**
- **Target Coverage: >85%**
- **Gap: 60% improvement needed**

## Coverage by File

| File | Coverage | Statements | Missing | Priority |
|------|----------|------------|---------|----------|
| `qwenvert/__init__.py` | 100.00% ✅ | 5 | 0 | ✓ Done |
| `qwenvert/cli.py` | 0.00% ❌ | 239 | 239 | **CRITICAL** |
| `qwenvert/dashboard.py` | 0.00% ❌ | 138 | 138 | **CRITICAL** |
| `qwenvert/downloader.py` | 0.00% ❌ | 100 | 100 | **CRITICAL** |
| `qwenvert/monitoring.py` | 0.00% ❌ | 116 | 116 | **CRITICAL** |
| `qwenvert/launcher.py` | 13.16% | 186 | 156 | **HIGH** |
| `qwenvert/router.py` | 9.20% | 156 | 133 | **HIGH** |
| `qwenvert/adapter.py` | 54.86% | 112 | 46 | MEDIUM |
| `qwenvert/config.py` | 76.30% | 99 | 24 | LOW |
| `qwenvert/models.py` | 74.43% | 108 | 19 | LOW |
| `qwenvert/hardware.py` | 83.97% | 105 | 18 | LOW |

## Impact Analysis

To reach 85% coverage:
- **Need to cover**: 85% of 1364 statements = 1159 statements
- **Currently covering**: 375 statements (25.83%)
- **Must add coverage for**: 784 additional statements
- **This is**: 79% of the currently missing code

## Phased Implementation Plan

### Phase 1: CLI Testing (0% → 75%) - +180 statements
**Impact**: +13% total coverage

Create `tests/unit/test_cli_commands.py`:
- Test all CLI commands using Click's CliRunner
- Mock subprocess calls, file I/O, HTTP requests
- Test cases:
  - `qwenvert init` - model selection, config generation
  - `qwenvert start` - server launch orchestration
  - `qwenvert stop` - graceful shutdown
  - `qwenvert status` - health checks
  - `qwenvert models list` - registry queries
  - `qwenvert hardware` - detection display
  - `qwenvert monitor` - dashboard launch (mock Rich)
  - Error handling for all commands
  - Help text generation

**Estimated lines**: ~400 lines of test code

### Phase 2: Router Testing (9% → 85%) - +120 statements
**Impact**: +9% total coverage

Enhance `tests/integration/test_backend_router.py` and `tests/unit/test_router.py`:
- Fix existing test failures (certifi imports, async issues)
- Add missing test coverage:
  - Prompt template generation
  - Token counting logic
  - Streaming response handling
  - Error response formatting
  - Backend-specific transformations
  - Context length handling
  - Temperature/top_p parameter mapping
  - Stop sequences processing

**Estimated lines**: ~300 lines additional test code

### Phase 3: Launcher Testing (13% → 80%) - +125 statements
**Impact**: +9% total coverage

Create `tests/unit/test_launcher_unit.py` and fix `tests/integration/test_server_lifecycle.py`:
- Fix ProcessHandle/ServerLauncher API mismatches
- Test backend process lifecycle:
  - Ollama server start/stop
  - llama.cpp server start/stop
  - Health check retries with exponential backoff
  - Timeout handling
  - Graceful vs force shutdown
  - PID file management
  - Port availability checking
  - Process cleanup on errors

**Estimated lines**: ~350 lines of test code

### Phase 4: Downloader Testing (0% → 80%) - +80 statements
**Impact**: +6% total coverage

Create `tests/unit/test_downloader.py`:
- Mock HuggingFace API calls with responses
- Test cases:
  - Model file downloads with progress tracking
  - Resume interrupted downloads
  - Checksum verification
  - Disk space validation
  - URL generation for different models
  - Error handling (network, disk full, invalid model)
  - Parallel chunk downloads
  - Cache directory management

**Estimated lines**: ~250 lines of test code

### Phase 5: Dashboard Testing (0% → 70%) - +97 statements
**Impact**: +7% total coverage

Create `tests/unit/test_dashboard.py`:
- Mock Rich Live context and psutil
- Test cases:
  - Dashboard initialization
  - Metrics collection (CPU, memory, temp)
  - Request history tracking
  - Live table rendering
  - Keyboard interrupt handling
  - Metrics formatting (tokens/sec, req/sec)
  - System resource alerts
  - Historical data aggregation

**Estimated lines**: ~280 lines of test code

### Phase 6: Monitoring Testing (0% → 70%) - +81 statements
**Impact**: +6% total coverage

Create `tests/unit/test_monitoring.py`:
- Mock asyncio and time.time()
- Test cases:
  - RequestMonitor request tracking
  - Latency calculations
  - Token counting
  - Time-window aggregations
  - Memory leak prevention (bounded history)
  - Concurrent request tracking
  - Statistics calculation (p50, p95, p99)
  - Export metrics to JSON

**Estimated lines**: ~230 lines of test code

### Phase 7: Adapter Coverage (55% → 85%) - +34 statements
**Impact**: +2% total coverage

Enhance `tests/integration/test_messages_api.py`:
- Fix async test fixture issues
- Add missing coverage:
  - Request validation edge cases
  - Response formatting variations
  - Streaming SSE event generation
  - Multipart message handling
  - Tool use formatting (if supported)
  - Max tokens enforcement
  - Stop sequence handling
  - Error response formatting

**Estimated lines**: ~150 lines additional test code

### Phase 8: Polish Remaining Files (+53 statements)
**Impact**: +4% total coverage

**config.py (76% → 90%)** - +14 statements:
- Edge cases in ConfigManager
- File permission errors
- YAML corruption handling
- Environment variable interpolation

**models.py (74% → 90%)** - +17 statements:
- Registry edge cases
- Model filtering with complex queries
- Model compatibility matrix
- Custom model registration

**hardware.py (84% → 95%)** - +11 statements:
- Unusual hardware configurations
- Fallback detection paths
- Error handling in sysctl calls

**Estimated lines**: ~120 lines of test code

## Summary

| Phase | Target File | Coverage Gain | New Tests |
|-------|------------|---------------|-----------|
| 1 | cli.py | +13% | ~400 lines |
| 2 | router.py | +9% | ~300 lines |
| 3 | launcher.py | +9% | ~350 lines |
| 4 | downloader.py | +6% | ~250 lines |
| 5 | dashboard.py | +7% | ~280 lines |
| 6 | monitoring.py | +6% | ~230 lines |
| 7 | adapter.py | +2% | ~150 lines |
| 8 | config/models/hardware | +4% | ~120 lines |
| **TOTAL** | **All** | **56%** | **~2,080 lines** |

**Final Expected Coverage**: 25.83% + 56% = **81.83%**

To exceed 85%, we'll need to add ~60 more statements of coverage (extra 3%), which can be achieved by:
- Increasing CLI testing to 80% instead of 75%
- Adding more edge cases to Phase 8 files
- Improving router and launcher coverage to 90%

## Implementation Order

1. **Phase 1 (CLI)** - Biggest impact, clear test patterns
2. **Phase 2 (Router)** - Fix existing broken tests first
3. **Phase 3 (Launcher)** - Critical for integration tests
4. **Phases 4-6 in parallel** - Independent components
5. **Phase 7 (Adapter)** - Build on router fixes
6. **Phase 8 (Polish)** - Final push to exceed 85%

## Test Failures to Fix First

Before adding new tests, fix these critical issues:

1. **Missing certifi dependency** - Add to dev dependencies
2. **Async test fixture issues** - Update pytest-asyncio usage
3. **ProcessHandle/ServerLauncher API** - Update test code to match implementation
4. **Import errors** - Fix missing `_check_backend_health` export
5. **AsyncClient API** - Update to match current httpx version

## Next Steps

1. Install missing test dependencies:
   ```bash
   pip install certifi pytest-httpx
   ```

2. Fix existing test failures (estimate: 2-3 hours)

3. Start Phase 1: CLI testing (estimate: 4-5 hours)

4. Continue through phases sequentially

5. Target completion: All phases in 2-3 days of work

## Estimated Effort

- **Test code to write**: ~2,080 lines
- **Existing tests to fix**: ~500 lines
- **Total effort**: 16-20 hours of focused development
- **Coverage target**: **85-90%**
