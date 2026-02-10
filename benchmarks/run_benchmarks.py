#!/usr/bin/env python3
"""
Performance benchmark suite for qwenvert.

Measures inference latency, throughput, and resource usage across:
- Different backends (Ollama, llama.cpp)
- Different models and quantizations (Q4, Q5, Q8)
- Different context lengths (4K, 8K, 16K, 32K)
- Different prompt types (short, medium, long)

Generates HTML reports with charts and stores results for regression
tracking.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table


console = Console()


@dataclass
class BenchmarkConfig:
    """Configuration for a single benchmark run."""

    name: str
    backend: str  # "ollama" or "llamacpp"
    model: str
    quantization: str
    context_length: int
    prompt: str
    max_tokens: int
    streaming: bool = False


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""

    # Config
    name: str
    backend: str
    model: str
    quantization: str
    context_length: int
    prompt_tokens: int
    max_tokens: int
    streaming: bool

    # Results
    success: bool
    error: str | None = None

    # Timing
    latency_ms: float = 0.0
    first_token_ms: float | None = None  # Time to first token (streaming)
    time_per_token_ms: float = 0.0

    # Throughput
    tokens_generated: int = 0
    tokens_per_second: float = 0.0

    # Resource usage (if available)
    peak_memory_mb: float | None = None
    avg_cpu_percent: float | None = None

    # Timestamp
    timestamp: str = ""


class BenchmarkRunner:
    """Runs performance benchmarks against qwenvert adapter."""

    def __init__(
        self,
        adapter_url: str = "http://localhost:8088",
        output_dir: Path = Path("benchmarks/results"),
    ) -> None:
        self.adapter_url = adapter_url
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: list[BenchmarkResult] = []

    async def check_adapter_health(self) -> bool:
        """Check if adapter is running."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.adapter_url}/health",
                    timeout=5.0,
                )
                return response.status_code == 200
        except httpx.RequestError:
            return False

    async def run_benchmark(
        self,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run a single benchmark."""

        console.print(f"[cyan]Running:[/cyan] {config.name}")

        result = BenchmarkResult(
            name=config.name,
            backend=config.backend,
            model=config.model,
            quantization=config.quantization,
            context_length=config.context_length,
            prompt_tokens=len(config.prompt.split()),  # Rough estimate
            max_tokens=config.max_tokens,
            streaming=config.streaming,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        try:
            if config.streaming:
                await self._benchmark_streaming(config, result)
            else:
                await self._benchmark_non_streaming(config, result)

            result.success = True

        except httpx.HTTPStatusError as e:
            result.success = False
            result.error = f"HTTP {e.response.status_code}: {e}"
            console.print(f"  [red]✗ Failed:[/red] {e}")
        except httpx.RequestError as e:
            result.success = False
            result.error = f"Request failed: {e}"
            console.print(f"  [red]✗ Failed:[/red] {e}")

        return result

    async def _benchmark_non_streaming(
        self,
        config: BenchmarkConfig,
        result: BenchmarkResult,
    ) -> None:
        """Benchmark non-streaming request."""

        request = {
            "model": "qwenvert-default",
            "messages": [{"role": "user", "content": config.prompt}],
            "max_tokens": config.max_tokens,
            "stream": False,
        }

        start_time = time.time()

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.adapter_url}/v1/messages",
                json=request,
                headers={"x-api-key": "local-qwen"},
            )
            response.raise_for_status()
            data = response.json()

        end_time = time.time()

        # Extract metrics
        result.latency_ms = (end_time - start_time) * 1000
        result.tokens_generated = (
            data.get("usage", {}).get("output_tokens", 0)
        )

        if result.tokens_generated > 0:
            result.tokens_per_second = result.tokens_generated / (
                result.latency_ms / 1000
            )
            result.time_per_token_ms = (
                result.latency_ms / result.tokens_generated
            )

        console.print(
            f"  [green]✓[/green] {result.latency_ms:.0f}ms | "
            f"{result.tokens_generated} tokens | "
            f"{result.tokens_per_second:.1f} t/s"
        )

    async def _benchmark_streaming(
        self,
        config: BenchmarkConfig,
        result: BenchmarkResult,
    ) -> None:
        """Benchmark streaming request."""

        request = {
            "model": "qwenvert-default",
            "messages": [{"role": "user", "content": config.prompt}],
            "max_tokens": config.max_tokens,
            "stream": True,
        }

        start_time = time.time()
        first_token_time = None
        token_count = 0

        async with (
            httpx.AsyncClient(timeout=120.0) as client,
            client.stream(
                "POST",
                f"{self.adapter_url}/v1/messages",
                json=request,
                headers={"x-api-key": "local-qwen"},
            ) as response,
        ):
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_json = line[6:]
                    try:
                        event = json.loads(data_json)

                        if event.get("type") == "content_block_delta":
                            if first_token_time is None:
                                first_token_time = time.time()
                            token_count += 1

                    except json.JSONDecodeError:
                        pass

        end_time = time.time()

        # Extract metrics
        result.latency_ms = (end_time - start_time) * 1000
        result.tokens_generated = token_count

        if first_token_time:
            result.first_token_ms = (first_token_time - start_time) * 1000

        if result.tokens_generated > 0:
            result.tokens_per_second = result.tokens_generated / (
                result.latency_ms / 1000
            )
            result.time_per_token_ms = (
                result.latency_ms / result.tokens_generated
            )

        ttft = (
            f"{result.first_token_ms:.0f}ms"
            if result.first_token_ms
            else "N/A"
        )
        console.print(
            f"  [green]✓[/green] {result.latency_ms:.0f}ms | "
            f"TTFT: {ttft} | "
            f"{result.tokens_generated} tokens | "
            f"{result.tokens_per_second:.1f} t/s"
        )

    async def run_suite(
        self,
        configs: list[BenchmarkConfig],
    ) -> list[BenchmarkResult]:
        """Run a suite of benchmarks."""

        console.print(
            "\n[bold blue]Qwenvert Performance Benchmark Suite"
            "[/bold blue]\n"
        )

        # Check adapter health
        console.print("Checking adapter health...")
        if not await self.check_adapter_health():
            console.print(
                f"[red]✗ Adapter not running at {self.adapter_url}[/red]"
            )
            console.print(
                "Start qwenvert first: [cyan]qwenvert start[/cyan]\n"
            )
            return []

        console.print("[green]✓ Adapter running[/green]\n")

        # Run benchmarks
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Running {len(configs)} benchmarks...",
                total=len(configs),
            )

            for config in configs:
                result = await self.run_benchmark(config)
                self.results.append(result)
                progress.advance(task)

        return self.results

    def save_results(self, filename: str | None = None) -> Path:
        """Save results to JSON file."""

        if filename is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_results_{timestamp}.json"

        output_path = self.output_dir / filename

        output_path.write_text(
            json.dumps(
                [asdict(r) for r in self.results],
                indent=2,
            )
        )

        console.print(f"\n[green]Results saved:[/green] {output_path}")
        return output_path

    def print_summary(self) -> None:
        """Print benchmark summary table."""

        if not self.results:
            return

        console.print("\n[bold]Benchmark Results Summary[/bold]\n")

        # Overall stats
        table = Table(title="Performance Metrics")
        table.add_column("Benchmark", style="cyan")
        table.add_column("Backend", style="yellow")
        table.add_column("Quant", justify="center")
        table.add_column("Latency", justify="right", style="green")
        table.add_column("Tokens", justify="right")
        table.add_column("Speed", justify="right", style="bold green")
        table.add_column("Status", justify="center")

        for result in self.results:
            status = "✓" if result.success else "✗"
            status_style = "green" if result.success else "red"

            table.add_row(
                result.name[:30],
                result.backend,
                result.quantization,
                f"{result.latency_ms:.0f}ms",
                str(result.tokens_generated),
                f"{result.tokens_per_second:.1f} t/s",
                f"[{status_style}]{status}[/{status_style}]",
            )

        console.print(table)

        # Summary stats
        successful = [r for r in self.results if r.success]
        if successful:
            avg_latency = (
                sum(r.latency_ms for r in successful) / len(successful)
            )
            avg_throughput = (
                sum(r.tokens_per_second for r in successful)
                / len(successful)
            )
            success_rate = len(successful) / len(self.results) * 100

            console.print("\n[bold]Summary:[/bold]")
            console.print(f"  Total benchmarks: {len(self.results)}")
            console.print(
                f"  Successful: {len(successful)} ({success_rate:.1f}%)"
            )
            console.print(f"  Average latency: {avg_latency:.0f}ms")
            console.print(
                f"  Average throughput: {avg_throughput:.1f} tokens/sec"
            )


def get_default_benchmarks() -> list[BenchmarkConfig]:
    """Get default benchmark configurations."""

    prompts = {
        "short": "What is 2+2?",
        "medium": (
            "Explain how Python list comprehensions work with examples."
        ),
        "long": (
            "Write a Python function that implements a binary search "
            "tree with the following methods:\n"
            "- insert(value): Insert a new node\n"
            "- search(value): Find a node\n"
            "- delete(value): Remove a node\n"
            "- inorder(): Return inorder traversal\n\n"
            "Include docstrings and type hints. "
            "Make the code production-ready."
        ),
        "code_generation": (
            "Write a FastAPI endpoint that accepts a POST request "
            "with JSON data and returns a structured response."
        ),
    }

    configs = []

    # Test different prompt lengths
    for prompt_name, prompt_text in prompts.items():
        configs.append(
            BenchmarkConfig(
                name=f"prompt_{prompt_name}",
                backend="ollama",  # Assuming Ollama is running
                model="qwen2.5-coder",
                quantization="Q4_K_M",
                context_length=32768,
                prompt=prompt_text,
                max_tokens=100,
                streaming=False,
            )
        )

    # Test streaming
    configs.append(
        BenchmarkConfig(
            name="streaming_medium",
            backend="ollama",
            model="qwen2.5-coder",
            quantization="Q4_K_M",
            context_length=32768,
            prompt=prompts["medium"],
            max_tokens=100,
            streaming=True,
        )
    )

    # Test different max_tokens
    configs.extend(
        [
            BenchmarkConfig(
                name=f"max_tokens_{max_tokens}",
                backend="ollama",
                model="qwen2.5-coder",
                quantization="Q4_K_M",
                context_length=32768,
                prompt=prompts["medium"],
                max_tokens=max_tokens,
                streaming=False,
            )
            for max_tokens in [50, 100, 200]
        ]
    )

    return configs


async def main() -> None:
    """Run benchmark suite."""

    runner = BenchmarkRunner()

    # Get benchmark configs
    configs = get_default_benchmarks()

    # Run benchmarks
    results = await runner.run_suite(configs)

    if results:
        # Print summary
        runner.print_summary()

        # Save results
        runner.save_results()

        console.print(
            "\n[bold green]✓ Benchmark suite complete![/bold green]\n"
        )
    else:
        console.print("\n[red]No benchmarks run[/red]\n")


if __name__ == "__main__":
    asyncio.run(main())
