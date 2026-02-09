"""
Qwenvert CLI - User-facing command-line interface.

Commands:
- init: Initialize configuration
- start: Start servers
- status: Show status
- stop: Stop servers
- models: List available models
"""

import sys

import click
from rich.console import Console
from rich.table import Table


console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """
    Qwenvert - One-click local LLM inference for Claude Code.

    Run local Qwen models with Claude Code through an Anthropic-compatible adapter.
    """


@cli.command()
@click.option(
    "--model",
    help="Model ID to use (e.g., qwen2.5-coder-7b-q4-ollama)",
)
@click.option(
    "--backend",
    type=click.Choice(["ollama", "llamacpp"]),
    help="Backend to use",
)
@click.option(
    "--adapter-port",
    type=int,
    default=8088,
    help="Adapter server port (default: 8088)",
)
@click.option(
    "--context-length",
    type=int,
    help="Maximum context length (default: hardware-dependent)",
)
def init(model, backend, adapter_port, context_length):
    """
    Initialize qwenvert configuration.

    Detects hardware, selects optimal model, and generates configuration.
    """
    from .config import ConfigGenerator, ConfigManager
    from .hardware import HardwareDetector
    from .models import Backend, ModelRegistry, ModelSelector

    console.print("\n[bold blue]Qwenvert Initialization[/bold blue]\n")

    # Step 1: Detect hardware
    with console.status("[cyan]Detecting hardware...", spinner="dots"):
        detector = HardwareDetector()
        hardware = detector.detect()

    console.print(f"✓ Detected: [green]{hardware}[/green]")

    # Step 2: Select model
    registry = ModelRegistry()
    selector = ModelSelector(registry)

    if model:
        # User specified model
        selected_model = registry.get_model(model)
        if not selected_model:
            console.print(f"[red]Error:[/red] Model '{model}' not found")
            console.print("\nAvailable models:")
            _list_models_table(registry)
            sys.exit(1)

        if not selected_model.fits_hardware(hardware):
            console.print(
                f"[yellow]Warning:[/yellow] Model may not fit on your hardware "
                f"({hardware.total_memory_gb}GB RAM, needs {selected_model.min_ram_gb}GB+)"
            )
            if not click.confirm("Continue anyway?"):
                sys.exit(1)
    else:
        # Auto-select optimal model
        selected_model = selector.select_default(hardware)
        if not selected_model:
            console.print(
                "[red]Error:[/red] No compatible model found for your hardware"
            )
            sys.exit(1)

    console.print(f"✓ Selected: [green]{selected_model.display_name}[/green]")

    # Step 3: Download model if needed
    from .downloader import ModelDownloader

    downloader = ModelDownloader()
    model_path = downloader.get_model_path(selected_model)

    if model_path:
        console.print(f"✓ Model already downloaded: [green]{model_path}[/green]")
    # Verify model has HuggingFace repo before attempting download
    elif not selected_model.huggingface_repo:
        console.print(
            f"\n[red]Error:[/red] Model {selected_model.id} has no HuggingFace repository specified"
        )
        console.print(
            "\n[yellow]You can manually download the model and place it in:[/yellow]"
        )
        console.print(f"  {downloader.models_dir}")
        if not click.confirm("\nContinue with configuration anyway?"):
            sys.exit(1)
    else:
        console.print(
            f"\n[cyan]Downloading {selected_model.display_name} from HuggingFace...[/cyan]"
        )
        console.print(f"Repository: {selected_model.huggingface_repo}")

        try:
            with console.status(
                f"[cyan]Downloading {selected_model.display_name}...",
                spinner="dots",
            ):
                model_path = downloader.download(selected_model)

            console.print(f"✓ Model downloaded: [green]{model_path}[/green]")
            size_gb = model_path.stat().st_size / (1024**3)
            console.print(f"  Size: {size_gb:.2f} GB")

        except Exception as e:
            console.print(f"\n[red]Error downloading model:[/red] {e}")
            console.print(
                "\n[yellow]You can manually download the model and place it in:[/yellow]"
            )
            console.print(f"  {downloader.models_dir}")
            if not click.confirm("\nContinue with configuration anyway?"):
                sys.exit(1)

    # Step 4: Generate configuration
    config_gen = ConfigGenerator(selected_model, hardware)
    config = config_gen.generate_qwenvert_config(adapter_port=adapter_port)

    if context_length:
        config.context_length = context_length

    # Update config with actual model path if downloaded
    if model_path:
        config.model_path = str(model_path)

    # Step 5: Save configuration
    config_path = ConfigManager.save(config)
    console.print(f"✓ Configuration saved: [green]{config_path}[/green]")

    # Step 6: Generate backend-specific configs
    if selected_model.backend == Backend.OLLAMA:
        modelfile = config_gen.generate_ollama_modelfile()
        modelfile_path = ConfigManager.save_ollama_modelfile(modelfile)
        console.print(f"✓ Ollama Modelfile: [green]{modelfile_path}[/green]")

    # Step 7: Print setup instructions
    instructions = config_gen.print_setup_instructions()
    console.print(instructions)

    console.print("[bold green]✓ Initialization complete![/bold green]")
    console.print("\nNext step: [bold]qwenvert start[/bold]\n")


