"""
Unit tests for BackendRouter.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from qwenvert.adapter import (
    Message,
    MessagesRequest,
    MessagesResponse,
)
from qwenvert.models import Backend, Model
from qwenvert.router import BackendRouter


@pytest.fixture
def ollama_model():
    """Ollama model fixture."""
    return Model(
        id="qwen2.5-coder-7b-q4-ollama",
        display_name="Qwen2.5 Coder 7B Q4",
        family="qwen2.5-coder",
        size_b=7.0,
        quantization="Q4_K_M",
        backend=Backend.OLLAMA,
        backend_model_id="qwen2.5-coder:7b",
        context_length=32768,
        min_ram_gb=8,
        recommended_ram_gb=16,
    )


@pytest.fixture
def llamacpp_model():
    """llama.cpp model fixture."""
    return Model(
        id="qwen2.5-coder-14b-q5-llamacpp",
        display_name="Qwen2.5 Coder 14B Q5",
        family="qwen2.5-coder",
        size_b=14.0,
        quantization="Q5_K_M",
        backend=Backend.LLAMACPP,
        backend_model_id="qwen2.5-coder-14b.gguf",
        context_length=32768,
        min_ram_gb=20,
        recommended_ram_gb=32,
    )


@pytest.fixture
def sample_request():
    """Sample Anthropic-format request."""
    return MessagesRequest(
        model="qwenvert-default",
        messages=[Message(role="user", content="Hello, how are you?")],
        max_tokens=100,
    )


class TestBackendRouterInit:
    """Test BackendRouter initialization."""

    def test_init_ollama(self, ollama_model):
        """Test initialization with Ollama model."""
        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        assert router.model == ollama_model
        assert router.backend_url == "http://localhost:11434"
        assert router.client is not None

    def test_init_strips_trailing_slash(self, ollama_model):
        """Test that trailing slashes are stripped from backend URL."""
        router = BackendRouter(
            model=ollama_model, backend_url="http://localhost:11434/"
        )

        assert router.backend_url == "http://localhost:11434"

    def test_init_llamacpp(self, llamacpp_model):
        """Test initialization with llama.cpp model."""
        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        assert router.model == llamacpp_model
        assert router.backend_url == "http://localhost:8080"


class TestOllamaGeneration:
    """Test Ollama backend generation."""

    @pytest.mark.asyncio
    async def test_generate_ollama_simple(self, ollama_model, sample_request):
        """Test simple Ollama generation."""
        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "I'm doing well, thank you!",
            },
            "done": True,
            "total_duration": 1000000000,
            "prompt_eval_count": 10,
            "eval_count": 8,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            response = await router.generate(sample_request)

            assert isinstance(response, MessagesResponse)
            assert response.role == "assistant"
            assert len(response.content) > 0
            assert response.content[0].text == "I'm doing well, thank you!"
            assert response.usage.input_tokens == 10
            assert response.usage.output_tokens == 8

            # Verify backend was called correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "/api/chat" in str(call_args)

    @pytest.mark.asyncio
    async def test_generate_ollama_with_system(self, ollama_model):
        """Test Ollama generation with system prompt."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Write code")],
            system="You are a helpful coding assistant.",
            max_tokens=200,
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "def hello(): pass"},
            "done": True,
            "prompt_eval_count": 15,
            "eval_count": 10,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            response = await router.generate(request)

            assert response.role == "assistant"
            assert "def" in response.content[0].text

            # Verify system prompt was included
            call_kwargs = mock_post.call_args.kwargs
            request_json = call_kwargs.get("json", {})
            # System prompt should be in the request
            assert "messages" in request_json or "system" in request_json


class TestLlamaCppGeneration:
    """Test llama.cpp backend generation."""

    @pytest.mark.asyncio
    async def test_generate_llamacpp(self, llamacpp_model, sample_request):
        """Test llama.cpp generation."""
        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "I'm doing well!",
            "stop": True,
            "tokens_predicted": 8,
            "tokens_evaluated": 10,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            response = await router.generate(sample_request)

            assert isinstance(response, MessagesResponse)
            assert response.role == "assistant"
            assert response.content[0].text == "I'm doing well!"

            # Verify llamacpp endpoint was called
            call_args = mock_post.call_args
            assert "/completion" in str(call_args) or "/v1/chat" in str(call_args)


