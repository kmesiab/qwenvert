# Working Memory: Claude CLI Interactive Mode Fix

## Current Status
**Branch**: `fix/claude-cli-interactive-mode`
**Worktree**: `/Users/kmesiab/go/github.com/kmesiab/qwenvert-cli-interactive-fix/`
**Date**: 2026-02-12

## Problem Statement
Claude CLI interactive mode displays raw JSON fragments instead of formatted text when using qwenvert as ANTHROPIC_BASE_URL:
- Shows `test`, `obj['output']`
- Shows raw JSON blocks with `"response": "..."`
- Shows broken markdown code fences

## Root Cause Identified
Qwenvert's streaming implementation was emitting **incomplete SSE event sequence**:
- ❌ Only emitted: `content_block_delta` → `message_stop`
- ✅ Required: `message_start` → `content_block_start` → `content_block_delta` → `content_block_stop` → `message_delta` → `message_stop`

## Changes Made

### 1. router.py - `_stream_ollama()` (lines 178-286)
**Before**: Only yielded content_block_delta and message_stop events

**After**: Complete Anthropic SSE event sequence:
1. **message_start**: Initial event with message metadata
2. **content_block_start**: Signals start of text content block (index 0)
3. **content_block_delta**: Text chunks with `{"type": "text_delta", "text": "..."}`
4. **content_block_stop**: Signals end of content block (index 0)
5. **message_delta**: Final metadata with stop_reason and output_tokens
6. **message_stop**: Final event signaling completion

**Key improvements**:
- Added message ID generation: `msg_{uuid}`
- Added content block index tracking (index: 0)
- Changed delta format to `{"type": "text_delta", "text": "..."}` (was just `{"text": "..."}`)
- Added cumulative token tracking
- Added stop_reason detection ("end_turn" vs "max_tokens")

### 2. router.py - `_stream_llamacpp()` (lines 343-423)
Applied same complete event sequence for llama.cpp backend

## Testing Plan
1. ✅ Code changes complete
2. ✅ SSE event sequence validation (PASSED)
3. ✅ Event format validation (PASSED - all 6 events in correct order)
4. ✅ Delta format validation (PASSED - includes "type": "text_delta")
5. ✅ Index field validation (PASSED - all content block events have index)
6. ✅ Run existing test suite (455/455 tests PASSED)
7. ⏳ Claude CLI interactive mode test (cannot test nested, but SSE format is correct)
8. ⏳ Create PR with detailed explanation

## Test Results

### SSE Event Sequence Test (✅ PASSED)
```
message_start: 1 ✓
content_block_start: 1 ✓
content_block_delta: 51 ✓ (≥1 required)
content_block_stop: 1 ✓
message_delta: 1 ✓
message_stop: 1 ✓
```

### Event Structure Validation (✅ PASSED)
- First event is message_start ✓
- Last event is message_stop ✓
- Delta events include "type": "text_delta" ✓
- Content block events include index field ✓
- Message start includes proper metadata (id, role, model, usage) ✓
- Message delta includes stop_reason and cumulative usage ✓

### Server Logs (✅ NO ERRORS)
- Server started successfully on port 8088
- Backend connected to Ollama (localhost:11434)
- Model: qwen2.5-coder:1.5b-instruct-q4_K_M
- All requests returned 200 OK

### Test Suite Results (✅ ALL TESTS PASSED)
```
455 tests passed
0 tests failed
4 tests skipped
```

All existing tests continue to pass - no regressions introduced.

## Research References
See `RESEARCH.md` for:
- Anthropic SSE specification analysis
- LiteLLM implementation study
- Ollama proxy implementation study
- Event sequence requirements

## Critical Reminders
- NEVER claim a bug is a feature to protect ego
- Interactive mode is THE primary use case
- Must work exactly like real Anthropic API
- No shortcuts, no "good enough"
- Fix it right or don't ship it

## Next Steps
1. Test with actual Claude CLI
2. Verify output is properly formatted
3. Document test results
4. Create PR only after verified working
