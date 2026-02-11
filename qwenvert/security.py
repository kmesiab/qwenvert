"""
Security validation module for qwenvert.

Enforces core security guarantees:
- Zero external network calls (only localhost/127.0.0.1)
- No data exfiltration
- Localhost-only binding
"""

from __future__ import annotations

import re


# Valid localhost patterns
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "::1",  # IPv6 localhost
]

# Patterns that should be rejected (properly anchored and escaped)
FORBIDDEN_PATTERNS = [
    r"^0\.0\.0\.0$",  # Binds to all interfaces
    r"^192\.168\.\d+\.\d+$",  # LAN IPs (192.168.0.0/16)
    r"^10\.\d+\.\d+\.\d+$",  # LAN IPs (10.0.0.0/8)
    r"^172\.(1[6-9]|2[0-9]|3[01])\.\d+\.\d+$",  # LAN IPs (172.16.0.0/12)
]


class SecurityValidationError(ValueError):
    """Raised when security validation fails."""


def is_localhost_url(url: str) -> bool:
    """
    Check if URL points to localhost.

    Uses proper URL parsing to prevent bypass attacks like:
    - http://localhost.evil.com (subdomain attack)
    - http://evil.com?redirect=http://localhost (query string attack)

    Args:
        url: URL to check (e.g., "http://localhost:8088")

    Returns:
        True if URL is localhost, False otherwise
    """
    if not url:
        return False

    # Use proper URL parsing to extract hostname
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname  # Automatically strips brackets from IPv6

        if not hostname:
            return False

        # Normalize to lowercase for comparison
        hostname_lower = hostname.lower()

        # Check against allowed hosts (exact match only)
        return hostname_lower in [h.lower() for h in ALLOWED_HOSTS]

    except Exception:
        # Invalid URL format
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
    return any(re.match(pattern, host) for pattern in FORBIDDEN_PATTERNS)


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
