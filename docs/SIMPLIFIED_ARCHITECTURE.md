# Simplified Architecture: Local-First Design

## The Reality Check

**Qwenvert is NOT an inference server.** It's a smart installer/configurator that:
1. Detects your hardware
2. Picks the optimal model
3. Downloads and configures existing tools (Ollama/llama.cpp/MLX)
4. Launches them with optimal settings
5. Optionally monitors performance

We leverage existing, battle-tested inference servers instead of building a new one.

---

## Revised Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code CLI                         │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP localhost:11434
                         │ (Anthropic Messages API)
                         │
┌────────────────────────▼────────────────────────────────────┐
│              Ollama / llama.cpp / MLX Server                 │
│         (Native HTTP server with Anthropic API)              │
│                                                               │
│  - Handles HTTP requests                                     │
│  - Manages model loading                                     │
│  - Executes inference                                        │
│  - Streams responses                                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Configured by:
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    Qwenvert (Our Tool)                       │
│                                                               │
│  Components:                                                 │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 1. Hardware Detector                               │     │
│  │    - Detect M1/M2/M3, RAM, cores                   │     │
│  │    - Identify cooling (Air vs Pro)                 │     │
│  └────────────────────────────────────────────────────┘     │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 2. Model Selector                                  │     │
│  │    - Pick optimal model for hardware               │     │
│  │    - Download from HuggingFace                     │     │
│  └────────────────────────────────────────────────────┘     │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 3. Configuration Generator                         │     │
│  │    - Generate Ollama Modelfile                     │     │
│  │    - Generate llama.cpp flags                      │     │
│  │    - Set optimal parameters                        │     │
│  └────────────────────────────────────────────────────┘     │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 4. Server Launcher                                 │     │
│  │    - Start Ollama/llama.cpp with config            │     │
│  │    - Verify server is running                      │     │
│  │    - Print connection instructions                 │     │
│  └────────────────────────────────────────────────────┘     │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 5. Telemetry Monitor (Optional)                    │     │
│  │    - Separate process watching system metrics      │     │
│  │    - CLI dashboard (if requested)                  │     │
│  │    - Prometheus export (if enabled)                │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## What Qwenvert Actually Is

**Qwenvert is a CLI tool** that automates the tedious parts of setting up local LLM inference:

### Instead of manually:
```bash
# User has to figure all this out:
brew install ollama
ollama pull qwen2.5-coder:7b-q4_k_m  # Which quantization?
ollama serve
export ANTHROPIC_BASE_URL=http://localhost:11434
export ANTHROPIC_AUTH_TOKEN=ollama

# Or worse, with llama.cpp:
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp && make LLAMA_METAL=1
# Download GGUF from... where? Which one?
./llama-server --model ??? -ngl ??? -t ??? -c ??? --anthropic-api
```

### With qwenvert:
```bash
# One command:
qwenvert setup

# It automatically:
# - Detects M1 16GB
# - Picks Qwen2.5-Coder-7B Q4_K_M
# - Downloads from HuggingFace
# - Configures Ollama/llama.cpp optimally
# - Starts server
# - Prints: "export ANTHROPIC_BASE_URL=http://localhost:11434"

claude  # Just works!
```

---

## Component Breakdown

### 1. Hardware Detector

```python
class HardwareDetector:
    """
    Detect Mac hardware and provide profile.
    Pure utility class, no server needed.
    """

    @staticmethod
    def detect() -> HardwareProfile:
        """Run sysctl commands, parse output, return profile."""
        chip = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"])
        memory = subprocess.check_output(["sysctl", "hw.memsize"])
        # ... parse and return profile
```

### 2. Model Selector

```python
class ModelSelector:
    """
    Pick optimal model based on hardware.
    Just decision logic, no server.
    """

    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def select_optimal(self, hardware: HardwareProfile) -> ModelConfig:
        """
        Decision matrix:
        - 8GB M1 → Qwen2.5-7B Q4_K_M
        - 16GB M1 → Qwen2.5-7B Q5_K_M
        - 32GB M1 → Qwen2.5-14B Q5_K_M
        """
        # Pure logic, returns config
```

### 3. Configuration Generator

