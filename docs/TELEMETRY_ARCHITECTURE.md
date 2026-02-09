# Telemetry Architecture for Cross-Platform Thermal Management

## Design Philosophy

**Goal**: Emit rich, actionable telemetry that works elegantly across architectures (Apple Silicon, x86, ARM) while optimizing for Apple Silicon first.

**Principles**:
1. **Platform-Agnostic Interface**: Common telemetry format across all platforms
2. **Platform-Specific Implementations**: Optimized collectors for each architecture
3. **Real-Time Observability**: Both programmatic (Prometheus) and visual (CLI/Web) access
4. **Actionable Metrics**: Not just data, but thresholds and recommendations

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Telemetry Consumers                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Orchestrator │  │ Web Dashboard│  │ Prometheus   │          │
│  │ (Actions)    │  │ (Graphical)  │  │ (Export)     │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          │ Subscribe        │ Stream           │ Scrape
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼─────────────────┐
│              Telemetry Aggregator & Event Bus                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  - Metric buffering and aggregation                      │   │
│  │  - Event emission (Observer pattern)                     │   │
│  │  - Threshold detection and alerting                      │   │
│  │  - Time-series storage (in-memory ring buffer)           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────┬──────────────────────────────────────────────────────┘
          │
          │ Collect metrics
          │
┌─────────▼──────────────────────────────────────────────────────┐
│           Platform-Specific Metric Collectors                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Apple Silicon│  │    x86_64    │  │   ARM/Other  │          │
│  │  Collector   │  │   Collector  │  │   Collector  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│       │                   │                  │                   │
│  Uses: powermetrics  Uses: sensors    Uses: psutil/generic      │
│        smc                 lm-sensors       /sys/class/thermal   │
└───────┼───────────────────┼──────────────────┼───────────────────┘
        │                   │                  │
   ┌────▼───────────────────▼──────────────────▼────┐
   │           Hardware Layer                        │
   │  CPU/GPU, Memory, Power, Thermal Sensors        │
   └─────────────────────────────────────────────────┘
```

---

## Core Telemetry Schema

### Standard Metrics (Cross-Platform)

All platforms emit these core metrics in a unified format:

```python
@dataclass
class TelemetrySnapshot:
    """
    Platform-agnostic telemetry snapshot.
    All platforms must provide these metrics, using best available sources.
    """

    timestamp: float  # Unix timestamp
    platform: str  # "apple_silicon", "x86_64", "arm", "unknown"

    # Thermal metrics
    cpu_temp_celsius: Optional[float]
    gpu_temp_celsius: Optional[float]
    thermal_pressure: float  # 0.0-1.0 normalized pressure index
    thermal_state: ThermalState  # NOMINAL, WARNING, CRITICAL

    # Memory metrics
    total_memory_gb: float
    used_memory_gb: float
    available_memory_gb: float
    swap_used_gb: float
    memory_pressure: float  # 0.0-1.0 normalized pressure index

    # Performance metrics
    cpu_utilization_percent: float
    gpu_utilization_percent: Optional[float]
    power_watts: Optional[float]
    inference_tokens_per_second: float  # Current throughput

    # Action recommendations (computed from metrics)
    recommended_action: Action  # CONTINUE, PAUSE_BRIEF, PAUSE_EXTENDED, SHUTDOWN


class ThermalState(Enum):
    """Universal thermal states across all platforms."""
    NOMINAL = "nominal"          # <70°C, no throttling expected
    WARNING = "warning"          # 70-85°C, may start throttling
    CRITICAL = "critical"        # >85°C, active throttling
    EMERGENCY = "emergency"      # >95°C, emergency shutdown risk


class Action(Enum):
    """Recommended actions based on telemetry."""
    CONTINUE = "continue"              # All good, continue inference
    PAUSE_BRIEF = "pause_brief"        # 300ms thermal break
    PAUSE_EXTENDED = "pause_extended"  # 5-10s cooldown
    REDUCE_BATCH = "reduce_batch"      # Lower batch size
    SHUTDOWN = "shutdown"              # Emergency stop
