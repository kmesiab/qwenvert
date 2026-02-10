"""
Unit tests for qwenvert.monitoring module.

Tests MetricsCollector, RequestMetrics, SystemMetrics, and PerformanceStats.
"""

import asyncio
import contextlib
import subprocess
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import psutil
import pytest

from qwenvert.monitoring import (
    MetricsCollector,
    PerformanceStats,
    RequestMetrics,
    SystemMetrics,
)


class TestDataClasses:
    """Test dataclass creation and attributes."""

    def test_request_metrics_creation(self):
        """Test RequestMetrics dataclass."""
        metric = RequestMetrics(
            timestamp=datetime.now(),
            model="qwen2.5:7b",
            tokens_generated=100,
            latency_ms=250.5,
            tokens_per_second=45.2,
            streaming=True,
            status="success",
        )
        assert metric.model == "qwen2.5:7b"
        assert metric.tokens_generated == 100
        assert metric.latency_ms == 250.5
        assert metric.streaming is True
        assert metric.status == "success"

    def test_system_metrics_creation(self):
        """Test SystemMetrics dataclass."""
        metrics = SystemMetrics(
            memory_used_gb=8.5,
            memory_total_gb=16.0,
            memory_percent=53.1,
            cpu_percent=45.2,
            cpu_temp_celsius=65.0,
            qwenvert_memory_mb=150.0,
            backend_memory_mb=2048.0,
            backend_process_name="Ollama",
        )
        assert metrics.memory_used_gb == 8.5
        assert metrics.cpu_temp_celsius == 65.0
        assert metrics.backend_process_name == "Ollama"

    def test_performance_stats_defaults(self):
        """Test PerformanceStats with default values."""
        stats = PerformanceStats()
        assert stats.total_requests == 0
        assert stats.successful_requests == 0
        assert stats.failed_requests == 0
        assert stats.avg_latency_ms == 0.0


class TestMetricsCollectorInit:
    """Test MetricsCollector initialization."""

    def test_init_defaults(self):
        """Test initialization with default values."""
        collector = MetricsCollector()
        assert collector.adapter_url == "http://localhost:8088"
        assert len(collector.request_history) == 0
        assert collector.start_time > 0
        assert collector._last_check_time > 0
        assert collector._last_request_count == 0

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        collector = MetricsCollector(
            adapter_url="http://localhost:9000",
            history_size=50,
        )
        assert collector.adapter_url == "http://localhost:9000"
        assert collector.request_history.maxlen == 50

    def test_init_history_size(self):
        """Test that history size is respected."""
        collector = MetricsCollector(history_size=3)

        # Add 5 metrics, only last 3 should remain
        for i in range(5):
            metric = RequestMetrics(
                timestamp=datetime.now(),
                model=f"model-{i}",
                tokens_generated=100,
                latency_ms=100.0,
                tokens_per_second=50.0,
                streaming=False,
                status="success",
            )
            collector.request_history.append(metric)

        assert len(collector.request_history) == 3
        assert collector.request_history[0].model == "model-2"


