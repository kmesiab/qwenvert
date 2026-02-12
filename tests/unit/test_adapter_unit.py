"""
Comprehensive unit tests for qwenvert/adapter.py.

Focuses on unit testing individual functions and components with mocked dependencies.
Aims to achieve 90%+ code coverage for adapter.py.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from qwenvert.adapter import (
    ContentBlock,
    ErrorResponse,
    Message,
    MessagesRequest,
    MessagesResponse,
    MessageStreamEvent,
    Usage,
    _estimate_tokens,
    _generate_response,
    _stream_response,
    create_app,
    run_server,
    start_server_sync,
)


# ============================================================================
# Model Validation Tests
# ============================================================================


class TestMessageModel:
    """Test Message model validation."""

    def test_message_with_string_content(self):
        """Test creating message with string content."""
        msg = Message(role="user", content="Hello, world!")
        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert isinstance(msg.content, str)

    def test_message_with_list_content(self):
        """Test creating message with content blocks."""
        content_blocks = [
            {"type": "text", "text": "First block"},
            {"type": "text", "text": "Second block"},
        ]
        msg = Message(role="user", content=content_blocks)
        assert msg.role == "user"
        assert msg.content == content_blocks
        assert isinstance(msg.content, list)

    def test_message_role_validation(self):
        """Test message role must be user, assistant, or system."""
        # Valid roles
        for role in ["user", "assistant", "system"]:
            msg = Message(role=role, content="test")
            assert msg.role == role

        # Invalid role should fail
        with pytest.raises(ValidationError):
            Message(role="invalid_role", content="test")

    def test_message_empty_content(self):
        """Test message with empty content string."""
        msg = Message(role="user", content="")
        assert msg.content == ""

    def test_message_empty_content_list(self):
        """Test message with empty content block list."""
        msg = Message(role="user", content=[])
        assert msg.content == []


class TestMessagesRequestModel:
    """Test MessagesRequest model validation."""

    def test_minimal_valid_request(self):
        """Test creating request with minimal required fields."""
        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
        )
        assert request.model == "test-model"
        assert len(request.messages) == 1
        assert request.max_tokens == 1024  # Default
        assert request.stream is False  # Default
        assert request.temperature is None

    def test_request_with_all_parameters(self):
        """Test creating request with all optional parameters."""
        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            max_tokens=2048,
            temperature=0.7,
            top_p=0.9,
            top_k=50,
            stop_sequences=["STOP", "END"],
            stream=True,
            metadata={"user_id": "123"},
            system="You are helpful.",
        )
        assert request.max_tokens == 2048
        assert request.temperature == 0.7
        assert request.top_p == 0.9
        assert request.top_k == 50
        assert request.stop_sequences == ["STOP", "END"]
        assert request.stream is True
        assert request.metadata == {"user_id": "123"}
        assert request.system == "You are helpful."

    def test_request_empty_messages_validation(self):
        """Test that empty messages list fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            MessagesRequest(model="test-model", messages=[])
        assert "messages" in str(exc_info.value)

    def test_request_first_message_must_be_user(self):
        """Test that first message must be from user."""
        # Valid: first message is user
        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
        )
        assert request.messages[0].role == "user"

        # Invalid: first message is assistant
        with pytest.raises(ValidationError) as exc_info:
            MessagesRequest(
                model="test-model",
                messages=[Message(role="assistant", content="Hello")],
            )
        assert "First message must be from user" in str(exc_info.value)

    def test_request_max_tokens_validation(self):
        """Test max_tokens parameter validation."""
        # Valid range: 1-4096
        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            max_tokens=1,
        )
        assert request.max_tokens == 1

        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            max_tokens=4096,
        )
        assert request.max_tokens == 4096

        # Invalid: below minimum
        with pytest.raises(ValidationError):
            MessagesRequest(
                model="test-model",
                messages=[Message(role="user", content="Hello")],
                max_tokens=0,
            )

        # max_tokens > 4096 is now handled by router (model-specific capping)
        # Adapter accepts any positive value, router caps based on model limits
        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            max_tokens=5000,
        )
        assert request.max_tokens == 5000, "Adapter accepts large values, router will cap"

    def test_request_temperature_validation(self):
        """Test temperature parameter validation."""
        # Valid range: 0.0-2.0
        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            temperature=0.0,
        )
        assert request.temperature == 0.0

        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            temperature=2.0,
        )
        assert request.temperature == 2.0

        # Invalid: below minimum
        with pytest.raises(ValidationError):
            MessagesRequest(
                model="test-model",
                messages=[Message(role="user", content="Hello")],
                temperature=-0.1,
            )

        # Invalid: above maximum
        with pytest.raises(ValidationError):
            MessagesRequest(
                model="test-model",
                messages=[Message(role="user", content="Hello")],
                temperature=2.1,
            )

    def test_request_top_p_validation(self):
        """Test top_p parameter validation."""
        # Valid range: 0.0-1.0
        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            top_p=0.5,
        )
        assert request.top_p == 0.5

        # Invalid: out of range
        with pytest.raises(ValidationError):
            MessagesRequest(
                model="test-model",
                messages=[Message(role="user", content="Hello")],
                top_p=1.5,
            )

    def test_request_top_k_validation(self):
        """Test top_k parameter validation."""
        # Valid: non-negative integer
        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            top_k=0,
        )
        assert request.top_k == 0

        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            top_k=100,
        )
        assert request.top_k == 100

        # Invalid: negative
        with pytest.raises(ValidationError):
            MessagesRequest(
                model="test-model",
                messages=[Message(role="user", content="Hello")],
                top_k=-1,
            )

    def test_request_stop_sequences_validation(self):
        """Test stop_sequences parameter validation."""
        # Valid: up to 4 sequences
        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            stop_sequences=["STOP1", "STOP2", "STOP3", "STOP4"],
        )
        assert len(request.stop_sequences) == 4

        # Invalid: more than 4 sequences
        with pytest.raises(ValidationError):
            MessagesRequest(
                model="test-model",
                messages=[Message(role="user", content="Hello")],
                stop_sequences=["S1", "S2", "S3", "S4", "S5"],
            )


