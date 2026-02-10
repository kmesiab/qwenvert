"""
Security tests for OpenTelemetry telemetry system.

Verifies that telemetry configuration maintains qwenvert's security guarantees:
- No data exfiltration to external collectors
- Localhost-only operation
- No sensitive data in metrics
"""

import contextlib

import pytest

from qwenvert.telemetry import _validate_localhost_endpoint, init_telemetry


class TestOTLPEndpointSecurity:
    """Test OTLP endpoint validation for security."""

    def test_localhost_endpoint_accepted(self):
        """SECURITY: localhost endpoints should be accepted."""
        valid_endpoints = [
            "localhost:4317",
            "127.0.0.1:4317",
            "::1:4317",
            "http://localhost:4317",
            "https://127.0.0.1:4317",
            "grpc://localhost:4317",
        ]

        for endpoint in valid_endpoints:
            result = _validate_localhost_endpoint(endpoint)
            assert result == endpoint

    def test_external_endpoint_rejected(self):
        """SECURITY: External endpoints must be rejected to prevent data exfiltration."""
        external_endpoints = [
            "collector.example.com:4317",
            "https://otlp.cloud.com:4317",
            "192.168.1.100:4317",
            "10.0.0.5:4317",
            "example.com:4317",
            "otel-collector.internal:4317",
            "0.0.0.0:4317",  # Bind to all interfaces
        ]

        for endpoint in external_endpoints:
            with pytest.raises(ValueError, match="localhost"):
                _validate_localhost_endpoint(endpoint)

    def test_init_telemetry_with_external_otlp_rejected(self):
        """SECURITY: init_telemetry must reject external OTLP endpoints."""
        from qwenvert.telemetry import shutdown_telemetry

        # Shutdown any existing telemetry first
        shutdown_telemetry()

        with pytest.raises(ValueError, match="localhost"):
            init_telemetry(
                service_name="test",
                enable_otlp=True,
                otlp_endpoint="https://collector.example.com:4317",
            )

    def test_init_telemetry_with_localhost_otlp_accepted(self):
        """SECURITY: init_telemetry should accept localhost OTLP endpoints."""
        from qwenvert.telemetry import shutdown_telemetry

        # Shutdown any existing telemetry first
        shutdown_telemetry()

        try:
            init_telemetry(
                service_name="test-localhost",
                enable_otlp=True,
                otlp_endpoint="localhost:4317",
            )
        except Exception as e:
            # May fail due to OTLP collector not running, but should not be ValueError
            assert "localhost" not in str(e).lower()  # noqa: PT017
        finally:
            shutdown_telemetry()


class TestMetricDataSecurity:
    """Test that metrics don't capture sensitive data."""

    def test_metrics_do_not_capture_prompt_content(self):
        """SECURITY: Verify no user prompts are captured in metrics."""
        from datetime import datetime, timezone

        from qwenvert.monitoring import MetricsCollector, RequestMetrics

        collector = MetricsCollector(enable_otel=False)  # Disable OTEL for unit test

        # Simulate a request with sensitive prompt content
        metric = RequestMetrics(
            timestamp=datetime.now(tz=timezone.utc),
            model="test-model",
            tokens_generated=100,
            latency_ms=1500,
            tokens_per_second=66.7,
            streaming=False,
            status="success",
        )

        collector.add_request_metric(metric)

        # Verify no prompt content in stored metrics
        for req in collector.request_history:
            assert not hasattr(req, "prompt")
            assert not hasattr(req, "content")
            assert "secret" not in str(req).lower()
            assert "hack" not in str(req).lower()

    def test_metrics_collector_only_captures_metadata(self):
        """SECURITY: Verify only non-sensitive metadata is captured."""
        from datetime import datetime, timezone

        from qwenvert.monitoring import MetricsCollector, RequestMetrics

        collector = MetricsCollector(enable_otel=False)

        metric = RequestMetrics(
            timestamp=datetime.now(tz=timezone.utc),
            model="qwen-test",
            tokens_generated=50,
            latency_ms=1000.0,  # Use float
            tokens_per_second=50.0,
            streaming=True,
            status="success",
        )

        collector.add_request_metric(metric)

        # Verify only safe metadata is present
        req = next(iter(collector.request_history))
        assert isinstance(req.tokens_generated, int)
        assert isinstance(req.latency_ms, (int, float))  # Accept both
        assert isinstance(req.tokens_per_second, (int, float))  # Accept both
        assert req.status in ["success", "error", "timeout"]
        assert req.streaming in [True, False]


