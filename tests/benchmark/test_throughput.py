"""
吞吐量测试

测试各种连接场景下的数据传输吞吐量：
- P2P 直连吞吐量 (TCP)
- 中继连接吞吐量 (Circuit Relay v2)
- QUIC 传输吞吐量
- WebRTC 传输吞吐量
- 多流并发吞吐量 (流复用)

性能目标: 达到 go-libp2p 吞吐量的 90%
"""
import asyncio
import statistics
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio


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


class ThroughputMeasurement:
    """吞吐量测量工具"""

    @staticmethod
    async def measure_tcp_throughput(
        host: str,
        port: int,
        duration_sec: float = 10.0,
        buffer_size: int = 64 * 1024,
    ) -> ThroughputStats:
        """
        测量 TCP 连接吞吐量

        Args:
            host: 目标主机
            port: 目标端口
            duration_sec: 测试持续时间（秒）
            buffer_size: 缓冲区大小

        Returns:
            ThroughputStats: 吞吐量统计结果
        """
        reader, writer = await asyncio.open_connection(host, port)

        # 准备测试数据
        test_data = bytes(buffer_size)

        start_time = time.time()
        total_bytes = 0
        end_time = start_time + duration_sec

        try:
            while time.time() < end_time:
                writer.write(test_data)
                await writer.drain()
                total_bytes += len(test_data)

                # 读取响应（如果服务器有响应）
                try:
                    await asyncio.wait_for(reader.read(buffer_size), timeout=0.1)
                except asyncio.TimeoutError:
                    pass

        finally:
            actual_duration = time.time() - start_time
            writer.close()
            await writer.wait_closed()

        # 计算吞吐量 (Mbps = bytes * 8 / 1_000_000 / seconds)
        throughput_mbps = (total_bytes * 8) / (actual_duration * 1_000_000)

        return ThroughputStats(
            throughput_mbps=throughput_mbps,
            total_bytes=total_bytes,
            duration_sec=actual_duration,
            buffer_size=buffer_size,
        )

    @staticmethod
    async def measure_stream_throughput(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        duration_sec: float = 10.0,
        buffer_size: int = 64 * 1024,
    ) -> ThroughputStats:
        """
        测量已建立连接的吞吐量

        Args:
            reader: 流读取器
            writer: 流写入器
            duration_sec: 测试持续时间
            buffer_size: 缓冲区大小

        Returns:
            ThroughputStats: 吞吐量统计结果
        """
        test_data = bytes(buffer_size)

        start_time = time.time()
        total_bytes = 0
        end_time = start_time + duration_sec

        try:
            while time.time() < end_time:
                writer.write(test_data)
                await writer.drain()
                total_bytes += len(test_data)

        finally:
            actual_duration = time.time() - start_time

        throughput_mbps = (total_bytes * 8) / (actual_duration * 1_000_000)

        return ThroughputStats(
            throughput_mbps=throughput_mbps,
            total_bytes=total_bytes,
            duration_sec=actual_duration,
            buffer_size=buffer_size,
        )


# ===== 测试基准值 (go-libp2p 参考值) =====

LIBP2P_THROUGHPUT_TARGETS = {
    "tcp_local": {"min_mbps": 500},  # 本地 TCP 应该 > 500 Mbps
    "tcp_lan": {"min_mbps": 100},  # LAN TCP 应该 > 100 Mbps
    "quic_local": {"min_mbps": 400},  # QUIC 本地
    "webrtc": {"min_mbps": 30},  # WebRTC DataChannel 典型值
}


# ===== Fixtures =====


@pytest_asyncio.fixture
async def throughput_server(free_port: int) -> AsyncGenerator[dict[str, Any], None]:
    """
    启动吞吐量测试服务器

    服务器简单地回显接收到的数据
    """
    host = "127.0.0.1"
    port = free_port

    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """吞吐量测试服务处理"""
        try:
            while True:
                data = await reader.read(64 * 1024)
                if not data:
                    break
                # 简单回显，不阻塞
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
def throughput_targets() -> dict[str, dict[str, float]]:
    """获取吞吐量目标基准值"""
    return LIBP2P_THROUGHPUT_TARGETS.copy()


# ===== TCP 吞吐量测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
class TestTCPThroughput:
    """TCP 吞吐量测试"""

    async def test_tcp_local_throughput(
        self,
        throughput_server: dict[str, Any],
        throughput_targets: dict[str, dict[str, float]],
    ):
        """
        测试本地 TCP 吞吐量

        目标: > 500 Mbps (本地回环)
        """
        stats = await ThroughputMeasurement.measure_tcp_throughput(
            throughput_server["host"],
            throughput_server["port"],
            duration_sec=5.0,
            buffer_size=64 * 1024,
        )

        # 验证性能目标
        target = throughput_targets["tcp_local"]
        assert (
            stats.throughput_mbps > target["min_mbps"]
        ), f"吞吐量 {stats.throughput_mbps:.2f} Mbps 低于目标 {target['min_mbps']} Mbps"

        print(f"\nTCP 吞吐量统计: {stats.to_dict()}")

    @pytest.mark.parametrize("buffer_size", [4 * 1024, 16 * 1024, 64 * 1024, 128 * 1024])
    async def test_tcp_throughput_vs_buffer_size(
        self, throughput_server: dict[str, Any], buffer_size: int
    ):
        """
        测试不同缓冲区大小对吞吐量的影响

        较大的缓冲区通常能获得更高的吞吐量
        """
        stats = await ThroughputMeasurement.measure_tcp_throughput(
            throughput_server["host"],
            throughput_server["port"],
            duration_sec=3.0,
            buffer_size=buffer_size,
        )

        print(f"\n缓冲区 {buffer_size // 1024}KB: {stats.throughput_mbps:.2f} Mbps")

        # 吞吐量应该随缓冲区增加而增加（但有上限）
        assert stats.throughput_mbps > 10, f"吞吐量过低: {stats.throughput_mbps:.2f} Mbps"


