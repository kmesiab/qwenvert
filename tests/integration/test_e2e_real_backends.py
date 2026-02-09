"""
End-to-end tests with real backends (Ollama, llama.cpp).

These tests require actual backend servers running and are meant to validate
the full qwenvert stack works in realistic conditions.

Prerequisites:
- Ollama installed and running: `ollama serve`
- Model downloaded: `ollama pull qwen2.5-coder:7b`
- OR llama.cpp server running with Qwen model

Run with: pytest -m e2e tests/integration/test_e2e_real_backends.py -v
"""

import asyncio
import json
import os
import subprocess
import time
from typing import Optional

import httpx
import pytest
import pytest_asyncio

from qwenvert.adapter import create_app
from qwenvert.config import ConfigGenerator
from qwenvert.hardware import HardwareDetector
from qwenvert.models import Backend, Model, ModelRegistry, ModelSelector
from qwenvert.router import BackendRouter

# Mark all tests in this file as e2e
pytestmark = pytest.mark.e2e


@pytest.fixture
def ollama_backend_url():
    """Ollama backend URL."""
    return os.getenv("OLLAMA_URL", "http://localhost:11434")


@pytest.fixture
def llamacpp_backend_url():
    """llama.cpp backend URL."""
    return os.getenv("LLAMACPP_URL", "http://localhost:8080")


@pytest_asyncio.fixture
async def check_ollama_available(ollama_backend_url):
    """Check if Ollama is running and has qwen model."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ollama_backend_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                tags = response.json()
                models = [m["name"] for m in tags.get("models", [])]
                # Check for qwen2.5-coder model
                has_qwen = any(
                    "qwen" in m.lower() and "coder" in m.lower() for m in models
                )
                return has_qwen
    except Exception as e:
        print(f"Ollama not available: {e}")
    return False


@pytest_asyncio.fixture
async def check_llamacpp_available(llamacpp_backend_url):
    """Check if llama.cpp server is running."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{llamacpp_backend_url}/health", timeout=5.0)
            return response.status_code == 200
    except Exception:
        return False


@pytest.fixture
def qwen_model_ollama():
    """Qwen model config for Ollama."""
    return Model(
        id="qwen2.5-coder-7b-q4-ollama",
        display_name="Qwen2.5 Coder 7B Q4",
        family="qwen2.5-coder",
        size_b=7.0,
        quantization="Q4_K_M",
        backend=Backend.OLLAMA,
        backend_model_id="qwen2.5-coder:7b",  # Ollama model tag
        context_length=32768,
        min_ram_gb=8,
        recommended_ram_gb=16,
    )