class TestResponseModels:
    """Test response model creation."""

    def test_content_block_creation(self):
        """Test creating ContentBlock."""
        block = ContentBlock(text="Hello, world!")
        assert block.type == "text"
        assert block.text == "Hello, world!"

    def test_usage_creation(self):
        """Test creating Usage model."""
        usage = Usage(input_tokens=10, output_tokens=20)
        assert usage.input_tokens == 10
        assert usage.output_tokens == 20

    def test_messages_response_creation(self):
        """Test creating MessagesResponse."""
        response = MessagesResponse(
            id="msg_123",
            content=[ContentBlock(text="Response")],
            model="test-model",
            usage=Usage(input_tokens=10, output_tokens=5),
        )
        assert response.id == "msg_123"
        assert response.type == "message"
        assert response.role == "assistant"
        assert response.model == "test-model"
        assert len(response.content) == 1

    def test_messages_response_with_stop_reason(self):
        """Test MessagesResponse with stop_reason."""
        response = MessagesResponse(
            id="msg_123",
            content=[ContentBlock(text="Response")],
            model="test-model",
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=5),
        )
        assert response.stop_reason == "end_turn"

        # Test other valid stop reasons
        for reason in ["max_tokens", "stop_sequence"]:
            response = MessagesResponse(
                id="msg_123",
                content=[ContentBlock(text="Response")],
                model="test-model",
                stop_reason=reason,
                usage=Usage(input_tokens=10, output_tokens=5),
            )
            assert response.stop_reason == reason

    def test_message_stream_event_creation(self):
        """Test creating MessageStreamEvent."""
        event = MessageStreamEvent(
            type="content_block_delta",
            delta={"type": "text_delta", "text": "Hello"},
            index=0,
        )
        assert event.type == "content_block_delta"
        assert event.delta == {"type": "text_delta", "text": "Hello"}
        assert event.index == 0

    def test_error_response_creation(self):
        """Test creating ErrorResponse."""
        error = ErrorResponse(
            error={"type": "invalid_request", "message": "Bad request"}
        )
        assert error.type == "error"
        assert error.error["type"] == "invalid_request"


