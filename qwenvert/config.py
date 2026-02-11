"""
Configuration generation and management.

Generates optimal configurations for Ollama, llama.cpp, and qwenvert
based on hardware profile and model selection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .models import Backend, Model
from .security import validate_adapter_host, validate_localhost_url


if TYPE_CHECKING:
    from .hardware import HardwareProfile


@dataclass
class QwenvertConfig:
    """
    Complete qwenvert configuration.

    Attributes:
        model_id: Selected model identifier
        backend: Backend type (ollama, llamacpp)
        backend_url: Backend server URL
        backend_model_id: Backend-specific model identifier
        adapter_host: Adapter server host
        adapter_port: Adapter server port
        context_length: Maximum context length
        thermal_monitoring: Enable thermal monitoring
        thermal_pacing: Enable thermal pacing (for fanless Macs)
    """

    model_id: str
    backend: str
    backend_url: str
    backend_model_id: str
    adapter_host: str = "127.0.0.1"
    adapter_port: int = 8088
    context_length: int = 16384
    thermal_monitoring: bool = True
    thermal_pacing: bool = False
    model_path: str | None = None

    @classmethod
    def default_config_path(cls) -> Path:
        """Get default config file path."""
        config_dir = Path.home() / ".config" / "qwenvert"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.yaml"

    def validate(self) -> None:
        """
        Validate configuration for security.

        Raises:
            SecurityValidationError: If configuration violates security requirements
        """
        # Validate adapter host is localhost-only
        validate_adapter_host(self.adapter_host)

        # Validate backend URL is localhost-only
        validate_localhost_url(self.backend_url)

    def save(self, path: Path | None = None) -> Path:
        """
        Save configuration to YAML file.

        Args:
            path: Config file path (default: ~/.config/qwenvert/config.yaml)

        Returns:
            Path where config was saved
        """
        if path is None:
            path = self.default_config_path()

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            yaml.safe_dump(asdict(self), f, default_flow_style=False)

        return path

    @classmethod
    def load(cls, path: Path | None = None) -> QwenvertConfig:
        """
        Load configuration from YAML file.

        Args:
            path: Config file path (default: ~/.config/qwenvert/config.yaml)

        Returns:
            Loaded configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            SecurityValidationError: If config violates security requirements
        """
        if path is None:
            path = cls.default_config_path()

        with open(path) as f:
            data = yaml.safe_load(f)

        config = cls(**data)

        # SECURITY: Validate loaded config
        config.validate()

        return config


class ConfigGenerator:
    """
    Generates optimal configurations for backends and qwenvert.
    """

    def __init__(self, model: Model, hardware: HardwareProfile) -> None:
        """
        Initialize config generator.

        Args:
            model: Selected model
            hardware: Detected hardware profile
        """
        self.model = model
        self.hardware = hardware

    def generate_qwenvert_config(
        self,
        adapter_host: str = "127.0.0.1",
        adapter_port: int = 8088,
    ) -> QwenvertConfig:
        """
        Generate qwenvert configuration.

        Args:
            adapter_host: Adapter server host
            adapter_port: Adapter server port

        Returns:
            Qwenvert configuration
        """
        # Determine backend URL based on backend type
        if self.model.backend == Backend.OLLAMA:
            backend_url = "http://localhost:11434"
        elif self.model.backend == Backend.LLAMACPP:
            backend_url = "http://localhost:8080"
        else:
            backend_url = "http://localhost:8080"

        # Determine context length (respect hardware constraints)
        context_length = min(
            self.model.context_length,
            self.hardware.recommended_context_length(),
        )

        # Enable thermal features for constrained hardware
        thermal_monitoring = True
        thermal_pacing = self.hardware.is_thermally_constrained()

        return QwenvertConfig(
            model_id=self.model.id,
            backend=self.model.backend.value,
            backend_url=backend_url,
            backend_model_id=self.model.backend_model_id,
            adapter_host=adapter_host,
            adapter_port=adapter_port,
            context_length=context_length,
            thermal_monitoring=thermal_monitoring,
            thermal_pacing=thermal_pacing,
        )

    def generate_ollama_modelfile(self) -> str:
        """
        Generate Ollama Modelfile with optimal parameters.

        Returns:
            Modelfile content as string

        Example:
            FROM qwen2.5-coder:7b-instruct-q4_K_M
            PARAMETER num_ctx 16384
            PARAMETER num_gpu 1
            PARAMETER num_thread 4
            PARAMETER temperature 0.7
        """
        if self.model.backend != Backend.OLLAMA:
            raise ValueError(f"Model backend is {self.model.backend}, not Ollama")

        context_length = min(
            self.model.context_length,
            self.hardware.recommended_context_length(),
        )

        # Use performance cores only
        num_threads = self.hardware.cpu_cores_performance

        return f"""# Qwenvert Modelfile for {self.model.display_name}