@pytest.mark.asyncio
class TestSystemMetrics:
    """Test system metrics collection."""

    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    @patch("psutil.process_iter")
    async def test_collect_system_metrics_basic(
        self, mock_process_iter, mock_cpu_percent, mock_virtual_memory
    ):
        """Test basic system metrics collection."""
        # Mock memory
        mock_memory = MagicMock()
        mock_memory.used = 8 * (1024**3)  # 8 GB
        mock_memory.total = 16 * (1024**3)  # 16 GB
        mock_memory.percent = 50.0
        mock_virtual_memory.return_value = mock_memory

        # Mock CPU
        mock_cpu_percent.return_value = 45.5

        # Mock empty process list
        mock_process_iter.return_value = []

        collector = MetricsCollector()

        with patch.object(collector, "_get_cpu_temperature", return_value=None):
            metrics = await collector.collect_system_metrics()

        assert metrics.memory_used_gb == 8.0
        assert metrics.memory_total_gb == 16.0
        assert metrics.memory_percent == 50.0
        assert metrics.cpu_percent == 45.5
        assert metrics.cpu_temp_celsius is None

    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    @patch("psutil.process_iter")
    async def test_collect_system_metrics_with_processes(
        self, mock_process_iter, mock_cpu_percent, mock_virtual_memory
    ):
        """Test system metrics collection with qwenvert and backend processes."""
        # Mock memory
        mock_memory = MagicMock()
        mock_memory.used = 8 * (1024**3)
        mock_memory.total = 16 * (1024**3)
        mock_memory.percent = 50.0
        mock_virtual_memory.return_value = mock_memory

        # Mock CPU
        mock_cpu_percent.return_value = 45.5

        # Mock processes
        mock_qwenvert_proc = MagicMock()
        mock_qwenvert_proc.info = {
            "pid": 1234,
            "name": "python3",
            "memory_info": MagicMock(rss=150 * 1024 * 1024),  # 150 MB
        }
        mock_qwenvert_proc.cmdline.return_value = [
            "python3",
            "/path/to/qwenvert",
            "serve",
        ]

        mock_ollama_proc = MagicMock()
        mock_ollama_proc.info = {
            "pid": 5678,
            "name": "ollama",
            "memory_info": MagicMock(rss=2048 * 1024 * 1024),  # 2048 MB
        }

        mock_process_iter.return_value = [mock_qwenvert_proc, mock_ollama_proc]

        collector = MetricsCollector()

        with patch.object(collector, "_get_cpu_temperature", return_value=65.0):
            metrics = await collector.collect_system_metrics()

        assert metrics.qwenvert_memory_mb == 150.0
        assert metrics.backend_memory_mb == 2048.0
        assert metrics.backend_process_name == "Ollama"
        assert metrics.cpu_temp_celsius == 65.0

    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    @patch("psutil.process_iter")
    async def test_collect_system_metrics_llama_backend(
        self, mock_process_iter, mock_cpu_percent, mock_virtual_memory
    ):
        """Test system metrics with llama.cpp backend."""
        # Mock memory and CPU
        mock_memory = MagicMock()
        mock_memory.used = 8 * (1024**3)
        mock_memory.total = 16 * (1024**3)
        mock_memory.percent = 50.0
        mock_virtual_memory.return_value = mock_memory
        mock_cpu_percent.return_value = 45.5

        # Mock llama process
        mock_llama_proc = MagicMock()
        mock_llama_proc.info = {
            "pid": 9999,
            "name": "llama-server",
            "memory_info": MagicMock(rss=1024 * 1024 * 1024),  # 1024 MB
        }

        mock_process_iter.return_value = [mock_llama_proc]

        collector = MetricsCollector()

        with patch.object(collector, "_get_cpu_temperature", return_value=None):
            metrics = await collector.collect_system_metrics()

        assert metrics.backend_memory_mb == 1024.0
        assert metrics.backend_process_name == "llama.cpp"

    @patch("psutil.virtual_memory")
    @patch("psutil.cpu_percent")
    @patch("psutil.process_iter")
    async def test_collect_system_metrics_process_error(
        self, mock_process_iter, mock_cpu_percent, mock_virtual_memory
    ):
        """Test system metrics collection handles process errors."""
        # Mock memory and CPU
        mock_memory = MagicMock()
        mock_memory.used = 8 * (1024**3)
        mock_memory.total = 16 * (1024**3)
        mock_memory.percent = 50.0
        mock_virtual_memory.return_value = mock_memory
        mock_cpu_percent.return_value = 45.5

        # Mock process that raises exception
        mock_proc = MagicMock()
        mock_proc.info = {"name": "python3"}
        mock_proc.cmdline.side_effect = psutil.NoSuchProcess(1234)

        mock_process_iter.return_value = [mock_proc]

        collector = MetricsCollector()

        with patch.object(collector, "_get_cpu_temperature", return_value=None):
            metrics = await collector.collect_system_metrics()

        # Should complete without error
        assert metrics.memory_used_gb == 8.0
        assert metrics.qwenvert_memory_mb is None


