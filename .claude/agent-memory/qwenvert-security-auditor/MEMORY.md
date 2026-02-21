# Qwenvert Security Audit - Agent Memory

## Last Audit: 2026-02-18 (Phase 1 Refactoring - v0.2.14)

### Core Security Architecture

**Critical Security Modules:**
- `/qwenvert/security.py` - Central validation (139 lines)
- `/qwenvert/config.py` - Configuration validation with Modelfile injection protection
- `/qwenvert/telemetry.py` - Localhost-only OTLP validation (586 lines)
- `/qwenvert/adapter.py` - FastAPI server with localhost binding
- `/qwenvert/launcher.py` - Process manager with security checks
- `/qwenvert/router.py` - Backend routing with URL validation

### Security Test Coverage

**Total Tests:** 573 (as of Phase 1 refactor)
**Security Tests:** 92 (all passing)

**Test Files:**
- `tests/security/test_network_isolation.py` - Network binding tests
- `tests/security/test_security_validation.py` - Core validation functions (56 tests)
- `tests/security/test_router_security.py` - Router URL validation
- `tests/security/test_launcher_security.py` - Launcher config validation
- `tests/security/test_telemetry_security.py` - Telemetry endpoint validation (36 tests)

### Validated Security Patterns

**1. Localhost-Only Binding:**
```python
# adapter.py:348, 373
config = uvicorn.Config(app, host="127.0.0.1", port=8088)

# Default config (config.py:45)
adapter_host: str = "127.0.0.1"
```

**2. URL Validation at Entry Points:**
```python
# router.py:56
validate_localhost_url(backend_url)

# launcher.py:323
validate_adapter_host(self.config.adapter_host)

# config.py:68-71
validate_adapter_host(self.adapter_host)
validate_localhost_url(self.backend_url)
```

**3. OTLP Endpoint Validation:**
```python
# telemetry.py:95-148
_validate_localhost_endpoint(endpoint)
# Rejects: external IPs, 0.0.0.0, LAN addresses
# Allows: localhost, 127.0.0.1, ::1
```

**4. Forbidden Pattern Detection:**
```python
# security.py:23-28
FORBIDDEN_PATTERNS = [
    r"^0\.0\.0\.0$",  # All interfaces
    r"^192\.168\.\d+\.\d+$",  # LAN
    r"^10\.\d+\.\d+\.\d+$",  # LAN
    r"^172\.(1[6-9]|2[0-9]|3[01])\.\d+\.\d+$",  # LAN
]
```

### External Network Calls (Legitimate)

**Model Downloads (HuggingFace Hub):**
- `downloader.py:89` - `hf_hub_download()` for model files
- User-initiated, not automatic
- No code/prompt exfiltration

**Binary Downloads (llama.cpp releases):**
- `binary_manager.py:72` - `https://api.github.com/repos/ggml-org/llama.cpp/releases/latest`
- `binary_manager.py:626` - GitHub release downloads
- User-initiated during setup
- Checksums verified (Zip Slip protection in place)

### Known Security Fixes

**v0.2.10 (2026-02-14):** CRITICAL - Zip Slip TOCTOU vulnerability patched
**v0.2.12 (2026-02-17):** llama.cpp repo migration (ggerganov -> ggml-org)
**v0.2.13 (2026-02-17):** Enhanced binary extraction with dylib support

### Configuration Security

**API Key Placeholder Pattern:**
```python
# config.py:370, 378, launcher.py:450
'ANTHROPIC_API_KEY': 'local-qwen'  # Placeholder, not real credential
```

**Modelfile Injection Protection:**
```python
# config.py:78-140
_validate_model_path(model_path)
# Blocks: newlines, control chars, Modelfile directives
```

### Dependency Analysis

**HTTP Clients (7 files use httpx):**
- `binary_manager.py` - GitHub API (localhost validation not required - downloads only)
- `router.py` - Backend communication (localhost validated)
- `launcher.py` - Health checks (localhost validated)
- `cli.py`, `monitoring.py` - Adapter communication
- `backends/ollama_backend.py`, `backends/llamacpp_backend.py` - Backend APIs

**No External Analytics:**
- No Sentry, DataDog, Segment, Amplitude, Mixpanel
- OpenTelemetry exporters disabled by default
- OTLP endpoints validated as localhost-only

### Security Baseline Metrics

- **Localhost patterns:** 30+ references to 127.0.0.1/localhost
- **Security validation calls:** validate_adapter_host(), validate_localhost_url()
- **Test coverage:** 16% of all tests are security-focused
- **Zero production 0.0.0.0 bindings** (only in test mocks)

### Audit Checklist (Use for Future Audits)

- [ ] No 0.0.0.0 bindings in production code
- [ ] All server configs bind to 127.0.0.1
- [ ] Router validates backend URLs as localhost
- [ ] Launcher validates adapter host
- [ ] Config.validate() called before use
- [ ] OTLP endpoints validated if telemetry enabled
- [ ] No hardcoded credentials (only placeholders)
- [ ] No external analytics/telemetry packages
- [ ] HuggingFace downloads user-initiated only
- [ ] GitHub API calls for binary downloads only
- [ ] All 92 security tests passing

### Risk Areas to Monitor

1. **New HTTP client usage** - Always validate URLs as localhost
2. **Config file loading** - Call `.validate()` immediately
3. **New telemetry exporters** - Validate endpoints
4. **Binary downloads** - Maintain checksum verification
5. **Model path handling** - Maintain injection protection
