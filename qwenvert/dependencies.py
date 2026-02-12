"""
Dependency checking and installation guidance for qwenvert.

Provides user-friendly error messages and installation instructions
for required dependencies like Ollama and Homebrew.
"""

from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass
from enum import Enum


class DependencyStatus(Enum):
    """Status of a dependency check."""

    INSTALLED = "installed"
    MISSING = "missing"
    UNKNOWN = "unknown"


@dataclass
class DependencyCheckResult:
    """Result of a dependency check."""

    name: str
    status: DependencyStatus
    path: str | None = None
    install_instructions: str | None = None
    error_message: str | None = None

    @property
    def is_available(self) -> bool:
        """Check if dependency is available."""
        return self.status == DependencyStatus.INSTALLED


class DependencyError(Exception):
    """Raised when a required dependency is missing."""

    def __init__(self, result: DependencyCheckResult) -> None:
        self.result = result
        super().__init__(result.error_message or f"{result.name} is not available")


# SECURITY: Whitelist of dependencies allowed for auto-installation
ALLOWED_AUTO_INSTALL_DEPENDENCIES = {"ollama", "llama.cpp"}


def check_homebrew() -> DependencyCheckResult:
    """
    Check if Homebrew is installed.

    Returns:
        DependencyCheckResult with status and installation instructions
    """
    brew_path = shutil.which("brew")

    if brew_path:
        return DependencyCheckResult(
            name="Homebrew",
            status=DependencyStatus.INSTALLED,
            path=brew_path,
        )

    # Check if we're on macOS (qwenvert is Mac-only)
    if platform.system() != "Darwin":
        return DependencyCheckResult(
            name="Homebrew",
            status=DependencyStatus.UNKNOWN,
            error_message="Homebrew is only available on macOS",
        )

    install_cmd = (
        '/bin/bash -c "$(curl -fsSL '
        'https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    )

    return DependencyCheckResult(
        name="Homebrew",
        status=DependencyStatus.MISSING,
        install_instructions=f"""Homebrew is not installed. Homebrew is the recommended way to install dependencies.

To install Homebrew:
  1. Run: {install_cmd}
  2. Follow the on-screen instructions
  3. Restart your terminal

Learn more: https://brew.sh""",
        error_message="Homebrew is not installed (recommended for managing dependencies)",
    )


def check_ollama() -> DependencyCheckResult:
    """
    Check if Ollama is installed.

    Returns:
        DependencyCheckResult with status and installation instructions
    """
    ollama_path = shutil.which("ollama")

    if ollama_path:
        return DependencyCheckResult(
            name="Ollama",
            status=DependencyStatus.INSTALLED,
            path=ollama_path,
        )

    # Check if Homebrew is available for installation instructions
    homebrew = check_homebrew()

    if homebrew.is_available:
        instructions = """Ollama is not installed. Ollama is required to run local LLM models.

To install Ollama using Homebrew:
  1. Run: brew install ollama
  2. Wait for installation to complete
  3. Run: qwenvert init

Learn more: https://ollama.ai"""
    else:
        instructions = """Ollama is not installed. Ollama is required to run local LLM models.

Installation options:

Option 1 - Install Homebrew first (recommended):
  1. Install Homebrew: https://brew.sh
  2. Run: brew install ollama
  3. Run: qwenvert init

Option 2 - Download directly:
  1. Visit: https://ollama.ai/download
  2. Download the macOS installer
  3. Open the .dmg file and follow instructions
  4. Run: qwenvert init

Learn more: https://ollama.ai"""

    return DependencyCheckResult(
        name="Ollama",
        status=DependencyStatus.MISSING,
        install_instructions=instructions,
        error_message="Ollama is not installed (required for running local models)",
    )


def check_llamacpp() -> DependencyCheckResult:
    """
    Check if llama.cpp server is installed.

    Returns:
        DependencyCheckResult with status and installation instructions
    """
    # Check multiple possible locations for llama-server
    possible_paths = [
        shutil.which("llama-server"),
        shutil.which("llama.cpp"),
    ]

    for path in possible_paths:
        if path:
            return DependencyCheckResult(
                name="llama.cpp",
                status=DependencyStatus.INSTALLED,
                path=path,
            )

    homebrew = check_homebrew()

    if homebrew.is_available:
        instructions = """llama.cpp is not installed. llama.cpp is required for the llamacpp backend.

Note: llama.cpp is more complex to set up than Ollama. Consider using Ollama instead.

To install llama.cpp:
  1. Visit: https://github.com/ggerganov/llama.cpp
  2. Follow the build instructions for macOS
  3. Ensure llama-server is in your PATH
  4. Run: qwenvert init --backend llamacpp

Easier alternative: Use Ollama backend instead
  Run: qwenvert init --backend ollama

Learn more: https://github.com/ggerganov/llama.cpp"""
    else:
        instructions = """llama.cpp is not installed. llama.cpp is required for the llamacpp backend.

Note: llama.cpp is more complex to set up than Ollama. Consider using Ollama instead.

To install llama.cpp:
  1. Install Homebrew first: https://brew.sh
  2. Visit: https://github.com/ggerganov/llama.cpp
  3. Follow the build instructions
  4. Run: qwenvert init --backend llamacpp

Easier alternative: Use Ollama backend instead (recommended)

Learn more: https://github.com/ggerganov/llama.cpp"""

    return DependencyCheckResult(
        name="llama.cpp",
        status=DependencyStatus.MISSING,
        install_instructions=instructions,
        error_message="llama.cpp is not installed (required for llamacpp backend)",
    )


def check_backend_dependencies(backend: str | None) -> DependencyCheckResult:
    """
    Check dependencies for a specific backend.

    Args:
        backend: Backend name ('ollama' or 'llamacpp') or None

    Returns:
        DependencyCheckResult for the backend
    """
    if backend is None:
        return DependencyCheckResult(
            name="",
            status=DependencyStatus.UNKNOWN,
            error_message="No backend specified",
        )

    if backend == "ollama":
        return check_ollama()
    if backend == "llamacpp":
        return check_llamacpp()

    return DependencyCheckResult(
        name=backend,
        status=DependencyStatus.UNKNOWN,
        error_message=f"Unknown backend: {backend}",
    )


def format_missing_dependency_message(result: DependencyCheckResult) -> str:
    """
    Format a user-friendly error message for a missing dependency.

    Args:
        result: DependencyCheckResult with missing status

    Returns:
        Formatted error message with installation instructions
    """
    if result.is_available:
        return f"{result.name} is installed at {result.path}"

    border = "=" * 70
    message = f"\n{border}\n"
    message += f"  Missing Dependency: {result.name}\n"
    message += f"{border}\n\n"

    if result.error_message:
        message += f"{result.error_message}\n\n"

    if result.install_instructions:
        message += f"{result.install_instructions}\n"

    message += f"\n{border}\n"

    return message


def can_auto_install(dependency_name: str) -> bool:
    """
    Check if a dependency can be auto-installed via Homebrew.

    Args:
        dependency_name: Name of the dependency ('ollama', 'homebrew', etc.)

    Returns:
        True if auto-installation is possible (dependency is whitelisted and Homebrew is available)
    """
    # Normalize dependency name for case-insensitive comparison
    normalized_name = dependency_name.lower().strip()

    # Special case: Homebrew itself requires manual installation
    if normalized_name == "homebrew":
        return False

    # Check if dependency is in the allowed whitelist
    if normalized_name not in ALLOWED_AUTO_INSTALL_DEPENDENCIES:
        return False

    # Check if Homebrew is available for installing dependencies
    homebrew = check_homebrew()
    return homebrew.is_available


def auto_install_dependency(dependency_name: str) -> bool:
    """
    Attempt to auto-install a dependency via Homebrew.

    Args:
        dependency_name: Name of the dependency to install

    Returns:
        True if installation succeeded

    Raises:
        RuntimeError: If Homebrew is not available or installation fails
        ValueError: If dependency_name is not in allowed list
        subprocess.TimeoutExpired: If installation times out after 5 minutes
    """
    import re
    import subprocess

    if not can_auto_install(dependency_name):
        raise RuntimeError(
            f"Cannot auto-install {dependency_name} (Homebrew not available)"
        )

    # SECURITY: Whitelist validation - only allow known dependencies
    normalized_name = dependency_name.lower().strip()

    if normalized_name not in ALLOWED_AUTO_INSTALL_DEPENDENCIES:
        raise ValueError(
            f"Security: Cannot auto-install '{dependency_name}' - not in allowed list. "
            f"Allowed: {', '.join(ALLOWED_AUTO_INSTALL_DEPENDENCIES)}"
        )

    # SECURITY: Additional validation - only allow alphanumeric, hyphen, dot
    if not re.match(r"^[a-z0-9\-\.]+$", normalized_name):
        raise ValueError(
            f"Security: Invalid dependency name format: '{dependency_name}'"
        )

    try:
        # Run brew install with validated, whitelisted dependency name
        # check=True will raise CalledProcessError on non-zero exit
        subprocess.run(
            ["brew", "install", normalized_name],
            capture_output=True,
            text=True,
            check=True,
            timeout=300,  # 5 minute timeout to prevent hanging
        )
        # If we reach here, installation succeeded
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to install {dependency_name}: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"Installation of {dependency_name} timed out after 5 minutes"
        ) from e
