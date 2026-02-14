"""
Qwenvert CLI - User-facing command-line interface.

Commands:
- init: Initialize configuration
- start: Start servers
- status: Show status
- stop: Stop servers
- models: List available models
- binary: Binary management commands
"""

from __future__ import annotations

import stat
import sys

import click
from rich.console import Console
from rich.table import Table

from . import __version__


console = Console()


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
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
    default="llamacpp",  # Default to llamacpp (3-7x faster than Ollama)
    help="Backend to use (default: llamacpp)",
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
@click.option(
    "--no-auto-install",
    is_flag=True,
    help="Disable automatic binary installation (requires manual setup)",
)
def init(model, backend, adapter_port, context_length, no_auto_install) -> None:
    """
    Initialize qwenvert configuration.

    Detects hardware, selects optimal model, and generates configuration.
    """
    from .config import ConfigGenerator, ConfigManager
    from .hardware import HardwareDetector
    from .models import Backend, ModelRegistry, ModelSelector

    console.print("\n[bold blue]Qwenvert Initialization[/bold blue]\n")

    # Step 0: Check dependencies early (before expensive operations)
    if backend is not None:
        from .dependencies import (
            check_backend_dependencies,
            format_missing_dependency_message,
        )

        dep_check = check_backend_dependencies(backend)
        if not dep_check.is_available:
            console.print(
                f"[yellow]Warning:[/yellow] {dep_check.name} is not installed\n"
            )
            console.print(format_missing_dependency_message(dep_check))

            if not click.confirm(
                "\nContinue with configuration anyway?", default=False
            ):
                console.print("\n[yellow]Initialization cancelled.[/yellow]")
                console.print(
                    f"\n[dim]Tip: After installing {dep_check.name}, run 'qwenvert init' again.[/dim]"
                )
                sys.exit(1)

            console.print("\n[yellow]Continuing without dependencies...[/yellow]\n")

    # Step 1: Detect hardware (needed for binary selection)
    with console.status("[cyan]Detecting hardware...", spinner="dots"):
        detector = HardwareDetector()
        hardware = detector.detect()

    console.print(f"✓ Detected: [green]{hardware}[/green]")

    # Step 0.5: Setup llama.cpp binary (if using llamacpp backend)
    if backend == "llamacpp":
        from .binary_manager import BinaryManager

        binary_mgr = BinaryManager()
        console.print("\n[cyan]Step 0.5: Setting up llama-server...[/cyan]")

        try:
            with console.status("[cyan]Installing llama-server...", spinner="dots"):
                binary_info = binary_mgr.get_or_install_binary(
                    hardware=hardware,
                    auto_install=not no_auto_install,  # Zero friction by default!
                )

            console.print(
                f"  ✓ llama-server ready: [green]{binary_info.path}[/green] "
                f"(v{binary_info.version}, {binary_info.source.value})\n"
            )

        except RuntimeError as e:
            # Graceful fallback to Ollama
            console.print("\n[yellow]Could not install llama-server:[/yellow]")
            console.print(f"  {e}\n")
            console.print("[cyan]Switching to Ollama backend (recommended)[/cyan]")
            backend = "ollama"

    # Step 2: Select model
    registry = ModelRegistry()
    selector = ModelSelector(registry)

    # Check for already-downloaded models to prioritize them
    from .downloader import ModelDownloader

    downloader = ModelDownloader()
    downloaded_models = downloader.list_downloaded_models()

    if downloaded_models:
        console.print(
            f"✓ Found {len(downloaded_models)} downloaded model(s), checking compatibility..."
        )

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
        # Auto-select optimal model (prioritizing already-downloaded models)
        selected_model = selector.select_default(
            hardware, downloaded_models, downloader
        )
        if not selected_model:
            console.print(
                "[red]Error:[/red] No compatible model found for your hardware"
            )
            sys.exit(1)

    console.print(f"✓ Selected: [green]{selected_model.display_name}[/green]")

    # Step 3: Download model if needed
    # (downloader already initialized above for downloaded models check)
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
        # Pass model_path if available to use local file instead of pulling
        modelfile = config_gen.generate_ollama_modelfile(model_path=config.model_path)
        modelfile_path = ConfigManager.save_ollama_modelfile(modelfile)
        console.print(f"✓ Ollama Modelfile: [green]{modelfile_path}[/green]")

    # Step 7: Print setup instructions
    instructions = config_gen.print_setup_instructions()
    console.print(instructions)

    console.print("[bold green]✓ Initialization complete![/bold green]")
    console.print("\nNext step: [bold]qwenvert start[/bold]\n")


