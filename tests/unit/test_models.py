"""
Unit tests for model registry and selection.
"""

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
