# Qwenvert Performance Benchmarks

Comprehensive benchmark suite for measuring qwenvert performance across different configurations.

## Quick Start

```bash
# Start qwenvert
qwenvert start

# Run benchmarks
python benchmarks/run_benchmarks.py

# Or use make
make benchmark
```

## What It Tests

### Prompt Variations
- **Short prompts** (4 tokens): "What is 2+2?"
- **Medium prompts** (~15 tokens): Code explanations
- **Long prompts** (~50 tokens): Complex code generation tasks
- **Code generation**: FastAPI endpoint creation

### Response Sizes
- 50 tokens
- 100 tokens (default)
- 200 tokens

### Streaming
- Non-streaming (batch) responses
- Streaming responses with Time-To-First-Token (TTFT) metrics

## Metrics Collected

**Latency:**
- Total request latency (ms)
- Time to first token (TTFT) for streaming
- Time per token (ms/token)

**Throughput:**
- Tokens generated per request
- Tokens per second (t/s)

**Resource Usage:** (future)
- Peak memory usage
- Average CPU utilization

## Output

### Terminal Output

```
Qwenvert Performance Benchmark Suite

Checking adapter health...
✓ Adapter running

Running: prompt_short
  ✓ 1234ms | 5 tokens | 4.1 t/s
Running: prompt_medium
  ✓ 2456ms | 89 tokens | 36.2 t/s
...

Benchmark Results Summary

┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ Benchmark          ┃ Backend ┃ Quant┃ Latency ┃ Tokens┃ Speed  ┃ Status ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ prompt_short       │ ollama  │ Q4_K │ 1234ms  │ 5     │ 4.1 t/s│   ✓    │
│ prompt_medium      │ ollama  │ Q4_K │ 2456ms  │ 89    │ 36.2t/s│   ✓    │
└────────────────────┴─────────┴──────┴─────────┴───────┴────────┴────────┘

Summary:
  Total benchmarks: 8
  Successful: 8 (100.0%)
  Average latency: 1845ms
  Average throughput: 32.4 tokens/sec

✓ Benchmark suite complete!
```

### JSON Results

Results are saved to `benchmarks/results/benchmark_results_TIMESTAMP.json`:

```json
[
  {
    "name": "prompt_short",
    "backend": "ollama",
    "model": "qwen2.5-coder",
    "quantization": "Q4_K_M",
    "context_length": 32768,
    "prompt_tokens": 4,
    "max_tokens": 100,
    "streaming": false,
    "success": true,
    "error": null,
    "latency_ms": 1234.5,
    "first_token_ms": null,
    "time_per_token_ms": 246.9,
    "tokens_generated": 5,
    "tokens_per_second": 4.05,
    "peak_memory_mb": null,
    "avg_cpu_percent": null,
    "timestamp": "2026-02-09T23:45:12.123456Z"
  }
]
```

## Custom Benchmarks

Create custom benchmark configs:

```python
from benchmarks.run_benchmarks import BenchmarkConfig, BenchmarkRunner
import asyncio

custom_benchmarks = [
    BenchmarkConfig(
        name="my_test",
        backend="ollama",
        model="qwen2.5-coder",
        quantization="Q4_K_M",
        context_length=32768,
        prompt="Your custom prompt here",
        max_tokens=200,
        streaming=True,
    ),
]

async def main():
    runner = BenchmarkRunner()
    results = await runner.run_suite(custom_benchmarks)
    runner.print_summary()
    runner.save_results()

asyncio.run(main())
```

## Performance Targets

**Expected performance** (M1 Pro, 16GB RAM, Q4 quantization):
- Short prompts (4 tokens): 1-2s total, 20-30 t/s
- Medium prompts (15 tokens): 2-4s total, 25-35 t/s
- Long prompts (50 tokens): 4-8s total, 20-30 t/s
- Streaming TTFT: 100-500ms

**Factors affecting performance:**
- Mac model (M1/M2/M3, RAM, cooling)
- Model quantization (Q4 vs Q5 vs Q8)
- Context length (larger = more memory = slower)
- Other apps running (memory pressure)
- Thermal throttling (especially MacBook Air)

## Regression Tracking

Compare benchmarks over time:

```bash
# Run and save baseline
python benchmarks/run_benchmarks.py
# Saved: benchmark_results_20260209_154523.json

# After changes, run again
python benchmarks/run_benchmarks.py
# Saved: benchmark_results_20260209_160134.json

# Compare (manual for now)
diff benchmarks/results/*.json
```

## Troubleshooting

### "Adapter not running"
```bash
# Start qwenvert first
qwenvert start

# Verify it's running
curl http://localhost:8088/health
```

### Slow performance
- Check memory pressure: `qwenvert monitor`
- Close other apps
- Use smaller model (Q4 instead of Q5)
- Reduce context length

### Benchmarks fail
- Check adapter logs
- Verify model is loaded: `qwenvert status`
- Increase timeout (120s default should be plenty)

## Future Enhancements

- [ ] HTML reports with charts (matplotlib/plotly)
- [ ] Comparison between backends (Ollama vs llama.cpp)
- [ ] Different quantizations (Q4 vs Q5 vs Q8)
- [ ] Resource usage tracking (memory, CPU)
- [ ] Automated regression detection
- [ ] CI integration (benchmark on every PR)
- [ ] Historical trend charts
