"""MLX backend implementation for Apple Silicon."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from qwenvert.backend_interface import BackendInfo, BackendLifecycle, BackendStatus


if TYPE_CHECKING:
    from qwenvert.hardware import HardwareProfile
    from qwenvert.models import Model


logger = logging.getLogger(__name__)


class MLXBackend(BackendLifecycle):
    """MLX backend implementation for Apple Silicon."""

    def __init__(self) -> None:
        """Initialize MLX backend."""
        self.server_url = "in-process"

    def detect(self) -> BackendInfo:
        """Detect MLX installation."""
        try:
            import mlx.core  # noqa: F401
            import mlx_lm

            version = getattr(mlx_lm, "__version__", "unknown")
            mlx_path = Path(mlx_lm.__file__).parent if hasattr(mlx_lm, "__file__") else None

            return BackendInfo(
                name="MLX",
                version=version,
                path=mlx_path,
                status=BackendStatus.AVAILABLE,
                installation_method="pip",
            )
        except ImportError:
            return BackendInfo(
                name="MLX",
                version=None,
                path=None,
                status=BackendStatus.MISSING,
                installation_method="none",
            )

    def install(self, auto: bool = True) -> BackendInfo:
        """Install MLX via pip."""
        if not auto:
            raise RuntimeError(
                "MLX not found and auto-install disabled. "
                "Install manually: pip install mlx mlx-lm"
            )

        # Check if running on Apple Silicon (not just macOS)
        import platform

        if sys.platform != "darwin":
            logger.warning("MLX is only supported on macOS")
            return BackendInfo(
                name="MLX",
                version=None,
                path=None,
                status=BackendStatus.FAILED,
                installation_method="none",
            )

        if platform.machine() != "arm64":
            logger.warning("MLX requires Apple Silicon (M1/M2/M3/M4/M5)")
            return BackendInfo(
                name="MLX",
                version=None,
                path=None,
                status=BackendStatus.FAILED,
                installation_method="none",
            )

        logger.info("Installing MLX via pip...")

        try:
            # Install mlx and mlx-lm
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "mlx", "mlx-lm"],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )

            if result.returncode != 0:
                logger.warning(f"pip installation failed: {result.stderr}")
                return BackendInfo(
                    name="MLX",
                    version=None,
                    path=None,
                    status=BackendStatus.FAILED,
                    installation_method="none",
                )

            logger.info("Successfully installed MLX via pip")
            return self.detect()

        except subprocess.TimeoutExpired:
            logger.warning("pip installation timed out")
            return BackendInfo(
                name="MLX",
                version=None,
                path=None,
                status=BackendStatus.FAILED,
                installation_method="none",
            )
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Failed to install via pip: {e}")
            return BackendInfo(
                name="MLX",
                version=None,
                path=None,
                status=BackendStatus.FAILED,
                installation_method="none",
            )

    def configure(self, model: Model, hardware: HardwareProfile) -> dict:
        """Generate MLX configuration."""
        # MLX uses HuggingFace model repos, typically from mlx-community
        # Extract the model path from backend_model_id or huggingface_repo
        model_path = model.huggingface_repo or model.backend_model_id

        # Map quantization to MLX format (q4, q8, etc.)
        # MLX uses lowercase quantization identifiers
        quantization = model.quantization.lower() if model.quantization else None

        return {
            "model_path": model_path,
            "quantization": quantization,
            "max_tokens": model.max_output_tokens,
            "server_url": self.server_url,
        }

    def get_server_url(self) -> str:
        """Get MLX server URL."""
        return self.server_url

    def health_check(self) -> bool:
        """Check if MLX is functional."""
        try:
            import mlx.core as mx

            # Try to set the default device to GPU
            mx.set_default_device(mx.gpu)
            return True
        except Exception:
            logger.exception("MLX health check failed")
            return False
