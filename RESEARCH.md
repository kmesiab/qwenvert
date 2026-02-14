# Research: Anthropic SSE Streaming Protocol

## Official Anthropic Specification

### Required Event Sequence
All streaming responses MUST emit events in this exact order:

```
1. message_start
2. content_block_start
3. content_block_delta (1 or more)
4. content_block_stop
5. message_delta
6. message_stop
```

### Event Details

#### 1. message_start
```json
{
  "type": "message_start",
  "message": {
    "id": "msg_...",
    "type": "message",
    "role": "assistant",
    "content": [],
    "model": "claude-...",
    "stop_reason": null,
    "stop_sequence": null,
    "usage": {"input_tokens": 0, "output_tokens": 0}
  }
}
```

#### 2. content_block_start
```json
{
  "type": "content_block_start",
  "index": 0,
  "content_block": {
    "type": "text",
    "text": ""
  }
}
```

#### 3. content_block_delta (multiple)
```json
{
  "type": "content_block_delta",
  "index": 0,
  "delta": {
    "type": "text_delta",
    "text": "chunk of text"
  }
}
```

**CRITICAL**: Delta must have `"type": "text_delta"` field, not just `{"text": "..."}`

#### 4. content_block_stop
```json
{
  "type": "content_block_stop",
  "index": 0
}
```

#### 5. message_delta
```json
{
  "type": "message_delta",
  "delta": {
    "stop_reason": "end_turn",  // or "max_tokens" or "stop_sequence"
    "stop_sequence": null
  },
  "usage": {
    "output_tokens": 15  // cumulative count
  }
}
```

**CRITICAL**: Usage must be cumulative, not incremental

#### 6. message_stop
```json
{
  "type": "message_stop"
}
```

## Implementation Requirements

### HTTP Headers
- **Content-Type**: `text/event-stream`
- **Cache-Control**: `no-cache`
- **Connection**: `keep-alive`
- **X-Accel-Buffering**: `no` (disable nginx buffering)

### SSE Format
```
event: message_start
data: {"type":"message_start",...}

event: content_block_delta
data: {"type":"content_block_delta",...}

```

Each event formatted as:
```
event: {event_type}
data: {json_payload}

```
(blank line between events)

## Working Implementations Studied

### LiteLLM (github.com/BerriAI/litellm)
- File: `litellm/proxy/proxy_server.py`
- Correctly implements full event sequence
- Handles multiple content blocks with proper indexing
- Cumulative token tracking

### Ollama (github.com/ollama/ollama)
- File: `server/routes.go`
- Shows how to transform non-Anthropic streaming to Anthropic format
- Proper SSE formatting

### Common Mistakes to Avoid
1. ❌ Emitting only content_block_delta events
2. ❌ Missing message_start or content_block_start
3. ❌ Incorrect delta format (missing `"type": "text_delta"`)
4. ❌ Forgetting content_block_stop before message_delta
5. ❌ Incremental instead of cumulative token counts
6. ❌ Missing index field in content block events
7. ❌ Wrong stop_reason values

## Why This Matters for Claude CLI

Claude CLI parses SSE events to:
1. Detect message boundaries (message_start → message_stop)
2. Track content blocks (content_block_start → content_block_stop)
3. Buffer and display text (content_block_delta)
4. Show token usage (message_delta.usage)
5. Format output properly

**Without complete event sequence**: CLI receives fragments and shows raw JSON or malformed output

**With complete event sequence**: CLI displays formatted text exactly like real Anthropic API

## Test Cases

### Minimal Streaming Response
```
event: message_start
data: {"type":"message_start","message":{...}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":" world"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}}

event: message_stop
data: {"type":"message_stop"}

```

## References
- Anthropic API Docs: https://docs.anthropic.com/en/api/messages-streaming
- Server-Sent Events Spec: https://html.spec.whatwg.org/multipage/server-sent-events.html
- LiteLLM GitHub: https://github.com/BerriAI/litellm
- Ollama GitHub: https://github.com/ollama/ollama
