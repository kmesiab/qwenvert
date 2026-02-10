"""
OpenTelemetry instrumentation and configuration for qwenvert.

Provides OpenTelemetry-compliant metrics, tracing, and exporters
following semantic conventions for HTTP, system, and gen_ai.
"""

import logging
import os
from typing import Optional

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
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


def _validate_localhost_endpoint(endpoint: str) -> str:
    """
    Validate that endpoint is localhost-only for security.

    Args:
        endpoint: Endpoint URL to validate

    Returns:
        The endpoint if valid

    Raises:
        ValueError: If endpoint is not localhost

    Security: Prevents data exfiltration to external collectors
    """
    endpoint_lower = endpoint.lower()

    # Allow localhost, 127.0.0.1, ::1, and no hostname (defaults to localhost)
    allowed_patterns = ["localhost", "127.0.0.1", "::1"]

    # Check if endpoint contains any allowed pattern
    if not any(pattern in endpoint_lower for pattern in allowed_patterns):
        msg = (
            f"Security: OTLP endpoint must be localhost for data privacy. "
            f"Got: {endpoint}. "
            f"Allowed: localhost, 127.0.0.1, ::1"
        )
        logger.error(msg)
        raise ValueError(msg)

    logger.info(f"✓ Validated localhost endpoint: {endpoint}")
    return endpoint


def init_telemetry(
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

    Args:
        service_name: Service name for telemetry
        service_version: Service version
        enable_console: Enable console exporters for debugging
        enable_otlp: Enable OTLP exporters
        enable_prometheus: Enable Prometheus exporter
        otlp_endpoint: OTLP collector endpoint (default: localhost:4317)
        prometheus_port: Prometheus metrics port (default: 9464)
    """
    global _initialized, _meter_provider, _tracer_provider

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

    # Initialize metrics
    _meter_provider = _init_metrics(
        resource=resource,
        enable_console=enable_console,
        enable_otlp=enable_otlp,
        enable_prometheus=enable_prometheus,
        otlp_endpoint=otlp_endpoint,
        prometheus_port=prometheus_port,
    )

    # Initialize tracing
    _tracer_provider = _init_tracing(
        resource=resource,
        enable_console=enable_console,
        enable_otlp=enable_otlp,
        otlp_endpoint=otlp_endpoint,
    )

    # Instrument HTTP libraries
    HTTPXClientInstrumentor().instrument()

    _initialized = True
    logger.info(f"✓ OpenTelemetry initialized for {service_name} v{service_version}")


def _init_metrics(
    resource: Resource,
    enable_console: bool,
    enable_otlp: bool,
    enable_prometheus: bool,
    otlp_endpoint: Optional[str],
    prometheus_port: int,
) -> MeterProvider:
    """Initialize metrics with configured exporters."""
    metric_readers = []

    # Console exporter for debugging
    if enable_console:
        console_reader = PeriodicExportingMetricReader(
            ConsoleMetricExporter(),
            export_interval_millis=60000,  # 60 seconds
        )
        metric_readers.append(console_reader)
        logger.info("✓ Console metric exporter enabled")

    # OTLP exporter for collectors (e.g., Jaeger, SigNoz)
    if enable_otlp:
        endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
        # Security: Validate endpoint is localhost-only
        endpoint = _validate_localhost_endpoint(endpoint)
        otlp_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=endpoint),
            export_interval_millis=60000,
        )
        metric_readers.append(otlp_reader)
        logger.info(f"✓ OTLP metric exporter enabled (endpoint: {endpoint})")

    # Prometheus exporter
    # Security Note: PrometheusMetricReader does NOT start an HTTP server.
    # It only prepares metrics for collection by an external Prometheus scraper.
    # No network port is opened by this reader.
    if enable_prometheus:
        prometheus_reader = PrometheusMetricReader()
        metric_readers.append(prometheus_reader)
        logger.info(f"✓ Prometheus exporter enabled (metrics available for collection)")
        logger.info("   Note: No HTTP server started - metrics must be scraped externally")

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
    if enable_otlp:
        endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
        # Security: Validate endpoint is localhost-only
        endpoint = _validate_localhost_endpoint(endpoint)
        otlp_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        tracer_provider.add_span_processor(otlp_processor)
        logger.info(f"✓ OTLP trace exporter enabled (endpoint: {endpoint})")

    # Set global tracer provider
    trace.set_tracer_provider(tracer_provider)

    return tracer_provider


def instrument_fastapi(app) -> None:
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

    Args:
        name: Meter name (typically module or component name)

    Returns:
        OpenTelemetry Meter instance
    """
    if not _initialized:
        logger.warning("Telemetry not initialized, returning no-op meter")

    return metrics.get_meter(name)


def get_tracer(name: str = "qwenvert") -> trace.Tracer:
    """
    Get OpenTelemetry tracer for creating spans.

    Args:
        name: Tracer name (typically module or component name)

    Returns:
        OpenTelemetry Tracer instance
    """
    if not _initialized:
        logger.warning("Telemetry not initialized, returning no-op tracer")

    return trace.get_tracer(name)


def shutdown_telemetry() -> None:
    """Shutdown telemetry and flush any pending data."""
    global _initialized, _meter_provider, _tracer_provider

    if not _initialized:
        return

    if _meter_provider:
        _meter_provider.shutdown()
        logger.info("✓ Metrics provider shut down")

    if _tracer_provider:
        _tracer_provider.shutdown()
        logger.info("✓ Tracer provider shut down")

    _initialized = False
    _meter_provider = None
    _tracer_provider = None


# Environment variable configuration helper
def init_from_env() -> None:
    """
    Initialize telemetry from environment variables.

    Environment variables:
    - OTEL_SERVICE_NAME: Service name (default: qwenvert)
    - OTEL_SERVICE_VERSION: Service version (default: 0.1.0)
    - OTEL_EXPORTER_CONSOLE: Enable console exporter (default: false)
    - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (default: localhost:4317)
    - OTEL_EXPORTER_PROMETHEUS_PORT: Prometheus port (default: 9464)
    - OTEL_METRICS_ENABLED: Enable metrics (default: true)
    - OTEL_TRACES_ENABLED: Enable traces (default: true)
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
        logger.warning(f"Invalid OTEL_EXPORTER_PROMETHEUS_PORT: {prometheus_port_str}, using default 9464")

    init_telemetry(
        service_name=service_name,
        service_version=service_version,
        enable_console=enable_console,
        enable_otlp=enable_otlp,
        enable_prometheus=enable_prometheus,
        otlp_endpoint=otlp_endpoint,
        prometheus_port=prometheus_port,
    )