@cli.command()
def start():
    """
    Start qwenvert servers (backend + adapter).

    Starts the backend server (Ollama or llama.cpp) and the qwenvert
    HTTP adapter, then displays connection instructions for Claude Code.
    """
    from .launcher import start_qwenvert_sync

    console.print("\n[bold blue]Starting Qwenvert[/bold blue]\n")

    try:
        start_qwenvert_sync()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


@cli.command()
def status():
    """
    Show qwenvert status.

    Displays current configuration and server health.
    """
    import httpx

    from .config import ConfigManager

    console.print("\n[bold blue]Qwenvert Status[/bold blue]\n")

    # Check if configured
    if not ConfigManager.exists():
        console.print(
            "[yellow]Not configured.[/yellow] Run [bold]qwenvert init[/bold] first.\n"
        )
        return

    # Load config
    config = ConfigManager.load()

    # Create status table
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Model", config.model_id)
    table.add_row("Backend", config.backend)
    table.add_row("Backend URL", config.backend_url)
    table.add_row("Adapter", f"http://{config.adapter_host}:{config.adapter_port}")
    table.add_row("Context Length", f"{config.context_length:,} tokens")
    table.add_row("Thermal Monitoring", "✓" if config.thermal_monitoring else "✗")
    table.add_row("Thermal Pacing", "✓" if config.thermal_pacing else "✗")

    console.print(table)

    # Check server health
    console.print("\n[bold]Server Health:[/bold]")

    # Check backend
    try:
        response = httpx.get(f"{config.backend_url}/health", timeout=2.0)
        if response.status_code == 200:
            console.print("  Backend:  [green]✓ Running[/green]")
        else:
            console.print("  Backend:  [red]✗ Unhealthy[/red]")
    except Exception:
        console.print("  Backend:  [red]✗ Not running[/red]")

    # Check adapter
    adapter_url = f"http://{config.adapter_host}:{config.adapter_port}"
    try:
        response = httpx.get(f"{adapter_url}/health", timeout=2.0)
        if response.status_code == 200:
            console.print("  Adapter:  [green]✓ Running[/green]")
        else:
            console.print("  Adapter:  [red]✗ Unhealthy[/red]")
    except Exception:
        console.print("  Adapter:  [red]✗ Not running[/red]")

    console.print()


@cli.command()
def stop():
    """
    Stop qwenvert servers.

    Gracefully stops the backend and adapter servers.
    """
    import subprocess

    from .config import ConfigManager

    console.print("\n[bold blue]Stopping Qwenvert[/bold blue]\n")

    if not ConfigManager.exists():
        console.print("[yellow]Not configured.[/yellow]\n")
        return

    # Kill processes (simple approach - could be improved with PID tracking)
    killed = False

    # Try to kill ollama
    try:
        subprocess.run(["pkill", "-f", "ollama serve"], check=False)
        killed = True
    except Exception:
        pass

    # Try to kill llama-server
    try:
        subprocess.run(["pkill", "-f", "llama-server"], check=False)
        killed = True
    except Exception:
        pass

    # Try to kill uvicorn (adapter)
    try:
        subprocess.run(["pkill", "-f", "uvicorn.*qwenvert"], check=False)
        killed = True
    except Exception:
        pass

    if killed:
        console.print("[green]✓ Servers stopped[/green]\n")
    else:
        console.print("[yellow]No running servers found[/yellow]\n")


