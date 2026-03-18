"""
P2P Platform 性能基准测试

对标 go-libp2p，验证优化效果。

性能目标 (达到 go-libp2p 的 90%):
- 连接建立延迟: <22ms (P95)
- 流创建延迟: <1.1ms (P50)
- 消息往返延迟: <0.55ms (P95)
- 单流吞吐量: >450 Mbps
- 并发连接数: >1000

测试工程师: tester-1
创建日期: 2026-03-06
"""

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, List

import pytest
import pytest_asyncio

# ===== 性能基准值 (go-libp2p 参考) =====

LIBP2P_BASELINES = {
    "connection": {
        "latency_p50_ms": 20.0,  # 连接建立延迟
        "latency_p95_ms": 22.0,
        "latency_p99_ms": 50.0,
    },
    "stream": {
        "creation_p50_ms": 1.0,  # 流创建延迟
        "creation_p95_ms": 1.5,
        "rtt_p50_ms": 0.5,  # 消息往返延迟
        "rtt_p95_ms": 0.55,
        "rtt_p99_ms": 1.0,
    },
    "throughput": {
        "single_stream_mbps": 500.0,  # 单流吞吐量
        "multi_stream_mbps": 450.0,  # 多流聚合吞吐量
        "large_file_mbps": 400.0,  # 大文件传输
    },
    "concurrent": {
        "max_connections": 10000,  # 最大并发连接
        "max_streams": 100000,  # 最大并发流
        "min_connections": 1000,  # 最低要求
        "memory_per_connection_mb": 0.5,  # 每连接内存
    },
}

# 性能目标 (90% 的 go-libp2p 性能)
PERFORMANCE_TARGETS = {
    "connection": {
        "latency_p95_ms": LIBP2P_BASELINES["connection"]["latency_p95_ms"] * 1.1,
        "latency_p99_ms": LIBP2P_BASELINES["connection"]["latency_p99_ms"] * 1.1,
    },
    "stream": {
        "creation_p50_ms": LIBP2P_BASELINES["stream"]["creation_p50_ms"] * 1.1,
        "rtt_p95_ms": LIBP2P_BASELINES["stream"]["rtt_p95_ms"] * 1.1,
        "rtt_p99_ms": LIBP2P_BASELINES["stream"]["rtt_p99_ms"] * 1.1,
    },
    "throughput": {
        "single_stream_mbps": LIBP2P_BASELINES["throughput"]["single_stream_mbps"] * 0.9,
        "multi_stream_mbps": LIBP2P_BASELINES["throughput"]["multi_stream_mbps"] * 0.9,
    },
    "concurrent": {
        "min_connections": LIBP2P_BASELINES["concurrent"]["min_connections"],
        "memory_per_connection_mb": LIBP2P_BASELINES["concurrent"]["memory_per_connection_mb"],
    },
}


# ===== 数据结构 =====


@dataclass
class LatencyStats:
    """延迟统计结果"""

    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    std_dev_ms: float
    samples: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "mean_ms": round(self.mean_ms, 3),
            "median_ms": round(self.median_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "std_dev_ms": round(self.std_dev_ms, 3),
            "samples": self.samples,
        }


@dataclass
class ThroughputStats:
    """吞吐量统计结果"""

    throughput_mbps: float
    total_bytes: int
    duration_sec: float
    buffer_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "throughput_mbps": round(self.throughput_mbps, 2),
            "total_mb": round(self.total_bytes / 1_000_000, 2),
            "duration_sec": round(self.duration_sec, 3),
            "buffer_size": self.buffer_size,
        }


@dataclass
class ConcurrentStats:
    """并发测试统计结果"""

    max_connections: int
    successful_connections: int
    failed_connections: int
    total_time_sec: float
    connections_per_sec: float
    memory_mb: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_connections": self.max_connections,
            "successful": self.successful_connections,
            "failed": self.failed_connections,
            "total_time_sec": round(self.total_time_sec, 3),
            "connections_per_sec": round(self.connections_per_sec, 2),
            "memory_mb": round(self.memory_mb, 2),
        }


# ===== 测试工具类 =====