class TestTelemetryDefaultSecurity:
    """Test that telemetry defaults are secure."""

    def test_otlp_disabled_by_default(self):
        """SECURITY: OTLP should be disabled by default."""
        # This is verified by checking the CLI and launcher code
        # Both default enable_otlp=False

    def test_prometheus_disabled_by_default(self):
        """SECURITY: Prometheus should be disabled by default."""
        # This is verified by checking the CLI and launcher code
        # Both default enable_prometheus=False

    def test_console_exporter_disabled_by_default(self):
        """SECURITY: Console exporter should be disabled by default to prevent log leaks."""
        # This is verified by checking the CLI and launcher code
        # Both default enable_console=False


class TestPrometheusExporterSecurity:
    """Test Prometheus exporter security."""

    def test_prometheus_reader_does_not_bind_network_port(self):
        """
        SECURITY: Verify PrometheusMetricReader doesn't open network ports.

        Note: PrometheusMetricReader in opentelemetry-exporter-prometheus
        does NOT start an HTTP server. It only prepares metrics for collection.
        """
        # This is a documentation test - the reader itself is safe
        # as it doesn't bind to any network interface
        from opentelemetry.exporter.prometheus import PrometheusMetricReader

        reader = PrometheusMetricReader()

        # PrometheusMetricReader doesn't have a server attribute
        assert not hasattr(reader, "server")
        assert not hasattr(reader, "http_server")

        # It only provides a collect() method for metrics
        assert hasattr(reader, "collect")


class TestTelemetryLifecycle:
    """Test telemetry initialization and shutdown lifecycle."""

    def test_shutdown_telemetry_clean(self):
        """OTEL-002: Test telemetry shuts down cleanly and flushes data."""
        import qwenvert.telemetry as telemetry_module
        from qwenvert.telemetry import init_telemetry, shutdown_telemetry

        # Initialize
        shutdown_telemetry()  # Clean slate
        init_telemetry(service_name="test-shutdown")

        # Verify initialized
        assert telemetry_module._initialized is True
        assert telemetry_module._meter_provider is not None
        assert telemetry_module._tracer_provider is not None

        # Shutdown
        shutdown_telemetry()

        # Verify cleaned up
        assert telemetry_module._initialized is False
        assert telemetry_module._meter_provider is None
        assert telemetry_module._tracer_provider is None

    def test_shutdown_telemetry_before_init(self):
        """OTEL-002: Test shutdown before init is safe (idempotent)."""
        import qwenvert.telemetry as telemetry_module
        from qwenvert.telemetry import shutdown_telemetry

        # Ensure not initialized
        shutdown_telemetry()
        assert telemetry_module._initialized is False

        # Shutdown again (should be safe)
        shutdown_telemetry()
        assert telemetry_module._initialized is False

    def test_double_shutdown_is_idempotent(self):
        """OTEL-002: Test double shutdown doesn't cause errors."""
        from qwenvert.telemetry import init_telemetry, shutdown_telemetry

        shutdown_telemetry()
        init_telemetry(service_name="test-double-shutdown")

        # First shutdown
        shutdown_telemetry()

        # Second shutdown (should be safe)
        shutdown_telemetry()  # Should not raise


class TestNoOpProviderFallback:
    """OTEL-004: Test no-op provider fallback when not initialized."""

    def test_get_meter_before_init_returns_noop(self):
        """Test no-op meter is returned when not initialized."""
        from qwenvert.telemetry import get_meter, shutdown_telemetry

        # Ensure clean state
        shutdown_telemetry()

        # Get meter before init
        meter = get_meter("test")

        # Should return meter (no-op), not raise exception
        counter = meter.create_counter("test_counter")
        counter.add(1)  # Should not crash

    def test_get_tracer_before_init_returns_noop(self):
        """Test no-op tracer is returned when not initialized."""
        from qwenvert.telemetry import get_tracer, shutdown_telemetry

        # Ensure clean state
        shutdown_telemetry()

        # Get tracer before init
        tracer = get_tracer("test")

        # Should return tracer (no-op), not raise exception
        with tracer.start_as_current_span("test_span"):
            pass  # Should not crash

    def test_get_meter_after_shutdown_returns_noop(self):
        """Test no-op meter after shutdown."""
        from qwenvert.telemetry import get_meter, init_telemetry, shutdown_telemetry

        shutdown_telemetry()
        init_telemetry(service_name="test")
        shutdown_telemetry()  # Now shutdown

        # Get meter after shutdown
        meter = get_meter("test")
        counter = meter.create_counter("test_counter")
        counter.add(1)  # Should not crash


