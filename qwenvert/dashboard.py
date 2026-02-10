"""
Real-time TUI dashboard for qwenvert monitoring.

Beautiful terminal UI showing:
- Live performance metrics
- System resources
- Request history
- Thermal status
"""

import asyncio
import contextlib
from datetime import timedelta

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .monitoring import MetricsCollector


class Dashboard:
    """
    Real-time TUI dashboard for qwenvert.

    Displays live metrics, system status, and request history
    in a beautiful terminal interface.
    """

    def __init__(
        self,
        collector: MetricsCollector,
        adapter_url: str = "http://localhost:8088",
    ) -> None:
        """
        Initialize dashboard.

        Args:
            collector: MetricsCollector instance
            adapter_url: URL of qwenvert adapter
        """
        self.collector = collector
        self.adapter_url = adapter_url
        self.console = Console()

    def create_layout(self) -> Layout:
        """
        Create dashboard layout.

        Returns:
            Rich Layout with dashboard structure
        """
        layout = Layout()

        # Split into header and body
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )

        # Split body into left and right columns
        layout["body"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1),
        )

        # Split left column into metrics and requests
        layout["left"].split_column(
            Layout(name="metrics", ratio=1),
            Layout(name="requests", ratio=1),
        )

        # Split right column into system and status
        layout["right"].split_column(
            Layout(name="system", ratio=1),
            Layout(name="status", ratio=1),
        )

        return layout

    def render_header(self) -> Panel:
        """Render dashboard header."""
        text = Text("Qwenvert Monitor", style="bold cyan", justify="center")
        text.append(" - Real-time Performance Dashboard", style="dim")

        return Panel(
            text,
            style="blue",
            border_style="bright_blue",
        )

    def render_metrics(self) -> Panel:
        """Render performance metrics panel."""
        stats = self.collector.get_performance_stats()

        # Create metrics table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold green")

        # Uptime
        uptime = str(timedelta(seconds=int(stats.uptime_seconds)))
        table.add_row("Uptime", uptime)

        # Requests
        success_rate = (
            (stats.successful_requests / stats.total_requests * 100)
            if stats.total_requests > 0
            else 0
        )
        table.add_row(
            "Requests",
            f"{stats.total_requests} total, {stats.successful_requests} success ({success_rate:.1f}%)",
        )

        # Tokens
        table.add_row("Tokens Generated", f"{stats.total_tokens:,}")

        # Latency
        if stats.avg_latency_ms > 0:
            table.add_row(
                "Latency",
                f"avg: {stats.avg_latency_ms:.0f}ms, "
                f"min: {stats.min_latency_ms:.0f}ms, "
                f"max: {stats.max_latency_ms:.0f}ms",
            )

        # Throughput
        if stats.avg_tokens_per_second > 0:
            table.add_row(
                "Throughput",
                f"{stats.avg_tokens_per_second:.1f} tokens/sec (avg)",
            )

        return Panel(
            table,
            title="[bold]Performance Metrics[/bold]",
            border_style="green",
        )

    def render_system(self) -> Panel:
        """Render system resources panel."""
        # Note: This is async in real usage, but for rendering we'll use cached data
        # In actual implementation, metrics would be cached in the collector

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Resource", style="cyan")
        table.add_column("Value", style="bold")

        # Placeholder for async data
        table.add_row("CPU", "Loading...")
        table.add_row("Memory", "Loading...")
        table.add_row("Temperature", "Loading...")

        return Panel(
            table,
            title="[bold]System Resources[/bold]",
            border_style="yellow",
        )

    def render_system_with_metrics(self, system_metrics) -> Panel:
        """
        Render system resources panel with actual metrics.

        Args:
            system_metrics: SystemMetrics instance

        Returns:
            Panel with system info
        """
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Resource", style="cyan")
        table.add_column("Value")

        # CPU
        cpu_style = "green" if system_metrics.cpu_percent < 70 else "yellow"
        if system_metrics.cpu_percent > 90:
            cpu_style = "red"

        table.add_row(
            "CPU",
            Text(f"{system_metrics.cpu_percent:.1f}%", style=cpu_style),
        )

        # Memory
        mem_style = "green" if system_metrics.memory_percent < 70 else "yellow"
        if system_metrics.memory_percent > 90:
            mem_style = "red"

        table.add_row(
            "Memory",
            Text(
                f"{system_metrics.memory_used_gb:.1f}GB / "
                f"{system_metrics.memory_total_gb:.1f}GB "
                f"({system_metrics.memory_percent:.0f}%)",
                style=mem_style,
            ),
        )

        # Temperature
        if system_metrics.cpu_temp_celsius:
            temp_style = "green" if system_metrics.cpu_temp_celsius < 70 else "yellow"
            if system_metrics.cpu_temp_celsius > 85:
                temp_style = "red"

            table.add_row(
                "Temperature",
                Text(f"{system_metrics.cpu_temp_celsius:.1f}°C", style=temp_style),
            )
        else:
            table.add_row("Temperature", Text("N/A", style="dim"))

        # Processes
        if system_metrics.qwenvert_memory_mb:
            table.add_row(
                "Qwenvert",
                f"{system_metrics.qwenvert_memory_mb:.0f}MB",
            )

        if system_metrics.backend_memory_mb and system_metrics.backend_process_name:
            table.add_row(
                system_metrics.backend_process_name,
                f"{system_metrics.backend_memory_mb:.0f}MB",
            )

        return Panel(
            table,
            title="[bold]System Resources[/bold]",
            border_style="yellow",
        )

    def render_status(self, is_healthy: bool) -> Panel:
        """Render adapter status panel."""
        if is_healthy:
            status_text = Text("● RUNNING", style="bold green")
            status_text.append("\n\n")
            status_text.append(f"Adapter: {self.adapter_url}", style="dim")
        else:
            status_text = Text("● OFFLINE", style="bold red")
            status_text.append("\n\n")
            status_text.append("Adapter not responding", style="dim")

        return Panel(
            status_text,
            title="[bold]Status[/bold]",
            border_style="blue",
        )

    def render_requests(self) -> Panel:
        """Render recent requests table."""
        recent = self.collector.get_recent_requests(count=10)

        if not recent:
            return Panel(
                Text("No requests yet...", style="dim", justify="center"),
                title="[bold]Recent Requests[/bold]",
                border_style="magenta",
            )

        # Create requests table
        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("Time", style="cyan", width=8)
        table.add_column("Tokens", justify="right", style="green", width=6)
        table.add_column("Latency", justify="right", width=8)
        table.add_column("Speed", justify="right", width=10)
        table.add_column("Status", width=7)

        for req in reversed(recent):  # Most recent first
            # Time
            time_str = req.timestamp.strftime("%H:%M:%S")

            # Status symbol
            if req.status == "success":
                status = Text("✓", style="green")
            elif req.status == "error":
                status = Text("✗", style="red")
            else:
                status = Text("⊗", style="yellow")

            # Latency color
            latency_style = "green"
            if req.latency_ms > 3000:
                latency_style = "yellow"
            if req.latency_ms > 5000:
                latency_style = "red"

            table.add_row(
                time_str,
                str(req.tokens_generated),
                Text(f"{req.latency_ms:.0f}ms", style=latency_style),
                (
                    f"{req.tokens_per_second:.1f} t/s"
                    if req.tokens_per_second > 0
                    else "-"
                ),
                status,
            )

        return Panel(
            table,
            title="[bold]Recent Requests[/bold]",
            border_style="magenta",
        )

    def render_footer(self) -> Panel:
        """Render dashboard footer with controls."""
        text = Text("Press ", style="dim")
        text.append("Ctrl+C", style="bold cyan")
        text.append(" to exit", style="dim")
        text.append(" | Refresh: 1s", style="dim")

        return Panel(text, style="dim")

    async def run(self, refresh_rate: float = 1.0) -> None:
        """
        Run the dashboard with live updates.

        Args:
            refresh_rate: Update interval in seconds
        """
        layout = self.create_layout()

        with Live(layout, console=self.console, screen=True, refresh_per_second=4):
            try:
                while True:
                    # Collect current metrics
                    system_metrics = await self.collector.collect_system_metrics()
                    is_healthy = await self.collector.check_adapter_health()

                    # Update layout
                    layout["header"].update(self.render_header())
                    layout["metrics"].update(self.render_metrics())
                    layout["system"].update(
                        self.render_system_with_metrics(system_metrics)
                    )
                    layout["status"].update(self.render_status(is_healthy))
                    layout["requests"].update(self.render_requests())
                    layout["footer"].update(self.render_footer())

                    await asyncio.sleep(refresh_rate)

            except KeyboardInterrupt:
                pass


async def run_dashboard(
    adapter_url: str = "http://localhost:8088",
    refresh_rate: float = 1.0,
) -> None:
    """
    Run the monitoring dashboard.

    Args:
        adapter_url: URL of qwenvert adapter
        refresh_rate: Update interval in seconds
    """
    collector = MetricsCollector(adapter_url=adapter_url)
    dashboard = Dashboard(collector, adapter_url=adapter_url)

    # Start monitoring loop in background
    monitor_task = asyncio.create_task(collector.monitor_loop(interval=refresh_rate))

    try:
        # Run dashboard
        await dashboard.run(refresh_rate=refresh_rate)
    finally:
        # Cleanup
        monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor_task
