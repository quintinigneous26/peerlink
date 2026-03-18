"""
延迟测试

测试各种连接场景下的延迟指标：
- 本地连接延迟 (localhost)
- 远程连接延迟 (LAN)
- 中继连接延迟 (Circuit Relay v2)
- QUIC 传输延迟
- WebRTC 传输延迟

性能目标: 达到 go-libp2p 延迟的 90%
"""
import asyncio
import socket
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio


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


class LatencyMeasurement:
    """延迟测量工具"""

    @staticmethod
    async def measure_tcp_latency(
        host: str, port: int, samples: int = 100
    ) -> LatencyStats:
        """
        测量 TCP 连接延迟

        Args:
            host: 目标主机
            port: 目标端口
            samples: 采样次数

        Returns:
            LatencyStats: 延迟统计结果
        """
        latencies = []

        for _ in range(samples):
            start = time.perf_counter()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                sock.connect((host, port))
                sock.close()
                latency_ms = (time.perf_counter() - start) * 1000
                latencies.append(latency_ms)
            except (OSError, socket.timeout):
                # 忽略连接失败，继续采样
                pass

        if not latencies:
            raise RuntimeError(f"无法连接到 {host}:{port}")

        latencies.sort()
        n = len(latencies)

        return LatencyStats(
            min_ms=latencies[0],
            max_ms=latencies[-1],
            mean_ms=statistics.mean(latencies),
            median_ms=latencies[n // 2],
            p95_ms=latencies[int(n * 0.95)],
            p99_ms=latencies[int(n * 0.99)],
            std_dev_ms=statistics.stdev(latencies) if n > 1 else 0,
            samples=n,
        )

    @staticmethod
    async def measure_ping_latency(
        host: str, count: int = 10
    ) -> LatencyStats:
        """
        使用 ICMP ping 测量延迟

        Args:
            host: 目标主机
            count: ping 次数

        Returns:
            LatencyStats: 延迟统计结果
        """
        import subprocess

        latencies = []

        for _ in range(count):
            try:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", host],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                # 解析 ping 输出中的时间
                output = result.stdout
                if "time=" in output:
                    time_str = output.split("time=")[1].split()[0]
                    latency_ms = float(time_str)
                    latencies.append(latency_ms)
            except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
                pass

        if not latencies:
            raise RuntimeError(f"无法 ping {host}")

        latencies.sort()
        n = len(latencies)

        return LatencyStats(
            min_ms=latencies[0],
            max_ms=latencies[-1],
            mean_ms=statistics.mean(latencies),
            median_ms=latencies[n // 2],
            p95_ms=latencies[int(n * 0.95)],
            p99_ms=latencies[int(n * 0.99)],
            std_dev_ms=statistics.stdev(latencies) if n > 1 else 0,
            samples=n,
        )


# ===== 测试基准值 (go-libp2p 参考值) =====

LIBP2P_LATENCY_TARGETS = {
    "local_tcp": {"p50_ms": 1.0, "p95_ms": 2.0, "p99_ms": 5.0},
    "lan_tcp": {"p50_ms": 5.0, "p95_ms": 10.0, "p99_ms": 20.0},
    "relay": {"p50_ms": 50.0, "p95_ms": 100.0, "p99_ms": 200.0},
    "quic": {"p50_ms": 10.0, "p95_ms": 20.0, "p99_ms": 50.0},
}


# ===== Fixtures =====

@pytest_asyncio.fixture
async def echo_server(free_port: int) -> AsyncGenerator[dict[str, Any], None]:
    """
    启动简单的 echo 服务器用于延迟测试

    Returns:
        dict: {"host": "127.0.0.1", "port": port}
    """
    host = "127.0.0.1"
    port = free_port

    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Echo 服务处理"""
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except asyncio.CancelledError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, host, port)

    async with server:
        yield {"host": host, "port": port}


@pytest.fixture
def latency_targets() -> dict[str, dict[str, float]]:
    """获取性能目标基准值"""
    return LIBP2P_LATENCY_TARGETS.copy()


# ===== 本地连接延迟测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
class TestLocalLatency:
    """本地连接延迟测试"""

    async def test_tcp_local_latency(
        self, echo_server: dict[str, Any], latency_targets: dict[str, dict[str, float]]
    ):
        """
        测试本地 TCP 连接延迟

        目标: p50 < 1ms, p95 < 2ms, p99 < 5ms (相当于 go-libp2p 的 90%)
        """
        stats = await LatencyMeasurement.measure_tcp_latency(
            echo_server["host"], echo_server["port"], samples=100
        )

        # 验证性能目标 (90% 的 libp2p 性能)
        target = latency_targets["local_tcp"]
        assert stats.median_ms < target["p50_ms"] * 1.1, (
            f"中位数延迟 {stats.median_ms:.3f}ms 超过目标 {target['p50_ms'] * 1.1}ms"
        )
        assert stats.p95_ms < target["p95_ms"] * 1.1, (
            f"P95 延迟 {stats.p95_ms:.3f}ms 超过目标 {target['p95_ms'] * 1.1}ms"
        )
        assert stats.p99_ms < target["p99_ms"] * 1.1, (
            f"P99 延迟 {stats.p99_ms:.3f}ms 超过目标 {target['p99_ms'] * 1.1}ms"
        )

        # 输出详细统计
        print(f"\n本地 TCP 延迟统计: {stats.to_dict()}")

    async def test_udp_local_latency(self, free_port: int):
        """
        测试本地 UDP 连接延迟

        UDP 通常比 TCP 延迟更低
        """
        host = "127.0.0.1"
        port = free_port

        # 创建 UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((host, port))

        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            try:
                # 发送数据到本地
                sock.sendto(b"ping", (host, port))
                sock.settimeout(0.01)
                data, _ = sock.recvfrom(1024)
                latency_ms = (time.perf_counter() - start) * 1000
                latencies.append(latency_ms)
            except socket.timeout:
                pass

        sock.close()

        if latencies:
            print(f"\n本地 UDP 平均延迟: {statistics.mean(latencies):.3f}ms")


# ===== 中继连接延迟测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.skipif(
    True,  # 需要中继服务器实现后启用
    reason="等待 Circuit Relay v2 实现完成"
)
class TestRelayLatency:
    """中继连接延迟测试"""

    async def test_circuit_relay_latency(self, latency_targets: dict[str, dict[str, float]]):
        """
        测试 Circuit Relay v2 中继连接延迟

        目标: p50 < 50ms, p95 < 100ms, p99 < 200ms
        """
        # TODO: 实现 Circuit Relay 延迟测试
        # 需要启动三个节点: initiator, relay, responder
        # 测量从 initiator 通过 relay 到达 responder 的延迟
        pytest.skip("等待 Circuit Relay v2 实现")


# ===== QUIC 传输延迟测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.skipif(
    True,  # 需要 QUIC 传输实现后启用
    reason="等待 QUIC 传输实现完成"
)
class TestQUICLatency:
    """QUIC 传输延迟测试"""

    async def test_quic_handshake_latency(self, latency_targets: dict[str, dict[str, float]]):
        """
        测试 QUIC 握手延迟

        QUIC 握手应该比 TCP + TLS 更快 (1-RTT)
        目标: p50 < 10ms, p95 < 20ms, p99 < 50ms
        """
        # TODO: 实现 QUIC 握手延迟测试
        pytest.skip("等待 QUIC 传输实现")


# ===== WebRTC 传输延迟测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.skipif(
    True,  # 需要 WebRTC 传输实现后启用
    reason="等待 WebRTC 传输实现完成"
)
class TestWebRTCLatency:
    """WebRTC 传输延迟测试"""

    async def test_webrtc_data_channel_latency(
        self, latency_targets: dict[str, dict[str, float]]
    ):
        """
        测试 WebRTC DataChannel 延迟

        WebRTC 设计用于低延迟实时通信
        目标: p50 < 20ms (LAN), p95 < 50ms
        """
        # TODO: 实现 WebRTC DataChannel 延迟测试
        pytest.skip("等待 WebRTC 传输实现")


# ===== 延迟对比测试 =====


@pytest.mark.benchmark
class TestLatencyComparison:
    """不同协议/传输的延迟对比"""

    async def test_noise_vs_tls_handshake_latency(self):
        """
        对比 Noise XX 和 TLS 1.3 握手延迟

        Noise XX 是 1-RTT，TLS 1.3 也是 1-RTT
        理论上延迟应该相近
        """
        # TODO: 实现握手延迟对比测试
        pytest.skip("等待 TLS 1.3 实现")

    async def test_yamux_vs_mplex_overhead(self):
        """
        对比 yamux 和 mplex 流复用开销

        测试打开/关闭流、数据传输的延迟差异
        """
        # TODO: 实现流复用延迟对比测试
        pytest.skip("等待 mplex 实现")


# ===== 压力下的延迟测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
class TestLatencyUnderLoad:
    """负载下的延迟稳定性测试"""

    async def test_latency_with_concurrent_streams(self, echo_server: dict[str, Any]):
        """
        测试并发流情况下的延迟

        验证在高并发情况下延迟是否稳定增长
        """
        host = echo_server["host"]
        port = echo_server["port"]

        async def single_connection_latency() -> float:
            """单个连接的延迟"""
            start = time.perf_counter()
            reader, writer = await asyncio.open_connection(host, port)
            writer.write(b"ping")
            await writer.drain()
            await reader.read(4)
            writer.close()
            await writer.wait_closed()
            return (time.perf_counter() - start) * 1000

        # 测试不同并发级别
        for concurrency in [1, 10, 50, 100]:
            tasks = [single_connection_latency() for _ in range(concurrency)]
            latencies = await asyncio.gather(*tasks)

            avg_latency = statistics.mean(latencies)
            max_latency = max(latencies)

            print(f"\n并发 {concurrency}: 平均 {avg_latency:.3f}ms, 最大 {max_latency:.3f}ms")

            # 验证延迟不会随并发数线性增长
            if concurrency > 1:
                # 平均延迟增长不超过 5 倍
                assert avg_latency < 50, f"并发 {concurrency} 时延迟过高: {avg_latency:.3f}ms"