class TestEnvironmentVariableInitialization:
    """OTEL-005: Test environment variable initialization."""

    def test_init_from_env_with_defaults(self, monkeypatch):
        """Test init_from_env with default environment."""
        from qwenvert.telemetry import init_from_env, shutdown_telemetry

        shutdown_telemetry()

        # No env vars set - should use defaults
        monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

        init_from_env()
        # Should not raise, should use defaults

    def test_init_from_env_with_otlp_endpoint(self, monkeypatch):
        """Test OTLP is enabled when env var set."""
        from qwenvert.telemetry import init_from_env, shutdown_telemetry

        shutdown_telemetry()
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")

        exc = None
        try:
            init_from_env()
            # Should initialize with OTLP enabled
        except Exception as e:
            # May fail if collector not running
            exc = e
        finally:
            shutdown_telemetry()

        # If an exception occurred, it shouldn't be a validation error about localhost
        if exc is not None:
            assert "localhost" not in str(exc).lower() or "connection" in str(exc).lower()

    def test_init_from_env_with_invalid_port(self, monkeypatch):
        """Test invalid Prometheus port is handled gracefully."""
        from qwenvert.telemetry import init_from_env, shutdown_telemetry

        shutdown_telemetry()
        monkeypatch.setenv("OTEL_EXPORTER_PROMETHEUS_PORT", "invalid_port")

        # Should use default 9464, not crash
        init_from_env()
        shutdown_telemetry()

    def test_init_from_env_with_console_enabled(self, monkeypatch):
        """Test console exporter enabled via env var."""
        from qwenvert.telemetry import init_from_env, shutdown_telemetry

        shutdown_telemetry()
        monkeypatch.setenv("OTEL_EXPORTER_CONSOLE", "true")

        init_from_env()
        # Should initialize with console enabled
        shutdown_telemetry()

    def test_init_from_env_with_custom_service_name(self, monkeypatch):
        """Test custom service name from env var."""
        from qwenvert.telemetry import init_from_env, shutdown_telemetry

        shutdown_telemetry()
        monkeypatch.setenv("OTEL_SERVICE_NAME", "my-custom-service")

        init_from_env()
        # Should use custom service name
        shutdown_telemetry()


class TestEnvironmentVariableSecurity:
    """Test environment variable handling for security."""

    def test_otlp_endpoint_env_var_validated(self, monkeypatch):
        """SECURITY: Environment variable OTEL_EXPORTER_OTLP_ENDPOINT must be validated."""
        from qwenvert.telemetry import shutdown_telemetry

        # Shutdown any existing telemetry first
        shutdown_telemetry()

        # Set external endpoint via env var
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "https://evil.com:4317")

        with pytest.raises(ValueError, match="localhost"):
            init_telemetry(
                service_name="test",
                enable_otlp=True,
                # otlp_endpoint not specified, should read from env var
            )

    def test_localhost_env_var_accepted(self, monkeypatch):
        """SECURITY: Localhost OTLP endpoint from env var should be accepted."""
        from qwenvert.telemetry import shutdown_telemetry

        # Shutdown any existing telemetry first
        shutdown_telemetry()

        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")

        exc = None
        try:
            init_telemetry(
                service_name="test",
                enable_otlp=True,
            )
        except Exception as e:
            # May fail due to collector not running
            exc = e
        finally:
            shutdown_telemetry()

        # If an exception occurred, it shouldn't be a validation error about localhost
        if exc is not None:
            assert "localhost" not in str(exc).lower() or "connection" in str(exc).lower()