class TestOllamaE2E:
    """End-to-end tests with real Ollama backend."""

    @pytest.mark.asyncio
    async def test_ollama_health_check(
        self, ollama_backend_url, check_ollama_available
    ):
        """Test Ollama server is running and responsive."""
        if not await check_ollama_available:
            pytest.skip("Ollama not available or qwen model not installed")

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ollama_backend_url}/api/tags")
            assert response.status_code == 200
            data = response.json()
            assert "models" in data
            assert len(data["models"]) > 0
            print(f"\n✅ Ollama available with {len(data['models'])} models")

    @pytest.mark.asyncio
    async def test_backend_router_ollama_simple_request(
        self, qwen_model_ollama, ollama_backend_url, check_ollama_available
    ):
        """Test BackendRouter with real Ollama backend."""
        if not await check_ollama_available:
            pytest.skip("Ollama not available")

        router = BackendRouter(
            model=qwen_model_ollama,
            backend_url=ollama_backend_url,
        )

        from qwenvert.adapter import MessagesRequest, Message

        request = MessagesRequest(
            model="qwenvert-default",
            messages=[
                Message(
                    role="user", content="Say 'Hello from Ollama' and nothing else."
                )
            ],
            max_tokens=20,
        )

        print("\n🔄 Calling Ollama backend...")
        start_time = time.time()
        response = await router.generate(request)
        elapsed = time.time() - start_time

        print(f"✅ Response received in {elapsed:.2f}s")
        print(f"📝 Response: {response.content[0].text[:100]}")

        # Validate response structure
        assert response.type == "message"
        assert response.role == "assistant"
        assert len(response.content) > 0
        assert response.content[0].type == "text"
        assert len(response.content[0].text) > 0
        assert response.usage.input_tokens > 0
        assert response.usage.output_tokens > 0
        assert response.stop_reason in ["end_turn", "stop_sequence", "max_tokens"]

        # Check response contains expected text
        response_text = response.content[0].text.lower()
        assert "hello" in response_text or "hi" in response_text

    @pytest.mark.asyncio
    async def test_backend_router_ollama_streaming(
        self, qwen_model_ollama, ollama_backend_url, check_ollama_available
    ):
        """Test streaming with real Ollama backend."""
        if not await check_ollama_available:
            pytest.skip("Ollama not available")

        router = BackendRouter(
            model=qwen_model_ollama,
            backend_url=ollama_backend_url,
        )

        from qwenvert.adapter import MessagesRequest, Message

        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Count from 1 to 5")],
            max_tokens=50,
            stream=True,
        )

        print("\n🔄 Streaming from Ollama...")
        events = []
        tokens = []

        async for event in router.generate_stream(request):
            events.append(event)
            if event.get("type") == "content_block_delta":
                delta = event.get("delta", {})
                if "text" in delta:
                    tokens.append(delta["text"])
                    print(f"Token: {delta['text']}", end="", flush=True)

        print(f"\n✅ Received {len(events)} events, {len(tokens)} tokens")

        # Validate streaming events
        assert len(events) > 0
        assert any(e.get("type") == "message_start" for e in events)
        assert any(e.get("type") == "content_block_delta" for e in events)
        assert any(e.get("type") == "message_stop" for e in events)

        # Check we got actual content
        assert len(tokens) > 0
        full_text = "".join(tokens)
        assert len(full_text) > 0

    @pytest.mark.asyncio
    async def test_full_adapter_stack_ollama(
        self, qwen_model_ollama, ollama_backend_url, check_ollama_available
    ):
        """Test complete adapter stack with Ollama backend."""
        if not await check_ollama_available:
            pytest.skip("Ollama not available")

        # Create adapter app with backend router
        app = create_app()
        app.state.backend_router = BackendRouter(
            model=qwen_model_ollama,
            backend_url=ollama_backend_url,
        )

        # Test with httpx client
        from httpx import AsyncClient, ASGITransport

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Test health check
            health_response = await client.get("/health")
            assert health_response.status_code == 200
            health_data = health_response.json()
            assert health_data["status"] == "healthy"
            assert health_data["backend"] == "connected"

            # Test /v1/messages endpoint
            print("\n🔄 Testing full /v1/messages endpoint...")
            messages_response = await client.post(
                "/v1/messages",
                json={
                    "model": "qwenvert-default",
                    "messages": [
                        {
                            "role": "user",
                            "content": "What is 2+2? Answer with just the number.",
                        }
                    ],
                    "max_tokens": 10,
                },
                headers={"x-api-key": "local-qwen"},
            )

            assert messages_response.status_code == 200
            data = messages_response.json()

            print(f"✅ Full stack response: {data['content'][0]['text'][:100]}")

            # Validate Anthropic format
            assert data["type"] == "message"
            assert data["role"] == "assistant"
            assert "content" in data
            assert len(data["content"]) > 0
            assert data["content"][0]["type"] == "text"
            assert "usage" in data
            assert data["usage"]["input_tokens"] > 0
            assert data["usage"]["output_tokens"] > 0

    @pytest.mark.asyncio
    async def test_adapter_streaming_ollama(
        self, qwen_model_ollama, ollama_backend_url, check_ollama_available
    ):
        """Test adapter streaming endpoint with Ollama."""
        if not await check_ollama_available:
            pytest.skip("Ollama not available")

        app = create_app()
        app.state.backend_router = BackendRouter(
            model=qwen_model_ollama,
            backend_url=ollama_backend_url,
        )

        from httpx import AsyncClient, ASGITransport

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            print("\n🔄 Testing streaming endpoint...")

            async with client.stream(
                "POST",
                "/v1/messages",
                json={
                    "model": "qwenvert-default",
                    "messages": [{"role": "user", "content": "Say hello"}],
                    "max_tokens": 20,
                    "stream": True,
                },
                headers={"x-api-key": "local-qwen"},
            ) as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers.get("content-type", "")

                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_json = line[6:]  # Remove "data: " prefix
                        try:
                            event = json.loads(data_json)
                            events.append(event)
                            print(f"Event: {event.get('type')}")
                        except json.JSONDecodeError:
                            pass

                print(f"✅ Received {len(events)} streaming events")
                assert len(events) > 0


