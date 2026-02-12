"""
Unit tests for configuration generation.
"""

import pytest

from qwenvert.config import ConfigGenerator, ConfigManager, QwenvertConfig
from qwenvert.models import Backend


class TestConfigGenerator:
    """Test configuration generation."""

    def test_generate_qwenvert_config(self, sample_model_7b_q4, mock_hardware_m1_16gb):
        """Test generating qwenvert config."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_16gb)
        config = gen.generate_qwenvert_config()

        assert config.model_id == sample_model_7b_q4.id
        assert config.backend == Backend.OLLAMA.value
        assert "localhost" in config.backend_url
        assert config.adapter_host == "127.0.0.1"
        assert config.adapter_port == 8088

    def test_context_length_respects_hardware(
        self, sample_model_7b_q4, mock_hardware_m1_air_8gb
    ):
        """Test that context length is limited by hardware."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_air_8gb)
        config = gen.generate_qwenvert_config()

        # 8GB system should get 8K context
        assert config.context_length <= 8192

    def test_thermal_pacing_for_fanless(
        self, sample_model_7b_q4, mock_hardware_m1_air_8gb
    ):
        """Test that thermal pacing is enabled for fanless Macs."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_air_8gb)
        config = gen.generate_qwenvert_config()

        assert config.thermal_pacing is True

    def test_no_thermal_pacing_with_fan(
        self, sample_model_7b_q4, mock_hardware_m1_16gb
    ):
        """Test that thermal pacing is disabled with active cooling."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_16gb)
        config = gen.generate_qwenvert_config()

        assert config.thermal_pacing is False

    def test_generate_ollama_modelfile(self, sample_model_7b_q4, mock_hardware_m1_16gb):
        """Test Ollama Modelfile generation."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_16gb)
        modelfile = gen.generate_ollama_modelfile()

        assert "FROM qwen2.5-coder:7b-instruct-q4_K_M" in modelfile
        assert "PARAMETER num_ctx" in modelfile
        assert "PARAMETER num_gpu 1" in modelfile

    def test_generate_llamacpp_flags(self, sample_model_14b_q5, mock_hardware_m1_16gb):
        """Test llama.cpp flags generation."""
        gen = ConfigGenerator(sample_model_14b_q5, mock_hardware_m1_16gb)
        flags = gen.generate_llamacpp_flags()

        assert "--model" in flags
        assert "-ngl" in flags
        assert "99" in flags  # Offload all layers
        assert "-t" in flags
        assert "4" in flags  # P-core count
        assert "--mlock" in flags

    def test_environment_vars_generation(
        self, sample_model_7b_q4, mock_hardware_m1_16gb
    ):
        """Test environment variable generation."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_16gb)
        env_vars = gen.generate_environment_vars()

        assert "ANTHROPIC_BASE_URL" in env_vars
        assert "ANTHROPIC_API_KEY" in env_vars
        assert "ANTHROPIC_MODEL" in env_vars
        # Accept either localhost or 127.0.0.1
        assert (
            "localhost" in env_vars["ANTHROPIC_BASE_URL"]
            or "127.0.0.1" in env_vars["ANTHROPIC_BASE_URL"]
        )
        assert env_vars["ANTHROPIC_API_KEY"] == "local-qwen"