@cli.group()
def models():
    """Model management commands."""


@models.command("list")
@click.option(
    "--backend", type=click.Choice(["ollama", "llamacpp"]), help="Filter by backend"
)
def list_models(backend):
    """
    List available models.

    Shows all models in the registry with their specifications.
    """
    from .models import Backend, ModelRegistry

    console.print("\n[bold blue]Available Models[/bold blue]\n")

    registry = ModelRegistry()
    backend_filter = Backend(backend) if backend else None
    all_models = registry.list_models(backend=backend_filter)

    _list_models_table(registry, backend_filter)

    console.print()


def _list_models_table(registry, backend_filter=None):
    """Helper to display models table."""
    all_models = registry.list_models(backend=backend_filter)

    table = Table()
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Size", justify="right")
    table.add_column("Quant", justify="center")
    table.add_column("Backend", justify="center")
    table.add_column("Min RAM", justify="right")
    table.add_column("Context", justify="right")

    for model in all_models:
        table.add_row(
            model.id,
            model.display_name,
            f"{model.size_b:.1f}B",
            model.quantization,
            model.backend.value,
            f"{model.min_ram_gb}GB",
            f"{model.context_length // 1024}K",
        )

    console.print(table)


@cli.command()
def hardware():
    """
    Show detected hardware information.

    Displays Mac hardware specs detected by qwenvert.
    """
    from .hardware import HardwareDetector

    console.print("\n[bold blue]Hardware Information[/bold blue]\n")

    detector = HardwareDetector()
    hw = detector.detect()

    table = Table()
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Chip", hw.chip)
    table.add_row("Chip Family", hw.chip_family)
    table.add_row("Total Memory", f"{hw.total_memory_gb}GB")
    table.add_row("GPU Cores", str(hw.gpu_cores))
    table.add_row("Performance Cores", str(hw.cpu_cores_performance))
    table.add_row("Efficiency Cores", str(hw.cpu_cores_efficiency))
    table.add_row(
        "Cooling", "Active (fan)" if hw.has_active_cooling else "Passive (fanless)"
    )
    table.add_row("Neural Engine Cores", str(hw.neural_engine_cores))
    table.add_row("Model Identifier", hw.model_identifier)
    table.add_row(
        "Recommended Context", f"{hw.recommended_context_length() // 1024}K tokens"
    )

    console.print(table)

    # Recommendations
    console.print("\n[bold]Recommendations:[/bold]")
    if hw.is_memory_constrained():
        console.print("  • [yellow]Memory constrained[/yellow] - use Q4 quantization")
    if hw.is_thermally_constrained():
        console.print(
            "  • [yellow]Thermally constrained[/yellow] - enable thermal pacing"
        )
    if not hw.is_memory_constrained() and not hw.is_thermally_constrained():
        console.print(
            "  • [green]Good configuration[/green] - can handle larger models"
        )

    console.print()


@cli.command()
@click.option(
    "--adapter-url",
    default="http://localhost:8088",
    help="Adapter URL to monitor (default: http://localhost:8088)",
)
@click.option(
    "--refresh-rate",
    type=float,
    default=1.0,
    help="Dashboard refresh rate in seconds (default: 1.0)",
)
def monitor(adapter_url, refresh_rate):
    """
    Real-time monitoring dashboard.

    Displays live performance metrics, system resources, and request history
    in a beautiful terminal interface.
    """
    import asyncio

    from .config import ConfigManager
    from .dashboard import run_dashboard

    console.print("\n[bold blue]Starting Qwenvert Monitor[/bold blue]\n")

    # Load config if available to get adapter URL
    if ConfigManager.exists():
        config = ConfigManager.load()
        adapter_url = f"http://{config.adapter_host}:{config.adapter_port}"
        console.print(f"Monitoring: [cyan]{adapter_url}[/cyan]")
    else:
        console.print(f"Monitoring: [cyan]{adapter_url}[/cyan]")
        console.print(
            "[yellow]Tip:[/yellow] Run [bold]qwenvert init[/bold] to configure\n"
        )

    console.print("Press [bold cyan]Ctrl+C[/bold cyan] to exit\n")

    try:
        asyncio.run(run_dashboard(adapter_url=adapter_url, refresh_rate=refresh_rate))
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped[/yellow]\n")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
