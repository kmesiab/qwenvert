"""
Server launcher and process management.

Manages lifecycle of backend servers (Ollama, llama.cpp) and
qwenvert adapter, including health checks and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import logging
import signal
import socket
import subprocess
import time
from pathlib import Path

import httpx

from .config import ConfigManager, QwenvertConfig
from .dependencies import (
    DependencyError,
    check_llamacpp,
    check_ollama,
)
from .models import Backend
from .security import validate_adapter_host, validate_localhost_url


logger = logging.getLogger(__name__)


class ProcessHandle:
    """Handle for a managed process."""

    def __init__(
        self, process: subprocess.Popen | None, name: str, is_unmanaged: bool = False
    ) -> None:
        self.process = process
        self.name = name
        self.pid = process.pid if process else None
        self.is_unmanaged = is_unmanaged

    @classmethod
    def unmanaged(cls, name: str) -> ProcessHandle:
        """Create an unmanaged process handle for externally-running processes."""
        return cls(process=None, name=name, is_unmanaged=True)

    def is_running(self) -> bool:
        """Check if process is still running."""
        if self.is_unmanaged or self.process is None:
            return False
        return self.process.poll() is None

    def terminate(self, timeout: int = 10) -> bool:
        """
        Gracefully terminate process.

        Args:
            timeout: Seconds to wait before force kill

        Returns:
            True if terminated successfully
        """
        if self.is_unmanaged or self.process is None:
            return True

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

    def __init__(self, config: QwenvertConfig) -> None:
        """
        Initialize server launcher.

        Args:
            config: Qwenvert configuration
        """
        self.config = config
        self.backend_process: ProcessHandle | None = None
        self.adapter_process: ProcessHandle | None = None

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
        if self.config.backend == Backend.LLAMACPP.value:
            return await self._start_llamacpp()
        raise ValueError(f"Unknown backend: {self.config.backend}")

    async def _start_ollama(self) -> ProcessHandle:
        """Start Ollama server."""
        logger.info("Starting Ollama server...")

        # Check if ollama is installed
        ollama_check = check_ollama()
        if not ollama_check.is_available:
            # Raise DependencyError without logging (CLI will display clean message)
            raise DependencyError(ollama_check)

        # Check if server is already running
        if await self._check_health("http://localhost:11434"):
            logger.info("Ollama server already running")
            # Still need to ensure model is available!
            await self._ensure_ollama_model()
            # Return unmanaged handle (we don't own this process)
            return ProcessHandle.unmanaged("ollama-existing")

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
            msg = "Ollama server failed to start"
            raise RuntimeError(msg)

        # Ensure model is pulled
        await self._ensure_ollama_model()

        logger.info("✓ Ollama server ready")
        return handle

    async def _start_llamacpp(self) -> ProcessHandle:
        """Start llama.cpp server."""
        logger.info("Starting llama.cpp server...")

        # Check if llama-server is available
        llamacpp_check = check_llamacpp()
        if not llamacpp_check.is_available:
            # Raise DependencyError without logging (CLI will display clean message)
            raise DependencyError(llamacpp_check)

        if not llamacpp_check.path:
            raise RuntimeError("llama-server path is not available")

        llamacpp_path = Path(llamacpp_check.path)

        # Generate flags from config
        from .config import ConfigGenerator
        from .models import ModelRegistry

        registry = ModelRegistry()
        model = registry.get_model(self.config.model_id)
        if not model:
            raise RuntimeError(f"Model {self.config.model_id} not found")

        # Detect actual hardware or use conservative fallback
        from .hardware import HardwareDetector, HardwareProfile

        try:
            hardware = HardwareDetector.detect()
        except Exception as e:
            logger.warning(
                f"Hardware detection failed: {e}, using conservative defaults"
            )
            # Conservative fallback for safety
            hardware = HardwareProfile(
                chip="Unknown",
                chip_family="M1",
                total_memory_gb=8,
                gpu_cores=8,
                cpu_cores_performance=4,
                cpu_cores_efficiency=4,
                has_active_cooling=False,
                neural_engine_cores=16,
                model_identifier="Unknown",
            )

        config_gen = ConfigGenerator(model, hardware)
        flags = config_gen.generate_llamacpp_flags()

        # Start llama-server
        cmd = [str(llamacpp_path), *flags]
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
            msg = "llama.cpp server failed to start"
            raise RuntimeError(msg)

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
            # Check if we have a local model file and Modelfile
            modelfile_path = ConfigManager.get_ollama_modelfile_path()
            model_path = (
                Path(self.config.model_path) if self.config.model_path else None
            )

            if model_path and model_path.exists() and modelfile_path.exists():
                # Create model from local file using Modelfile
                logger.info(f"Creating model from local file: {model_path}...")
                subprocess.run(
                    [
                        "ollama",
                        "create",
                        self.config.backend_model_id,
                        "-f",
                        str(modelfile_path),
                    ],
                    check=True,
                )
                logger.info("✓ Model created from local file")
            else:
                # Fall back to pulling from Ollama registry
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
        Start qwenvert adapter server with OpenTelemetry instrumentation.

        Args:
            backend_handle: Handle to backend server process

        Raises:
            SecurityValidationError: If adapter_host or backend_url is not localhost
        """
        logger.info("Starting qwenvert adapter...")

        # SECURITY: Validate adapter host is localhost-only
        validate_adapter_host(self.config.adapter_host)
        logger.info(
            f"Security: Validated adapter host '{self.config.adapter_host}' is localhost"
        )

        # Initialize OpenTelemetry
        from .telemetry import init_telemetry, instrument_fastapi

        try:
            init_telemetry(
                service_name="qwenvert-adapter",
                service_version="0.1.0",
                enable_console=False,
                enable_otlp=False,  # Can be enabled via env vars
                enable_prometheus=False,  # Can be enabled via env vars
            )
            logger.info("✓ OpenTelemetry initialized")
        except Exception as e:
            logger.warning(f"Could not initialize OpenTelemetry: {e}")
            logger.info("Continuing without OpenTelemetry instrumentation...")

        # Import adapter and router
        from .adapter import create_app
        from .models import ModelRegistry
        from .router import BackendRouter

        # Get model
        registry = ModelRegistry()
        model = registry.get_model(self.config.model_id)
        if not model:
            raise RuntimeError(f"Model {self.config.model_id} not found")

        # Create router (validates backend_url)
        router = BackendRouter(model, self.config.backend_url)

        # Create and configure app
        app = create_app()
        app.state.backend_router = router

        # Instrument FastAPI app with OpenTelemetry
        try:
            instrument_fastapi(app)
        except Exception as e:
            logger.warning(f"Could not instrument FastAPI: {e}")

        # Check if port is available before trying to bind
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind((self.config.adapter_host, self.config.adapter_port))
        except OSError as e:
            if e.errno == errno.EADDRINUSE:
                raise RuntimeError(
                    f"Port {self.config.adapter_port} is already in use.\n\n"
                    f"Another process is using port {self.config.adapter_port}. "
                    f"This could be:\n"
                    f"  • Another qwenvert instance already running\n"
                    f"  • A different application using the same port\n\n"
                    f"Solutions:\n"
                    f"  1. Stop the other qwenvert instance: qwenvert stop\n"
                    f"  2. Find and kill the process: lsof -ti:{self.config.adapter_port} | xargs kill\n"
                    f"  3. Use a different port: qwenvert init --adapter-port <PORT>\n"
                ) from e
            raise

        # Start server in background
        import uvicorn

        # Filter out noisy health check logs
        class HealthCheckFilter(logging.Filter):
            """Filter to suppress health check endpoint logs."""

            def filter(self, record: logging.LogRecord) -> bool:
                """Return False to suppress health check logs."""
                return "/health" not in record.getMessage()

        config = uvicorn.Config(
            app,
            host=self.config.adapter_host,
            port=self.config.adapter_port,
            log_level="info",
        )

        server = uvicorn.Server(config)

        # Apply health check filter to uvicorn's access logger
        uvicorn_access_logger = logging.getLogger("uvicorn.access")
        uvicorn_access_logger.addFilter(HealthCheckFilter())

        # Run server in asyncio task (non-blocking)
        self.adapter_task = asyncio.create_task(server.serve())

        # Wait for adapter to be ready
        adapter_url = f"http://{self.config.adapter_host}:{self.config.adapter_port}"
        if not await self._wait_for_health(f"{adapter_url}/health", timeout=10):
            msg = "Qwenvert adapter failed to start"
            raise RuntimeError(msg)

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
        backend_url = self.config.backend_url
        model_name = self.config.backend_model_id

        print("\n" + "=" * 70)
        print("🚀 Qwenvert is running!")
        print("=" * 70)
        print(f"\n📡 Adapter:  {adapter_url}")
        print(f"🔧 Backend:  {backend_url}")
        print(f"🤖 Model:    {model_name}")
        print("\n💡 Configure Claude Code:")
        print(f"   export ANTHROPIC_BASE_URL={adapter_url}")
        print("   export ANTHROPIC_API_KEY=local-qwen")
        print("   export ANTHROPIC_MODEL=qwenvert-default")
        print("\n" + "=" * 70 + "\n")

    async def stop_all(self) -> None:
        """Stop all managed processes and shutdown telemetry."""
        logger.info("Stopping qwenvert...")

        # Stop adapter
        if hasattr(self, "adapter_task"):
            self.adapter_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.adapter_task

        # Stop backend
        if self.backend_process:
            self.backend_process.terminate()

        # Shutdown telemetry
        from .telemetry import shutdown_telemetry

        shutdown_telemetry()

        logger.info("✓ Qwenvert stopped")

    async def _check_health(self, url: str) -> bool:
        """
        Check if server is healthy.

        Args:
            url: Health check URL

        Returns:
            True if server is healthy

        Raises:
            SecurityValidationError: If URL is not localhost
        """
        # SECURITY: Validate URL before making HTTP request
        validate_localhost_url(url)

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


async def start_qwenvert() -> None:
    """
    Main entry point for starting qwenvert.

    Loads config, starts servers, and handles shutdown signals.
    """
    # Load config
    if not ConfigManager.exists():
        return

    config = ConfigManager.load()

    # Create launcher
    launcher = ServerLauncher(config)

    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def handle_shutdown(signum, frame) -> None:
        # Schedule shutdown coroutine in a thread-safe way
        asyncio.run_coroutine_threadsafe(launcher.stop_all(), loop)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Start servers
    try:
        await launcher.start_all()

        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        await launcher.stop_all()
    except DependencyError:
        # Re-raise dependency errors without logging traceback
        # CLI will handle displaying the clean error message
        await launcher.stop_all()
        raise
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await launcher.stop_all()
        raise


def start_qwenvert_sync() -> None:
    """Synchronous wrapper for CLI."""
    asyncio.run(start_qwenvert())
