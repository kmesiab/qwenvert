"""
Security tests for BackendRouter.

Verifies that router rejects non-localhost backend URLs.
"""

import pytest

from qwenvert.models import Backend, Model
from qwenvert.router import BackendRouter
from qwenvert.security import SecurityValidationError


@pytest.fixture
def test_model():
    """Create test model for router initialization."""
    return Model(
        id="test",
        display_name="Test Model",
        family="test",
        size_b=7.0,
        quantization="Q4_K_M",
        backend=Backend.OLLAMA,
        backend_model_id="test:7b",
        context_length=4096,
        min_ram_gb=8,
        recommended_ram_gb=16,
    )


class TestRouterSecurityValidation:
    """Test that BackendRouter validates backend URLs for security."""

    def test_router_accepts_localhost_backend_url(self, test_model):
        """Should accept valid localhost backend URL."""
        # Should not raise
        router = BackendRouter(test_model, "http://localhost:11434")
        assert router.backend_url == "http://localhost:11434"

    def test_router_accepts_127_0_0_1_backend_url(self, test_model):
        """Should accept 127.0.0.1 backend URL."""
        router = BackendRouter(test_model, "http://127.0.0.1:11434")
        assert router.backend_url == "http://127.0.0.1:11434"

    def test_router_accepts_ipv6_localhost(self, test_model):
        """Should accept IPv6 localhost [::1]."""
        router = BackendRouter(test_model, "http://[::1]:11434")
        assert router.backend_url == "http://[::1]:11434"

    def test_router_rejects_non_localhost_backend_url(self, test_model):
        """Should reject external domain backend URL."""
        with pytest.raises(SecurityValidationError) as exc_info:
            BackendRouter(test_model, "http://example.com:11434")

        error_msg = str(exc_info.value)
        assert "Security violation" in error_msg
        assert "example.com" in error_msg

    def test_router_blocks_external_domain(self, test_model):
        """Should block external API endpoints."""
        with pytest.raises(SecurityValidationError) as exc_info:
            BackendRouter(test_model, "https://api.openai.com")

        assert "Security violation" in str(exc_info.value)

    def test_router_blocks_0_0_0_0(self, test_model):
        """Should reject 0.0.0.0 (binds to all interfaces)."""
        with pytest.raises(SecurityValidationError) as exc_info:
            BackendRouter(test_model, "http://0.0.0.0:11434")

        error_msg = str(exc_info.value)
        assert "Security violation" in error_msg
        assert "0.0.0.0" in error_msg

    def test_router_blocks_lan_ip_addresses(self, test_model):
        """Should reject LAN IP addresses."""
        lan_ips = [
            "http://192.168.1.100:11434",
            "http://10.0.0.5:11434",
            "http://172.16.0.1:11434",
        ]

        for lan_ip in lan_ips:
            with pytest.raises(SecurityValidationError) as exc_info:
                BackendRouter(test_model, lan_ip)

            assert "Security violation" in str(exc_info.value)

    def test_router_validates_url_at_init(self, test_model):
        """Validation should happen at initialization, not later."""
        # This test verifies validation happens synchronously during __init__
        with pytest.raises(SecurityValidationError):
            BackendRouter(test_model, "http://evil.com")

    def test_router_strips_trailing_slash(self, test_model):
        """Router should strip trailing slash from validated URL."""
        router = BackendRouter(test_model, "http://localhost:11434/")
        assert router.backend_url == "http://localhost:11434"
        # Validation should happen before stripping

    def test_router_error_message_helpful(self, test_model):
        """Error message should explain security issue."""
        with pytest.raises(SecurityValidationError) as exc_info:
            BackendRouter(test_model, "http://remote-server:11434")

        error_msg = str(exc_info.value)
        assert "localhost" in error_msg.lower()
        assert "privacy" in error_msg.lower()
        # Should suggest valid alternatives