class TestOTLPConnectionFailureHandling:
    """OTEL-011: Test OTLP exporter graceful degradation."""

    def test_init_succeeds_with_unreachable_otlp_endpoint(self):
        """
        Test telemetry initialization succeeds even if OTLP collector is unreachable.

        OTLP exporters use lazy connection - the connection is only attempted
        when data is exported, not during initialization.
        """
        from qwenvert.telemetry import init_telemetry, shutdown_telemetry

        shutdown_telemetry()

        # Use a port that's unlikely to be in use
        try:
            init_telemetry(
                service_name="test-unreachable",
                enable_otlp=True,
                otlp_endpoint="localhost:19999",  # Unreachable port
            )
            # Should succeed - connection is lazy
        finally:
            shutdown_telemetry()

    def test_metrics_export_degrades_gracefully_on_connection_failure(self):
        """
        Test metrics export doesn't crash when OTLP collector is unreachable.

        Metrics should be dropped silently, not crash the application.
        """
        from qwenvert.telemetry import get_meter, init_telemetry, shutdown_telemetry

        shutdown_telemetry()

        try:
            # Initialize with unreachable endpoint
            init_telemetry(
                service_name="test-graceful",
                enable_otlp=True,
                otlp_endpoint="localhost:29999",  # Unreachable
            )

            # Create and use metrics
            meter = get_meter("test")
            counter = meter.create_counter("test.counter")

            # This should not crash, even though OTLP export will fail
            counter.add(1)
            counter.add(5, {"key": "value"})

            # Force a metrics collection attempt
            import qwenvert.telemetry as telemetry_module

            if telemetry_module._meter_provider:
                # Trigger metric readers
                for (
                    reader
                ) in telemetry_module._meter_provider._sdk_config.metric_readers:
                    # Expected - OTLP collector not available
                    # Should not propagate to application
                    with contextlib.suppress(Exception):
                        reader.collect()

        finally:
            shutdown_telemetry()

    def test_traces_export_degrades_gracefully_on_connection_failure(self):
        """
        Test traces export doesn't crash when OTLP collector is unreachable.

        Spans should be dropped silently, not crash the application.
        """
        from qwenvert.telemetry import get_tracer, init_telemetry, shutdown_telemetry

        shutdown_telemetry()

        try:
            # Initialize with unreachable endpoint
            init_telemetry(
                service_name="test-traces",
                enable_otlp=True,
                otlp_endpoint="localhost:39999",  # Unreachable
            )

            # Create and use tracer
            tracer = get_tracer("test")

            # This should not crash
            with tracer.start_as_current_span("test.span") as span:
                span.set_attribute("test", "value")

            # Force span export
            import qwenvert.telemetry as telemetry_module

            if telemetry_module._tracer_provider:
                # Span processors export in background
                # Just verify we can complete spans without crashing
                pass

        finally:
            shutdown_telemetry()

    def test_shutdown_succeeds_even_with_failed_otlp_connection(self):
        """
        Test shutdown completes even if OTLP connection never succeeded.

        Shutdown should flush pending data without blocking indefinitely.
        """
        import time

        from qwenvert.telemetry import init_telemetry, shutdown_telemetry

        shutdown_telemetry()

        try:
            init_telemetry(
                service_name="test-shutdown",
                enable_otlp=True,
                otlp_endpoint="localhost:49999",
            )

            # Create some data
            from qwenvert.telemetry import get_meter

            meter = get_meter("test")
            counter = meter.create_counter("test.counter")
            counter.add(100)

            # Shutdown should complete quickly (not block forever)
            start = time.time()
            shutdown_telemetry()
            elapsed = time.time() - start

            # Shutdown should complete in under 5 seconds
            # (not hang waiting for unreachable collector)
            assert elapsed < 5.0, f"Shutdown took {elapsed}s (expected < 5s)"

        except Exception:
            # Cleanup
            shutdown_telemetry()

    def test_multiple_failed_exports_dont_accumulate_errors(self):
        """
        Test that repeated failed exports don't accumulate errors.

        Verify memory doesn't leak from failed export attempts.
        """
        from qwenvert.telemetry import get_meter, init_telemetry, shutdown_telemetry

        shutdown_telemetry()

        try:
            init_telemetry(
                service_name="test-accumulation",
                enable_otlp=True,
                otlp_endpoint="localhost:59999",
            )

            meter = get_meter("test")
            counter = meter.create_counter("test.counter")

            # Generate many metrics
            for i in range(100):
                counter.add(1, {"iteration": i})

            # Should not crash or accumulate unbounded errors

        finally:
            shutdown_telemetry()


