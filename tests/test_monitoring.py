"""
Tests for qwenvert monitoring and metrics collection.

OTEL-014: System metrics collection tests
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import psutil
import pytest

from qwenvert.monitoring import MetricsCollector, RequestMetrics, SystemMetrics


class TestSystemMetricsCollection:
    """OTEL-014: Test system metrics collection."""

    @pytest.mark.asyncio
    async def test_collect_system_metrics_basic(self):
        """Test basic system metrics collection."""
        collector = MetricsCollector(enable_otel=False)
        metrics = await collector.collect_system_metrics()

        # Verify basic metrics are collected
        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent >= 0.0
        assert metrics.memory_total_gb > 0.0
        assert metrics.memory_used_gb >= 0.0
        assert 0.0 <= metrics.memory_percent <= 100.0

    @pytest.mark.asyncio
    async def test_collect_system_metrics_memory_calculations(self):
        """Test memory metrics are reasonable."""
        collector = MetricsCollector(enable_otel=False)
        metrics = await collector.collect_system_metrics()

        # Memory used should be less than or equal to total
        assert metrics.memory_used_gb <= metrics.memory_total_gb

        # Memory percent should be reasonable (psutil calculates this including cache/buffers)
        # Just verify it's in a valid range
        assert 0.0 <= metrics.memory_percent <= 100.0

    @pytest.mark.asyncio
    async def test_collect_system_metrics_cpu_temp_optional(self):
        """Test CPU temperature is optional (may be None)."""
        collector = MetricsCollector(enable_otel=False)
        metrics = await collector.collect_system_metrics()

        # CPU temp may be None if not available
        if metrics.cpu_temp_celsius is not None:
            assert metrics.cpu_temp_celsius > 0.0
            # Reasonable temperature range (not running at 0°C or 200°C)
            assert 10.0 < metrics.cpu_temp_celsius < 120.0

    @pytest.mark.asyncio
    async def test_collect_system_metrics_process_discovery(self):
        """Test process discovery for qwenvert and backends."""
        collector = MetricsCollector(enable_otel=False)
        metrics = await collector.collect_system_metrics()

        # Process memory metrics are optional (may be None if not running)
        if metrics.qwenvert_memory_mb is not None:
            assert metrics.qwenvert_memory_mb > 0.0

        if metrics.backend_memory_mb is not None:
            assert metrics.backend_memory_mb > 0.0
            assert metrics.backend_process_name in ["Ollama", "llama.cpp"]

    @pytest.mark.asyncio
    async def test_collect_system_metrics_handles_psutil_errors(self):
        """Test graceful handling when psutil operations fail."""
        collector = MetricsCollector(enable_otel=False)

        # Mock psutil to raise an error
        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.side_effect = RuntimeError("Permission denied")

            # Should raise the error (not caught at this level)
            with pytest.raises(RuntimeError):
                await collector.collect_system_metrics()

    @pytest.mark.asyncio
    async def test_collect_system_metrics_handles_process_errors(self):
        """Test graceful handling of process iteration errors."""
        collector = MetricsCollector(enable_otel=False)

        # Mock process_iter to raise NoSuchProcess
        with patch("psutil.process_iter") as mock_iter:
            mock_proc = Mock()
            mock_proc.info = {"name": "python", "pid": 12345, "memory_info": None}
            mock_proc.cmdline.side_effect = psutil.NoSuchProcess(12345)

            mock_iter.return_value = [mock_proc]

            # Should handle error gracefully and return metrics
            metrics = await collector.collect_system_metrics()
            assert isinstance(metrics, SystemMetrics)

    @pytest.mark.asyncio
    async def test_collect_system_metrics_identifies_qwenvert_process(self):
        """Test identification of qwenvert process by command line."""
        collector = MetricsCollector(enable_otel=False)

        # Mock a qwenvert process
        with patch("psutil.process_iter") as mock_iter:
            mock_proc = Mock()
            mock_proc.info = {
                "name": "python3",
                "pid": 12345,
                "memory_info": Mock(rss=100 * 1024 * 1024),  # 100MB
            }
            mock_proc.cmdline.return_value = ["python3", "-m", "qwenvert"]

            mock_iter.return_value = [mock_proc]

            metrics = await collector.collect_system_metrics()

            # Should identify qwenvert process
            assert metrics.qwenvert_memory_mb is not None
            assert metrics.qwenvert_memory_mb > 0

    @pytest.mark.asyncio
    async def test_collect_system_metrics_identifies_ollama_process(self):
        """Test identification of Ollama backend process."""
        collector = MetricsCollector(enable_otel=False)

        # Mock an Ollama process
        with patch("psutil.process_iter") as mock_iter:
            mock_proc = Mock()
            mock_proc.info = {
                "name": "ollama",
                "pid": 23456,
                "memory_info": Mock(rss=500 * 1024 * 1024),  # 500MB
            }
            mock_proc.cmdline.return_value = ["ollama", "serve"]

            mock_iter.return_value = [mock_proc]

            metrics = await collector.collect_system_metrics()

            # Should identify Ollama process
            assert metrics.backend_memory_mb is not None
            assert metrics.backend_memory_mb > 0
            assert metrics.backend_process_name == "Ollama"

    @pytest.mark.asyncio
    async def test_collect_system_metrics_identifies_llama_cpp_process(self):
        """Test identification of llama.cpp backend process."""
        collector = MetricsCollector(enable_otel=False)

        # Mock a llama.cpp process
        with patch("psutil.process_iter") as mock_iter:
            mock_proc = Mock()
            mock_proc.info = {
                "name": "llama-server",
                "pid": 34567,
                "memory_info": Mock(rss=600 * 1024 * 1024),  # 600MB
            }
            mock_proc.cmdline.return_value = ["llama-server", "--model", "qwen"]

            mock_iter.return_value = [mock_proc]

            metrics = await collector.collect_system_metrics()

            # Should identify llama.cpp process
            assert metrics.backend_memory_mb is not None
            assert metrics.backend_memory_mb > 0
            assert metrics.backend_process_name == "llama.cpp"

    @pytest.mark.asyncio
    async def test_collect_system_metrics_multiple_processes(self):
        """Test metrics collection with multiple processes."""
        collector = MetricsCollector(enable_otel=False)

        # Mock both qwenvert and Ollama processes
        with patch("psutil.process_iter") as mock_iter:
            qwenvert_proc = Mock()
            qwenvert_proc.info = {
                "name": "python3",
                "pid": 12345,
                "memory_info": Mock(rss=100 * 1024 * 1024),
            }
            qwenvert_proc.cmdline.return_value = ["python3", "qwenvert"]

            ollama_proc = Mock()
            ollama_proc.info = {
                "name": "ollama",
                "pid": 23456,
                "memory_info": Mock(rss=500 * 1024 * 1024),
            }
            ollama_proc.cmdline.return_value = ["ollama"]

            mock_iter.return_value = [qwenvert_proc, ollama_proc]

            metrics = await collector.collect_system_metrics()

            # Should identify both processes
            assert metrics.qwenvert_memory_mb is not None
            assert metrics.backend_memory_mb is not None
            assert metrics.backend_process_name == "Ollama"


class TestRequestMetrics:
    """Test request metrics recording."""

    def test_add_request_metric_basic(self):
        """Test adding basic request metric."""
        collector = MetricsCollector(enable_otel=False)

        metric = RequestMetrics(
            timestamp=datetime.now(tz=timezone.utc),
            model="qwen-test",
            tokens_generated=100,
            latency_ms=1500.0,
            tokens_per_second=66.7,
            streaming=False,
            status="success",
        )

        collector.add_request_metric(metric)

        # Verify metric was added to history
        assert len(collector.request_history) == 1
        assert collector.request_history[0] == metric

    def test_add_request_metric_history_limit(self):
        """Test request history respects size limit."""
        collector = MetricsCollector(enable_otel=False, history_size=10)

        # Add more than history_size metrics
        for i in range(20):
            metric = RequestMetrics(
                timestamp=datetime.now(tz=timezone.utc),
                model="qwen-test",
                tokens_generated=i,
                latency_ms=1000.0,
                tokens_per_second=50.0,
                streaming=False,
                status="success",
            )
            collector.add_request_metric(metric)

        # Should only keep last 10
        assert len(collector.request_history) == 10
        # Most recent should be last one added (tokens=19)
        assert collector.request_history[-1].tokens_generated == 19

    def test_get_performance_stats_empty(self):
        """Test performance stats with no requests."""
        collector = MetricsCollector(enable_otel=False)
        stats = collector.get_performance_stats()

        assert stats.total_requests == 0
        assert stats.successful_requests == 0
        assert stats.failed_requests == 0
        assert stats.total_tokens == 0
        assert stats.uptime_seconds > 0

    def test_get_performance_stats_with_requests(self):
        """Test performance stats calculation."""
        collector = MetricsCollector(enable_otel=False)

        # Add some test metrics
        metrics = [
            RequestMetrics(
                timestamp=datetime.now(tz=timezone.utc),
                model="qwen-test",
                tokens_generated=100,
                latency_ms=1000.0,
                tokens_per_second=100.0,
                streaming=False,
                status="success",
            ),
            RequestMetrics(
                timestamp=datetime.now(tz=timezone.utc),
                model="qwen-test",
                tokens_generated=200,
                latency_ms=2000.0,
                tokens_per_second=100.0,
                streaming=False,
                status="success",
            ),
            RequestMetrics(
                timestamp=datetime.now(tz=timezone.utc),
                model="qwen-test",
                tokens_generated=0,
                latency_ms=500.0,
                tokens_per_second=0.0,
                streaming=False,
                status="error",
            ),
        ]

        for m in metrics:
            collector.add_request_metric(m)

        stats = collector.get_performance_stats()

        assert stats.total_requests == 3
        assert stats.successful_requests == 2
        assert stats.failed_requests == 1
        assert stats.total_tokens == 300
        assert abs(stats.avg_latency_ms - 1166.67) < 0.1  # (1000+2000+500)/3
        assert stats.avg_tokens_per_second == 100.0  # Only counts non-zero
        assert stats.min_latency_ms == 500.0
        assert stats.max_latency_ms == 2000.0


class TestMetricsCollectorInitialization:
    """Test MetricsCollector initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        collector = MetricsCollector()

        assert collector.adapter_url == "http://localhost:8088"
        assert len(collector.request_history) == 0
        assert collector.enable_otel is False  # Opt-in design

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        collector = MetricsCollector(
            adapter_url="http://localhost:9999",
            history_size=50,
            enable_otel=False,
        )

        assert collector.adapter_url == "http://localhost:9999"
        assert collector.request_history.maxlen == 50
        assert collector.enable_otel is False

    def test_init_otel_metrics_disabled(self):
        """Test OTEL metrics are not initialized when disabled."""
        collector = MetricsCollector(enable_otel=False)

        # Should not have OTEL metric attributes
        assert not hasattr(collector, "token_usage_counter")
        assert not hasattr(collector, "request_duration_histogram")
