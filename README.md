# Qwenvert

**Run Claude Code with a local LLM on your Mac. Keep your code private.**

[![PyPI version](https://badge.fury.io/py/qwenvert.svg)](https://badge.fury.io/py/qwenvert)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/downloads/)

Qwenvert lets you use Claude Code CLI with a completely local LLM (Qwen2.5-Coder) instead of Anthropic's API. Your code never leaves your machine.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Claude Code │ --> │   Qwenvert   │ --> │ Local Qwen  │
│     CLI     │     │   (adapter)  │     │    Model    │
└─────────────┘     └──────────────┘     └─────────────┘
                         :8088              (via Ollama)
```

**Why?** Privacy. Security. Compliance. Zero inference costs. No internet required.

---

## ⚡ 5-Minute Quick Start

### 1. Install

**Requirements:**
- Mac with M1/M2/M3 chip (8GB RAM minimum)
- Python 3.9-3.12 (check: `python3 --version`)
- [Ollama](https://ollama.ai) or llama.cpp

**Install from PyPI:**
```bash
pip install qwenvert
```

**Or with Homebrew (coming soon):**

> Homebrew formula is not published yet. See [PUBLISHING.md](./PUBLISHING.md#homebrew) for instructions on creating a Homebrew tap.

**Or install from source:**
```bash
git clone https://github.com/kmesiab/qwenvert.git
cd qwenvert
pip install -e .
```

### 2. Setup (One Command)

```bash
qwenvert init
```

This will:
- ✅ Detect your hardware (chip, RAM, cooling)
- ✅ Pick the best model for your Mac
- ✅ Download the model from HuggingFace (~4GB)
- ✅ Configure everything automatically

**Example output:**
```
Qwenvert Initialization

✓ Detected: M1 Pro, 16GB RAM, 16 GPU cores, Active cooling
✓ Selected: Qwen2.5 Coder 7B Q5
✓ Downloading from HuggingFace...
✓ Model downloaded: ~/.qwenvert/models/qwen25-coder-7b-q5.gguf (4.2GB)
✓ Configuration saved: ~/.config/qwenvert/config.yaml

Next step: qwenvert start
```

### 3. Start Qwenvert

```bash
qwenvert start
```

**You'll see:**
```
Starting Qwenvert

✓ Backend: Ollama with qwen2.5-coder:7b
✓ Backend server: http://localhost:11434 (healthy)
✓ Qwenvert adapter: http://localhost:8088
✓ Ready for Claude Code!

Configure Claude Code:
  export ANTHROPIC_BASE_URL=http://localhost:8088
  export ANTHROPIC_API_KEY=local-qwen
  export ANTHROPIC_MODEL=qwenvert-default
```

Leave this terminal running.

### 4. Configure Claude Code (New Terminal)

```bash
export ANTHROPIC_BASE_URL=http://localhost:8088
export ANTHROPIC_API_KEY=local-qwen
export ANTHROPIC_MODEL=qwenvert-default

claude
```

**That's it!** Claude Code now uses your local model. Your code stays on your machine.

### What Just Happened?

**Without qwenvert (default):**
```
Claude Code → api.anthropic.com → Claude Sonnet/Opus
              (internet)           (cloud)
              💰 Costs money      ☁️ Code leaves machine
```

**With qwenvert (configured):**
```
Claude Code → localhost:8088 → Ollama → Qwen Model
              (no internet)     (local)  (your Mac)
              💰 Free            🔒 Code stays local
```

Claude Code doesn't know the difference - it just uses whatever `ANTHROPIC_BASE_URL` points to!

---

## 📖 How to Use

### Basic Workflow

```bash
# Start qwenvert (terminal 1)
qwenvert start

# Use Claude Code (terminal 2)
export ANTHROPIC_BASE_URL=http://localhost:8088
export ANTHROPIC_API_KEY=local-qwen
export ANTHROPIC_MODEL=qwenvert-default
claude

# When done, stop qwenvert
qwenvert stop
```

### Make Environment Variables Permanent

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
# Qwenvert - Local Claude Code
export ANTHROPIC_BASE_URL=http://localhost:8088
export ANTHROPIC_API_KEY=local-qwen
export ANTHROPIC_MODEL=qwenvert-default
```

Then reload: `source ~/.zshrc`

Now `claude` will automatically use qwenvert!

### Verify Claude Code is Using Qwenvert

After setting environment variables, verify the setup:

```bash
# Check environment variables are set
echo $ANTHROPIC_BASE_URL
# Should show: http://localhost:8088

echo $ANTHROPIC_API_KEY
# Should show: local-qwen

echo $ANTHROPIC_MODEL
# Should show: qwenvert-default

# Make sure qwenvert is running
curl http://localhost:8088/health
# Should return: {"status":"healthy","backend":"connected"}

# Test with Claude Code
claude
# In Claude Code, ask: "What model are you?"
# It should respond as Qwen2.5-Coder (though it might say Claude)
```

**How to tell it's working:**
- ✅ Claude Code starts without asking for an API key
- ✅ Responses come quickly (no network delay)
- ✅ `qwenvert monitor` shows requests appearing
- ✅ Works offline (disconnect wifi and try)

**If it's NOT working:**
- ❌ "Invalid API key" error → Check `ANTHROPIC_API_KEY=local-qwen`
- ❌ "Connection refused" → Check `ANTHROPIC_BASE_URL` and qwenvert is running
- ❌ "Model not found" → Check `ANTHROPIC_MODEL=qwenvert-default`

---

## 🎯 Common Commands

### Check Status

```bash
qwenvert status
```

**Output:**
```
Qwenvert Status

Configuration
  Model:              qwen2.5-coder-7b-q5
  Backend:            ollama
  Backend URL:        http://localhost:11434
  Adapter:            http://localhost:8088
  Context Length:     32,768 tokens

Server Health:
  Backend:  ✓ Running
  Adapter:  ✓ Running
```

### Monitor Performance (Optional)

```bash
qwenvert monitor
```

Shows a live dashboard with:
- Requests per second
- Token generation speed
- System resources (CPU, memory, temp)
- Recent request history

**OpenTelemetry Support**: The monitor now uses OpenTelemetry-compliant metrics. Enable OTLP export for integration with observability platforms:

```bash
# Enable with local OTLP collector (secure)
export OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317
qwenvert monitor --enable-otel
```

See [TELEMETRY_SECURITY.md](./TELEMETRY_SECURITY.md) for complete security details.

Press `Ctrl+C` to exit.

### List Available Models

```bash
qwenvert models list
```

**Output:**
```
Available Models

ID                           Size    RAM    Context
qwen2.5-coder-7b-q4          4.1GB   8GB    32K
qwen2.5-coder-7b-q5          4.8GB   16GB   32K
qwen2.5-coder-14b-q4         8.5GB   16GB   32K
qwen2.5-coder-14b-q5         10GB    32GB   32K
```

### Check Your Hardware

```bash
qwenvert hardware
```

**Output:**
```
Hardware Information

Chip:               M1 Pro
Total Memory:       16GB
GPU Cores:          16
Performance Cores:  8
Cooling:            Active (fan)
Recommended:        32K tokens context
```

---

## 🔧 Advanced Usage

### Use a Specific Model

```bash
# List models
qwenvert models list

# Re-initialize with different model
qwenvert init --model qwen2.5-coder-14b-q5

# Restart
qwenvert stop
qwenvert start
```

### Use llama.cpp Instead of Ollama

```bash
# Initialize with llama.cpp backend
qwenvert init --backend llamacpp

# Start (same command)
qwenvert start
```

**Why llama.cpp?**
- More control over inference parameters
- Slightly faster on some Macs
- Lower memory overhead

**Why Ollama?** (default)
- Easier to install
- Better model management
- More beginner-friendly

### Custom Context Length

```bash
# Longer context = more memory
qwenvert init --context-length 65536  # 64K tokens

# Shorter context = less memory
qwenvert init --context-length 16384  # 16K tokens
```

**Rule of thumb:**
- 8GB Mac: 16K max
- 16GB Mac: 32K safe
- 32GB+ Mac: 64K works

---

## ❓ Troubleshooting

### "Connection refused" when starting Claude Code

**Check if qwenvert is running:**
```bash
curl http://localhost:8088/health
```

**Should return:**
```json
{"status": "healthy", "backend": "connected"}
```

**If not running:**
```bash
qwenvert start
```

---

### Model download fails

**Problem:** HuggingFace download interrupted

**Solution:**
```bash
# Try again (downloads resume automatically)
qwenvert init

# Or download manually and place in ~/.qwenvert/models/
```

---

### Slow response times

**Check memory usage:**
```bash
qwenvert status
```

**Solutions:**
1. **Use smaller model:**
   ```bash
   qwenvert init --model qwen2.5-coder-7b-q4
   ```

2. **Reduce context length:**
   ```bash
   qwenvert init --context-length 16384
   ```

3. **Close other apps** to free RAM

**Expected speeds:**
- 8GB Mac: 15-20 tokens/sec
- 16GB Mac: 25-35 tokens/sec
- 32GB+ Mac: 30-40 tokens/sec

---

### MacBook Air overheating

**Enable thermal pacing:**

Edit `~/.config/qwenvert/config.yaml`:
```yaml
thermal_pacing: true
thermal_threshold: 70  # Celsius
```

Or re-run init with thermal protection:
```bash
qwenvert init --thermal-pacing
```

---

### Can't install - Python version error

**Problem:** Python 3.13 not supported yet

**Solution:** Use Python 3.12 or earlier
```bash
# Check version
python3 --version

# Install Python 3.12 via Homebrew
brew install python@3.12

# Use it
pip3.12 install -e .
```

---

### Environment variables not persisting

**Problem:** Variables reset when you close terminal

**Solution:** Add to shell config

```bash
# Open your shell config
nano ~/.zshrc  # or ~/.bashrc for bash

# Add these lines
export ANTHROPIC_BASE_URL=http://localhost:8088
export ANTHROPIC_API_KEY=local-qwen
export ANTHROPIC_MODEL=qwenvert-default

# Save and reload
source ~/.zshrc
```

---

## 🔒 Privacy & Security

### What Data Stays Local?

**Everything.** Qwenvert is designed for security-conscious developers.

✅ **Your code** - Never sent to any server
✅ **Prompts** - Processed only on your Mac
✅ **Responses** - Generated locally
✅ **Model weights** - Stored in `~/.qwenvert/models/`

### How We Guarantee This

1. **Localhost-only binding** - Adapter listens on `127.0.0.1` only (not accessible from network)
2. **No external calls** - Code explicitly blocks external connections
3. **Telemetry security** - All telemetry exporters disabled by default; OTLP endpoints validated to be localhost-only (see [TELEMETRY_SECURITY.md](./TELEMETRY_SECURITY.md))
4. **Test-proven** - 23 dedicated security tests verify isolation and telemetry safety
5. **Transparent code** - Full source available for audit

**Perfect for:**
- HIPAA/SOC2 compliance
- Proprietary code bases
- Air-gapped development
- Security research
- Offline work

---

## 📊 Performance Expectations

### What to Expect

| Mac Type | Model | Speed | Memory | Context |
|----------|-------|-------|--------|---------|
| 8GB M1 (Air) | 7B Q4 | 15-20 t/s | ~4GB | 16K tokens |
| 16GB M1 Pro | 7B Q5 | 25-35 t/s | ~6GB | 32K tokens |
| 32GB M1 Max | 14B Q5 | 20-30 t/s | ~12GB | 64K tokens |

**t/s** = tokens per second

### Compared to Cloud APIs

| Feature | Qwenvert | Claude API |
|---------|----------|------------|
| Speed | 20-35 t/s | 40-60 t/s |
| Latency | ~0ms (local) | 100-300ms (network) |
| Cost | $0/month | $15-300/month |
| Privacy | 100% local | Cloud |
| Offline | ✅ Yes | ❌ No |
| Code quality | Good | Excellent |

**Best for:** Security/privacy-critical work, cost-sensitive projects, offline development

**Not ideal for:** Highest code quality, fastest possible responses

---

## 🎓 Understanding Qwenvert

### What Is It?

Qwenvert is an **HTTP adapter** that sits between Claude Code CLI and your local LLM:

```
Claude Code → Qwenvert → Ollama/llama.cpp → Qwen Model
```

**Not just config** - It's a full translation layer:
- Translates Anthropic API → Ollama/llama.cpp format
- Converts responses back to Anthropic format
- Handles streaming (Server-Sent Events)
- Manages backend processes
- Monitors performance

### Why Not Use Ollama Directly?

Ollama has basic Anthropic API support, but:
- ❌ Limited streaming support
- ❌ Missing some API features
- ❌ No thermal management
- ❌ No hardware optimization
- ❌ Can't switch backends easily

Qwenvert provides:
- ✅ Full Anthropic Messages API
- ✅ Works with Ollama **or** llama.cpp
- ✅ Thermal monitoring for MacBook Air
- ✅ Hardware-aware model selection
- ✅ Easy to extend with new backends

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code CLI                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                    POST /v1/messages
                         │
┌────────────────────────▼────────────────────────────────────┐
│                 Qwenvert HTTP Adapter                        │
│                     (localhost:8088)                         │
│  • Validates requests                                        │
│  • Translates Anthropic → Backend format                    │
│  • Handles streaming (SSE)                                   │
│  • Monitors performance                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                Backend-specific API
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Ollama or llama.cpp Server                      │
│                  (localhost:11434 or :8080)                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                  ┌──────▼───────┐
                  │  Qwen Model  │
                  │    (GGUF)    │
                  └──────────────┘
```

---

## 🚀 Next Steps

### After Installation

1. **Optimize for your use case:**
   - Heavy coding? Use Q5 quantization for better quality
   - Low RAM? Use Q4 quantization to save memory
   - Need speed? Use llama.cpp backend

2. **Set up convenience aliases:**
   ```bash
   # Add to ~/.zshrc
   alias qw-start='qwenvert start'
   alias qw-stop='qwenvert stop'
   alias qw-status='qwenvert status'
   ```

3. **Monitor performance:**
   ```bash
   qwenvert monitor
   ```

4. **Read advanced docs:**
   - [ARCHITECTURE.md](./ARCHITECTURE.md) - How it works
   - [SIMPLIFIED_ARCHITECTURE.md](./docs/SIMPLIFIED_ARCHITECTURE.md) - Beginner-friendly overview

---

## 💡 Tips & Best Practices

### For Best Performance

1. **Close other apps** when running inference
2. **Use appropriate model size** for your RAM
3. **Monitor temperature** on MacBook Air (use `qwenvert monitor`)
4. **Don't use Rosetta** - qwenvert is native Apple Silicon

### For Best Code Quality

1. **Use Q5 quantization** if you have 16GB+ RAM
2. **Give it more context** - longer prompts = better results
3. **Be specific** in your prompts (same as with Claude)
4. **Iterate** - local models benefit from refinement

### For Development

1. **Keep qwenvert running** in a dedicated terminal
2. **Check logs** if something seems wrong: `qwenvert status`
3. **Update models** periodically - new versions improve quality
4. **Share feedback** - open issues for bugs/improvements

---

## 📊 Performance Benchmarks

Measure qwenvert performance on your Mac:

```bash
# Start qwenvert
qwenvert start

# Run benchmarks (separate terminal)
make benchmark
```

**What it tests:**
- Different prompt lengths (short, medium, long)
- Streaming vs non-streaming
- Different token limits (50, 100, 200)
- Code generation tasks

**Metrics:**
- Latency (ms)
- Throughput (tokens/sec)
- Time to first token (TTFT)
- Success rate

**Example output:**
```
┌────────────────┬─────────┬──────┬─────────┬────────┬─────────┬────────┐
│ Benchmark      │ Backend │ Quant│ Latency │ Tokens │ Speed   │ Status │
├────────────────┼─────────┼──────┼─────────┼────────┼─────────┼────────┤
│ prompt_short   │ ollama  │ Q4_K │ 1234ms  │ 5      │ 4.1 t/s │   ✓    │
│ prompt_medium  │ ollama  │ Q4_K │ 2456ms  │ 89     │ 36.2t/s │   ✓    │
└────────────────┴─────────┴──────┴─────────┴────────┴─────────┴────────┘

Summary:
  Average latency: 1845ms
  Average throughput: 32.4 tokens/sec
```

Results saved to `benchmarks/results/` for tracking over time.

See [benchmarks/README.md](./benchmarks/README.md) for details.

---

## 🤝 Contributing

We welcome contributions! Areas where help is needed:

- **Model support** - Add Qwen3-Coder, other model families
- **Backend support** - MLX, vLLM, TensorRT-LLM
- **Performance** - Optimization for specific Mac models
- **Testing** - More edge cases, hardware configurations
- **Documentation** - Tutorials, examples, translations

See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

---

## 📚 More Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System design and component details
- **[TELEMETRY_SECURITY.md](./TELEMETRY_SECURITY.md)** - OpenTelemetry security guarantees and configuration
- **[SIMPLIFIED_ARCHITECTURE.md](./docs/SIMPLIFIED_ARCHITECTURE.md)** - Beginner-friendly architecture overview
- **[AGENTS.md](./AGENTS.md)** - AI agents for development and security auditing
- **[TASKS.md](./TASKS.md)** - Development roadmap and task tracking
- **[tests/](./tests/)** - Test suite with 23 dedicated security tests

---

## 🙏 Acknowledgments

- **Qwen Team** (Alibaba) - Excellent Qwen2.5-Coder models
- **Apple ML Team** - Metal acceleration, unified memory
- **llama.cpp community** - High-performance inference engine
- **Ollama team** - Making local LLMs accessible
- **Anthropic** - Claude Code CLI and Messages API

---

## 📝 License

Apache 2.0 License - see [LICENSE](./LICENSE)

---

## ⚠️ Limitations & Disclaimers

### Known Limitations

- **Mac only** - Designed for M1/M2/M3 Macs (Intel/Windows not supported)
- **Python 3.9-3.12** - Python 3.13 not yet compatible
- **Large downloads** - Models are 4-10GB (one-time download)
- **Code quality** - Good, but not as good as Claude Opus/Sonnet
- **First run slow** - Model loading takes 10-30 seconds

### Not Affiliated

Qwenvert is an independent project and is not affiliated with, endorsed by, or supported by Anthropic. Claude Code is a trademark of Anthropic.

---

## 📖 Research & Methodology

This project implements research-backed development practices for AI agent collaboration:

### Repository-Level Instructions

Our [AGENTS.md](./AGENTS.md) file follows findings from:

> **"Repository-Level Instructions Enhance AI Assistant Completion and Efficiency"**
> Li et al., 2025. arXiv:2601.20404
> https://arxiv.org/abs/2601.20404

**Key findings from the research:**
- **28.64% reduction** in AI agent task completion time
- **16.58% reduction** in token usage
- Repository-level instructions significantly improve code generation accuracy

**How we apply it:**
- Structured project conventions in [AGENTS.md](./AGENTS.md)
- Security-critical rules documented upfront
- File modification requirements clearly specified
- Specialized agent catalog with use cases

This approach makes qwenvert development more efficient and maintainable when working with AI coding assistants like Claude Code.

---

**Questions? Issues? Feedback?**

Open an issue: https://github.com/kmesiab/qwenvert/issues

---

**Built with care for the Mac M1 community** 🚀
