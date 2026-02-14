"""
Backend abstraction layer for qwenvert.

Provides unified interface for different LLM backends (Ollama, llama.cpp, MLX, vLLM).
Enables clean separation between qwenvert core and backend implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .hardware import HardwareProfile
    from .models import Model


class BackendStatus(Enum):
    """Backend availability status."""

    AVAILABLE = "available"
    MISSING = "missing"
    INSTALLING = "installing"
    FAILED = "failed"


@dataclass
class BackendInfo:
    """Information about a backend."""

    name: str
    version: str | None
    path: Path | None
    status: BackendStatus
    installation_method: str  # "system", "homebrew", "downloaded"

    def __str__(self) -> str:
        """Human-readable representation."""
        status_str = self.status.value
        if self.version:
            return f"{self.name} v{self.version} ({status_str}, {self.installation_method})"
        return f"{self.name} ({status_str})"


class BackendLifecycle(ABC):
    """
    Abstract interface for backend lifecycle management.

    All backends must implement these methods for detection,
    installation, configuration, and lifecycle management.
    """

    @abstractmethod
    def detect(self) -> BackendInfo:
        """
        Detect if backend is available.

        Returns:
            BackendInfo with current status
        """

    @abstractmethod
    def install(self, auto: bool = True) -> BackendInfo:
        """
        Install backend if not available.

        Args:
            auto: If True, install without prompts

        Returns:
            BackendInfo after installation attempt

        Raises:
            RuntimeError: If installation fails
        """

    @abstractmethod
    def configure(self, model: "Model", hardware: "HardwareProfile") -> dict:
        """
        Generate backend-specific configuration.

        Args:
            model: Selected model
            hardware: Hardware profile

        Returns:
            Configuration dict for backend
        """

    @abstractmethod
    def get_server_url(self) -> str:
        """
        Get backend server URL.

        Returns:
            URL string (e.g., "http://localhost:8080")
        """

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if backend server is healthy.

        Returns:
            True if backend is responding
        """
