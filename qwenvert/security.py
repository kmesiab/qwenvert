"""
Security validation module for qwenvert.

Enforces core security guarantees:
- Zero external network calls (only localhost/127.0.0.1)
- No data exfiltration
- Localhost-only binding
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# Valid localhost patterns
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "::1",  # IPv6 localhost
]

# Patterns that should be rejected
FORBIDDEN_PATTERNS = [
    "0.0.0.0",  # Binds to all interfaces
    r"192\.168\.\d+\.\d+",  # LAN IPs
    r"10\.\d+\.\d+\.\d+",  # LAN IPs
    r"172\.(1[6-9]|2[0-9]|3[01])\.\d+\.\d+",  # LAN IPs
]


class SecurityValidationError(ValueError):
    """Raised when security validation fails."""

    pass


def is_localhost_url(url: str) -> bool:
    """
    Check if URL points to localhost.

    Args:
        url: URL to check (e.g., "http://localhost:8088")

    Returns:
        True if URL is localhost, False otherwise
    """
    if not url:
        return False

    url_lower = url.lower()

    # Check for allowed hosts
    for host in ALLOWED_HOSTS:
        if f"://{host}" in url_lower or url_lower.startswith(host):
            return True

    # Check for IPv6 localhost with brackets [::1]
    if "://[::1]" in url_lower:
        return True

    return False


def is_forbidden_host(host: str) -> bool:
    """
    Check if host is forbidden (0.0.0.0, LAN IPs, etc).

    Args:
        host: Host to check

    Returns:
        True if host is forbidden, False otherwise
    """
    if not host:
        return False

    # Check forbidden patterns
    for pattern in FORBIDDEN_PATTERNS:
        if re.match(pattern, host):
            return True

    return False


def validate_localhost_url(url: str) -> None:
    """
    Validate that URL is localhost-only.

    Raises:
        SecurityValidationError: If URL is not localhost

    Args:
        url: URL to validate
    """
    if not url:
        raise SecurityValidationError("URL cannot be empty")

    if not is_localhost_url(url):
        raise SecurityValidationError(
            f"Security violation: URL must be localhost/127.0.0.1, got: {url}\n"
            f"Qwenvert only allows localhost connections to protect your privacy.\n"
            f"Valid examples: http://localhost:8088, http://127.0.0.1:11434"
        )


def validate_adapter_host(host: str) -> None:
    """
    Validate that adapter host is localhost-only.

    Raises:
        SecurityValidationError: If host is not localhost

    Args:
        host: Host to validate (e.g., "127.0.0.1")
    """
    if not host:
        raise SecurityValidationError("Host cannot be empty")

    # Check if forbidden
    if is_forbidden_host(host):
        raise SecurityValidationError(
            f"Security violation: Host '{host}' is not allowed.\n"
            f"Binding to '{host}' would expose qwenvert to your network/internet.\n"
            f"Qwenvert only allows localhost binding (127.0.0.1, localhost) to protect your privacy."
        )

    # Check if allowed
    if host.lower() not in ALLOWED_HOSTS:
        raise SecurityValidationError(
            f"Security violation: Host must be localhost/127.0.0.1, got: {host}\n"
            f"Qwenvert only allows localhost binding to protect your privacy.\n"
            f"Valid hosts: {', '.join(ALLOWED_HOSTS)}"
        )
