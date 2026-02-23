"""
Unit tests for hardware detection.
"""

from unittest.mock import patch

from qwenvert.hardware import HardwareDetector


class TestHardwareProfile:
    """Test HardwareProfile helper methods."""

    def test_is_memory_constrained(
        self, mock_hardware_m1_air_8gb, mock_hardware_m1_16gb
    ):
        """Test memory constraint detection."""
        assert mock_hardware_m1_air_8gb.is_memory_constrained()
        assert not mock_hardware_m1_16gb.is_memory_constrained()

    def test_is_thermally_constrained(
        self, mock_hardware_m1_air_8gb, mock_hardware_m1_16gb
    ):
        """Test thermal constraint detection."""
        assert mock_hardware_m1_air_8gb.is_thermally_constrained()  # Fanless
        assert not mock_hardware_m1_16gb.is_thermally_constrained()  # Has fan

    def test_recommended_context_length(
        self, mock_hardware_m1_air_8gb, mock_hardware_m1_16gb, mock_hardware_m1_max_32gb
    ):
        """Test context length recommendations based on RAM."""
        assert mock_hardware_m1_air_8gb.recommended_context_length() == 8192
        assert (
            mock_hardware_m1_16gb.recommended_context_length() == 32768
        )  # ≥16GB gets 32k
        assert mock_hardware_m1_max_32gb.recommended_context_length() == 32768


class TestHardwareDetector:
    """Test hardware detection logic."""

    @patch("subprocess.check_output")
    def test_detect_m1_chip(self, mock_check_output):
        """Test M1 chip detection."""
        # Mock returns string because real code uses text=True
        mock_check_output.return_value = "Apple M1\n"

        detector = HardwareDetector()
        chip_name = detector._detect_chip()

        assert chip_name == "M1"

    @patch("subprocess.check_output")
    def test_detect_memory(self, mock_check_output):
        """Test memory detection and rounding."""
        # 17179869184 bytes = 16GB
        mock_check_output.return_value = b"17179869184\n"

        detector = HardwareDetector()
        memory_gb = detector._detect_memory()

        assert memory_gb == 16

    def test_extract_chip_family(self):
        """Test chip family extraction."""
        detector = HardwareDetector()

        assert detector._extract_chip_family("M1") == "M1"
        assert detector._extract_chip_family("M1 Pro") == "M1"
        assert detector._extract_chip_family("M1 Max") == "M1"
        assert detector._extract_chip_family("M2") == "M2"
        assert detector._extract_chip_family("M3 Max") == "M3"