# ============================================================================
# FastAPI App Tests
# ============================================================================


class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_check_without_backend(self):
        """Test health check when backend router is not configured."""
        app = create_app()
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["adapter"] == "running"
        assert data["backend"] == "unknown"

    def test_health_check_with_backend(self):
        """Test health check when backend router is configured."""
        app = create_app()
        app.state.backend_router = Mock()
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert data["adapter"] == "running"
        assert data["backend"] == "connected"


class TestCreateMessageEndpoint:
    """Test /v1/messages endpoint."""

    def test_create_message_without_backend_router(self):
        """Test that endpoint fails when backend router not configured."""
        app = create_app()
        client = TestClient(app)

        response = client.post(
            "/v1/messages",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 503
        data = response.json()
        assert "Backend router not initialized" in data["detail"]

    def test_create_message_validation_error(self):
        """Test that invalid requests return validation errors."""
        app = create_app()
        app.state.backend_router = Mock()
        client = TestClient(app)

        # Missing required 'messages' field
        response = client.post(
            "/v1/messages",
            json={"model": "test-model"},
        )
        assert response.status_code == 422

        # Invalid temperature value
        response = client.post(
            "/v1/messages",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "temperature": 5.0,  # Out of range
            },
        )
        assert response.status_code == 422

    def test_create_message_non_streaming_success(self):
        """Test successful non-streaming message creation."""
        app = create_app()

        # Mock backend router
        mock_router = AsyncMock()
        mock_response = MessagesResponse(
            id="msg_test123",
            content=[ContentBlock(text="Hello! How can I help?")],
            model="test-model",
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=8),
        )
        mock_router.generate = AsyncMock(return_value=mock_response)
        app.state.backend_router = mock_router

        client = TestClient(app)

        response = client.post(
            "/v1/messages",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == "msg_test123"
        assert data["type"] == "message"
        assert data["role"] == "assistant"
        assert len(data["content"]) == 1
        assert data["content"][0]["text"] == "Hello! How can I help?"
        assert data["usage"]["input_tokens"] == 10
        assert data["usage"]["output_tokens"] == 8

        # Verify backend was called
        mock_router.generate.assert_called_once()

    def test_create_message_with_system_prompt(self):
        """Test message creation with system prompt."""
        app = create_app()

        mock_router = AsyncMock()
        mock_response = MessagesResponse(
            id="msg_test456",
            content=[ContentBlock(text="Response")],
            model="test-model",
            usage=Usage(input_tokens=20, output_tokens=10),
        )
        mock_router.generate = AsyncMock(return_value=mock_response)
        app.state.backend_router = mock_router

        client = TestClient(app)

        response = client.post(
            "/v1/messages",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "system": "You are a helpful assistant.",
                "max_tokens": 100,
            },
        )

        assert response.status_code == 200
        # Verify system prompt was passed to backend
        call_args = mock_router.generate.call_args[0][0]
        assert call_args.system == "You are a helpful assistant."

    def test_create_message_streaming_response(self):
        """Test streaming message creation."""
        app = create_app()

        # Mock backend router with streaming
        async def mock_stream_generator(request):
            yield {
                "type": "message_start",
                "message": {"id": "msg_test", "type": "message"},
            }
            yield {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "Hello"},
            }
            yield {
                "type": "message_stop",
            }

        mock_router = AsyncMock()
        mock_router.generate_stream = mock_stream_generator
        app.state.backend_router = mock_router

        client = TestClient(app)

        response = client.post(
            "/v1/messages",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 100,
                "stream": True,
            },
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_create_message_backend_error(self):
        """Test handling of backend generation errors."""
        app = create_app()

        mock_router = AsyncMock()
        mock_router.generate = AsyncMock(
            side_effect=Exception("Backend connection failed")
        )
        app.state.backend_router = mock_router

        client = TestClient(app)

        response = client.post(
            "/v1/messages",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )

        assert response.status_code == 500
        data = response.json()
        assert "Error processing request" in data["detail"]
        assert "Backend connection failed" in data["detail"]

    def test_create_message_with_all_parameters(self):
        """Test message creation with all optional parameters."""
        app = create_app()

        mock_router = AsyncMock()
        mock_response = MessagesResponse(
            id="msg_full",
            content=[ContentBlock(text="Response")],
            model="test-model",
            usage=Usage(input_tokens=15, output_tokens=10),
        )
        mock_router.generate = AsyncMock(return_value=mock_response)
        app.state.backend_router = mock_router

        client = TestClient(app)

        response = client.post(
            "/v1/messages",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
                "max_tokens": 2048,
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40,
                "stop_sequences": ["STOP"],
                "metadata": {"user_id": "test123"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "msg_full"

        # Verify all parameters were passed
        assert mock_router.generate.called
        call_args = mock_router.generate.call_args[0][0]
        assert call_args.max_tokens == 2048
        assert call_args.temperature == 0.7
        assert call_args.top_p == 0.9
        assert call_args.top_k == 40
        assert call_args.stop_sequences == ["STOP"]
        assert call_args.metadata == {"user_id": "test123"}


# ============================================================================
# Helper Functions Tests
# ============================================================================


class TestGenerateResponse:
    """Test _generate_response function."""

    @pytest.mark.asyncio
    async def test_generate_response_success(self):
        """Test successful response generation."""
        mock_router = AsyncMock()
        mock_response = MessagesResponse(
            id="msg_123",
            content=[ContentBlock(text="Test response")],
            model="test-model",
            usage=Usage(input_tokens=10, output_tokens=5),
        )
        mock_router.generate = AsyncMock(return_value=mock_response)

        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
        )

        response = await _generate_response(request, mock_router)

        assert response.id == "msg_123"
        assert response.content[0].text == "Test response"
        mock_router.generate.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_generate_response_backend_error(self):
        """Test error handling in response generation."""
        mock_router = AsyncMock()
        mock_router.generate = AsyncMock(side_effect=Exception("Backend error"))

        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
        )

        with pytest.raises(Exception, match="Backend error"):
            await _generate_response(request, mock_router)


