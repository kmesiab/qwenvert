"""
Unit tests for model registry and selection.
"""


from qwenvert.models import Backend, ModelRegistry, ModelSelector


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

    def test_list_models_without_filters(self, model_registry):
        """Test listing all models without filters."""
        all_models = model_registry.list_models(
            coder_only=False, default_candidates_only=False
        )
        assert len(all_models) > 0

    def test_list_models_default_candidates_only(self, model_registry):
        """Test filtering to default candidate models only."""
        default_only = model_registry.list_models(default_candidates_only=True)
        assert all(m.is_default_candidate for m in default_only)

    def test_get_nonexistent_model(self, model_registry):
        """Test retrieving non-existent model returns None."""
        model = model_registry.get_model("nonexistent-model-id")
        assert model is None

    def test_registry_load_from_yaml(self, tmp_path):
        """Test loading models from YAML config."""
        import yaml

        config_path = tmp_path / "models.yaml"
        config_data = {
            "models": [
                {
                    "id": "test-model",
                    "display_name": "Test Model",
                    "family": "test",
                    "size_b": 7.0,
                    "quantization": "Q4_K_M",
                    "backend": "ollama",
                    "backend_model_id": "test:7b",
                    "context_length": 8192,
                    "min_ram_gb": 8,
                    "recommended_ram_gb": 16,
                }
            ]
        }

        with open(config_path, "w") as f:
            yaml.safe_dump(config_data, f)

        registry = ModelRegistry(config_path=config_path)
        model = registry.get_model("test-model")

        assert model is not None
        assert model.display_name == "Test Model"

    def test_registry_loads_defaults_when_no_config(self, tmp_path):
        """Test that registry loads default models when config file doesn't exist."""
        # Point to a non-existent config file
        nonexistent_path = tmp_path / "nonexistent" / "models.yaml"

        registry = ModelRegistry(config_path=nonexistent_path)

        # Should have loaded default models
        models = registry.list_models()
        assert len(models) > 0

        # Check for some expected default models
        assert registry.get_model("qwen2.5-coder-7b-q4-ollama") is not None
        assert registry.get_model("qwen2.5-coder-7b-q5-ollama") is not None
        assert registry.get_model("qwen2.5-coder-14b-q4-llamacpp") is not None


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

    def test_select_by_preference_balanced(self, model_registry, mock_hardware_m1_16gb):
        """No preference should use default selection."""
        selector = ModelSelector(model_registry)
        model = selector.select_by_preference(mock_hardware_m1_16gb)

        assert model is not None
        assert model.fits_hardware(mock_hardware_m1_16gb)

    def test_select_default_no_compatible_models(self, model_registry):
        """Test selection when no models are compatible."""
        from qwenvert.hardware import HardwareProfile

        # Create a hardware profile with impossibly low RAM
        low_ram_hardware = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=2,  # Too low for any model
            gpu_cores=7,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="Test",
        )

        selector = ModelSelector(model_registry)
        model = selector.select_default(low_ram_hardware)

        assert model is None

    def test_select_fanless_mac_prefers_smaller_models(
        self, model_registry, mock_hardware_m1_air_8gb
    ):
        """Test that fanless Macs get appropriate smaller models."""
        selector = ModelSelector(model_registry)
        model = selector.select_default(mock_hardware_m1_air_8gb)

        assert model is not None
        # Should be constrained for thermal reasons
        assert model.size_b <= 7.0

    def test_select_default_no_q4_fallback(self, model_registry):
        """Test selection when no Q4 models available for constrained system."""
        from qwenvert.hardware import HardwareProfile

        # Create 8GB system (constrained)
        constrained = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=8,
            gpu_cores=7,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="Test",
        )

        selector = ModelSelector(model_registry)
        model = selector.select_default(constrained)

        # Should still find a model even without Q4
        assert model is not None

    def test_select_default_fanless_no_optimal(self, model_registry):
        """Test fanless Mac selection when no optimal models exist."""
        from qwenvert.hardware import HardwareProfile

        # Create fanless Mac with limited RAM
        fanless_limited = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=12,  # Between min and recommended for some models
            gpu_cores=7,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=False,
            neural_engine_cores=16,
            model_identifier="MacBookAir10,1",
        )

        selector = ModelSelector(model_registry)
        model = selector.select_default(fanless_limited)

        assert model is not None

    def test_select_default_no_optimal_models(self, model_registry):
        """Test selection when no optimal models but compatible models exist."""
        from qwenvert.hardware import HardwareProfile

        # Create hardware with RAM that fits some models but not optimally
        limited_ram = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=10,  # Fits min but not recommended for some models
            gpu_cores=8,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="Test",
        )

        selector = ModelSelector(model_registry)
        model = selector.select_default(limited_ram)

        # Should fall back to best compatible model
        assert model is not None
        assert model.min_ram_gb <= 10

    def test_select_by_preference_no_compatible(self, model_registry):
        """Test preference selection when no compatible models."""
        from qwenvert.hardware import HardwareProfile

        low_ram = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=2,
            gpu_cores=7,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="Test",
        )

        selector = ModelSelector(model_registry)
        model = selector.select_by_preference(low_ram, prefer_quality=True)

        assert model is None


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

    def test_model_str_representation(self, sample_model_7b_q4):
        """Test model string representation."""
        model_str = str(sample_model_7b_q4)

        assert sample_model_7b_q4.display_name in model_str
        assert sample_model_7b_q4.quantization in model_str
        assert sample_model_7b_q4.backend.value in model_str
