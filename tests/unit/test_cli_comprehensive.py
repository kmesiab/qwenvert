"""
Comprehensive CLI tests to achieve 70%+ coverage.

Tests all qwenvert CLI commands with proper mocking of internal imports.
Key insight: Imports happen INSIDE functions, so patch at the SOURCE module location,
not at qwenvert.cli.X
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from click.testing import CliRunner

from qwenvert.cli import cli
from qwenvert.config import QwenvertConfig
from qwenvert.hardware import HardwareProfile
from qwenvert.models import Backend, Model


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_hardware():
    """Mock hardware profile."""
    return HardwareProfile(
        chip="M1 Pro",
        chip_family="M1",
        total_memory_gb=16,
        gpu_cores=16,
        cpu_cores_performance=8,
        cpu_cores_efficiency=2,
        has_active_cooling=True,
        neural_engine_cores=16,
        model_identifier="MacBookPro18,1",
    )


@pytest.fixture
def mock_model():
    """Mock model."""
    return Model(
        id="qwen2.5-coder-7b-q4-ollama",
        display_name="Qwen2.5 Coder 7B Q4",
        family="qwen2.5-coder",
        size_b=7.0,
        quantization="Q4_K_M",
        backend=Backend.OLLAMA,
        backend_model_id="qwen2.5-coder:7b",
        context_length=32768,
        max_output_tokens=12288,
        min_ram_gb=8,
        recommended_ram_gb=16,
        huggingface_repo="Qwen/Qwen2.5-Coder-7B-GGUF",
    )


@pytest.fixture
def mock_config():
    """Mock qwenvert config."""
    return QwenvertConfig(
        backend="ollama",
        backend_url="http://localhost:11434",
        model_id="qwen2.5-coder-7b-q4-ollama",
        backend_model_id="qwen2.5-coder:7b",
        context_length=32768,
        adapter_host="127.0.0.1",
        adapter_port=8088,
        thermal_pacing=False,
        thermal_monitoring=True,
    )


@pytest.fixture(autouse=True)
def mock_backend_dependencies():
    """Auto-mock backend dependency checks for all tests."""
    with patch("qwenvert.dependencies.check_backend_dependencies") as mock_check:
        mock_result = MagicMock()
        mock_result.is_available = True
        mock_check.return_value = mock_result
        yield mock_check


@pytest.fixture(autouse=True)
def mock_binary_manager():
    """Auto-mock BinaryManager for all tests."""
    from pathlib import Path

    from qwenvert.binary_manager import BinaryInfo, BinarySource

    mock_binary_info = BinaryInfo(
        path=Path("/usr/local/bin/llama-server"),
        version="b3600",
        source=BinarySource.SYSTEM,
        architecture="arm64",
        is_valid=True,
    )

    with patch("qwenvert.cli.BinaryManager") as mock_mgr_cls:
        mock_mgr = MagicMock()
        mock_mgr.detect_binary.return_value = mock_binary_info
        mock_mgr_cls.return_value = mock_mgr
        yield mock_mgr


class TestInitCommand:
    """Test 'qwenvert init' command."""

    def test_init_auto_select_model(
        self, runner, mock_hardware, mock_model, mock_config, tmp_path
    ):
        """Test init command with automatic model selection."""
        # Mock all the dependencies
        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.list_models.return_value = [mock_model]
                mock_registry_cls.return_value = mock_registry

                with patch("qwenvert.models.ModelSelector") as mock_selector_cls:
                    mock_selector = MagicMock()
                    mock_selector.select_default.return_value = mock_model
                    mock_selector_cls.return_value = mock_selector

                    with patch(
                        "qwenvert.downloader.ModelDownloader"
                    ) as mock_downloader_cls:
                        mock_downloader = MagicMock()
                        mock_downloader.get_model_path.return_value = (
                            tmp_path / "model.gguf"
                        )
                        mock_downloader.models_dir = tmp_path
                        mock_downloader_cls.return_value = mock_downloader

                        with patch("qwenvert.config.ConfigGenerator") as mock_gen_cls:
                            mock_gen = MagicMock()
                            mock_gen.generate_qwenvert_config.return_value = mock_config
                            mock_gen.print_setup_instructions.return_value = (
                                "Instructions"
                            )
                            mock_gen_cls.return_value = mock_gen

                            with patch(
                                "qwenvert.config.ConfigManager"
                            ) as mock_manager_cls:
                                mock_manager = MagicMock()
                                mock_manager.save.return_value = (
                                    tmp_path / "config.yaml"
                                )
                                mock_manager_cls.save = mock_manager.save

                                result = runner.invoke(cli, ["init"])

                                assert result.exit_code == 0
                                assert "Initialization" in result.output
                                assert (
                                    "M1 Pro" in result.output
                                    or "Detected" in result.output
                                )

    def test_init_with_specified_model(
        self, runner, mock_hardware, mock_model, mock_config, tmp_path
    ):
        """Test init command with user-specified model."""
        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.get_model.return_value = mock_model
                mock_registry_cls.return_value = mock_registry

                with patch(
                    "qwenvert.downloader.ModelDownloader"
                ) as mock_downloader_cls:
                    mock_downloader = MagicMock()
                    mock_downloader.get_model_path.return_value = (
                        tmp_path / "model.gguf"
                    )
                    mock_downloader.models_dir = tmp_path
                    mock_downloader_cls.return_value = mock_downloader

                    with patch("qwenvert.config.ConfigGenerator") as mock_gen_cls:
                        mock_gen = MagicMock()
                        mock_gen.generate_qwenvert_config.return_value = mock_config
                        mock_gen.print_setup_instructions.return_value = "Instructions"
                        mock_gen_cls.return_value = mock_gen

                        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
                            mock_manager = MagicMock()
                            mock_manager.save.return_value = tmp_path / "config.yaml"
                            mock_manager_cls.save = mock_manager.save

                            result = runner.invoke(
                                cli, ["init", "--model", "qwen2.5-coder-7b-q4-ollama"]
                            )

                            assert result.exit_code == 0
                            mock_registry.get_model.assert_called_once_with(
                                "qwen2.5-coder-7b-q4-ollama"
                            )

    def test_init_model_not_found(self, runner, mock_hardware):
        """Test init with invalid model ID."""
        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.get_model.return_value = None
                mock_registry.list_models.return_value = []
                mock_registry_cls.return_value = mock_registry

                result = runner.invoke(cli, ["init", "--model", "invalid-model"])

                assert result.exit_code == 1
                assert "not found" in result.output or "Error" in result.output

    def test_init_model_insufficient_ram_user_declines(
        self, runner, mock_hardware, mock_model, tmp_path
    ):
        """Test init when model doesn't fit hardware and user declines."""
        # Make the model require more RAM than available
        large_model = Model(
            id="qwen2.5-coder-32b-q8-ollama",
            display_name="Qwen2.5 Coder 32B Q8",
            family="qwen2.5-coder",
            size_b=32.0,
            quantization="Q8_0",
            backend=Backend.OLLAMA,
            backend_model_id="qwen2.5-coder:32b",
            context_length=32768,
            max_output_tokens=16384,
            min_ram_gb=64,  # More than our mock hardware has
            recommended_ram_gb=128,
            huggingface_repo="Qwen/Qwen2.5-Coder-32B-GGUF",
        )

        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry.get_model.return_value = large_model
                mock_registry_cls.return_value = mock_registry

                # User declines to continue
                result = runner.invoke(
                    cli, ["init", "--model", "qwen2.5-coder-32b-q8-ollama"], input="n\n"
                )

                assert result.exit_code == 1
                assert "Warning" in result.output or "may not fit" in result.output

    def test_init_no_compatible_model(self, runner, mock_hardware):
        """Test init when no compatible model found for hardware."""
        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry_cls.return_value = mock_registry

                with patch("qwenvert.models.ModelSelector") as mock_selector_cls:
                    mock_selector = MagicMock()
                    mock_selector.select_default.return_value = (
                        None  # No compatible model
                    )
                    mock_selector_cls.return_value = mock_selector

                    result = runner.invoke(cli, ["init"])

                    assert result.exit_code == 1
                    assert (
                        "No compatible model" in result.output
                        or "Error" in result.output
                    )

    def test_init_model_download_needed(
        self, runner, mock_hardware, mock_model, mock_config, tmp_path
    ):
        """Test init when model needs to be downloaded."""
        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry_cls.return_value = mock_registry

                with patch("qwenvert.models.ModelSelector") as mock_selector_cls:
                    mock_selector = MagicMock()
                    mock_selector.select_default.return_value = mock_model
                    mock_selector_cls.return_value = mock_selector

                    with patch(
                        "qwenvert.downloader.ModelDownloader"
                    ) as mock_downloader_cls:
                        mock_downloader = MagicMock()
                        # First call: model not present
                        # Second call (after download): return path
                        downloaded_path = tmp_path / "model.gguf"
                        downloaded_path.touch()
                        mock_downloader.get_model_path.return_value = None
                        mock_downloader.download.return_value = downloaded_path
                        mock_downloader.models_dir = tmp_path
                        mock_downloader_cls.return_value = mock_downloader

                        with patch("qwenvert.config.ConfigGenerator") as mock_gen_cls:
                            mock_gen = MagicMock()
                            mock_gen.generate_qwenvert_config.return_value = mock_config
                            mock_gen.print_setup_instructions.return_value = (
                                "Instructions"
                            )
                            mock_gen_cls.return_value = mock_gen

                            with patch(
                                "qwenvert.config.ConfigManager"
                            ) as mock_manager_cls:
                                mock_manager = MagicMock()
                                mock_manager.save.return_value = (
                                    tmp_path / "config.yaml"
                                )
                                mock_manager_cls.save = mock_manager.save

                                result = runner.invoke(cli, ["init"])

                                assert result.exit_code == 0
                                assert (
                                    "Downloaded" in result.output
                                    or "Downloading" in result.output
                                )

    def test_init_model_no_huggingface_repo_user_continues(
        self, runner, mock_hardware, mock_config, tmp_path
    ):
        """Test init when model has no HuggingFace repo but user continues."""
        model_no_hf = Model(
            id="custom-model",
            display_name="Custom Model",
            family="custom",
            size_b=7.0,
            quantization="Q4_K_M",
            backend=Backend.OLLAMA,
            backend_model_id="custom:7b",
            context_length=32768,
            max_output_tokens=12288,
            min_ram_gb=8,
            recommended_ram_gb=16,
            huggingface_repo=None,  # No HuggingFace repo
        )

        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry_cls.return_value = mock_registry

                with patch("qwenvert.models.ModelSelector") as mock_selector_cls:
                    mock_selector = MagicMock()
                    mock_selector.select_default.return_value = model_no_hf
                    mock_selector_cls.return_value = mock_selector

                    with patch(
                        "qwenvert.downloader.ModelDownloader"
                    ) as mock_downloader_cls:
                        mock_downloader = MagicMock()
                        mock_downloader.get_model_path.return_value = None
                        mock_downloader.models_dir = tmp_path
                        mock_downloader_cls.return_value = mock_downloader

                        with patch("qwenvert.config.ConfigGenerator") as mock_gen_cls:
                            mock_gen = MagicMock()
                            mock_gen.generate_qwenvert_config.return_value = mock_config
                            mock_gen.print_setup_instructions.return_value = (
                                "Instructions"
                            )
                            mock_gen_cls.return_value = mock_gen

                            with patch(
                                "qwenvert.config.ConfigManager"
                            ) as mock_manager_cls:
                                mock_manager = MagicMock()
                                mock_manager.save.return_value = (
                                    tmp_path / "config.yaml"
                                )
                                mock_manager_cls.save = mock_manager.save

                                # User continues despite no HuggingFace repo
                                result = runner.invoke(cli, ["init"], input="y\n")

                                assert result.exit_code == 0
                                assert (
                                    "no HuggingFace" in result.output
                                    or "manually download" in result.output
                                )

    def test_init_download_error_user_continues(
        self, runner, mock_hardware, mock_model, mock_config, tmp_path
    ):
        """Test init when download fails but user continues."""
        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry_cls.return_value = mock_registry

                with patch("qwenvert.models.ModelSelector") as mock_selector_cls:
                    mock_selector = MagicMock()
                    mock_selector.select_default.return_value = mock_model
                    mock_selector_cls.return_value = mock_selector

                    with patch(
                        "qwenvert.downloader.ModelDownloader"
                    ) as mock_downloader_cls:
                        mock_downloader = MagicMock()
                        mock_downloader.get_model_path.return_value = None
                        mock_downloader.download.side_effect = Exception(
                            "Download failed"
                        )
                        mock_downloader.models_dir = tmp_path
                        mock_downloader_cls.return_value = mock_downloader

                        with patch("qwenvert.config.ConfigGenerator") as mock_gen_cls:
                            mock_gen = MagicMock()
                            mock_gen.generate_qwenvert_config.return_value = mock_config
                            mock_gen.print_setup_instructions.return_value = (
                                "Instructions"
                            )
                            mock_gen_cls.return_value = mock_gen

                            with patch(
                                "qwenvert.config.ConfigManager"
                            ) as mock_manager_cls:
                                mock_manager = MagicMock()
                                mock_manager.save.return_value = (
                                    tmp_path / "config.yaml"
                                )
                                mock_manager_cls.save = mock_manager.save

                                # User continues after download error
                                result = runner.invoke(cli, ["init"], input="y\n")

                                assert result.exit_code == 0
                                assert (
                                    "Error downloading" in result.output
                                    or "manually download" in result.output
                                )

    def test_init_with_context_length(
        self, runner, mock_hardware, mock_model, mock_config, tmp_path
    ):
        """Test init with custom context length."""
        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry_cls.return_value = mock_registry

                with patch("qwenvert.models.ModelSelector") as mock_selector_cls:
                    mock_selector = MagicMock()
                    mock_selector.select_default.return_value = mock_model
                    mock_selector_cls.return_value = mock_selector

                    with patch(
                        "qwenvert.downloader.ModelDownloader"
                    ) as mock_downloader_cls:
                        mock_downloader = MagicMock()
                        mock_downloader.get_model_path.return_value = (
                            tmp_path / "model.gguf"
                        )
                        mock_downloader.models_dir = tmp_path
                        mock_downloader_cls.return_value = mock_downloader

                        with patch("qwenvert.config.ConfigGenerator") as mock_gen_cls:
                            mock_gen = MagicMock()
                            mock_gen.generate_qwenvert_config.return_value = mock_config
                            mock_gen.print_setup_instructions.return_value = (
                                "Instructions"
                            )
                            mock_gen_cls.return_value = mock_gen

                            with patch(
                                "qwenvert.config.ConfigManager"
                            ) as mock_manager_cls:
                                mock_manager = MagicMock()
                                mock_manager.save.return_value = (
                                    tmp_path / "config.yaml"
                                )
                                mock_manager_cls.save = mock_manager.save

                                result = runner.invoke(
                                    cli, ["init", "--context-length", "65536"]
                                )

                                assert result.exit_code == 0
                                # Verify context length was set
                                assert mock_config.context_length == 65536

    def test_init_ollama_backend_generates_modelfile(
        self, runner, mock_hardware, mock_model, mock_config, tmp_path
    ):
        """Test init with Ollama backend generates Modelfile."""
        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
                mock_registry = MagicMock()
                mock_registry_cls.return_value = mock_registry

                with patch("qwenvert.models.ModelSelector") as mock_selector_cls:
                    mock_selector = MagicMock()
                    mock_selector.select_default.return_value = (
                        mock_model  # Ollama backend
                    )
                    mock_selector_cls.return_value = mock_selector

                    with patch(
                        "qwenvert.downloader.ModelDownloader"
                    ) as mock_downloader_cls:
                        mock_downloader = MagicMock()
                        mock_downloader.get_model_path.return_value = (
                            tmp_path / "model.gguf"
                        )
                        mock_downloader.models_dir = tmp_path
                        mock_downloader_cls.return_value = mock_downloader

                        with patch("qwenvert.config.ConfigGenerator") as mock_gen_cls:
                            mock_gen = MagicMock()
                            mock_gen.generate_qwenvert_config.return_value = mock_config
                            mock_gen.generate_ollama_modelfile.return_value = (
                                "FROM ./model.gguf"
                            )
                            mock_gen.print_setup_instructions.return_value = (
                                "Instructions"
                            )
                            mock_gen_cls.return_value = mock_gen

                            with patch(
                                "qwenvert.config.ConfigManager"
                            ) as mock_manager_cls:
                                mock_manager = MagicMock()
                                mock_manager.save.return_value = (
                                    tmp_path / "config.yaml"
                                )
                                mock_manager.save_ollama_modelfile.return_value = (
                                    tmp_path / "Modelfile"
                                )
                                mock_manager_cls.save = mock_manager.save
                                mock_manager_cls.save_ollama_modelfile = (
                                    mock_manager.save_ollama_modelfile
                                )

                                result = runner.invoke(cli, ["init"])

                                assert result.exit_code == 0
                                mock_gen.generate_ollama_modelfile.assert_called_once()
                                mock_manager.save_ollama_modelfile.assert_called_once()


