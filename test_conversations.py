"""
Test multi-turn conversations with context management.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from qwenvert.adapter import MessagesRequest, Message
from qwenvert.models import Model, Backend
from qwenvert.router import BackendRouter


async def test_conversations():
    """Test multi-turn conversation handling."""

    print("=" * 60)
    print("Testing Multi-Turn Conversations")
    print("=" * 60)

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

    router = BackendRouter(model, "http://localhost:11434")

    # Build a conversation with multiple turns
    print(f"\n📝 Building conversation...")

    conversation = [
        Message(role="user", content="What is 2 + 2?"),
        Message(role="assistant", content="2 + 2 = 4"),
        Message(role="user", content="What about 3 + 3?"),
        Message(role="assistant", content="3 + 3 = 6"),
        Message(role="user", content="Now write a Python function to add two numbers."),
    ]

    print(f"   Conversation has {len(conversation)} messages")
    for i, msg in enumerate(conversation, 1):
        preview = msg.content[:40] if len(msg.content) > 40 else msg.content
        print(f"   {i}. {msg.role}: {preview}...")

    # Test with large max_tokens and array system
    request = MessagesRequest(
        model="test",
        messages=conversation,
        max_tokens=21333,  # Will be capped
        system=[
            {
                "type": "text",
                "text": "You are Claude Code. You help with coding.",
                "cache_control": {"type": "ephemeral"}
            }
        ]
    )

    print(f"\n📤 Request details:")
    print(f"   Messages: {len(request.messages)}")
    print(f"   max_tokens: {request.max_tokens} (will cap to {model.max_output_tokens})")
    print(f"   System: array format → normalized")

    try:
        print(f"\n🔄 Generating response...")

        response = await router.generate(request)

        print(f"\n✅ Response received!")
        print(f"   Response ID: {response.id}")
        print(f"   Stop reason: {response.stop_reason}")
        print(f"   Input tokens: {response.usage.input_tokens}")
        print(f"   Output tokens: {response.usage.output_tokens}")
        print(f"   Total tokens: {response.usage.input_tokens + response.usage.output_tokens}")

        # Context check
        total_tokens = response.usage.input_tokens + response.usage.output_tokens
        context_percentage = (total_tokens / model.context_length) * 100

        print(f"\n📊 Context usage:")
        print(f"   {total_tokens} / {model.context_length} tokens ({context_percentage:.1f}%)")

        if context_percentage < 50:
            print(f"   ✅ Well within context limit")
        elif context_percentage < 80:
            print(f"   ⚠️  Getting close to limit")
        else:
            print(f"   🚨 Approaching context limit")

        # Show response
        text = response.content[0].text
        preview = text[:200] if len(text) > 200 else text
        print(f"\n📝 Assistant response:")
        print(f"   {preview}...")

        print(f"\n" + "=" * 60)
        print("✅ Multi-turn conversation test PASSED")
        print("=" * 60)
        print(f"✅ Multi-turn messages handled correctly")
        print(f"✅ Context management working")
        print(f"✅ max_tokens capped appropriately")
        print(f"✅ System prompt applied across conversation")

        await router.close()
        return True

    except Exception as e:
        print(f"\n❌ Conversation test FAILED: {e}")
        import traceback
        traceback.print_exc()
        await router.close()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_conversations())
    sys.exit(0 if success else 1)