# ===== 流复用吞吐量测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
class TestMuxerThroughput:
    """流复用器吞吐量测试"""

    async def test_yamux_single_stream_throughput(self, free_port: int):
        """
        测试 yamux 单流吞吐量

        yamux 开销应该很小，接近原生 TCP
        """
        # TODO: 实现 yamux 吞吐量测试
        pytest.skip("等待 yamux 吞吐量测试实现")

    async def test_yamux_multi_stream_throughput(self, free_port: int):
        """
        测试 yamux 多流并发吞吐量

        多流并发应该能达到接近单流的吞吐量
        """
        # TODO: 实现 yamux 多流吞吐量测试
        pytest.skip("等待 yamux 多流吞吐量测试实现")

    @pytest.mark.skipif(
        True,  # 需要 mplex 实现后启用
        reason="等待 mplex 实现完成"
    )
    async def test_mplex_vs_yamux_throughput(self):
        """
        对比 mplex 和 yamux 的吞吐量

        mplex 使用帧分隔，yamux 使用长度前缀
        理论上 yamux 应该更高效
        """
        # TODO: 实现 mplex vs yamux 吞吐量对比
        pytest.skip("等待 mplex 实现")


# ===== 中继吞吐量测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.skipif(
    True,  # 需要中继服务器实现后启用
    reason="等待 Circuit Relay v2 实现完成"
)
class TestRelayThroughput:
    """中继连接吞吐量测试"""

    async def test_circuit_relay_throughput(self):
        """
        测试 Circuit Relay v2 中继吞吐量

        中继会引入额外开销，吞吐量会降低
        目标: > 10 Mbps (受限于中继节点)
        """
        # TODO: 实现中继吞吐量测试
        pytest.skip("等待 Circuit Relay v2 实现")


# ===== QUIC 吞吐量测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.skipif(
    True,  # 需要 QUIC 传输实现后启用
    reason="等待 QUIC 传输实现完成"
)
class TestQUICThroughput:
    """QUIC 传输吞吐量测试"""

    async def test_quic_local_throughput(
        self, throughput_targets: dict[str, dict[str, float]]
    ):
        """
        测试 QUIC 本地吞吐量

        QUIC 使用 UDP，应该能达到接近 TCP 的吞吐量
        目标: > 400 Mbps
        """
        # TODO: 实现 QUIC 吞吐量测试
        pytest.skip("等待 QUIC 传输实现")

    async def test_quic_stream_concurrency(self):
        """
        测试 QUIC 多流并发吞吐量

        QUIC 原生支持多流，应该没有额外开销
        """
        # TODO: 实现 QUIC 多流吞吐量测试
        pytest.skip("等待 QUIC 传输实现")


# ===== WebRTC 吞吐量测试 =====


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.skipif(
    True,  # 需要 WebRTC 传输实现后启用
    reason="等待 WebRTC 传输实现完成"
)
class TestWebRTCThroughput:
    """WebRTC 传输吞吐量测试"""

    async def test_webrtc_data_channel_throughput(
        self, throughput_targets: dict[str, dict[str, float]]
    ):
        """
        测试 WebRTC DataChannel 吞吐量

        DataChannel 受限于 SCTP 和浏览器实现
        目标: > 30 Mbps (典型值)
        """
        # TODO: 实现 WebRTC DataChannel 吞吐量测试
        pytest.skip("等待 WebRTC 传输实现")


# ===== 吞吐量稳定性测试 =====


@pytest.mark.benchmark
class TestThroughputStability:
    """吞吐量稳定性测试"""

    async def test_throughput_consistency(self, throughput_server: dict[str, Any]):
        """
        测试吞吐量一致性

        多次测量应该得到相近的结果
        """
        measurements = []

        for _ in range(5):
            stats = await ThroughputMeasurement.measure_tcp_throughput(
                throughput_server["host"],
                throughput_server["port"],
                duration_sec=2.0,
            )
            measurements.append(stats.throughput_mbps)

        # 计算变异系数
        mean = statistics.mean(measurements)
        std_dev = statistics.stdev(measurements) if len(measurements) > 1 else 0
        cv = (std_dev / mean) if mean > 0 else 0

        print(f"\n吞吐量一致性: 平均 {mean:.2f} Mbps, 标准差 {std_dev:.2f}, 变异系数 {cv:.3f}")

        # 变异系数应该小于 0.1 (10%)
        assert cv < 0.1, f"吞吐量不稳定，变异系数 {cv:.3f} 超过 0.1"
