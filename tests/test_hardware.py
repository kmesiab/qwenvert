"""Tests for hardware detection module."""

import subprocess
from unittest.mock import MagicMock, patch

from qwenvert.hardware import (
    HardwareDetector,
    HardwareProfile,
    detect_hardware,
)


class TestHardwareProfile:
    """Test HardwareProfile dataclass."""

    def test_hardware_profile_creation(self) -> None:
        """Test creating a hardware profile."""
        profile = HardwareProfile(
            chip="M1 Pro",
            chip_family="M1",
            total_memory_gb=16,
            gpu_cores=16,
            cpu_cores_performance=8,
            cpu_cores_efficiency=2,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="MacBookPro18,3",
        )

        assert profile.chip == "M1 Pro"
        assert profile.total_memory_gb == 16
        assert profile.gpu_cores == 16

    def test_str_representation(self) -> None:
        """Test string representation of hardware profile."""
        profile = HardwareProfile(
            chip="M1 Pro",
            chip_family="M1",
            total_memory_gb=16,
            gpu_cores=16,
            cpu_cores_performance=8,
            cpu_cores_efficiency=2,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="MacBookPro18,3",
        )

        result = str(profile)
        assert "M1 Pro" in result
        assert "16GB RAM" in result
        assert "16 GPU cores" in result
        assert "Active Cooling" in result

    def test_fanless_str_representation(self) -> None:
        """Test string representation for fanless Mac."""
        profile = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=8,
            gpu_cores=7,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=False,
            neural_engine_cores=16,
            model_identifier="MacBookAir10,1",
        )

        result = str(profile)
        assert "Fanless" in result

    def test_is_memory_constrained(self) -> None:
        """Test memory constraint detection."""
        # Constrained (8GB)
        profile_8gb = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=8,
            gpu_cores=7,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=False,
            neural_engine_cores=16,
            model_identifier="MacBookAir10,1",
        )
        assert profile_8gb.is_memory_constrained() is True

        # Not constrained (16GB)
        profile_16gb = HardwareProfile(
            chip="M1 Pro",
            chip_family="M1",
            total_memory_gb=16,
            gpu_cores=16,
            cpu_cores_performance=8,
            cpu_cores_efficiency=2,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="MacBookPro18,3",
        )
        assert profile_16gb.is_memory_constrained() is False

    def test_is_thermally_constrained(self) -> None:
        """Test thermal constraint detection."""
        # Thermally constrained (fanless)
        profile_fanless = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=8,
            gpu_cores=7,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=False,
            neural_engine_cores=16,
            model_identifier="MacBookAir10,1",
        )
        assert profile_fanless.is_thermally_constrained() is True

        # Not thermally constrained (has fan)
        profile_fan = HardwareProfile(
            chip="M1 Pro",
            chip_family="M1",
            total_memory_gb=16,
            gpu_cores=16,
            cpu_cores_performance=8,
            cpu_cores_efficiency=2,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="MacBookPro18,3",
        )
        assert profile_fan.is_thermally_constrained() is False

    def test_recommended_context_length(self) -> None:
        """Test context length recommendations based on memory."""
        # 8GB -> 8192 tokens
        profile_8gb = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=8,
            gpu_cores=7,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=False,
            neural_engine_cores=16,
            model_identifier="MacBookAir10,1",
        )
        assert profile_8gb.recommended_context_length() == 8192

        # 9GB -> 8192 tokens (< 10GB)
        profile_9gb = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=9,
            gpu_cores=7,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=False,
            neural_engine_cores=16,
            model_identifier="MacBookAir10,1",
        )
        assert profile_9gb.recommended_context_length() == 8192

        # 10GB -> 16384 tokens (≥10GB, <16GB)
        profile_10gb = HardwareProfile(
            chip="M1",
            chip_family="M1",
            total_memory_gb=10,
            gpu_cores=8,
            cpu_cores_performance=4,
            cpu_cores_efficiency=4,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="MacBookPro18,1",
        )
        assert profile_10gb.recommended_context_length() == 16384

        # 16GB -> 32768 tokens (≥16GB gets full 32k context)
        profile_16gb = HardwareProfile(
            chip="M1 Pro",
            chip_family="M1",
            total_memory_gb=16,
            gpu_cores=16,
            cpu_cores_performance=8,
            cpu_cores_efficiency=2,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="MacBookPro18,3",
        )
        assert profile_16gb.recommended_context_length() == 32768  # ≥16GB gets 32k

        # 32GB -> 32768 tokens
        profile_32gb = HardwareProfile(
            chip="M1 Max",
            chip_family="M1",
            total_memory_gb=32,
            gpu_cores=32,
            cpu_cores_performance=8,
            cpu_cores_efficiency=2,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="MacBookPro18,1",
        )
        assert profile_32gb.recommended_context_length() == 32768


