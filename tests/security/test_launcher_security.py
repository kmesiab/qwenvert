"""
Security tests for ServerLauncher.

Verifies that launcher validates adapter_host and backend_url before starting servers.
This is CRITICAL for preventing the 0.0.0.0 binding vulnerability.
"""

import pytest

from qwenvert.config import QwenvertConfig
from qwenvert.launcher import ServerLauncher
from qwenvert.models import Backend
from qwenvert.security import SecurityValidationError


@pytest.fixture
def valid_config():
    """Create valid localhost-only configuration."""
    return QwenvertConfig(
        model_id="qwen2.5-coder-7b-q4",
        backend="ollama",
        backend_url="http://localhost:11434",
        backend_model_id="qwen2.5-coder:7b",
        adapter_host="127.0.0.1",
        adapter_port=8088,
        context_length=4096,
    )


@pytest.fixture
def launcher(valid_config):
    """Create launcher with valid config."""
    return ServerLauncher(valid_config)


class TestLauncherAdapterHostValidation:
    """Test that launcher validates adapter_host before binding."""

    @pytest.mark.asyncio
    async def test_launcher_accepts_localhost_adapter_host(self, launcher):
        """Should accept localhost adapter host."""
        # Config has localhost host, should not raise during setup
        assert launcher.config.adapter_host == "127.0.0.1"
        # No exception = success

    @pytest.mark.asyncio
    async def test_launcher_rejects_0_0_0_0_adapter_host(self, valid_config):
        """Should reject 0.0.0.0 adapter host (CRITICAL VULNERABILITY FIX)."""
        # This is the main vulnerability - config file could be tampered to set 0.0.0.0
        valid_config.adapter_host = "0.0.0.0"
        launcher = ServerLauncher(valid_config)

        # Mock backend process
        from unittest.mock import MagicMock

        mock_backend = MagicMock()

        # Should fail validation before binding
        with pytest.raises(SecurityValidationError) as exc_info:
            await launcher.start_adapter(mock_backend)

        error_msg = str(exc_info.value)
        assert "0.0.0.0" in error_msg
        assert "Security violation" in error_msg

    @pytest.mark.asyncio
    async def test_launcher_rejects_non_localhost_adapter_host(self, valid_config):
        """Should reject external domain as adapter host."""
        valid_config.adapter_host = "example.com"
        launcher = ServerLauncher(valid_config)

        from unittest.mock import MagicMock

        mock_backend = MagicMock()

        with pytest.raises(SecurityValidationError):
            await launcher.start_adapter(mock_backend)

    @pytest.mark.asyncio
    async def test_launcher_rejects_lan_ip_adapter_host(self, valid_config):
        """Should reject LAN IP as adapter host."""
        valid_config.adapter_host = "192.168.1.100"
        launcher = ServerLauncher(valid_config)

        from unittest.mock import MagicMock

        mock_backend = MagicMock()

        with pytest.raises(SecurityValidationError):
            await launcher.start_adapter(mock_backend)


class TestLauncherBackendUrlValidation:
    """Test that launcher validates backend_url."""

    @pytest.mark.asyncio
    async def test_launcher_validates_backend_url(self, valid_config):
        """Should validate backend URL through BackendRouter."""
        valid_config.backend_url = "http://evil.com:11434"
        launcher = ServerLauncher(valid_config)

        from unittest.mock import MagicMock, patch

        mock_backend = MagicMock()

        # Mock model registry to return a valid model
        from qwenvert.models import Backend, Model

        mock_model = Model(
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

        with patch("qwenvert.models.ModelRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.get_model.return_value = mock_model
            mock_registry_class.return_value = mock_registry

            # BackendRouter should raise SecurityValidationError when given evil.com URL
            with pytest.raises(SecurityValidationError):
                await launcher.start_adapter(mock_backend)


class TestLauncherHealthCheckValidation:
    """Test that launcher validates URLs before health checks."""

    @pytest.mark.asyncio
    async def test_check_health_accepts_localhost(self, launcher):
        """Should accept localhost URL for health checks."""
        # Should not raise
        result = await launcher._check_health("http://localhost:11434/health")
        # Result will be False since no server is running, but validation passed

    @pytest.mark.asyncio
    async def test_check_health_rejects_external_url(self, launcher):
        """Should reject external URL for health checks."""
        with pytest.raises(SecurityValidationError):
            await launcher._check_health("http://evil.com/health")

    @pytest.mark.asyncio
    async def test_check_health_rejects_0_0_0_0(self, launcher):
        """Should reject 0.0.0.0 URL for health checks."""
        with pytest.raises(SecurityValidationError):
            await launcher._check_health("http://0.0.0.0:11434/health")


class TestConfigFileTamperingDetection:
    """Test that launcher detects tampered config files."""

    @pytest.mark.asyncio
    async def test_config_file_tampering_detected(self, valid_config):
        """
        Simulate user manually editing config file to set 0.0.0.0.
        Launcher should detect and reject this at startup.
        """
        # User tampers with config file
        valid_config.adapter_host = "0.0.0.0"

        launcher = ServerLauncher(valid_config)

        from unittest.mock import MagicMock

        mock_backend = MagicMock()

        # Should fail validation
        with pytest.raises(SecurityValidationError) as exc_info:
            await launcher.start_adapter(mock_backend)

        # Error should explain the security issue
        error_msg = str(exc_info.value)
        assert "0.0.0.0" in error_msg
        assert "network" in error_msg.lower() or "internet" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_launcher_fails_fast_on_invalid_config(self, valid_config):
        """Validation should happen immediately, not after server starts."""
        valid_config.adapter_host = "0.0.0.0"
        launcher = ServerLauncher(valid_config)

        from unittest.mock import MagicMock

        mock_backend = MagicMock()

        # Should fail before attempting to bind
        with pytest.raises(SecurityValidationError):
            await launcher.start_adapter(mock_backend)

        # Verify no server was started (no cleanup needed)
        assert not hasattr(launcher, "adapter_task") or launcher.adapter_task is None