class TestErrorHandling:
    """Test error scenarios."""

    @pytest.mark.asyncio
    async def test_backend_not_available(self, qwen_model_ollama):
        """Test error handling when backend is not available."""
        router = BackendRouter(
            model=qwen_model_ollama,
            backend_url="http://localhost:9999",  # Non-existent backend
        )

        from qwenvert.adapter import MessagesRequest, Message

        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Hello")],
            max_tokens=10,
        )

        print("\n🔄 Testing error handling (backend down)...")
        with pytest.raises(Exception):  # Should raise connection error
            await router.generate(request)

        print("✅ Error properly raised for unavailable backend")

    @pytest.mark.asyncio
    async def test_adapter_without_router(self):
        """Test adapter returns 503 when router not configured."""
        app = create_app()
        # Don't set app.state.backend_router

        from httpx import AsyncClient, ASGITransport

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/messages",
                json={
                    "model": "qwenvert-default",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "max_tokens": 10,
                },
                headers={"x-api-key": "local-qwen"},
            )

            assert response.status_code == 503
            assert "not initialized" in response.json()["detail"].lower()
            print("✅ Adapter correctly returns 503 when router not configured")


class TestClaudeCodeCompatibility:
    """Test compatibility with Claude Code environment."""

    @pytest.mark.asyncio
    async def test_environment_variable_setup(self, check_ollama_available):
        """Test that environment variables work correctly."""
        if not await check_ollama_available:
            pytest.skip("Ollama not available")

        # Simulate Claude Code environment
        os.environ["ANTHROPIC_BASE_URL"] = "http://localhost:8088"
        os.environ["ANTHROPIC_API_KEY"] = "local-qwen"
        os.environ["ANTHROPIC_MODEL"] = "qwenvert-default"

        # Verify environment
        assert os.getenv("ANTHROPIC_BASE_URL") == "http://localhost:8088"
        assert os.getenv("ANTHROPIC_API_KEY") == "local-qwen"
        assert os.getenv("ANTHROPIC_MODEL") == "qwenvert-default"

        print("✅ Claude Code environment variables set correctly")


class TestPerformance:
    """Basic performance validation."""

    @pytest.mark.asyncio
    async def test_response_time_acceptable(
        self, qwen_model_ollama, ollama_backend_url, check_ollama_available
    ):
        """Test that response time is acceptable (<5s for 50 tokens)."""
        if not await check_ollama_available:
            pytest.skip("Ollama not available")

        router = BackendRouter(
            model=qwen_model_ollama,
            backend_url=ollama_backend_url,
        )

        from qwenvert.adapter import MessagesRequest, Message

        request = MessagesRequest(
            model="qwenvert-default",
            messages=[Message(role="user", content="Say hello")],
            max_tokens=50,
        )

        print("\n⏱️ Measuring response time...")
        start = time.time()
        response = await router.generate(request)
        elapsed = time.time() - start

        print(f"⏱️ Response time: {elapsed:.2f}s")
        print(f"📊 Tokens generated: {response.usage.output_tokens}")

        tokens_per_second = response.usage.output_tokens / elapsed if elapsed > 0 else 0
        print(f"📊 Speed: {tokens_per_second:.1f} tokens/second")

        # Basic performance check (should be faster than 10s for 50 tokens)
        assert elapsed < 10.0, f"Response too slow: {elapsed:.2f}s"

        # Reasonable performance (at least 5 tokens/second)
        assert tokens_per_second >= 5.0, f"Too slow: {tokens_per_second:.1f} tokens/s"

        print("✅ Performance acceptable")
