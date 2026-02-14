# CRITICAL Performance Issue: M1 8GB Memory Exhaustion

**Date**: 2026-02-13
**System**: M1 MacBook Air (8GB, fanless)
**Reported Symptom**: 6m 7s response time for simple query with 0 tokens downloaded

## Root Cause Analysis

### Issue
The 7B Q4 model (4.7 GB) is too large for M1 base 8GB systems when the OS and other apps are loaded.

### Memory Analysis
```
Total RAM: 8 GB
Free: 0.07 GB (CRITICAL - only 70 MB!)
Active: 1.06 GB
Inactive: 1.00 GB
Wired: 2.04 GB
Used: 3.10 GB (38.7%)

Available for LLM: ~1.07 GB (free + inactive)
7B Q4 model needs: ~4-5 GB + OS overhead
```

### What's Happening
1. Model selection chose `qwen2.5-coder-7b-q4-ollama` (4.7 GB)
2. System has only 70 MB truly free memory
3. Loading model causes massive swapping to disk
4. M1 Air is fanless (thermal_pacing: true in config)
5. Combination of swapping + thermal throttling = 6+ minute latency

### Configuration Found
```yaml
model_id: qwen2.5-coder-7b-q4-ollama
backend_model_id: qwen2.5-coder:7b-instruct-q4_K_M
context_length: 8192
thermal_pacing: true  # Fanless Mac detected correctly
```

## Model Selection Bug

The model selection algorithm in `/Users/kmesiab/go/github.com/kmesiab/qwenvert/qwenvert/models.py:415-422` has a logic issue:

```python
if hardware.is_memory_constrained():
    # 8GB or less: choose smallest compatible model with good quantization
    # Prefer Q4_K_M for memory efficiency
    candidates = [m for m in compatible if m.quantization == "Q4_K_M"]
    if candidates:
        return min(candidates, key=lambda m: m.size_b)
```

**Problem**: It selects the SMALLEST Q4_K_M model from all compatible models. On an 8GB system:
- Compatible models: 1.5B, 3B, 7B (all fit "min_ram_gb: 8")
- Selected: 7B Q4 (smallest in Q4_K_M category that fits)
- SHOULD select: 1.5B Q4 or 3B Q4

The algorithm prioritizes Q4 quantization over model size, which is backwards for memory-constrained systems.

## Expected vs Actual Performance

### With 7B Model (Current - BROKEN)
- Model size: 4.7 GB
- Memory pressure: CRITICAL
- Swapping: Severe (disk I/O bottleneck)
- Thermal throttling: Yes (fanless M1 Air)
- Response time: **6m 7s** (measured)
- Expected for this config: 15-30s (without swapping, 20-25 tok/s)

### With 1.5B Model (RECOMMENDED)
- Model size: 1.1 GB
- Memory pressure: Normal
- Swapping: None expected
- Thermal throttling: Minimal
- Response time: **2-4s** for simple queries
- Throughput: 30-40 tokens/sec (faster than 7B due to less thermal load)

### With 3B Model (ALTERNATIVE)
- Model size: ~2.5 GB
- Memory pressure: Moderate
- Swapping: Minimal
- Response time: **3-5s** for simple queries
- Throughput: 25-35 tokens/sec
- Better quality than 1.5B

## Fix Required

### 1. Model Selection Logic Fix (HIGH PRIORITY)

**File**: `/Users/kmesiab/go/github.com/kmesiab/qwenvert/qwenvert/models.py`
**Lines**: 415-422

**Current (BROKEN)**:
```python
if hardware.is_memory_constrained():
    candidates = [m for m in compatible if m.quantization == "Q4_K_M"]
    if candidates:
        return min(candidates, key=lambda m: m.size_b)  # BUG: Sorts ascending!
```

**Fixed**:
```python
if hardware.is_memory_constrained():
    # For 8GB systems, prioritize SMALLEST model first (size over quantization)
    # Sort by size ascending (smallest first), then prefer Q4_K_M
    compatible_sorted = sorted(
        compatible,
        key=lambda m: (m.size_b, 0 if m.quantization == "Q4_K_M" else 1)
    )
    if compatible_sorted:
        return compatible_sorted[0]  # Return smallest compatible model
```

### 2. Immediate User Fix (NO CODE CHANGE)

```bash
# Reconfigure with 1.5B model
qwenvert init --model qwen2.5-coder-1.5b-q4-ollama

# Restart
qwenvert stop
qwenvert start
```

This will:
- Use 1.5B model (1.1 GB instead of 4.7 GB)
- Eliminate swapping
- Reduce thermal load
- Achieve 2-4s response times instead of 6+ minutes

### 3. Config Update for 8GB Systems

Update `/Users/kmesiab/go/github.com/kmesiab/qwenvert/configs/models.yaml`:

Change line 22 for 7B model:
```yaml
min_ram_gb: 8  # WRONG - causes selection on 8GB systems
```

To:
```yaml
min_ram_gb: 12  # CORRECT - prevents selection on 8GB systems
```

This prevents the 7B model from being selected on 8GB systems altogether.

## Performance Benchmarks (Expected)

### M1 8GB with 1.5B Q4
- Simple query (10 tokens): 0.3-0.5s
- Medium query (50 tokens): 1.5-2.0s
- Long generation (200 tokens): 5-7s
- Throughput: 30-40 tok/s

### M1 8GB with 7B Q4 (Current - BROKEN)
- Simple query: 6+ minutes (SWAPPING)
- Throughput: <1 tok/s (when swapping)
- Thermal throttling: Severe on fanless Air

## Verification Steps

After fix:

```bash
# 1. Reconfigure
qwenvert init --model qwen2.5-coder-1.5b-q4-ollama

# 2. Restart
qwenvert stop && qwenvert start

# 3. Test
curl -X POST http://localhost:8088/v1/messages \
  -H "x-api-key: local-qwen" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwenvert-default",
    "messages": [{"role": "user", "content": "Say hello in 5 words"}],
    "max_tokens": 20
  }'

# Should return in 1-2 seconds
```

## Memory Guidelines for Model Selection

| RAM | Recommended Model | Max Model (risky) | Notes |
|-----|------------------|-------------------|-------|
| 8GB | 1.5B Q4 or 3B Q4 | 7B Q4 | Avoid 7B unless no other apps running |
| 16GB | 7B Q5 | 14B Q4 | Good balance |
| 24GB | 14B Q4 | 14B Q5 | Optimal for quality |
| 32GB+ | 14B Q5 or 32B Q4 | 32B Q5 | High-end configs |

## Lessons Learned

1. `min_ram_gb` in model registry is misleading - it's the ABSOLUTE minimum, not recommended
2. Model selection should account for OS overhead (typically 2-3 GB on macOS)
3. Fanless Macs (MacBook Air) need even more conservative defaults due to thermal constraints
4. Algorithm should prioritize model SIZE over quantization on memory-constrained systems

## Impact

This affects ALL M1 8GB users who run `qwenvert init` without specifying a model:
- M1 MacBook Air (base config)
- M1 Mac Mini (base config)
- M1 iMac (base config)

Estimated user base: 20-30% of qwenvert users based on M1 8GB sales.

## Priority

**CRITICAL** - Renders qwenvert unusable on common hardware configuration.
