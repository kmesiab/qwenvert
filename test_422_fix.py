"""
Test script to verify 422 error fix.

Tests:
1. max_tokens > 4096 (should be capped to 4096)
2. system as array with cache_control (should be converted to string)
3. system as string (backwards compatibility)
"""

import sys
import json
from qwenvert.adapter import MessagesRequest, Message

def test_max_tokens_capping():
    """Test that max_tokens > 4096 is capped to 4096."""
    print("\n=== Test 1: max_tokens capping ===")

    request_data = {
        "model": "qwen",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 21333,  # Claude Code sends this
    }

    try:
        request = MessagesRequest(**request_data)
        print(f"✅ Request accepted")
        print(f"   Original max_tokens: 21333")
        print(f"   Capped max_tokens: {request.max_tokens}")
        assert request.max_tokens == 4096, f"Expected 4096, got {request.max_tokens}"
        print(f"✅ max_tokens correctly capped to 4096")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_system_array_format():
    """Test that system array format is converted to string."""
    print("\n=== Test 2: system array format (Claude Code) ===")

    request_data = {
        "model": "qwen",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 1024,
        "system": [
            {
                "type": "text",
                "text": "You are Claude Code, Anthropic's official CLI for Claude.",
                "cache_control": {"type": "ephemeral"}
            },
            {
                "type": "text",
                "text": "\nYou are an interactive CLI tool that helps users.",
                "cache_control": {"type": "ephemeral"}
            }
        ]
    }

    try:
        request = MessagesRequest(**request_data)
        print(f"✅ Request accepted")
        print(f"   System type: {type(request.system)}")
        print(f"   System value: {request.system[:100]}..." if len(request.system) > 100 else f"   System value: {request.system}")
        assert isinstance(request.system, str), f"Expected str, got {type(request.system)}"
        assert "Claude Code" in request.system, "Expected text content to be extracted"
        print(f"✅ system array correctly converted to string")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_system_string_format():
    """Test backwards compatibility with system as string."""
    print("\n=== Test 3: system string format (backwards compat) ===")

    request_data = {
        "model": "qwen",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 1024,
        "system": "You are a helpful assistant."
    }

    try:
        request = MessagesRequest(**request_data)
        print(f"✅ Request accepted")
        print(f"   System type: {type(request.system)}")
        print(f"   System value: {request.system}")
        assert isinstance(request.system, str), f"Expected str, got {type(request.system)}"
        assert request.system == "You are a helpful assistant.", "System string should be unchanged"
        print(f"✅ system string correctly preserved")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_combined():
    """Test max_tokens capping AND system array conversion together."""
    print("\n=== Test 4: combined (max_tokens + system array) ===")

    request_data = {
        "model": "qwen",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 21333,
        "system": [
            {
                "type": "text",
                "text": "You are Claude Code.",
                "cache_control": {"type": "ephemeral"}
            }
        ]
    }

    try:
        request = MessagesRequest(**request_data)
        print(f"✅ Request accepted")
        print(f"   max_tokens: {request.max_tokens} (capped from 21333)")
        print(f"   system type: {type(request.system)}")
        print(f"   system value: {request.system}")
        assert request.max_tokens == 4096, f"Expected 4096, got {request.max_tokens}"
        assert isinstance(request.system, str), f"Expected str, got {type(request.system)}"
        print(f"✅ Both transformations work together")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Testing 422 Error Fix")
    print("=" * 60)

    results = [
        test_max_tokens_capping(),
        test_system_array_format(),
        test_system_string_format(),
        test_combined(),
    ]

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    sys.exit(0 if all(results) else 1)