```

### Extended Metrics (Platform-Specific)

Platform-specific collectors can emit additional metrics:

```python
@dataclass
class AppleSiliconExtendedMetrics:
    """Apple Silicon specific metrics."""
    neural_engine_utilization: float
    efficiency_core_freq_mhz: int
    performance_core_freq_mhz: int
    memory_bandwidth_gb_per_sec: float
    smc_fan_speed_rpm: Optional[int]  # None for fanless Macs
    battery_level_percent: Optional[float]
    power_source: str  # "AC" or "Battery"


@dataclass
class X86ExtendedMetrics:
    """x86_64 specific metrics."""
    cpu_freq_mhz: int
    cpu_package_temp: float
    per_core_temps: List[float]
    fan_speeds_rpm: List[int]
    tdp_watts: float
    turbo_boost_active: bool
```

---

## Implementation: Platform-Specific Collectors

### Apple Silicon Collector

```python
class AppleSiliconCollector(MetricCollector):
    """
    Optimized collector for Apple Silicon (M1/M2/M3/M4).
    Uses powermetrics and SMC for comprehensive hardware visibility.
    """

    def __init__(self):
        self.platform = "apple_silicon"
        self._verify_tools()

    def _verify_tools(self):
        """Ensure powermetrics is available (requires sudo)."""
        try:
            subprocess.run(
                ["sudo", "-n", "powermetrics", "--version"],
                capture_output=True,
                check=True,
                timeout=1
            )
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            logger.warning(
                "powermetrics requires sudo. Run: "
                "echo '%admin ALL=(ALL) NOPASSWD: /usr/bin/powermetrics' | sudo tee /etc/sudoers.d/powermetrics"
            )

    async def collect(self) -> TelemetrySnapshot:
        """
        Collect comprehensive Apple Silicon metrics.
        """
        # Get thermal data from powermetrics
        thermal_data = await self._get_thermal_data()

        # Get memory stats from vm_stat
        memory_data = await self._get_memory_data()

        # Get power consumption
        power_data = await self._get_power_data()

        # Compute thermal pressure index (0.0-1.0)
        thermal_pressure = self._compute_thermal_pressure(
            cpu_temp=thermal_data['cpu_temp'],
            gpu_temp=thermal_data['gpu_temp'],
            temp_history=self._temp_history
        )

        # Compute memory pressure index
        memory_pressure = self._compute_memory_pressure(
            used=memory_data['used_gb'],
            total=memory_data['total_gb'],
            swap=memory_data['swap_gb']
        )

        # Determine thermal state
        thermal_state = self._classify_thermal_state(
            cpu_temp=thermal_data['cpu_temp'],
            gpu_temp=thermal_data['gpu_temp'],
            pressure=thermal_pressure
        )

        # Compute recommended action
        action = self._compute_action(
            thermal_state=thermal_state,
            thermal_pressure=thermal_pressure,
            memory_pressure=memory_pressure
        )

        snapshot = TelemetrySnapshot(
            timestamp=time.time(),
            platform=self.platform,
            cpu_temp_celsius=thermal_data['cpu_temp'],
            gpu_temp_celsius=thermal_data['gpu_temp'],
            thermal_pressure=thermal_pressure,
            thermal_state=thermal_state,
            total_memory_gb=memory_data['total_gb'],
            used_memory_gb=memory_data['used_gb'],
            available_memory_gb=memory_data['available_gb'],
            swap_used_gb=memory_data['swap_gb'],
            memory_pressure=memory_pressure,
            cpu_utilization_percent=thermal_data['cpu_util'],
            gpu_utilization_percent=thermal_data['gpu_util'],
            power_watts=power_data['total_watts'],
            inference_tokens_per_second=self._current_throughput,
            recommended_action=action
        )

        # Store for history-based predictions
        self._temp_history.append(thermal_data['cpu_temp'])

        return snapshot

    async def _get_thermal_data(self) -> Dict:
        """
        Get thermal data using powermetrics.
        Sample output parsing:
        CPU die temperature: 65.23 °C
        GPU die temperature: 62.45 °C
        """
        output = await self._run_command([
            "sudo", "powermetrics",
            "--samplers", "smc,cpu_power,gpu_power",
            "-n", "1",
            "-i", "1000"
        ])

        cpu_temp = self._parse_temp(output, "CPU die temperature")
        gpu_temp = self._parse_temp(output, "GPU die temperature")
        cpu_util = self._parse_utilization(output, "CPU")
        gpu_util = self._parse_utilization(output, "GPU")

        return {
            'cpu_temp': cpu_temp or 0.0,
            'gpu_temp': gpu_temp or 0.0,
            'cpu_util': cpu_util or 0.0,
            'gpu_util': gpu_util or 0.0
        }

    def _compute_thermal_pressure(
        self,
        cpu_temp: float,
        gpu_temp: float,
        temp_history: List[float]
    ) -> float:
        """
        Compute normalized thermal pressure (0.0-1.0).

        Factors:
        1. Absolute temperature (50% weight)
        2. Rate of temperature rise (30% weight)
        3. Time above threshold (20% weight)

        Returns:
            0.0-0.3: Low pressure (green)
            0.3-0.7: Medium pressure (yellow)
            0.7-1.0: High pressure (red)
        """
        # Component 1: Absolute temperature pressure
        # Maps 20°C->0.0, 65°C->0.5, 95°C->1.0
        max_temp = max(cpu_temp, gpu_temp)
        temp_pressure = np.clip((max_temp - 20) / 75, 0.0, 1.0)

        # Component 2: Rate of change pressure
        if len(temp_history) >= 3:
            recent_temps = temp_history[-3:]
            temp_delta = recent_temps[-1] - recent_temps[0]
            time_delta = 3 * 2.0  # 3 samples at 2-second intervals
            rise_rate = temp_delta / time_delta  # °C/sec

            # >1.5°C/sec is high pressure
            rate_pressure = np.clip(rise_rate / 1.5, 0.0, 1.0)
        else:
            rate_pressure = 0.0

        # Component 3: Time above threshold pressure
        high_temp_samples = sum(1 for t in temp_history[-10:] if t > 75)
        time_pressure = high_temp_samples / 10.0

        # Weighted combination
        pressure = (
            0.5 * temp_pressure +
            0.3 * rate_pressure +
            0.2 * time_pressure
        )

        return float(np.clip(pressure, 0.0, 1.0))

    def _compute_action(
        self,
        thermal_state: ThermalState,
        thermal_pressure: float,
        memory_pressure: float
    ) -> Action:
        """
        Compute recommended action from system state.

        Decision matrix:
        - CRITICAL thermal + high pressure → PAUSE_EXTENDED
        - WARNING thermal + rising fast → PAUSE_BRIEF
        - High memory pressure + swap → REDUCE_BATCH
        - EMERGENCY thermal → SHUTDOWN
        - Otherwise → CONTINUE
        """
        if thermal_state == ThermalState.EMERGENCY:
            return Action.SHUTDOWN

        if thermal_state == ThermalState.CRITICAL and thermal_pressure > 0.8:
            return Action.PAUSE_EXTENDED

        if thermal_state == ThermalState.WARNING and thermal_pressure > 0.6:
            return Action.PAUSE_BRIEF

        if memory_pressure > 0.85:
            return Action.REDUCE_BATCH

        return Action.CONTINUE


