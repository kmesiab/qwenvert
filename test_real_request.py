"""
Test qwenvert with a real Claude Code-style request.

This sends the exact format that Claude Code uses, including:
- Large max_tokens (21333)
- System field as array with cache_control
- Realistic system prompt
"""

import httpx
import json

def test_claude_code_request():
    """Send a Claude Code-style request to qwenvert."""

    # Claude Code request format
    request_data = {
        "model": "qwen2.5-coder-7b-q4",
        "messages": [
            {
                "role": "user",
                "content": "Write a simple Python function that calculates fibonacci numbers."
            }
        ],
        "max_tokens": 21333,  # Claude Code's default
        "temperature": 0.7,
        "system": [
            {
                "type": "text",
                "text": "You are Claude Code, Anthropic's official CLI for Claude.\n\nYou are an interactive agent that helps users with software engineering tasks.",
                "cache_control": {"type": "ephemeral"}
            }
        ]
    }

    print("=" * 60)
    print("Testing Claude Code Request Format")
    print("=" * 60)

    print(f"\n📤 Sending request:")
    print(f"   Model: {request_data['model']}")
    print(f"   max_tokens: {request_data['max_tokens']}")
    print(f"   system: array with {len(request_data['system'])} blocks")
    print(f"   message: {request_data['messages'][0]['content'][:60]}...")

    try:
        # Send to qwenvert (assuming it's running on localhost:8088)
        client = httpx.Client(timeout=60.0)
        response = client.post(
            "http://localhost:8088/v1/messages",
            json=request_data
        )

        print(f"\n✅ Response received: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"   Response ID: {data['id']}")
            print(f"   Model: {data['model']}")
            print(f"   Stop reason: {data['stop_reason']}")
            print(f"   Usage: {data['usage']['input_tokens']} input, {data['usage']['output_tokens']} output tokens")

            # Show first part of response
            if data['content']:
                text = data['content'][0]['text']
                preview = text[:200] if len(text) > 200 else text
                print(f"\n📝 Response preview:")
                print(f"   {preview}...")

            print(f"\n✅ SUCCESS: Claude Code format accepted and processed!")
            return True
        else:
            print(f"\n❌ ERROR: {response.status_code}")
            print(f"   {response.text}")
            return False

    except httpx.ConnectError:
        print(f"\n❌ Connection Error: Is qwenvert running on localhost:8088?")
        print(f"\n💡 To start qwenvert:")
        print(f"   qwenvert start")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_claude_code_request()
    exit(0 if success else 1)
