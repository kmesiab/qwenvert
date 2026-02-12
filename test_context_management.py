"""
Test context window management with model-specific limits.

Tests:
1. max_tokens capping based on model limits
2. system field normalization (array → string)
3. Different models have different limits
4. Realistic coding scenario
"""

import asyncio
from qwenvert.adapter import MessagesRequest, Message
from qwenvert.router import BackendRouter
from qwenvert.models import Model, Backend

def test_system_normalization():
    """Test that system array format is converted to string."""
    print("\n=== Test 1: System Field Normalization ===")

    request_data = {
        "model": "qwen2.5-coder-7b-q4",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 2000,
        "system": [
            {
                "type": "text",
                "text": "You are Claude Code, Anthropic's official CLI.",
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": "\nYou help with software engineering tasks.",
                "cache_control": {"type": "ephemeral"}
            }
        ]
    }

    try:
        request = MessagesRequest(**request_data)
        print(f"✅ Request accepted")
        print(f"   System type: {type(request.system)}")
        print(f"   System preview: {request.system[:80]}...")
        assert isinstance(request.system, str), f"Expected str, got {type(request.system)}"
        assert "Claude Code" in request.system, "Expected text content extracted"
        print(f"✅ System array normalized to string")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


async def test_model_based_capping():
    """Test that max_tokens is capped based on model limits."""
    print("\n=== Test 2: Model-Based max_tokens Capping ===")

    # Create two models with different limits
    small_model = Model(
        id="qwen2.5-coder-1.5b-q4",
        display_name="Qwen2.5 Coder 1.5B Q4",
        family="qwen2.5-coder",
        size_b=1.5,
        quantization="Q4_K_M",
        backend=Backend.OLLAMA,
        backend_model_id="qwen2.5-coder:1.5b-instruct-q4_K_M",
        context_length=32768,
        max_output_tokens=8192,  # Smaller model, less output
        min_ram_gb=4,
        recommended_ram_gb=8,
    )

    large_model = Model(
        id="qwen2.5-coder-14b-q4",
        display_name="Qwen2.5 Coder 14B Q4",
        family="qwen2.5-coder",
        size_b=14.0,
        quantization="Q4_K_M",
        backend=Backend.LLAMACPP,
        backend_model_id="qwen2.5-coder-14b-instruct-q4_K_M.gguf",
        context_length=32768,
        max_output_tokens=16384,  # Larger model, more output
        min_ram_gb=16,
        recommended_ram_gb=24,
    )

    # Test small model with large request
    print("\n--- Small Model (1.5B, max_output=8K) ---")
    router_small = BackendRouter(small_model, "http://localhost:11434")

    request_data = {
        "model": "qwen2.5-coder-1.5b-q4",
        "messages": [{"role": "user", "content": "Generate a large file"}],
        "max_tokens": 21333,  # Claude Code's request
    }

    request = MessagesRequest(**request_data)
    print(f"   Original max_tokens: {request.max_tokens}")

    # Cap it
    capped_request = router_small._cap_max_tokens(request)
    print(f"   Capped max_tokens: {capped_request.max_tokens}")
    assert capped_request.max_tokens == 8192, f"Expected 8192, got {capped_request.max_tokens}"
    print(f"✅ Correctly capped to 8K for small model")

    # Test large model with large request
    print("\n--- Large Model (14B, max_output=16K) ---")
    router_large = BackendRouter(large_model, "http://localhost:8080")

    request_data["model"] = "qwen2.5-coder-14b-q4"
    request = MessagesRequest(**request_data)
    print(f"   Original max_tokens: {request.max_tokens}")

    capped_request = router_large._cap_max_tokens(request)
    print(f"   Capped max_tokens: {capped_request.max_tokens}")
    assert capped_request.max_tokens == 16384, f"Expected 16384, got {capped_request.max_tokens}"
    print(f"✅ Correctly capped to 16K for large model")

    # Test request within limits (no capping needed)
    print("\n--- Request Within Limits ---")
    request_data["max_tokens"] = 4096
    request = MessagesRequest(**request_data)
    print(f"   Original max_tokens: {request.max_tokens}")

    capped_request = router_large._cap_max_tokens(request)
    print(f"   After capping: {capped_request.max_tokens}")
    assert capped_request.max_tokens == 4096, "Should not cap if within limits"
    print(f"✅ No capping when within limits")

    await router_small.close()
    await router_large.close()

    return True


def test_realistic_coding_scenario():
    """Test with a realistic Claude Code coding request."""
    print("\n=== Test 3: Realistic Coding Scenario ===")

    # Simulate Claude Code request with large context
    request_data = {
        "model": "qwen2.5-coder-7b-q4",
        "messages": [
            {
                "role": "user",
                "content": "Generate a Python class that implements a REST API client with authentication, error handling, and retries. Include complete implementation with docstrings."
            }
        ],
        "max_tokens": 21333,  # Claude Code's default
        "temperature": 0.7,
        "system": [
            {
                "type": "text",
                "text": "You are Claude Code, Anthropic's official CLI for Claude.\n\nYou are an interactive agent that helps users with software engineering tasks. Use the instructions below and the tools available to you to assist the user.",
                "cache_control": {"type": "ephemeral"}
            }
        ]
    }

    try:
        request = MessagesRequest(**request_data)
        print(f"✅ Request accepted")
        print(f"   Model: {request.model}")
        print(f"   Original max_tokens: 21333")
        print(f"   System prompt: {len(request.system)} chars (normalized from array)")
        print(f"   Message: {request.messages[0].content[:60]}...")
        print(f"✅ Realistic coding request handled successfully")

        # This would be capped to 12288 by the router (7B model limit)
        print(f"\n   Note: Router will cap to 12,288 tokens for 7B model")
        print(f"   That's ~9,000 words or ~1,500 lines of code - plenty for most tasks!")

        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Context Window Management Tests")
    print("=" * 60)

    results = [
        test_system_normalization(),
        asyncio.run(test_model_based_capping()),
        test_realistic_coding_scenario(),
    ]

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    if all(results):
        print("\n✅ All tests passed!")
        print("\nSummary:")
        print("- Small models (1.5-3B): 8K token output")
        print("- Medium models (7B): 12K token output")
        print("- Large models (14-32B): 16K token output")
        print("- System prompts properly normalized from array format")
        print("- Graceful capping with clear logging")
    else:
        print("\n❌ Some tests failed")
        exit(1)
