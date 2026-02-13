"""
Test edge cases and error handling for context management.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from qwenvert.adapter import MessagesRequest, Message
from qwenvert.models import Model, Backend
from qwenvert.router import BackendRouter


async def test_edge_cases():
    """Test various edge cases."""

    print("=" * 60)
    print("Testing Edge Cases")
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
    results = []

    # Test 1: Extremely large max_tokens
    print(f"\n### Test 1: Extremely large max_tokens (100K)")
    try:
        request = MessagesRequest(
            model="test",
            messages=[Message(role="user", content="Hi")],
            max_tokens=100000,  # Ridiculous value
        )
        capped = router._cap_max_tokens(request)
        assert capped.max_tokens == 8192, f"Expected 8192, got {capped.max_tokens}"
        print(f"✅ PASS: 100K capped to {capped.max_tokens}")
        results.append(True)
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(False)

    # Test 2: max_tokens within limits (no capping)
    print(f"\n### Test 2: max_tokens within limits (4096)")
    try:
        request = MessagesRequest(
            model="test",
            messages=[Message(role="user", content="Hi")],
            max_tokens=4096,
        )
        capped = router._cap_max_tokens(request)
        assert capped.max_tokens == 4096, f"Should not cap, got {capped.max_tokens}"
        print(f"✅ PASS: No capping needed, stays at {capped.max_tokens}")
        results.append(True)
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(False)

    # Test 3: Empty system prompt
    print(f"\n### Test 3: Empty/None system prompt")
    try:
        request = MessagesRequest(
            model="test",
            messages=[Message(role="user", content="Hi")],
            max_tokens=100,
            system=None,
        )
        assert request.system is None
        print(f"✅ PASS: None system handled correctly")
        results.append(True)
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(False)

    # Test 4: Multiple system blocks
    print(f"\n### Test 4: Multiple system blocks in array")
    try:
        request = MessagesRequest(
            model="test",
            messages=[Message(role="user", content="Hi")],
            max_tokens=100,
            system=[
                {"type": "text", "text": "Block 1", "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": "Block 2", "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": "Block 3", "cache_control": {"type": "ephemeral"}},
            ]
        )
        assert "Block 1" in request.system
        assert "Block 2" in request.system
        assert "Block 3" in request.system
        print(f"✅ PASS: All 3 blocks extracted and joined")
        print(f"   Result: {request.system[:80]}...")
        results.append(True)
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(False)

    # Test 5: String system prompt (backwards compat)
    print(f"\n### Test 5: String system prompt (backwards compat)")
    try:
        request = MessagesRequest(
            model="test",
            messages=[Message(role="user", content="Hi")],
            max_tokens=100,
            system="You are a helpful assistant."
        )
        assert request.system == "You are a helpful assistant."
        print(f"✅ PASS: String system preserved")
        results.append(True)
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(False)

    # Test 6: Real inference with edge case values
    print(f"\n### Test 6: Real inference with extreme max_tokens")
    try:
        request = MessagesRequest(
            model="test",
            messages=[Message(role="user", content="Say 'hello'")],
            max_tokens=50000,  # Very large
            system=[
                {"type": "text", "text": "Be concise.", "cache_control": {"type": "ephemeral"}}
            ]
        )

        response = await router.generate(request)
        assert response is not None
        assert response.content[0].text
        print(f"✅ PASS: Inference succeeded with extreme values")
        print(f"   Response: {response.content[0].text[:60]}...")
        results.append(True)
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append(False)

    await router.close()

    # Summary
    print(f"\n" + "=" * 60)
    print(f"Edge Cases Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"✅ Passed: {passed}/{total}")

    if passed == total:
        print(f"\n✅ ALL EDGE CASES PASSED")
        return True
    else:
        print(f"\n⚠️  Some edge cases failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_edge_cases())
    sys.exit(0 if success else 1)
