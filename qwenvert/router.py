"""
Backend router and response transformer.

Translates Anthropic Messages API requests to backend-specific formats
(Ollama, llama.cpp) and transforms responses back to Anthropic format.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

import httpx

from .adapter import (
    ContentBlock,
    Message,
    MessagesRequest,
    MessagesResponse,
    Usage,
)
from .models import Backend, Model
from .security import validate_localhost_url


if TYPE_CHECKING:
    from collections.abc import AsyncIterator


logger = logging.getLogger(__name__)


class BackendRouter:
    """
    Routes requests to appropriate backend and transforms responses.

    Supports:
    - Ollama (/api/chat, /api/generate)
    - llama.cpp (/completion, /v1/chat/completions)
    """

    def __init__(self, model: Model, backend_url: str) -> None:
        """
        Initialize backend router.

        Args:
            model: Model configuration
            backend_url: Base URL for backend server (e.g., http://localhost:11434)

        Raises:
            SecurityValidationError: If backend_url is not localhost
        """
        # SECURITY: Validate backend URL is localhost-only
        validate_localhost_url(backend_url)
        logger.info(f"Router initialized with validated backend: {backend_url}")

        self.model = model
        self.backend_url = backend_url.rstrip("/")
        self.client = httpx.AsyncClient(
            timeout=300.0
        )  # 5 min timeout for long generations

    def _cap_max_tokens(self, request: MessagesRequest) -> MessagesRequest:
        """
        Cap max_tokens to model's limit.

        Args:
            request: Original request

        Returns:
            Request with capped max_tokens
        """
        if request.max_tokens > self.model.max_output_tokens:
            logger.warning(
                f"max_tokens={request.max_tokens} exceeds model limit "
                f"({self.model.max_output_tokens}), capping to {self.model.max_output_tokens}"
            )
            # Create a copy with capped max_tokens
            request_dict = request.model_dump()
            request_dict["max_tokens"] = self.model.max_output_tokens
            return MessagesRequest(**request_dict)
        return request

    async def generate(self, request: MessagesRequest) -> MessagesResponse:
        """
        Generate response from backend.

        Args:
            request: Anthropic Messages API request

        Returns:
            Anthropic Messages API response

        Raises:
            httpx.HTTPError: If backend request fails
        """
        # Cap max_tokens to model's limit
        request = self._cap_max_tokens(request)

        if self.model.backend == Backend.OLLAMA:
            return await self._generate_ollama(request)
        if self.model.backend == Backend.LLAMACPP:
            return await self._generate_llamacpp(request)
        raise NotImplementedError(f"Backend {self.model.backend} not implemented")

    async def generate_stream(
        self, request: MessagesRequest
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Generate streaming response from backend.

        Args:
            request: Anthropic Messages API request

        Yields:
            Anthropic-format streaming events

        Raises:
            httpx.HTTPError: If backend request fails
        """
        # Cap max_tokens to model's limit
        request = self._cap_max_tokens(request)

        if self.model.backend == Backend.OLLAMA:
            async for event in self._stream_ollama(request):
                yield event
        elif self.model.backend == Backend.LLAMACPP:
            async for event in self._stream_llamacpp(request):
                yield event
        else:
            raise NotImplementedError(f"Backend {self.model.backend} not implemented")

    # Ollama Backend Implementation

    async def _generate_ollama(self, request: MessagesRequest) -> MessagesResponse:
        """Generate response from Ollama backend."""
        # Convert Anthropic messages to Ollama chat format
        ollama_messages = self._anthropic_to_ollama_messages(
            request.messages, request.system
        )

        # Build Ollama request
        ollama_request = {
            "model": self.model.backend_model_id,
            "messages": ollama_messages,
            "stream": False,
            "options": {},
        }

        # Add generation parameters
        if request.max_tokens:
            ollama_request["options"]["num_predict"] = request.max_tokens
        if request.temperature is not None:
            ollama_request["options"]["temperature"] = request.temperature
        if request.top_p is not None:
            ollama_request["options"]["top_p"] = request.top_p
        if request.top_k is not None:
            ollama_request["options"]["top_k"] = request.top_k
        if request.stop_sequences:
            ollama_request["options"]["stop"] = request.stop_sequences

        logger.debug(f"Ollama request: {ollama_request}")

        # Call Ollama API
        response = await self.client.post(
            f"{self.backend_url}/api/chat",
            json=ollama_request,
        )
        response.raise_for_status()

        ollama_response = response.json()
        logger.debug(f"Ollama response: {ollama_response}")

        # Transform to Anthropic format
        return self._ollama_to_anthropic_response(ollama_response, request)

    async def _stream_ollama(
        self, request: MessagesRequest
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream response from Ollama backend."""
        ollama_messages = self._anthropic_to_ollama_messages(
            request.messages, request.system
        )

        ollama_request = {
            "model": self.model.backend_model_id,
            "messages": ollama_messages,
            "stream": True,
            "options": {},
        }

        if request.max_tokens:
            ollama_request["options"]["num_predict"] = request.max_tokens
        if request.temperature is not None:
            ollama_request["options"]["temperature"] = request.temperature
        if request.top_p is not None:
            ollama_request["options"]["top_p"] = request.top_p
        if request.top_k is not None:
            ollama_request["options"]["top_k"] = request.top_k
        if request.stop_sequences:
            ollama_request["options"]["stop"] = request.stop_sequences

        # Generate message ID for Anthropic compatibility
        message_id = f"msg_{uuid.uuid4().hex[:8]}"

        # Emit message_start event (required first event)
        yield {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": request.model,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        }

        # Emit content_block_start event (required before first delta)
        yield {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        }

        # Track cumulative usage stats
        input_tokens = 0
        output_tokens = 0

        async with self.client.stream(
            "POST", f"{self.backend_url}/api/chat", json=ollama_request
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line:
                    import json

                    chunk = json.loads(line)

                    # Ollama streams message chunks
                    if "message" in chunk and "content" in chunk["message"]:
                        yield {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {
                                "type": "text_delta",
                                "text": chunk["message"]["content"],
                            },
                        }

                    # Final chunk indicates completion
                    if chunk.get("done", False):
                        # Update usage stats from final chunk
                        input_tokens = chunk.get("prompt_eval_count", 0)
                        output_tokens = chunk.get("eval_count", 0)

                        # Emit content_block_stop event (required after last delta)
                        yield {
                            "type": "content_block_stop",
                            "index": 0,
                        }

                        # Emit message_delta event with usage (required before message_stop)
                        stop_reason = "end_turn"
                        if chunk.get("done_reason") == "length":
                            stop_reason = "max_tokens"

                        yield {
                            "type": "message_delta",
                            "delta": {
                                "stop_reason": stop_reason,
                                "stop_sequence": None,
                            },
                            "usage": {"output_tokens": output_tokens},
                        }

                        # Emit message_stop event (required final event)
                        yield {
                            "type": "message_stop",
                        }

    def _anthropic_to_ollama_messages(
        self, messages: list[Message], system: str | None = None
    ) -> list[dict[str, str]]:
        """
        Convert Anthropic messages to Ollama chat format.

        Args:
            messages: Anthropic messages
            system: Optional system prompt

        Returns:
            Ollama-format messages
        """
        ollama_messages = []

        # Add system message if provided
        if system:
            ollama_messages.append({"role": "system", "content": system})

        # Convert messages
        for msg in messages:
            content = msg.content
            if isinstance(content, list):
                # Extract text from content blocks
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])
                content = " ".join(text_parts)

            ollama_messages.append({"role": msg.role, "content": content})

        return ollama_messages

    def _ollama_to_anthropic_response(
        self, ollama_response: dict[str, Any], request: MessagesRequest
    ) -> MessagesResponse:
        """
        Transform Ollama response to Anthropic format.

        Args:
            ollama_response: Ollama API response
            request: Original request

        Returns:
            Anthropic Messages API response
        """
        message_id = f"msg_{uuid.uuid4().hex[:8]}"

        # Extract text from Ollama response
        assistant_text = ollama_response.get("message", {}).get("content", "")

        # Determine stop reason
        stop_reason = "end_turn"
        if ollama_response.get("done_reason") == "stop":
            stop_reason = "end_turn"
        elif ollama_response.get("done_reason") == "length":
            stop_reason = "max_tokens"

        return MessagesResponse(
            id=message_id,
            type="message",
            role="assistant",
            content=[ContentBlock(type="text", text=assistant_text)],
            model=request.model,
            stop_reason=stop_reason,
            usage=Usage(
                input_tokens=ollama_response.get("prompt_eval_count", 0),
                output_tokens=ollama_response.get("eval_count", 0),
            ),
        )

    # llama.cpp Backend Implementation

    async def _generate_llamacpp(self, request: MessagesRequest) -> MessagesResponse:
        """Generate response from llama.cpp backend."""
        # Convert to llama.cpp format (uses /completion endpoint)
        prompt = self._anthropic_to_llamacpp_prompt(request.messages, request.system)

        llamacpp_request = {
            "prompt": prompt,
            "n_predict": request.max_tokens or 512,
            "stream": False,
        }

        # Add generation parameters
        if request.temperature is not None:
            llamacpp_request["temperature"] = request.temperature
        if request.top_p is not None:
            llamacpp_request["top_p"] = request.top_p
        if request.top_k is not None:
            llamacpp_request["top_k"] = request.top_k
        if request.stop_sequences:
            llamacpp_request["stop"] = request.stop_sequences

        logger.debug(f"llama.cpp request: {llamacpp_request}")

        # Call llama.cpp API
        response = await self.client.post(
            f"{self.backend_url}/completion",
            json=llamacpp_request,
        )
        response.raise_for_status()

        llamacpp_response = response.json()
        logger.debug(f"llama.cpp response: {llamacpp_response}")

        # Transform to Anthropic format
        return self._llamacpp_to_anthropic_response(llamacpp_response, request)

    async def _stream_llamacpp(
        self, request: MessagesRequest
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream response from llama.cpp backend."""
        prompt = self._anthropic_to_llamacpp_prompt(request.messages, request.system)

        llamacpp_request = {
            "prompt": prompt,
            "n_predict": request.max_tokens or 512,
            "stream": True,
        }

        if request.temperature is not None:
            llamacpp_request["temperature"] = request.temperature
        if request.top_p is not None:
            llamacpp_request["top_p"] = request.top_p
        if request.top_k is not None:
            llamacpp_request["top_k"] = request.top_k
        if request.stop_sequences:
            llamacpp_request["stop"] = request.stop_sequences

        # Generate message ID for Anthropic compatibility
        message_id = f"msg_{uuid.uuid4().hex[:8]}"

        # Emit message_start event (required first event)
        yield {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "content": [],
                "model": request.model,
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        }

        # Emit content_block_start event (required before first delta)
        yield {
            "type": "content_block_start",
            "index": 0,
            "content_block": {"type": "text", "text": ""},
        }

        # Track tokens and stop metadata for final events
        tokens_evaluated = 0
        tokens_predicted = 0
        stop = False
        stopped_limit = False
        stopped_word = False

        async with self.client.stream(
            "POST", f"{self.backend_url}/completion", json=llamacpp_request
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    import json

                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        # Emit content_block_stop event (required after last delta)
                        yield {
                            "type": "content_block_stop",
                            "index": 0,
                        }

                        # Map llama.cpp stop metadata to Anthropic stop_reason
                        stop_reason = "end_turn"
                        if stop:
                            if stopped_limit:
                                stop_reason = "max_tokens"
                            elif stopped_word:
                                stop_reason = "stop_sequence"

                        # Emit message_delta event with usage (required before message_stop)
                        yield {
                            "type": "message_delta",
                            "delta": {
                                "stop_reason": stop_reason,
                                "stop_sequence": None,
                            },
                            "usage": {"output_tokens": tokens_predicted},
                        }

                        # Emit message_stop event (required final event)
                        yield {"type": "message_stop"}
                        break

                    chunk = json.loads(data)

                    if "content" in chunk:
                        yield {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {"type": "text_delta", "text": chunk["content"]},
                        }

                    # Track token counts and stop metadata from each chunk
                    if "tokens_evaluated" in chunk:
                        tokens_evaluated = chunk["tokens_evaluated"]
                    if "tokens_predicted" in chunk:
                        tokens_predicted = chunk["tokens_predicted"]
                    if "stop" in chunk:
                        stop = chunk["stop"]
                    if "stopped_limit" in chunk:
                        stopped_limit = chunk["stopped_limit"]
                    if "stopped_word" in chunk:
                        stopped_word = chunk["stopped_word"]

    def _anthropic_to_llamacpp_prompt(
        self, messages: list[Message], system: str | None = None
    ) -> str:
        """
        Convert Anthropic messages to llama.cpp prompt format.

        llama.cpp uses a single string prompt, so we need to format
        the conversation into a prompt template.

        Args:
            messages: Anthropic messages
            system: Optional system prompt

        Returns:
            Formatted prompt string
        """
        # Use Qwen chat template format
        prompt_parts = []

        if system:
            prompt_parts.append(f"<|im_start|>system\n{system}<|im_end|>")

        for msg in messages:
            content = msg.content
            if isinstance(content, list):
                # Extract text from content blocks
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        text_parts.append(block["text"])
                content = " ".join(text_parts)

            prompt_parts.append(f"<|im_start|>{msg.role}\n{content}<|im_end|>")

        # Add assistant prompt
        prompt_parts.append("<|im_start|>assistant\n")

        return "\n".join(prompt_parts)

    def _llamacpp_to_anthropic_response(
        self, llamacpp_response: dict[str, Any], request: MessagesRequest
    ) -> MessagesResponse:
        """
        Transform llama.cpp response to Anthropic format.

        Args:
            llamacpp_response: llama.cpp API response
            request: Original request

        Returns:
            Anthropic Messages API response
        """
        message_id = f"msg_{uuid.uuid4().hex[:8]}"

        # Extract generated text
        assistant_text = llamacpp_response.get("content", "")

        # Determine stop reason
        stop_reason = "end_turn"
        if llamacpp_response.get("stop", False):
            if llamacpp_response.get("stopped_limit", False):
                stop_reason = "max_tokens"
            elif llamacpp_response.get("stopped_word", False):
                stop_reason = "stop_sequence"

        return MessagesResponse(
            id=message_id,
            type="message",
            role="assistant",
            content=[ContentBlock(type="text", text=assistant_text)],
            model=request.model,
            stop_reason=stop_reason,
            usage=Usage(
                input_tokens=llamacpp_response.get("tokens_evaluated", 0),
                output_tokens=llamacpp_response.get("tokens_predicted", 0),
            ),
        )

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
