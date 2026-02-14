"""
Model registry and selection module.

Maintains catalog of supported Qwen models with hardware requirements
and provides intelligent model selection based on detected hardware.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import yaml


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from .downloader import ModelDownloader
    from .hardware import HardwareProfile


class Backend(str, Enum):
    """Supported inference backends."""

    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    MLX = "mlx"
    VLLM = "vllm"


@dataclass
class Model:
    """
    Model metadata and configuration.

    Attributes:
        id: Internal identifier (e.g., "qwen2.5-coder-7b-q4-ollama")
        display_name: Human-readable name
        family: Model family (e.g., "qwen2.5-coder")
        size_b: Model size in billions of parameters
        quantization: Quantization format (e.g., "Q4_K_M", "Q5_K_M", "Q8_0")
        backend: Primary backend for this model
        backend_model_id: Backend-specific model identifier
        context_length: Maximum context window in tokens
        max_output_tokens: Maximum tokens for generation (output only)
        min_ram_gb: Minimum RAM required
        recommended_ram_gb: Recommended RAM for good performance
        min_vram_gb: Minimum VRAM required (if applicable)
        recommended_vram_gb: Recommended VRAM
        is_coder_model: Whether this is a code-specialized model
        is_default_candidate: Whether this can be auto-selected
        huggingface_repo: HuggingFace repository (for downloads)
        notes: Additional information
    """

    id: str
    display_name: str
    family: str
    size_b: float
    quantization: str
    backend: Backend
    backend_model_id: str
    context_length: int
    max_output_tokens: int
    min_ram_gb: int
    recommended_ram_gb: int
    min_vram_gb: int | None = None
    recommended_vram_gb: int | None = None
    is_coder_model: bool = True
    is_default_candidate: bool = True
    huggingface_repo: str | None = None
    notes: str | None = None

    def fits_hardware(self, hardware: HardwareProfile) -> bool:
        """
        Check if model fits on given hardware.

        Args:
            hardware: Hardware profile to check against

        Returns:
            True if model can run on this hardware
        """
        return hardware.total_memory_gb >= self.min_ram_gb

    def is_optimal_for_hardware(self, hardware: HardwareProfile) -> bool:
        """
        Check if model is optimal (not just fits) for given hardware.

        Args:
            hardware: Hardware profile to check against

        Returns:
            True if model is in optimal range for this hardware
        """
        return hardware.total_memory_gb >= self.recommended_ram_gb

    def __str__(self) -> str:
        """Human-readable model description."""
        return f"{self.display_name} ({self.quantization}, {self.backend.value})"


class ModelRegistry:
    """
    Registry of supported models.

    Loads model definitions from YAML and provides lookup/filtering methods.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        """
        Initialize model registry.

        Args:
            config_path: Path to models.yaml (default: configs/models.yaml)
        """
        self.models: dict[str, Model] = {}

        if config_path is None:
            # Default to configs/models.yaml in package
            package_dir = Path(__file__).parent.parent
            config_path = package_dir / "configs" / "models.yaml"

        if config_path.exists():
            self._load_from_yaml(config_path)
        else:
            # Load hardcoded defaults if no config file
            self._load_defaults()

    def _load_from_yaml(self, config_path: Path) -> None:
        """Load models from YAML configuration."""
        with open(config_path) as f:
            data = yaml.safe_load(f)

        for model_data in data.get("models", []):
            model = Model(
                id=model_data["id"],
                display_name=model_data["display_name"],
                family=model_data["family"],
                size_b=model_data["size_b"],
                quantization=model_data["quantization"],
                backend=Backend(model_data["backend"]),
                backend_model_id=model_data["backend_model_id"],
                context_length=model_data["context_length"],
                max_output_tokens=model_data["max_output_tokens"],
                min_ram_gb=model_data["min_ram_gb"],
                recommended_ram_gb=model_data["recommended_ram_gb"],
                min_vram_gb=model_data.get("min_vram_gb"),
                recommended_vram_gb=model_data.get("recommended_vram_gb"),
                is_coder_model=model_data.get("is_coder_model", True),
                is_default_candidate=model_data.get("is_default_candidate", True),
                huggingface_repo=model_data.get("huggingface_repo"),
                notes=model_data.get("notes"),
            )
            self.models[model.id] = model

    def _load_defaults(self) -> None:
        """Load hardcoded default models if no config file."""
        defaults = [
            Model(
                id="qwen2.5-coder-7b-q4-ollama",
                display_name="Qwen2.5 Coder 7B Q4",
                family="qwen2.5-coder",
                size_b=7.0,
                quantization="Q4_K_M",
                backend=Backend.OLLAMA,
                backend_model_id="qwen2.5-coder:7b-instruct-q4_K_M",
                context_length=32768,
                max_output_tokens=12288,
                min_ram_gb=12,
                recommended_ram_gb=16,
                is_coder_model=True,
                is_default_candidate=True,
                huggingface_repo="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
                notes="Best balance for most systems. Requires 12GB+ RAM to avoid swapping.",
            ),
            Model(
                id="qwen2.5-coder-7b-q5-ollama",
                display_name="Qwen2.5 Coder 7B Q5",
                family="qwen2.5-coder",
                size_b=7.0,
                quantization="Q5_K_M",
                backend=Backend.OLLAMA,
                backend_model_id="qwen2.5-coder:7b-instruct-q5_K_M",
                context_length=32768,
                max_output_tokens=12288,
                min_ram_gb=12,
                recommended_ram_gb=16,
                is_coder_model=True,
                is_default_candidate=True,
                huggingface_repo="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
                notes="Higher quality, needs more RAM",
            ),
            Model(
                id="qwen2.5-coder-14b-q4-llamacpp",
                display_name="Qwen2.5 Coder 14B Q4",
                family="qwen2.5-coder",
                size_b=14.0,
                quantization="Q4_K_M",
                backend=Backend.LLAMACPP,
                backend_model_id="qwen2.5-coder-14b-instruct-q4_K_M.gguf",
                context_length=32768,
                max_output_tokens=16384,
                min_ram_gb=16,
                recommended_ram_gb=24,
                is_coder_model=True,
                is_default_candidate=True,
                huggingface_repo="Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
                notes="Better quality, needs 16GB+",
            ),
            Model(
                id="qwen2.5-coder-14b-q5-llamacpp",
                display_name="Qwen2.5 Coder 14B Q5",
                family="qwen2.5-coder",
                size_b=14.0,
                quantization="Q5_K_M",
                backend=Backend.LLAMACPP,
                backend_model_id="qwen2.5-coder-14b-instruct-q5_K_M.gguf",
                context_length=32768,
                max_output_tokens=16384,
                min_ram_gb=20,
                recommended_ram_gb=32,
                is_coder_model=True,
                is_default_candidate=True,
                huggingface_repo="Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
                notes="Best quality for high-end systems",
            ),
        ]

        for model in defaults:
            self.models[model.id] = model

    def get_model(self, model_id: str) -> Model | None:
        """
        Get model by ID.

        Args:
            model_id: Model identifier

        Returns:
            Model if found, None otherwise
        """
        return self.models.get(model_id)

    def list_models(
        self,
        backend: Backend | None = None,
        coder_only: bool = True,
        default_candidates_only: bool = False,
    ) -> list[Model]:
        """
        List models with optional filtering.

        Args:
            backend: Filter by backend type
            coder_only: Only return code-specialized models
            default_candidates_only: Only return auto-selectable models

        Returns:
            List of matching models
        """
        models = list(self.models.values())

        if backend:
            models = [m for m in models if m.backend == backend]

        if coder_only:
            models = [m for m in models if m.is_coder_model]

        if default_candidates_only:
            models = [m for m in models if m.is_default_candidate]

        # Sort by size (smaller first) and quantization (higher quality first)
        quantization_order = {"Q8_0": 3, "Q6_K": 2, "Q5_K_M": 1, "Q4_K_M": 0}
        models.sort(
            key=lambda m: (m.size_b, quantization_order.get(m.quantization, -1))
        )

        return models

    def find_compatible_models(self, hardware: HardwareProfile) -> list[Model]:
        """
        Find all models compatible with given hardware.

        Args:
            hardware: Hardware profile

        Returns:
            List of models that fit on this hardware
        """
        return [m for m in self.list_models() if m.fits_hardware(hardware)]

    def find_optimal_models(self, hardware: HardwareProfile) -> list[Model]:
        """
        Find optimal models for given hardware.

        Args:
            hardware: Hardware profile

        Returns:
            List of models in optimal range for this hardware
        """
        return [m for m in self.list_models() if m.is_optimal_for_hardware(hardware)]


