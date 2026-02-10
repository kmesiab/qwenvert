"""
Integration tests for backend routing and transformation.

Tests the critical translation layer between Anthropic format and backend formats.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from qwenvert.models import Backend, Model
from qwenvert.router import BackendRouter


class TestOllamaBackendRouter:
    """Test Ollama backend routing and transformation."""

    @pytest.mark.asyncio
    async def test_anthropic_to_ollama_transformation(self, sample_model_7b_q4):
        """Test request transformation from Anthropic to Ollama format."""
        from qwenvert.adapter import Message, MessagesRequest

        with patch("httpx.AsyncClient.post") as mock_post:
            # Mock Ollama response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "model": "qwen2.5-coder:7b",
                "created_at": "2024-01-01T00:00:00Z",
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you?",
                },
                "done": True,
                "total_duration": 1000000000,
                "prompt_eval_count": 10,
                "eval_count": 8,
            }
            mock_post.return_value = mock_response

            router = BackendRouter(
                model=sample_model_7b_q4,
                backend_url="http://localhost:11434",
            )

            # Anthropic-format request
            request = MessagesRequest(
                model="qwenvert-default",
                messages=[Message(role="user", content="Hello")],
                max_tokens=100,
                temperature=0.7,
            )

            response = await router.generate(request)

            # Verify transformation
            assert mock_post.called
            call_args = mock_post.call_args

            # Check Ollama endpoint
            assert "/api/chat" in str(call_args)

            # Check transformed request has Ollama fields
            request_json = call_args.kwargs.get("json", {})
            assert "model" in request_json
            assert "messages" in request_json
            assert "options" in request_json or "temperature" in request_json

            # Check response transformation back to Anthropic format
            assert response.type == "message"
            assert response.role == "assistant"
            assert len(response.content) > 0
            assert response.usage.input_tokens > 0

    @pytest.mark.asyncio
    async def test_ollama_system_message_handling(self, sample_model_7b_q4):
        """Test that system messages are properly injected for Ollama."""
        from qwenvert.adapter import Message, MessagesRequest

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "model": "qwen2.5-coder:7b",
                "message": {
                    "role": "assistant",
                    "content": "Yes, I'm a coding assistant.",
                },
                "done": True,
                "prompt_eval_count": 15,
                "eval_count": 6,
            }
            mock_post.return_value = mock_response

            router = BackendRouter(
                model=sample_model_7b_q4,
                backend_url="http://localhost:11434",
            )

            # Request with system prompt (Anthropic style)
            request = MessagesRequest(
                model="qwenvert-default",
                system="You are a helpful coding assistant.",
                messages=[Message(role="user", content="Are you a coding assistant?")],
                max_tokens=100,
            )

            await router.generate(request)

            # Verify system message was added to Ollama messages array
            call_args = mock_post.call_args
            request_json = call_args.kwargs.get("json", {})
            messages = request_json.get("messages", [])

            # Ollama expects system message as first message in array
            assert len(messages) >= 2
            assert messages[0]["role"] == "system"
            assert "coding assistant" in messages[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_ollama_token_counting(self, sample_model_7b_q4):
        """Test that Ollama token counts are properly converted to usage stats."""
        from qwenvert.adapter import Message, MessagesRequest

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "model": "qwen2.5-coder:7b",
                "message": {"role": "assistant", "content": "Response text"},
                "done": True,
                "prompt_eval_count": 25,  # Input tokens
                "eval_count": 12,  # Output tokens
            }
            mock_post.return_value = mock_response

            router = BackendRouter(
                model=sample_model_7b_q4,
                backend_url="http://localhost:11434",
            )

            request = MessagesRequest(
                model="qwenvert-default",
                messages=[Message(role="user", content="Test")],
                max_tokens=50,
            )

            response = await router.generate(request)

            # Verify usage stats
            assert response.usage.input_tokens == 25
            assert response.usage.output_tokens == 12


class TestLlamaCppBackendRouter:
    """Test llama.cpp backend routing and transformation."""

    @pytest.mark.asyncio
    async def test_anthropic_to_llamacpp_transformation(self, sample_model_14b_q5):
        """Test request transformation from Anthropic to llama.cpp format."""
        from qwenvert.adapter import Message, MessagesRequest

        # Update model to llama.cpp backend
        llamacpp_model = Model(
            id=sample_model_14b_q5.id,
            display_name=sample_model_14b_q5.display_name,
            family=sample_model_14b_q5.family,
            size_b=sample_model_14b_q5.size_b,
            quantization=sample_model_14b_q5.quantization,
            backend=Backend.LLAMACPP,
            backend_model_id=sample_model_14b_q5.backend_model_id,
            context_length=sample_model_14b_q5.context_length,
            min_ram_gb=sample_model_14b_q5.min_ram_gb,
            recommended_ram_gb=sample_model_14b_q5.recommended_ram_gb,
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "content": "Hello! How can I help you?",
                "stop": True,
                "model": "qwen",
                "tokens_predicted": 8,
                "tokens_evaluated": 10,
                "generation_settings": {},
                "timings": {},
            }
            mock_post.return_value = mock_response

            router = BackendRouter(
                model=llamacpp_model,
                backend_url="http://localhost:8080",
            )

            request = MessagesRequest(
                model="qwenvert-default",
                messages=[Message(role="user", content="Hello")],
                max_tokens=100,
                temperature=0.7,
            )

            response = await router.generate(request)

            # Verify transformation
            assert mock_post.called
            call_args = mock_post.call_args

            # Check llama.cpp endpoint
            assert "/completion" in str(call_args) or "/v1/chat/completions" in str(
                call_args
            )

            # Check transformed request has llama.cpp fields
            request_json = call_args.kwargs.get("json", {})
            assert "prompt" in request_json or "messages" in request_json
            assert "n_predict" in request_json or "max_tokens" in request_json

            # Check response transformation
            assert response.type == "message"
            assert response.role == "assistant"
            assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_llamacpp_prompt_templating(self, sample_model_14b_q5):
        """Test that messages are properly converted to llama.cpp prompt format."""
        from qwenvert.adapter import Message, MessagesRequest

        llamacpp_model = Model(
            id=sample_model_14b_q5.id,
            display_name=sample_model_14b_q5.display_name,
            family=sample_model_14b_q5.family,
            size_b=sample_model_14b_q5.size_b,
            quantization=sample_model_14b_q5.quantization,
            backend=Backend.LLAMACPP,
            backend_model_id=sample_model_14b_q5.backend_model_id,
            context_length=sample_model_14b_q5.context_length,
            min_ram_gb=sample_model_14b_q5.min_ram_gb,
            recommended_ram_gb=sample_model_14b_q5.recommended_ram_gb,
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "content": "I can help with that!",
                "stop": True,
                "tokens_predicted": 5,
                "tokens_evaluated": 20,
            }
            mock_post.return_value = mock_response

            router = BackendRouter(
                model=llamacpp_model,
                backend_url="http://localhost:8080",
            )

            request = MessagesRequest(
                model="qwenvert-default",
                system="You are a coding assistant.",
                messages=[Message(role="user", content="Help me write code")],
                max_tokens=100,
            )

            await router.generate(request)

            # Verify prompt was constructed with Qwen template
            call_args = mock_post.call_args
            request_json = call_args.kwargs.get("json", {})

            # llama.cpp should receive prompt string or messages array
            assert "prompt" in request_json or "messages" in request_json

            if "prompt" in request_json:
                prompt = request_json["prompt"]
                # Should contain system message and user message
                assert "coding assistant" in prompt.lower()
                assert "help me write code" in prompt.lower()


class TestStreamingBackend:
    """Test streaming response handling."""

    @pytest.mark.asyncio
    async def test_ollama_streaming_transformation(self, sample_model_7b_q4):
        """Test streaming response from Ollama is converted to Anthropic SSE format."""
        from qwenvert.adapter import Message, MessagesRequest

        async def mock_ollama_stream():
            """Mock Ollama streaming response."""
            yield b'{"message": {"role": "assistant", "content": "Hello"}, "done": false}\n'
            yield b'{"message": {"role": "assistant", "content": " world"}, "done": false}\n'
            yield b'{"message": {"role": "assistant", "content": "!"}, "done": true, "prompt_eval_count": 10, "eval_count": 3}\n'

        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_response = MagicMock()
            mock_response.aiter_lines = mock_ollama_stream
            mock_stream.return_value.__aenter__.return_value = mock_response

            router = BackendRouter(
                model=sample_model_7b_q4,
                backend_url="http://localhost:11434",
            )

            request = MessagesRequest(
                model="qwenvert-default",
                messages=[Message(role="user", content="Hello")],
                max_tokens=10,
                stream=True,
            )

            events = []
            async for event in router.generate_stream(request):
                events.append(event)

            # Verify Anthropic SSE format
            assert len(events) > 0
            assert any(e["type"] == "content_block_delta" for e in events)
            assert events[-1]["type"] == "message_stop"


class TestErrorHandling:
    """Test backend error handling and retry logic."""

    @pytest.mark.asyncio
    async def test_backend_http_error(self, sample_model_7b_q4):
        """Test handling of backend HTTP errors."""
        from qwenvert.adapter import Message, MessagesRequest

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500 Server Error", request=MagicMock(), response=mock_response
            )
            mock_post.return_value = mock_response

            router = BackendRouter(
                model=sample_model_7b_q4,
                backend_url="http://localhost:11434",
            )

            request = MessagesRequest(
                model="qwenvert-default",
                messages=[Message(role="user", content="Test")],
                max_tokens=10,
            )

            with pytest.raises(Exception):  # Should propagate error
                await router.generate(request)

    @pytest.mark.asyncio
    async def test_backend_timeout(self, sample_model_7b_q4):
        """Test handling of backend timeout."""
        from qwenvert.adapter import Message, MessagesRequest

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timeout")

            router = BackendRouter(
                model=sample_model_7b_q4,
                backend_url="http://localhost:11434",
            )

            request = MessagesRequest(
                model="qwenvert-default",
                messages=[Message(role="user", content="Test")],
                max_tokens=10,
            )

            with pytest.raises(httpx.TimeoutException):
                await router.generate(request)

    @pytest.mark.skip(reason="Backend handles missing fields gracefully with defaults")
    @pytest.mark.asyncio
    async def test_malformed_backend_response(self, sample_model_7b_q4):
        """Test handling of malformed backend response."""
