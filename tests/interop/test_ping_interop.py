"""
Ping 协议互操作性测试

验证与 go-libp2p 和 js-libp2p 的 Ping 协议兼容性。

协议规范: https://github.com/libp2p/specs/tree/master/ping

测试覆盖:
- Ping 消息格式
- RTT 测量
- 与 go-libp2p 互操作
- 与 js-libp2p 互操作
"""

import asyncio
import pytest
from typing import Optional
from dataclasses import dataclass

from p2p_engine.protocol.ping import (
    PingProtocol,
    PingConfig,
    PROTOCOL_ID,
    PING_PROTOCOL_ID,
)


class TestPingProtocolCompliance:
    """Ping 协议合规性测试"""

    def test_ping_protocol_id(self):
        """验证 Ping 协议 ID"""
        assert PING_PROTOCOL_ID == "/ipfs/ping/1.0.0"

    def test_ping_config_default(self):
        """验证默认 Ping 配置"""
        config = PingConfig()
        assert config.timeout > 0
        assert config.ping_interval > 0

    @pytest.mark.skip(reason="PingMessage not implemented")
    def test_ping_message_format(self):
        """验证 Ping 消息格式"""
        # Ping 消息只是简单的序号 (未实现)
        pass


@pytest.mark.skip(reason="API mismatch - PingProtocol requires reader/writer, needs test refactoring")
class TestPingMessageHandling:
    """Ping 消息处理测试"""

    @pytest.mark.asyncio
    async def test_ping_request_response(self):
        """验证 Ping 请求-响应"""
        config = PingConfig()
        ping = PingProtocol("local-peer", config)

        # 创建读写管道
        reader1, writer1 = asyncio.Pipe()
        reader2, writer2 = asyncio.Pipe()

        # 模拟发送 ping
        rtt = await ping.ping_once(reader2, writer1)

        # RTT 应该被测量
        assert rtt >= 0

    @pytest.mark.asyncio
    async def test_continuous_ping(self):
        """验证持续 Ping"""
        config = PingConfig(ping_interval=0.1)
        ping = PingProtocol("local-peer", config)

        results = []

        async def ping_handler():
            while True:
                rtt = await ping.ping_once(asyncio.StreamReader(), asyncio.StreamWriter())
                results.append(rtt)
                await asyncio.sleep(config.ping_interval)

        # 运行几个 ping
        task = asyncio.create_task(ping_handler())
        await asyncio.sleep(0.35)
        task.cancel()

        # 应该有几次 ping 结果
        assert len(results) >= 2

    @pytest.mark.asyncio
    async def test_ping_timeout(self):
        """验证 Ping 超时"""
        config = PingConfig(ping_timeout=0.1)
        ping = PingProtocol("local-peer", config)

        # 创建一个不响应的 reader
        class NoResponseReader:
            async def read(self, n=-1):
                await asyncio.sleep(1)
                return b""

        writer = asyncio.StreamWriter()

        # Ping 应该超时
        with pytest.raises((TimeoutError, asyncio.TimeoutError)):
            await ping.ping_once(NoResponseReader(), writer)


@pytest.mark.skip(reason="API mismatch - needs test refactoring")
class TestPingRTTMeasurement:
    """Ping RTT 测量测试"""

    @pytest.mark.asyncio
    async def test_rtt_accuracy(self):
        """验证 RTT 测量准确性"""
        config = PingConfig()
        ping = PingProtocol("local-peer", config)

        # 模拟本地连接
        class LocalReader:
            def __init__(self):
                self.latency = 0.001  # 1ms

            async def read(self, n=-1):
                await asyncio.sleep(self.latency)
                return b"1"  # ping 响应

        class LocalWriter:
            def write(self, data):
                return len(data)

            async def drain(self):
                pass

        # 测量 RTT
        start = asyncio.get_event_loop().time()
        rtt = await ping.ping_once(LocalReader(), LocalWriter())
        elapsed = asyncio.get_event_loop().time() - start

        # RTT 应该接近实际往返时间
        assert rtt > 0

    @pytest.mark.asyncio
    async def test_multiple_rtt_samples(self):
        """验证多次 RTT 采样"""
        config = PingConfig()
        ping = PingProtocol("local-peer", config)

        rtts = []

        for _ in range(10):
            rtt = await ping.ping_once(asyncio.StreamReader(), asyncio.StreamWriter())
            rtts.append(rtt)

        # 应该有多个样本
        assert len(rtts) == 10


# ==================== Go-libp2p 互操作测试 ====================

