# OpenTelemetry Security in Qwenvert

This document describes the security measures implemented in qwenvert's OpenTelemetry integration to maintain our core guarantee: **your code never leaves your machine**.

## Security Guarantees

### 1. Localhost-Only Operation (Default)

By default, **all telemetry exporters are disabled**:
- ❌ OTLP exporter: OFF
- ❌ Prometheus exporter: OFF
- ❌ Console exporter: OFF

When running `qwenvert start` or `qwenvert monitor`, no telemetry data leaves your machine unless you explicitly enable exporters.

### 2. OTLP Endpoint Validation

If you enable the OTLP exporter, **qwenvert enforces localhost-only endpoints**:

```python
# ✅ SAFE - Localhost endpoints are allowed
export OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317
export OTEL_EXPORTER_OTLP_ENDPOINT=127.0.0.1:4317
export OTEL_EXPORTER_OTLP_ENDPOINT=::1:4317

# 🚨 BLOCKED - External endpoints are rejected
export OTEL_EXPORTER_OTLP_ENDPOINT=collector.example.com:4317  # ValueError!
export OTEL_EXPORTER_OTLP_ENDPOINT=192.168.1.100:4317          # ValueError!
```

This prevents accidental data exfiltration to cloud collectors.

### 3. No Sensitive Data Collection

Qwenvert telemetry collects **only metadata**, never your code or prompts:

#### ✅ What IS Collected

- **Token counts** (integers only)
  - Input tokens: 150
  - Output tokens: 200

- **Request latencies** (milliseconds)
  - Request duration: 1500ms

- **System metrics** (CPU, memory utilization)
  - CPU: 45%
  - Memory: 8.2GB / 16GB

- **Request status codes**
  - Status: success/error/timeout

- **Model names** (e.g., "qwen2.5-coder-7b-q4")

#### ❌ What is NOT Collected

- ❌ User prompts
- ❌ Generated code or text
- ❌ File paths or file contents
- ❌ Error messages containing user content
- ❌ API keys or credentials
- ❌ Environment variables
- ❌ Git commit messages or diffs

**Security Test**: See `tests/security/test_telemetry_security.py::test_metrics_do_not_capture_prompt_content`

## Data Flow Diagram

```
┌─────────────────────────────────────────────┐
│  Your Machine (localhost)                   │
│                                              │
│  qwenvert adapter                            │
│       ↓                                      │
│  OpenTelemetry SDK                           │
│       ↓                                      │
│  ┌─────────────────────────────────────┐   │
│  │ Exporters (ALL DISABLED by default) │   │
│  │                                      │   │
│  │  • Console → /dev/null               │   │
│  │  • OTLP    → /dev/null               │   │
│  │  • Prometheus → /dev/null            │   │
│  └─────────────────────────────────────┘   │
│                                              │
│  🔒 Data stays on your machine              │
└─────────────────────────────────────────────┘
```

## Safe Configuration Examples

### Example 1: No Telemetry (Default)

```bash
# Default behavior - no telemetry exported
qwenvert start
```

Metrics are collected internally for the dashboard, but not exported anywhere.

### Example 2: Local OTLP Collector

If you're running a local OpenTelemetry collector for development:

```bash
# Start local OTLP collector (must be localhost!)
docker run -p 4317:4317 otel/opentelemetry-collector

# Enable OTLP exporter (validated to be localhost)
export OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317
qwenvert start
```

✅ **Safe**: Data stays on your machine, sent to local collector.

### Example 3: Monitoring Dashboard

```bash
# View live stats (no external export)
qwenvert monitor
```

The dashboard uses OpenTelemetry metrics internally but doesn't export them.

## Unsafe Configurations (Blocked)

These configurations are **blocked by qwenvert** for your security:

```bash
# 🚨 BLOCKED - External collector
export OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud-collector.com:4317
qwenvert start
# ValueError: OTLP endpoint must be localhost for data privacy

# 🚨 BLOCKED - Cloud telemetry service
export OTEL_EXPORTER_OTLP_ENDPOINT=otel.vendor.com:443
qwenvert start
# ValueError: OTLP endpoint must be localhost for data privacy

# 🚨 BLOCKED - Network IP address
export OTEL_EXPORTER_OTLP_ENDPOINT=10.0.0.5:4317
qwenvert start
# ValueError: OTLP endpoint must be localhost for data privacy
```

## Environment Variables Reference

### Secure Variables (Recommended)