class X86Collector(MetricCollector):
    """
    Collector for x86_64 systems.
    Uses lm-sensors and /sys/class/thermal.
    """

    def __init__(self):
        self.platform = "x86_64"
        self._verify_tools()

    async def collect(self) -> TelemetrySnapshot:
        """Collect x86-specific metrics."""
        # Similar structure to Apple Silicon, different data sources
        # Uses: sensors, /proc/stat, /sys/class/thermal
        pass


class GenericCollector(MetricCollector):
    """
    Fallback collector for unsupported platforms.
    Uses psutil for basic cross-platform metrics.
    """

    def __init__(self):
        self.platform = "generic"

    async def collect(self) -> TelemetrySnapshot:
        """Collect basic metrics available on all platforms."""
        import psutil

        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()

        # Try to get temperatures (may not be available)
        temps = psutil.sensors_temperatures() if hasattr(psutil, 'sensors_temperatures') else {}
        cpu_temp = None
        if temps:
            # Try common sensor names
            for name in ['coretemp', 'cpu_thermal', 'acpitz']:
                if name in temps and temps[name]:
                    cpu_temp = temps[name][0].current
                    break

        return TelemetrySnapshot(
            timestamp=time.time(),
            platform=self.platform,
            cpu_temp_celsius=cpu_temp,
            gpu_temp_celsius=None,
            thermal_pressure=0.5 if cpu_temp and cpu_temp > 70 else 0.3,
            thermal_state=ThermalState.NOMINAL,
            total_memory_gb=memory.total / (1024**3),
            used_memory_gb=memory.used / (1024**3),
            available_memory_gb=memory.available / (1024**3),
            swap_used_gb=swap.used / (1024**3),
            memory_pressure=memory.percent / 100.0,
            cpu_utilization_percent=cpu_percent,
            gpu_utilization_percent=None,
            power_watts=None,
            inference_tokens_per_second=0.0,
            recommended_action=Action.CONTINUE
        )