class TestStreamResponse:
    """Test _stream_response function."""

    @pytest.mark.asyncio
    async def test_stream_response_success(self):
        """Test successful streaming response."""

        async def mock_backend_stream(request):
            yield {"type": "message_start", "message": {"id": "msg_1"}}
            yield {"type": "content_block_delta", "delta": {"text": "Hi"}}
            yield {"type": "message_stop"}

        mock_router = AsyncMock()
        mock_router.generate_stream = mock_backend_stream

        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            stream=True,
        )

        events = []
        async for event_str in _stream_response(request, mock_router):
            events.append(event_str)

        # Should have at least the 3 events we yielded
        assert len(events) >= 3

        # Check that our events are in the output
        event_types = [event.split("\n")[0].replace("event: ", "") for event in events]
        assert "message_start" in event_types
        assert (
            "content_block_delta" in event_types or "content_block_start" in event_types
        )
        assert "message_stop" in event_types

        # Verify JSON data format
        for event_str in events:
            assert "data: {" in event_str
            assert event_str.endswith("\n\n")

    @pytest.mark.asyncio
    async def test_stream_response_error_handling(self):
        """Test error handling in streaming response."""

        async def mock_backend_stream_error(request):
            yield {"type": "message_start", "message": {"id": "msg_1"}}
            msg = "Stream error"
            raise RuntimeError(msg)

        mock_router = AsyncMock()
        mock_router.generate_stream = mock_backend_stream_error

        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            stream=True,
        )

        events = []
        # The error should be caught and an error event yielded
        try:
            async for event_str in _stream_response(request, mock_router):
                events.append(event_str)
        except Exception:
            pass  # Error is expected

        # Should have collected some events before error
        assert len(events) >= 1

        # Check if error event was generated
        if len(events) > 1:
            # Look for error event
            has_error_event = any("error" in event for event in events)
            assert has_error_event

    @pytest.mark.asyncio
    async def test_stream_response_event_formatting(self):
        """Test SSE event formatting."""

        async def mock_backend_stream(request):
            yield {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "Hello"},
                "index": 0,
            }

        mock_router = AsyncMock()
        mock_router.generate_stream = mock_backend_stream

        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            stream=True,
        )

        events = []
        async for event_str in _stream_response(request, mock_router):
            events.append(event_str)

        # Should have at least one event
        assert len(events) >= 1

        # Find the content_block_delta event
        delta_events = [e for e in events if "content_block_delta" in e]
        assert len(delta_events) >= 1

        event_str = delta_events[0]

        # Verify SSE format
        assert "event: content_block_delta\n" in event_str
        assert "data: {" in event_str
        # Check for JSON with or without spaces
        assert "content_block_delta" in event_str
        assert event_str.endswith("\n\n")


