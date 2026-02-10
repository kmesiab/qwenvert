"""
Simplified CLI tests focusing on coverage.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from qwenvert.cli import cli


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


class TestCLIHelp:
    """Test CLI help commands - these work without mocking."""

    def test_main_help(self, runner):
        """Test main CLI help."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "start" in result.output

    def test_init_help(self, runner):
        """Test init command help."""
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0
        assert "model" in result.output.lower()

    def test_start_help(self, runner):
        """Test start command help."""
        result = runner.invoke(cli, ["start", "--help"])
        assert result.exit_code == 0

    def test_stop_help(self, runner):
        """Test stop command help."""
        result = runner.invoke(cli, ["stop", "--help"])
        assert result.exit_code == 0

    def test_status_help(self, runner):
        """Test status command help."""
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0

    def test_models_help(self, runner):
        """Test models command help."""
        result = runner.invoke(cli, ["models", "--help"])
        assert result.exit_code == 0

    def test_hardware_help(self, runner):
        """Test hardware command help."""
        result = runner.invoke(cli, ["hardware", "--help"])
        assert result.exit_code == 0

    def test_monitor_help(self, runner):
        """Test monitor command help."""
        result = runner.invoke(cli, ["monitor", "--help"])
        assert result.exit_code == 0


class TestCLIErrors:
    """Test error handling."""

    def test_invalid_command(self, runner):
        """Test invalid command."""
        result = runner.invoke(cli, ["invalid"])
        assert result.exit_code != 0

    def test_version(self, runner):
        """Test version flag."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output or "version" in result.output.lower()
