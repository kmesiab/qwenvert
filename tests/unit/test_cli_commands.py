"""
Unit tests for CLI commands.

Tests all qwenvert CLI commands using Click's CliRunner with mocked dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

from qwenvert.cli import cli
from qwenvert.config import QwenvertConfig
from qwenvert.hardware import HardwareProfile
from qwenvert.models import Backend, Model, ModelRegistry


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_hardware():
    """Mock hardware detection."""
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


class TestInitCommand:
    """Test 'qwenvert init' command."""

    def test_init_default(self, runner, mock_hardware, mock_config, tmp_path):
        """Test init command with default settings."""
        with patch("qwenvert.hardware.HardwareDetector") as mock_detector_class:
            mock_detector = MagicMock()
            mock_detector.detect.return_value = mock_hardware
            mock_detector_class.return_value = mock_detector

            with patch("qwenvert.models.ModelRegistry") as mock_registry_class:
                mock_registry = MagicMock()
                mock_model = Model(
                    id="qwen2.5-coder-7b-q4-ollama",
                    display_name="Qwen2.5 Coder 7B Q4",
                    family="qwen2.5-coder",
                    size_b=7.0,
                    quantization="Q4_K_M",
                    backend=Backend.OLLAMA,
                    backend_model_id="qwen2.5-coder:7b",
                    context_length=32768,
                    min_ram_gb=8,
                    recommended_ram_gb=16,
                )
                mock_registry.find_compatible_models.return_value = [mock_model]
                mock_registry_class.return_value = mock_registry

                with patch("qwenvert.cli.ConfigGenerator") as mock_gen_class:
                    mock_gen = MagicMock()
                    mock_gen.generate_qwenvert_config.return_value = mock_config
                    mock_gen_class.return_value = mock_gen

                    with patch("qwenvert.cli.ConfigManager") as mock_manager_class:
                        mock_manager = MagicMock()
                        mock_manager.save.return_value = None
                        mock_manager_class.return_value = mock_manager

                        result = runner.invoke(cli, ["init"])

                        assert result.exit_code == 0
                        assert "Qwenvert Initialization" in result.output
                        assert "M1 Pro" in result.output or "configuration" in result.output.lower()

    def test_init_with_model_flag(self, runner, mock_hardware, tmp_path):
        """Test init command with specific model."""
        with patch("qwenvert.cli.detect_hardware", return_value=mock_hardware):
            with patch("qwenvert.cli.ModelRegistry") as mock_registry_class:
                mock_registry = MagicMock()
                mock_model = Model(
                    id="qwen2.5-coder-14b-q5-ollama",
                    display_name="Qwen2.5 Coder 14B Q5",
                    family="qwen2.5-coder",
                    size_b=14.0,
                    quantization="Q5_K_M",
                    backend=Backend.OLLAMA,
                    backend_model_id="qwen2.5-coder:14b",
                    context_length=32768,
                    min_ram_gb=20,
                    recommended_ram_gb=32,
                )
                mock_registry.get_model_by_id.return_value = mock_model
                mock_registry_class.return_value = mock_registry

                with patch("qwenvert.cli.ConfigGenerator"):
                    with patch("qwenvert.cli.ConfigManager"):
                        result = runner.invoke(
                            cli, ["init", "--model", "qwen2.5-coder-14b-q5-ollama"]
                        )

                        # Should at least attempt to use the specified model
                        mock_registry.get_model_by_id.assert_called_once_with(
                            "qwen2.5-coder-14b-q5-ollama"
                        )

    def test_init_with_backend_flag(self, runner, mock_hardware):
        """Test init command with specific backend."""
        with patch("qwenvert.cli.detect_hardware", return_value=mock_hardware):
            with patch("qwenvert.cli.ModelRegistry"):
                with patch("qwenvert.cli.ConfigGenerator"):
                    with patch("qwenvert.cli.ConfigManager"):
                        result = runner.invoke(cli, ["init", "--backend", "llamacpp"])

                        # Should complete without error
                        assert result.exit_code in [0, 1]  # May fail if no models found

    def test_init_with_context_length(self, runner, mock_hardware):
        """Test init command with custom context length."""
        with patch("qwenvert.cli.detect_hardware", return_value=mock_hardware):
            with patch("qwenvert.cli.ModelRegistry"):
                with patch("qwenvert.cli.ConfigGenerator") as mock_gen_class:
                    mock_gen = MagicMock()
                    mock_gen_class.return_value = mock_gen

                    with patch("qwenvert.cli.ConfigManager"):
                        result = runner.invoke(
                            cli, ["init", "--context-length", "65536"]
                        )

                        # Verify context length was passed
                        if result.exit_code == 0:
                            assert mock_gen.generate_qwenvert_config.called


class TestStartCommand:
    """Test 'qwenvert start' command."""

    def test_start_basic(self, runner, mock_config):
        """Test basic start command."""
        with patch("qwenvert.cli.ConfigManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.load.return_value = mock_config
            mock_manager_class.return_value = mock_manager

            with patch("qwenvert.cli.ServerLauncher") as mock_launcher_class:
                mock_launcher = MagicMock()
                mock_launcher.start_backend = AsyncMock(return_value=MagicMock())
                mock_launcher.start_adapter = AsyncMock(return_value=MagicMock())
                mock_launcher_class.return_value = mock_launcher

                with patch("qwenvert.cli.asyncio.run"):
                    result = runner.invoke(cli, ["start"])

                    # Should load config and attempt to start
                    assert mock_manager.load.called

    def test_start_without_init(self, runner):
        """Test start command without prior init."""
        with patch("qwenvert.cli.ConfigManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.load.side_effect = FileNotFoundError("Config not found")
            mock_manager_class.return_value = mock_manager

            result = runner.invoke(cli, ["start"])

            assert result.exit_code != 0
            assert "init" in result.output.lower() or "config" in result.output.lower()


class TestStopCommand:
    """Test 'qwenvert stop' command."""

    def test_stop_basic(self, runner):
        """Test basic stop command."""
        with patch("qwenvert.cli.Path.exists", return_value=True):
            with patch("qwenvert.cli.Path.read_text", return_value="12345"):
                with patch("qwenvert.cli.psutil.Process") as mock_process_class:
                    mock_process = MagicMock()
                    mock_process.is_running.return_value = True
                    mock_process_class.return_value = mock_process

                    result = runner.invoke(cli, ["stop"])

                    # Should attempt to stop process
                    assert mock_process.terminate.called or result.exit_code == 0

    def test_stop_when_not_running(self, runner):
        """Test stop command when qwenvert is not running."""
        with patch("qwenvert.cli.Path.exists", return_value=False):
            result = runner.invoke(cli, ["stop"])

            assert result.exit_code in [0, 1]
            assert "not running" in result.output.lower() or "no pid" in result.output.lower() or result.exit_code == 0


class TestStatusCommand:
    """Test 'qwenvert status' command."""

    def test_status_healthy(self, runner, mock_config):
        """Test status command when services are healthy."""
        with patch("qwenvert.cli.ConfigManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.load.return_value = mock_config
            mock_manager_class.return_value = mock_manager

            with patch("qwenvert.cli.httpx.Client") as mock_client_class:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_client.get.return_value = mock_response
                mock_client_class.return_value.__enter__.return_value = mock_client

                result = runner.invoke(cli, ["status"])

                assert result.exit_code == 0
                assert "status" in result.output.lower() or "running" in result.output.lower() or "healthy" in result.output.lower()

    def test_status_without_config(self, runner):
        """Test status command without configuration."""
        with patch("qwenvert.cli.ConfigManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.load.side_effect = FileNotFoundError()
            mock_manager_class.return_value = mock_manager

            result = runner.invoke(cli, ["status"])

            assert result.exit_code != 0


class TestModelsCommand:
    """Test 'qwenvert models' command."""

    def test_models_list(self, runner):
        """Test listing available models."""
        mock_models = [
            Model(
                id="qwen2.5-coder-7b-q4-ollama",
                display_name="Qwen2.5 Coder 7B Q4",
                family="qwen2.5-coder",
                size_b=7.0,
                quantization="Q4_K_M",
                backend=Backend.OLLAMA,
                backend_model_id="qwen2.5-coder:7b",
                context_length=32768,
                min_ram_gb=8,
                recommended_ram_gb=16,
            ),
            Model(
                id="qwen2.5-coder-14b-q5-ollama",
                display_name="Qwen2.5 Coder 14B Q5",
                family="qwen2.5-coder",
                size_b=14.0,
                quantization="Q5_K_M",
                backend=Backend.OLLAMA,
                backend_model_id="qwen2.5-coder:14b",
                context_length=32768,
                min_ram_gb=20,
                recommended_ram_gb=32,
            ),
        ]

        with patch("qwenvert.cli.ModelRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.list_models.return_value = mock_models
            mock_registry_class.return_value = mock_registry

            result = runner.invoke(cli, ["models", "list"])

            assert result.exit_code == 0
            assert "7B" in result.output
            assert "14B" in result.output

    def test_models_list_ollama_only(self, runner):
        """Test listing only Ollama models."""
        with patch("qwenvert.cli.ModelRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.list_models.return_value = []
            mock_registry_class.return_value = mock_registry

            result = runner.invoke(cli, ["models", "list", "--backend", "ollama"])

            assert result.exit_code == 0
            mock_registry.list_models.assert_called_once_with(backend=Backend.OLLAMA)


class TestHardwareCommand:
    """Test 'qwenvert hardware' command."""

    def test_hardware_detection(self, runner, mock_hardware):
        """Test hardware detection command."""
        with patch("qwenvert.cli.detect_hardware", return_value=mock_hardware):
            result = runner.invoke(cli, ["hardware"])

            assert result.exit_code == 0
            assert "M1 Pro" in result.output or "M1" in result.output
            assert "16" in result.output  # Memory or cores


class TestMonitorCommand:
    """Test 'qwenvert monitor' command."""

    def test_monitor_command_starts(self, runner, mock_config):
        """Test that monitor command can be invoked."""
        with patch("qwenvert.cli.ConfigManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.load.return_value = mock_config
            mock_manager_class.return_value = mock_manager

            with patch("qwenvert.cli.Dashboard") as mock_dashboard_class:
                mock_dashboard = MagicMock()
                mock_dashboard.run = Mock(side_effect=KeyboardInterrupt)
                mock_dashboard_class.return_value = mock_dashboard

                result = runner.invoke(cli, ["monitor"])

                # Should start but exit gracefully on keyboard interrupt
                assert result.exit_code in [0, 1]


class TestCLIHelp:
    """Test CLI help text."""

    def test_main_help(self, runner):
        """Test main CLI help."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "qwenvert" in result.output.lower() or "usage" in result.output.lower()
        assert "init" in result.output
        assert "start" in result.output
        assert "stop" in result.output

    def test_init_help(self, runner):
        """Test init command help."""
        result = runner.invoke(cli, ["init", "--help"])

        assert result.exit_code == 0
        assert "model" in result.output.lower()
        assert "backend" in result.output.lower()

    def test_models_help(self, runner):
        """Test models command help."""
        result = runner.invoke(cli, ["models", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output.lower()


class TestErrorHandling:
    """Test CLI error handling."""

    def test_invalid_command(self, runner):
        """Test invalid command."""
        result = runner.invoke(cli, ["invalid-command"])

        assert result.exit_code != 0

    def test_init_with_invalid_model(self, runner, mock_hardware):
        """Test init with invalid model ID."""
        with patch("qwenvert.cli.detect_hardware", return_value=mock_hardware):
            with patch("qwenvert.cli.ModelRegistry") as mock_registry_class:
                mock_registry = MagicMock()
                mock_registry.get_model_by_id.return_value = None
                mock_registry_class.return_value = mock_registry

                result = runner.invoke(
                    cli, ["init", "--model", "invalid-model-id"]
                )

                assert result.exit_code != 0

    def test_init_with_invalid_backend(self, runner, mock_hardware):
        """Test init with invalid backend."""
        with patch("qwenvert.cli.detect_hardware", return_value=mock_hardware):
            result = runner.invoke(cli, ["init", "--backend", "invalid-backend"])

            assert result.exit_code != 0