```

---

## Telemetry Aggregator & Event Bus

```python
class TelemetryAggregator:
    """
    Central hub for telemetry collection, aggregation, and distribution.
    Implements Observer pattern for event-driven actions.
    """

    def __init__(self, collector: MetricCollector):
        self.collector = collector
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.metrics_buffer = deque(maxlen=300)  # 10 minutes at 2-sec intervals
        self.running = False

        # Prometheus metrics
        self._setup_prometheus_metrics()

    def _setup_prometheus_metrics(self):
        """Initialize Prometheus gauges for all metrics."""
        from prometheus_client import Gauge

        self.prom_cpu_temp = Gauge('qwenvert_cpu_temperature_celsius', 'CPU temperature')
        self.prom_gpu_temp = Gauge('qwenvert_gpu_temperature_celsius', 'GPU temperature')
        self.prom_thermal_pressure = Gauge('qwenvert_thermal_pressure', 'Thermal pressure index 0-1')
        self.prom_memory_pressure = Gauge('qwenvert_memory_pressure', 'Memory pressure index 0-1')
        self.prom_memory_used = Gauge('qwenvert_memory_used_gb', 'Memory used in GB')
        self.prom_swap_used = Gauge('qwenvert_swap_used_gb', 'Swap used in GB')
        self.prom_tokens_per_sec = Gauge('qwenvert_throughput_tokens_per_second', 'Inference throughput')
        self.prom_thermal_state = Gauge('qwenvert_thermal_state', 'Thermal state (0=nominal, 1=warning, 2=critical, 3=emergency)')

    async def start(self, poll_interval: float = 2.0):
        """Start telemetry collection loop."""
        self.running = True

        while self.running:
            try:
                # Collect metrics
                snapshot = await self.collector.collect()

                # Store in buffer
                self.metrics_buffer.append(snapshot)

                # Update Prometheus metrics
                self._update_prometheus(snapshot)

                # Emit events
                await self._emit_events(snapshot)

                # Sleep until next collection
                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Telemetry collection error: {e}", exc_info=True)
                await asyncio.sleep(poll_interval)

    def subscribe(self, event_type: str, callback: Callable):
        """
        Subscribe to telemetry events.

        Event types:
        - "snapshot": Every telemetry snapshot
        - "thermal_warning": Thermal pressure > 0.6
        - "thermal_critical": Thermal pressure > 0.8
        - "memory_warning": Memory pressure > 0.7
        - "action_recommended": Action != CONTINUE
        """
        self.subscribers[event_type].append(callback)

    async def _emit_events(self, snapshot: TelemetrySnapshot):
        """Emit events based on snapshot state."""
        # Always emit snapshot event
        await self._notify("snapshot", snapshot)

        # Thermal events
        if snapshot.thermal_pressure > 0.8:
            await self._notify("thermal_critical", snapshot)
        elif snapshot.thermal_pressure > 0.6:
            await self._notify("thermal_warning", snapshot)

        # Memory events
        if snapshot.memory_pressure > 0.7:
            await self._notify("memory_warning", snapshot)

        # Action events
        if snapshot.recommended_action != Action.CONTINUE:
            await self._notify("action_recommended", snapshot)

    async def _notify(self, event_type: str, snapshot: TelemetrySnapshot):
        """Notify all subscribers of an event."""
        for callback in self.subscribers[event_type]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(snapshot)
                else:
                    callback(snapshot)
            except Exception as e:
                logger.error(f"Error in telemetry subscriber: {e}", exc_info=True)

    def _update_prometheus(self, snapshot: TelemetrySnapshot):
        """Update Prometheus metrics from snapshot."""
        if snapshot.cpu_temp_celsius:
            self.prom_cpu_temp.set(snapshot.cpu_temp_celsius)
        if snapshot.gpu_temp_celsius:
            self.prom_gpu_temp.set(snapshot.gpu_temp_celsius)

        self.prom_thermal_pressure.set(snapshot.thermal_pressure)
        self.prom_memory_pressure.set(snapshot.memory_pressure)
        self.prom_memory_used.set(snapshot.used_memory_gb)
        self.prom_swap_used.set(snapshot.swap_used_gb)
        self.prom_tokens_per_sec.set(snapshot.inference_tokens_per_second)

        # Map thermal state to numeric
        state_map = {
            ThermalState.NOMINAL: 0,
            ThermalState.WARNING: 1,
            ThermalState.CRITICAL: 2,
            ThermalState.EMERGENCY: 3
        }
        self.prom_thermal_state.set(state_map[snapshot.thermal_state])

    def get_recent_metrics(self, window_seconds: int = 60) -> List[TelemetrySnapshot]:
        """Get recent metrics within time window."""
        cutoff = time.time() - window_seconds
        return [s for s in self.metrics_buffer if s.timestamp >= cutoff]

    def get_summary(self) -> Dict:
        """Get summary statistics over recent window."""
        if not self.metrics_buffer:
            return {}

        recent = list(self.metrics_buffer)[-30:]  # Last 30 samples (1 minute)

        return {
            "avg_cpu_temp": np.mean([s.cpu_temp_celsius or 0 for s in recent]),
            "max_cpu_temp": np.max([s.cpu_temp_celsius or 0 for s in recent]),
            "avg_thermal_pressure": np.mean([s.thermal_pressure for s in recent]),
            "avg_memory_pressure": np.mean([s.memory_pressure for s in recent]),
            "avg_throughput": np.mean([s.inference_tokens_per_second for s in recent]),
            "thermal_warnings": sum(1 for s in recent if s.thermal_state in [ThermalState.WARNING, ThermalState.CRITICAL]),
        }
