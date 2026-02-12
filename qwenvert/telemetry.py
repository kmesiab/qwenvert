"""
OpenTelemetry instrumentation and configuration for qwenvert.

Provides OpenTelemetry-compliant metrics, tracing, and exporters
following semantic conventions for HTTP, system, and gen_ai.

Security-First Design:
    - All exporters disabled by default
    - OTLP endpoints validated as localhost-only
    - No sensitive data (prompts/responses) captured
    - No network ports opened automatically

Example usage:
    Basic initialization (all exporters disabled):
        >>> from qwenvert.telemetry import init_telemetry
        >>> init_telemetry(service_name="qwenvert")

    Enable OTLP export to local collector:
        >>> init_telemetry(
        ...     service_name="qwenvert",
        ...     enable_otlp=True,
        ...     otlp_endpoint="localhost:4317"
        ... )

    Enable console exporter for debugging:
        >>> init_telemetry(
        ...     service_name="qwenvert",
        ...     enable_console=True
        ... )

    Initialize from environment variables:
        >>> import os
        >>> os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "localhost:4317"
        >>> from qwenvert.telemetry import init_from_env
        >>> init_from_env()

    Get meter for custom metrics:
        >>> from qwenvert.telemetry import get_meter
        >>> meter = get_meter("my.component")
        >>> counter = meter.create_counter("my.metric")
        >>> counter.add(1)

    Get tracer for custom spans:
        >>> from qwenvert.telemetry import get_tracer
        >>> tracer = get_tracer("my.component")
        >>> with tracer.start_as_current_span("my.operation"):
        ...     # Your code here
        ...     pass

    Graceful shutdown (flushes all metrics/traces):
        >>> from qwenvert.telemetry import shutdown_telemetry
        >>> shutdown_telemetry()

See also:
    - TELEMETRY_SECURITY.md for security guarantees
    - OpenTelemetry semantic conventions:
      https://opentelemetry.io/docs/specs/semconv/
"""

import logging
import os
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

from opentelemetry import metrics, trace


if TYPE_CHECKING:
    from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


logger = logging.getLogger(__name__)


# Global telemetry state
_initialized = False
_meter_provider: Optional[MeterProvider] = None
_tracer_provider: Optional[TracerProvider] = None


def _validate_localhost_endpoint(endpoint: Optional[str]) -> str:
    """
    Validate that endpoint is localhost-only for security.

    Args:
        endpoint: Endpoint URL to validate. Can include protocol prefix
                  (http://, https://, grpc://) and port number.
                  Examples: "localhost:4317", "http://127.0.0.1:4317"
                  If None, defaults to "localhost:4317"

    Returns:
        The endpoint if valid (unchanged)

    Raises:
        ValueError: If endpoint is not localhost. Error message includes
                    the rejected endpoint and list of allowed patterns.

    Security: Prevents data exfiltration to external collectors.
              Only localhost, 127.0.0.1, and ::1 are permitted.
    """
    if endpoint is None:
        endpoint = "localhost:4317"

    # Parse the endpoint to extract hostname
    # Handle various formats: "host:port", "http://host:port", "[::1]:4317"
    parsed_endpoint = endpoint

    # Add scheme if missing to help urlparse
    if "://" not in endpoint:
        parsed_endpoint = f"http://{endpoint}"

    try:
        parsed = urlparse(parsed_endpoint)
        # Extract hostname (handles IPv6 brackets automatically)
        hostname = parsed.hostname or "localhost"
    except Exception:
        # If parsing fails, fall back to original string check
        hostname = endpoint.split(":")[0].strip("[]")

    # Allowed localhost hostnames (exact match only)
    allowed_hostnames = {"localhost", "127.0.0.1", "::1"}

    if hostname.lower() not in allowed_hostnames:
        msg = (
            f"Security: OTLP endpoint must be localhost for data privacy. "
            f"Got: {endpoint} (hostname: {hostname}). "
            f"Allowed: localhost, 127.0.0.1, ::1"
        )
        logger.error(msg)
        raise ValueError(msg)

    logger.info(f"✓ Validated localhost endpoint: {endpoint} (hostname: {hostname})")
    return endpoint


