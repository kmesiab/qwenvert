"""
Unit tests for model registry and selection.
"""

from pathlib import Path

from qwenvert.models import Backend, ModelSelector


class TestModelRegistry:
    """Test model registry functionality."""

    def test_registry_loads_default_models(self, model_registry):
        """Test that registry loads with default models."""
        models = model_registry.list_models()
        assert len(models) > 0
        assert any(m.id == "qwen2.5-coder-7b-q4-ollama" for m in models)

    def test_get_model_by_id(self, model_registry):
        """Test retrieving model by ID."""
        model = model_registry.get_model("qwen2.5-coder-7b-q4-ollama")
        assert model is not None
        assert model.display_name == "Qwen2.5 Coder 7B Q4"
        assert model.backend == Backend.OLLAMA

    def test_list_models_filter_by_backend(self, model_registry):
        """Test filtering models by backend."""
        ollama_models = model_registry.list_models(backend=Backend.OLLAMA)
        assert all(m.backend == Backend.OLLAMA for m in ollama_models)

        llamacpp_models = model_registry.list_models(backend=Backend.LLAMACPP)
        assert all(m.backend == Backend.LLAMACPP for m in llamacpp_models)

    def test_find_compatible_models(self, model_registry, mock_hardware_m1_16gb):
        """Test finding models compatible with hardware."""
        compatible = model_registry.find_compatible_models(mock_hardware_m1_16gb)
        assert len(compatible) > 0
        # All should fit in 16GB
        assert all(m.min_ram_gb <= 16 for m in compatible)

    def test_find_optimal_models(self, model_registry, mock_hardware_m1_16gb):
        """Test finding optimal models for hardware."""
        optimal = model_registry.find_optimal_models(mock_hardware_m1_16gb)
        # Optimal models have recommended RAM <= available RAM
        assert all(m.recommended_ram_gb <= 16 for m in optimal)


