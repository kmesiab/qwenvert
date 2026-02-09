"""
Hardware detection module for Apple Silicon Macs.

Detects chip type, memory, GPU cores, and cooling configuration to enable
optimal model selection and performance tuning.
"""

import re
import subprocess
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class HardwareProfile:
    """
    Complete hardware profile for a Mac.

    Attributes:
        chip: Chip identifier (e.g., "M1", "M1 Pro", "M1 Max", "M2", "M3")
        chip_family: Base chip family ("M1", "M2", "M3", "M4")
        total_memory_gb: Total unified memory in GB
        gpu_cores: Number of GPU cores
        cpu_cores_performance: Number of performance CPU cores
        cpu_cores_efficiency: Number of efficiency CPU cores
        has_active_cooling: True if Mac has a fan, False for fanless (MacBook Air)
        neural_engine_cores: Number of Neural Engine cores (typically 16)
        model_identifier: Mac model identifier (e.g., "MacBookAir10,1")
    """

    chip: str
    chip_family: str
    total_memory_gb: int
    gpu_cores: int
    cpu_cores_performance: int
    cpu_cores_efficiency: int
    has_active_cooling: bool
    neural_engine_cores: int
    model_identifier: str

    def __str__(self) -> str:
        """Human-readable hardware description."""
        cooling = "Active Cooling" if self.has_active_cooling else "Fanless"
        return (
            f"{self.chip} | {self.total_memory_gb}GB RAM | "
            f"{self.gpu_cores} GPU cores | {cooling}"
        )

    def is_memory_constrained(self) -> bool:
        """Check if system has limited memory (≤8GB)."""
        return self.total_memory_gb <= 8

    def is_thermally_constrained(self) -> bool:
        """Check if system is thermally constrained (fanless)."""
        return not self.has_active_cooling

    def recommended_context_length(self) -> int:
        """
        Recommend context window size based on available memory.

        Returns:
            Recommended context length in tokens
        """
        if self.total_memory_gb >= 32:
            return 32768
        if self.total_memory_gb >= 16:
            return 16384
        return 8192


