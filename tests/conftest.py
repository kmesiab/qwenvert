"""
Pytest configuration and shared fixtures.
"""


import pytest

from qwenvert.hardware import HardwareProfile
from qwenvert.models import Backend, Model, ModelRegistry


@pytest.fixture
def mock_hardware_m1_16gb():
    """Mock M1 Mac with 16GB RAM."""
    return HardwareProfile(
        chip="M1",
        chip_family="M1",
        total_memory_gb=16,
        gpu_cores=8,
        cpu_cores_performance=4,
        cpu_cores_efficiency=4,
        has_active_cooling=True,
        neural_engine_cores=16,
        model_identifier="MacBookPro18,1",
    )


@pytest.fixture
def mock_hardware_m1_air_8gb():
    """Mock M1 MacBook Air with 8GB RAM (constrained)."""
    return HardwareProfile(
        chip="M1",
        chip_family="M1",
        total_memory_gb=8,
        gpu_cores=7,
        cpu_cores_performance=4,
        cpu_cores_efficiency=4,
        has_active_cooling=False,  # Fanless
        neural_engine_cores=16,
        model_identifier="MacBookAir10,1",
    )


@pytest.fixture
def mock_hardware_m1_max_32gb():
    """Mock M1 Max with 32GB RAM (high-end)."""
    return HardwareProfile(
        chip="M1 Max",
        chip_family="M1",
        total_memory_gb=32,
        gpu_cores=32,
        cpu_cores_performance=8,
        cpu_cores_efficiency=2,
        has_active_cooling=True,
        neural_engine_cores=16,
        model_identifier="MacBookPro18,3",
    )


@pytest.fixture
def sample_model_7b_q4():
    """Sample Qwen 7B Q4 model."""
    return Model(
        id="qwen2.5-coder-7b-q4-ollama",
        display_name="Qwen2.5 Coder 7B Q4",
        family="qwen2.5-coder",
        size_b=7.0,
        quantization="Q4_K_M",
        backend=Backend.OLLAMA,
        backend_model_id="qwen2.5-coder:7b-instruct-q4_K_M",
        context_length=32768,
        min_ram_gb=8,
        recommended_ram_gb=16,
        is_coder_model=True,
        is_default_candidate=True,
        huggingface_repo="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
    )


@pytest.fixture
def sample_model_14b_q5():
    """Sample Qwen 14B Q5 model."""
    return Model(
        id="qwen2.5-coder-14b-q5-llamacpp",
        display_name="Qwen2.5 Coder 14B Q5",
        family="qwen2.5-coder",
        size_b=14.0,
        quantization="Q5_K_M",
        backend=Backend.LLAMACPP,
        backend_model_id="qwen2.5-coder-14b-instruct-q5_K_M.gguf",
        context_length=32768,
        min_ram_gb=20,
        recommended_ram_gb=32,
        is_coder_model=True,
        is_default_candidate=True,
        huggingface_repo="Qwen/Qwen2.5-Coder-14B-Instruct-GGUF",
    )


@pytest.fixture
def model_registry():
    """Model registry with default models."""
    return ModelRegistry()


@pytest.fixture
def temp_config_dir(tmp_path):
    """Temporary config directory for tests."""
    config_dir = tmp_path / ".config" / "qwenvert"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def mock_qwenvert_config(sample_model_7b_q4, temp_config_dir):
    """Mock QwenvertConfig for testing."""
    from qwenvert.config import QwenvertConfig

    return QwenvertConfig(
        backend="ollama",
        backend_url="http://localhost:11434",
        model_id=sample_model_7b_q4.id,
        context_length=32768,
        adapter_host="127.0.0.1",
        adapter_port=8088,
        thermal_pacing=False,
        thermal_threshold=80,
    )