class TestQwenvertConfig:
    """Test QwenvertConfig class."""

    def test_save_and_load_config(self, temp_config_dir, sample_model_7b_q4):
        """Test saving and loading configuration."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
        )

        # Save to temp directory
        config_path = temp_config_dir / "config.yaml"
        saved_path = config.save(config_path)

        assert saved_path.exists()

        # Load it back
        loaded_config = QwenvertConfig.load(config_path)

        assert loaded_config.model_id == config.model_id
        assert loaded_config.backend == config.backend
        assert loaded_config.backend_url == config.backend_url


class TestConfigManager:
    """Test configuration management."""

    def test_save_and_load_through_manager(
        self, sample_model_7b_q4, monkeypatch, temp_config_dir
    ):
        """Test ConfigManager save/load operations."""

        # Monkey patch default config path to use temp directory
        @classmethod
        def mock_default_path(cls):
            return temp_config_dir / "config.yaml"

        monkeypatch.setattr(QwenvertConfig, "default_config_path", mock_default_path)

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
        )

        # Save
        ConfigManager.save(config)

        # Check exists
        assert ConfigManager.exists()

        # Load
        loaded = ConfigManager.load()
        assert loaded.model_id == config.model_id


class TestModelPathValidation:
    """Test model_path validation to prevent injection attacks."""

    def test_valid_absolute_path(self, sample_model_7b_q4):
        """Test that valid absolute paths pass validation."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            model_path="/Users/test/.qwenvert/models/model.gguf",
        )
        # Should not raise
        config.validate()

    def test_valid_home_path(self, sample_model_7b_q4):
        """Test that paths with ~ pass validation."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            model_path="~/.qwenvert/models/model.gguf",
        )
        # Should not raise
        config.validate()

    def test_none_model_path_is_valid(self, sample_model_7b_q4):
        """Test that None model_path is valid (falls back to pull)."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            model_path=None,
        )
        # Should not raise
        config.validate()

    def test_newline_injection_rejected(self, sample_model_7b_q4):
        """Test that paths with newlines are rejected (Modelfile injection)."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            model_path="/path/to/model.gguf\nPARAMETER num_ctx 999999",
        )
        with pytest.raises(ValueError, match="newline.*injection"):
            config.validate()

    def test_carriage_return_injection_rejected(self, sample_model_7b_q4):
        """Test that paths with carriage returns are rejected."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            model_path="/path/to/model.gguf\rSYSTEM malicious",
        )
        with pytest.raises(ValueError, match="newline.*injection"):
            config.validate()

    def test_control_character_rejected(self, sample_model_7b_q4):
        """Test that paths with control characters are rejected."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            model_path="/path/to/model\x00.gguf",  # Null byte
        )
        with pytest.raises(ValueError, match="control character"):
            config.validate()

    def test_modelfile_directive_injection_rejected(self, sample_model_7b_q4):
        """Test that paths with Modelfile directives are rejected."""
        # Create a path with a suspicious directory name
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            model_path="/tmp/FROM malicious/model.gguf",
        )
        with pytest.raises(ValueError, match="suspicious Modelfile keyword.*FROM"):
            config.validate()

    def test_parameter_directive_injection_rejected(self, sample_model_7b_q4):
        """Test that PARAMETER directive in path is rejected."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            model_path="/tmp/PARAMETER num_ctx/model.gguf",
        )
        with pytest.raises(ValueError, match="suspicious Modelfile keyword.*PARAMETER"):
            config.validate()

    def test_system_directive_injection_rejected(self, sample_model_7b_q4):
        """Test that SYSTEM directive in path is rejected."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            model_path="/tmp/SYSTEM malicious/model.gguf",
        )
        with pytest.raises(ValueError, match="suspicious Modelfile keyword.*SYSTEM"):
            config.validate()

    def test_empty_path_rejected(self, sample_model_7b_q4):
        """Test that empty paths are rejected."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            model_path="",
        )
        with pytest.raises(ValueError, match="empty"):
            config.validate()

    def test_whitespace_only_path_rejected(self, sample_model_7b_q4):
        """Test that whitespace-only paths are rejected."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
            model_path="   ",
        )
        with pytest.raises(ValueError, match="empty"):
            config.validate()

    def test_validation_runs_on_load(self, temp_config_dir, sample_model_7b_q4):
        """Test that validation runs when loading config from file."""
        import yaml

        # Create config file with malicious model_path
        config_path = temp_config_dir / "config.yaml"
        malicious_config = {
            "model_id": sample_model_7b_q4.id,
            "backend": Backend.OLLAMA.value,
            "backend_url": "http://localhost:11434",
            "backend_model_id": sample_model_7b_q4.backend_model_id,
            "model_path": "/path/to/model.gguf\nPARAMETER num_ctx 999999",
        }

        with open(config_path, "w") as f:
            yaml.safe_dump(malicious_config, f)

        # Loading should fail validation
        with pytest.raises(ValueError, match="newline.*injection"):
            QwenvertConfig.load(config_path)

    def test_modelfile_generation_with_validated_path(
        self, sample_model_7b_q4, mock_hardware_m1_16gb
    ):
        """Test that Modelfile generation works with validated paths."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_16gb)

        # Valid path should work
        valid_path = "/Users/test/.qwenvert/models/model.gguf"
        modelfile = gen.generate_ollama_modelfile(model_path=valid_path)

        assert f"FROM {valid_path}" in modelfile
        assert "PARAMETER num_ctx" in modelfile

    def test_modelfile_prevents_directive_injection(
        self, sample_model_7b_q4, mock_hardware_m1_16gb
    ):
        """Test that malicious paths don't inject directives into Modelfile."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_16gb)

        # This path would be caught by validation, but let's verify
        # the Modelfile generation itself doesn't introduce vulnerabilities
        valid_path = "/home/user/models/qwen-model.gguf"
        modelfile = gen.generate_ollama_modelfile(model_path=valid_path)

        # Count occurrences of PARAMETER - should only be the intended ones
        param_count = modelfile.count("PARAMETER")
        # Expected: num_ctx, num_gpu, num_thread, temperature, top_p, top_k, repeat_penalty
        assert param_count == 7

        # Count FROM - should only be one
        from_count = modelfile.count("FROM")
        assert from_count == 1

        # Count SYSTEM - should only be one
        system_count = modelfile.count("SYSTEM")
        assert system_count == 1