class TestCPUTemperature:
    """Test CPU temperature retrieval."""

    def test_get_cpu_temperature_non_darwin(self):
        """Test CPU temperature on non-macOS systems."""
        collector = MetricsCollector()

        with patch("platform.system", return_value="Linux"):
            temp = collector._get_cpu_temperature()

        assert temp is None

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_get_cpu_temperature_darwin_success(self, mock_run, mock_system):
        """Test successful CPU temperature retrieval on macOS."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
CPU die temperature: 65.5 C
GPU die temperature: 55.0 C
"""
        mock_run.return_value = mock_result

        collector = MetricsCollector()
        temp = collector._get_cpu_temperature()

        assert temp == 65.5

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_get_cpu_temperature_darwin_no_permission(self, mock_run, mock_system):
        """Test CPU temperature retrieval fails without sudo."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        collector = MetricsCollector()
        temp = collector._get_cpu_temperature()

        assert temp is None

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_get_cpu_temperature_darwin_timeout(self, mock_run, mock_system):
        """Test CPU temperature handles timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 2)

        collector = MetricsCollector()
        temp = collector._get_cpu_temperature()

        assert temp is None

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_get_cpu_temperature_darwin_invalid_output(self, mock_run, mock_system):
        """Test CPU temperature handles invalid output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Invalid output"
        mock_run.return_value = mock_result

        collector = MetricsCollector()
        temp = collector._get_cpu_temperature()

        assert temp is None


@pytest.mark.asyncio
class TestAdapterHealth:
    """Test adapter health checking."""

    async def test_check_adapter_health_success(self):
        """Test successful health check."""
        collector = MetricsCollector()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            is_healthy = await collector.check_adapter_health()

        assert is_healthy is True

    async def test_check_adapter_health_failure(self):
        """Test health check with non-200 response."""
        collector = MetricsCollector()

        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            is_healthy = await collector.check_adapter_health()

        assert is_healthy is False

    async def test_check_adapter_health_exception(self):
        """Test health check handles exceptions."""
        collector = MetricsCollector()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            is_healthy = await collector.check_adapter_health()

        assert is_healthy is False


class TestRequestMetrics:
    """Test request metrics tracking."""

    def test_add_request_metric(self):
        """Test adding request metrics."""
        collector = MetricsCollector()

        metric = RequestMetrics(
            timestamp=datetime.now(),
            model="qwen2.5:7b",
            tokens_generated=100,
            latency_ms=250.5,
            tokens_per_second=45.2,
            streaming=True,
            status="success",
        )

        collector.add_request_metric(metric)

        assert len(collector.request_history) == 1
        assert collector.request_history[0].model == "qwen2.5:7b"

    def test_get_performance_stats_empty(self):
        """Test performance stats with no request history."""
        collector = MetricsCollector()

        stats = collector.get_performance_stats()

        assert stats.total_requests == 0
        assert stats.successful_requests == 0
        assert stats.failed_requests == 0
        assert stats.total_tokens == 0
        assert stats.avg_latency_ms == 0.0
        assert stats.uptime_seconds > 0

    def test_get_performance_stats_with_requests(self):
        """Test performance stats with request history."""
        collector = MetricsCollector()

        # Add successful requests
        for i in range(3):
            metric = RequestMetrics(
                timestamp=datetime.now(),
                model="qwen2.5:7b",
                tokens_generated=100,
                latency_ms=200.0 + i * 50,  # 200, 250, 300
                tokens_per_second=50.0,
                streaming=False,
                status="success",
            )
            collector.add_request_metric(metric)

        # Add failed request
        failed_metric = RequestMetrics(
            timestamp=datetime.now(),
            model="qwen2.5:7b",
            tokens_generated=0,
            latency_ms=100.0,
            tokens_per_second=0.0,
            streaming=False,
            status="error",
        )
        collector.add_request_metric(failed_metric)

        stats = collector.get_performance_stats()

        assert stats.total_requests == 4
        assert stats.successful_requests == 3
        assert stats.failed_requests == 1
        assert stats.total_tokens == 300
        assert stats.avg_latency_ms == 212.5  # (200+250+300+100)/4 = 850/4
        assert stats.avg_tokens_per_second == 50.0  # Only successful requests
        assert stats.min_latency_ms == 100.0
        assert stats.max_latency_ms == 300.0

    def test_get_performance_stats_no_throughput(self):
        """Test performance stats when all requests have zero throughput."""
        collector = MetricsCollector()

        metric = RequestMetrics(
            timestamp=datetime.now(),
            model="qwen2.5:7b",
            tokens_generated=0,
            latency_ms=100.0,
            tokens_per_second=0.0,
            streaming=False,
            status="error",
        )
        collector.add_request_metric(metric)

        stats = collector.get_performance_stats()

        assert stats.avg_tokens_per_second == 0.0

    def test_get_recent_requests(self):
        """Test getting recent requests."""
        collector = MetricsCollector()

        # Add 15 requests
        for i in range(15):
            metric = RequestMetrics(
                timestamp=datetime.now(),
                model=f"model-{i}",
                tokens_generated=100,
                latency_ms=200.0,
                tokens_per_second=50.0,
                streaming=False,
                status="success",
            )
            collector.add_request_metric(metric)

        # Get last 10
        recent = collector.get_recent_requests(count=10)

        assert len(recent) == 10
        assert recent[0].model == "model-5"
        assert recent[-1].model == "model-14"

    def test_get_recent_requests_fewer_than_requested(self):
        """Test getting recent requests when fewer exist."""
        collector = MetricsCollector()

        # Add only 3 requests
        for i in range(3):
            metric = RequestMetrics(
                timestamp=datetime.now(),
                model=f"model-{i}",
                tokens_generated=100,
                latency_ms=200.0,
                tokens_per_second=50.0,
                streaming=False,
                status="success",
            )
            collector.add_request_metric(metric)

        # Request 10
        recent = collector.get_recent_requests(count=10)

        assert len(recent) == 3


@pytest.mark.asyncio
class TestMonitorLoop:
    """Test continuous monitoring loop."""

    async def test_monitor_loop_single_iteration(self):
        """Test monitor loop runs one iteration."""
        collector = MetricsCollector()

        mock_system_metrics = SystemMetrics(
            memory_used_gb=8.0,
            memory_total_gb=16.0,
            memory_percent=50.0,
            cpu_percent=45.5,
        )

        with (
            patch.object(
                collector, "collect_system_metrics", return_value=mock_system_metrics
            ),
            patch.object(collector, "check_adapter_health", return_value=True),
        ):
            # Run one iteration then cancel
            task = asyncio.create_task(collector.monitor_loop(interval=0.1))
            await asyncio.sleep(0.15)
            task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_monitor_loop_handles_exception(self):
        """Test monitor loop handles exceptions and continues."""
        collector = MetricsCollector()

        call_count = 0

        async def mock_collect_with_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = "Test error"
                raise Exception(msg)
            return SystemMetrics(
                memory_used_gb=8.0,
                memory_total_gb=16.0,
                memory_percent=50.0,
                cpu_percent=45.5,
            )

        with (
            patch.object(
                collector, "collect_system_metrics", side_effect=mock_collect_with_error
            ),
            patch.object(collector, "check_adapter_health", return_value=True),
        ):
            # Run loop and let it handle the error
            task = asyncio.create_task(collector.monitor_loop(interval=0.1))
            await asyncio.sleep(0.25)
            task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await task

            # Should have been called at least twice (once with error, once success)
            assert call_count >= 2