def init_telemetry(  # noqa: PLR0913
    service_name: str = "qwenvert",
    service_version: str = "0.1.0",
    enable_console: bool = False,
    enable_otlp: bool = False,
    enable_prometheus: bool = False,
    otlp_endpoint: Optional[str] = None,
    prometheus_port: int = 9464,
) -> None:
    """
    Initialize OpenTelemetry SDK with metrics and tracing.

    Security:
        - All exporters disabled by default (zero network exposure)
        - OTLP endpoints validated as localhost-only
        - External endpoints raise ValueError

    Args:
        service_name: Service name for telemetry
        service_version: Service version
        enable_console: Enable console exporters for debugging
        enable_otlp: Enable OTLP exporters
        enable_prometheus: Enable Prometheus exporter
        otlp_endpoint: OTLP collector endpoint (default: localhost:4317)
        prometheus_port: Prometheus metrics port (default: 9464)

    Raises:
        ValueError: If otlp_endpoint is not localhost

    Example:
        Basic initialization (no exporters):
            >>> init_telemetry(service_name="my-service")

        Enable OTLP export to local collector:
            >>> init_telemetry(
            ...     service_name="my-service",
            ...     enable_otlp=True,
            ...     otlp_endpoint="localhost:4317"
            ... )

        Debug mode with console output:
            >>> init_telemetry(
            ...     service_name="my-service",
            ...     enable_console=True
            ... )
    """
    global _initialized, _meter_provider, _tracer_provider  # noqa: PLW0603

    if _initialized:
        logger.warning("Telemetry already initialized, skipping")
        return

    # Create resource with semantic conventions
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": service_version,
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.language": "python",
        }
    )

    # Resolve and validate OTLP endpoint once
    resolved_otlp_endpoint = None
    if enable_otlp:
        resolved_otlp_endpoint = otlp_endpoint or os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"
        )
        resolved_otlp_endpoint = _validate_localhost_endpoint(resolved_otlp_endpoint)

    # Initialize metrics
    _meter_provider = _init_metrics(
        resource=resource,
        enable_console=enable_console,
        enable_otlp=enable_otlp,
        enable_prometheus=enable_prometheus,
        otlp_endpoint=resolved_otlp_endpoint,
        prometheus_port=prometheus_port,
    )

    # Initialize tracing
    _tracer_provider = _init_tracing(
        resource=resource,
        enable_console=enable_console,
        enable_otlp=enable_otlp,
        otlp_endpoint=resolved_otlp_endpoint,
    )

    # Instrument HTTP libraries
    HTTPXClientInstrumentor().instrument()

    _initialized = True
    logger.info(f"✓ OpenTelemetry initialized for {service_name} v{service_version}")


def _init_metrics(  # noqa: PLR0913
    resource: Resource,
    enable_console: bool,
    enable_otlp: bool,
    enable_prometheus: bool,
    otlp_endpoint: Optional[str],
    prometheus_port: int,
) -> MeterProvider:
    """Initialize metrics with configured exporters."""
    metric_readers: list[MetricReader] = []

    # Console exporter for debugging
    if enable_console:
        console_reader = PeriodicExportingMetricReader(
            ConsoleMetricExporter(),
            export_interval_millis=60000,  # 60 seconds
        )
        metric_readers.append(console_reader)
        logger.info("✓ Console metric exporter enabled")

    # OTLP exporter for collectors (e.g., Jaeger, SigNoz)
    if enable_otlp and otlp_endpoint:
        # Endpoint already resolved and validated in init_telemetry
        otlp_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=otlp_endpoint),
            export_interval_millis=60000,
        )
        metric_readers.append(otlp_reader)
        logger.info(f"✓ OTLP metric exporter enabled (endpoint: {otlp_endpoint})")

    # Prometheus exporter
    # Security Note: PrometheusMetricReader does NOT start an HTTP server.
    # It only prepares metrics for collection by an external Prometheus scraper.
    # No network port is opened by this reader.
    if enable_prometheus:
        prometheus_reader = PrometheusMetricReader()
        metric_readers.append(prometheus_reader)
        logger.info("✓ Prometheus exporter enabled (metrics available for collection)")
        logger.info(
            "   Note: No HTTP server started - metrics must be scraped externally"
        )

    # Create meter provider
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=metric_readers,
    )

    # Set global meter provider
    metrics.set_meter_provider(meter_provider)

    return meter_provider