class ModelSelector:
    """
    Intelligent model selection based on hardware profile.

    Implements selection logic that balances model quality with
    hardware constraints (memory, thermal, performance).
    """

    def __init__(self, registry: ModelRegistry) -> None:
        """
        Initialize model selector.

        Args:
            registry: Model registry to select from
        """
        self.registry = registry

    def _find_downloaded_model(
        self,
        downloaded_models: list[Path],
        compatible: list[Model],
        downloader: ModelDownloader | None = None,
    ) -> Model | None:
        """
        Find first downloaded model that matches compatible models.

        Args:
            downloaded_models: List of downloaded GGUF file paths
            compatible: List of compatible models from registry
            downloader: ModelDownloader instance (optional)

        Returns:
            First matching model, or None if no match found
        """
        # Import here to avoid circular dependency (downloader imports Model)
        from .downloader import ModelDownloader

        # Use provided downloader or create one (avoids side effects when possible)
        if downloader is None:
            downloader = ModelDownloader()

        for model_path in downloaded_models:
            filename = model_path.name

            # Try to match this downloaded file to a model in registry
            for model in compatible:
                try:
                    expected_filename = downloader.get_model_filename(model)
                    if filename == expected_filename:
                        # Found a match! Use this already-downloaded model
                        logger.info(
                            f"Found already-downloaded compatible model: {model.display_name} "
                            f"({model_path.name})"
                        )
                        return model
                except (ValueError, AttributeError):
                    # Skip models with invalid/missing filename info
                    continue

        return None

    def select_default(
        self,
        hardware: HardwareProfile,
        downloaded_models: list[Path] | None = None,
        downloader: ModelDownloader | None = None,
    ) -> Model | None:
        """
        Select default model for given hardware.

        Selection strategy:
        1. Check for already-downloaded compatible models (prioritize existing)
        2. Filter to compatible models (fits in RAM)
        3. Prefer models in "optimal" range (recommended RAM)
        4. For memory-constrained systems (<= 8GB): prefer smaller, higher quantization
        5. For thermally-constrained (fanless): prefer smaller models
        6. Otherwise: prefer larger model with highest quantization

        Args:
            hardware: Detected hardware profile
            downloaded_models: List of paths to already-downloaded GGUF files (optional)
            downloader: ModelDownloader instance for filename matching (optional,
                       avoids filesystem side effects in tests)

        Returns:
            Selected model, or None if no compatible model found
        """
        # Get compatible models
        compatible = self.registry.find_compatible_models(hardware)
        if not compatible:
            return None

        # NEW: Check for already-downloaded compatible models first
        if downloaded_models:
            found_model = self._find_downloaded_model(
                downloaded_models, compatible, downloader
            )
            if found_model:
                return found_model

        # Get optimal models (recommended RAM available)
        optimal = self.registry.find_optimal_models(hardware)

        # Decision logic based on hardware constraints
        if hardware.is_memory_constrained():
            # 8GB or less: PRIORITIZE SMALLEST model to avoid swapping
            # Size is more important than quantization quality on constrained systems
            # Sort by size first, then prefer Q4_K_M for efficiency
            compatible_sorted = sorted(
                compatible,
                key=lambda m: (m.size_b, 0 if m.quantization == "Q4_K_M" else 1),
            )
            return compatible_sorted[0] if compatible_sorted else None

        if hardware.is_thermally_constrained():
            # Fanless Mac: prefer smaller models to reduce thermal load
            # Use Q5_K_M if available (good quality/performance balance)
            candidates = [
                m
                for m in optimal
                if m.size_b <= 7.0 and m.quantization in ["Q5_K_M", "Q4_K_M"]
            ]
            if candidates:
                # Prefer Q5_K_M over Q4_K_M
                q5_candidates = [m for m in candidates if m.quantization == "Q5_K_M"]
                if q5_candidates:
                    return q5_candidates[0]
                return candidates[0]

        # Standard case: maximize quality within optimal range
        if optimal:
            # Sort by size (desc) then quantization quality (desc)
            quantization_quality = {"Q8_0": 3, "Q6_K": 2, "Q5_K_M": 1, "Q4_K_M": 0}
            optimal_sorted = sorted(
                optimal,
                key=lambda m: (m.size_b, quantization_quality.get(m.quantization, -1)),
                reverse=True,
            )
            return optimal_sorted[0]

        # No optimal models, choose best compatible
        # Prefer larger models with better quantization
        quantization_quality = {"Q8_0": 3, "Q6_K": 2, "Q5_K_M": 1, "Q4_K_M": 0}
        compatible_sorted = sorted(
            compatible,
            key=lambda m: (m.size_b, quantization_quality.get(m.quantization, -1)),
            reverse=True,
        )
        return compatible_sorted[0]

    def select_by_preference(
        self,
        hardware: HardwareProfile,
        prefer_quality: bool = False,
        prefer_speed: bool = False,
    ) -> Model | None:
        """
        Select model based on user preference.

        Args:
            hardware: Detected hardware profile
            prefer_quality: Prioritize model quality over speed
            prefer_speed: Prioritize inference speed over quality

        Returns:
            Selected model based on preference
        """
        compatible = self.registry.find_compatible_models(hardware)
        if not compatible:
            return None

        if prefer_quality:
            # Choose largest model with highest quantization
            quantization_quality = {"Q8_0": 3, "Q6_K": 2, "Q5_K_M": 1, "Q4_K_M": 0}
            return max(
                compatible,
                key=lambda m: (m.size_b, quantization_quality.get(m.quantization, -1)),
            )

        if prefer_speed:
            # Choose smallest model with lower quantization
            return min(compatible, key=lambda m: (m.size_b, m.quantization))

        # Default to balanced selection
        return self.select_default(hardware)
