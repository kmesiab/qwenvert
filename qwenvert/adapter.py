"""
Anthropic Messages API HTTP adapter.

FastAPI server implementing /v1/messages endpoint compatible with Claude Code.
Translates Anthropic Messages API requests to backend format.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Dict, List, Literal, Optional, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger(__name__)


# Anthropic Messages API Models (Request)


class Message(BaseModel):
    """Single message in conversation."""

    role: Literal["user", "assistant", "system"]
    content: Union[str, List[Dict[str, Any]]]  # String or content blocks


class MessagesRequest(BaseModel):
    """
    Anthropic Messages API request format.

    Matches the API spec from Claude Code:
    https://docs.anthropic.com/en/api/messages
    """

    model: str = Field(..., description="Model identifier")
    messages: List[Message] = Field(
        ..., min_length=1, description="Conversation messages"
    )
    max_tokens: int = Field(1024, ge=1, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(
        None, ge=0.0, le=2.0, description="Sampling temperature"
    )
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Nucleus sampling")
    top_k: Optional[int] = Field(None, ge=0, description="Top-k sampling")
    stop_sequences: Optional[List[str]] = Field(
        None, max_length=4, description="Stop sequences"
    )
    stream: bool = Field(False, description="Enable streaming responses")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Request metadata")
    system: Optional[Union[str, List[Dict[str, Any]]]] = Field(
        None, description="System prompt (string or array with cache_control)"
    )

    @field_validator("system")
    @classmethod
    def normalize_system(
        cls, v: Optional[Union[str, List[Dict[str, Any]]]]
    ) -> Optional[str]:
        """Convert system field from array format to string."""
        if v is None:
            return None

        # If already a string, return as-is
        if isinstance(v, str):
            return v

        # If array (Claude Code format with cache_control), extract text
        if isinstance(v, list):
            text_parts = []
            for block in v:
                if isinstance(block, dict) and "text" in block:
                    text_parts.append(block["text"])
            result = "\n".join(text_parts)
            logger.debug(f"Converted system array to string ({len(text_parts)} blocks)")
            return result

        return None

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages: List[Message]) -> List[Message]:
        """Ensure messages alternate roles and first is user."""
        if not messages:
            raise ValueError("At least one message required")

        if messages[0].role != "user":
            raise ValueError("First message must be from user")

        # Anthropic doesn't strictly require alternation, but it's good practice
        return messages


# Anthropic Messages API Models (Response)


class ContentBlock(BaseModel):
    """Content block in response."""

    type: Literal["text"] = "text"
    text: str


class Usage(BaseModel):
    """Token usage statistics."""

    input_tokens: int
    output_tokens: int


class MessagesResponse(BaseModel):
    """Anthropic Messages API response format."""

    id: str
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: List[ContentBlock]
    model: str
    stop_reason: Optional[Literal["end_turn", "max_tokens", "stop_sequence"]] = None
    stop_sequence: Optional[str] = None
    usage: Usage


class MessageStreamEvent(BaseModel):
    """Server-Sent Event for streaming responses."""

    type: Literal[
        "message_start",
        "content_block_start",
        "content_block_delta",
        "content_block_stop",
        "message_delta",
        "message_stop",
    ]
    message: Optional[MessagesResponse] = None
    delta: Optional[Dict[str, Any]] = None
    index: Optional[int] = None


# Error Models


class ErrorResponse(BaseModel):
    """Error response format."""

    type: Literal["error"] = "error"
    error: Dict[str, Any]


# FastAPI Application


def create_app() -> FastAPI:
    """
    Create FastAPI application with Anthropic Messages API endpoints.

    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Qwenvert Adapter",
        description="Anthropic Messages API adapter for local Qwen models",
        version="0.1.0",
    )

    # Placeholder for backend router (will be injected)
    app.state.backend_router = None

    @app.get("/health")
    async def health_check():
        """
        Health check endpoint.

        Returns:
            Health status
        """
        return {
            "status": "healthy",
            "adapter": "running",
            "backend": "unknown" if not app.state.backend_router else "connected",
        }

    @app.post("/v1/messages", response_model=MessagesResponse)
    async def create_message(
        request: MessagesRequest, http_request: Request
    ) -> Union[MessagesResponse, StreamingResponse]:
        """
        Create a message (Anthropic Messages API endpoint).

        This is the primary endpoint that Claude Code will call.

        Args:
            request: Anthropic Messages API request
            http_request: FastAPI HTTP request object

        Returns:
            Message response (non-streaming) or StreamingResponse (streaming)

        Raises:
            HTTPException: If backend router not configured or request fails
        """
        if not app.state.backend_router:
            raise HTTPException(
                status_code=503,
                detail="Backend router not initialized. Run qwenvert start first.",
            )

        logger.info(
            f"Received request for model={request.model}, "
            f"messages={len(request.messages)}, "
            f"max_tokens={request.max_tokens}, "
            f"stream={request.stream}"
        )

        try:
            if request.stream:
                # Streaming response
                return StreamingResponse(
                    _stream_response(request, app.state.backend_router),
                    media_type="text/event-stream",
                )
            # Non-streaming response
            response = await _generate_response(request, app.state.backend_router)
            return response

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error processing request: {e!s}",
            )

    return app


