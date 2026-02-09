"""
Server launcher and process management.

Manages lifecycle of backend servers (Ollama, llama.cpp) and
qwenvert adapter, including health checks and graceful shutdown.
"""

import asyncio
import logging
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx

from .config import ConfigManager, QwenvertConfig
from .models import Backend

logger = logging.getLogger(__name__)


class ProcessHandle:
    """Handle for a managed process."""

    def __init__(self, process: subprocess.Popen, name: str):
        self.process = process
        self.name = name
        self.pid = process.pid

    def is_running(self) -> bool:
        """Check if process is still running."""
        return self.process.poll() is None

    def terminate(self, timeout: int = 10) -> bool:
        """
        Gracefully terminate process.

        Args:
            timeout: Seconds to wait before force kill

        Returns:
            True if terminated successfully
        """
        if not self.is_running():
            return True

        logger.info(f"Terminating {self.name} (PID {self.pid})...")

        # Try graceful shutdown
        self.process.terminate()

        try:
            self.process.wait(timeout=timeout)
            logger.info(f"{self.name} terminated gracefully")
            return True
        except subprocess.TimeoutExpired:
            # Force kill
            logger.warning(f"{self.name} did not terminate, force killing...")
            self.process.kill()
            self.process.wait()
            logger.info(f"{self.name} killed")
            return True


