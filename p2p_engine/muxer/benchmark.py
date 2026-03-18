"""
Performance Benchmarks for Muxer Implementations

This module provides benchmarks for yamux and mplex implementations
to measure:
- Stream creation latency
- Message throughput
- Concurrent stream handling
- Memory usage

Target performance goals (aligned with go-libp2p):
- Stream creation: < 2ms
- Message throughput: > 200 Mbps
- Concurrent streams: > 1000
- Connection establishment: < 30ms
"""

import asyncio
import time
import logging
import statistics
from typing import List, Dict, Any, Callable
from dataclasses import dataclass
import tracemalloc

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    p50_time: float
    p95_time: float
    p99_time: float
    throughput: float  # ops/sec or bytes/sec
    metadata: Dict[str, Any]


class MuxerBenchmark:
    """
    Benchmark suite for muxer implementations.

    Tests yamux and mplex against go-libp2p performance targets.
    """

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    async def benchmark_stream_creation(
        self,
        session_factory: Callable,
        target_latency_ms: float = 2.0,
        iterations: int = 1000,
    ) -> BenchmarkResult:
        """
        Benchmark stream creation latency.

        Target: < 2ms per stream
        """
        latencies = []

        for _ in range(iterations):
            session = session_factory()

            start = time.perf_counter()
            stream = await session.open_stream()
            end = time.perf_counter()

            latencies.append((end - start) * 1000)  # Convert to ms

            await stream.close()
            await session.close()

        avg = statistics.mean(latencies)
        minimum = min(latencies)
        maximum = max(latencies)
        p50 = statistics.median(latencies)
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile

        result = BenchmarkResult(
            name="stream_creation",
            iterations=iterations,
            total_time=sum(latencies) / 1000,
            avg_time=avg,
            min_time=minimum,
            max_time=maximum,
            p50_time=p50,
            p95_time=p95,
            p99_time=p99,
            throughput=1000 / avg,  # streams per second
            metadata={
                "target_latency_ms": target_latency_ms,
                "passed": avg < target_latency_ms,
            },
        )

        self.results.append(result)
        return result

    async def benchmark_message_throughput(
        self,
        stream_factory: Callable,
        message_size: int = 1024,  # 1KB
        target_mbps: float = 200.0,
        duration_sec: float = 5.0,
    ) -> BenchmarkResult:
        """
        Benchmark message throughput.

        Target: > 200 Mbps
        """
        stream = await stream_factory()

        total_bytes = 0
        start_time = time.time()
        times = []

        while time.time() - start_time < duration_sec:
            data = b"x" * message_size

            write_start = time.perf_counter()
            await stream.write(data)
            write_end = time.perf_counter()

            times.append((write_end - write_start) * 1000)
            total_bytes += message_size

        await stream.close()

        total_time = time.time() - start_time
        throughput_mbps = (total_bytes * 8) / (total_time * 1_000_000)

        avg_time = statistics.mean(times)

        result = BenchmarkResult(
            name="message_throughput",
            iterations=len(times),
            total_time=total_time,
            avg_time=avg_time,
            min_time=min(times),
            max_time=max(times),
            p50_time=statistics.median(times),
            p95_time=statistics.quantiles(times, n=20)[18],
            p99_time=statistics.quantiles(times, n=100)[98],
            throughput=throughput_mbps,
            metadata={
                "message_size": message_size,
                "target_mbps": target_mbps,
                "passed": throughput_mbps > target_mbps,
            },
        )

        self.results.append(result)
        return result

    async def benchmark_concurrent_streams(
        self,
        session_factory: Callable,
        target_streams: int = 1000,
        messages_per_stream: int = 10,
    ) -> BenchmarkResult:
        """
        Benchmark concurrent stream handling.

        Target: > 1000 concurrent streams
        """
        session = session_factory()

        async def use_stream(stream_id: int):
            """Single stream workload."""
            stream = await session.open_stream()

            for _ in range(messages_per_stream):
                data = b"test" * 256  # 1KB
                await stream.write(data)
                received = await stream.read(len(data))

            await stream.close()
            return stream_id

        start_time = time.time()

        # Create concurrent streams
        tasks = [use_stream(i) for i in range(target_streams)]
        await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        result = BenchmarkResult(
            name="concurrent_streams",
            iterations=target_streams,
            total_time=total_time,
            avg_time=total_time / target_streams,
            min_time=0,  # Not applicable for concurrent test
            max_time=0,
            p50_time=0,
            p95_time=0,
            p99_time=0,
            throughput=target_streams / total_time,  # streams/sec
            metadata={
                "messages_per_stream": messages_per_stream,
                "target_streams": target_streams,
                "passed": True,  # If we completed, we passed
            },
        )

        self.results.append(result)
        await session.close()
        return result

    async def benchmark_memory_usage(
        self,
        session_factory: Callable,
        streams: int = 100,
    ) -> BenchmarkResult:
        """
        Benchmark memory usage for multiple streams.
        """
        tracemalloc.start()

        # Baseline memory
        snapshot1 = tracemalloc.take_snapshot()

        # Create streams
        session = session_factory()
        active_streams = []

        for _ in range(streams):
            stream = await session.open_stream()
            active_streams.append(stream)

        # Peak memory
        snapshot2 = tracemalloc.take_snapshot()

        # Cleanup
        for stream in active_streams:
            await stream.close()
        await session.close()

        # Final memory
        snapshot3 = tracemalloc.take_snapshot()

        tracemalloc.stop()

        # Calculate memory usage
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_kb = sum(stat.size_diff for stat in top_stats) / 1024
        per_stream_kb = total_kb / streams

        result = BenchmarkResult(
            name="memory_usage",
            iterations=streams,
            total_time=0,
            avg_time=per_stream_kb,
            min_time=0,
            max_time=0,
            p50_time=0,
            p95_time=0,
            p99_time=0,
            throughput=0,
            metadata={
                "total_memory_kb": total_kb,
                "per_stream_kb": per_stream_kb,
                "streams": streams,
            },
        )

        self.results.append(result)
        return result

    def print_results(self) -> None:
        """Print all benchmark results."""
        print("\n" + "=" * 80)
        print("MUXER PERFORMANCE BENCHMARK RESULTS")
        print("=" * 80)

        for result in self.results:
            print(f"\n{result.name.upper().replace('_', ' ')}")
            print("-" * 80)
            print(f"Iterations:        {result.iterations:,}")
            print(f"Total time:        {result.total_time:.3f}s")
            print(f"Avg time:          {result.avg_time:.3f}ms")
            print(f"Min time:          {result.min_time:.3f}ms")
            print(f"Max time:          {result.max_time:.3f}ms")
            print(f"P50 time:          {result.p50_time:.3f}ms")
            print(f"P95 time:          {result.p95_time:.3f}ms")
            print(f"P99 time:          {result.p99_time:.3f}ms")
            print(f"Throughput:        {result.throughput:.2f}")

            if result.metadata:
                print("\nMetadata:")
                for key, value in result.metadata.items():
                    print(f"  {key}: {value}")

        print("\n" + "=" * 80)