async def _generate_response(
    request: MessagesRequest, backend_router: Any
) -> MessagesResponse:
    """
    Generate non-streaming response.

    Args:
        request: Anthropic Messages API request
        backend_router: Backend router instance

    Returns:
        Complete message response

    Raises:
        httpx.HTTPError: If backend request fails
        Exception: For other backend errors
    """
    try:
        # Call backend router to generate response
        response = await backend_router.generate(request)
        logger.debug(
            f"Backend returned response with {response.usage.output_tokens} output tokens"
        )
        return response

    except Exception as e:
        logger.error(f"Backend generation failed: {e}", exc_info=True)
        raise


async def _stream_response(
    request: MessagesRequest, backend_router: Any
) -> AsyncIterator[str]:
    """
    Generate streaming response (Server-Sent Events).

    Args:
        request: Anthropic Messages API request
        backend_router: Backend router instance

    Yields:
        SSE-formatted event strings

    Raises:
        httpx.HTTPError: If backend request fails
        Exception: For other backend errors
    """
    try:
        # Stream events from backend router
        async for event in backend_router.generate_stream(request):
            # Convert event dict to SSE format
            # Backend router already provides Anthropic-format events
            event_type = event.get("type", "message_delta")

            # Format as Server-Sent Event
            yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"

    except Exception as e:
        logger.error(f"Streaming generation failed: {e}", exc_info=True)
        # Send error event
        error_event = {
            "type": "error",
            "error": {"type": "api_error", "message": str(e)},
        }
        yield f"event: error\ndata: {json.dumps(error_event)}\n\n"
        raise


def _estimate_tokens(messages: List[Message]) -> int:
    """
    Rough estimate of token count for messages.

    Args:
        messages: List of messages

    Returns:
        Estimated token count
    """
    total_chars = 0
    for msg in messages:
        if isinstance(msg.content, str):
            total_chars += len(msg.content)
        elif isinstance(msg.content, list):
            for block in msg.content:
                if "text" in block:
                    total_chars += len(block["text"])

    # Rough estimate: 1 token ≈ 4 characters
    return total_chars // 4


# Server Runner


async def run_server(
    host: str = "127.0.0.1",
    port: int = 8088,
    backend_router: Optional[Any] = None,
):
    """
    Run the FastAPI server.

    Args:
        host: Host to bind to (default: localhost only)
        port: Port to bind to (default: 8088)
        backend_router: Backend router instance to inject

    Example:
        >>> app = create_app()
        >>> app.state.backend_router = my_router
        >>> await run_server(backend_router=my_router)
    """
    import uvicorn

    app = create_app()
    if backend_router:
        app.state.backend_router = backend_router

    logger.info(f"Starting qwenvert adapter on {host}:{port}")

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)
    await server.serve()


# CLI integration (for qwenvert start command)


def start_server_sync(
    host: str = "127.0.0.1",
    port: int = 8088,
    backend_router: Optional[Any] = None,
):
    """
    Synchronous wrapper for running server (for CLI commands).

    Args:
        host: Host to bind to
        port: Port to bind to
        backend_router: Backend router instance
    """
    asyncio.run(run_server(host, port, backend_router))