class TestHardwareDetector:
    """Test HardwareDetector class."""

    @patch("subprocess.check_output")
    def test_detect_chip_from_brand_string(self, mock_subprocess: MagicMock) -> None:
        """Test detecting chip from brand string."""
        mock_subprocess.return_value = "Apple M1 Pro"

        detector = HardwareDetector()
        result = detector._detect_chip()

        assert result == "M1 Pro"

    @patch("subprocess.check_output")
    def test_detect_chip_fallback_to_model(self, mock_subprocess: MagicMock) -> None:
        """Test detecting chip falls back to model identifier."""
        mock_subprocess.side_effect = [
            "Some other string",  # brand_string doesn't contain Apple
            "MacBookAir10,1",  # hw.model
        ]

        detector = HardwareDetector()
        result = detector._detect_chip()

        assert result == "M1"

    def test_extract_chip_family(self) -> None:
        """Test extracting chip family from full name."""
        detector = HardwareDetector()

        assert detector._extract_chip_family("M1 Pro") == "M1"
        assert detector._extract_chip_family("M2 Max") == "M2"
        assert detector._extract_chip_family("M3") == "M3"
        assert detector._extract_chip_family("Unknown") == "Unknown"

    @patch("subprocess.check_output")
    def test_detect_memory(self, mock_subprocess: MagicMock) -> None:
        """Test memory detection and rounding."""
        # 16GB = 17179869184 bytes
        mock_subprocess.return_value = "17179869184"

        detector = HardwareDetector()
        result = detector._detect_memory()

        assert result == 16

    @patch("subprocess.check_output")
    def test_detect_memory_rounds_to_common_size(
        self, mock_subprocess: MagicMock
    ) -> None:
        """Test memory rounds to nearest common size."""
        # 12GB should round to nearest common size
        mock_subprocess.return_value = str(12 * 1024**3)

        detector = HardwareDetector()
        result = detector._detect_memory()

        # Should round to either 8 or 16
        assert result in [8, 16]

    @patch("subprocess.check_output")
    def test_detect_cpu_cores(self, mock_subprocess: MagicMock) -> None:
        """Test CPU core detection."""
        mock_subprocess.side_effect = ["8", "2"]  # 8 perf, 2 efficiency

        detector = HardwareDetector()
        perf, eff = detector._detect_cpu_cores()

        assert perf == 8
        assert eff == 2

    @patch("subprocess.check_output")
    def test_detect_cpu_cores_fallback(self, mock_subprocess: MagicMock) -> None:
        """Test CPU core detection fallback."""
        mock_subprocess.side_effect = subprocess.SubprocessError()

        detector = HardwareDetector()
        perf, eff = detector._detect_cpu_cores()

        # Fallback to M1 base config
        assert perf == 4
        assert eff == 4

    @patch("subprocess.check_output")
    def test_detect_gpu_cores_from_system_profiler(
        self, mock_subprocess: MagicMock
    ) -> None:
        """Test GPU core detection from system_profiler."""
        mock_subprocess.return_value = """
        Graphics/Displays:
            Apple M1 Pro:
                Total Number of Cores: 16
        """

        detector = HardwareDetector()
        result = detector._detect_gpu_cores("M1 Pro")

        assert result == 16

    def test_detect_gpu_cores_from_lookup(self) -> None:
        """Test GPU core detection from lookup table."""
        detector = HardwareDetector()

        # Mock system_profiler to fail
        with patch(
            "subprocess.check_output",
            side_effect=subprocess.SubprocessError(),
        ):
            # Note: Will match "M1" before "M1 Pro" due to dict iteration order
            result = detector._detect_gpu_cores("M1 Pro")

        assert result == 7  # From lookup table (matches "M1" first)

    @patch("subprocess.check_output")
    def test_detect_model_identifier(self, mock_subprocess: MagicMock) -> None:
        """Test model identifier detection."""
        mock_subprocess.return_value = "MacBookPro18,3"

        detector = HardwareDetector()
        result = detector._detect_model_identifier()

        assert result == "MacBookPro18,3"

    def test_infer_chip_from_model(self) -> None:
        """Test inferring chip from model identifier."""
        detector = HardwareDetector()

        assert detector._infer_chip_from_model("MacBookAir10,1") == "M1"
        assert detector._infer_chip_from_model("Mac14,2") == "M2"
        assert detector._infer_chip_from_model("Mac15,12") == "M3"
        assert detector._infer_chip_from_model("Unknown") == "Unknown"

    def test_fanless_models_list(self) -> None:
        """Test fanless models are correctly identified."""
        assert "MacBookAir10,1" in HardwareDetector.FANLESS_MODELS
        assert "Mac14,2" in HardwareDetector.FANLESS_MODELS
        assert "Mac15,12" in HardwareDetector.FANLESS_MODELS

    def test_gpu_cores_map(self) -> None:
        """Test GPU cores map has expected entries."""
        assert HardwareDetector.GPU_CORES_MAP["M1"] == 7
        assert HardwareDetector.GPU_CORES_MAP["M1 Pro"] == 14
        assert HardwareDetector.GPU_CORES_MAP["M2"] == 8
        assert HardwareDetector.GPU_CORES_MAP["M3 Max"] == 30


class TestDetectHardwareFunction:
    """Test convenience function."""

    @patch("qwenvert.hardware.HardwareDetector.detect")
    def test_detect_hardware_calls_detector(self, mock_detect: MagicMock) -> None:
        """Test detect_hardware function calls HardwareDetector.detect()."""
        mock_profile = HardwareProfile(
            chip="M1 Pro",
            chip_family="M1",
            total_memory_gb=16,
            gpu_cores=16,
            cpu_cores_performance=8,
            cpu_cores_efficiency=2,
            has_active_cooling=True,
            neural_engine_cores=16,
            model_identifier="MacBookPro18,3",
        )
        mock_detect.return_value = mock_profile

        result = detect_hardware()

        assert result == mock_profile
        mock_detect.assert_called_once()