```bash
# Service identification (safe - no sensitive data)
export OTEL_SERVICE_NAME=qwenvert
export OTEL_SERVICE_VERSION=0.1.0

# Localhost OTLP endpoint (safe - validated)
export OTEL_EXPORTER_OTLP_ENDPOINT=localhost:4317

# Enable exporters (safe when localhost)
export OTEL_EXPORTER_CONSOLE=false      # Recommended: false (prevents log leaks)
export OTEL_EXPORTER_PROMETHEUS=false   # Recommended: false (no scraper needed)
```

### Security Flags

```bash
# Disable telemetry in qwenvert monitor
qwenvert monitor --no-otel

# Run without any telemetry collection
qwenvert start  # Already disabled by default
```

## Prometheus Metrics Security

**Important**: The Prometheus exporter in qwenvert **does NOT start an HTTP server**.

```python
# This only prepares metrics for collection, doesn't bind to any port
prometheus_reader = PrometheusMetricReader()
```

To expose metrics for Prometheus scraping, you would need to:
1. Run a separate Prometheus exporter HTTP server
2. Configure it to scrape qwenvert metrics
3. Ensure it binds to localhost only (0.0.0.0 would expose to network!)

**Recommendation**: Keep Prometheus disabled unless you have a specific local monitoring setup.

## Console Exporter Security Warning

The console exporter writes telemetry to stdout/stderr:

```bash
# ⚠️ WARNING: Console output could be captured by log aggregators
export OTEL_EXPORTER_CONSOLE=true
qwenvert start 2>&1 | tee app.log  # Metrics written to app.log
```

**Risk**: If you use log aggregation (CloudWatch, Datadog, etc.), console exporter data could be uploaded.

**Recommendation**: Keep `OTEL_EXPORTER_CONSOLE=false` (default) in production.

## Security Testing

Run security tests to verify telemetry safety:

```bash
# Run all security tests
pytest tests/security/ -v

# Run telemetry-specific security tests
pytest tests/security/test_telemetry_security.py -v

# Key security tests:
# - test_external_endpoint_rejected
# - test_metrics_do_not_capture_prompt_content
# - test_otlp_endpoint_env_var_validated
```

## Threat Model

### Threat 1: Data Exfiltration via OTLP

**Attack**: Malicious actor sets `OTEL_EXPORTER_OTLP_ENDPOINT` to external server.

**Mitigation**:
- ✅ Endpoint validation rejects non-localhost URLs
- ✅ Security test coverage
- ✅ Error logged with rejected endpoint

### Threat 2: Sensitive Data in Metrics

**Attack**: User prompts or code captured in metric attributes.

**Mitigation**:
- ✅ Only metadata collected (tokens, latencies, status)
- ✅ No content fields in RequestMetrics dataclass
- ✅ Security tests verify no sensitive data

### Threat 3: Log Aggregation Leak

**Attack**: Console exporter writes data to logs, which are uploaded to cloud.

**Mitigation**:
- ✅ Console exporter disabled by default
- ✅ Documentation warns about log aggregation
- ✅ Recommendation to keep disabled

### Threat 4: Network Exposure via Prometheus

**Attack**: Prometheus HTTP server exposes metrics on public interface.

**Mitigation**:
- ✅ PrometheusMetricReader doesn't start HTTP server
- ✅ Prometheus disabled by default
- ✅ Documentation clarifies behavior

## Advanced: mTLS for Remote Collectors (Future)

If you need to send telemetry to a remote collector for enterprise monitoring, future versions will support:

```bash
# Future feature - not yet implemented
export OTEL_EXPORTER_OTLP_ENDPOINT=https://secure-collector.internal:4317
export OTEL_EXPORTER_OTLP_CERTIFICATE=/path/to/ca.crt
export OTEL_EXPORTER_OTLP_CLIENT_KEY=/path/to/client.key
export OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE=/path/to/client.crt
export QWENVERT_ALLOW_REMOTE_TELEMETRY=true  # Explicit opt-in
```

**Status**: Not implemented. Localhost-only is enforced.

## Security Audit Report

Full security audit results: See `AGENTS.md` for running the security auditor.

```bash
# Run security audit on telemetry system
claude-code task --agent=qwenvert-security-auditor "Audit OpenTelemetry implementation"
```

**Last Audit**: 2026-02-09
**Findings**: 2 critical issues fixed, 3 warnings documented
**Status**: ✅ SECURE for localhost operation

## Reporting Security Issues

If you discover a security vulnerability in qwenvert's telemetry:

1. **DO NOT** open a public issue
2. Email: kmesiab@gmail.com with subject "SECURITY: Qwenvert Telemetry"
3. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and credit reporters in security advisories.

## Summary

✅ **Telemetry is secure by default**
✅ **Localhost-only enforcement**
✅ **No sensitive data collection**
✅ **Security test coverage**
✅ **Clear documentation**

Your code stays on your machine. Always.