class TestStartCommand:
    """Test 'qwenvert start' command."""

    def test_start_success(self, runner):
        """Test start command success path."""
        with patch("qwenvert.launcher.start_qwenvert_sync") as mock_start:
            result = runner.invoke(cli, ["start"])

            assert result.exit_code == 0
            mock_start.assert_called_once()
            assert "Starting" in result.output

    def test_start_keyboard_interrupt(self, runner):
        """Test start command handles Ctrl+C gracefully."""
        with patch("qwenvert.launcher.start_qwenvert_sync") as mock_start:
            mock_start.side_effect = KeyboardInterrupt()

            result = runner.invoke(cli, ["start"])

            assert result.exit_code == 0
            assert "Interrupted" in result.output or "user" in result.output

    def test_start_exception(self, runner):
        """Test start command handles exceptions."""
        with patch("qwenvert.launcher.start_qwenvert_sync") as mock_start:
            mock_start.side_effect = Exception("Test error")

            result = runner.invoke(cli, ["start"])

            assert result.exit_code == 1
            assert "Error" in result.output


class TestStatusCommand:
    """Test 'qwenvert status' command."""

    def test_status_not_configured(self, runner):
        """Test status when config doesn't exist."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = False

            result = runner.invoke(cli, ["status"])

            assert result.exit_code == 0
            assert "Not configured" in result.output or "init" in result.output

    def test_status_healthy_servers(self, runner, mock_config):
        """Test status when both servers are healthy."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = True
            mock_manager_cls.load.return_value = mock_config

            # Mock httpx.get to return healthy responses
            mock_response = MagicMock()
            mock_response.status_code = 200

            with patch("httpx.get", return_value=mock_response):
                result = runner.invoke(cli, ["status"])

                assert result.exit_code == 0
                assert "Configuration" in result.output or "Status" in result.output
                assert "Running" in result.output or "✓" in result.output

    def test_status_backend_unhealthy(self, runner, mock_config):
        """Test status when backend returns non-200 status."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = True
            mock_manager_cls.load.return_value = mock_config

            # Mock backend as unhealthy, adapter as healthy
            def mock_get(url, timeout=None):
                response = MagicMock()
                if "11434" in url:  # Backend
                    response.status_code = 500
                else:  # Adapter
                    response.status_code = 200
                return response

            with patch("httpx.get", side_effect=mock_get):
                result = runner.invoke(cli, ["status"])

                assert result.exit_code == 0
                assert "Unhealthy" in result.output or "✗" in result.output

    def test_status_servers_not_running(self, runner, mock_config):
        """Test status when servers are not running (connection errors)."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = True
            mock_manager_cls.load.return_value = mock_config

            # Mock httpx.get to raise connection errors
            with patch(
                "httpx.get", side_effect=httpx.ConnectError("Connection refused")
            ):
                result = runner.invoke(cli, ["status"])

                assert result.exit_code == 0
                assert "Not running" in result.output or "✗" in result.output