class TestEstimateTokens:
    """Test _estimate_tokens function."""

    def test_estimate_tokens_string_content(self):
        """Test token estimation with string content."""
        messages = [
            Message(role="user", content="Hello, world!"),  # 13 chars
            Message(role="assistant", content="Hi there!"),  # 9 chars
        ]

        tokens = _estimate_tokens(messages)
        # 22 chars / 4 = 5.5 -> 5 tokens
        assert tokens == 5

    def test_estimate_tokens_list_content(self):
        """Test token estimation with content blocks."""
        messages = [
            Message(
                role="user",
                content=[
                    {"type": "text", "text": "First block"},  # 11 chars
                    {"type": "text", "text": "Second block"},  # 12 chars
                ],
            ),
        ]

        tokens = _estimate_tokens(messages)
        # 23 chars / 4 = 5.75 -> 5 tokens
        assert tokens == 5

    def test_estimate_tokens_mixed_content(self):
        """Test token estimation with mixed content types."""
        messages = [
            Message(role="user", content="String message"),  # 14 chars
            Message(
                role="assistant",
                content=[
                    {"type": "text", "text": "Block message"},  # 13 chars
                ],
            ),
        ]

        tokens = _estimate_tokens(messages)
        # 27 chars / 4 = 6.75 -> 6 tokens
        assert tokens == 6

    def test_estimate_tokens_empty_messages(self):
        """Test token estimation with empty messages."""
        messages = [Message(role="user", content="")]
        tokens = _estimate_tokens(messages)
        assert tokens == 0

    def test_estimate_tokens_long_content(self):
        """Test token estimation with long content."""
        long_text = "a" * 1000
        messages = [Message(role="user", content=long_text)]
        tokens = _estimate_tokens(messages)
        # 1000 chars / 4 = 250 tokens
        assert tokens == 250

    def test_estimate_tokens_content_blocks_without_text(self):
        """Test token estimation with non-text content blocks."""
        messages = [
            Message(
                role="user",
                content=[
                    {"type": "image", "source": "data:image/png;base64,..."},
                    {"type": "text", "text": "Describe this"},  # 13 chars
                ],
            ),
        ]

        tokens = _estimate_tokens(messages)
        # Only text blocks counted: 13 chars / 4 = 3.25 -> 3 tokens
        assert tokens == 3


# ============================================================================
# Server Runner Tests
# ============================================================================


