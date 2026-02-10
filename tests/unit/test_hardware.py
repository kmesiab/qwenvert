"""
Unit tests for hardware detection.
"""

from unittest.mock import patch

import pytest

from qwenvert.hardware import HardwareDetector, HardwareProfile


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
        assert mock_hardware_m1_16gb.recommended_context_length() == 16384
        assert mock_hardware_m1_max_32gb.recommended_context_length() == 32768


class TestHardwareDetector:
    """Test hardware detection logic."""

    @patch("subprocess.check_output")
    def test_detect_m1_chip(self, mock_check_output):
        """Test M1 chip detection."""
        mock_check_output.return_value = "Apple M1"

        detector = HardwareDetector()
        chip_name = detector._detect_chip()

        assert chip_name == "M1"

    @patch("subprocess.check_output")
    def test_detect_memory(self, mock_check_output):
        """Test memory detection and rounding."""
        # 17179869184 bytes = 16GB
        mock_check_output.return_value = "17179869184"

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

    @patch("subprocess.check_output")
    def test_detect_chip_fallback_to_hw_model(self, mock_check_output):
        """Test chip detection falls back to hw.model."""
        # First call returns non-Apple string, second call returns model
        mock_check_output.side_effect = ["Unknown CPU", "MacBookAir10,1"]

        detector = HardwareDetector()
        chip_name = detector._detect_chip()

        # Should infer M1 from MacBookAir10,1
        assert chip_name == "M1"

    @patch("subprocess.check_output")
    def test_detect_cpu_cores(self, mock_check_output):
        """Test CPU core detection."""
        # Return 4 performance cores and 4 efficiency cores
        mock_check_output.side_effect = ["4", "4"]

        detector = HardwareDetector()
        perf, eff = detector._detect_cpu_cores()

        assert perf == 4
        assert eff == 4

    @patch("subprocess.check_output")
    def test_detect_cpu_cores_fallback(self, mock_check_output):
        """Test CPU core detection fallback on error."""
        import subprocess

        mock_check_output.side_effect = subprocess.SubprocessError("Error")

        detector = HardwareDetector()
        perf, eff = detector._detect_cpu_cores()

        # Should return default M1 config
        assert perf == 4
        assert eff == 4

    @patch("subprocess.check_output")
    def test_detect_cpu_cores_no_efficiency_cores(self, mock_check_output):
        """Test CPU core detection when no efficiency cores reported."""
        import subprocess

        def side_effect(cmd, **kwargs):
            if "perflevel0" in cmd[2]:
                return "8"
            msg = "No efficiency cores"
            raise subprocess.SubprocessError(msg)

        mock_check_output.side_effect = side_effect

        detector = HardwareDetector()
        perf, eff = detector._detect_cpu_cores()

        assert perf == 8
        assert eff == 0

    @patch("subprocess.check_output")
    def test_detect_gpu_cores_from_system_profiler(self, mock_check_output):
        """Test GPU core detection from system_profiler."""
        mock_check_output.return_value = "Total Number of Cores: 16"

        detector = HardwareDetector()
        gpu_cores = detector._detect_gpu_cores("M1 Pro")

        assert gpu_cores == 16

    @patch("subprocess.check_output")
    def test_detect_gpu_cores_fallback_to_map(self, mock_check_output):
        """Test GPU core detection falls back to lookup table."""
        import subprocess

        # TimeoutExpired is also caught, so use that
        mock_check_output.side_effect = subprocess.TimeoutExpired("cmd", 5)

        detector = HardwareDetector()
        # Note: "M1" matches before "M1 Pro" in the lookup, so we get M1's value
        gpu_cores = detector._detect_gpu_cores("M1")

        assert gpu_cores == 7  # From GPU_CORES_MAP for M1

    @patch("subprocess.check_output")
    def test_detect_gpu_cores_default_fallback(self, mock_check_output):
        """Test GPU core detection default fallback."""
        import subprocess

        mock_check_output.side_effect = subprocess.SubprocessError(
            "system_profiler failed"
        )

        detector = HardwareDetector()
        gpu_cores = detector._detect_gpu_cores("Unknown Chip")

        assert gpu_cores == 8  # Default fallback

    @patch("subprocess.check_output")
    def test_detect_model_identifier(self, mock_check_output):
        """Test model identifier detection."""
        mock_check_output.return_value = "MacBookPro18,3"

        detector = HardwareDetector()
        model_id = detector._detect_model_identifier()

        assert model_id == "MacBookPro18,3"

    @patch("subprocess.check_output")
    def test_detect_model_identifier_error(self, mock_check_output):
        """Test model identifier detection on error."""
        import subprocess

        mock_check_output.side_effect = subprocess.SubprocessError("Error")

        detector = HardwareDetector()
        model_id = detector._detect_model_identifier()

        assert model_id == "Unknown"

    def test_infer_chip_from_model(self):
        """Test chip inference from model identifier."""
        detector = HardwareDetector()

        assert detector._infer_chip_from_model("MacBookAir10,1") == "M1"
        assert detector._infer_chip_from_model("Mac14,2") == "M2"
        assert detector._infer_chip_from_model("Mac15,12") == "M3"
        assert detector._infer_chip_from_model("Unknown") == "Unknown"

    @patch("subprocess.check_output")
    def test_detect_memory_rounding_to_common_sizes(self, mock_check_output):
        """Test memory rounding to common sizes."""
        detector = HardwareDetector()

        # Test various memory sizes
        # 25GB should round to 24GB
        mock_check_output.return_value = str(25 * 1024**3)
        assert detector._detect_memory() == 24

        # 50GB should round to 48GB
        mock_check_output.return_value = str(50 * 1024**3)
        assert detector._detect_memory() == 48

    @patch("subprocess.check_output")
    def test_detect_memory_error_handling(self, mock_check_output):
        """Test memory detection error handling."""
        import subprocess

        mock_check_output.side_effect = subprocess.SubprocessError("Error")

        detector = HardwareDetector()

        with pytest.raises(RuntimeError, match="Failed to detect memory"):
            detector._detect_memory()

    @patch("subprocess.check_output")
    def test_detect_chip_error_handling(self, mock_check_output):
        """Test chip detection error handling."""
        import subprocess

        mock_check_output.side_effect = subprocess.SubprocessError("Error")

        detector = HardwareDetector()

        with pytest.raises(RuntimeError, match="Failed to detect chip"):
            detector._detect_chip()

    def test_hardware_profile_string_representation(self, mock_hardware_m1_16gb):
        """Test HardwareProfile string representation."""
        hw_str = str(mock_hardware_m1_16gb)

        assert "M1" in hw_str
        assert "16GB" in hw_str
        assert "8 GPU cores" in hw_str
        assert "Active Cooling" in hw_str

    def test_hardware_profile_string_fanless(self, mock_hardware_m1_air_8gb):
        """Test HardwareProfile string representation for fanless Mac."""
        hw_str = str(mock_hardware_m1_air_8gb)

        assert "Fanless" in hw_str

    @patch.object(HardwareDetector, "detect")
    def test_detect_hardware_convenience_function(self, mock_detect):
        """Test detect_hardware convenience function."""
        from qwenvert.hardware import detect_hardware

        mock_profile = HardwareProfile(
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
        mock_detect.return_value = mock_profile

        result = detect_hardware()

        assert result == mock_profile
        mock_detect.assert_called_once()

    def test_fanless_models_set_contains_known_models(self):
        """Test that FANLESS_MODELS contains expected model identifiers."""
        assert "MacBookAir10,1" in HardwareDetector.FANLESS_MODELS
        assert "Mac14,2" in HardwareDetector.FANLESS_MODELS
        assert "Mac15,12" in HardwareDetector.FANLESS_MODELS

    def test_gpu_cores_map_contains_common_chips(self):
        """Test that GPU_CORES_MAP contains common Apple Silicon chips."""
        assert "M1" in HardwareDetector.GPU_CORES_MAP
        assert "M1 Pro" in HardwareDetector.GPU_CORES_MAP
        assert "M2" in HardwareDetector.GPU_CORES_MAP
        assert "M3" in HardwareDetector.GPU_CORES_MAP

    @patch("subprocess.check_output")
    def test_full_detect_integration(self, mock_check_output):
        """Test full hardware detection flow."""
        # Mock all subprocess calls in order
        mock_check_output.side_effect = [
            "Apple M1 Pro",  # chip detection (brand string)
            "17179869184",  # memory detection (16GB)
            "8",  # performance cores
            "4",  # efficiency cores
            "MacBookPro18,3",  # model identifier
        ]

        with patch(
            "subprocess.check_output", side_effect=mock_check_output.side_effect
        ):
            # Mock system_profiler to raise timeout
            with patch.object(HardwareDetector, "_detect_gpu_cores") as mock_gpu:
                mock_gpu.return_value = 16  # M1 Pro GPU cores

                profile = HardwareDetector.detect()

                assert profile.chip == "M1 Pro"
                assert profile.chip_family == "M1"
                assert profile.total_memory_gb == 16
                assert profile.cpu_cores_performance == 8
                assert profile.cpu_cores_efficiency == 4
                assert profile.gpu_cores == 16
                assert profile.model_identifier == "MacBookPro18,3"
                assert profile.has_active_cooling is True

    def test_extract_chip_family_unknown(self):
        """Test chip family extraction for unknown chip."""
        detector = HardwareDetector()

        assert detector._extract_chip_family("Unknown Chip") == "Unknown"

    @patch("subprocess.check_output")
    def test_detect_memory_various_sizes(self, mock_check_output):
        """Test memory detection with various memory sizes."""
        detector = HardwareDetector()

        # Test 8GB
        mock_check_output.return_value = str(8 * 1024**3)
        assert detector._detect_memory() == 8

        # Test 32GB
        mock_check_output.return_value = str(32 * 1024**3)
        assert detector._detect_memory() == 32

        # Test 64GB
        mock_check_output.return_value = str(64 * 1024**3)
        assert detector._detect_memory() == 64
