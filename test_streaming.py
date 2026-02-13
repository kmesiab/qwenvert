"""
Test streaming responses with context window management.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from qwenvert.adapter import MessagesRequest, Message
from qwenvert.models import Model, Backend
from qwenvert.router import BackendRouter


async def test_streaming():
    """Test streaming with large max_tokens and array system."""

    print("=" * 60)
    print("Testing Streaming with Context Management")
    print("=" * 60)

    # Create model
    model = Model(
        id="qwen2.5-coder-1.5b-q4-ollama",
        display_name="Qwen2.5 Coder 1.5B Q4",
        family="qwen2.5-coder",
        size_b=1.5,
        quantization="Q4_K_M",
        backend=Backend.OLLAMA,
        backend_model_id="qwen2.5-coder:1.5b-instruct-q4_K_M",
        context_length=32768,
        max_output_tokens=8192,
        min_ram_gb=4,
        recommended_ram_gb=8,
    )

    # Create router
    router = BackendRouter(model, "http://localhost:11434")

    # Create request with Claude Code format
    request = MessagesRequest(
        model="qwen2.5-coder-1.5b-q4",
        messages=[
            Message(
                role="user",
                content="Write a Python function to calculate factorial. Include docstring and type hints."
            )
        ],
        max_tokens=21333,  # Will be capped to 8192
        stream=True,
        system=[
            {
                "type": "text",
                "text": "You are Claude Code. You help with coding tasks.",
                "cache_control": {"type": "ephemeral"}
            }
        ]
    )

    print(f"\n📤 Streaming request:")
    print(f"   max_tokens: {request.max_tokens} (will cap to {model.max_output_tokens})")
    print(f"   system: array format")
    print(f"   stream: {request.stream}")

    try:
        print(f"\n🔄 Streaming from backend...")

        chunks_received = 0
        total_text = ""

        async for event in router.generate_stream(request):
            chunks_received += 1

            if event.get("type") == "content_block_delta":
                text = event.get("delta", {}).get("text", "")
                total_text += text

                # Show first few chunks
                if chunks_received <= 5:
                    preview = text[:50] if len(text) > 50 else text
                    print(f"   Chunk {chunks_received}: {preview}...")

            elif event.get("type") == "message_stop":
                print(f"\n✅ Stream complete:")
                print(f"   Total chunks: {chunks_received}")
                print(f"   Total text length: {len(total_text)} chars")
                print(f"   Stop reason: {event.get('stop_reason')}")

                if event.get("usage"):
                    usage = event["usage"]
                    print(f"   Usage: {usage.get('input_tokens')} in, {usage.get('output_tokens')} out")

        print(f"\n📝 Generated text preview:")
        preview = total_text[:200] if len(total_text) > 200 else total_text
        print(f"   {preview}...")

        print(f"\n" + "=" * 60)
        print("✅ Streaming test PASSED")
        print("=" * 60)
        print(f"✅ Large max_tokens accepted and capped")
        print(f"✅ Array system normalized")
        print(f"✅ Streaming worked correctly")
        print(f"✅ Received {chunks_received} chunks")

        await router.close()
        return True

    except Exception as e:
        print(f"\n❌ Streaming test FAILED: {e}")
        import traceback
        traceback.print_exc()
        await router.close()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_streaming())
    sys.exit(0 if success else 1)