class ServerLauncher:
    """
    Manages backend and adapter server processes.
    """

    def __init__(self, config: QwenvertConfig):
        """
        Initialize server launcher.

        Args:
            config: Qwenvert configuration
        """
        self.config = config
        self.backend_process: Optional[ProcessHandle] = None
        self.adapter_process: Optional[ProcessHandle] = None

    async def start_backend(self) -> ProcessHandle:
        """
        Start backend server (Ollama or llama.cpp).

        Returns:
            ProcessHandle for backend server

        Raises:
            RuntimeError: If backend fails to start
        """
        if self.config.backend == Backend.OLLAMA.value:
            return await self._start_ollama()
        elif self.config.backend == Backend.LLAMACPP.value:
            return await self._start_llamacpp()
        else:
            raise ValueError(f"Unknown backend: {self.config.backend}")

    async def _start_ollama(self) -> ProcessHandle:
        """Start Ollama server."""
        logger.info("Starting Ollama server...")

        # Check if ollama is installed
        if not shutil.which("ollama"):
            raise RuntimeError(
                "Ollama not found. Install with: brew install ollama"
            )

        # Check if server is already running
        if await self._check_health("http://localhost:11434"):
            logger.info("Ollama server already running")
            # Return placeholder handle (we don't own this process)
            return ProcessHandle(
                subprocess.Popen(["echo"], stdout=subprocess.DEVNULL),
                "ollama-existing"
            )

        # Start Ollama server
        process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,  # Detach from parent
        )

        handle = ProcessHandle(process, "ollama")
        logger.info(f"Ollama server started (PID {handle.pid})")

        # Wait for server to be ready
        if not await self._wait_for_health("http://localhost:11434", timeout=30):
            handle.terminate()
            raise RuntimeError("Ollama server failed to start")

        # Ensure model is pulled
        await self._ensure_ollama_model()

        logger.info("✓ Ollama server ready")
        return handle

    async def _start_llamacpp(self) -> ProcessHandle:
        """Start llama.cpp server."""
        logger.info("Starting llama.cpp server...")

        # Check if llama-server is available
        llamacpp_path = Path.home() / ".local" / "bin" / "llama-server"
        if not llamacpp_path.exists():
            # Try common locations
            for alt_path in ["/usr/local/bin/llama-server", "./llama-server"]:
                if Path(alt_path).exists():
                    llamacpp_path = Path(alt_path)
                    break
            else:
                raise RuntimeError(
                    "llama-server not found. Install llama.cpp first."
                )

        # Generate flags from config
        from .config import ConfigGenerator
        from .models import ModelRegistry

        registry = ModelRegistry()
        model = registry.get_model(self.config.model_id)
        if not model:
            raise RuntimeError(f"Model {self.config.model_id} not found")

        # Placeholder hardware (we don't have it here, but flags are mostly static)
        from .hardware import HardwareProfile
        hardware = HardwareProfile(
            chip="M1", chip_family="M1", total_memory_gb=16,
            gpu_cores=8, cpu_cores_performance=4, cpu_cores_efficiency=4,
            has_active_cooling=True, neural_engine_cores=16,
            model_identifier="Unknown"
        )

        config_gen = ConfigGenerator(model, hardware)
        flags = config_gen.generate_llamacpp_flags()

        # Start llama-server
        cmd = [str(llamacpp_path)] + flags
        logger.info(f"Running: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        handle = ProcessHandle(process, "llama-cpp")
        logger.info(f"llama.cpp server started (PID {handle.pid})")

        # Wait for server to be ready
        if not await self._wait_for_health("http://localhost:8080/health", timeout=60):
            handle.terminate()
            raise RuntimeError("llama.cpp server failed to start")

        logger.info("✓ llama.cpp server ready")
        return handle

    async def _ensure_ollama_model(self) -> None:
        """Ensure Ollama model is pulled and ready."""
        logger.info(f"Checking model: {self.config.backend_model_id}...")

        # Check if model exists
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
        )

        if self.config.backend_model_id not in result.stdout:
            logger.info(f"Pulling model {self.config.backend_model_id}...")
            subprocess.run(
                ["ollama", "pull", self.config.backend_model_id],
                check=True,
            )
            logger.info("✓ Model pulled")
        else:
            logger.info("✓ Model already available")

    async def start_adapter(self, backend_handle: ProcessHandle) -> None:
        """
        Start qwenvert adapter server.

        Args:
            backend_handle: Handle to backend server process
        """
        logger.info("Starting qwenvert adapter...")

        # Import adapter and router
        from .adapter import create_app
        from .router import BackendRouter
        from .models import ModelRegistry

        # Get model
        registry = ModelRegistry()
        model = registry.get_model(self.config.model_id)
        if not model:
            raise RuntimeError(f"Model {self.config.model_id} not found")

        # Create router
        router = BackendRouter(model, self.config.backend_url)

        # Create and configure app
        app = create_app()
        app.state.backend_router = router

        # Start server in background
        import uvicorn

        config = uvicorn.Config(
            app,
            host=self.config.adapter_host,
            port=self.config.adapter_port,
            log_level="info",
        )

        server = uvicorn.Server(config)

        # Run server in asyncio task (non-blocking)
        self.adapter_task = asyncio.create_task(server.serve())

        # Wait for adapter to be ready
        adapter_url = f"http://{self.config.adapter_host}:{self.config.adapter_port}"
        if not await self._wait_for_health(f"{adapter_url}/health", timeout=10):
            raise RuntimeError("Qwenvert adapter failed to start")

        logger.info(f"✓ Qwenvert adapter ready on {adapter_url}")

    async def start_all(self) -> None:
        """
        Start backend and adapter servers.

        Raises:
            RuntimeError: If any server fails to start
        """
        # Start backend
        self.backend_process = await self.start_backend()

        # Start adapter
        await self.start_adapter(self.backend_process)

        # Print success message
        self._print_startup_success()

    def _print_startup_success(self) -> None:
        """Print startup success message with instructions."""
        adapter_url = f"http://{self.config.adapter_host}:{self.config.adapter_port}"

        print("\n" + "=" * 70)
        print("✓ Qwenvert is running!")
        print("=" * 70)
        print(f"\nBackend:  {self.config.backend} on {self.config.backend_url}")
        print(f"Adapter:  {adapter_url}")
        print(f"Model:    {self.config.backend_model_id}")
        print(f"\nConfigure Claude Code:\n")
        print(f"  export ANTHROPIC_BASE_URL=\"{adapter_url}\"")
        print(f"  export ANTHROPIC_API_KEY=\"local-qwen\"")
        print(f"  export ANTHROPIC_MODEL=\"qwenvert-default\"")
        print(f"\nThen run: claude\n")
        print("=" * 70 + "\n")

    async def stop_all(self) -> None:
        """Stop all managed processes."""
        logger.info("Stopping qwenvert...")

        # Stop adapter
        if hasattr(self, 'adapter_task'):
            self.adapter_task.cancel()
            try:
                await self.adapter_task
            except asyncio.CancelledError:
                pass

        # Stop backend
        if self.backend_process:
            self.backend_process.terminate()

        logger.info("✓ Qwenvert stopped")

    async def _check_health(self, url: str) -> bool:
        """
        Check if server is healthy.

        Args:
            url: Health check URL

        Returns:
            True if server is healthy
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=2.0)
                return response.status_code == 200
        except Exception:
            return False

    async def _wait_for_health(self, url: str, timeout: int = 30) -> bool:
        """
        Wait for server to become healthy.

        Args:
            url: Health check URL
            timeout: Maximum seconds to wait

        Returns:
            True if server became healthy, False if timeout
        """
        start = time.time()

        while time.time() - start < timeout:
            if await self._check_health(url):
                return True
            await asyncio.sleep(1)

        return False


async def start_qwenvert():
    """
    Main entry point for starting qwenvert.

    Loads config, starts servers, and handles shutdown signals.
    """
    # Load config
    if not ConfigManager.exists():
        print("Error: No configuration found. Run 'qwenvert init' first.")
        return

    config = ConfigManager.load()

    # Create launcher
    launcher = ServerLauncher(config)

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    def handle_shutdown(signum, frame):
        print("\n\nShutting down...")
        asyncio.create_task(launcher.stop_all())
        loop.stop()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Start servers
    try:
        await launcher.start_all()

        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await launcher.stop_all()
        raise


def start_qwenvert_sync():
    """Synchronous wrapper for CLI."""
    asyncio.run(start_qwenvert())
