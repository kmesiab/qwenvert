"""
Tests for security validation module.

Verifies that security.py correctly validates localhost-only URLs and hosts.
"""

import pytest

from qwenvert.security import (
    ALLOWED_HOSTS,
    SecurityValidationError,
    is_forbidden_host,
    is_localhost_url,
    validate_adapter_host,
    validate_localhost_url,
)


class TestIsLocalhostUrl:
    """Test is_localhost_url() helper function."""

    def test_accepts_localhost_http(self):
        """Should accept http://localhost URLs."""
        assert is_localhost_url("http://localhost:8088")
        assert is_localhost_url("http://localhost:11434")
        assert is_localhost_url("http://localhost")

    def test_accepts_localhost_https(self):
        """Should accept https://localhost URLs."""
        assert is_localhost_url("https://localhost:8088")

    def test_accepts_127_0_0_1(self):
        """Should accept 127.0.0.1 URLs."""
        assert is_localhost_url("http://127.0.0.1:8088")
        assert is_localhost_url("http://127.0.0.1:11434")
        assert is_localhost_url("http://127.0.0.1")

    def test_accepts_ipv6_localhost(self):
        """Should accept IPv6 localhost [::1]."""
        assert is_localhost_url("http://[::1]:8088")
        assert is_localhost_url("http://[::1]")

    def test_rejects_external_domain(self):
        """Should reject external domains."""
        assert not is_localhost_url("http://example.com")
        assert not is_localhost_url("https://api.anthropic.com")
        assert not is_localhost_url("http://google.com:8080")

    def test_rejects_0_0_0_0(self):
        """Should reject 0.0.0.0 (binds to all interfaces)."""
        assert not is_localhost_url("http://0.0.0.0:8088")

    def test_rejects_lan_ips(self):
        """Should reject LAN IP addresses."""
        assert not is_localhost_url("http://192.168.1.100:8088")
        assert not is_localhost_url("http://10.0.0.5:8088")
        assert not is_localhost_url("http://172.16.0.1:8088")

    def test_rejects_empty_string(self):
        """Should reject empty string."""
        assert not is_localhost_url("")

    def test_case_insensitive(self):
        """Should be case-insensitive."""
        assert is_localhost_url("http://LOCALHOST:8088")
        assert is_localhost_url("HTTP://localhost:8088")

    def test_rejects_localhost_subdomain(self):
        """Should reject localhost as subdomain (bypass attack)."""
        # This would bypass substring matching: "localhost" appears in URL
        # but actual host is "localhost.evil.com"
        assert not is_localhost_url("http://localhost.evil.com:8088")
        assert not is_localhost_url("https://localhost.attacker.com/")
        assert not is_localhost_url("http://mylocalhost.com")

    def test_rejects_localhost_in_query_string(self):
        """Should reject localhost in query string (bypass attack)."""
        # This would bypass substring matching: "localhost" appears in URL
        # but actual host is "evil.com"
        assert not is_localhost_url("http://evil.com?redirect=http://localhost")
        assert not is_localhost_url("http://evil.com?url=localhost:8088")
        assert not is_localhost_url("http://attacker.com#localhost")


class TestIsForbiddenHost:
    """Test is_forbidden_host() helper function."""

    def test_detects_0_0_0_0(self):
        """Should detect 0.0.0.0 as forbidden."""
        assert is_forbidden_host("0.0.0.0")

    def test_detects_lan_ips(self):
        """Should detect LAN IPs as forbidden."""
        assert is_forbidden_host("192.168.1.1")
        assert is_forbidden_host("192.168.0.100")
        assert is_forbidden_host("10.0.0.1")
        assert is_forbidden_host("10.255.255.255")
        assert is_forbidden_host("172.16.0.1")
        assert is_forbidden_host("172.31.255.255")

    def test_allows_localhost(self):
        """Should not mark localhost as forbidden."""
        assert not is_forbidden_host("localhost")
        assert not is_forbidden_host("127.0.0.1")
        assert not is_forbidden_host("::1")

    def test_empty_string(self):
        """Should handle empty string."""
        assert not is_forbidden_host("")