@cli.command()
@click.option(
    "--auto-install",
    is_flag=True,
    help="Automatically install missing dependencies via Homebrew",
)
def start(auto_install: bool) -> None:
    """
    Start qwenvert servers (backend + adapter).

    Starts the backend server (Ollama or llama.cpp) and the qwenvert
    HTTP adapter, then displays connection instructions for Claude Code.
    """
    from .launcher import start_qwenvert_sync

    console.print(f"\n[bold blue]Starting Qwenvert v{__version__}[/bold blue]\n")

    try:
        start_qwenvert_sync()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as e:
        # Check if it's a dependency error
        from .dependencies import (
            DependencyError,
            auto_install_dependency,
            can_auto_install,
            format_missing_dependency_message,
        )

        if isinstance(e, DependencyError):
            # Show clean, user-friendly error message without traceback
            console.print(format_missing_dependency_message(e.result))

            # Offer auto-installation if possible
            dep_name = e.result.name
            if can_auto_install(dep_name):
                console.print()

                # Check if user wants auto-install
                should_install = auto_install or click.confirm(
                    f"Would you like to install {dep_name} automatically using Homebrew?",
                    default=True,
                )

                if should_install:
                    console.print(
                        f"\n[cyan]Installing {dep_name} via Homebrew...[/cyan]"
                    )
                    try:
                        with console.status(
                            f"[cyan]Running: brew install {dep_name.lower()}...",
                            spinner="dots",
                        ):
                            auto_install_dependency(dep_name)

                        console.print(
                            f"[green]✓ {dep_name} installed successfully![/green]"
                        )
                        console.print(
                            "\n[bold]Please run 'qwenvert start' again to continue.[/bold]\n"
                        )
                        sys.exit(0)
                    except Exception as install_error:
                        console.print(
                            f"\n[red]Installation failed:[/red] {install_error}"
                        )
                        console.print(
                            "\n[yellow]Please install manually using the instructions above.[/yellow]"
                        )
                        sys.exit(1)
                else:
                    console.print(
                        "\n[dim]Tip: After installing dependencies, run 'qwenvert start' again.[/dim]"
                    )
                    sys.exit(1)
            else:
                console.print(
                    "\n[dim]Tip: After installing dependencies, run 'qwenvert start' again.[/dim]"
                )
                sys.exit(1)

        # RuntimeError from launcher (e.g., port already in use)
        if isinstance(e, RuntimeError):
            # Show clean error message without traceback
            console.print(f"\n[red]Error:[/red] {e}")
            sys.exit(1)

        # For other unexpected errors, show the full traceback
        console.print(f"\n[red]Error:[/red] {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


@cli.command()
def status() -> None:
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
def stop() -> None:
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
def models() -> None:
    """Model management commands."""


@models.command("list")
@click.option(
    "--backend", type=click.Choice(["ollama", "llamacpp"]), help="Filter by backend"
)
def list_models(backend) -> None:
    """
    List available models.

    Shows all models in the registry with their specifications.
    """
    from .models import Backend, ModelRegistry

    console.print("\n[bold blue]Available Models[/bold blue]\n")

    registry = ModelRegistry()
    backend_filter = Backend(backend) if backend else None

    _list_models_table(registry, backend_filter)

    console.print()


@models.command("clean")
@click.option(
    "--model-id",
    help="Specific model filename to remove (e.g., qwen2.5-coder-7b-instruct-q4_k_m.gguf)",
)
@click.option(
    "--all",
    "all_models",
    is_flag=True,
    help="Remove all downloaded models",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be deleted without actually deleting",
)
def clean_models(model_id, all_models, dry_run) -> None:
    """
    Remove downloaded model files to free disk space.

    Examples:
        qwenvert models clean --model-id qwen2.5-coder-7b-instruct-q4_k_m.gguf
        qwenvert models clean --all
        qwenvert models clean --dry-run
    """
    from pathlib import Path  # noqa: TC003

    from .downloader import ModelDownloader

    console.print("\n[bold blue]Model Cleanup[/bold blue]\n")

    downloader = ModelDownloader()

    # Get list of downloaded models
    downloaded_models = downloader.list_downloaded_models()

    if not downloaded_models:
        console.print("[yellow]No models downloaded yet.[/yellow]\n")
        return

    # Show current disk usage
    _show_disk_usage(downloader)

    # Determine which models to delete
    models_to_delete: list[Path] = []

    if all_models:
        models_to_delete = downloaded_models
    elif model_id:
        # Find model by filename
        matching_model = next(
            (m for m in downloaded_models if m.name == model_id), None
        )
        if matching_model:
            models_to_delete = [matching_model]
        else:
            console.print(f"\n[red]Error:[/red] Model '{model_id}' not found\n")
            console.print("[dim]Available models:[/dim]")
            for model_path in downloaded_models:
                console.print(f"  • {model_path.name}")
            console.print()
            return
    else:
        # Interactive selection
        models_to_delete = _interactive_model_selection(downloaded_models)
        if not models_to_delete:
            console.print("\n[yellow]Cleanup cancelled.[/yellow]\n")
            return

    # Show what will be deleted
    _show_deletion_summary(models_to_delete)

    # Confirm deletion (unless dry-run)
    if not _confirm_deletion(models_to_delete, dry_run):
        return

    # Delete models
    try:
        deleted_count = 0
        total_freed = 0

        with console.status("[cyan]Deleting models...", spinner="dots") as status:
            for model_path in models_to_delete:
                try:
                    success, size = downloader.delete_model_by_path(model_path)
                    if success:
                        deleted_count += 1
                        total_freed += size
                        status.update(
                            f"[cyan]Deleted {deleted_count}/{len(models_to_delete)}..."
                        )
                except Exception as e:
                    console.print(f"\n[red]Error deleting {model_path.name}:[/red] {e}")

        console.print(
            f"\n[green]✓ Cleanup complete![/green] Deleted {deleted_count} "
            f"model(s), freed {total_freed / (1024**3):.2f} GB\n"
        )

        # Show updated disk usage
        console.print("[bold]Updated disk usage:[/bold]")
        _show_disk_usage(downloader)

    except KeyboardInterrupt:
        console.print("\n[yellow]Cleanup interrupted by user[/yellow]\n")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error during cleanup:[/red] {e}\n")
        sys.exit(1)


def _show_disk_usage(downloader) -> None:
    """Display current disk usage statistics."""
    usage = downloader.get_disk_usage()
    console.print(f"[dim]Models disk usage: {usage['total_gb']:.2f} GB[/dim]")
    console.print(f"[dim]Available disk space: {usage['available_gb']:.2f} GB[/dim]\n")


def _show_deletion_summary(models: list) -> None:
    """Show summary of models to be deleted."""
    from pathlib import Path

    console.print("\n[bold]Models to be deleted:[/bold]\n")

    table = Table()
    table.add_column("Filename", style="cyan")
    table.add_column("Size", justify="right", style="yellow")

    total_size = 0
    for model_path in models:
        if isinstance(model_path, Path):
            size = model_path.stat().st_size
            total_size += size
            table.add_row(model_path.name, f"{size / (1024**3):.2f} GB")

    console.print(table)
    console.print(
        f"\n[bold]Total space to free: {total_size / (1024**3):.2f} GB[/bold]"
    )


def _confirm_deletion(model_paths: list, dry_run: bool) -> bool:
    """Confirm model deletion with user."""
    if dry_run:
        console.print(
            "\n[yellow]Dry run - showing preview only, no models will be deleted[/yellow]\n"
        )
        return False

    console.print()
    return click.confirm("Delete these models?", default=False)


def _interactive_model_selection(downloaded_models: list) -> list:
    """Interactively select models to delete."""
    from pathlib import Path

    console.print("[bold]Downloaded models:[/bold]\n")

    # Show numbered list
    for idx, model_path in enumerate(downloaded_models, 1):
        if isinstance(model_path, Path):
            size = model_path.stat().st_size
            console.print(
                f"  {idx}. {model_path.name} [dim]({size / (1024**3):.2f} GB)[/dim]"
            )

    console.print(f"  {len(downloaded_models) + 1}. All models")
    console.print(f"  {len(downloaded_models) + 2}. Cancel")

    # Get user input
    try:
        selection = click.prompt(
            "\nEnter number(s) separated by commas",
            type=str,
            show_default=False,
        )

        # Parse selection and deduplicate
        selected_indices = sorted({int(s.strip()) for s in selection.split(",")})

        # Check for "All" or "Cancel"
        if len(downloaded_models) + 2 in selected_indices:
            return []
        if len(downloaded_models) + 1 in selected_indices:
            return downloaded_models

        # Collect selected models
        models_to_delete = []
        for idx in selected_indices:
            if 1 <= idx <= len(downloaded_models):
                models_to_delete.append(downloaded_models[idx - 1])
            else:
                console.print(
                    f"\n[yellow]Warning:[/yellow] Invalid selection {idx}, skipping"
                )

        return models_to_delete

    except (ValueError, EOFError, KeyboardInterrupt):
        return []


def _list_models_table(registry, backend_filter=None) -> None:
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
def hardware() -> None:
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
@click.option(
    "--enable-otel/--no-otel",
    default=False,
    help="Enable OpenTelemetry metrics (default: disabled)",
)
def monitor(adapter_url, refresh_rate, enable_otel) -> None:
    """
    Real-time monitoring dashboard.

    Displays live performance metrics, system resources, and request history
    in a beautiful terminal interface with OpenTelemetry-compliant metrics.
    """
    import asyncio

    from .config import ConfigManager
    from .dashboard import run_dashboard
    from .telemetry import init_telemetry, shutdown_telemetry

    console.print("\n[bold blue]Starting Qwenvert Monitor[/bold blue]\n")

    # Initialize OpenTelemetry if enabled
    if enable_otel:
        try:
            init_telemetry(
                service_name="qwenvert-monitor",
                service_version=__version__,
                enable_console=False,  # Console exporter would interfere with TUI
                enable_otlp=False,  # User can enable via env vars if needed
                enable_prometheus=False,  # User can enable via env vars if needed
            )
            console.print("[dim]✓ OpenTelemetry metrics enabled[/dim]")
        except Exception as e:
            console.print(
                f"[yellow]Warning:[/yellow] Could not initialize telemetry: {e}"
            )
            console.print("[dim]Continuing without OpenTelemetry...[/dim]")

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
        asyncio.run(
            run_dashboard(
                adapter_url=adapter_url,
                refresh_rate=refresh_rate,
                enable_otel=enable_otel,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped[/yellow]\n")
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        if enable_otel:
            shutdown_telemetry()


@cli.group()
def binary() -> None:
    """Binary management commands for llama-server."""


@binary.command("info")
def binary_info() -> None:
    """Show information about installed llama-server binary."""
    from .binary_manager import BinaryManager

    binary_mgr = BinaryManager()
    binary_info_obj = binary_mgr.detect_binary()

    if not binary_info_obj:
        console.print("[yellow]No llama-server binary found[/yellow]\n")
        console.print("Install with: [cyan]qwenvert binary install[/cyan]")
        console.print("Or use: [cyan]qwenvert init --backend llamacpp[/cyan]\n")
        sys.exit(1)

    # Display binary information in a table
    table = Table(title="llama-server Binary Info", show_header=True)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Path", str(binary_info_obj.path))
    table.add_row("Version", binary_info_obj.version)
    table.add_row("Source", binary_info_obj.source.value)
    table.add_row("Architecture", binary_info_obj.architecture)
    table.add_row("Valid", "✓ Yes" if binary_info_obj.is_valid else "✗ No")

    console.print()
    console.print(table)
    console.print()


@binary.command("install")
@click.option("--version", help="Specific version to install (e.g., b3600)")
@click.option("--force", is_flag=True, help="Force reinstall even if exists")
def binary_install(version: str | None, force: bool) -> None:
    """Install llama-server binary."""
    from .binary_manager import BinaryManager
    from .hardware import HardwareDetector

    binary_mgr = BinaryManager()

    # Check if already installed
    if not force:
        existing = binary_mgr.detect_binary()
        if existing:
            console.print(
                f"[yellow]llama-server already installed:[/yellow] {existing.path}"
            )
            console.print(f"Version: {existing.version}")
            console.print(
                "\nUse [cyan]--force[/cyan] to reinstall or "
                "[cyan]qwenvert binary update[/cyan] to upgrade\n"
            )
            return

    # Detect hardware
    with console.status("[cyan]Detecting hardware...", spinner="dots"):
        detector = HardwareDetector()
        hardware = detector.detect()

    console.print(f"Hardware: {hardware.chip}, {hardware.total_memory_gb}GB\n")

    # Backup existing if forcing
    if force and binary_mgr.binary_path.exists():
        console.print("[cyan]Creating backup...[/cyan]")
        backup_path = binary_mgr.backup_binary()
        if backup_path:
            console.print(f"✓ Backup created: {backup_path}\n")

    # Install
    try:
        if version:
            console.print(f"[cyan]Installing llama-server {version}...[/cyan]\n")
            binary_path = binary_mgr.download_specific_version(version, hardware)
        else:
            console.print("[cyan]Installing latest llama-server...[/cyan]\n")
            binary_path = binary_mgr.download_binary(hardware)

        console.print(f"✓ Successfully installed: [green]{binary_path}[/green]\n")

        # Show version info
        info = binary_mgr.detect_binary()
        if info:
            console.print(f"Version: {info.version}")
            console.print(f"Architecture: {info.architecture}\n")

    except Exception as e:
        console.print(f"[red]Installation failed:[/red] {e}\n")
        sys.exit(1)


@binary.command("update")
def binary_update() -> None:
    """Update llama-server to latest version."""
    from .binary_manager import BinaryManager
    from .hardware import HardwareDetector

    binary_mgr = BinaryManager()

    # Check current version
    current = binary_mgr.get_installed_version()
    if not current:
        console.print("[yellow]No llama-server currently installed[/yellow]\n")
        console.print("Install with: [cyan]qwenvert binary install[/cyan]\n")
        sys.exit(1)

    console.print(f"Current version: {current}")

    # Check latest version
    with console.status("[cyan]Checking for updates...", spinner="dots"):
        try:
            latest = binary_mgr._get_latest_release_version()
        except Exception as e:
            console.print(f"[red]Failed to check for updates:[/red] {e}\n")
            sys.exit(1)

    console.print(f"Latest version: {latest}\n")

    if current == latest:
        console.print("[green]✓ Already up to date[/green]\n")
        return

    # Confirm update
    if not click.confirm(f"Update {current} → {latest}?", default=True):
        console.print("[yellow]Update cancelled[/yellow]\n")
        return

    # Backup current binary
    console.print("\n[cyan]Creating backup...[/cyan]")
    backup_path = binary_mgr.backup_binary()
    if backup_path:
        console.print(f"✓ Backup created: {backup_path}\n")

    # Download latest
    try:
        detector = HardwareDetector()
        hardware = detector.detect()

        console.print(f"[cyan]Downloading llama-server {latest}...[/cyan]\n")
        binary_path = binary_mgr.download_binary(hardware)

        console.print(f"✓ Successfully updated to {latest}\n")

        # Verify
        info = binary_mgr.detect_binary()
        if info:
            console.print(f"Version: {info.version}")
            console.print(f"Path: {info.path}\n")

    except Exception as e:
        console.print(f"[red]Update failed:[/red] {e}\n")
        console.print("[yellow]Rollback available:[/yellow] qwenvert binary rollback\n")
        sys.exit(1)


@binary.command("list")
@click.option("--limit", default=10, help="Number of versions to show (default: 10)")
def binary_list(limit: int) -> None:
    """List available llama-server versions from GitHub."""
    from .binary_manager import BinaryManager

    binary_mgr = BinaryManager()

    with console.status("[cyan]Fetching releases from GitHub...", spinner="dots"):
        versions = binary_mgr.list_available_versions(limit=limit)

    if not versions:
        console.print("[yellow]Could not fetch releases from GitHub[/yellow]\n")
        sys.exit(1)

    # Get currently installed version
    current = binary_mgr.get_installed_version()

    # Display versions in a table
    table = Table(title=f"Available llama.cpp Releases (latest {limit})")
    table.add_column("Version", style="cyan")
    table.add_column("Date", style="dim")
    table.add_column("Status", style="green")

    for ver in versions:
        version_str = ver["version"]
        date_str = ver["date"].split("T")[0] if "T" in ver["date"] else ver["date"]

        # Mark current version
        status = ""
        if version_str == current:
            status = "✓ Installed"

        # Mark prerelease
        if ver.get("prerelease"):
            version_str += " [dim](prerelease)[/dim]"

        table.add_row(version_str, date_str, status)

    console.print()
    console.print(table)
    console.print()

    if current:
        console.print(f"Currently installed: [green]{current}[/green]")
    console.print(
        "\nInstall specific version: [cyan]qwenvert binary install --version <version>[/cyan]\n"
    )


@binary.command("verify")
def binary_verify() -> None:
    """Verify installed binary integrity."""
    from .binary_manager import BinaryManager

    binary_mgr = BinaryManager()

    console.print("[cyan]Verifying llama-server binary...[/cyan]\n")

    # Check existence
    if not binary_mgr.binary_path.exists():
        console.print(f"✗ Binary not found: {binary_mgr.binary_path}\n")
        sys.exit(1)

    console.print(f"✓ Binary exists: {binary_mgr.binary_path}")

    # Check if executable
    if not binary_mgr.binary_path.stat().st_mode & stat.S_IEXEC:
        console.print("✗ Binary is not executable\n")
        sys.exit(1)

    console.print("✓ Binary is executable")

    # Test execution
    try:
        import subprocess

        result = subprocess.run(
            [str(binary_mgr.binary_path), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        if result.returncode == 0:
            console.print("✓ Binary runs successfully")
            console.print(f"  Output: {result.stdout.strip()[:100]}")
        else:
            console.print(f"✗ Binary execution failed (exit code {result.returncode})")
            sys.exit(1)

    except Exception as e:
        console.print(f"✗ Binary execution failed: {e}\n")
        sys.exit(1)

    # Get full info
    info = binary_mgr.detect_binary()
    if info and info.is_valid:
        console.print("\n[green]✓ Binary verification passed[/green]")
        console.print(f"  Version: {info.version}")
        console.print(f"  Architecture: {info.architecture}")
        console.print(f"  Source: {info.source.value}\n")
    else:
        console.print("\n[yellow]⚠ Binary validation warnings detected[/yellow]\n")
        sys.exit(1)


@binary.command("rollback")
def binary_rollback() -> None:
    """Rollback to previous binary version from backup."""
    from .binary_manager import BinaryManager

    binary_mgr = BinaryManager()

    # Check for backups
    backup_files = list(binary_mgr.bin_dir.glob(f"{binary_mgr.BINARY_NAME}.backup.*"))

    if not backup_files:
        console.print("[yellow]No backup files found[/yellow]\n")
        console.print(
            "Backups are created automatically during updates and forced installs.\n"
        )
        return

    # Show available backups
    backup_files.sort(reverse=True)
    console.print(f"\nFound {len(backup_files)} backup(s):\n")

    for backup in backup_files[:5]:  # Show up to 5 most recent
        timestamp = int(backup.suffix.split(".")[-1])
        import datetime

        date_str = datetime.datetime.fromtimestamp(timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        console.print(f"  {backup.name} ({date_str})")

    console.print()

    # Confirm rollback
    if not click.confirm("Rollback to most recent backup?", default=True):
        console.print("[yellow]Rollback cancelled[/yellow]\n")
        return

    # Perform rollback
    console.print("\n[cyan]Rolling back...[/cyan]")

    if binary_mgr.rollback_binary():
        console.print("[green]✓ Successfully rolled back[/green]\n")

        # Show current version
        info = binary_mgr.detect_binary()
        if info:
            console.print(f"Current version: {info.version}")
            console.print(f"Path: {info.path}\n")
    else:
        console.print("[red]✗ Rollback failed[/red]\n")
        sys.exit(1)


@cli.command("backends")
def backends_command() -> None:
    """Detect and show available LLM backends."""
    from .backend_interface import BackendStatus
    from .backend_manager import BackendManager

    console.print("\n[cyan]Detecting available backends...[/cyan]\n")

    all_backends = BackendManager.detect_all()

    # Display backends in a table
    table = Table(title="Available Backends")
    table.add_column("Backend", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Version", style="dim")
    table.add_column("Path", style="dim")
    table.add_column("Installation", style="dim")

    for backend_type, info in all_backends.items():
        status_icon = {
            BackendStatus.AVAILABLE: "✓ Available",
            BackendStatus.MISSING: "✗ Missing",
            BackendStatus.INSTALLING: "⟳ Installing",
            BackendStatus.FAILED: "✗ Failed",
        }.get(info.status, info.status.value)

        # Color code status
        if info.status == BackendStatus.AVAILABLE:
            status_str = f"[green]{status_icon}[/green]"
        elif info.status == BackendStatus.MISSING:
            status_str = f"[yellow]{status_icon}[/yellow]"
        else:
            status_str = f"[red]{status_icon}[/red]"

        table.add_row(
            info.name,
            status_str,
            info.version or "-",
            str(info.path) if info.path else "-",
            info.installation_method,
        )

    console.print(table)
    console.print()

    # Show recommendation
    from .hardware import HardwareDetector

    detector = HardwareDetector()
    hardware = detector.detect()
    recommended = BackendManager.recommend_backend()

    console.print(f"Recommended backend: [cyan]{recommended.value}[/cyan]")
    console.print(f"  (Based on: {hardware.chip}, {hardware.total_memory_gb}GB RAM)\n")

    # Show installation commands
    console.print("[dim]Install missing backends:[/dim]")
    console.print("  llama.cpp: [cyan]qwenvert binary install[/cyan]")
    console.print("  Ollama:    [cyan]brew install ollama[/cyan]\n")


if __name__ == "__main__":
    cli()
