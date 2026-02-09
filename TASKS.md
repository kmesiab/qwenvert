# qwenvert Implementation Tasks

**Status**: 5/7 core components complete, 2 need integration work

**Last Updated**: 2024-02-09

---

## 🔴 CRITICAL - Blocking Basic Functionality

### Task 1: Connect Adapter to Backend Router
**File**: `qwenvert/adapter.py`
**Status**: ❌ Not Started
**Priority**: P0 (Blocking)
**Estimate**: 30 minutes

**Problem**: Adapter returns placeholder responses, doesn't call backend router

**Current Code** (line 226):
```python
# TODO: Implement actual backend routing (Task #7)
# For now, return a placeholder response
```

**Requirements**:
- [ ] Import BackendRouter in adapter.py
- [ ] Initialize router with model and backend URL
- [ ] Call `router.generate(request)` in `_generate_response()`
- [ ] Transform backend response to Anthropic format
- [ ] Handle backend errors gracefully (timeouts, connection errors)
- [ ] Return proper MessagesResponse

**Acceptance Criteria**:
- ✅ Adapter successfully calls Ollama backend
- ✅ Adapter successfully calls llama.cpp backend
- ✅ Response matches Anthropic Messages API format
- ✅ Usage stats (tokens) correctly returned
- ✅ Errors properly propagated to client

**Testing**:
```bash
# Start Ollama with qwen model
ollama run qwen2.5-coder:7b

# Start qwenvert adapter
qwenvert start

# Test request
curl -X POST http://localhost:8088/v1/messages \
  -H "x-api-key: local-qwen" \
  -d '{"model":"qwenvert-default","messages":[{"role":"user","content":"Hello"}],"max_tokens":50}'
```

---

### Task 2: Implement Streaming Support
**File**: `qwenvert/adapter.py`
**Status**: ❌ Not Started
**Priority**: P0 (Blocking)
**Estimate**: 30 minutes

**Problem**: Streaming endpoint returns placeholder events, doesn't stream from backend

**Current Code** (line 271):
```python
# TODO: Implement actual streaming (Task #7)
# For now, yield placeholder events
```

**Requirements**:
- [ ] Call `router.generate_stream(request)`
- [ ] Convert backend stream to Anthropic SSE format
- [ ] Handle message_start, content_block_delta, message_delta, message_stop events
- [ ] Properly format SSE events (`data: {...}\n\n`)
- [ ] Handle streaming errors mid-stream

**Acceptance Criteria**:
- ✅ Streaming works with Ollama backend
- ✅ Streaming works with llama.cpp backend
- ✅ Events match Anthropic streaming format
- ✅ Tokens arrive in real-time (no buffering)
- ✅ Final event includes usage statistics

**Testing**:
```bash
curl -X POST http://localhost:8088/v1/messages \
  -H "x-api-key: local-qwen" \
  -d '{"model":"qwenvert-default","messages":[{"role":"user","content":"Count to 10"}],"max_tokens":50,"stream":true}'
```

---

## 🟡 HIGH PRIORITY - Core Features

### Task 3: Model Downloading from HuggingFace
**File**: New file `qwenvert/downloader.py`
**Status**: ❌ Not Started
**Priority**: P1 (Important)
**Estimate**: 1-2 hours

**Problem**: Users must manually download models, not "one-click"

**Requirements**:
- [ ] Create ModelDownloader class
- [ ] Use huggingface_hub library (already in requirements)
- [ ] Download GGUF files from HuggingFace repos
- [ ] Show progress bar during download
- [ ] Verify file integrity (checksums)
- [ ] Store models in `~/.qwenvert/models/`
- [ ] Integrate with `qwenvert init` command
- [ ] Handle resume on interrupted downloads

**Models to Support**:
- Qwen/Qwen2.5-Coder-7B-Instruct-GGUF
- Qwen/Qwen2.5-Coder-14B-Instruct-GGUF
- Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF

**Acceptance Criteria**:
- ✅ `qwenvert init` downloads model automatically if not present
- ✅ Progress bar shows download status
- ✅ Corrupted downloads are detected and re-downloaded
- ✅ Models stored in standardized location
- ✅ Ollama Modelfile references downloaded model
- ✅ llama.cpp flags reference downloaded model path

**Testing**:
```bash
# Remove existing models
rm -rf ~/.qwenvert/models/

# Run init
qwenvert init

# Should download and configure model
```

---

### Task 4: End-to-End Integration Testing
**File**: New tests in `tests/integration/`
**Status**: ❌ Not Started
**Priority**: P1 (Important)
**Estimate**: 1 hour

**Problem**: Need to verify full stack works with real backends

**Requirements**:
- [ ] Test with actual Ollama backend
- [ ] Test with actual llama.cpp backend
- [ ] Test full request flow (adapter → router → backend → response)
- [ ] Test streaming flow
- [ ] Test error scenarios (backend down, invalid model)
- [ ] Test with Claude Code environment variables

**Acceptance Criteria**:
- ✅ Ollama integration test passes with real backend
- ✅ llama.cpp integration test passes with real backend
- ✅ Streaming test produces real tokens
- ✅ Claude Code can successfully use qwenvert
- ✅ Response times acceptable (<3s for 50 tokens)