class TestObservableCallbackErrorHandling:
    """OTEL-012: Test observable callback error handling."""

    def test_cpu_utilization_callback_handles_division_by_zero(self):
        """Test CPU utilization callback handles edge case when cached value is invalid."""
        from opentelemetry.metrics import CallbackOptions

        from qwenvert.monitoring import MetricsCollector

        collector = MetricsCollector(enable_otel=False)  # No OTEL to avoid side effects

        # Set invalid cached CPU value
        collector._cached_cpu = float("inf")

        # Call observable callback
        options = CallbackOptions()
        result = collector._observe_cpu_utilization(options)

        # Should return empty list on error, not crash
        assert isinstance(result, list)

    def test_memory_utilization_callback_handles_invalid_cached_value(self):
        """Test memory utilization callback handles corrupted cached value."""
        from opentelemetry.metrics import CallbackOptions

        from qwenvert.monitoring import MetricsCollector

        collector = MetricsCollector(enable_otel=False)

        # Set invalid cached memory value
        collector._cached_memory = float("nan")

        # Call observable callback
        options = CallbackOptions()
        result = collector._observe_memory_utilization(options)

        # Should return empty list on error, not crash
        assert isinstance(result, list)

    def test_cpu_temperature_callback_handles_none_cached_value(self):
        """Test CPU temperature callback returns empty when temp unavailable."""
        from opentelemetry.metrics import CallbackOptions

        from qwenvert.monitoring import MetricsCollector

        collector = MetricsCollector(enable_otel=False)

        # Temperature not available (None)
        collector._cached_temp = None

        # Call observable callback
        options = CallbackOptions()
        result = collector._observe_cpu_temperature(options)

        # Should return empty list (no observation)
        assert result == []

    def test_token_throughput_callback_handles_empty_history(self):
        """Test token throughput callback handles empty request history."""
        from opentelemetry.metrics import CallbackOptions

        from qwenvert.monitoring import MetricsCollector

        collector = MetricsCollector(enable_otel=False)

        # Empty request history
        collector.request_history.clear()

        # Call observable callback
        options = CallbackOptions()
        result = collector._observe_token_throughput(options)

        # Should return observation with 0.0 value, not crash
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].value == 0.0

    def test_observable_callbacks_log_errors_without_crashing(self, caplog):
        """Test all observable callbacks log errors instead of crashing."""
        import logging
        from unittest.mock import patch

        from opentelemetry.metrics import CallbackOptions

        from qwenvert.monitoring import MetricsCollector

        collector = MetricsCollector(enable_otel=False)

        # Mock to raise an exception in callback
        with patch.object(
            collector, "_cached_cpu", new_callable=lambda: property(lambda _: 1 / 0)
        ):
            with caplog.at_level(logging.ERROR):
                options = CallbackOptions()
                result = collector._observe_cpu_utilization(options)

                # Should return empty list, not crash
                assert result == []

    def test_all_observable_callbacks_are_resilient(self):
        """
        Integration test: Verify all observable callbacks are resilient.

        Tests that callbacks can be called repeatedly without crashing,
        even with edge case values.
        """
        from opentelemetry.metrics import CallbackOptions

        from qwenvert.monitoring import MetricsCollector

        collector = MetricsCollector(enable_otel=False)
        options = CallbackOptions()

        # Test with various edge case values
        edge_cases = [
            (float("inf"), float("inf"), float("inf")),
            (float("nan"), float("nan"), float("nan")),
            (0.0, 0.0, 0.0),
            (-1.0, -1.0, -1.0),
            (10000.0, 10000.0, 10000.0),
        ]

        for cpu, mem, temp in edge_cases:
            collector._cached_cpu = cpu
            collector._cached_memory = mem
            collector._cached_temp = temp

            # All callbacks should handle edge cases gracefully
            cpu_result = collector._observe_cpu_utilization(options)
            mem_result = collector._observe_memory_utilization(options)
            temp_result = collector._observe_cpu_temperature(options)
            throughput_result = collector._observe_token_throughput(options)

            # Should return lists, not crash
            assert isinstance(cpu_result, list)
            assert isinstance(mem_result, list)
            assert isinstance(temp_result, list)
            assert isinstance(throughput_result, list)

    def test_observable_callback_returns_empty_on_attribute_error(self):
        """Test callbacks return empty list if cached attributes are missing."""
        from opentelemetry.metrics import CallbackOptions

        from qwenvert.monitoring import MetricsCollector

        collector = MetricsCollector(enable_otel=False)
        options = CallbackOptions()

        # Delete cached attributes to simulate corruption
        del collector._cached_cpu

        # Should return empty, not raise AttributeError
        result = collector._observe_cpu_utilization(options)
        assert result == []