class TestStopCommand:
    """Test 'qwenvert stop' command."""

    def test_stop_not_configured(self, runner):
        """Test stop when config doesn't exist."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = False

            result = runner.invoke(cli, ["stop"])

            assert result.exit_code == 0
            assert "Not configured" in result.output

    def test_stop_kills_processes(self, runner):
        """Test stop command kills processes."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = True

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                result = runner.invoke(cli, ["stop"])

                assert result.exit_code == 0
                # Should call pkill for ollama, llama-server, and uvicorn
                assert mock_run.call_count >= 3
                assert "stopped" in result.output or "Stopping" in result.output

    def test_stop_no_processes_found(self, runner):
        """Test stop when no processes are running."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = True

            with patch("subprocess.run") as mock_run:
                # pkill returns non-zero when no processes found
                mock_run.return_value = MagicMock(returncode=1)

                result = runner.invoke(cli, ["stop"])

                assert result.exit_code == 0
                assert (
                    "No running servers" in result.output or "stopped" in result.output
                )

    def test_stop_subprocess_exception(self, runner):
        """Test stop when subprocess raises exception."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = True

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Subprocess error")

                result = runner.invoke(cli, ["stop"])

                # Should handle exception gracefully
                assert result.exit_code == 0


class TestModelsCommand:
    """Test 'qwenvert models' command."""

    def test_models_list_all(self, runner, mock_model):
        """Test listing all models."""
        model2 = Model(
            id="qwen2.5-coder-14b-q5-ollama",
            display_name="Qwen2.5 Coder 14B Q5",
            family="qwen2.5-coder",
            size_b=14.0,
            quantization="Q5_K_M",
            backend=Backend.OLLAMA,
            backend_model_id="qwen2.5-coder:14b",
            context_length=32768,
            max_output_tokens=16384,
            min_ram_gb=20,
            recommended_ram_gb=32,
        )

        with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.list_models.return_value = [mock_model, model2]
            mock_registry_cls.return_value = mock_registry

            result = runner.invoke(cli, ["models", "list"])

            assert result.exit_code == 0
            assert "Available Models" in result.output or "Models" in result.output
            assert "7B" in result.output
            assert "14B" in result.output

    def test_models_list_filter_backend(self, runner, mock_model):
        """Test listing models filtered by backend."""
        with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.list_models.return_value = [mock_model]
            mock_registry_cls.return_value = mock_registry

            result = runner.invoke(cli, ["models", "list", "--backend", "ollama"])

            assert result.exit_code == 0
            mock_registry.list_models.assert_called()

    def test_models_list_empty(self, runner):
        """Test listing models when no models available."""
        with patch("qwenvert.models.ModelRegistry") as mock_registry_cls:
            mock_registry = MagicMock()
            mock_registry.list_models.return_value = []
            mock_registry_cls.return_value = mock_registry

            result = runner.invoke(cli, ["models", "list"])

            assert result.exit_code == 0
            # Should still display table header even if empty
            assert "Available Models" in result.output or "Models" in result.output