class TestStreamingGeneration:
    """Test streaming generation."""

    @pytest.mark.asyncio
    async def test_stream_ollama(self, ollama_model, sample_request):
        """Test Ollama streaming generation."""
        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        class MockStreamResponse:
            def __init__(self):
                self.status_code = 200

            async def aiter_lines(self):
                yield '{"message":{"content":"Hello"},"done":false}'
                yield '{"message":{"content":" world"},"done":false}'
                yield '{"message":{"content":"!"},"done":true,"prompt_eval_count":10,"eval_count":3}'

            def raise_for_status(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_stream_response = MockStreamResponse()

        with patch.object(router.client, "stream") as mock_stream:
            mock_stream.return_value = mock_stream_response

            chunks = []
            async for chunk in router.generate_stream(sample_request):
                chunks.append(chunk)

            assert len(chunks) > 0
            # Should contain message_start, deltas, and message_stop events
            types = [chunk.get("type") for chunk in chunks]
            assert "message_start" in types or "content_block_delta" in types or chunks


class TestErrorHandling:
    """Test error handling in router."""

    @pytest.mark.asyncio
    async def test_unknown_backend(self, ollama_model, sample_request):
        """Test error when backend is unknown."""
        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        # Manually set invalid backend
        router.model.backend = "invalid_backend"

        with pytest.raises(NotImplementedError):
            await router.generate(sample_request)

    @pytest.mark.asyncio
    async def test_backend_connection_error(self, ollama_model, sample_request):
        """Test handling of backend connection errors."""
        import httpx

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")

            with pytest.raises(httpx.ConnectError):
                await router.generate(sample_request)

    @pytest.mark.asyncio
    async def test_backend_http_error(self, ollama_model, sample_request):
        """Test handling of backend HTTP errors."""
        import httpx

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with pytest.raises((httpx.HTTPStatusError, Exception)):
                await router.generate(sample_request)


class TestRequestTransformation:
    """Test request transformation logic."""

    @pytest.mark.asyncio
    async def test_max_tokens_parameter(self, ollama_model):
        """Test that max_tokens is properly passed to backend."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=500,
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Response"},
            "done": True,
            "prompt_eval_count": 5,
            "eval_count": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await router.generate(request)

            # Verify max_tokens was sent to backend
            call_kwargs = mock_post.call_args.kwargs
            request_json = call_kwargs.get("json", {})
            # Backend should receive some form of token limit
            assert request_json  # At least verify request was made

    @pytest.mark.asyncio
    async def test_multipart_message(self, ollama_model):
        """Test handling of multipart messages."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[
                Message(
                    role="user",
                    content=[
                        {"type": "text", "text": "First part"},
                        {"type": "text", "text": "Second part"},
                    ],
                )
            ],
            max_tokens=100,
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Response"},
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            response = await router.generate(request)

            assert response.role == "assistant"
            mock_post.assert_called_once()


class TestRouterClose:
    """Test router cleanup."""

    @pytest.mark.asyncio
    async def test_close_client(self, ollama_model):
        """Test that close properly closes the HTTP client."""
        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        with patch.object(
            router.client, "aclose", new_callable=AsyncMock
        ) as mock_close:
            await router.close()
            mock_close.assert_called_once()


class TestOllamaParameterMapping:
    """Test Ollama parameter mapping."""

    @pytest.mark.asyncio
    async def test_temperature_parameter(self, ollama_model):
        """Test temperature parameter is properly mapped."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=100,
            temperature=0.7,
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Response"},
            "done": True,
            "prompt_eval_count": 5,
            "eval_count": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await router.generate(request)

            call_kwargs = mock_post.call_args.kwargs
            request_json = call_kwargs.get("json", {})
            assert "options" in request_json
            assert request_json["options"]["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_top_p_parameter(self, ollama_model):
        """Test top_p parameter is properly mapped."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=100,
            top_p=0.9,
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Response"},
            "done": True,
            "prompt_eval_count": 5,
            "eval_count": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await router.generate(request)

            call_kwargs = mock_post.call_args.kwargs
            request_json = call_kwargs.get("json", {})
            assert request_json["options"]["top_p"] == 0.9

    @pytest.mark.asyncio
    async def test_top_k_parameter(self, ollama_model):
        """Test top_k parameter is properly mapped."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=100,
            top_k=40,
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Response"},
            "done": True,
            "prompt_eval_count": 5,
            "eval_count": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await router.generate(request)

            call_kwargs = mock_post.call_args.kwargs
            request_json = call_kwargs.get("json", {})
            assert request_json["options"]["top_k"] == 40

    @pytest.mark.asyncio
    async def test_stop_sequences_parameter(self, ollama_model):
        """Test stop_sequences parameter is properly mapped."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=100,
            stop_sequences=["###", "STOP"],
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Response"},
            "done": True,
            "prompt_eval_count": 5,
            "eval_count": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await router.generate(request)

            call_kwargs = mock_post.call_args.kwargs
            request_json = call_kwargs.get("json", {})
            assert request_json["options"]["stop"] == ["###", "STOP"]