async def run_yamux_benchmarks() -> None:
    """Run benchmarks for yamux implementation."""
    from .yamux import YamuxSession

    benchmark = MuxerBenchmark()

    # Setup test server
    async def yamux_session_factory():
        # For testing, create a loopback connection
        import socket

        # Create a pair of connected sockets
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("127.0.0.1", 0))
        server_sock.listen(1)

        port = server_sock.getsockname()[1]

        # Connect client
        reader, writer = await asyncio.open_connection("127.0.0.1", port)

        # Accept server
        server_reader, server_writer = await asyncio.open_connection(
            sock=server_sock.accept()[0]
        )

        session = YamuxSession(reader, writer, is_client=True)
        return session

    # Run benchmarks
    logger.info("Running yamux benchmarks...")

    try:
        await benchmark.benchmark_stream_creation(yamux_session_factory)
    except Exception as e:
        logger.error(f"Stream creation benchmark failed: {e}")

    try:
        await benchmark.benchmark_message_throughput(
            lambda: yamux_session_factory().open_stream()
        )
    except Exception as e:
        logger.error(f"Message throughput benchmark failed: {e}")

    benchmark.print_results()


async def run_mplex_benchmarks() -> None:
    """Run benchmarks for mplex implementation."""
    from .mplex import MplexSession

    benchmark = MuxerBenchmark()

    async def mplex_session_factory():
        import socket

        # Create a pair of connected sockets
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("127.0.0.1", 0))
        server_sock.listen(1)

        port = server_sock.getsockname()[1]

        # Connect client
        reader, writer = await asyncio.open_connection("127.0.0.1", port)

        session = MplexSession(reader, writer, is_client=True)
        return session

    # Run benchmarks
    logger.info("Running mplex benchmarks...")

    try:
        await benchmark.benchmark_stream_creation(mplex_session_factory)
    except Exception as e:
        logger.error(f"Stream creation benchmark failed: {e}")

    benchmark.print_results()


async def main():
    """Run all muxer benchmarks."""
    logging.basicConfig(level=logging.INFO)

    print("P2P Muxer Performance Benchmarks")
    print("Target: go-libp2p compatibility")
    print()

    await run_yamux_benchmarks()
    await run_mplex_benchmarks()


if __name__ == "__main__":
    asyncio.run(main())
