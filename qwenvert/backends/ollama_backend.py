"""Ollama backend implementation."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from qwenvert.backend_interface import BackendInfo, BackendLifecycle, BackendStatus


if TYPE_CHECKING:
    from qwenvert.hardware import HardwareProfile
    from qwenvert.models import Model


logger = logging.getLogger(__name__)


class OllamaBackend(BackendLifecycle):
    """Ollama backend implementation."""

    def __init__(self) -> None:
        """Initialize Ollama backend."""
        self.server_url = "http://localhost:11434"

    def detect(self) -> BackendInfo:
        """Detect Ollama installation."""
        ollama_path = shutil.which("ollama")

        if ollama_path:
            # Try to get version
            import subprocess

            try:
                result = subprocess.run(
                    [ollama_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )

                if result.returncode == 0:
                    parts = result.stdout.strip().split()
                    version = parts[-1] if parts else "unknown"
                else:
                    version = "unknown"

            except (subprocess.TimeoutExpired, subprocess.SubprocessError, IndexError):
                version = "unknown"

            return BackendInfo(
                name="ollama",
                version=version,
                path=Path(ollama_path) if ollama_path else None,
                status=BackendStatus.AVAILABLE,
                installation_method="system",
            )

        return BackendInfo(
            name="ollama",
            version=None,
            path=None,
            status=BackendStatus.MISSING,
            installation_method="none",
        )

    def install(self, auto: bool = True) -> BackendInfo:
        """Install Ollama via Homebrew."""
        if not auto:
            raise RuntimeError(
                "Ollama not found and auto-install disabled. "
                "Install manually: brew install ollama"
            )

        # Try Homebrew installation
        brew_path = shutil.which("brew")
        if not brew_path:
            logger.warning("Homebrew not found - cannot auto-install Ollama")
            return BackendInfo(
                name="ollama",
                version=None,
                path=None,
                status=BackendStatus.FAILED,
                installation_method="none",
            )

        logger.info("Installing Ollama via Homebrew...")

        try:
            import subprocess

            result = subprocess.run(
                [brew_path, "install", "ollama"],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )

            if result.returncode != 0:
                logger.warning(f"Homebrew installation failed: {result.stderr}")
                return BackendInfo(
                    name="ollama",
                    version=None,
                    path=None,
                    status=BackendStatus.FAILED,
                    installation_method="none",
                )

            logger.info("Successfully installed Ollama via Homebrew")
            return self.detect()

        except subprocess.TimeoutExpired:
            logger.warning("Homebrew installation timed out")
            return BackendInfo(
                name="ollama",
                version=None,
                path=None,
                status=BackendStatus.FAILED,
                installation_method="none",
            )
        except (subprocess.SubprocessError, OSError) as e:
            logger.warning(f"Failed to install via Homebrew: {e}")
            return BackendInfo(
                name="ollama",
                version=None,
                path=None,
                status=BackendStatus.FAILED,
                installation_method="none",
            )

    def configure(self, model: Model, hardware: HardwareProfile) -> dict:
        """Generate Ollama configuration."""
        from qwenvert.config import ConfigGenerator

        config_gen = ConfigGenerator(model, hardware)
        modelfile_content = config_gen.generate_ollama_modelfile()

        return {
            "modelfile": modelfile_content,
            "server_url": self.server_url,
            "model_id": model.backend_model_id,
        }

    def get_server_url(self) -> str:
        """Get Ollama server URL."""
        return self.server_url

    def health_check(self) -> bool:
        """Check Ollama server health."""
        try:
            response = httpx.get(
                f"{self.server_url}/api/tags",
                timeout=2.0,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False