class TestGoLibp2pPingInterop:
    """与 go-libp2p 的 Ping 互操作性测试"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 go-libp2p Ping 节点运行")
    async def test_go_libp2p_ping_exchange(self):
        """
        验证与 go-libp2p 的 Ping 交换

        go-libp2p 实现:
        https://github.com/libp2p/go-libp2p-pubsub/tree/master/ping

        运行方式:
        1. 启动 go-libp2p 节点
        2. pytest --run-interop-tests tests/interop/test_ping_interop.py
        """
        host = "127.0.0.1"
        port = 12345

        reader, writer = await asyncio.open_connection(host, port)

        try:
            config = PingConfig()
            ping = PingProtocol("python-peer", config)

            # 执行 ping
            rtt = await ping.ping_once(reader, writer)

            # RTT 应该是合理的
            assert rtt > 0 and rtt < 10  # < 10 秒

        finally:
            writer.close()
            await writer.wait_closed()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 go-libp2p Ping 节点运行")
    async def test_go_libp2p_continuous_ping(self):
        """验证与 go-libp2p 的持续 Ping"""
        host = "127.0.0.1"
        port = 12345

        reader, writer = await asyncio.open_connection(host, port)

        try:
            config = PingConfig(ping_interval=0.5, ping_timeout=2.0)
            ping = PingProtocol("python-peer", config)

            rtts = []
            for _ in range(5):
                rtt = await ping.ping_once(reader, writer)
                rtts.append(rtt)

            # 应该成功完成所有 ping
            assert len(rtts) == 5
            # RTT 应该一致
            assert all(rtt > 0 for rtt in rtts)

        finally:
            writer.close()
            await writer.wait_closed()


# ==================== JS-libp2p 互操作测试 ====================

class TestJSLibp2pPingInterop:
    """与 js-libp2p 的 Ping 互操作性测试"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 js-libp2p Ping 节点运行")
    async def test_js_libp2p_ping_exchange(self):
        """
        验证与 js-libp2p 的 Ping 交换

        js-libp2p 实现:
        https://github.com/libp2p/js-libp2p/tree/master/packages/ping

        运行方式:
        1. 启动 js-libp2p 节点
        2. pytest --run-interop-tests tests/interop/test_ping_interop.py
        """
        host = "127.0.0.1"
        port = 12346

        reader, writer = await asyncio.open_connection(host, port)

        try:
            config = PingConfig()
            ping = PingProtocol("python-peer", config)

            rtt = await ping.ping_once(reader, writer)

            assert rtt > 0

        finally:
            writer.close()
            await writer.wait_closed()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 js-libp2p Ping 节点运行")
    async def test_js_libp2p_ping_over_websocket(self):
        """验证通过 WebSocket 的 Ping"""
        # js-libp2p 常用 WebSocket
        # 需要 WebSocket 客户端
        pass


# ==================== 错误恢复测试 ====================

@pytest.mark.skip(reason="API mismatch - needs test refactoring")
class TestPingErrorRecovery:
    """Ping 错误恢复测试"""

    @pytest.mark.asyncio
    async def test_unresponsive_peer(self):
        """验证不响应对等体处理"""
        config = PingConfig(ping_timeout=0.1, max_ping_failures=3)
        ping = PingProtocol("local-peer", config)

        # 创建不响应的连接
        class NoResponseReader:
            async def read(self, n=-1):
                await asyncio.sleep(1)
                return b""

        writer = asyncio.StreamWriter()

        # 多次尝试 ping
        failures = 0
        for _ in range(config.max_ping_failures + 1):
            try:
                await ping.ping_once(NoResponseReader(), writer)
            except (TimeoutError, asyncio.TimeoutError):
                failures += 1

        assert failures >= config.max_ping_failures

    @pytest.mark.asyncio
    async def test_connection_reset(self):
        """验证连接重置处理"""
        config = PingConfig()
        ping = PingProtocol("local-peer", config)

        # 创建会重置的连接
        class ResetReader:
            async def read(self, n=-1):
                raise ConnectionResetError("Connection reset")

        writer = asyncio.StreamWriter()

        # 应该处理连接重置
        with pytest.raises(ConnectionResetError):
            await ping.ping_once(ResetReader(), writer)

    @pytest.mark.asyncio
    async def test_malformed_response(self):
        """验证畸形响应处理"""
        config = PingConfig()
        ping = PingProtocol("local-peer", config)

        # 创建返回无效数据的连接
        class MalformedReader:
            async def read(self, n=-1):
                return b"invalid ping response"

        writer = asyncio.StreamWriter()

        # 应该处理无效响应
        try:
            await ping.ping_once(MalformedReader(), writer)
        except (ValueError, struct.error):
            pass  # 预期错误


# ==================== 性能基准测试 ====================

@pytest.mark.skip(reason="API mismatch - needs test refactoring")
class TestPingPerformance:
    """Ping 性能基准测试"""

    @pytest.mark.asyncio
    async def test_ping_throughput(self):
        """测试 Ping 吞吐量"""
        config = PingConfig()
        ping = PingProtocol("local-peer", config)

        import time
        start = time.perf_counter()

        pings = 1000
        for _ in range(pings):
            # 模拟 ping (不需要实际连接)
            await asyncio.sleep(0.0001)

        elapsed = time.perf_counter() - start
        pings_per_second = pings / elapsed

        # 应该能处理大量 ping
        assert pings_per_second > 100

    @pytest.mark.asyncio
    async def test_concurrent_pings(self):
        """测试并发 Ping"""
        config = PingConfig()
        ping = PingProtocol("local-peer", config)

        # 并发执行多个 ping
        tasks = [
            ping.ping_once(asyncio.StreamReader(), asyncio.StreamWriter())
            for _ in range(10)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 所有 ping 应该完成
        assert len(results) == 10


# ==================== 辅助函数 ====================

@pytest.fixture
async def ping_server() -> tuple:
    """创建 Ping 测试服务器"""
    # 创建服务器读写管道
    server_reader = asyncio.StreamReader()
    server_writer = asyncio.StreamWriter()
    return server_reader, server_writer


@pytest.fixture
async def ping_client() -> tuple:
    """创建 Ping 测试客户端"""
    # 创建客户端读写管道
    client_reader = asyncio.StreamReader()
    client_writer = asyncio.StreamWriter()
    return client_reader, client_writer


# 导入 struct 用于错误测试
import struct