```python
class ConfigGenerator:
    """
    Generate optimal configs for backend servers.
    No server, just file writing.
    """

    def generate_ollama_modelfile(self, model: ModelConfig) -> str:
        """
        Generate Ollama Modelfile with optimal parameters.

        Example output:
        FROM qwen2.5-coder:7b-q4_k_m
        PARAMETER num_ctx 16384
        PARAMETER num_gpu 1
        PARAMETER num_thread 4
        """
        return f"""
FROM {model.name}
PARAMETER num_ctx {model.context_length}
PARAMETER num_gpu 1
PARAMETER num_thread 4
PARAMETER temperature 0.7
"""

    def generate_llamacpp_flags(self, model: ModelConfig) -> List[str]:
        """
        Generate optimal llama.cpp flags.

        Returns:
        ["--model", "path.gguf", "-ngl", "99", "-t", "4", "-c", "16384", "--anthropic-api"]
        """
        return [
            "--model", model.path,
            "-ngl", "99",  # Offload all layers to Metal
            "-t", "4",     # 4 threads (P-cores)
            "-c", str(model.context_length),
            "--host", "0.0.0.0",
            "--port", "11434",
            "--mlock",  # Lock in memory
            "--anthropic-api"  # Enable Anthropic API
        ]
```

### 4. Server Launcher

```python
class ServerLauncher:
    """
    Launch and manage the actual inference server process.
    This is NOT a server itself - it launches Ollama/llama.cpp.
    """

    def __init__(self, backend: str):
        self.backend = backend  # "ollama", "llamacpp", "mlx"
        self.process: Optional[subprocess.Popen] = None

    async def start_ollama(self, modelfile_path: str):
        """
        Start Ollama server with custom Modelfile.
        """
        # Create model from Modelfile
        subprocess.run(["ollama", "create", "qwenvert", "-f", modelfile_path])

        # Start server (Ollama manages this as daemon)
        subprocess.run(["ollama", "serve"])

        # Wait for server to be ready
        await self._wait_for_http("http://localhost:11434")

        print("✓ Ollama server running on http://localhost:11434")
        print()
        print("Configure Claude Code:")
        print("  export ANTHROPIC_BASE_URL=http://localhost:11434")
        print("  export ANTHROPIC_AUTH_TOKEN=ollama")

    async def start_llamacpp(self, flags: List[str]):
        """
        Start llama.cpp server with optimal flags.
        """
        cmd = ["./llama.cpp/llama-server"] + flags

        # Start as subprocess
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for server to be ready
        await self._wait_for_http("http://localhost:11434")

        print("✓ llama.cpp server running on http://localhost:11434")

    async def _wait_for_http(self, url: str, timeout: int = 30):
        """Wait for HTTP server to be ready."""
        import httpx
        start = time.time()

        while time.time() - start < timeout:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{url}/health")
                    if response.status_code == 200:
                        return
            except:
                pass
            await asyncio.sleep(1)

        raise TimeoutError(f"Server at {url} did not start within {timeout}s")
```

### 5. Telemetry Monitor (Optional, Separate Process)

```python
class TelemetryMonitor:
    """
    OPTIONAL: Separate monitoring process.
    Does NOT intercept inference - just watches system.
    """

    def __init__(self):
        self.collector = AppleSiliconCollector()
        self.running = False

    async def run_dashboard(self):
        """
        Run real-time CLI dashboard.
        This is a separate terminal window, not blocking anything.
        """
        from rich.live import Live

        with Live(refresh_per_second=2) as live:
            while self.running:
                snapshot = await self.collector.collect()
                live.update(self._render_dashboard(snapshot))
                await asyncio.sleep(0.5)

    async def export_prometheus(self, port: int = 9090):
        """
        Export Prometheus metrics.
        Separate HTTP server on different port.
        """
        from prometheus_client import start_http_server, Gauge

        # Start Prometheus HTTP server
        start_http_server(port)

        # Collect and update metrics
        while self.running:
            snapshot = await self.collector.collect()
            self._update_prometheus_metrics(snapshot)
            await asyncio.sleep(2)
```

---

## CLI Interface (The User Experience)

