"""llama.cpp backend implementation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from ..backend_interface import BackendInfo, BackendLifecycle, BackendStatus
from ..binary_manager import BinaryManager

if TYPE_CHECKING:
    from ..hardware import HardwareProfile
    from ..models import Model


logger = logging.getLogger(__name__)


class LlamaCppBackend(BackendLifecycle):
    """llama.cpp backend implementation."""

    def __init__(self) -> None:
        """Initialize llama.cpp backend."""
        self.binary_manager = BinaryManager()
        self.server_url = "http://localhost:8080"

    def detect(self) -> BackendInfo:
        """Detect llama-server binary."""
        binary_info = self.binary_manager.detect_binary()

        if binary_info:
            return BackendInfo(
                name="llama.cpp",
                version=binary_info.version,
                path=binary_info.path,
                status=BackendStatus.AVAILABLE,
                installation_method=binary_info.source.value,
            )

        return BackendInfo(
            name="llama.cpp",
            version=None,
            path=None,
            status=BackendStatus.MISSING,
            installation_method="none",
        )

    def install(self, auto: bool = True) -> BackendInfo:
        """Install llama-server binary."""
        try:
            binary_info_obj = self.binary_manager.get_or_install_binary(
                hardware=None,  # Auto-detect
                auto_install=auto,
            )

            return BackendInfo(
                name="llama.cpp",
                version=binary_info_obj.version,
                path=binary_info_obj.path,
                status=BackendStatus.AVAILABLE,
                installation_method=binary_info_obj.source.value,
            )

        except RuntimeError as e:
            logger.error(f"Failed to install llama.cpp: {e}")
            return BackendInfo(
                name="llama.cpp",
                version=None,
                path=None,
                status=BackendStatus.FAILED,
                installation_method="none",
            )

    def configure(self, model: Model, hardware: HardwareProfile) -> dict:
        """Generate llama.cpp configuration."""
        from ..config import ConfigGenerator

        config_gen = ConfigGenerator(model, hardware)
        flags = config_gen.generate_llamacpp_flags()

        return {
            "binary_path": self.binary_manager.get_binary_path(),
            "flags": flags,
            "server_url": self.server_url,
        }

    def get_server_url(self) -> str:
        """Get llama.cpp server URL."""
        return self.server_url

    def health_check(self) -> bool:
        """Check llama.cpp server health."""
        try:
            response = httpx.get(
                f"{self.server_url}/health",
                timeout=2.0,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False
