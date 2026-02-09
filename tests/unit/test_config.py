"""
Unit tests for configuration generation.
"""

import pytest
from pathlib import Path

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
        assert "localhost" in env_vars["ANTHROPIC_BASE_URL"] or "127.0.0.1" in env_vars["ANTHROPIC_BASE_URL"]
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