```bash
# One-click setup
qwenvert setup
# Output:
# Detecting hardware...
# ✓ Found: M1 with 16GB RAM
# ✓ Selected: Qwen2.5-Coder-7B Q4_K_M
# Downloading model... [████████████] 100%
# ✓ Model downloaded
# ✓ Configuring Ollama...
# ✓ Starting server...
# ✓ Server running on http://localhost:11434
#
# Configure Claude Code:
#   export ANTHROPIC_BASE_URL=http://localhost:11434
#   export ANTHROPIC_AUTH_TOKEN=ollama
#   claude

# Optional: Monitor in separate terminal
qwenvert monitor
# Shows real-time dashboard:
# ┌─────────────────────────────────┐
# │   Qwenvert Monitor              │
# ├─────────────────────────────────┤
# │ CPU Temp:    62.3°C  ✓          │
# │ GPU Temp:    59.1°C  ✓          │
# │ Thermal:     0.42    ✓          │
# │ Memory:      8.2/16GB ✓         │
# │ Throughput:  32.1 tok/s         │
# └─────────────────────────────────┘

# Stop server
qwenvert stop

# Check status
qwenvert status
# Output:
# ✓ Server running (PID: 12345)
# ✓ Model: Qwen2.5-Coder-7B Q4_K_M
# ✓ Listening: http://localhost:11434
# ✓ Health: OK
```

---

## File Structure (Simplified)

```
qwenvert/
├── qwenvert/
│   ├── __init__.py
│   ├── hardware.py           # HardwareDetector
│   ├── models.py             # ModelSelector, ModelRegistry
│   ├── config.py             # ConfigGenerator
│   ├── launcher.py           # ServerLauncher
│   ├── telemetry.py          # TelemetryMonitor (optional)
│   └── cli.py                # CLI commands
├── configs/
│   └── models.yaml           # Model registry
├── tests/
├── requirements.txt
├── setup.py
└── README.md
```

**That's it.** No API gateway, no orchestrator, no abstractions over abstractions.

---

## Benefits of Simplified Approach

1. **Leverage Existing Tools**: Ollama/llama.cpp are battle-tested, optimized, and maintained
2. **Less Code to Maintain**: We focus on hardware detection and configuration, not building an inference server
3. **Better Performance**: Native servers are highly optimized (C++, Metal, etc.)
4. **Easier to Understand**: Clear separation: we configure, they serve
5. **True One-Click**: User doesn't need to know anything about Ollama/llama.cpp internals

---

## What We Actually Build

### Core (Required):
- ✅ Hardware detection
- ✅ Model selection logic
- ✅ Configuration generation
- ✅ Server launcher/manager
- ✅ CLI interface

### Optional (Nice-to-have):
- ⭐ Telemetry monitoring (separate process)
- ⭐ Prometheus export
- ⭐ CLI dashboard
- ⭐ Web UI (future)

---

## Example: Complete Setup Flow

```python
# qwenvert/cli.py

@click.command()
def setup():
    """One-click setup for local LLM inference."""

    # 1. Detect hardware
    detector = HardwareDetector()
    hardware = detector.detect()
    console.print(f"✓ Detected: {hardware.chip} with {hardware.total_memory_gb}GB RAM")

    # 2. Select model
    selector = ModelSelector(ModelRegistry())
    model = selector.select_optimal(hardware)
    console.print(f"✓ Selected: {model.name} ({model.quantization})")

    # 3. Download model (if needed)
    downloader = ModelDownloader()
    if not downloader.is_cached(model):
        console.print("Downloading model...")
        downloader.download(model, show_progress=True)
    console.print(f"✓ Model ready")

    # 4. Generate config
    config_gen = ConfigGenerator()

    # Try Ollama first (easiest)
    if shutil.which("ollama"):
        modelfile = config_gen.generate_ollama_modelfile(model)
        Path("~/.ollama/Modelfile.qwenvert").write_text(modelfile)
        console.print("✓ Configured Ollama")

        # 5. Start server
        launcher = ServerLauncher("ollama")
        launcher.start_ollama("~/.ollama/Modelfile.qwenvert")

    else:
        # Fallback to llama.cpp
        console.print("Ollama not found, using llama.cpp...")
        # Install llama.cpp if needed, then launch
        pass

    console.print()
    console.print("[bold green]✓ Setup complete![/bold green]")
    console.print()
    console.print("Configure Claude Code:")
    console.print("  [bold]export ANTHROPIC_BASE_URL=http://localhost:11434[/bold]")
    console.print("  [bold]export ANTHROPIC_AUTH_TOKEN=ollama[/bold]")
    console.print()
    console.print("Then run: [bold]claude[/bold]")
```

---

This is what a local-first tool should look like. **We configure, existing servers serve.**

Much better?
