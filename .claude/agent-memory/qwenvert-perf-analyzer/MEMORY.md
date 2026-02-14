# Qwenvert Performance Analyzer Memory

## Active Critical Issues

See `CRITICAL-ISSUE-M1-8GB-2026-02-13.md` for details on 6m+ latency bug affecting M1 8GB users.

## Hardware-Specific Performance Baselines

### M1 8GB (MacBook Air - Fanless)
- **CRITICAL**: 7B models cause severe swapping (6+ min latency)
- **Recommended**: 1.5B Q4 (30-40 tok/s, 1-2s for simple queries)
- **Alternative**: 3B Q4 (25-35 tok/s, better quality)
- **Memory overhead**: OS uses ~2-3 GB, leaving ~5 GB for apps
- **Thermal**: Fanless design throttles under sustained load
- **Config**: thermal_pacing: true automatically applied

### M1 16GB (MacBook Pro - Active Cooling)
- **Optimal**: 7B Q5 (28-35 tok/s)
- **Max**: 14B Q4 (18-25 tok/s)
- **Memory overhead**: OS ~3 GB, ~13 GB available

### M1 Pro/Max 32GB+
- **Optimal**: 14B Q5 (22-30 tok/s)
- **Max**: 32B Q4 (12-18 tok/s)

## Model Selection Algorithm Issues

### Bug in models.py:415-422
```python
# BROKEN: Selects smallest Q4_K_M but ignores absolute size
if hardware.is_memory_constrained():
    candidates = [m for m in compatible if m.quantization == "Q4_K_M"]
    if candidates:
        return min(candidates, key=lambda m: m.size_b)  # Ascending sort!
```

**Issue**: On 8GB systems with models [1.5B Q4, 3B Q4, 7B Q4], this selects 7B Q4 (largest).
**Fix**: Should sort by size first, quantization second.

### Model Registry min_ram_gb Misleading

`min_ram_gb: 8` for 7B Q4 is technically correct (model CAN load) but ignores:
- OS overhead (2-3 GB)
- Other apps (1-2 GB)
- Working memory for inference (1-2 GB)
- ACTUAL requirement for usable performance: 12+ GB

## Performance Bottlenecks by Symptom

### 6+ Minute Latency (CRITICAL)
- **Cause**: Swapping to disk (memory exhaustion)
- **Detection**: vm_stat shows <0.5 GB free, high page faults
- **Fix**: Use smaller model or close apps
- **Affected**: M1 8GB with 7B+ models

### Thermal Throttling (Fanless Macs)
- **Cause**: Sustained high CPU/GPU load on MacBook Air
- **Detection**: CPU frequency drops, elevated temps
- **Mitigation**: thermal_pacing in config (not yet implemented)
- **Impact**: 15-30% throughput reduction under load

### Slow First Token (Model Load Delay)
- **Cause**: Model not loaded in Ollama, needs pull/load
- **Detection**: First request slow, subsequent fast
- **Fix**: Ensure model pre-loaded with `ollama run <model>`

## Memory Analysis Commands

```bash
# Check memory pressure
vm_stat | head -10

# Calculate available memory (macOS)
python3 << 'EOF'
import subprocess
vm_stat = subprocess.check_output(['vm_stat']).decode()
lines = vm_stat.split('\n')
page_size = 16384  # M1 uses 16KB pages
free = int([l for l in lines if 'free' in l][0].split()[2].rstrip('.'))
inactive = int([l for l in lines if 'inactive' in l][0].split()[2].rstrip('.'))
free_gb = (free * page_size) / (1024**3)
inactive_gb = (inactive * page_size) / (1024**3)
print(f"Free: {free_gb:.2f} GB")
print(f"Available (free+inactive): {(free_gb+inactive_gb):.2f} GB")
EOF

# Check Ollama memory usage
ps aux | grep [o]llama | awk '{print $2, $4, $6}'  # PID, %MEM, RSS
```

## Configuration Paths

- User config: `~/.config/qwenvert/config.yaml`
- Model registry: `/Users/kmesiab/go/github.com/kmesiab/qwenvert/configs/models.yaml`
- Model selection: `/Users/kmesiab/go/github.com/kmesiab/qwenvert/qwenvert/models.py:372-458`
- Hardware detection: `/Users/kmesiab/go/github.com/kmesiab/qwenvert/qwenvert/hardware.py:106-150`

## Quick Fixes by Symptom

### User reports "extremely slow" (6+ min)
1. Check memory: `vm_stat | head -10`
2. If free <0.5 GB → Swapping issue
3. Fix: `qwenvert init --model qwen2.5-coder-1.5b-q4-ollama`

### User reports "model not found"
1. Check: `ollama list | grep qwen`
2. If missing → Model not pulled
3. Fix: Check config.yaml backend_model_id, ensure it matches

### User reports "port already in use"
1. Check: `lsof -ti:8088` (adapter) or `lsof -ti:11434` (ollama)
2. Fix: `qwenvert stop` or kill process