class TestValidateLocalhostUrl:
    """Test validate_localhost_url() validation function."""

    def test_accepts_valid_localhost_urls(self):
        """Should accept valid localhost URLs without error."""
        validate_localhost_url("http://localhost:8088")
        validate_localhost_url("http://127.0.0.1:11434")
        validate_localhost_url("http://[::1]:8088")
        # No exception = success

    def test_rejects_external_domain(self):
        """Should reject external domains with SecurityValidationError."""
        with pytest.raises(SecurityValidationError) as exc_info:
            validate_localhost_url("http://example.com")

        assert "Security violation" in str(exc_info.value)
        assert "localhost" in str(exc_info.value).lower()

    def test_rejects_0_0_0_0(self):
        """Should reject 0.0.0.0."""
        with pytest.raises(SecurityValidationError) as exc_info:
            validate_localhost_url("http://0.0.0.0:8088")

        assert "Security violation" in str(exc_info.value)

    def test_rejects_lan_ip(self):
        """Should reject LAN IP addresses."""
        with pytest.raises(SecurityValidationError):
            validate_localhost_url("http://192.168.1.100:8088")

        with pytest.raises(SecurityValidationError):
            validate_localhost_url("http://10.0.0.5:11434")

    def test_rejects_empty_url(self):
        """Should reject empty URL."""
        with pytest.raises(SecurityValidationError) as exc_info:
            validate_localhost_url("")

        assert "cannot be empty" in str(exc_info.value).lower()

    def test_error_message_helpful(self):
        """Error message should explain the security issue."""
        with pytest.raises(SecurityValidationError) as exc_info:
            validate_localhost_url("http://evil.com")

        error_msg = str(exc_info.value)
        assert "Security violation" in error_msg
        assert "privacy" in error_msg.lower()
        assert "localhost" in error_msg.lower()
        assert "http://localhost:8088" in error_msg  # Example


class TestValidateAdapterHost:
    """Test validate_adapter_host() validation function."""

    def test_accepts_valid_hosts(self):
        """Should accept valid localhost hosts."""
        for host in ALLOWED_HOSTS:
            validate_adapter_host(host)
        # No exception = success

    def test_accepts_localhost_case_insensitive(self):
        """Should accept localhost regardless of case."""
        validate_adapter_host("localhost")
        validate_adapter_host("LOCALHOST")
        validate_adapter_host("Localhost")

    def test_rejects_0_0_0_0(self):
        """Should reject 0.0.0.0 (binds to all interfaces)."""
        with pytest.raises(SecurityValidationError) as exc_info:
            validate_adapter_host("0.0.0.0")

        error_msg = str(exc_info.value)
        assert "Security violation" in error_msg
        assert "0.0.0.0" in error_msg
        assert "network" in error_msg.lower() or "internet" in error_msg.lower()

    def test_rejects_lan_ips(self):
        """Should reject LAN IP addresses."""
        with pytest.raises(SecurityValidationError):
            validate_adapter_host("192.168.1.1")

        with pytest.raises(SecurityValidationError):
            validate_adapter_host("10.0.0.1")

    def test_rejects_external_domain(self):
        """Should reject external domain names."""
        with pytest.raises(SecurityValidationError) as exc_info:
            validate_adapter_host("example.com")

        assert "Security violation" in str(exc_info.value)

    def test_rejects_empty_host(self):
        """Should reject empty host."""
        with pytest.raises(SecurityValidationError) as exc_info:
            validate_adapter_host("")

        assert "cannot be empty" in str(exc_info.value).lower()

    def test_error_message_explains_risk(self):
        """Error message should explain why 0.0.0.0 is dangerous."""
        with pytest.raises(SecurityValidationError) as exc_info:
            validate_adapter_host("0.0.0.0")

        error_msg = str(exc_info.value)
        assert "0.0.0.0" in error_msg
        assert "expose" in error_msg.lower()
        assert "network" in error_msg.lower() or "internet" in error_msg.lower()
        assert "privacy" in error_msg.lower()

    def test_error_message_shows_valid_hosts(self):
        """Error message should show valid alternatives."""
        with pytest.raises(SecurityValidationError) as exc_info:
            validate_adapter_host("invalid-host")

        error_msg = str(exc_info.value)
        assert "127.0.0.1" in error_msg
        assert "localhost" in error_msg.lower()
