"""Integration tests for zero-friction initialization (Phase 1)."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from qwenvert.binary_manager import BinaryInfo, BinarySource
from qwenvert.cli import cli


@pytest.fixture
def cli_runner():
    """Create Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_binary_info():
    """Create mock BinaryInfo."""
    return BinaryInfo(
        path=Path("/cache/llama-server"),
        version="b3600",
        source=BinarySource.DOWNLOADED,
        architecture="arm64",
        is_valid=True,
    )


@pytest.mark.integration
class TestZeroFrictionInit:
    """Test zero-friction initialization flow."""

    def test_init_with_existing_binary(self, cli_runner, mock_binary_info):
        """Test init when binary already exists (no download needed)."""
        with patch("qwenvert.cli.HardwareDetector") as mock_detector_cls:
            with patch("qwenvert.cli.BinaryManager") as mock_mgr_cls:
                with patch("qwenvert.cli.ModelRegistry"):
                    with patch("qwenvert.cli.ModelSelector"):
                        with patch("qwenvert.cli.ConfigManager"):
                            # Setup mocks
                            mock_detector = Mock()
                            mock_detector.detect.return_value = Mock(
                                chip="M1 Pro",
                                chip_family="M1",
                                total_memory_gb=16,
                            )
                            mock_detector_cls.return_value = mock_detector

                            mock_mgr = Mock()
                            mock_mgr.get_or_install_binary.return_value = mock_binary_info
                            mock_mgr_cls.return_value = mock_mgr

                            # Run init
                            result = cli_runner.invoke(
                                cli, ["init", "--backend", "llamacpp"]
                            )

                            # Should succeed without prompts
                            assert result.exit_code == 0
                            assert "llama-server ready" in result.output
                            assert mock_mgr.get_or_install_binary.called

    def test_init_with_auto_download(self, cli_runner, mock_binary_info):
        """Test init triggers auto-download when binary missing."""
        with patch("qwenvert.cli.HardwareDetector") as mock_detector_cls:
            with patch("qwenvert.cli.BinaryManager") as mock_mgr_cls:
                with patch("qwenvert.cli.ModelRegistry"):
                    with patch("qwenvert.cli.ModelSelector"):
                        with patch("qwenvert.cli.ConfigManager"):
                            # Setup mocks
                            mock_detector = Mock()
                            mock_detector.detect.return_value = Mock(
                                chip="M1 Pro",
                                total_memory_gb=16,
                            )
                            mock_detector_cls.return_value = mock_detector

                            mock_mgr = Mock()
                            # Simulate auto-download success
                            mock_mgr.get_or_install_binary.return_value = mock_binary_info
                            mock_mgr_cls.return_value = mock_mgr

                            result = cli_runner.invoke(
                                cli, ["init", "--backend", "llamacpp"]
                            )

                            # Should succeed with auto-download
                            assert result.exit_code == 0
                            mock_mgr.get_or_install_binary.assert_called_once()

    def test_init_with_no_auto_install_flag(self, cli_runner):
        """Test init with --no-auto-install flag."""
        with patch("qwenvert.cli.HardwareDetector") as mock_detector_cls:
            with patch("qwenvert.cli.BinaryManager") as mock_mgr_cls:
                # Setup mocks
                mock_detector = Mock()
                mock_detector.detect.return_value = Mock(
                    chip="M1 Pro",
                    total_memory_gb=16,
                )
                mock_detector_cls.return_value = mock_detector

                mock_mgr = Mock()
                mock_mgr.get_or_install_binary.side_effect = RuntimeError(
                    "auto-install disabled"
                )
                mock_mgr_cls.return_value = mock_mgr

                result = cli_runner.invoke(
                    cli, ["init", "--backend", "llamacpp", "--no-auto-install"]
                )

                # Should fail gracefully and switch to Ollama
                mock_mgr.get_or_install_binary.assert_called_with(
                    hardware=mock_detector.detect.return_value,
                    auto_install=False,  # Flag should be passed through
                )

    def test_init_fallback_to_ollama(self, cli_runner):
        """Test fallback to Ollama when llama.cpp installation fails."""
        with patch("qwenvert.cli.HardwareDetector") as mock_detector_cls:
            with patch("qwenvert.cli.BinaryManager") as mock_mgr_cls:
                with patch("qwenvert.cli.ModelRegistry"):
                    with patch("qwenvert.cli.ModelSelector"):
                        with patch("qwenvert.cli.ConfigManager"):
                            # Setup mocks
                            mock_detector = Mock()
                            mock_detector.detect.return_value = Mock(
                                chip="M1 Pro",
                                total_memory_gb=16,
                            )
                            mock_detector_cls.return_value = mock_detector

                            mock_mgr = Mock()
                            mock_mgr.get_or_install_binary.side_effect = RuntimeError(
                                "All installation strategies failed"
                            )
                            mock_mgr_cls.return_value = mock_mgr

                            result = cli_runner.invoke(
                                cli, ["init", "--backend", "llamacpp"]
                            )

                            # Should switch to Ollama
                            assert "Switching to Ollama" in result.output