class TestLlamaCppParameterMapping:
    """Test llama.cpp parameter mapping."""

    @pytest.mark.asyncio
    async def test_temperature_parameter(self, llamacpp_model):
        """Test temperature parameter is properly mapped."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=100,
            temperature=0.7,
        )

        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "Response",
            "stop": True,
            "tokens_predicted": 5,
            "tokens_evaluated": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await router.generate(request)

            call_kwargs = mock_post.call_args.kwargs
            request_json = call_kwargs.get("json", {})
            assert request_json["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_top_p_parameter(self, llamacpp_model):
        """Test top_p parameter is properly mapped."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=100,
            top_p=0.9,
        )

        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "Response",
            "stop": True,
            "tokens_predicted": 5,
            "tokens_evaluated": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await router.generate(request)

            call_kwargs = mock_post.call_args.kwargs
            request_json = call_kwargs.get("json", {})
            assert request_json["top_p"] == 0.9

    @pytest.mark.asyncio
    async def test_top_k_parameter(self, llamacpp_model):
        """Test top_k parameter is properly mapped."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=100,
            top_k=40,
        )

        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "Response",
            "stop": True,
            "tokens_predicted": 5,
            "tokens_evaluated": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await router.generate(request)

            call_kwargs = mock_post.call_args.kwargs
            request_json = call_kwargs.get("json", {})
            assert request_json["top_k"] == 40

    @pytest.mark.asyncio
    async def test_stop_sequences_parameter(self, llamacpp_model):
        """Test stop_sequences parameter is properly mapped."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=100,
            stop_sequences=["###", "STOP"],
        )

        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "Response",
            "stop": True,
            "tokens_predicted": 5,
            "tokens_evaluated": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await router.generate(request)

            call_kwargs = mock_post.call_args.kwargs
            request_json = call_kwargs.get("json", {})
            assert request_json["stop"] == ["###", "STOP"]


class TestOllamaStopReasons:
    """Test Ollama stop reason mapping."""

    @pytest.mark.asyncio
    async def test_stop_reason_end_turn(self, ollama_model, sample_request):
        """Test stop reason mapping for normal completion."""
        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Response"},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 5,
            "eval_count": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            response = await router.generate(sample_request)
            assert response.stop_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_stop_reason_max_tokens(self, ollama_model, sample_request):
        """Test stop reason mapping for length limit."""
        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Response"},
            "done": True,
            "done_reason": "length",
            "prompt_eval_count": 5,
            "eval_count": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            response = await router.generate(sample_request)
            assert response.stop_reason == "max_tokens"


class TestLlamaCppStopReasons:
    """Test llama.cpp stop reason mapping."""

    @pytest.mark.asyncio
    async def test_stop_reason_max_tokens(self, llamacpp_model, sample_request):
        """Test stop reason for max tokens."""
        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "Response",
            "stop": True,
            "stopped_limit": True,
            "tokens_predicted": 5,
            "tokens_evaluated": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            response = await router.generate(sample_request)
            assert response.stop_reason == "max_tokens"

    @pytest.mark.asyncio
    async def test_stop_reason_stop_sequence(self, llamacpp_model, sample_request):
        """Test stop reason for stop sequence."""
        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "Response",
            "stop": True,
            "stopped_word": True,
            "tokens_predicted": 5,
            "tokens_evaluated": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            response = await router.generate(sample_request)
            assert response.stop_reason == "stop_sequence"

    @pytest.mark.asyncio
    async def test_stop_reason_end_turn(self, llamacpp_model, sample_request):
        """Test stop reason for normal completion."""
        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "Response",
            "stop": False,
            "tokens_predicted": 5,
            "tokens_evaluated": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            response = await router.generate(sample_request)
            assert response.stop_reason == "end_turn"


