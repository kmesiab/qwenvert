"""
Unit tests for configuration generation.
"""

from pathlib import Path

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

    def test_generate_qwenvert_config_llamacpp_backend(
        self, sample_model_14b_q5, mock_hardware_m1_16gb
    ):
        """Test generating qwenvert config for llama.cpp backend."""
        gen = ConfigGenerator(sample_model_14b_q5, mock_hardware_m1_16gb)
        config = gen.generate_qwenvert_config()

        assert config.backend == Backend.LLAMACPP.value
        assert config.backend_url == "http://localhost:8080"

    def test_generate_qwenvert_config_custom_adapter_settings(
        self, sample_model_7b_q4, mock_hardware_m1_16gb
    ):
        """Test generating config with custom adapter settings."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_16gb)
        config = gen.generate_qwenvert_config(adapter_host="0.0.0.0", adapter_port=9000)

        assert config.adapter_host == "0.0.0.0"
        assert config.adapter_port == 9000

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

    def test_generate_ollama_modelfile_wrong_backend_raises_error(
        self, sample_model_14b_q5, mock_hardware_m1_16gb
    ):
        """Test that Ollama Modelfile generation fails for non-Ollama backend."""
        gen = ConfigGenerator(sample_model_14b_q5, mock_hardware_m1_16gb)

        with pytest.raises(ValueError, match="not Ollama"):
            gen.generate_ollama_modelfile()

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

    def test_generate_llamacpp_flags_wrong_backend_raises_error(
        self, sample_model_7b_q4, mock_hardware_m1_16gb
    ):
        """Test that llama.cpp flags generation fails for non-llama.cpp backend."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_16gb)

        with pytest.raises(ValueError, match="not llama.cpp"):
            gen.generate_llamacpp_flags()

    def test_print_setup_instructions(self, sample_model_7b_q4, mock_hardware_m1_16gb):
        """Test setup instructions generation."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_16gb)
        instructions = gen.print_setup_instructions()

        assert "Qwenvert Setup Complete" in instructions
        assert sample_model_7b_q4.display_name in instructions
        assert "ANTHROPIC_BASE_URL" in instructions
        assert "ANTHROPIC_API_KEY" in instructions
        assert "claude" in instructions

    def test_environment_vars_generation(
        self, sample_model_7b_q4, mock_hardware_m1_16gb
    ):
        """Test environment variable generation."""
        gen = ConfigGenerator(sample_model_7b_q4, mock_hardware_m1_16gb)
        env_vars = gen.generate_environment_vars()

        assert "ANTHROPIC_BASE_URL" in env_vars
        assert "ANTHROPIC_API_KEY" in env_vars
        assert "ANTHROPIC_MODEL" in env_vars
        assert "127.0.0.1" in env_vars["ANTHROPIC_BASE_URL"]
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

    def test_load_nonexistent_config_raises_error(self, temp_config_dir):
        """Test loading non-existent config raises FileNotFoundError."""
        config_path = temp_config_dir / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            QwenvertConfig.load(config_path)

    def test_default_config_path(self):
        """Test default config path creation."""
        path = QwenvertConfig.default_config_path()

        assert ".config" in str(path)
        assert "qwenvert" in str(path)
        assert "config.yaml" in str(path)

    def test_save_creates_parent_directories(self, temp_config_dir, sample_model_7b_q4):
        """Test that save creates parent directories if they don't exist."""
        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
        )

        # Use a deeply nested path that doesn't exist
        nested_path = temp_config_dir / "deeply" / "nested" / "path" / "config.yaml"
        saved_path = config.save(nested_path)

        assert saved_path.exists()
        assert saved_path.parent.exists()


class TestConfigManager:
    """Test configuration management."""

    def test_save_and_load_through_manager(
        self, sample_model_7b_q4, monkeypatch, temp_config_dir
    ):
        """Test ConfigManager save/load operations."""

        # Monkey patch default config path to use temp directory
        def mock_default_path(cls):
            return temp_config_dir / "config.yaml"

        monkeypatch.setattr(
            QwenvertConfig, "default_config_path", classmethod(mock_default_path)
        )

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

    def test_delete_config(self, sample_model_7b_q4, monkeypatch, temp_config_dir):
        """Test ConfigManager delete operation."""

        def mock_default_path(cls):
            return temp_config_dir / "config.yaml"

        monkeypatch.setattr(
            QwenvertConfig, "default_config_path", classmethod(mock_default_path)
        )

        config = QwenvertConfig(
            model_id=sample_model_7b_q4.id,
            backend=Backend.OLLAMA.value,
            backend_url="http://localhost:11434",
            backend_model_id=sample_model_7b_q4.backend_model_id,
        )

        # Save config
        ConfigManager.save(config)
        assert ConfigManager.exists()

        # Delete config
        ConfigManager.delete()
        assert not ConfigManager.exists()

    def test_save_ollama_modelfile(self, temp_config_dir, monkeypatch):
        """Test saving Ollama Modelfile."""

        def mock_modelfile_path():
            return temp_config_dir / "Modelfile.qwenvert"

        monkeypatch.setattr(
            ConfigManager, "get_ollama_modelfile_path", mock_modelfile_path
        )

        content = "FROM qwen2.5-coder:7b\nPARAMETER num_ctx 16384"
        path = ConfigManager.save_ollama_modelfile(content)

        assert path.exists()
        assert path.read_text() == content

    def test_get_ollama_modelfile_path(self, monkeypatch, temp_config_dir):
        """Test getting Ollama Modelfile path."""

        def mock_home():
            return temp_config_dir.parent.parent

        monkeypatch.setattr(Path, "home", mock_home)

        path = ConfigManager.get_ollama_modelfile_path()
        assert "Modelfile.qwenvert" in str(path)
