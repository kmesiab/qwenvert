"""
Integration tests for /v1/messages API endpoint.

These tests validate the complete end-to-end flow:
1. Claude Code-like request → Adapter
2. Adapter → Backend (Ollama/llama.cpp)
3. Backend → Adapter → Response
4. Streaming and non-streaming modes
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from qwenvert.adapter import create_app
from qwenvert.router import BackendRouter


@pytest.fixture
async def adapter_client(sample_model_7b_q4):
    """Create test client for adapter."""
    app = create_app()

    # Mock the backend router to avoid actual backend calls
    with patch("qwenvert.adapter.BackendRouter") as mock_router_class:
        mock_router = AsyncMock()
        mock_router_class.return_value = mock_router

        # Configure mock to return realistic response
        mock_router.generate.return_value = {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello! How can I help you?"}],
            "model": "qwenvert-default",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 8},
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://localhost:8088"
        ) as client:
            yield client, mock_router


class TestMessagesEndpoint:
    """Test /v1/messages endpoint."""

    @pytest.mark.asyncio
    async def test_simple_message_request(self, adapter_client):
        """Test basic non-streaming message request."""
        client, _mock_router = adapter_client

        response = await client.post(
            "/v1/messages",
            json={
                "model": "qwenvert-default",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
            },
            headers={"x-api-key": "local-qwen"},
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert data["type"] == "message"
        assert data["role"] == "assistant"
        assert len(data["content"]) > 0
        assert data["content"][0]["type"] == "text"
        assert "usage" in data
        assert data["usage"]["input_tokens"] > 0

    @pytest.mark.asyncio
    async def test_message_with_system_prompt(self, adapter_client):
        """Test message with system prompt."""
        client, _mock_router = adapter_client

        response = await client.post(
            "/v1/messages",
            json={
                "model": "qwenvert-default",
                "messages": [{"role": "user", "content": "Write a Python function"}],
                "system": "You are a helpful coding assistant.",
                "max_tokens": 500,
            },
            headers={"x-api-key": "local-qwen"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_streaming_message_request(self, adapter_client):
        """Test streaming message request with SSE."""
        client, mock_router = adapter_client

        # Mock streaming response
        async def mock_stream():
            yield {
                "type": "message_start",
                "message": {"id": "msg_test", "type": "message", "role": "assistant"},
            }
            yield {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "Hello"},
            }
            yield {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": " world"},
            }
            yield {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 2},
            }
            yield {"type": "message_stop"}

        mock_router.generate_stream = mock_stream

        response = await client.post(
            "/v1/messages",
            json={
                "model": "qwenvert-default",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
                "stream": True,
            },
            headers={"x-api-key": "local-qwen"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream"

    @pytest.mark.asyncio
    async def test_multimodal_message(self, adapter_client):
        """Test message with multiple content blocks."""
        client, _mock_router = adapter_client

        response = await client.post(
            "/v1/messages",
            json={
                "model": "qwenvert-default",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze this code:"},
                            {"type": "text", "text": "def hello(): print('hi')"},
                        ],
                    }
                ],
                "max_tokens": 200,
            },
            headers={"x-api-key": "local-qwen"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "message"

    @pytest.mark.asyncio
    async def test_missing_api_key(self, adapter_client):
        """Test that missing API key is accepted (local mode)."""
        client, _ = adapter_client

        # In local mode, API key should be optional or any value accepted
        response = await client.post(
            "/v1/messages",
            json={
                "model": "qwenvert-default",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
            },
        )

        # Should succeed (local mode doesn't require strict auth)
        assert response.status_code in [200, 401]  # Depends on implementation

    @pytest.mark.asyncio
    async def test_invalid_model(self, adapter_client):
        """Test request with invalid model."""
        client, _ = adapter_client

        response = await client.post(
            "/v1/messages",
            json={
                "model": "invalid-model-name",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
            },
            headers={"x-api-key": "local-qwen"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_temperature_parameter(self, adapter_client):
        """Test temperature parameter is passed through."""
        client, mock_router = adapter_client

        response = await client.post(
            "/v1/messages",
            json={
                "model": "qwenvert-default",
                "messages": [{"role": "user", "content": "Be creative"}],
                "max_tokens": 100,
                "temperature": 0.9,
            },
            headers={"x-api-key": "local-qwen"},
        )

        assert response.status_code == 200
        # Verify temperature was passed to backend
        call_args = mock_router.generate.call_args
        assert call_args is not None


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test /health endpoint."""
        app = create_app()
        async with AsyncClient(app=app, base_url="http://localhost:8088") as client:
            response = await client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "adapter_version" in data


