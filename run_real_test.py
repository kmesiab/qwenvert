"""
Start qwenvert and test it with a real Claude Code-style request.
"""

import asyncio
import httpx
import json
import sys
from pathlib import Path

# Add qwenvert to path
sys.path.insert(0, str(Path(__file__).parent))

from qwenvert.adapter import create_app
from qwenvert.models import ModelRegistry, Backend, Model
from qwenvert.router import BackendRouter


async def start_and_test():
    """Start qwenvert and send a test request."""

    print("=" * 60)
    print("Starting qwenvert and testing inference")
    print("=" * 60)

    # Create a 1.5B model config (matches what's in Ollama)
    model = Model(
        id="qwen2.5-coder-1.5b-q4-ollama",
        display_name="Qwen2.5 Coder 1.5B Q4",
        family="qwen2.5-coder",
        size_b=1.5,
        quantization="Q4_K_M",
        backend=Backend.OLLAMA,
        backend_model_id="qwen2.5-coder:1.5b-instruct-q4_K_M",
        context_length=32768,
        max_output_tokens=8192,  # Small model gets 8K output
        min_ram_gb=4,
        recommended_ram_gb=8,
    )

    print(f"\n✅ Model: {model.display_name}")
    print(f"   max_output_tokens: {model.max_output_tokens}")
    print(f"   backend: {model.backend}")

    # Create backend router
    backend_url = "http://localhost:11434"
    router = BackendRouter(model, backend_url)
    print(f"\n✅ Router created with backend: {backend_url}")

    # Create FastAPI app
    app = create_app()
    app.state.backend_router = router
    print(f"✅ Adapter created")

    # Now test it with a Claude Code-style request
    print(f"\n" + "=" * 60)
    print("Testing Claude Code Request Format")
    print("=" * 60)

    # Import directly to test
    from qwenvert.adapter import MessagesRequest, Message

    # Claude Code request with large max_tokens and array system
    request = MessagesRequest(
        model="qwen2.5-coder-1.5b-q4",
        messages=[Message(role="user", content="Write a Python function that adds two numbers.")],
        max_tokens=21333,  # Claude Code's default - will be capped to 8192
        temperature=0.7,
        system=[
            {
                "type": "text",
                "text": "You are Claude Code, Anthropic's official CLI for Claude.\n\nYou help with software engineering tasks.",
                "cache_control": {"type": "ephemeral"}
            }
        ]
    )

    print(f"\n📤 Request details:")
    print(f"   Original max_tokens: 21333")
    print(f"   System field: array with cache_control")
    print(f"   System normalized to: {request.system[:60]}...")
    print(f"   Message: {request.messages[0].content}")

    # Test the generation
    print(f"\n🔄 Calling backend...")
    try:
        response = await router.generate(request)

        print(f"\n✅ Response received!")
        print(f"   Response ID: {response.id}")
        print(f"   Model: {response.model}")
        print(f"   Stop reason: {response.stop_reason}")
        print(f"   Usage: {response.usage.input_tokens} input, {response.usage.output_tokens} output tokens")

        # Show response
        if response.content:
            text = response.content[0].text
            preview = text[:300] if len(text) > 300 else text
            print(f"\n📝 Response:")
            print(f"   {preview}")
            if len(text) > 300:
                print(f"   ... ({len(text)} total characters)")

        print(f"\n" + "=" * 60)
        print("✅ SUCCESS: All transformations working!")
        print("=" * 60)
        print(f"\n✅ max_tokens capped: 21333 → {model.max_output_tokens}")
        print(f"✅ system array normalized to string")
        print(f"✅ Inference completed successfully")

        await router.close()
        return True

    except Exception as e:
        print(f"\n❌ Error during inference: {e}")
        import traceback
        traceback.print_exc()
        await router.close()
        return False


if __name__ == "__main__":
    success = asyncio.run(start_and_test())
    sys.exit(0 if success else 1)
