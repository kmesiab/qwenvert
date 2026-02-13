# Fix for 422 Error: Context Window Management

## Problem

Claude Code was sending requests that qwenvert couldn't handle:

1. **max_tokens too large**: Claude Code sends `max_tokens=21333` but Qwen models only support ≤ 4096
2. **system field format**: Claude Code sends `system` as an array with `cache_control` objects:
   ```json
   "system": [
     {
       "type": "text",
       "text": "You are Claude Code...",
       "cache_control": {"type": "ephemeral"}
     }
   ]
   ```
   But qwenvert expected a simple string.

This caused 422 validation errors and prevented inference.

## Solution

### 1. Accept and Cap max_tokens (adapter.py:44-70)

**Before**: Validation rejected `max_tokens > 4096` with error
```python
max_tokens: int = Field(1024, ge=1, le=4096, ...)
```

**After**: Accept any value, cap to 4096 with warning
```python
max_tokens: int = Field(1024, ge=1, ...)  # No upper limit

@field_validator("max_tokens")
@classmethod
def cap_max_tokens(cls, v: int) -> int:
    """Cap max_tokens to 4096 for Qwen models."""
    if v > 4096:
        logger.warning(f"max_tokens={v} exceeds Qwen limit, capping to 4096")
        return 4096
    return v
```

**Rationale**:
- Qwen models have smaller context windows than Claude
- Graceful degradation is better than hard rejection
- Users get full responses, just capped at model limits

### 2. Normalize system Field (adapter.py:57-95)

**Before**: Only accepted string
```python
system: Optional[str] = Field(None, ...)
```

**After**: Accept string OR array, normalize to string
```python
system: Optional[Union[str, List[Dict[str, Any]]]] = Field(
    None, description="System prompt (string or array with cache_control)"
)

@field_validator("system")
@classmethod
def normalize_system(cls, v: Optional[Union[str, List[Dict[str, Any]]]]) -> Optional[str]:
    """Convert system field from array format to string."""
    if v is None:
        return None

    # If already a string, return as-is (backwards compat)
    if isinstance(v, str):
        return v

    # If array (Claude Code format), extract text from blocks
    if isinstance(v, list):
        text_parts = []
        for block in v:
            if isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
        result = "\n".join(text_parts)
        logger.debug(f"Converted system array to string ({len(text_parts)} blocks)")
        return result

    return None
```

**Rationale**:
- Claude Code uses prompt caching with array format
- Qwen backends (Ollama, llama.cpp) expect simple string
- Extracting text content preserves system prompt semantics
- Backwards compatible with string format

## Testing

Created comprehensive test suite (`test_422_fix.py`):

✅ **Test 1**: max_tokens capping (21333 → 4096)
✅ **Test 2**: system array format conversion
✅ **Test 3**: system string format (backwards compat)
✅ **Test 4**: Combined transformation

All tests pass. Example:
```
max_tokens=21333 exceeds Qwen limit, capping to 4096
System array correctly converted to string (2 blocks)
```

## Test Suite Results

- **Security tests**: 55/57 passed ✅
  - 2 failures due to missing dependencies (not related to changes)
- **Adapter unit tests**: 49/52 passed ✅
  - 3 failures due to missing uvicorn (not related to changes)
  - Updated `test_request_max_tokens_validation` to test capping behavior

## Files Modified

1. `qwenvert/adapter.py` - Added validators for max_tokens and system field
2. `tests/unit/test_adapter_unit.py` - Updated test to expect capping instead of error

## Impact

- ✅ Fixes 422 errors when using Claude Code with qwenvert
- ✅ Maintains security (all localhost validation still in place)
- ✅ Backwards compatible (still accepts old format)
- ✅ Graceful degradation (caps instead of rejects)
- ✅ User-visible warnings in logs for debugging

## Example Log Output

```
WARNING qwenvert.adapter:adapter.py:66 max_tokens=21333 exceeds Qwen limit, capping to 4096
DEBUG qwenvert.adapter:adapter.py:92 Converted system array to string (2 blocks)
```

## Next Steps

1. Test with real Claude Code instance
2. Consider adding max_tokens to config (per-model limits)
3. Monitor for any edge cases in system prompt conversion