class TestHardwareCommand:
    """Test 'qwenvert hardware' command."""

    def test_hardware_display(self, runner, mock_hardware):
        """Test hardware command displays hardware info."""
        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(cli, ["hardware"])

            assert result.exit_code == 0
            assert (
                "Hardware Information" in result.output or "Hardware" in result.output
            )
            assert "M1 Pro" in result.output
            assert "16GB" in result.output or "16" in result.output

    def test_hardware_memory_constrained(self, runner):
        """Test hardware command with memory-constrained system."""
        constrained_hw = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=8,  # Low memory
            gpu_cores=8,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=False,
            neural_engine_cores=16,
            model_identifier="MacBookAir10,1",
        )

        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = constrained_hw
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(cli, ["hardware"])

            assert result.exit_code == 0
            assert "Memory constrained" in result.output or "Q4" in result.output

    def test_hardware_thermally_constrained(self, runner):
        """Test hardware command with thermally-constrained system."""
        thermal_hw = HardwareProfile(
            chip="M2",
            chip_family="M2",
            total_memory_gb=24,
            gpu_cores=10,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=False,  # Fanless - thermally constrained
            neural_engine_cores=16,
            model_identifier="Mac14,7",
        )

        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = thermal_hw
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(cli, ["hardware"])

            assert result.exit_code == 0
            assert (
                "Thermally constrained" in result.output
                or "thermal pacing" in result.output
            )

    def test_hardware_good_configuration(self, runner, mock_hardware):
        """Test hardware command with good hardware configuration."""
        # Use our standard mock_hardware which is well-configured
        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(cli, ["hardware"])

            assert result.exit_code == 0
            assert (
                "Good configuration" in result.output
                or "larger models" in result.output
            )