**Testing**:
```bash
# Start Ollama
ollama serve

# Run integration tests
pytest -m integration tests/integration/test_e2e_real_backends.py -v

# Test with Claude Code
export ANTHROPIC_BASE_URL=http://localhost:8088
export ANTHROPIC_API_KEY=local-qwen
export ANTHROPIC_MODEL=qwenvert-default
claude
```

---

## 🟢 MEDIUM PRIORITY - Quality of Life

### Task 5: Monitor Command (Real-time Dashboard)
**File**: `qwenvert/cli.py`, new file `qwenvert/monitoring.py`
**Status**: ❌ Not Started
**Priority**: P2 (Optional)
**Estimate**: 2-3 hours

**Problem**: No way to see real-time performance metrics

**Requirements**:
- [ ] Display live metrics (tokens/sec, latency, memory)
- [ ] Show request history
- [ ] Display thermal status (CPU temp, throttling)
- [ ] Use Rich library for TUI
- [ ] Update every 1 second
- [ ] Graceful exit on Ctrl+C

**Acceptance Criteria**:
- ✅ `qwenvert monitor` shows live metrics
- ✅ Refreshes without flicker
- ✅ Shows recent requests
- ✅ Displays thermal pressure indicator
- ✅ Clean UI with colors and formatting

---

### Task 6: Performance Benchmark Suite
**File**: New file `benchmarks/run_benchmarks.py`
**Status**: ❌ Not Started
**Priority**: P2 (Optional)
**Estimate**: 2 hours

**Problem**: No standardized performance measurements

**Requirements**:
- [ ] Benchmark inference latency (tokens/sec)
- [ ] Benchmark different context lengths
- [ ] Compare Ollama vs llama.cpp
- [ ] Test with different quantizations (Q4, Q5, Q8)
- [ ] Generate report with charts
- [ ] Store results for regression tracking

**Acceptance Criteria**:
- ✅ `make benchmark` runs full suite
- ✅ Results saved to `benchmarks/results/`
- ✅ HTML report generated with charts
- ✅ Detects performance regressions

---

## 🔵 LOW PRIORITY - Nice to Have

### Task 7: PyPI Packaging
**Files**: `setup.py`, `pyproject.toml`, `MANIFEST.in`
**Status**: ❌ Not Started
**Priority**: P3 (Enhancement)
**Estimate**: 1 hour

**Requirements**:
- [ ] Configure setuptools for PyPI
- [ ] Add package metadata (classifiers, keywords)
- [ ] Include non-Python files (models.yaml, configs)
- [ ] Test installation with `pip install -e .`
- [ ] Publish to TestPyPI first
- [ ] Publish to PyPI

**Acceptance Criteria**:
- ✅ `pip install qwenvert` works
- ✅ All dependencies installed correctly
- ✅ CLI available as `qwenvert` command
- ✅ Package shows up on PyPI

---

### Task 8: Homebrew Formula
**File**: New file `qwenvert.rb` (separate repo)
**Status**: ❌ Not Started
**Priority**: P3 (Enhancement)
**Estimate**: 1 hour

**Requirements**:
- [ ] Create Homebrew formula
- [ ] Test installation on macOS
- [ ] Submit to homebrew-core or create tap
- [ ] Add dependencies (Python, Ollama)

**Acceptance Criteria**:
- ✅ `brew install qwenvert` works
- ✅ Formula passes `brew audit`
- ✅ Auto-installs dependencies

---

## 📊 Progress Tracking

**Core Functionality**: 5/7 (71%)
- ✅ HardwareDetector
- ✅ ModelRegistry & ModelSelector
- ✅ ConfigGenerator
- ✅ ServerLauncher
- ✅ CLI
- ❌ HTTP Adapter (needs integration)
- ❌ Backend Router integration

**Testing**: 2/3 (67%)
- ✅ Unit tests
- ✅ Integration tests (mocked)
- ❌ End-to-end tests (real backends)

**Features**: 0/4 (0%)
- ❌ Model downloading
- ❌ Monitor command
- ❌ Benchmark suite
- ❌ Distribution (PyPI/Homebrew)

---

## 🎯 Recommended Order

1. **Task 1** - Connect adapter to router (30 min) ← START HERE
2. **Task 2** - Implement streaming (30 min)
3. **Task 4** - E2E testing (1 hour)
4. **Task 3** - Model downloading (1-2 hours)
5. **Task 5** - Monitor command (optional)
6. **Task 6** - Benchmarks (optional)
7. **Task 7** - PyPI packaging (optional)
8. **Task 8** - Homebrew (optional)

**Estimated time to MVP**: ~3 hours (Tasks 1-4)
**Estimated time to full feature set**: ~10 hours (all tasks)

---

## 🚀 Ready to Start?

Run:
```bash
# Create worktree for implementation
git worktree add ../qwenvert-adapter-fix feature/connect-adapter-router

# Start working on Task 1
cd ../qwenvert-adapter-fix
```

Let's ship this! 🎉
