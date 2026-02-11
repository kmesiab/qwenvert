---
layout: default
---

# Privacy-First Local AI for Claude Code

Use Claude Code CLI with **local Qwen models** on your Mac M1/M2/M3. No cloud, no API fees, your code never leaves your machine.

---

## 🔒 Why Qwenvert?

### Privacy First
All inference happens locally. Localhost-only binding with **93 security tests** ensures your code never leaves your machine.

### Zero API Costs
No subscription fees, no pay-per-token. Use your Mac's hardware for unlimited AI assistance.

### Apple Silicon Optimized
Hardware-aware configuration for M1/M2/M3 Macs with Metal acceleration and thermal management.

### Full API Compatibility
Drop-in replacement for Claude Code. Works with existing workflows, just point to localhost.

### Multiple Backends
Choose between Ollama or llama.cpp. Switch backends without changing your setup.

### Built-in Monitoring
Real-time dashboard tracks performance, thermal behavior, and token throughput.

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/kmesiab/qwenvert
cd qwenvert

# Install with pip
pip install -e .
```

> **Note:** Qwenvert is not yet published on PyPI. Install from source as shown above.

### Initialize & Start

```bash
# Detect hardware and download optimal model (one-time setup)
qwenvert init

# Start the adapter + backend
qwenvert start
```

### Configure Claude Code

```bash
export ANTHROPIC_BASE_URL=http://localhost:8088
export ANTHROPIC_API_KEY=local-qwen
export ANTHROPIC_MODEL=qwenvert-default

# Start coding!
claude
```

> **First run downloads a 4-10GB model (one-time). Requires Python 3.9-3.12 and Mac M1/M2/M3.**

---

## 🏗️ How It Works

Qwenvert is an HTTP adapter that translates between Claude Code and local LLM backends:

```
┌──────────────────┐
│  Claude Code CLI │
└────────┬─────────┘
         │ POST /v1/messages
         │ (Anthropic API)
         │
┌────────▼─────────────────┐
│  Qwenvert Adapter        │
│  (localhost:8088)        │
│  • API Translation       │
│  • Security Validation   │
│  • Streaming (SSE)       │
└────────┬─────────────────┘
         │
┌────────▼─────────────────┐
│  Backend                 │
│  (Ollama or llama.cpp)   │
└────────┬─────────────────┘
         │
┌────────▼─────────────────┐
│  Qwen Model (Local)      │
│  • Metal Acceleration    │
│  • Quantized (Q4/Q5)     │
└──────────────────────────┘
```

### What Qwenvert Does

- **Translates APIs**: Converts Anthropic Messages API → Ollama/llama.cpp format
- **Validates Security**: All URLs/hosts checked for localhost-only access (93 tests)
- **Manages Backends**: Launches and monitors Ollama or llama.cpp servers
- **Streams Responses**: Server-Sent Events for real-time token streaming
- **Optimizes Hardware**: Auto-configures for your Mac's specs and thermal profile

---

## 📊 Performance

- **100% Private**: Zero cloud dependencies, all inference local
- **$0 API Fees**: No subscription, no per-token costs
- **93 Security Tests**: Comprehensive localhost-only validation
- **Metal Accelerated**: Optimized for Apple Silicon unified memory
- **Thermal Aware**: Pacing for fanless MacBook Air models

---

## 📚 Documentation

### Core Documentation
- [Complete Guide (README)](https://github.com/kmesiab/qwenvert/blob/main/README.md) - Full setup and configuration
- [Architecture](https://github.com/kmesiab/qwenvert/blob/main/ARCHITECTURE.md) - System design deep dive
- [AI Agents Guide](https://github.com/kmesiab/qwenvert/blob/main/AGENTS.md) - Development workflow with AI agents

### Security & Telemetry
- [Security Model](https://github.com/kmesiab/qwenvert/blob/main/TELEMETRY_SECURITY.md) - Localhost-only guarantees
- [OpenTelemetry](https://github.com/kmesiab/qwenvert/blob/main/TELEMETRY_SECURITY.md) - Observability with privacy

### Development
- [Contributing](https://github.com/kmesiab/qwenvert/blob/main/CONTRIBUTING.md) - How to contribute
- [Benchmarks](https://github.com/kmesiab/qwenvert/tree/main/benchmarks) - Performance testing suite

---

## ❓ FAQ

### Is this better than using Claude directly?

No - Claude Opus/Sonnet are more capable. Qwenvert is for when you want **privacy**, **zero API costs**, or **offline coding**. Think of it as a privacy-focused alternative, not a replacement.

### What are the hardware requirements?

Mac M1/M2/M3 with at least **8GB RAM** (16GB recommended). Python 3.9-3.12. 10-20GB free disk space for models.

### Does it work on Intel Macs or Windows?

Not currently - qwenvert is optimized for Apple Silicon's unified memory and Metal acceleration. Intel/Windows support would require significant changes.

### How is security guaranteed?

93 security tests validate localhost-only operation. All URLs are checked with proper parsing (no substring matching). Config tampering is detected on load. See [TELEMETRY_SECURITY.md](https://github.com/kmesiab/qwenvert/blob/main/TELEMETRY_SECURITY.md) for details.

### Which Qwen model should I use?

Start with **qwen2.5-coder:7b** (4GB, balanced). For better quality: 14b/32b models if you have 16GB+ RAM. For speed: 1.5b/3b models on lower-end hardware.

### Can I use other models besides Qwen?

Technically yes - any Ollama/llama.cpp model works. But qwenvert is tuned for Qwen2.5-Coder's instruction format and code generation strengths.

---

## 📖 Research

This project implements research-backed development practices. Our [AGENTS.md](https://github.com/kmesiab/qwenvert/blob/main/AGENTS.md) follows findings from:

> **"Repository-Level Instructions Enhance AI Assistant Completion and Efficiency"**
> Li et al., 2025. [arXiv:2601.20404](https://arxiv.org/abs/2601.20404)

**Key findings:**
- **28.64% reduction** in AI agent task completion time
- **16.58% reduction** in token usage
- Repository-level instructions significantly improve code generation accuracy

---

## 🤝 Contributing

We welcome contributions! Areas where help is needed:

- **Model support** - Add Qwen3-Coder, other model families
- **Backend support** - MLX, vLLM, TensorRT-LLM
- **Performance** - Optimization for specific Mac models
- **Testing** - More edge cases, hardware configurations
- **Documentation** - Tutorials, examples, translations

See [CONTRIBUTING.md](https://github.com/kmesiab/qwenvert/blob/main/CONTRIBUTING.md) for guidelines.

---

## 📝 License

Apache 2.0 License - see [LICENSE](https://github.com/kmesiab/qwenvert/blob/main/LICENSE)

---

## ⚠️ Disclaimer

**Not Affiliated**: Qwenvert is an independent project and is not affiliated with, endorsed by, or supported by Anthropic. Claude Code is a trademark of Anthropic.

**Known Limitations**:
- Mac only (M1/M2/M3)
- Python 3.9-3.12
- Large model downloads (4-10GB)
- Code quality good, but not as good as Claude Opus/Sonnet
- First run slow (model loading 10-30 seconds)

---

## 💬 Support

- **Issues**: [github.com/kmesiab/qwenvert/issues](https://github.com/kmesiab/qwenvert/issues)
- **Discussions**: [github.com/kmesiab/qwenvert/discussions](https://github.com/kmesiab/qwenvert/discussions)
- **Twitter**: [@kmesiab](https://twitter.com/kmesiab)

---

**Built with care for the Mac M1 community** 🚀