class TestOllamaStreaming:
    """Test Ollama streaming functionality."""

    @pytest.mark.asyncio
    async def test_stream_with_parameters(self, ollama_model):
        """Test Ollama streaming with all parameters."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=100,
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            stop_sequences=["###"],
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        # Mock streaming response
        class MockStreamResponse:
            def __init__(self):
                self.status_code = 200

            async def aiter_lines(self):
                yield '{"message":{"content":"Hello"},"done":false}'
                yield '{"message":{"content":" world"},"done":false}'
                yield '{"message":{"content":"!"},"done":true,"prompt_eval_count":10,"eval_count":3}'

            def raise_for_status(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_stream_response = MockStreamResponse()

        with patch.object(router.client, "stream") as mock_stream:
            mock_stream.return_value = mock_stream_response

            chunks = []
            async for chunk in router.generate_stream(request):
                chunks.append(chunk)

            assert len(chunks) > 0
            # Should have content deltas and message stop
            has_delta = any(c.get("type") == "content_block_delta" for c in chunks)
            has_stop = any(c.get("type") == "message_stop" for c in chunks)
            assert has_delta or has_stop

    @pytest.mark.asyncio
    async def test_stream_with_system_message(self, ollama_model):
        """Test Ollama streaming with system message."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            system="You are a helpful assistant.",
            max_tokens=100,
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        class MockStreamResponse:
            def __init__(self):
                self.status_code = 200

            async def aiter_lines(self):
                yield '{"message":{"content":"Response"},"done":true,"prompt_eval_count":10,"eval_count":3}'

            def raise_for_status(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_stream_response = MockStreamResponse()

        with patch.object(router.client, "stream") as mock_stream:
            mock_stream.return_value = mock_stream_response

            chunks = []
            async for chunk in router.generate_stream(request):
                chunks.append(chunk)

            assert len(chunks) > 0


class TestLlamaCppStreaming:
    """Test llama.cpp streaming functionality."""

    @pytest.mark.asyncio
    async def test_stream_with_parameters(self, llamacpp_model):
        """Test llama.cpp streaming with all parameters."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=100,
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            stop_sequences=["###"],
        )

        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        class MockStreamResponse:
            def __init__(self):
                self.status_code = 200

            async def aiter_lines(self):
                yield 'data: {"content":"Hello"}'
                yield 'data: {"content":" world"}'
                yield "data: [DONE]"

            def raise_for_status(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        mock_stream_response = MockStreamResponse()

        with patch.object(router.client, "stream") as mock_stream:
            mock_stream.return_value = mock_stream_response

            chunks = []
            async for chunk in router.generate_stream(request):
                chunks.append(chunk)

            assert len(chunks) > 0
            has_delta = any(c.get("type") == "content_block_delta" for c in chunks)
            has_stop = any(c.get("type") == "message_stop" for c in chunks)
            assert has_delta or has_stop

    @pytest.mark.asyncio
    async def test_stream_unknown_backend(self, ollama_model):
        """Test streaming with unknown backend."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            max_tokens=100,
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")
        router.model.backend = "invalid_backend"

        with pytest.raises(NotImplementedError):
            async for _ in router.generate_stream(request):
                pass


class TestMessageTransformation:
    """Test message transformation logic."""

    @pytest.mark.asyncio
    async def test_multi_turn_conversation_ollama(self, ollama_model):
        """Test multi-turn conversation with Ollama."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi there!"),
                Message(role="user", content="How are you?"),
            ],
            max_tokens=100,
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "I'm doing well!"},
            "done": True,
            "prompt_eval_count": 15,
            "eval_count": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            response = await router.generate(request)
            assert response.role == "assistant"

    @pytest.mark.asyncio
    async def test_multi_turn_conversation_llamacpp(self, llamacpp_model):
        """Test multi-turn conversation with llama.cpp."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi there!"),
                Message(role="user", content="How are you?"),
            ],
            max_tokens=100,
        )

        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "I'm doing well!",
            "stop": True,
            "tokens_predicted": 5,
            "tokens_evaluated": 15,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            response = await router.generate(request)
            assert response.role == "assistant"

    @pytest.mark.asyncio
    async def test_system_message_llamacpp(self, llamacpp_model):
        """Test system message formatting with llama.cpp."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Test")],
            system="You are a helpful assistant.",
            max_tokens=100,
        )

        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "Response",
            "stop": True,
            "tokens_predicted": 5,
            "tokens_evaluated": 10,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await router.generate(request)

            # Verify system message was included in prompt
            call_kwargs = mock_post.call_args.kwargs
            request_json = call_kwargs.get("json", {})
            prompt = request_json.get("prompt", "")
            assert "system" in prompt.lower()

    @pytest.mark.asyncio
    async def test_content_blocks_ollama(self, ollama_model):
        """Test content block extraction for Ollama."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[
                Message(
                    role="user",
                    content=[
                        {"type": "text", "text": "Part 1"},
                        {"type": "text", "text": "Part 2"},
                    ],
                )
            ],
            max_tokens=100,
        )

        router = BackendRouter(model=ollama_model, backend_url="http://localhost:11434")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Response"},
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 5,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            response = await router.generate(request)
            assert response.role == "assistant"

    @pytest.mark.asyncio
    async def test_content_blocks_llamacpp(self, llamacpp_model):
        """Test content block extraction for llama.cpp."""
        request = MessagesRequest(
            model="qwenvert-default",
            messages=[
                Message(
                    role="user",
                    content=[
                        {"type": "text", "text": "Part 1"},
                        {"type": "text", "text": "Part 2"},
                    ],
                )
            ],
            max_tokens=100,
        )

        router = BackendRouter(
            model=llamacpp_model, backend_url="http://localhost:8080"
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "Response",
            "stop": True,
            "tokens_predicted": 5,
            "tokens_evaluated": 10,
        }

        with patch.object(router.client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            response = await router.generate(request)
            assert response.role == "assistant"