# Generated for {self.hardware.chip} with {self.hardware.total_memory_gb}GB RAM

FROM {self.model.backend_model_id}

# Context window
PARAMETER num_ctx {context_length}

# Hardware optimization
PARAMETER num_gpu 1
PARAMETER num_thread {num_threads}

# Generation parameters (can be overridden per-request)
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER repeat_penalty 1.1

# System prompt
SYSTEM You are a helpful AI coding assistant powered by Qwen2.5-Coder running locally via qwenvert.
"""

    def generate_llamacpp_flags(self) -> list[str]:
        """
        Generate llama.cpp command-line flags with optimal parameters.

        Returns:
            List of command-line flags

        Example:
            ['--model', 'path.gguf', '-ngl', '99', '-t', '4', '-c', '16384']
        """
        if self.model.backend != Backend.LLAMACPP:
            raise ValueError(f"Model backend is {self.model.backend}, not llama.cpp")

        context_length = min(
            self.model.context_length,
            self.hardware.recommended_context_length(),
        )

        # Use performance cores only
        num_threads = self.hardware.cpu_cores_performance

        return [
            "--model",
            f"~/.cache/qwenvert/models/{self.model.backend_model_id}",
            # GPU offloading
            "-ngl",
            "99",  # Offload all layers to Metal
            # CPU threads
            "-t",
            str(num_threads),
            # Context window
            "-c",
            str(context_length),
            # Server config
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
            # Memory optimization
            "--mlock",  # Lock model in memory
            # API compatibility
            "--log-disable",  # Reduce log noise
        ]

    def generate_environment_vars(self) -> dict[str, str]:
        """
        Generate environment variables for Claude Code integration.

        Returns:
            Dictionary of environment variables

        Example:
            {
                'ANTHROPIC_BASE_URL': 'http://localhost:8088',
                'ANTHROPIC_API_KEY': 'local-qwen',
                'ANTHROPIC_MODEL': 'qwenvert-default'
            }
        """
        config = self.generate_qwenvert_config()

        return {
            "ANTHROPIC_BASE_URL": f"http://{config.adapter_host}:{config.adapter_port}",
            "ANTHROPIC_API_KEY": "local-qwen",
            "ANTHROPIC_MODEL": "qwenvert-default",
        }

    def print_setup_instructions(self) -> str:
        """
        Generate user-friendly setup instructions.

        Returns:
            Formatted setup instructions
        """
        config = self.generate_qwenvert_config()
        env_vars = self.generate_environment_vars()

        return f"""
╔════════════════════════════════════════════════════════════════╗
║                  Qwenvert Setup Complete                       ║
╚════════════════════════════════════════════════════════════════╝

Selected Configuration:
  Model:    {self.model.display_name}
  Backend:  {self.model.backend.value}
  Context:  {config.context_length:,} tokens
  Thermal:  {"Pacing enabled (fanless Mac)" if config.thermal_pacing else "Monitoring enabled"}

To use with Claude Code, run these commands:

  export ANTHROPIC_BASE_URL="{env_vars["ANTHROPIC_BASE_URL"]}"
  export ANTHROPIC_API_KEY="{env_vars["ANTHROPIC_API_KEY"]}"
  export ANTHROPIC_MODEL="{env_vars["ANTHROPIC_MODEL"]}"

Then start Claude Code:

  claude

Configuration saved to: {config.default_config_path()}
"""


class ConfigManager:
    """
    Manages qwenvert configuration lifecycle.
    """

    @staticmethod
    def exists() -> bool:
        """Check if config file exists."""
        return QwenvertConfig.default_config_path().exists()

    @staticmethod
    def load() -> QwenvertConfig:
        """Load existing configuration."""
        return QwenvertConfig.load()

    @staticmethod
    def save(config: QwenvertConfig) -> Path:
        """Save configuration."""
        return config.save()

    @staticmethod
    def delete() -> None:
        """Delete configuration file."""
        path = QwenvertConfig.default_config_path()
        if path.exists():
            path.unlink()

    @staticmethod
    def get_ollama_modelfile_path() -> Path:
        """Get path for Ollama Modelfile."""
        config_dir = Path.home() / ".config" / "qwenvert"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "Modelfile.qwenvert"

    @staticmethod
    def save_ollama_modelfile(content: str) -> Path:
        """
        Save Ollama Modelfile.

        Args:
            content: Modelfile content

        Returns:
            Path where Modelfile was saved
        """
        path = ConfigManager.get_ollama_modelfile_path()
        path.write_text(content)
        return path