class TestModelSelection:
    """Test intelligent model selection."""

    def test_select_default_for_8gb_system(
        self, model_registry, mock_hardware_m1_air_8gb
    ):
        """8GB system should get Q4 7B or smaller."""
        selector = ModelSelector(model_registry)
        model = selector.select_default(mock_hardware_m1_air_8gb)

        assert model is not None
        assert model.min_ram_gb <= 8
        # Should prefer Q4 for memory efficiency
        assert "Q4" in model.quantization

    def test_select_default_for_16gb_system(
        self, model_registry, mock_hardware_m1_16gb
    ):
        """16GB system should get optimal 7B model."""
        selector = ModelSelector(model_registry)
        model = selector.select_default(mock_hardware_m1_16gb)

        assert model is not None
        assert model.min_ram_gb <= 16
        assert model.recommended_ram_gb <= 16

    def test_select_default_for_32gb_system(
        self, model_registry, mock_hardware_m1_max_32gb
    ):
        """32GB system should get larger model."""
        selector = ModelSelector(model_registry)
        model = selector.select_default(mock_hardware_m1_max_32gb)

        assert model is not None
        # Should be able to handle larger models
        assert model.min_ram_gb <= 32

    def test_thermal_constraint_selects_smaller_model(
        self, model_registry, mock_hardware_m1_air_8gb
    ):
        """Fanless Mac should prefer smaller models."""
        selector = ModelSelector(model_registry)
        model = selector.select_default(mock_hardware_m1_air_8gb)

        assert model is not None
        # Fanless system should get conservative choice
        assert model.size_b <= 7.0

    def test_select_by_preference_quality(self, model_registry, mock_hardware_m1_16gb):
        """Quality preference should select higher quantization."""
        selector = ModelSelector(model_registry)
        model = selector.select_by_preference(
            mock_hardware_m1_16gb, prefer_quality=True
        )

        assert model is not None
        # Should prefer higher quantization or larger model
        assert model.fits_hardware(mock_hardware_m1_16gb)

    def test_select_by_preference_speed(self, model_registry, mock_hardware_m1_16gb):
        """Speed preference should select smaller/lower quant."""
        selector = ModelSelector(model_registry)
        model = selector.select_by_preference(mock_hardware_m1_16gb, prefer_speed=True)

        assert model is not None
        # Should be smaller for faster inference
        assert model.fits_hardware(mock_hardware_m1_16gb)

    def test_select_default_prioritizes_downloaded_models(
        self, model_registry, mock_hardware_m1_16gb
    ):
        """Should prioritize already-downloaded compatible models."""
        selector = ModelSelector(model_registry)

        # Create mock downloaded model paths - 1.5B model
        downloaded_models = [
            Path("/fake/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf")
        ]

        # Without downloaded models, 16GB system would normally select 7B
        model_without = selector.select_default(mock_hardware_m1_16gb)
        assert model_without is not None
        # Should select a larger model for 16GB system
        assert model_without.size_b >= 7.0

        # With downloaded 1.5B model, should prefer the downloaded one
        model_with = selector.select_default(mock_hardware_m1_16gb, downloaded_models)
        assert model_with is not None
        # Should select the 1.5B model that's already downloaded (prioritizes downloaded over optimal)
        assert model_with.size_b == 1.5

    def test_select_default_skips_incompatible_downloaded_models(
        self, model_registry, mock_hardware_m1_air_8gb
    ):
        """Should skip downloaded models that don't fit hardware."""
        selector = ModelSelector(model_registry)

        # Create mock downloaded model path - 14B model (too large for 8GB)
        downloaded_models = [
            Path("/fake/models/qwen2.5-coder-14b-instruct-q4_k_m.gguf")
        ]

        # Should fall back to hardware-based selection since 14B doesn't fit 8GB
        model = selector.select_default(mock_hardware_m1_air_8gb, downloaded_models)
        assert model is not None
        # Should select a smaller model that fits
        assert model.size_b <= 7.0
        assert model.min_ram_gb <= 8

    def test_select_default_works_without_downloaded_models(
        self, model_registry, mock_hardware_m1_16gb
    ):
        """Should work normally when no downloaded models provided."""
        selector = ModelSelector(model_registry)

        # Pass None for downloaded_models (default)
        model = selector.select_default(mock_hardware_m1_16gb, None)
        assert model is not None
        assert model.fits_hardware(mock_hardware_m1_16gb)

        # Pass empty list
        model = selector.select_default(mock_hardware_m1_16gb, [])
        assert model is not None
        assert model.fits_hardware(mock_hardware_m1_16gb)

    def test_select_default_respects_backend_filter(
        self, model_registry, mock_hardware_m1_16gb
    ):
        """Should filter models by backend when specified."""
        selector = ModelSelector(model_registry)

        # Force llamacpp backend
        model = selector.select_default(mock_hardware_m1_16gb, backend=Backend.LLAMACPP)

        assert model is not None
        assert model.backend == Backend.LLAMACPP

        # Force ollama backend
        model = selector.select_default(mock_hardware_m1_16gb, backend=Backend.OLLAMA)

        assert model is not None
        assert model.backend == Backend.OLLAMA

    def test_select_default_backend_filter_8gb_system(
        self, model_registry, mock_hardware_m1_air_8gb
    ):
        """Should find compatible small models for 8GB system with llamacpp backend."""
        selector = ModelSelector(model_registry)

        # After Phase 1, should find 1.5B/3B llamacpp models for 8GB systems
        model = selector.select_default(
            mock_hardware_m1_air_8gb, backend=Backend.LLAMACPP
        )

        # Should find a compatible model now (1.5B or 3B)
        assert model is not None
        assert model.backend == Backend.LLAMACPP
        assert model.size_b <= 3.0  # Small model for 8GB system

    def test_select_default_4gb_system(self, model_registry):
        """Should select 1.5B model for 4GB system."""
        from qwenvert.hardware import HardwareProfile
        from qwenvert.models import Backend

        # Create 4GB hardware profile
        hardware_4gb = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=4.0,
            gpu_cores=7,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="MacBookAir10,1",
        )

        selector = ModelSelector(model_registry)

        # Should select smallest model (1.5B)
        model = selector.select_default(hardware_4gb, backend=Backend.LLAMACPP)

        assert model is not None
        assert model.size_b == 1.5  # Only 1.5B fits in 4GB
        assert model.min_ram_gb <= 4.0

    def test_select_default_model_doesnt_fit(self, model_registry):
        """Should return None when no models fit hardware."""
        from qwenvert.hardware import HardwareProfile

        # Create extremely constrained hardware (2GB)
        hardware_2gb = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=2.0,
            gpu_cores=7,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="MacBookAir10,1",
        )

        selector = ModelSelector(model_registry)

        # Should return None (no models fit in 2GB)
        model = selector.select_default(hardware_2gb)

        assert model is None

    def test_select_default_multiple_downloaded_models(
        self, model_registry, mock_hardware_m1_16gb, tmp_path
    ):
        """Should prioritize best downloaded model when multiple exist."""
        from pathlib import Path

        selector = ModelSelector(model_registry)

        # Simulate multiple downloaded models
        downloaded_models = [
            tmp_path / "qwen2.5-coder-1.5b-instruct-q4_K_M.gguf",
            tmp_path / "qwen2.5-coder-3b-instruct-q4_K_M.gguf",
        ]

        # Create the files
        for model_file in downloaded_models:
            model_file.touch()

        # Should select first compatible (prioritizes downloaded over optimal)
        model = selector.select_default(
            mock_hardware_m1_16gb, downloaded_models=downloaded_models
        )

        assert model is not None
        # Should get one of the downloaded models
        assert model.size_b in [1.5, 3.0]

    def test_select_default_empty_registry(self):
        """Should handle empty registry gracefully."""
        from qwenvert.hardware import HardwareProfile
        from qwenvert.models import ModelRegistry, ModelSelector

        # Create empty registry
        empty_registry = ModelRegistry()
        empty_registry.models = {}

        selector = ModelSelector(empty_registry)

        hardware = HardwareProfile(
            chip="M1 Pro",
            chip_family="M1",
            total_memory_gb=16.0,
            gpu_cores=16,
            cpu_cores_performance=8,
            cpu_cores_efficiency=2,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="MacBookPro18,1",
        )

        # Should return None gracefully
        model = selector.select_default(hardware)

        assert model is None

    def test_select_default_unknown_quantization(
        self, model_registry, mock_hardware_m1_16gb
    ):
        """Should handle unknown quantization formats gracefully."""
        from qwenvert.models import Model, Backend

        # Add model with unknown quantization
        unknown_quant_model = Model(
            id="test-unknown-quant",
            display_name="Test Unknown Quant",
            family="qwen2.5-coder",
            size_b=7.0,
            quantization="Q2_K",  # Unknown format
            backend=Backend.LLAMACPP,
            backend_model_id="test-unknown.gguf",
            context_length=32768,
            max_output_tokens=8192,
            min_ram_gb=8,
            recommended_ram_gb=16,
            is_coder_model=True,
            is_default_candidate=True,
        )

        model_registry.models[unknown_quant_model.id] = unknown_quant_model

        selector = ModelSelector(model_registry)

        # Should handle gracefully (score as -1)
        model = selector.select_default(mock_hardware_m1_16gb)

        assert model is not None
        # Should get quantization score of -1 for unknown format
        assert selector._get_quantization_score(unknown_quant_model) == -1

    def test_filter_by_backend_no_matches(self, model_registry):
        """Should return empty list when backend filter excludes all models."""
        from qwenvert.models import Backend

        selector = ModelSelector(model_registry)

        # Get all models
        all_models = list(model_registry.models.values())

        # Filter by MLX (no models have this backend)
        filtered = selector._filter_by_backend(
            all_models, Backend.MLX, log_if_empty=True
        )

        assert filtered == []


class TestModelMetadata:
    """Test model metadata and methods."""

    def test_model_fits_hardware(self, sample_model_7b_q4, mock_hardware_m1_16gb):
        """Test hardware compatibility check."""
        assert sample_model_7b_q4.fits_hardware(mock_hardware_m1_16gb)

    def test_model_doesnt_fit_constrained_hardware(
        self, sample_model_14b_q5, mock_hardware_m1_air_8gb
    ):
        """Test that large model doesn't fit small system."""
        assert not sample_model_14b_q5.fits_hardware(mock_hardware_m1_air_8gb)

    def test_model_is_optimal(self, sample_model_7b_q4, mock_hardware_m1_16gb):
        """Test optimal model check."""
        assert sample_model_7b_q4.is_optimal_for_hardware(mock_hardware_m1_16gb)
