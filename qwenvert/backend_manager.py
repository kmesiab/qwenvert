"""
Backend manager for unified backend access.

Provides factory pattern for backend selection and management.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from .backend_interface import BackendInfo, BackendLifecycle, BackendStatus
from .backends import LlamaCppBackend, MLXBackend, OllamaBackend
from .models import Backend


logger = logging.getLogger(__name__)


class BackendManager:
    """
    Factory and manager for backend implementations.
    """

    _backends: ClassVar[dict[Backend, type[BackendLifecycle]]] = {
        Backend.LLAMACPP: LlamaCppBackend,
        Backend.OLLAMA: OllamaBackend,
        Backend.MLX: MLXBackend,
    }

    @classmethod
    def get_backend(cls, backend_type: Backend) -> BackendLifecycle:
        """
        Get backend implementation instance.

        Args:
            backend_type: Backend type enum

        Returns:
            Backend implementation instance

        Raises:
            ValueError: If backend type unknown
        """
        backend_class = cls._backends.get(backend_type)
        if not backend_class:
            raise ValueError(f"Unknown backend: {backend_type}")
        return backend_class()

    @classmethod
    def detect_all(cls) -> dict[Backend, BackendInfo]:
        """
        Detect all available backends.

        Returns:
            Dict mapping backend type to BackendInfo
        """
        results = {}
        for backend_type in cls._backends:
            try:
                backend = cls.get_backend(backend_type)
                results[backend_type] = backend.detect()
            except Exception as e:
                logger.warning(f"Failed to detect {backend_type.value}: {e}")
                results[backend_type] = BackendInfo(
                    name=backend_type.value,
                    version=None,
                    path=None,
                    status=BackendStatus.FAILED,
                    installation_method="none",
                )
        return results

    @classmethod
    def recommend_backend(cls) -> Backend:
        """
        Recommend optimal backend based on availability.

        Priority (Apple Silicon): MLX (if available) > llama.cpp > Ollama
        Priority (Other): llama.cpp > Ollama

        Returns:
            Recommended backend type
        """
        # Detect all backends
        available = cls.detect_all()

        # Check if running on Apple Silicon
        import platform

        is_apple_silicon = (
            platform.system() == "Darwin" and platform.machine() == "arm64"
        )

        # Priority 1: MLX (fastest on Apple Silicon, but only if already available)
        if is_apple_silicon and available[Backend.MLX].status == BackendStatus.AVAILABLE:
            logger.info("Recommending MLX (available and fastest on Apple Silicon)")
            return Backend.MLX

        # Priority 2: llama.cpp (3-7x faster than Ollama)
        if available[Backend.LLAMACPP].status == BackendStatus.AVAILABLE:
            logger.info("Recommending llama.cpp (available and faster)")
            return Backend.LLAMACPP

        # Priority 3: Ollama (easier to install, more forgiving)
        if available[Backend.OLLAMA].status == BackendStatus.AVAILABLE:
            logger.info("Recommending Ollama (llama.cpp not available)")
            return Backend.OLLAMA

        # Default to llama.cpp (will trigger auto-install)
        logger.info("Recommending llama.cpp (default, will auto-install)")
        return Backend.LLAMACPP