class HardwareDetector:
    """
    Detects Apple Silicon Mac hardware configuration.

    Uses sysctl and system_profiler to gather comprehensive hardware info.
    Optimized for M-series chips but provides graceful degradation for
    unsupported hardware.
    """

    # Known Mac model identifiers and their cooling configurations
    FANLESS_MODELS: ClassVar[set[str]] = {
        "MacBookAir10,1",  # M1 MacBook Air
        "Mac14,2",  # M2 MacBook Air 13"
        "Mac14,15",  # M2 MacBook Air 15"
        "Mac15,12",  # M3 MacBook Air 13"
        "Mac15,13",  # M3 MacBook Air 15"
    }

    # GPU core counts by chip variant
    GPU_CORES_MAP: ClassVar[dict[str, int]] = {
        "M1": 7,  # Base M1 (some have 8)
        "M1 Pro": 14,  # Base M1 Pro (16 for higher config)
        "M1 Max": 24,  # Base M1 Max (32 for higher config)
        "M1 Ultra": 48,  # Base M1 Ultra (64 for higher config)
        "M2": 8,  # Base M2 (10 for higher config)
        "M2 Pro": 16,  # Base M2 Pro (19 for higher config)
        "M2 Max": 30,  # Base M2 Max (38 for higher config)
        "M2 Ultra": 60,  # Base M2 Ultra (76 for higher config)
        "M3": 8,  # Base M3 (10 for higher config)
        "M3 Pro": 14,  # Base M3 Pro (18 for higher config)
        "M3 Max": 30,  # Base M3 Max (40 for higher config)
        "M4": 10,  # Base M4
    }

    @staticmethod
    def detect() -> HardwareProfile:
        """
        Detect hardware profile of current Mac.

        Returns:
            HardwareProfile with complete system configuration

        Raises:
            RuntimeError: If not running on macOS or detection fails
        """
        detector = HardwareDetector()

        # Detect chip
        chip_name = detector._detect_chip()
        chip_family = detector._extract_chip_family(chip_name)

        # Detect memory
        total_memory_gb = detector._detect_memory()

        # Detect CPU cores
        perf_cores, efficiency_cores = detector._detect_cpu_cores()

        # Detect GPU cores
        gpu_cores = detector._detect_gpu_cores(chip_name)

        # Detect model identifier
        model_id = detector._detect_model_identifier()

        # Determine cooling
        has_active_cooling = model_id not in HardwareDetector.FANLESS_MODELS

        # Neural Engine cores (constant across M-series)
        neural_engine_cores = 16

        return HardwareProfile(
            chip=chip_name,
            chip_family=chip_family,
            total_memory_gb=total_memory_gb,
            gpu_cores=gpu_cores,
            cpu_cores_performance=perf_cores,
            cpu_cores_efficiency=efficiency_cores,
            has_active_cooling=has_active_cooling,
            neural_engine_cores=neural_engine_cores,
            model_identifier=model_id,
        )

    def _detect_chip(self) -> str:
        """
        Detect chip name from system.

        Returns:
            Chip name (e.g., "M1", "M1 Pro", "M2 Max")
        """
        try:
            # Try machdep.cpu.brand_string first (most reliable)
            output = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()

            # Parse chip from brand string
            # Example: "Apple M1 Pro"
            if "Apple" in output:
                return output.replace("Apple ", "").strip()

            # Fallback: try hw.model
            output = subprocess.check_output(
                ["sysctl", "-n", "hw.model"], text=True, stderr=subprocess.DEVNULL
            ).strip()

            # Parse from model identifier (e.g., "MacBookPro18,3" → M1 Pro)
            return self._infer_chip_from_model(output)

        except subprocess.SubprocessError as e:
            raise RuntimeError(f"Failed to detect chip: {e}") from e

    def _extract_chip_family(self, chip_name: str) -> str:
        """
        Extract base chip family from full chip name.

        Args:
            chip_name: Full chip name (e.g., "M1 Pro")

        Returns:
            Base chip family (e.g., "M1")
        """
        # Extract M1, M2, M3, etc.
        match = re.match(r"(M\d+)", chip_name)
        if match:
            return match.group(1)
        return "Unknown"

    def _detect_memory(self) -> int:
        """
        Detect total system memory in GB.

        Returns:
            Total memory in gigabytes (rounded)
        """
        try:
            output = subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True, stderr=subprocess.DEVNULL
            ).strip()

            bytes_total = int(output)
            gb_total = bytes_total / (1024**3)

            # Round to nearest common size (8, 16, 24, 32, 48, 64, 96, 128)
            common_sizes = [8, 16, 24, 32, 48, 64, 96, 128]
            return min(common_sizes, key=lambda x: abs(x - gb_total))

        except (subprocess.SubprocessError, ValueError) as e:
            raise RuntimeError(f"Failed to detect memory: {e}") from e

    def _detect_cpu_cores(self) -> tuple[int, int]:
        """
        Detect CPU core configuration.

        Returns:
            Tuple of (performance_cores, efficiency_cores)
        """
        try:
            # Get performance core count
            perf_output = subprocess.check_output(
                ["sysctl", "-n", "hw.perflevel0.physicalcpu"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            perf_cores = int(perf_output)

            # Get efficiency core count
            try:
                eff_output = subprocess.check_output(
                    ["sysctl", "-n", "hw.perflevel1.physicalcpu"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
                eff_cores = int(eff_output)
            except subprocess.SubprocessError:
                # Some Macs may not report efficiency cores separately
                eff_cores = 0

            return perf_cores, eff_cores

        except (subprocess.SubprocessError, ValueError):
            # Fallback: assume M1 base config (4P+4E)
            return 4, 4

    def _detect_gpu_cores(self, chip_name: str) -> int:
        """
        Detect or infer GPU core count.

        Args:
            chip_name: Detected chip name

        Returns:
            Number of GPU cores
        """
        # Try to detect from system_profiler (slower but accurate)
        try:
            output = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )

            # Look for "Total Number of Cores: XX"
            match = re.search(r"Total Number of Cores:\s*(\d+)", output)
            if match:
                return int(match.group(1))
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            pass

        # Fallback: use lookup table
        for chip_variant, cores in HardwareDetector.GPU_CORES_MAP.items():
            if chip_variant in chip_name:
                return cores

        # Default fallback
        return 8

    def _detect_model_identifier(self) -> str:
        """
        Detect Mac model identifier.

        Returns:
            Model identifier (e.g., "MacBookAir10,1")
        """
        try:
            return subprocess.check_output(
                ["sysctl", "-n", "hw.model"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except subprocess.SubprocessError:
            return "Unknown"

    def _infer_chip_from_model(self, model_id: str) -> str:
        """
        Infer chip type from model identifier.

        Args:
            model_id: Mac model identifier

        Returns:
            Inferred chip name
        """
        # This is a fallback heuristic
        if "MacBookAir10,1" in model_id:
            return "M1"
        if "Mac14" in model_id:
            return "M2"
        if "Mac15" in model_id:
            return "M3"

        return "Unknown"


# Convenience function for quick detection
def detect_hardware() -> HardwareProfile:
    """
    Convenience function to detect hardware profile.

    Returns:
        HardwareProfile of current system

    Example:
        >>> from qwenvert import detect_hardware
        >>> profile = detect_hardware()
        >>> print(profile)
        M1 Pro | 16GB RAM | 16 GPU cores | Active Cooling
    """
    return HardwareDetector.detect()