class TestMonitorCommand:
    """Test 'qwenvert monitor' command."""

    def test_monitor_with_config(self, runner, mock_config):
        """Test monitor command with existing config."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = True
            mock_manager_cls.load.return_value = mock_config

            with patch("qwenvert.dashboard.run_dashboard") as mock_dashboard:
                # Simulate user pressing Ctrl+C
                mock_dashboard.side_effect = KeyboardInterrupt()

                with patch("asyncio.run") as mock_asyncio_run:
                    mock_asyncio_run.side_effect = KeyboardInterrupt()

                    result = runner.invoke(cli, ["monitor"])

                    assert result.exit_code == 0
                    assert "Monitor" in result.output
                    assert "stopped" in result.output or "Interrupted" in result.output

    def test_monitor_without_config(self, runner):
        """Test monitor command without existing config."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = False

            with patch("qwenvert.dashboard.run_dashboard") as mock_dashboard:
                mock_dashboard.side_effect = KeyboardInterrupt()

                with patch("asyncio.run") as mock_asyncio_run:
                    mock_asyncio_run.side_effect = KeyboardInterrupt()

                    result = runner.invoke(cli, ["monitor"])

                    assert result.exit_code == 0
                    assert "Monitoring" in result.output or "Monitor" in result.output
                    # Should use default URL and show tip
                    assert "localhost:8088" in result.output or "Tip" in result.output

    def test_monitor_custom_url(self, runner):
        """Test monitor command with custom adapter URL."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = False

            with patch("qwenvert.dashboard.run_dashboard") as mock_dashboard:
                mock_dashboard.side_effect = KeyboardInterrupt()

                with patch("asyncio.run") as mock_asyncio_run:
                    mock_asyncio_run.side_effect = KeyboardInterrupt()

                    result = runner.invoke(
                        cli, ["monitor", "--adapter-url", "http://localhost:9000"]
                    )

                    assert result.exit_code == 0
                    assert "Monitor" in result.output

    def test_monitor_custom_refresh_rate(self, runner):
        """Test monitor command with custom refresh rate."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = False

            with patch("qwenvert.dashboard.run_dashboard") as mock_dashboard:
                mock_dashboard.side_effect = KeyboardInterrupt()

                with patch("asyncio.run") as mock_asyncio_run:
                    mock_asyncio_run.side_effect = KeyboardInterrupt()

                    result = runner.invoke(cli, ["monitor", "--refresh-rate", "0.5"])

                    assert result.exit_code == 0

    def test_monitor_exception(self, runner):
        """Test monitor command handles exceptions."""
        with patch("qwenvert.config.ConfigManager") as mock_manager_cls:
            mock_manager_cls.exists.return_value = False

            with patch("asyncio.run") as mock_asyncio_run:
                mock_asyncio_run.side_effect = Exception("Test error")

                result = runner.invoke(cli, ["monitor"])

                assert result.exit_code == 1
                assert "Error" in result.output