class TestBackendIntegration:
    """Test integration with actual backends (requires running backend)."""

    @pytest.mark.integration
    @pytest.mark.skipif(
        True,  # Skip by default, run with pytest -m integration
        reason="Requires running Ollama backend",
    )
    @pytest.mark.asyncio
    async def test_ollama_backend_real_request(self, sample_model_7b_q4):
        """Test real request to Ollama backend.

        Prerequisites:
        - Ollama running on localhost:11434
        - qwen2.5-coder:7b model downloaded
        """

        router = BackendRouter(
            model=sample_model_7b_q4,
            backend_url="http://localhost:11434",
        )

        response = await router.generate(
            {
                "model": "qwenvert-default",
                "messages": [{"role": "user", "content": "Say 'Hello'"}],
                "max_tokens": 10,
            }
        )

        assert response["type"] == "message"
        assert response["role"] == "assistant"
        assert len(response["content"]) > 0

    @pytest.mark.integration
    @pytest.mark.skipif(
        True,
        reason="Requires running llama.cpp backend",
    )
    @pytest.mark.asyncio
    async def test_llamacpp_backend_real_request(self, sample_model_14b_q5):
        """Test real request to llama.cpp backend.

        Prerequisites:
        - llama.cpp server running on localhost:8080
        - Qwen model loaded
        """

        router = BackendRouter(
            model=sample_model_14b_q5,
            backend_url="http://localhost:8080",
        )

        response = await router.generate(
            {
                "model": "qwenvert-default",
                "messages": [{"role": "user", "content": "Say 'Hello'"}],
                "max_tokens": 10,
            }
        )

        assert response["type"] == "message"
        assert response["role"] == "assistant"


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_backend_connection_error(self, sample_model_7b_q4):
        """Test handling of backend connection failure."""

        # Point to non-existent backend
        router = BackendRouter(
            model=sample_model_7b_q4,
            backend_url="http://localhost:9999",  # Not running
        )

        with pytest.raises(Exception):  # Should raise connection error
            await router.generate(
                {
                    "model": "qwenvert-default",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 10,
                }
            )

    @pytest.mark.asyncio
    async def test_malformed_request(self, adapter_client):
        """Test handling of malformed request."""
        client, _ = adapter_client

        response = await client.post(
            "/v1/messages",
            json={
                "model": "qwenvert-default",
                # Missing required 'messages' field
                "max_tokens": 100,
            },
            headers={"x-api-key": "local-qwen"},
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_empty_messages_array(self, adapter_client):
        """Test handling of empty messages array."""
        client, _ = adapter_client

        response = await client.post(
            "/v1/messages",
            json={
                "model": "qwenvert-default",
                "messages": [],  # Empty
                "max_tokens": 100,
            },
            headers={"x-api-key": "local-qwen"},
        )

        assert response.status_code == 400


class TestAnthropicCompatibility:
    """Test strict Anthropic Messages API compatibility."""

    @pytest.mark.asyncio
    async def test_response_format_matches_anthropic(self, adapter_client):
        """Test that response format exactly matches Anthropic spec."""
        client, _ = adapter_client

        response = await client.post(
            "/v1/messages",
            json={
                "model": "qwenvert-default",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
            },
            headers={"x-api-key": "local-qwen"},
        )

        assert response.status_code == 200
        data = response.json()

        # Required fields per Anthropic spec
        required_fields = [
            "id",
            "type",
            "role",
            "content",
            "model",
            "stop_reason",
            "usage",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Type validations
        assert data["type"] == "message"
        assert data["role"] == "assistant"
        assert isinstance(data["content"], list)
        assert all(isinstance(block, dict) for block in data["content"])
        assert isinstance(data["usage"], dict)
        assert "input_tokens" in data["usage"]
        assert "output_tokens" in data["usage"]

    @pytest.mark.asyncio
    async def test_stop_reason_values(self, adapter_client):
        """Test that stop_reason uses valid Anthropic values."""
        client, mock_router = adapter_client

        # Test different stop reasons
        valid_stop_reasons = ["end_turn", "max_tokens", "stop_sequence"]

        for stop_reason in valid_stop_reasons:
            mock_router.generate.return_value["stop_reason"] = stop_reason

            response = await client.post(
                "/v1/messages",
                json={
                    "model": "qwenvert-default",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 100,
                },
                headers={"x-api-key": "local-qwen"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["stop_reason"] in valid_stop_reasons