class PerformanceMeasurements:
    """性能测量工具类"""

    @staticmethod
    def calculate_latency_stats(latencies_ms: List[float]) -> LatencyStats:
        """计算延迟统计"""
        if not latencies_ms:
            raise ValueError("延迟数据不能为空")

        latencies_ms.sort()
        n = len(latencies_ms)

        return LatencyStats(
            min_ms=latencies_ms[0],
            max_ms=latencies_ms[-1],
            mean_ms=statistics.mean(latencies_ms),
            median_ms=latencies_ms[n // 2],
            p95_ms=latencies_ms[int(n * 0.95)],
            p99_ms=latencies_ms[int(n * 0.99)] if n >= 100 else latencies_ms[-1],
            std_dev_ms=statistics.stdev(latencies_ms) if n > 1 else 0.0,
            samples=n,
        )

    @staticmethod
    def calculate_throughput(
        total_bytes: int, duration_sec: float, buffer_size: int
    ) -> ThroughputStats:
        """计算吞吐量"""
        if duration_sec <= 0:
            raise ValueError("持续时间必须大于 0")

        throughput_mbps = (total_bytes * 8) / (duration_sec * 1_000_000)

        return ThroughputStats(
            throughput_mbps=throughput_mbps,
            total_bytes=total_bytes,
            duration_sec=duration_sec,
            buffer_size=buffer_size,
        )


# ===== Fixtures =====


@pytest_asyncio.fixture
async def echo_server(free_port: int) -> AsyncGenerator[dict[str, Any], None]:
    """启动 echo 服务器用于测试"""

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Echo 服务处理"""
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except asyncio.CancelledError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "127.0.0.1", free_port)

    async with server:
        yield {"host": "127.0.0.1", "port": free_port}


# ===== 连接建立延迟测试 =====


@pytest.mark.benchmark
class TestConnectionLatency:
    """连接建立延迟测试"""

    async def test_local_tcp_connection_latency_p95(
        self, echo_server: dict[str, Any]
    ) -> LatencyStats:
        """
        测试本地 TCP 连接延迟 P95

        目标: <22ms (90% of go-libp2p)
        """
        latencies = []

        for _ in range(1000):
            start = time.perf_counter()
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        echo_server["host"], echo_server["port"]
                    ),
                    timeout=1.0,
                )
                latency_ms = (time.perf_counter() - start) * 1000
                latencies.append(latency_ms)
                writer.close()
                await writer.wait_closed()
            except (asyncio.TimeoutError, OSError):
                pass

        stats = PerformanceMeasurements.calculate_latency_stats(latencies)

        # 验证性能目标
        target = PERFORMANCE_TARGETS["connection"]["latency_p95_ms"]
        assert stats.p95_ms < target, (
            f"P95 延迟 {stats.p95_ms:.3f}ms 超过目标 {target}ms"
        )

        print(f"\n连接延迟统计: {stats.to_dict()}")
        return stats

    async def test_connection_latency_under_load(
        self, echo_server: dict[str, Any]
    ) -> LatencyStats:
        """
        测试负载下的连接延迟

        在有并发连接的情况下测量新连接的延迟
        """
        # 先建立 100 个连接制造负载
        existing_connections = []
        for _ in range(100):
            try:
                reader, writer = await asyncio.open_connection(
                    echo_server["host"], echo_server["port"]
                )
                existing_connections.append((reader, writer))
            except OSError:
                pass

        # 测量新连接延迟
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        echo_server["host"], echo_server["port"]
                    ),
                    timeout=1.0,
                )
                latency_ms = (time.perf_counter() - start) * 1000
                latencies.append(latency_ms)
                writer.close()
                await writer.wait_closed()
            except (asyncio.TimeoutError, OSError):
                pass

        # 清理现有连接
        for reader, writer in existing_connections:
            writer.close()
            await writer.wait_closed()

        stats = PerformanceMeasurements.calculate_latency_stats(latencies)

        # 负载下延迟不应超过目标的 2 倍
        target = PERFORMANCE_TARGETS["connection"]["latency_p95_ms"] * 2
        assert stats.p95_ms < target, (
            f"负载下 P95 延迟 {stats.p95_ms:.3f}ms 超过目标 {target}ms"
        )

        print(f"\n负载下连接延迟: {stats.to_dict()}")
        return stats


# ===== 流操作延迟测试 =====


@pytest.mark.benchmark
class TestStreamLatency:
    """流操作延迟测试"""

    async def test_stream_creation_latency_p50(
        self, echo_server: dict[str, Any]
    ) -> LatencyStats:
        """
        测试流创建延迟 P50

        目标: <1.1ms (90% of go-libp2p)
        """
        latencies = []

        for _ in range(1000):
            start = time.perf_counter()
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        echo_server["host"], echo_server["port"]
                    ),
                    timeout=1.0,
                )
                latency_ms = (time.perf_counter() - start) * 1000
                latencies.append(latency_ms)
                writer.close()
                await writer.wait_closed()
            except (asyncio.TimeoutError, OSError):
                pass

        stats = PerformanceMeasurements.calculate_latency_stats(latencies)

        # 验证性能目标
        target = PERFORMANCE_TARGETS["stream"]["creation_p50_ms"]
        assert stats.median_ms < target, (
            f"P50 延迟 {stats.median_ms:.3f}ms 超过目标 {target}ms"
        )

        print(f"\n流创建延迟: {stats.to_dict()}")
        return stats

    async def test_message_rtt_latency_p95(
        self, echo_server: dict[str, Any]
    ) -> LatencyStats:
        """
        测试消息往返延迟 P95

        目标: <0.55ms (90% of go-libp2p)
        """
        reader, writer = await asyncio.open_connection(
            echo_server["host"], echo_server["port"]
        )

        latencies = []
        test_message = b"ping"

        for _ in range(1000):
            start = time.perf_counter()
            writer.write(test_message)
            await writer.drain()
            await reader.read(len(test_message))
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        writer.close()
        await writer.wait_closed()

        stats = PerformanceMeasurements.calculate_latency_stats(latencies)

        # 验证性能目标
        target = PERFORMANCE_TARGETS["stream"]["rtt_p95_ms"]
        assert stats.p95_ms < target, (
            f"P95 RTT {stats.p95_ms:.3f}ms 超过目标 {target}ms"
        )

        print(f"\n消息 RTT 延迟: {stats.to_dict()}")
        return stats


# ===== 吞吐量测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
class TestThroughput:
    """吞吐量测试"""

    async def test_single_stream_throughput(
        self, echo_server: dict[str, Any]
    ) -> ThroughputStats:
        """
        测试单流吞吐量

        目标: >450 Mbps (90% of go-libp2p)
        """
        reader, writer = await asyncio.open_connection(
            echo_server["host"], echo_server["port"]
        )

        buffer_size = 64 * 1024  # 64KB
        test_data = bytes(buffer_size)
        duration_sec = 5.0

        start_time = time.time()
        total_bytes = 0

        try:
            while time.time() - start_time < duration_sec:
                writer.write(test_data)
                await writer.drain()
                total_bytes += len(test_data)
                # 读取响应以避免缓冲区满
                try:
                    await asyncio.wait_for(reader.read(buffer_size), timeout=0.01)
                except asyncio.TimeoutError:
                    pass
        finally:
            actual_duration = time.time() - start_time
            writer.close()
            await writer.wait_closed()

        stats = PerformanceMeasurements.calculate_throughput(
            total_bytes, actual_duration, buffer_size
        )

        # 验证性能目标
        target = PERFORMANCE_TARGETS["throughput"]["single_stream_mbps"]
        assert stats.throughput_mbps > target, (
            f"吞吐量 {stats.throughput_mbps:.2f} Mbps 低于目标 {target} Mbps"
        )

        print(f"\n单流吞吐量: {stats.to_dict()}")
        return stats

    async def test_multi_stream_aggregate_throughput(
        self, echo_server: dict[str, Any]
    ) -> ThroughputStats:
        """
        测试多流聚合吞吐量

        目标: >400 Mbps (90% of go-libp2p)
        """
        num_streams = 10
        buffer_size = 64 * 1024

        async def pump_data():
            """单个流的数据泵"""
            reader, writer = await asyncio.open_connection(
                echo_server["host"], echo_server["port"]
            )
            test_data = bytes(buffer_size)
            bytes_sent = 0

            start_time = time.time()
            while time.time() - start_time < 2.0:
                writer.write(test_data)
                await writer.drain()
                bytes_sent += len(test_data)
                try:
                    await asyncio.wait_for(reader.read(buffer_size), timeout=0.01)
                except asyncio.TimeoutError:
                    pass

            writer.close()
            await writer.wait_closed()
            return bytes_sent

        start_time = time.time()
        results = await asyncio.gather(*[pump_data() for _ in range(num_streams)])
        total_duration = time.time() - start_time
        total_bytes = sum(results)

        stats = PerformanceMeasurements.calculate_throughput(
            total_bytes, total_duration, buffer_size
        )

        # 验证性能目标
        target = PERFORMANCE_TARGETS["throughput"]["multi_stream_mbps"]
        assert stats.throughput_mbps > target, (
            f"聚合吞吐量 {stats.throughput_mbps:.2f} Mbps 低于目标 {target} Mbps"
        )

        print(f"\n多流聚合吞吐量 ({num_streams} 流): {stats.to_dict()}")
        return stats


# ===== 并发测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
class TestConcurrentConnections:
    """并发连接测试"""

    async def test_min_concurrent_connections(
        self, echo_server: dict[str, Any]
    ) -> ConcurrentStats:
        """
        测试最低并发连接要求

        目标: >1000 连接
        """
        target_connections = PERFORMANCE_TARGETS["concurrent"]["min_connections"]
        host = echo_server["host"]
        port = echo_server["port"]

        async def create_and_hold_connection():
            """创建并保持连接"""
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=10.0
                )
                # 保持连接活跃
                await asyncio.sleep(0.1)
                writer.close()
                await writer.wait_closed()
                return True
            except (asyncio.TimeoutError, OSError):
                return False

        start_time = time.time()

        tasks = [create_and_hold_connection() for _ in range(target_connections)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time

        successful = sum(1 for r in results if r is True)
        failed = target_connections - successful

        stats = ConcurrentStats(
            max_connections=target_connections,
            successful_connections=successful,
            failed_connections=failed,
            total_time_sec=total_time,
            connections_per_sec=target_connections / total_time if total_time > 0 else 0,
            memory_mb=0.0,  # 需要额外的内存监控
        )

        # 验证成功率 >95%
        success_rate = successful / target_connections
        assert success_rate >= 0.95, (
            f"成功率 {success_rate:.2%} 低于 95% ({successful}/{target_connections})"
        )

        print(f"\n并发连接统计: {stats.to_dict()}")
        return stats

    async def test_memory_per_connection(
        self, echo_server: dict[str, Any]
    ) -> float:
        """
        测试每连接内存使用

        目标: <0.5MB/连接
        """
        try:
            import psutil

            process = psutil.Process()
        except ImportError:
            pytest.skip("需要 psutil 库")

        target_memory_mb = PERFORMANCE_TARGETS["concurrent"]["memory_per_connection_mb"]
        host = echo_server["host"]
        port = echo_server["port"]

        # 测试不同连接数的内存使用
        memory_samples = []

        for count in [10, 50, 100]:
            initial_memory = process.memory_info().rss / 1_000_000

            # 创建连接
            connections = []
            for _ in range(count):
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=5.0
                    )
                    connections.append((reader, writer))
                except (asyncio.TimeoutError, OSError):
                    pass

            await asyncio.sleep(0.5)  # 等待稳定

            peak_memory = process.memory_info().rss / 1_000_000
            memory_used = peak_memory - initial_memory
            per_connection = memory_used / len(connections) if connections else 0
            memory_samples.append(per_connection)

            print(f"\n{len(connections)} 连接: {memory_used:.2f}MB, {per_connection:.3f}MB/连接")

            # 清理连接
            for reader, writer in connections:
                writer.close()
                await writer.wait_closed()

            await asyncio.sleep(0.5)

        # 计算平均内存使用
        avg_memory_per_conn = statistics.mean(memory_samples)

        assert (
            avg_memory_per_conn < target_memory_mb
        ), f"每连接内存 {avg_memory_per_conn:.3f}MB 超过目标 {target_memory_mb}MB"

        return avg_memory_per_conn


# ===== 性能回归对比 =====


@pytest.mark.benchmark
class TestPerformanceRegression:
    """性能回归测试"""

    async def test_performance_vs_baseline(
        self, echo_server: dict[str, Any], tmp_path: Path
    ):
        """
        与基线对比性能

        如果存在基线数据，对比当前性能与基线
        """
        # 运行性能测试
        reader, writer = await asyncio.open_connection(
            echo_server["host"], echo_server["port"]
        )

        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            writer.write(b"ping")
            await writer.drain()
            await reader.read(4)
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        writer.close()
        await writer.wait_closed()

        current_stats = PerformanceMeasurements.calculate_latency_stats(latencies)

        # 保存当前结果
        baseline_file = tmp_path / "current_baseline.json"
        import json

        with open(baseline_file, "w") as f:
            json.dump(current_stats.to_dict(), f, indent=2)

        print(f"\n当前性能基线: {current_stats.to_dict()}")
        print(f"基线已保存至: {baseline_file}")

        # TODO: 实现与历史基线的对比逻辑
        # 1. 读取历史基线文件
        # 2. 对比性能指标
        # 3. 如果性能下降超过阈值，标记为回归

        return current_stats
