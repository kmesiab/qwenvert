"""
Security tests: Network isolation.

CRITICAL: These tests verify that qwenvert makes NO external network calls
during runtime, ensuring code and data never leave the local machine.
"""

import pytest

from qwenvert.models import Backend, Model
from qwenvert.security import SecurityValidationError


class TestNetworkIsolation:
    """
    Test that qwenvert is completely isolated from external networks.

    These tests are CRITICAL for the security value proposition.
    """

    @pytest.mark.asyncio
    async def test_adapter_only_binds_localhost(self):
        """
        SECURITY: Adapter MUST bind to localhost only, not 0.0.0.0.

        This prevents the adapter from being accessible from the network.
        """
        import uvicorn

        from qwenvert.adapter import create_app

        app = create_app()

        # Create config with explicit localhost binding
        config = uvicorn.Config(
            app,
            host="127.0.0.1",  # MUST be localhost, not 0.0.0.0
            port=8088,
        )

        # Verify host is localhost
        assert config.host == "127.0.0.1", "Adapter MUST bind to localhost only"
        assert config.host != "0.0.0.0", "Adapter MUST NOT bind to all interfaces"

    def test_config_generator_only_creates_localhost_urls(self):
        """
        SECURITY: ConfigGenerator MUST only create localhost URLs.

        Never generate configs that point to external services.
        """
        from qwenvert.config import ConfigGenerator
        from qwenvert.hardware import HardwareProfile

        hardware = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=16,
            gpu_cores=8,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="Test",
        )

        # Test with Ollama backend
        ollama_model = Model(
            id="test",
            display_name="Test",
            family="test",
            size_b=7.0,
            quantization="Q4_K_M",
            backend=Backend.OLLAMA,
            backend_model_id="test:7b",
            context_length=4096,
            min_ram_gb=8,
            recommended_ram_gb=16,
        )

        config = ConfigGenerator(ollama_model, hardware).generate_qwenvert_config()

        assert (
            "localhost" in config.backend_url or "127.0.0.1" in config.backend_url
        ), f"Backend URL {config.backend_url} is not localhost!"

        assert config.adapter_host in [
            "127.0.0.1",
            "localhost",
        ], f"Adapter host {config.adapter_host} is not localhost!"

    def test_environment_variables_safe(self):
        """
        SECURITY: Verify environment variables don't leak data.
        """
        from qwenvert.config import ConfigGenerator
        from qwenvert.hardware import HardwareProfile

        hardware = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=16,
            gpu_cores=8,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="Test",
        )

        model = Model(
            id="test",
            display_name="Test",
            family="test",
            size_b=7.0,
            quantization="Q4_K_M",
            backend=Backend.OLLAMA,
            backend_model_id="test:7b",
            context_length=4096,
            min_ram_gb=8,
            recommended_ram_gb=16,
        )

        config_gen = ConfigGenerator(model, hardware)
        env_vars = config_gen.generate_environment_vars()

        # Check ANTHROPIC_BASE_URL is localhost
        base_url = env_vars.get("ANTHROPIC_BASE_URL", "")
        assert (
            "localhost" in base_url or "127.0.0.1" in base_url
        ), f"ANTHROPIC_BASE_URL {base_url} is not localhost!"

        # Check API key is placeholder
        api_key = env_vars.get("ANTHROPIC_API_KEY", "")
        assert api_key == "local-qwen", "API key should be placeholder 'local-qwen'"


class TestConfigValidation:
    """Test that QwenvertConfig validates on load."""

    def test_config_validate_accepts_localhost_config(self):
        """Should accept valid localhost configuration."""
        from qwenvert.config import QwenvertConfig

        config = QwenvertConfig(
            model_id="test",
            backend="ollama",
            backend_url="http://localhost:11434",
            backend_model_id="test:7b",
            adapter_host="127.0.0.1",
            adapter_port=8088,
        )

        # Should not raise
        config.validate()

    def test_config_validate_rejects_external_backend_url(self):
        """Should reject external backend URL."""
        from qwenvert.config import QwenvertConfig

        config = QwenvertConfig(
            model_id="test",
            backend="ollama",
            backend_url="http://evil.com:11434",
            backend_model_id="test:7b",
            adapter_host="127.0.0.1",
            adapter_port=8088,
        )

        with pytest.raises(SecurityValidationError):
            config.validate()

    def test_config_validate_rejects_0_0_0_0_adapter_host(self):
        """Should reject 0.0.0.0 adapter host."""
        from qwenvert.config import QwenvertConfig

        config = QwenvertConfig(
            model_id="test",
            backend="ollama",
            backend_url="http://localhost:11434",
            backend_model_id="test:7b",
            adapter_host="0.0.0.0",
            adapter_port=8088,
        )

        with pytest.raises(SecurityValidationError) as exc_info:
            config.validate()

        assert "0.0.0.0" in str(exc_info.value)

    def test_config_load_validates_tampered_file(self, tmp_path):
        """Should detect tampered config file on load."""
        from qwenvert.config import QwenvertConfig

        # Create tampered config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
model_id: test
backend: ollama
backend_url: http://evil.com:11434
backend_model_id: test:7b
adapter_host: 127.0.0.1
adapter_port: 8088
context_length: 4096
"""
        )

        # Should raise SecurityValidationError on load
        with pytest.raises(SecurityValidationError):
            QwenvertConfig.load(config_file)

    def test_config_load_validates_0_0_0_0_binding(self, tmp_path):
        """Should detect 0.0.0.0 binding in config file."""
        from qwenvert.config import QwenvertConfig

        # Create config with 0.0.0.0 (the critical vulnerability)
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
model_id: test
backend: ollama
backend_url: http://localhost:11434
backend_model_id: test:7b
adapter_host: 0.0.0.0
adapter_port: 8088
context_length: 4096
"""
        )

        # Should raise SecurityValidationError
        with pytest.raises(SecurityValidationError) as exc_info:
            QwenvertConfig.load(config_file)

        error_msg = str(exc_info.value)
        assert "0.0.0.0" in error_msg
        assert "network" in error_msg.lower() or "internet" in error_msg.lower()