def _init_tracing(
    resource: Resource,
    enable_console: bool,
    enable_otlp: bool,
    otlp_endpoint: Optional[str],
) -> TracerProvider:
    """Initialize tracing with configured exporters."""
    tracer_provider = TracerProvider(resource=resource)

    # Console exporter for debugging
    if enable_console:
        console_processor = BatchSpanProcessor(ConsoleSpanExporter())
        tracer_provider.add_span_processor(console_processor)
        logger.info("✓ Console trace exporter enabled")

    # OTLP exporter
    if enable_otlp and otlp_endpoint:
        # Endpoint already resolved and validated in init_telemetry
        otlp_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
        tracer_provider.add_span_processor(otlp_processor)
        logger.info(f"✓ OTLP trace exporter enabled (endpoint: {otlp_endpoint})")

    # Set global tracer provider
    trace.set_tracer_provider(tracer_provider)

    return tracer_provider


def instrument_fastapi(app: "FastAPI") -> None:
    """
    Instrument FastAPI app with OpenTelemetry.

    Args:
        app: FastAPI application instance
    """
    if not _initialized:
        logger.warning("Telemetry not initialized, call init_telemetry() first")
        return

    FastAPIInstrumentor.instrument_app(app)
    logger.info("✓ FastAPI instrumented with OpenTelemetry")


def get_meter(name: str = "qwenvert") -> metrics.Meter:
    """
    Get OpenTelemetry meter for creating metrics.

    Returns a no-op meter if telemetry not initialized.

    Args:
        name: Meter name (typically module or component name)

    Returns:
        OpenTelemetry Meter instance (no-op if not initialized)

    Example:
        Create a counter:
            >>> meter = get_meter("my.component")
            >>> request_counter = meter.create_counter(
            ...     name="http.server.requests",
            ...     description="Total HTTP requests",
            ...     unit="request"
            ... )
            >>> request_counter.add(1, {"method": "GET", "status": 200})

        Create a histogram:
            >>> latency_histogram = meter.create_histogram(
            ...     name="http.server.request.duration",
            ...     description="Request duration",
            ...     unit="ms"
            ... )
            >>> latency_histogram.record(150.5, {"method": "POST"})

        Create an observable gauge:
            >>> def observe_memory():
            ...     import psutil
            ...     return [Observation(value=psutil.virtual_memory().percent)]
            >>>
            >>> meter.create_observable_gauge(
            ...     name="system.memory.utilization",
            ...     description="Memory usage",
            ...     unit="1",
            ...     callbacks=[observe_memory]
            ... )
    """
    if not _initialized:
        logger.warning("Telemetry not initialized, returning no-op meter")

    return metrics.get_meter(name)


def get_tracer(name: str = "qwenvert") -> trace.Tracer:
    """
    Get OpenTelemetry tracer for creating spans.

    Returns a no-op tracer if telemetry not initialized.

    Args:
        name: Tracer name (typically module or component name)

    Returns:
        OpenTelemetry Tracer instance (no-op if not initialized)

    Example:
        Basic span:
            >>> tracer = get_tracer("my.component")
            >>> with tracer.start_as_current_span("my.operation") as span:
            ...     span.set_attribute("key", "value")
            ...     # Your code here
            ...     pass

        Nested spans:
            >>> with tracer.start_as_current_span("outer") as outer:
            ...     outer.set_attribute("operation", "process_request")
            ...     with tracer.start_as_current_span("inner") as inner:
            ...         inner.set_attribute("sub_operation", "fetch_data")
            ...         # Inner operation
            ...         pass
            ...     # Outer operation continues
            ...     pass

        Error handling:
            >>> from opentelemetry.trace import Status, StatusCode
            >>> with tracer.start_as_current_span("risky_operation") as span:
            ...     try:
            ...         # Your code
            ...         pass
            ...     except Exception as e:
            ...         span.set_status(Status(StatusCode.ERROR, str(e)))
            ...         span.record_exception(e)
            ...         raise
    """
    if not _initialized:
        logger.warning("Telemetry not initialized, returning no-op tracer")

    return trace.get_tracer(name)