```

---

## Visualization: Real-Time CLI Dashboard

```python
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.console import Console

class TelemetryDashboard:
    """
    Real-time terminal dashboard for telemetry visualization.
    Uses Rich for beautiful CLI rendering.
    """

    def __init__(self, aggregator: TelemetryAggregator):
        self.aggregator = aggregator
        self.console = Console()

    async def run(self):
        """Run live dashboard."""
        with Live(self._render(), refresh_per_second=2, console=self.console) as live:
            while True:
                live.update(self._render())
                await asyncio.sleep(0.5)

    def _render(self) -> Layout:
        """Render dashboard layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )

        layout["main"].split_row(
            Layout(name="metrics"),
            Layout(name="graph")
        )

        # Header
        layout["header"].update(
            Panel("🔥 Qwenvert Telemetry Dashboard", style="bold blue")
        )

        # Metrics table
        if self.aggregator.metrics_buffer:
            latest = self.aggregator.metrics_buffer[-1]
            layout["metrics"].update(self._render_metrics_table(latest))
        else:
            layout["metrics"].update(Panel("Waiting for metrics...", style="dim"))

        # Graph
        layout["graph"].update(self._render_thermal_graph())

        # Footer with recommendations
        if self.aggregator.metrics_buffer:
            latest = self.aggregator.metrics_buffer[-1]
            layout["footer"].update(self._render_action_panel(latest))

        return layout

    def _render_metrics_table(self, snapshot: TelemetrySnapshot) -> Table:
        """Render current metrics as a table."""
        table = Table(title="Current Metrics", show_header=True)

        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_column("Status", justify="center")

        # Thermal metrics
        cpu_status = self._get_temp_status(snapshot.cpu_temp_celsius)
        table.add_row(
            "CPU Temp",
            f"{snapshot.cpu_temp_celsius:.1f}°C" if snapshot.cpu_temp_celsius else "N/A",
            cpu_status
        )

        if snapshot.gpu_temp_celsius:
            gpu_status = self._get_temp_status(snapshot.gpu_temp_celsius)
            table.add_row(
                "GPU Temp",
                f"{snapshot.gpu_temp_celsius:.1f}°C",
                gpu_status
            )

        # Pressure metrics
        thermal_status = self._get_pressure_status(snapshot.thermal_pressure)
        table.add_row(
            "Thermal Pressure",
            f"{snapshot.thermal_pressure:.2f}",
            thermal_status
        )

        memory_status = self._get_pressure_status(snapshot.memory_pressure)
        table.add_row(
            "Memory Pressure",
            f"{snapshot.memory_pressure:.2f}",
            memory_status
        )

        # Performance
        table.add_row(
            "Throughput",
            f"{snapshot.inference_tokens_per_second:.1f} tok/s",
            "✓" if snapshot.inference_tokens_per_second > 15 else "⚠"
        )

        # Memory
        table.add_row(
            "Memory Used",
            f"{snapshot.used_memory_gb:.1f} / {snapshot.total_memory_gb:.1f} GB",
            "✓" if snapshot.memory_pressure < 0.7 else "⚠"
        )

        if snapshot.swap_used_gb > 0.1:
            table.add_row(
                "Swap Used",
                f"{snapshot.swap_used_gb:.1f} GB",
                "❌ SWAPPING!"
            )

        return table

    def _render_thermal_graph(self) -> Panel:
        """Render ASCII thermal graph for last 60 samples."""
        if len(self.aggregator.metrics_buffer) < 2:
            return Panel("Not enough data", title="Thermal History")

        recent = list(self.aggregator.metrics_buffer)[-60:]
        temps = [s.cpu_temp_celsius or 0 for s in recent]

        # Simple ASCII sparkline
        height = 10
        width = 60
        min_temp = max(20, min(temps) - 5)
        max_temp = min(100, max(temps) + 5)

        graph_lines = []
        for i in range(height, 0, -1):
            threshold = min_temp + (max_temp - min_temp) * i / height
            line = ""
            for temp in temps:
                if temp >= threshold:
                    line += "█"
                else:
                    line += " "
            graph_lines.append(f"{threshold:5.1f}°C │{line}")

        graph_lines.append(f"      └{'─' * width}")
        graph_lines.append(f"       {len(recent)} samples (last {len(recent)*2}s)")

        return Panel("\n".join(graph_lines), title="CPU Temperature History")

    def _render_action_panel(self, snapshot: TelemetrySnapshot) -> Panel:
        """Render recommended action panel."""
        action_map = {
            Action.CONTINUE: ("✓ All systems nominal", "green"),
            Action.PAUSE_BRIEF: ("⏸ Brief thermal break (300ms)", "yellow"),
            Action.PAUSE_EXTENDED: ("⏸ Extended cooldown (5-10s)", "red"),
            Action.REDUCE_BATCH: ("📉 Reducing batch size", "yellow"),
            Action.SHUTDOWN: ("🛑 EMERGENCY SHUTDOWN", "red bold")
        }

        message, style = action_map[snapshot.recommended_action]
        return Panel(message, style=style, title="System Status")

    def _get_temp_status(self, temp: Optional[float]) -> str:
        """Get status emoji for temperature."""
        if not temp:
            return "?"
        if temp < 65:
            return "[green]✓[/green]"
        elif temp < 80:
            return "[yellow]⚠[/yellow]"
        else:
            return "[red]❌[/red]"

    def _get_pressure_status(self, pressure: float) -> str:
        """Get status emoji for pressure metric."""
        if pressure < 0.3:
            return "[green]✓ Low[/green]"
        elif pressure < 0.7:
            return "[yellow]⚠ Medium[/yellow]"
        else:
            return "[red]❌ High[/red]"
```

---

## Integration with Orchestrator

```python
class InferenceOrchestrator:
    """Updated orchestrator with telemetry-driven actions."""

    def __init__(
        self,
        engine: InferenceEngine,
        telemetry: TelemetryAggregator
    ):
        self.engine = engine
        self.telemetry = telemetry

        # Subscribe to telemetry events
        self.telemetry.subscribe("action_recommended", self._handle_action)
        self.telemetry.subscribe("thermal_critical", self._handle_thermal_critical)

    async def _handle_action(self, snapshot: TelemetrySnapshot):
        """Handle recommended actions from telemetry."""
        action = snapshot.recommended_action

        if action == Action.PAUSE_BRIEF:
            logger.info(f"Thermal pressure {snapshot.thermal_pressure:.2f}, pausing 300ms")
            await asyncio.sleep(0.3)

        elif action == Action.PAUSE_EXTENDED:
            logger.warning(f"Critical thermal state, pausing 10s")
            await asyncio.sleep(10)

        elif action == Action.REDUCE_BATCH:
            logger.warning(f"High memory pressure, reducing batch size")
            # Implement batch size reduction

        elif action == Action.SHUTDOWN:
            logger.critical("Emergency thermal shutdown!")
            # Graceful shutdown

    async def _handle_thermal_critical(self, snapshot: TelemetrySnapshot):
        """Alert on critical thermal state."""
        logger.error(
            f"THERMAL CRITICAL: CPU={snapshot.cpu_temp_celsius}°C, "
            f"Pressure={snapshot.thermal_pressure:.2f}"
        )
```

---

## Recommendation: Focus on Apple Silicon First

**Yes, focus on Apple Silicon first**, because:

1. **Target Hardware**: Mac M1 is your primary deployment target
2. **Rich Telemetry**: Apple provides excellent tools (powermetrics, SMC)
3. **Critical Thermal**: M1 thermal management is most critical (especially fanless MacBook Air)
4. **Unified Memory**: Apple's unique architecture requires specialized optimization

**But design for extensibility**:
- Platform-agnostic interface (`TelemetrySnapshot`, `MetricCollector`)
- Plugin architecture for new platforms
- Generic fallback for unsupported systems

**Implementation priority**:
1. **Phase 1**: Apple Silicon collector (fully featured)
2. **Phase 2**: Prometheus export and CLI dashboard (works for all platforms)
3. **Phase 3**: x86 collector (when needed)
4. **Phase 4**: ARM/generic collector (completeness)

This gives you production-grade telemetry on M1 immediately, with a clean path to expand later.

---

## Summary: Actionable Telemetry

This architecture provides:

✅ **Platform-agnostic interface** with platform-specific optimizations
✅ **Real-time thermal pressure** with predictive analytics
✅ **Actionable metrics** (not just data, but recommendations)
✅ **Multiple visualization** options (CLI, Prometheus, programmatic)
✅ **Event-driven architecture** for reactive thermal management
✅ **Apple Silicon first** with extensibility for other platforms

The thermal pressure index (0.0-1.0) is your single numerical value to take action on, computed from multiple signals. The CLI dashboard gives you real-time graphical visibility.