class TestModelsCleanCommand:
    """Test models clean command."""

    def test_clean_help(self, runner):
        """Test clean command help output."""
        result = runner.invoke(cli, ["models", "clean", "--help"])
        assert result.exit_code == 0
        assert "Remove downloaded model files" in result.output
        assert "--model-id" in result.output
        assert "--all" in result.output
        assert "--dry-run" in result.output

    def test_clean_no_models(self, runner):
        """Test clean when no models are downloaded."""
        with patch("qwenvert.downloader.ModelDownloader") as mock_downloader_cls:
            mock_downloader = MagicMock()
            mock_downloader.list_downloaded_models.return_value = []
            mock_downloader_cls.return_value = mock_downloader

            result = runner.invoke(cli, ["models", "clean"])

            assert result.exit_code == 0
            assert "No models downloaded" in result.output

    def test_clean_dry_run(self, runner, tmp_path):
        """Test dry run doesn't delete files."""
        # Create fake model files
        fake_model = tmp_path / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
        fake_model.write_bytes(b"fake model data" * 1000)

        with patch("qwenvert.downloader.ModelDownloader") as mock_downloader_cls:
            mock_downloader = MagicMock()
            mock_downloader.list_downloaded_models.return_value = [fake_model]
            mock_downloader.get_disk_usage.return_value = {
                "total_gb": 0.01,
                "available_gb": 100.0,
            }
            mock_downloader_cls.return_value = mock_downloader

            result = runner.invoke(cli, ["models", "clean", "--all", "--dry-run"])

            assert result.exit_code == 0
            assert "Dry run" in result.output
            assert fake_model.exists()  # File should still exist

    def test_clean_specific_model(self, runner, tmp_path):
        """Test cleaning a specific model by filename."""
        # Create fake model files
        model1 = tmp_path / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
        model2 = tmp_path / "qwen2.5-coder-14b-instruct-q5_k_m.gguf"
        model1.write_bytes(b"fake model 1" * 1000)
        model2.write_bytes(b"fake model 2" * 1000)

        with patch("qwenvert.downloader.ModelDownloader") as mock_downloader_cls:
            mock_downloader = MagicMock()
            mock_downloader.list_downloaded_models.return_value = [model1, model2]
            mock_downloader.get_disk_usage.return_value = {
                "total_gb": 0.02,
                "available_gb": 100.0,
            }
            mock_downloader_cls.return_value = mock_downloader

            result = runner.invoke(
                cli,
                [
                    "models",
                    "clean",
                    "--model-id",
                    "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
                ],
                input="y\n",
            )

            assert result.exit_code == 0
            assert "Cleanup complete" in result.output

    def test_clean_model_not_found(self, runner, tmp_path):
        """Test cleaning non-existent model shows error."""
        model1 = tmp_path / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
        model1.write_bytes(b"fake model" * 1000)

        with patch("qwenvert.downloader.ModelDownloader") as mock_downloader_cls:
            mock_downloader = MagicMock()
            mock_downloader.list_downloaded_models.return_value = [model1]
            mock_downloader.get_disk_usage.return_value = {
                "total_gb": 0.01,
                "available_gb": 100.0,
            }
            mock_downloader_cls.return_value = mock_downloader

            result = runner.invoke(
                cli,
                ["models", "clean", "--model-id", "nonexistent.gguf"],
            )

            assert result.exit_code == 0
            assert "not found" in result.output
            assert "Available models" in result.output

    def test_clean_all_with_confirmation(self, runner, tmp_path):
        """Test --all flag with user confirmation."""
        # Create fake model files
        model1 = tmp_path / "model1.gguf"
        model2 = tmp_path / "model2.gguf"
        model1.write_bytes(b"fake model 1" * 1000)
        model2.write_bytes(b"fake model 2" * 1000)

        with patch("qwenvert.downloader.ModelDownloader") as mock_downloader_cls:
            mock_downloader = MagicMock()
            mock_downloader.list_downloaded_models.return_value = [model1, model2]
            mock_downloader.get_disk_usage.return_value = {
                "total_gb": 0.02,
                "available_gb": 100.0,
            }
            mock_downloader_cls.return_value = mock_downloader

            # Test with confirmation
            result = runner.invoke(cli, ["models", "clean", "--all"], input="y\n")

            assert result.exit_code == 0
            assert "Cleanup complete" in result.output

    def test_clean_all_with_denial(self, runner, tmp_path):
        """Test --all flag with user denying confirmation."""
        model1 = tmp_path / "model1.gguf"
        model1.write_bytes(b"fake model" * 1000)

        with patch("qwenvert.downloader.ModelDownloader") as mock_downloader_cls:
            mock_downloader = MagicMock()
            mock_downloader.list_downloaded_models.return_value = [model1]
            mock_downloader.get_disk_usage.return_value = {
                "total_gb": 0.01,
                "available_gb": 100.0,
            }
            mock_downloader_cls.return_value = mock_downloader

            # Test with denial
            result = runner.invoke(cli, ["models", "clean", "--all"], input="n\n")

            assert result.exit_code == 0
            assert model1.exists()  # File should still exist

    def test_clean_keyboard_interrupt(self, runner, tmp_path):
        """Test clean handles keyboard interrupt gracefully."""
        model1 = tmp_path / "model1.gguf"
        model1.write_bytes(b"fake model" * 1000)

        with patch("qwenvert.downloader.ModelDownloader") as mock_downloader_cls:
            mock_downloader = MagicMock()
            mock_downloader.list_downloaded_models.return_value = [model1]
            mock_downloader.get_disk_usage.return_value = {
                "total_gb": 0.01,
                "available_gb": 100.0,
            }
            mock_downloader_cls.return_value = mock_downloader

            # Simulate KeyboardInterrupt during deletion
            mock_downloader.delete_model_by_path.side_effect = KeyboardInterrupt()

            result = runner.invoke(cli, ["models", "clean", "--all"], input="y\n")

            assert result.exit_code == 1
            assert "interrupted" in result.output.lower()

    def test_clean_deletion_error(self, runner, tmp_path):
        """Test clean handles deletion errors gracefully."""
        model1 = tmp_path / "model1.gguf"
        model1.write_bytes(b"fake model" * 1000)

        with patch("qwenvert.downloader.ModelDownloader") as mock_downloader_cls:
            mock_downloader = MagicMock()
            mock_downloader.list_downloaded_models.return_value = [model1]
            mock_downloader.get_disk_usage.return_value = {
                "total_gb": 0.01,
                "available_gb": 100.0,
            }
            mock_downloader_cls.return_value = mock_downloader

            # Simulate permission error during deletion
            mock_downloader.delete_model_by_path.side_effect = PermissionError(
                "Permission denied"
            )

            result = runner.invoke(cli, ["models", "clean", "--all"], input="y\n")

            assert result.exit_code == 0  # Should continue despite error
            assert "Error deleting" in result.output