def shutdown_telemetry() -> None:
    """
    Shutdown telemetry and flush any pending data.

    This function is idempotent - safe to call multiple times.
    Always call before application exit to ensure all metrics
    and traces are flushed to exporters.

    Example:
        Graceful shutdown:
            >>> from qwenvert.telemetry import init_telemetry, shutdown_telemetry
            >>> init_telemetry(service_name="my-service")
            >>> # ... application code ...
            >>> shutdown_telemetry()

        With signal handling:
            >>> import signal
            >>> import sys
            >>>
            >>> def signal_handler(sig, frame):
            ...     print("Shutting down...")
            ...     shutdown_telemetry()
            ...     sys.exit(0)
            >>>
            >>> signal.signal(signal.SIGINT, signal_handler)
            >>> signal.signal(signal.SIGTERM, signal_handler)

        Context manager pattern:
            >>> class TelemetryContext:
            ...     def __enter__(self):
            ...         init_telemetry(service_name="my-service")
            ...         return self
            ...     def __exit__(self, *args):
            ...         shutdown_telemetry()
            >>>
            >>> with TelemetryContext():
            ...     # Application code
            ...     pass
    """
    global _initialized, _meter_provider, _tracer_provider  # noqa: PLW0603

    if not _initialized:
        return

    try:
        # Uninstrument HTTP libraries
        try:
            HTTPXClientInstrumentor().uninstrument()
        except Exception as e:
            logger.debug(f"HTTPX uninstrumentation skipped: {e}")

        # Shutdown providers with individual error handling
        if _meter_provider:
            try:
                _meter_provider.shutdown()
                logger.info("✓ Metrics provider shut down")
            except Exception as e:
                logger.warning(
                    f"Error shutting down metrics provider: {e}", exc_info=True
                )

        if _tracer_provider:
            try:
                _tracer_provider.shutdown()
                logger.info("✓ Tracer provider shut down")
            except Exception as e:
                logger.warning(
                    f"Error shutting down tracer provider: {e}", exc_info=True
                )
    finally:
        # Always reset state even if shutdown fails
        _initialized = False
        _meter_provider = None
        _tracer_provider = None


# Environment variable configuration helper
def init_from_env() -> None:
    """
    Initialize telemetry from environment variables.

    Follows 12-factor app configuration pattern. If OTEL_EXPORTER_OTLP_ENDPOINT
    is set, OTLP export is automatically enabled.

    Environment variables:
        OTEL_SERVICE_NAME: Service name (default: qwenvert)
        OTEL_SERVICE_VERSION: Service version (default: 0.1.0)
        OTEL_EXPORTER_CONSOLE: Enable console exporter (default: false)
        OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (enables OTLP if set)
        OTEL_EXPORTER_PROMETHEUS: Enable Prometheus (default: false)
        OTEL_EXPORTER_PROMETHEUS_PORT: Prometheus port (default: 9464)

    Security:
        OTLP endpoints are validated as localhost-only.
        External endpoints raise ValueError.

    Example:
        Basic usage:
            >>> import os
            >>> os.environ["OTEL_SERVICE_NAME"] = "my-service"
            >>> init_from_env()

        Enable OTLP export:
            >>> import os
            >>> os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "localhost:4317"
            >>> init_from_env()  # OTLP automatically enabled

        Enable console debugging:
            >>> import os
            >>> os.environ["OTEL_EXPORTER_CONSOLE"] = "true"
            >>> init_from_env()

        Docker/Kubernetes deployment:
            In docker-compose.yml:
                environment:
                  - OTEL_SERVICE_NAME=qwenvert
                  - OTEL_EXPORTER_OTLP_ENDPOINT=otel-collector:4317

            In application:
                >>> init_from_env()  # Reads from environment
    """
    service_name = os.getenv("OTEL_SERVICE_NAME", "qwenvert")
    service_version = os.getenv("OTEL_SERVICE_VERSION", "0.1.0")
    enable_console = os.getenv("OTEL_EXPORTER_CONSOLE", "false").lower() == "true"

    # Check which exporters are enabled
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    enable_otlp = otlp_endpoint is not None

    prometheus_port_str = os.getenv("OTEL_EXPORTER_PROMETHEUS_PORT", "9464")
    enable_prometheus = os.getenv("OTEL_EXPORTER_PROMETHEUS", "false").lower() == "true"

    try:
        prometheus_port = int(prometheus_port_str)
    except ValueError:
        prometheus_port = 9464
        logger.warning(
            f"Invalid OTEL_EXPORTER_PROMETHEUS_PORT: {prometheus_port_str}, using default 9464"
        )

    init_telemetry(
        service_name=service_name,
        service_version=service_version,
        enable_console=enable_console,
        enable_otlp=enable_otlp,
        enable_prometheus=enable_prometheus,
        otlp_endpoint=otlp_endpoint,
        prometheus_port=prometheus_port,
    )
