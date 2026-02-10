"""
Real-time monitoring and metrics for qwenvert.

Collects performance metrics, thermal data, and request history
for display in the monitor dashboard. Now OpenTelemetry-compliant.
"""

import asyncio
import logging
import platform
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Optional

import httpx
import psutil
from opentelemetry.metrics import CallbackOptions, Observation

from .telemetry import get_meter


logger = logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for a single request."""

    timestamp: datetime
    model: str
    tokens_generated: int
    latency_ms: float
    tokens_per_second: float
    streaming: bool
    status: str  # "success", "error", "timeout"


@dataclass
class SystemMetrics:
    """System-level metrics."""

    # Memory
    memory_used_gb: float
    memory_total_gb: float
    memory_percent: float

    # CPU
    cpu_percent: float
    cpu_temp_celsius: Optional[float] = None

    # Processes
    qwenvert_memory_mb: Optional[float] = None
    backend_memory_mb: Optional[float] = None
    backend_process_name: Optional[str] = None


@dataclass
class PerformanceStats:
    """Aggregate performance statistics."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    avg_latency_ms: float = 0.0
    avg_tokens_per_second: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    uptime_seconds: float = 0.0


class MetricsCollector:
    """
    Collects real-time metrics from qwenvert adapter and system.

    Now OpenTelemetry-compliant with semantic conventions for:
    - gen_ai.client.token.usage (tokens generated)
    - http.server.request.duration (request latency)
    - system.cpu.utilization (CPU usage)
    - system.memory.utilization (memory usage)

    Monitors:
    - Request performance (latency, throughput)
    - System resources (CPU, memory, temperature)
    - Process health (qwenvert, Ollama/llama.cpp)
    """

    def __init__(
        self,
        adapter_url: str = "http://localhost:8088",
        history_size: int = 100,
        enable_otel: bool = False,
    ):
        """
        Initialize metrics collector.

        Args:
            adapter_url: URL of qwenvert adapter
            history_size: Number of requests to keep in history
            enable_otel: Enable OpenTelemetry metrics (default: True)
        """
        self.adapter_url = adapter_url
        self.request_history: Deque[RequestMetrics] = deque(maxlen=history_size)
        self.start_time = time.time()

        # For tracking real-time requests
        self._last_check_time = time.time()
        self._last_request_count = 0

        # Cached system metrics (updated in background, non-blocking reads)
        self._cached_cpu = 0.0
        self._cached_memory = 0.0
        self._cached_temp: Optional[float] = None

        # OpenTelemetry metrics
        self.enable_otel = enable_otel
        if enable_otel:
            self._init_otel_metrics()

    def _init_otel_metrics(self) -> None:
        """Initialize OpenTelemetry metrics following semantic conventions."""
        meter = get_meter("qwenvert.monitoring")

        # Gen AI semantic conventions
        # https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/
        self.token_usage_counter = meter.create_counter(
            name="gen_ai.client.token.usage",
            description="Number of tokens used in prompts and completions",
            unit="token",
        )

        # HTTP semantic conventions
        # https://opentelemetry.io/docs/specs/semconv/http/http-metrics/
        self.request_duration_histogram = meter.create_histogram(
            name="http.server.request.duration",
            description="Duration of HTTP requests",
            unit="s",  # OTEL spec requires seconds
        )

        # System semantic conventions
        # https://opentelemetry.io/docs/specs/semconv/system/system-metrics/
        meter.create_observable_gauge(
            name="system.cpu.utilization",
            description="CPU utilization ratio",
            unit="1",  # ratio 0-1
            callbacks=[self._observe_cpu_utilization],
        )

        meter.create_observable_gauge(
            name="system.memory.utilization",
            description="Memory utilization ratio",
            unit="1",  # ratio 0-1
            callbacks=[self._observe_memory_utilization],
        )

        meter.create_observable_gauge(
            name="system.cpu.temperature",
            description="CPU temperature in Celsius",
            unit="Cel",
            callbacks=[self._observe_cpu_temperature],
        )

        # Request status counter
        self.request_status_counter = meter.create_counter(
            name="qwenvert.request.count",
            description="Total number of requests by status",
            unit="request",
        )

        # Tokens per second gauge
        meter.create_observable_gauge(
            name="gen_ai.client.token.throughput",
            description="Token generation throughput",
            unit="token/s",
            callbacks=[self._observe_token_throughput],
        )

        logger.info("✓ OpenTelemetry metrics initialized")

    def _observe_cpu_utilization(self, options: CallbackOptions) -> list[Observation]:
        """
        Observable callback for CPU utilization (non-blocking).

        Uses cached value updated by background task to avoid blocking
        the metric export thread.
        """
        try:
            # Use cached value (non-blocking)
            return [Observation(value=self._cached_cpu / 100.0)]
        except Exception as e:
            logger.error(f"Error observing CPU utilization: {e}")
            return []

    def _observe_memory_utilization(
        self, options: CallbackOptions
    ) -> list[Observation]:
        """
        Observable callback for memory utilization (non-blocking).

        Uses cached value updated by background task.
        """
        try:
            # Use cached value (non-blocking)
            return [Observation(value=self._cached_memory / 100.0)]
        except Exception as e:
            logger.error(f"Error observing memory utilization: {e}")
            return []

    def _observe_cpu_temperature(self, options: CallbackOptions) -> list[Observation]:
        """
        Observable callback for CPU temperature (non-blocking).

        Uses cached value updated by background task.
        """
        try:
            if self._cached_temp is not None:
                return [Observation(value=self._cached_temp)]
        except Exception as e:
            logger.error(f"Error observing CPU temperature: {e}")

        return []

    def _observe_token_throughput(self, options: CallbackOptions) -> list[Observation]:
        """Observable callback for token throughput."""
        try:
            stats = self.get_performance_stats()
            return [Observation(value=stats.avg_tokens_per_second)]
        except Exception as e:
            logger.error(f"Error observing token throughput: {e}")
            return []

    async def collect_system_metrics(self) -> SystemMetrics:
        """
        Collect current system metrics.

        Returns:
            SystemMetrics with current system state
        """
        # Memory
        memory = psutil.virtual_memory()

        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Try to get CPU temperature (macOS specific)
        cpu_temp = self._get_cpu_temperature()

        # Find qwenvert and backend processes
        qwenvert_mem = None
        backend_mem = None
        backend_name = None

        for proc in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                name = proc.info["name"].lower()
                mem_info = proc.info["memory_info"]

                # Skip if memory info not available
                if mem_info is None:
                    continue

                if "python" in name:
                    # Check if it's running qwenvert
                    cmdline = proc.cmdline()
                    if any("qwenvert" in arg for arg in cmdline):
                        qwenvert_mem = mem_info.rss / (1024 * 1024)

                elif "ollama" in name:
                    backend_mem = mem_info.rss / (1024 * 1024)
                    backend_name = "Ollama"

                elif "llama" in name or "server" in name:
                    backend_mem = mem_info.rss / (1024 * 1024)
                    backend_name = "llama.cpp"

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return SystemMetrics(
            memory_used_gb=memory.used / (1024**3),
            memory_total_gb=memory.total / (1024**3),
            memory_percent=memory.percent,
            cpu_percent=cpu_percent,
            cpu_temp_celsius=cpu_temp,
            qwenvert_memory_mb=qwenvert_mem,
            backend_memory_mb=backend_mem,
            backend_process_name=backend_name,
        )

    def _get_cpu_temperature(self) -> Optional[float]:
        """
        Get CPU temperature on macOS.

        Returns:
            Temperature in Celsius, or None if unavailable
        """
        if platform.system() != "Darwin":
            return None

        try:
            # Try powermetrics (requires sudo, but may work)
            result = subprocess.run(
                [
                    "sudo",
                    "-n",
                    "powermetrics",
                    "--samplers",
                    "smc",
                    "-i",
                    "1",
                    "-n",
                    "1",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "CPU die temperature" in line:
                        # Extract temperature value
                        temp_str = line.split(":")[-1].strip().split()[0]
                        return float(temp_str)

        except (subprocess.TimeoutExpired, subprocess.SubprocessError, ValueError):
            pass

        return None

    async def check_adapter_health(self) -> bool:
        """
        Check if adapter is running and healthy.

        Returns:
            True if adapter is reachable, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.adapter_url}/health",
                    timeout=2.0,
                )
                return response.status_code == 200
        except Exception:
            return False

    def add_request_metric(self, metric: RequestMetrics) -> None:
        """
        Add a request metric to history and record to OpenTelemetry.

        Args:
            metric: Request metrics to add
        """
        self.request_history.append(metric)

        # Record to OpenTelemetry
        if self.enable_otel:
            # Map internal status to OTEL-compliant finish reasons
            # https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/
            finish_reason_map = {
                "success": "stop",  # Completion finished naturally
                "timeout": "timeout",  # Request timed out
                "error": "error",  # Error occurred
            }
            finish_reason = finish_reason_map.get(metric.status, "stop")

            # Record token usage with semantic conventions
            self.token_usage_counter.add(
                metric.tokens_generated,
                attributes={
                    "gen_ai.operation.name": "completion",
                    "gen_ai.request.model": metric.model,
                    "gen_ai.response.finish_reasons": [finish_reason],
                },
            )

            # Map internal status to HTTP status codes
            status_code_map = {
                "success": 200,
                "timeout": 504,  # Gateway Timeout
                "error": 500,  # Internal Server Error
            }
            status_code = status_code_map.get(metric.status, 500)

            # Record request duration (convert ms to seconds per OTEL spec)
            self.request_duration_histogram.record(
                metric.latency_ms / 1000.0,
                attributes={
                    "http.request.method": "POST",
                    "http.route": "/v1/messages",
                    "http.response.status_code": status_code,
                },
            )

            # Record request status
            self.request_status_counter.add(
                1,
                attributes={
                    "status": metric.status,
                    "model": metric.model,
                    "streaming": str(metric.streaming).lower(),
                },
            )

    def get_performance_stats(self) -> PerformanceStats:
        """
        Calculate aggregate performance statistics.

        Returns:
            PerformanceStats with aggregated metrics
        """
        if not self.request_history:
            return PerformanceStats(uptime_seconds=time.time() - self.start_time)

        total = len(self.request_history)
        successful = sum(1 for r in self.request_history if r.status == "success")
        failed = sum(1 for r in self.request_history if r.status != "success")

        total_tokens = sum(r.tokens_generated for r in self.request_history)
        latencies = [r.latency_ms for r in self.request_history]
        throughputs = [
            r.tokens_per_second for r in self.request_history if r.tokens_per_second > 0
        ]

        return PerformanceStats(
            total_requests=total,
            successful_requests=successful,
            failed_requests=failed,
            total_tokens=total_tokens,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
            avg_tokens_per_second=(
                sum(throughputs) / len(throughputs) if throughputs else 0.0
            ),
            min_latency_ms=min(latencies) if latencies else 0.0,
            max_latency_ms=max(latencies) if latencies else 0.0,
            uptime_seconds=time.time() - self.start_time,
        )

    def get_recent_requests(self, count: int = 10) -> list[RequestMetrics]:
        """
        Get most recent requests.

        Args:
            count: Number of recent requests to return

        Returns:
            List of recent RequestMetrics
        """
        return list(self.request_history)[-count:]

    async def monitor_loop(self, interval: float = 1.0):
        """
        Continuous monitoring loop.

        Updates cached system metrics for non-blocking observable callbacks
        and checks adapter health.

        Args:
            interval: Update interval in seconds
        """
        while True:
            try:
                # Update cached system metrics (for non-blocking observable callbacks)
                if self.enable_otel:
                    try:
                        self._cached_cpu = psutil.cpu_percent(interval=0.1)
                        self._cached_memory = psutil.virtual_memory().percent
                        self._cached_temp = self._get_cpu_temperature()
                    except Exception as e:
                        logger.debug(f"Error updating cached system metrics: {e}")

                # Collect system metrics
                system_metrics = await self.collect_system_metrics()

                # Check adapter health
                is_healthy = await self.check_adapter_health()

                # Could emit metrics here (to Prometheus, logs, etc.)
                logger.debug(f"System: {system_metrics}, Healthy: {is_healthy}")

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                await asyncio.sleep(interval)
