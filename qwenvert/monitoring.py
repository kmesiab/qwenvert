"""
Real-time monitoring and metrics for qwenvert.

Collects performance metrics, thermal data, and request history
for display in the monitor dashboard.
"""
from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx
import psutil


if TYPE_CHECKING:
    from datetime import datetime


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
    cpu_temp_celsius: float | None = None

    # Processes
    qwenvert_memory_mb: float | None = None
    backend_memory_mb: float | None = None
    backend_process_name: str | None = None


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

    Monitors:
    - Request performance (latency, throughput)
    - System resources (CPU, memory, temperature)
    - Process health (qwenvert, Ollama/llama.cpp)
    """

    def __init__(
        self,
        adapter_url: str = "http://localhost:8088",
        history_size: int = 100,
    ) -> None:
        """
        Initialize metrics collector.

        Args:
            adapter_url: URL of qwenvert adapter
            history_size: Number of requests to keep in history
        """
        self.adapter_url = adapter_url
        self.request_history: deque[RequestMetrics] = deque(maxlen=history_size)
        self.start_time = time.time()

        # For tracking real-time requests
        self._last_check_time = time.time()
        self._last_request_count = 0

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

                if "python" in name:
                    # Check if it's running qwenvert
                    cmdline = proc.cmdline()
                    if any("qwenvert" in arg for arg in cmdline):
                        qwenvert_mem = proc.info["memory_info"].rss / (1024 * 1024)

                elif "ollama" in name:
                    backend_mem = proc.info["memory_info"].rss / (1024 * 1024)
                    backend_name = "Ollama"

                elif "llama" in name or "server" in name:
                    backend_mem = proc.info["memory_info"].rss / (1024 * 1024)
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

    def _get_cpu_temperature(self) -> float | None:
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
        Add a request metric to history.

        Args:
            metric: Request metrics to add
        """
        self.request_history.append(metric)

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

    async def monitor_loop(self, interval: float = 1.0) -> None:
        """
        Continuous monitoring loop.

        Args:
            interval: Update interval in seconds
        """
        while True:
            try:
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