@pytest.mark.integration
class TestBinaryCommands:
    """Test binary management CLI commands."""

    def test_binary_info_command(self, cli_runner, mock_binary_info):
        """Test qwenvert binary info command."""
        with patch("qwenvert.cli.BinaryManager") as mock_mgr_cls:
            mock_mgr = Mock()
            mock_mgr.detect_binary.return_value = mock_binary_info
            mock_mgr_cls.return_value = mock_mgr

            result = cli_runner.invoke(cli, ["binary", "info"])

            assert result.exit_code == 0
            assert "b3600" in result.output
            assert "arm64" in result.output

    def test_binary_info_not_found(self, cli_runner):
        """Test binary info when binary not found."""
        with patch("qwenvert.cli.BinaryManager") as mock_mgr_cls:
            mock_mgr = Mock()
            mock_mgr.detect_binary.return_value = None
            mock_mgr_cls.return_value = mock_mgr

            result = cli_runner.invoke(cli, ["binary", "info"])

            assert result.exit_code == 1
            assert "not found" in result.output.lower()

    def test_binary_list_command(self, cli_runner):
        """Test qwenvert binary list command."""
        with patch("qwenvert.cli.BinaryManager") as mock_mgr_cls:
            mock_mgr = Mock()
            mock_mgr.list_available_versions.return_value = [
                {
                    "version": "b3601",
                    "date": "2024-02-13T10:00:00Z",
                    "url": "https://github.com/example",
                    "prerelease": False,
                },
                {
                    "version": "b3600",
                    "date": "2024-02-12T10:00:00Z",
                    "url": "https://github.com/example",
                    "prerelease": False,
                },
            ]
            mock_mgr.get_installed_version.return_value = "b3600"
            mock_mgr_cls.return_value = mock_mgr

            result = cli_runner.invoke(cli, ["binary", "list"])

            assert result.exit_code == 0
            assert "b3601" in result.output
            assert "b3600" in result.output
            assert "Installed" in result.output

    def test_binary_verify_command(self, cli_runner, mock_binary_info):
        """Test qwenvert binary verify command."""
        with patch("qwenvert.cli.BinaryManager") as mock_mgr_cls:
            mock_mgr = Mock()
            mock_mgr.binary_path = Path("/cache/llama-server")
            mock_mgr.detect_binary.return_value = mock_binary_info
            mock_mgr_cls.return_value = mock_mgr

            # Create fake binary file
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.stat") as mock_stat:
                    import stat

                    mock_stat.return_value = Mock(st_mode=stat.S_IEXEC)

                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = Mock(
                            returncode=0, stdout="llama-server version b3600"
                        )

                        result = cli_runner.invoke(cli, ["binary", "verify"])

                        assert result.exit_code == 0
                        assert "verification passed" in result.output.lower()


@pytest.mark.integration
class TestBackendsCommand:
    """Test backends detection command."""

    def test_backends_command(self, cli_runner):
        """Test qwenvert backends command."""
        from qwenvert.backend_interface import BackendInfo, BackendStatus
        from qwenvert.models import Backend

        mock_backends = {
            Backend.LLAMACPP: BackendInfo(
                name="llama.cpp",
                version="b3600",
                path=Path("/usr/local/bin/llama-server"),
                status=BackendStatus.AVAILABLE,
                installation_method="system",
            ),
            Backend.OLLAMA: BackendInfo(
                name="ollama",
                version=None,
                path=None,
                status=BackendStatus.MISSING,
                installation_method="none",
            ),
        }

        with patch("qwenvert.cli.BackendManager") as mock_mgr_cls:
            with patch("qwenvert.cli.HardwareDetector") as mock_detector_cls:
                mock_mgr_cls.detect_all.return_value = mock_backends
                mock_mgr_cls.recommend_backend.return_value = Backend.LLAMACPP

                mock_detector = Mock()
                mock_detector.detect.return_value = Mock(
                    chip="M1 Pro",
                    total_memory_gb=16,
                )
                mock_detector_cls.return_value = mock_detector

                result = cli_runner.invoke(cli, ["backends"])

                assert result.exit_code == 0
                assert "llama.cpp" in result.output
                assert "ollama" in result.output
                assert "Available" in result.output
                assert "Missing" in result.output
