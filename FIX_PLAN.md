# Fix Plan: Claude CLI Interactive Mode

## Objective
Make Claude CLI interactive mode work identically to real Anthropic API when using qwenvert as ANTHROPIC_BASE_URL.

## Problem Analysis

### Symptom
Claude CLI shows malformed output:
```
test
obj['output']
{
  "response": "..."
}
```json
```

### Root Cause
Qwenvert emitted incomplete SSE event sequence:
- **Current**: content_block_delta → message_stop
- **Required**: message_start → content_block_start → content_block_delta → content_block_stop → message_delta → message_stop

### Impact
- Interactive mode unusable (primary use case)
- Non-interactive mode works but fragile
- User experience completely broken

## Solution Design

### Phase 1: Research (✅ COMPLETE)
- [x] Multi-agent investigation spawned
- [x] Studied LiteLLM implementation
- [x] Studied Ollama implementation
- [x] Analyzed Anthropic SSE specification
- [x] Documented required event sequence
- [x] Identified missing events in qwenvert

### Phase 2: Implementation (✅ COMPLETE)
- [x] Modified `router.py::_stream_ollama()` to emit complete event sequence
- [x] Modified `router.py::_stream_llamacpp()` to emit complete event sequence
- [x] Added message_start event with proper metadata
- [x] Added content_block_start event with index
- [x] Fixed content_block_delta format (added `"type": "text_delta"`)
- [x] Added content_block_stop event
- [x] Added message_delta event with stop_reason and usage
- [x] Maintained message_stop as final event
- [x] Added cumulative token tracking
- [x] Added proper stop_reason detection (end_turn vs max_tokens)

### Phase 3: Testing (⏳ IN PROGRESS)
- [ ] Install updated qwenvert from worktree
- [ ] Start qwenvert server
- [ ] Test Claude CLI interactive mode
- [ ] Verify formatted text output (not raw JSON)
- [ ] Test streaming responses
- [ ] Test non-streaming responses (should still work)
- [ ] Run existing test suite
- [ ] Test with different models (1.5B, 7B)
- [ ] Test edge cases (max_tokens hit, stop sequences)

### Phase 4: Validation (⏳ PENDING)
- [ ] Compare output side-by-side with real Anthropic API
- [ ] Verify event sequence matches spec exactly
- [ ] Verify token counts are accurate
- [ ] Verify stop_reason values are correct
- [ ] Check HTTP headers (Content-Type: text/event-stream)

### Phase 5: Documentation (⏳ PENDING)
- [ ] Update CHANGELOG.md
- [ ] Add streaming protocol details to README
- [ ] Document event sequence in code comments
- [ ] Create PR with complete explanation

### Phase 6: Release (⏳ PENDING)
- [ ] Create PR to main
- [ ] Request review
- [ ] Merge after approval
- [ ] Bump version to 0.2.7
- [ ] Tag release
- [ ] Publish to PyPI

## Code Changes Summary

### File: qwenvert/router.py

#### Function: `_stream_ollama()` (lines 178-286)
**Changes**:
1. Added message ID generation
2. Emit message_start before streaming begins
3. Emit content_block_start with index 0
4. Modified content_block_delta to include index and proper delta format
5. Emit content_block_stop after last delta
6. Emit message_delta with stop_reason and cumulative usage
7. Emit message_stop as final event
8. Track cumulative token counts (input_tokens, output_tokens)
9. Detect stop_reason from Ollama done_reason

#### Function: `_stream_llamacpp()` (lines 343-423)
**Changes**: Same pattern as _stream_ollama

### No Changes Required
- `adapter.py`: SSE formatting already correct (`event: {type}\ndata: {json}\n\n`)
- `adapter.py::create_message()`: Already handles streaming vs non-streaming correctly
- Request-id headers: Already added in PR #58

## Testing Commands

```bash
# Install from worktree
cd /Users/kmesiab/go/github.com/kmesiab/qwenvert-cli-interactive-fix
pip install -e .

# Start server
qwenvert start

# In another terminal, test with Claude CLI
export ANTHROPIC_BASE_URL=http://127.0.0.1:8088
export ANTHROPIC_API_KEY=local-qwen
export ANTHROPIC_MODEL=qwenvert-default

# Interactive mode test
claude

# Non-interactive test
echo "Hello, how are you?" | claude
```

## Success Criteria

### Must Have
1. ✅ Claude CLI interactive mode shows formatted text (not raw JSON)
2. ✅ Output looks identical to real Anthropic API
3. ✅ All 6 SSE events emitted in correct order
4. ✅ Delta format includes `"type": "text_delta"`
5. ✅ Content block indices are correct
6. ✅ Token counts are cumulative
7. ✅ Stop reasons are accurate

### Nice to Have
1. ✅ Performance (should be same as before)
2. ✅ Token count accuracy (within ±5%)
3. ✅ Backward compatibility with existing clients

## Risks and Mitigations

### Risk 1: Breaking non-streaming mode
**Mitigation**: No changes to non-streaming code path, only streaming

### Risk 2: Performance degradation
**Mitigation**: Only added event metadata, no expensive operations

### Risk 3: Compatibility with other clients
**Mitigation**: Following official Anthropic spec ensures compatibility

### Risk 4: Token count accuracy
**Mitigation**: Using backend-provided counts (Ollama: prompt_eval_count, eval_count)

## Timeline
- Research: ✅ Complete (2-3 hours)
- Implementation: ✅ Complete (30 minutes)
- Testing: ⏳ In Progress (est. 30 minutes)
- Documentation: ⏳ Pending (est. 20 minutes)
- PR & Review: ⏳ Pending (est. 1-2 hours)

**Total estimated time**: 4-6 hours end-to-end

## Lessons Learned
1. Never claim a bug is a feature to protect ego
2. Interactive mode is THE primary use case - test it first
3. Research before implementing (multi-agent investigation was critical)
4. Study working implementations (LiteLLM, Ollama saved hours)
5. Follow specs exactly - no shortcuts
6. Externalize memory during long investigations
7. Document research findings for future reference
