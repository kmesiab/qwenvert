"""Unit tests for MLX backend implementation."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from qwenvert.backend_interface import BackendInfo, BackendStatus
from qwenvert.backends.mlx_backend import MLXBackend
from qwenvert.hardware import HardwareProfile
from qwenvert.models import Backend, Model


@pytest.fixture
def mock_hardware():
    """Create mock HardwareProfile for Apple Silicon."""
    return HardwareProfile(
        chip="M1 Pro",
        chip_family="M1",
        total_memory_gb=16,
        gpu_cores=16,
        cpu_cores_performance=6,
        cpu_cores_efficiency=2,
        has_active_cooling=True,
        neural_engine_cores=16,
        model_identifier="MacBookPro18,3",
    )


@pytest.fixture
def mock_mlx_model():
    """Create mock MLX Model."""
    return Model(
        id="qwen2.5-coder-7b-q4-mlx",
        display_name="Qwen2.5 Coder 7B Q4 (MLX)",
        family="qwen2.5-coder",
        size_b=7,
        quantization="q4",
        backend=Backend.MLX,
        backend_model_id="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
        context_length=32768,
        max_output_tokens=12288,
        min_ram_gb=8,
        recommended_ram_gb=12,
        huggingface_repo="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
        notes="MLX optimized for Apple Silicon",
    )


class TestMLXBackend:
    """Test MLXBackend implementation."""

    def test_detect_available(self):
        """Test detection when MLX is available."""
        backend = MLXBackend()

        # Create mock modules
        mock_mlx_core = Mock()
        mock_mlx_lm = Mock()
        mock_mlx_lm.__version__ = "0.10.0"
        mock_mlx_lm.__file__ = "/opt/homebrew/lib/python3.11/site-packages/mlx_lm/__init__.py"

        # Mock the import by patching builtins.__import__
        import builtins

        original_import = builtins.__import__

        def custom_import(name, *args, **kwargs):
            if name == "mlx.core":
                return mock_mlx_core
            if name == "mlx_lm":
                return mock_mlx_lm
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=custom_import):
            info = backend.detect()

            assert info.name == "MLX"
            assert info.version == "0.10.0"
            assert info.status == BackendStatus.AVAILABLE
            assert info.installation_method == "pip"

    def test_detect_missing(self):
        """Test detection when MLX is not available."""
        backend = MLXBackend()

        # Simulate ImportError for mlx
        with patch.dict("sys.modules", {"mlx.core": None, "mlx_lm": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                info = backend.detect()

                assert info.name == "MLX"
                assert info.version is None
                assert info.status == BackendStatus.MISSING
                assert info.path is None

    def test_install_success_darwin(self):
        """Test successful installation on macOS."""
        backend = MLXBackend()

        with patch("sys.platform", "darwin"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

                # Mock detect after install
                mock_info = BackendInfo(
                    name="MLX",
                    version="0.10.0",
                    path=Path("/opt/homebrew/lib/python3.11/site-packages/mlx_lm"),
                    status=BackendStatus.AVAILABLE,
                    installation_method="pip",
                )

                with patch.object(backend, "detect", return_value=mock_info):
                    info = backend.install(auto=True)

                    assert info.status == BackendStatus.AVAILABLE
                    assert info.version == "0.10.0"

    def test_install_failure_non_macos(self):
        """Test installation failure on non-macOS platform."""
        backend = MLXBackend()

        with patch("sys.platform", "linux"):
            info = backend.install(auto=True)

            assert info.status == BackendStatus.FAILED
            assert info.version is None

    def test_install_pip_failure(self):
        """Test installation failure when pip fails."""
        backend = MLXBackend()

        with patch("sys.platform", "darwin"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(
                    returncode=1, stdout="", stderr="pip install failed"
                )

                info = backend.install(auto=True)

                assert info.status == BackendStatus.FAILED

    def test_install_auto_false(self):
        """Test installation with auto=False raises error."""
        backend = MLXBackend()

        with pytest.raises(RuntimeError, match="MLX not found and auto-install disabled"):
            backend.install(auto=False)

    def test_configure(self, mock_mlx_model, mock_hardware):
        """Test MLX configuration generation."""
        backend = MLXBackend()

        config = backend.configure(mock_mlx_model, mock_hardware)

        assert "model_path" in config
        assert "quantization" in config
        assert "max_tokens" in config
        assert "server_url" in config
        assert config["model_path"] == "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
        assert config["quantization"] == "q4"
        assert config["server_url"] == "in-process"

    def test_configure_uses_huggingface_repo(self, mock_hardware):
        """Test that configuration uses huggingface_repo when available."""
        backend = MLXBackend()

        model = Model(
            id="test-model",
            display_name="Test Model",
            family="test",
            size_b=7,
            quantization="Q4_K_M",
            backend=Backend.MLX,
            backend_model_id="old-path",
            context_length=32768,
            max_output_tokens=12288,
            min_ram_gb=8,
            recommended_ram_gb=12,
            huggingface_repo="mlx-community/TestModel-4bit",
        )

        config = backend.configure(model, mock_hardware)

        assert config["model_path"] == "mlx-community/TestModel-4bit"

    def test_configure_lowercase_quantization(self, mock_hardware):
        """Test that quantization is converted to lowercase."""
        backend = MLXBackend()

        model = Model(
            id="test-model",
            display_name="Test Model",
            family="test",
            size_b=7,
            quantization="Q4_K_M",
            backend=Backend.MLX,
            backend_model_id="mlx-community/TestModel",
            context_length=32768,
            max_output_tokens=12288,
            min_ram_gb=8,
            recommended_ram_gb=12,
        )

        config = backend.configure(model, mock_hardware)

        assert config["quantization"] == "q4_k_m"

    def test_get_server_url(self):
        """Test get_server_url returns in-process."""
        backend = MLXBackend()

        assert backend.get_server_url() == "in-process"

    def test_health_check_success(self):
        """Test health check when MLX is functional."""
        backend = MLXBackend()

        mock_mx = Mock()
        mock_mx.gpu = "gpu"
        mock_mx.set_default_device = Mock()

        # Create a mock mlx parent module
        mock_mlx = Mock()
        mock_mlx.core = mock_mx

        # Mock both mlx and mlx.core modules in sys.modules
        with patch.dict("sys.modules", {"mlx": mock_mlx, "mlx.core": mock_mx}):
            result = backend.health_check()
            assert result is True
            mock_mx.set_default_device.assert_called_once_with(mock_mx.gpu)

    def test_health_check_failure(self):
        """Test health check when MLX fails."""
        backend = MLXBackend()

        # Create a mock that raises an exception when set_default_device is called
        mock_mx = Mock()
        mock_mx.gpu = "gpu"
        mock_mx.set_default_device.side_effect = Exception("MLX error")

        # Create a mock mlx parent module
        mock_mlx = Mock()
        mock_mlx.core = mock_mx

        with patch.dict("sys.modules", {"mlx": mock_mlx, "mlx.core": mock_mx}):
            result = backend.health_check()
            assert result is False
