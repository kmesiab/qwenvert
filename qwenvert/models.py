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

# Quantization quality rankings (higher = better quality)
# Shared across ModelRegistry and ModelSelector
QUANTIZATION_QUALITY: dict[str, int] = {
    "Q8_0": 3,  # Highest quality
    "Q6_K": 2,  # Good balance
    "Q5_K_M": 1,  # Efficient
    "Q4_K_M": 0,  # Smallest/fastest
}


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
            # Small models for 8GB systems
            Model(
                id="qwen2.5-coder-1.5b-q4-llamacpp",
                display_name="Qwen2.5 Coder 1.5B Q4",
                family="qwen2.5-coder",
                size_b=1.5,
                quantization="Q4_K_M",
                backend=Backend.LLAMACPP,
                backend_model_id="qwen2.5-coder-1.5b-instruct-q4_K_M.gguf",
                context_length=32768,
                max_output_tokens=8192,
                min_ram_gb=4,
                recommended_ram_gb=8,
                is_coder_model=True,
                is_default_candidate=True,
                huggingface_repo="Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
                notes="Fast, lightweight model for low-memory systems. 3-7x faster than Ollama.",
            ),
            Model(
                id="qwen2.5-coder-3b-q4-llamacpp",
                display_name="Qwen2.5 Coder 3B Q4",
                family="qwen2.5-coder",
                size_b=3.0,
                quantization="Q4_K_M",
                backend=Backend.LLAMACPP,
                backend_model_id="qwen2.5-coder-3b-instruct-q4_K_M.gguf",
                context_length=32768,
                max_output_tokens=8192,
                min_ram_gb=6,
                recommended_ram_gb=8,
                is_coder_model=True,
                is_default_candidate=True,
                huggingface_repo="Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
                notes="Good balance for 8GB systems. 3-7x faster than Ollama.",
            ),
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
        models.sort(
            key=lambda m: (m.size_b, -QUANTIZATION_QUALITY.get(m.quantization, -1))
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

    # Maximum model size for thermally-constrained systems (fanless Macs)
    THERMAL_CONSTRAINED_MAX_SIZE_GB: float = 7.0

    def __init__(self, registry: ModelRegistry) -> None:
        """
        Initialize model selector.

        Args:
            registry: Model registry to select from
        """
        self.registry = registry

    def get_preferred_backend(self, hardware: HardwareProfile) -> Backend:
        """
        Determine preferred backend based on hardware.

        Backend Priority Logic (Feb 2026):
        - Mac M-Series: Default to llama.cpp (Metal) for best performance
        - Other systems: Default to Ollama for ease of use

        Args:
            hardware: Detected hardware profile

        Returns:
            Preferred backend for this hardware
        """
        # Mac M-Series: Default to llama.cpp (Metal)
        if hardware.chip_family in ["M1", "M2", "M3", "M4"]:
            logger.info(
                f"Mac {hardware.chip_family} detected - preferring llama.cpp (Metal)"
            )
            return Backend.LLAMACPP

        # Default to Ollama for other systems
        return Backend.OLLAMA

    def auto_select_model_for_memory(self, hardware: HardwareProfile) -> str | None:
        """
        Auto-select model ID based on available memory.

        Logic Gate (Feb 2026):
        - If mem < 10GB: auto-select Qwen3-Coder-Next-8B Q4 or Gemma3-4B-IT
        - If mem > 16GB: suggest larger models (14B+ or MoE variants)
        - If mem 10-16GB: balanced selection (7-8B models)

        Args:
            hardware: Detected hardware profile

        Returns:
            Recommended model ID, or None if no suitable model
        """
        total_mem = hardware.total_memory_gb

        # < 10GB: Prioritize smallest efficient models
        if total_mem < 10:
            logger.info(
                f"{total_mem}GB RAM detected - selecting compact model for 8GB optimization"
            )

            # Try Qwen3-Coder-Next-8B first (best for 8GB)
            if self.registry.get_model("qwen3-coder-next-8b-q4-llamacpp"):
                return "qwen3-coder-next-8b-q4-llamacpp"

            # Fallback to Gemma3-4B-IT (ultra-compact)
            if self.registry.get_model("gemma3-4b-it-q4-llamacpp"):
                return "gemma3-4b-it-q4-llamacpp"

            # Legacy fallback: Qwen2.5 Coder 3B
            if self.registry.get_model("qwen2.5-coder-3b-q4-llamacpp"):
                return "qwen2.5-coder-3b-q4-llamacpp"

            return None

        # > 16GB: Suggest larger models
        if total_mem > 16:
            logger.info(f"{total_mem}GB RAM detected - selecting high-capacity model")

            # Try 14B variants first
            if self.registry.get_model("qwen2.5-coder-14b-q5-llamacpp"):
                return "qwen2.5-coder-14b-q5-llamacpp"

            if self.registry.get_model("qwen2.5-coder-14b-q4-llamacpp"):
                return "qwen2.5-coder-14b-q4-llamacpp"

            # Fallback to 7-8B
            if self.registry.get_model("qwen3-coder-next-8b-q4-llamacpp"):
                return "qwen3-coder-next-8b-q4-llamacpp"

            return None

        # 10-16GB: Balanced selection (7-8B models)
        logger.info(f"{total_mem}GB RAM detected - selecting balanced model")

        # Prioritize Qwen3-Coder-Next-8B
        if self.registry.get_model("qwen3-coder-next-8b-q4-llamacpp"):
            return "qwen3-coder-next-8b-q4-llamacpp"

        # Fallback to legacy Qwen2.5 7B
        if self.registry.get_model("qwen2.5-coder-7b-q4-llamacpp"):
            return "qwen2.5-coder-7b-q4-llamacpp"

        return None

    def _filter_by_backend(
        self,
        models: list[Model],
        backend: Backend | None,
        log_if_empty: bool = False,
    ) -> list[Model]:
        """
        Filter models by backend if specified.

        Args:
            models: List of models to filter
            backend: Backend to filter by (None = no filtering)
            log_if_empty: Whether to log warning if no models remain

        Returns:
            Filtered list of models
        """
        if backend is None:
            return models

        filtered = [m for m in models if m.backend == backend]

        if log_if_empty and not filtered:
            logger.warning(f"No compatible {backend.value} models found for hardware")

        return filtered

    def _get_quantization_score(self, model: Model) -> int:
        """
        Get quantization quality score (higher = better).

        Args:
            model: Model to score

        Returns:
            Quality score (-1 for unknown quantization formats)
        """
        return QUANTIZATION_QUALITY.get(model.quantization, -1)

    def _sort_key_smallest_efficient(self, model: Model) -> tuple[float, int]:
        """
        Sort key for memory-constrained systems: smallest size, prefer Q4_K_M.

        Args:
            model: Model to generate sort key for

        Returns:
            Tuple of (size, quantization_penalty)
        """
        return (model.size_b, 0 if model.quantization == "Q4_K_M" else 1)

    def _sort_key_largest_quality(self, model: Model) -> tuple[float, int]:
        """
        Sort key for standard systems: largest size, highest quantization.

        Args:
            model: Model to generate sort key for

        Returns:
            Tuple of (size, quality_score)
        """
        return (model.size_b, self._get_quantization_score(model))

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
                    # Case-insensitive matching for robustness (handles q4_k_m vs Q4_K_M)
                    if filename.lower() == expected_filename.lower():
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
        backend: Backend | None = None,
    ) -> Model | None:
        """
        Select default model for given hardware.

        Selection strategy:
        1. Determine preferred backend (llama.cpp for Mac M-Series)
        2. Filter to compatible models (fits in RAM)
        3. Filter by backend (if specified, or use preferred)
        4. Check for already-downloaded compatible models (prioritize existing)
        5. Prefer models in "optimal" range (recommended RAM)
        6. For memory-constrained systems (<= 8GB): prefer smaller, higher quantization
        7. For thermally-constrained (fanless): prefer smaller models
        8. Otherwise: prefer larger model with highest quantization

        Args:
            hardware: Detected hardware profile
            downloaded_models: List of paths to already-downloaded GGUF files (optional)
            downloader: ModelDownloader instance for filename matching (optional,
                       avoids filesystem side effects in tests)
            backend: Backend to filter models by (if specified, handles fallback scenario)

        Returns:
            Selected model, or None if no compatible model found
        """
        # Auto-select preferred backend if not specified
        if backend is None:
            backend = self.get_preferred_backend(hardware)
            logger.info(f"Auto-selected backend: {backend.value}")

        # Get compatible models
        compatible = self.registry.find_compatible_models(hardware)
        if not compatible:
            return None

        # Filter by backend if specified (handles fallback scenario)
        compatible = self._filter_by_backend(compatible, backend, log_if_empty=True)
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

        # Filter optimal by backend if specified (ensures all code paths respect backend)
        optimal = self._filter_by_backend(optimal, backend)

        # Decision logic based on hardware constraints
        if hardware.is_memory_constrained():
            # 8GB or less: PRIORITIZE SMALLEST model to avoid swapping
            # Size is more important than quantization quality on constrained systems
            # Sort by size first, then prefer Q4_K_M for efficiency
            compatible_sorted = sorted(
                compatible, key=self._sort_key_smallest_efficient
            )
            return compatible_sorted[0] if compatible_sorted else None

        if hardware.is_thermally_constrained():
            # Fanless Mac: prefer smaller models to reduce thermal load
            # Use Q5_K_M if available (good quality/performance balance)
            candidates = [
                m
                for m in optimal
                if m.size_b <= self.THERMAL_CONSTRAINED_MAX_SIZE_GB
                and m.quantization in ["Q5_K_M", "Q4_K_M"]
            ]
            if candidates:
                # Prefer Q5_K_M over Q4_K_M
                q5_candidates = [m for m in candidates if m.quantization == "Q5_K_M"]
                if q5_candidates:
                    return q5_candidates[0]
                return candidates[0]

            logger.warning(
                f"No thermally-safe models found (size <= {self.THERMAL_CONSTRAINED_MAX_SIZE_GB}GB, "
                f"quantizations Q5_K_M/Q4_K_M); falling back to standard selection"
            )

        # Standard case: maximize quality within optimal range
        if optimal:
            # Sort by size (desc) then quantization quality (desc)
            optimal_sorted = sorted(
                optimal, key=self._sort_key_largest_quality, reverse=True
            )
            return optimal_sorted[0]

        # No optimal models, choose best compatible
        # Prefer larger models with better quantization
        compatible_sorted = sorted(
            compatible, key=self._sort_key_largest_quality, reverse=True
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
            return max(compatible, key=self._sort_key_largest_quality)

        if prefer_speed:
            # Choose smallest model with lower quantization
            return min(compatible, key=lambda m: (m.size_b, m.quantization))

        # Default to balanced selection
        return self.select_default(hardware)
