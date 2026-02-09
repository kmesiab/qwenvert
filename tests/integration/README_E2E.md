# End-to-End Testing Guide

This guide covers running E2E tests that validate qwenvert works with real backends.

## Prerequisites

### Option A: Ollama Backend (Recommended)

```bash
# Install Ollama
brew install ollama

# Start Ollama server
ollama serve

# In another terminal, pull Qwen model
ollama pull qwen2.5-coder:7b
```

### Option B: llama.cpp Backend (Advanced)

```bash
# Build llama.cpp
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make

# Download Qwen GGUF model from HuggingFace
# (See qwenvert docs for model URLs)

# Start llama.cpp server
./server -m /path/to/qwen-model.gguf -c 4096 --port 8080
```

## Running E2E Tests

### Run All E2E Tests

```bash
# From qwenvert root
pytest -m e2e tests/integration/test_e2e_real_backends.py -v
```

### Run Specific Test Classes

```bash
# Ollama tests only
pytest -m e2e tests/integration/test_e2e_real_backends.py::TestOllamaE2E -v

# Error handling tests
pytest -m e2e tests/integration/test_e2e_real_backends.py::TestErrorHandling -v

# Performance tests
pytest -m e2e tests/integration/test_e2e_real_backends.py::TestPerformance -v
```

### Run Individual Tests

```bash
# Test simple Ollama request
pytest -m e2e tests/integration/test_e2e_real_backends.py::TestOllamaE2E::test_backend_router_ollama_simple_request -v

# Test streaming
pytest -m e2e tests/integration/test_e2e_real_backends.py::TestOllamaE2E::test_backend_router_ollama_streaming -v

# Test full adapter stack
pytest -m e2e tests/integration/test_e2e_real_backends.py::TestOllamaE2E::test_full_adapter_stack_ollama -v
```

## Test Coverage

### Backend Integration
- ✅ Ollama health check
- ✅ Simple request/response
- ✅ Streaming responses
- ✅ Full adapter stack (FastAPI → Router → Backend)

### Error Scenarios
- ✅ Backend not available
- ✅ Adapter without router configured
- ✅ Connection timeouts
- ✅ Malformed responses

### Performance Validation
- ✅ Response time < 10s for 50 tokens
- ✅ Throughput ≥ 5 tokens/second
- ✅ Latency tracking

### Claude Code Compatibility
- ✅ Environment variables
- ✅ API format compatibility

## Expected Behavior

### Successful Test Run

```
$ pytest -m e2e tests/integration/test_e2e_real_backends.py -v

tests/integration/test_e2e_real_backends.py::TestOllamaE2E::test_ollama_health_check
✅ Ollama available with 1 models
PASSED

tests/integration/test_e2e_real_backends.py::TestOllamaE2E::test_backend_router_ollama_simple_request
🔄 Calling Ollama backend...
✅ Response received in 2.34s
📝 Response: Hello from Ollama
PASSED

tests/integration/test_e2e_real_backends.py::TestOllamaE2E::test_backend_router_ollama_streaming
🔄 Streaming from Ollama...
Token: HelloToken: Token: fromToken: ...
✅ Received 15 events, 8 tokens
PASSED

tests/integration/test_e2e_real_backends.py::TestOllamaE2E::test_full_adapter_stack_ollama
🔄 Testing full /v1/messages endpoint...
✅ Full stack response: Hello! How can I help you today?
PASSED

tests/integration/test_e2e_real_backends.py::TestPerformance::test_response_time_acceptable
⏱️ Measuring response time...
⏱️ Response time: 2.45s
📊 Tokens generated: 42
📊 Speed: 17.1 tokens/second
✅ Performance acceptable
PASSED

========================= 5 passed in 15.23s =========================
```

### When Backend Not Available

Tests will be **skipped** automatically:

```
tests/integration/test_e2e_real_backends.py::TestOllamaE2E::test_ollama_health_check
SKIPPED (Ollama not available or qwen model not installed)
```

## Troubleshooting

### "Ollama not available"

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve

# Verify model is downloaded
ollama list | grep qwen
```

### "Model not found"

```bash
# Download Qwen model
ollama pull qwen2.5-coder:7b

# Or use a different model
export OLLAMA_MODEL=qwen2.5-coder:1.5b
```

### Slow Performance

```bash
# Check system resources
top | grep ollama

# Reduce context length
# Edit qwenvert config: context_length: 4096

# Use smaller model
ollama pull qwen2.5-coder:1.5b
```

### Connection Refused

```bash
# Check port not in use
lsof -i :11434

# Check firewall
# Ollama binds to localhost only by default

# Verify backend URL in tests
export OLLAMA_URL=http://localhost:11434
```

## CI/CD Integration

### GitHub Actions

Add to `.github/workflows/e2e-tests.yml`:

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e-ollama:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install Ollama
        run: |
          curl -fsSL https://ollama.com/install.sh | sh
          ollama serve &
          sleep 5
          ollama pull qwen2.5-coder:1.5b

      - name: Run E2E Tests
        run: |
          pip install -e .
          pytest -m e2e tests/integration/test_e2e_real_backends.py -v
```

### Local Pre-Commit Hook

Add to `.git/hooks/pre-push`:

```bash
#!/bin/bash
# Run E2E tests before pushing

if command -v ollama &> /dev/null; then
    echo "Running E2E tests..."
    pytest -m e2e tests/integration/test_e2e_real_backends.py -x

    if [ $? -ne 0 ]; then
        echo "E2E tests failed! Push aborted."
        exit 1
    fi
fi
```

## Performance Baselines

### Expected Performance (M1 Mac, 16GB)

| Metric | Qwen 7B Q4 | Qwen 14B Q5 |
|--------|------------|-------------|
| Response Time (50 tokens) | 2-3s | 4-6s |
| Tokens/Second | 18-25 | 12-18 |
| First Token Latency | <500ms | <800ms |
| Memory Usage | ~4GB | ~10GB |

### Regression Thresholds

Tests will FAIL if:
- Response time > 10s for 50 tokens
- Throughput < 5 tokens/second
- Memory usage > 150% of baseline

## Additional Resources

- [qwenvert Architecture](../../docs/ARCHITECTURE.md)
- [Testing Strategy](../README.md)
- [Ollama Documentation](https://ollama.com/docs)
- [llama.cpp Server Guide](https://github.com/ggerganov/llama.cpp/tree/master/examples/server)
