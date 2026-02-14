"""Unit tests for backend abstraction layer (Phase 3)."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from qwenvert.backend_interface import BackendInfo, BackendStatus
from qwenvert.backend_manager import BackendManager
from qwenvert.backends.llamacpp_backend import LlamaCppBackend
from qwenvert.backends.ollama_backend import OllamaBackend
from qwenvert.binary_manager import BinaryInfo, BinarySource
from qwenvert.hardware import HardwareProfile
from qwenvert.models import Backend, Model


@pytest.fixture
def mock_hardware():
    """Create mock HardwareProfile."""
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
def mock_model():
    """Create mock Model."""
    return Model(
        id="qwen2.5-coder-7b-q4-llamacpp",
        backend=Backend.LLAMACPP,
        backend_model_id="qwen2.5-coder-7b-instruct-q4_K_M.gguf",
        context_length=32768,
        max_output_tokens=16384,
        min_ram_gb=8,
        recommended_ram_gb=12,
    )


class TestLlamaCppBackend:
    """Test LlamaCppBackend implementation."""

    def test_detect_available(self):
        """Test detection when llama-server is available."""
        backend = LlamaCppBackend()

        mock_binary = BinaryInfo(
            path=Path("/usr/local/bin/llama-server"),
            version="b3600",
            source=BinarySource.SYSTEM,
            architecture="arm64",
            is_valid=True,
        )

        with patch.object(
            backend.binary_manager, "detect_binary", return_value=mock_binary
        ):
            info = backend.detect()

            assert info.name == "llama.cpp"
            assert info.version == "b3600"
            assert info.status == BackendStatus.AVAILABLE
            assert info.path == mock_binary.path

    def test_detect_missing(self):
        """Test detection when llama-server is not available."""
        backend = LlamaCppBackend()

        with patch.object(backend.binary_manager, "detect_binary", return_value=None):
            info = backend.detect()

            assert info.name == "llama.cpp"
            assert info.version is None
            assert info.status == BackendStatus.MISSING
            assert info.path is None

    def test_install_success(self):
        """Test successful installation."""
        backend = LlamaCppBackend()

        mock_binary = BinaryInfo(
            path=Path("/cache/llama-server"),
            version="b3600",
            source=BinarySource.DOWNLOADED,
            architecture="arm64",
            is_valid=True,
        )

        with patch.object(
            backend.binary_manager, "get_or_install_binary", return_value=mock_binary
        ):
            info = backend.install(auto=True)

            assert info.status == BackendStatus.AVAILABLE
            assert info.version == "b3600"

    def test_install_failure(self):
        """Test installation failure."""
        backend = LlamaCppBackend()

        with patch.object(
            backend.binary_manager,
            "get_or_install_binary",
            side_effect=RuntimeError("Install failed"),
        ):
            info = backend.install(auto=True)

            assert info.status == BackendStatus.FAILED
            assert info.version is None

    def test_configure(self, mock_model, mock_hardware):
        """Test configuration generation."""
        backend = LlamaCppBackend()

        with patch("qwenvert.backends.llamacpp_backend.ConfigGenerator") as mock_gen_cls:
            mock_gen = Mock()
            mock_gen.generate_llamacpp_flags.return_value = [
                "--model",
                "test.gguf",
                "-ngl",
                "99",
            ]
            mock_gen_cls.return_value = mock_gen

            config = backend.configure(mock_model, mock_hardware)

            assert "binary_path" in config
            assert "flags" in config
            assert "server_url" in config
            assert config["server_url"] == "http://localhost:8080"

    def test_health_check_healthy(self):
        """Test health check when server is healthy."""
        backend = LlamaCppBackend()

        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = backend.health_check()
            assert result is True

    def test_health_check_unhealthy(self):
        """Test health check when server is unhealthy."""
        backend = LlamaCppBackend()

        with patch("httpx.get", side_effect=Exception("Connection error")):
            result = backend.health_check()
            assert result is False


class TestOllamaBackend:
    """Test OllamaBackend implementation."""

    def test_detect_available(self):
        """Test detection when Ollama is available."""
        backend = OllamaBackend()

        with patch("shutil.which", return_value="/usr/local/bin/ollama"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(
                    returncode=0, stdout="ollama version 0.1.26"
                )

                info = backend.detect()

                assert info.name == "ollama"
                assert info.version == "0.1.26"
                assert info.status == BackendStatus.AVAILABLE

    def test_detect_missing(self):
        """Test detection when Ollama is not available."""
        backend = OllamaBackend()

        with patch("shutil.which", return_value=None):
            info = backend.detect()

            assert info.name == "ollama"
            assert info.version is None
            assert info.status == BackendStatus.MISSING

    def test_install_success(self):
        """Test successful Homebrew installation."""
        backend = OllamaBackend()

        with patch("shutil.which", return_value="/opt/homebrew/bin/brew"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(returncode=0)

                # Mock detect after install
                mock_info = BackendInfo(
                    name="ollama",
                    version="0.1.26",
                    path=Path("/opt/homebrew/bin/ollama"),
                    status=BackendStatus.AVAILABLE,
                    installation_method="homebrew",
                )

                with patch.object(backend, "detect", return_value=mock_info):
                    info = backend.install(auto=True)

                    assert info.status == BackendStatus.AVAILABLE

    def test_install_no_brew(self):
        """Test installation failure when Homebrew not available."""
        backend = OllamaBackend()

        with patch("shutil.which", return_value=None):
            info = backend.install(auto=True)

            assert info.status == BackendStatus.FAILED

    def test_configure(self, mock_hardware):
        """Test Ollama configuration generation."""
        backend = OllamaBackend()

        ollama_model = Model(
            id="qwen2.5-coder-7b-q4-ollama",
            backend=Backend.OLLAMA,
            backend_model_id="qwen2.5-coder:7b-instruct-q4_K_M",
            context_length=32768,
            max_output_tokens=16384,
            min_ram_gb=8,
            recommended_ram_gb=12,
        )

        with patch("qwenvert.backends.ollama_backend.ConfigGenerator") as mock_gen_cls:
            mock_gen = Mock()
            mock_gen.generate_ollama_modelfile.return_value = "FROM qwen2.5-coder:7b"
            mock_gen_cls.return_value = mock_gen

            config = backend.configure(ollama_model, mock_hardware)

            assert "modelfile" in config
            assert "server_url" in config
            assert "model_id" in config
            assert config["server_url"] == "http://localhost:11434"

    def test_health_check(self):
        """Test Ollama health check."""
        backend = OllamaBackend()

        with patch("httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = backend.health_check()
            assert result is True


class TestBackendManager:
    """Test BackendManager factory."""

    def test_get_backend_llamacpp(self):
        """Test getting llama.cpp backend."""
        backend = BackendManager.get_backend(Backend.LLAMACPP)
        assert isinstance(backend, LlamaCppBackend)

    def test_get_backend_ollama(self):
        """Test getting Ollama backend."""
        backend = BackendManager.get_backend(Backend.OLLAMA)
        assert isinstance(backend, OllamaBackend)

    def test_get_backend_invalid(self):
        """Test getting invalid backend."""
        with pytest.raises(ValueError, match="Unknown backend"):
            BackendManager.get_backend(Backend.MLX)

    def test_detect_all(self):
        """Test detecting all backends."""
        mock_llamacpp_info = BackendInfo(
            name="llama.cpp",
            version="b3600",
            path=Path("/usr/local/bin/llama-server"),
            status=BackendStatus.AVAILABLE,
            installation_method="system",
        )

        mock_ollama_info = BackendInfo(
            name="ollama",
            version=None,
            path=None,
            status=BackendStatus.MISSING,
            installation_method="none",
        )

        with patch.object(LlamaCppBackend, "detect", return_value=mock_llamacpp_info):
            with patch.object(OllamaBackend, "detect", return_value=mock_ollama_info):
                results = BackendManager.detect_all()

                assert Backend.LLAMACPP in results
                assert Backend.OLLAMA in results
                assert results[Backend.LLAMACPP].status == BackendStatus.AVAILABLE
                assert results[Backend.OLLAMA].status == BackendStatus.MISSING

    def test_recommend_backend_llamacpp_available(self, mock_hardware):
        """Test recommendation when llama.cpp is available."""
        mock_llamacpp = BackendInfo(
            name="llama.cpp",
            version="b3600",
            path=Path("/usr/local/bin/llama-server"),
            status=BackendStatus.AVAILABLE,
            installation_method="system",
        )

        mock_ollama = BackendInfo(
            name="ollama",
            version=None,
            path=None,
            status=BackendStatus.MISSING,
            installation_method="none",
        )

        with patch.object(
            BackendManager,
            "detect_all",
            return_value={Backend.LLAMACPP: mock_llamacpp, Backend.OLLAMA: mock_ollama},
        ):
            recommended = BackendManager.recommend_backend(mock_hardware)
            assert recommended == Backend.LLAMACPP

    def test_recommend_backend_ollama_fallback(self, mock_hardware):
        """Test recommendation when only Ollama is available."""
        mock_llamacpp = BackendInfo(
            name="llama.cpp",
            version=None,
            path=None,
            status=BackendStatus.MISSING,
            installation_method="none",
        )

        mock_ollama = BackendInfo(
            name="ollama",
            version="0.1.26",
            path=Path("/usr/local/bin/ollama"),
            status=BackendStatus.AVAILABLE,
            installation_method="system",
        )

        with patch.object(
            BackendManager,
            "detect_all",
            return_value={Backend.LLAMACPP: mock_llamacpp, Backend.OLLAMA: mock_ollama},
        ):
            recommended = BackendManager.recommend_backend(mock_hardware)
            assert recommended == Backend.OLLAMA

    def test_recommend_backend_default(self, mock_hardware):
        """Test default recommendation when none available."""
        mock_llamacpp = BackendInfo(
            name="llama.cpp",
            version=None,
            path=None,
            status=BackendStatus.MISSING,
            installation_method="none",
        )

        mock_ollama = BackendInfo(
            name="ollama",
            version=None,
            path=None,
            status=BackendStatus.MISSING,
            installation_method="none",
        )

        with patch.object(
            BackendManager,
            "detect_all",
            return_value={Backend.LLAMACPP: mock_llamacpp, Backend.OLLAMA: mock_ollama},
        ):
            recommended = BackendManager.recommend_backend(mock_hardware)
            # Defaults to llama.cpp (will trigger auto-install)
            assert recommended == Backend.LLAMACPP