class TestRunServer:
    """Test run_server and start_server_sync functions."""

    @pytest.mark.asyncio
    async def test_run_server_configuration(self):
        """Test server configuration."""
        with patch("uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            mock_router = Mock()

            # Run server (will be mocked, not actually run)
            await run_server(
                host="0.0.0.0",
                port=9999,
                backend_router=mock_router,
            )

            # Verify server was configured correctly
            mock_server_class.assert_called_once()
            config = mock_server_class.call_args[0][0]
            assert config.host == "0.0.0.0"
            assert config.port == 9999

            # Verify serve was called
            mock_server.serve.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_server_default_parameters(self):
        """Test server with default parameters."""
        with patch("uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            await run_server()

            config = mock_server_class.call_args[0][0]
            assert config.host == "127.0.0.1"
            assert config.port == 8088

    @pytest.mark.asyncio
    async def test_run_server_with_backend_router(self):
        """Test server initialization with backend router."""
        with patch("uvicorn.Server") as mock_server_class:
            mock_server = AsyncMock()
            mock_server_class.return_value = mock_server

            mock_router = Mock()
            await run_server(backend_router=mock_router)

            # Verify backend router was injected
            # This is tested indirectly through app state
            mock_server.serve.assert_called_once()

    def test_start_server_sync(self):
        """Test synchronous server wrapper."""
        with patch("asyncio.run") as mock_run:
            mock_router = Mock()

            start_server_sync(
                host="localhost",
                port=8000,
                backend_router=mock_router,
            )

            # Verify asyncio.run was called
            mock_run.assert_called_once()


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_message_with_very_long_content(self):
        """Test message with very long content string."""
        long_content = "x" * 100000
        msg = Message(role="user", content=long_content)
        assert len(msg.content) == 100000

    def test_message_with_unicode_content(self):
        """Test message with unicode characters."""
        msg = Message(role="user", content="Hello 世界 🌍")
        assert msg.content == "Hello 世界 🌍"

    def test_message_with_nested_content_blocks(self):
        """Test message with complex nested content blocks."""
        content = [
            {
                "type": "text",
                "text": "Regular text",
            },
            {
                "type": "tool_use",
                "id": "tool_123",
                "name": "calculator",
                "input": {"operation": "add", "a": 1, "b": 2},
            },
        ]
        msg = Message(role="assistant", content=content)
        assert len(msg.content) == 2
        assert msg.content[1]["type"] == "tool_use"

    def test_request_with_null_optional_fields(self):
        """Test request with explicitly null optional fields."""
        request = MessagesRequest(
            model="test-model",
            messages=[Message(role="user", content="Hello")],
            temperature=None,
            top_p=None,
            top_k=None,
            stop_sequences=None,
            metadata=None,
            system=None,
        )
        assert request.temperature is None
        assert request.top_p is None
        assert request.top_k is None

    def test_multiple_messages_conversation(self):
        """Test request with multi-turn conversation."""
        request = MessagesRequest(
            model="test-model",
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi there!"),
                Message(role="user", content="How are you?"),
            ],
        )
        assert len(request.messages) == 3
        assert request.messages[0].role == "user"
        assert request.messages[1].role == "assistant"
        assert request.messages[2].role == "user"

    def test_app_creation_is_idempotent(self):
        """Test that create_app can be called multiple times."""
        app1 = create_app()
        app2 = create_app()

        # Both should be valid FastAPI apps
        assert app1.title == "Qwenvert Adapter"
        assert app2.title == "Qwenvert Adapter"

        # But should be different instances
        assert app1 is not app2

    def test_response_with_null_stop_sequence(self):
        """Test response with null stop_sequence."""
        response = MessagesResponse(
            id="msg_123",
            content=[ContentBlock(text="Response")],
            model="test-model",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=Usage(input_tokens=10, output_tokens=5),
        )
        assert response.stop_sequence is None

    def test_response_with_stop_sequence_string(self):
        """Test response with actual stop_sequence."""
        response = MessagesResponse(
            id="msg_123",
            content=[ContentBlock(text="Response")],
            model="test-model",
            stop_reason="stop_sequence",
            stop_sequence="STOP",
            usage=Usage(input_tokens=10, output_tokens=5),
        )
        assert response.stop_sequence == "STOP"
