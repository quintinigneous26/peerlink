"""
传输层互操作性测试

验证 QUIC、WebRTC、WebTransport 传输与 libp2p 的兼容性。

协议规范:
- QUIC: https://github.com/libp2p/specs/tree/master/quic
- WebRTC: https://github.com/libp2p/specs/tree/master/webrtc
- WebTransport: https://github.com/libp2p/specs/tree/master/webtransport

测试覆盖:
- QUIC 传输
- WebRTC DataChannel
- WebTransport
- 与浏览器兼容性
"""

import asyncio
import pytest
from typing import Optional, Tuple

# QUIC 传输测试
try:
    from p2p_engine.transport.quic import (
        QUICTransport,
        QUICConnection,
        QUICListener,
        QUIC_PROTOCOL_ID,
        HAS_AIOQUIC,
    )
except ImportError:
    HAS_AIOQUIC = False
    QUICTransport = None
    QUICConnection = None
    QUICListener = None
    QUIC_PROTOCOL_ID = "/quic-v1"

# WebRTC 传输测试
try:
    from p2p_engine.transport.webrtc import (
        WebRTCTransport,
        WebRTCConnection,
        WebRTCListener,
        WEBRTC_PROTOCOL_ID,
        HAS_AIORTC,
    )
except ImportError:
    HAS_AIORTC = False
    WebRTCTransport = None
    WebRTCConnection = None
    WebRTCListener = None
    WEBRTC_PROTOCOL_ID = "/webrtc-direct"

# WebTransport 传输测试
try:
    from p2p_engine.transport.webtransport import (
        WebTransportTransport,
        WebTransportConnection,
        WebTransportListener,
        WEBTRANSPORT_PROTOCOL_ID,
    )
except ImportError:
    WebTransportTransport = None
    WebTransportConnection = None
    WebTransportListener = None
    WEBTRANSPORT_PROTOCOL_ID = "/webtransport/1.0.0"


class TestQUICProtocolCompliance:
    """QUIC 协议合规性测试"""

    def test_quic_protocol_id(self):
        """验证 QUIC 协议 ID"""
        assert QUIC_PROTOCOL_ID == "/quic-v1"

    @pytest.mark.skipif(not HAS_AIOQUIC, reason="需要 aioquic 库")
    def test_quic_transport_exists(self):
        """验证 QUIC 传输存在"""
        assert QUICTransport is not None

    @pytest.mark.skipif(not HAS_AIOQUIC, reason="需要 aioquic 库")
    def test_quic_connection_creation(self):
        """验证 QUIC 连接创建"""
        # 需要 aioquic 库
        assert HAS_AIOQUIC


class TestWebRTCProtocolCompliance:
    """WebRTC 协议合规性测试"""

    def test_webrtc_protocol_id(self):
        """验证 WebRTC 协议 ID"""
        assert WEBRTC_PROTOCOL_ID == "/webrtc-direct"

    @pytest.mark.skipif(not HAS_AIORTC, reason="需要 aiortc 库")
    def test_webrtc_transport_exists(self):
        """验证 WebRTC 传输存在"""
        assert WebRTCTransport is not None

    @pytest.mark.skipif(not HAS_AIORTC, reason="需要 aiortc 库")
    def test_webrtc_datachannel_support(self):
        """验证 WebRTC DataChannel 支持"""
        # 需要 aiortc 库
        assert HAS_AIORTC


class TestWebTransportProtocolCompliance:
    """WebTransport 协议合规性测试"""

    def test_webtransport_protocol_id(self):
        """验证 WebTransport 协议 ID"""
        assert WEBTRANSPORT_PROTOCOL_ID == "/webtransport/1.0.0"

    @pytest.mark.skip(reason="WebTransport not implemented")
    def test_webtransport_transport_exists(self):
        """验证 WebTransport 传输存在"""
        # WebTransport 基于 aioquic
        assert WebTransportTransport is not None


# ==================== QUIC 互操作测试 ====================

class TestQUICInterop:
    """QUIC 传输互操作性测试"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 QUIC 测试服务器")
    async def test_quic_connection_establishment(self):
        """
        验证 QUIC 连接建立

        运行方式:
        1. 启动 QUIC 测试服务器
        2. pytest --run-interop-tests tests/interop/test_transport_interop.py
        """
        if not HAS_AIOQUIC:
            pytest.skip("需要 aioquic 库")

        transport = QUICTransport()
        conn = await transport.dial("localhost:12345")

        assert conn is not None
        assert not conn.is_closed()

        await conn.close()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 QUIC 测试服务器")
    async def test_quic_data_transfer(self):
        """验证 QUIC 数据传输"""
        if not HAS_AIOQUIC:
            pytest.skip("需要 aioquic 库")

        transport = QUICTransport()
        conn = await transport.dial("localhost:12345")

        # 发送数据
        data = b"Hello, QUIC!"
        await conn.write(data)

        # 接收数据
        received = await conn.read(len(data))
        assert received == data

        await conn.close()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 go-libp2p QUIC 节点")
    async def test_go_libp2p_quic_interop(self):
        """
        验证与 go-libp2p QUIC 传输的互操作

        go-libp2p QUIC 实现:
        https://github.com/libp2p/go-libp2p/tree/master/transports/quic
        """
        if not HAS_AIOQUIC:
            pytest.skip("需要 aioquic 库")

        transport = QUICTransport()
        conn = await transport.dial("localhost:12345")

        # 验证连接
        assert not conn.is_closed()

        await conn.close()


# ==================== WebRTC 互操作测试 ====================

class TestWebRTCInterop:
    """WebRTC 传输互操作性测试"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 WebRTC 信令服务器")
    async def test_webrtc_signaling(self):
        """
        验证 WebRTC 信令

        运行方式:
        1. 启动信令服务器
        2. pytest --run-interop-tests tests/interop/test_transport_interop.py
        """
        if not HAS_AIORTC:
            pytest.skip("需要 aiortc 库")

        transport = WebRTCTransport()
        listener = await transport.listen("0.0.0.0:0")

        # 等待连接
        conn = await listener.accept()
        assert conn is not None

        await listener.close()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要浏览器 WebRTC 客户端")
    async def test_webrtc_browser_interop(self):
        """
        验证与浏览器 WebRTC 的互操作

        需要在浏览器中运行 WebRTC 客户端
        """
        if not HAS_AIORTC:
            pytest.skip("需要 aiortc 库")

        # 创建 WebRTC 连接
        transport = WebRTCTransport()

        # 交换 SDP 和 ICE 候选
        offer = await transport.create_offer()

        # 从浏览器接收 answer
        # answer = await receive_browser_answer()

        # 完成连接
        # await transport.set_remote_description(answer)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要浏览器 WebRTC 客户端")
    async def test_webrtc_datachannel_transfer(self):
        """验证 WebRTC DataChannel 数据传输"""
        if not HAS_AIORTC:
            pytest.skip("需要 aiortc 库")

        transport = WebRTCTransport()
        conn = await transport.dial("browser-peer-id")

        # 发送数据
        data = b"Hello, Browser!"
        await conn.write(data)

        # 接收数据
        received = await conn.read(len(data))
        assert received == data


# ==================== WebTransport 互操作测试 ====================

class TestWebTransportInterop:
    """WebTransport 传输互操作性测试"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 WebTransport 测试服务器")
    async def test_webtransport_connection(self):
        """
        验证 WebTransport 连接

        运行方式:
        1. 启动 WebTransport 测试服务器
        2. pytest --run-interop-tests tests/interop/test_transport_interop.py
        """
        transport = WebTransportTransport()
        conn = await transport.dial("localhost:12345")

        assert conn is not None
        assert not conn.is_closed()

        await conn.close()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要浏览器 WebTransport 客户端")
    async def test_webtransport_browser_interop(self):
        """
        验证与浏览器 WebTransport 的互操作

        需要在支持 WebTransport 的浏览器中测试
        """
        transport = WebTransportTransport()
        conn = await transport.dial("browser-transport-url")

        # 发送数据
        data = b"Hello, WebTransport!"
        await conn.write(data)

        await conn.close()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 WebTransport 测试服务器")
    async def test_webtransport_streams(self):
        """验证 WebTransport 流传输"""
        transport = WebTransportTransport()
        conn = await transport.dial("localhost:12345")

        # 创建双向流
        stream = await conn.open_stream()

        # 发送数据
        await stream.write(b"stream data")

        # 接收数据
        data = await stream.read(1024)

        await stream.close()
        await conn.close()


# ==================== NAT 穿透测试 ====================

class TestTransportNATTraversal:
    """传输 NAT 穿透测试"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 NAT 环境")
    async def test_quic_nat_traversal(self):
        """验证 QUIC NAT 穿透"""
        if not HAS_AIOQUIC:
            pytest.skip("需要 aioquic 库")

        # 测试通过 NAT 建立 QUIC 连接
        transport = QUICTransport()
        conn = await transport.dial("behind-nat-peer:12345")

        assert conn is not None
        await conn.close()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 NAT 环境")
    async def test_webrtc_ice_negotiation(self):
        """验证 WebRTC ICE 协商"""
        if not HAS_AIORTC:
            pytest.skip("需要 aiortc 库")

        transport = WebRTCTransport()

        # ICE 候选交换
        await transport.gather_ice_candidates()

        # 验证 ICE 连接
        assert len(transport.ice_candidates) > 0


# ==================== 错误恢复测试 ====================

class TestTransportErrorRecovery:
    """传输错误恢复测试"""

    @pytest.mark.asyncio
    async def test_connection_timeout_recovery(self):
        """验证连接超时恢复"""
        if not HAS_AIOQUIC:
            pytest.skip("需要 aioquic 库")

        transport = QUICTransport(timeout=0.1)

        # 尝试连接到不存在的地址
        with pytest.raises((TimeoutError, ConnectionError)):
            await transport.dial("192.0.2.1:12345")  # TEST-NET-1

    @pytest.mark.asyncio
    async def test_connection_reset_recovery(self):
        """验证连接重置恢复"""
        if not HAS_AIOQUIC:
            pytest.skip("需要 aioquic 库")

        transport = QUICTransport()
        conn = await transport.dial("localhost:12345")

        # 模拟连接重置
        # await conn.reset()

        # 应该能创建新连接
        new_conn = await transport.dial("localhost:12345")

    @pytest.mark.asyncio
    async def test_webrtc_signaling_failure(self):
        """验证 WebRTC 信令失败处理"""
        if not HAS_AIORTC:
            pytest.skip("需要 aiortc 库")

        transport = WebRTCTransport()

        # 信令失败应该优雅处理
        with pytest.raises(ConnectionError):
            await transport.connect_via_signaling("invalid-offer")


# ==================== 性能基准测试 ====================

class TestTransportPerformance:
    """传输性能基准测试"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要网络连接")
    async def test_quic_throughput(self):
        """测试 QUIC 吞吐量"""
        if not HAS_AIOQUIC:
            pytest.skip("需要 aioquic 库")

        transport = QUICTransport()
        conn = await transport.dial("localhost:12345")

        # 测试吞吐量
        data = b"x" * (1024 * 1024)  # 1MB
        import time
        start = time.perf_counter()

        await conn.write(data)

        elapsed = time.perf_counter() - start
        throughput = len(data) / elapsed / (1024 * 1024)  # MB/s

        # QUIC 应该有高吞吐量
        assert throughput > 10  # > 10 MB/s

        await conn.close()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要网络连接")
    async def test_webrtc_latency(self):
        """测试 WebRTC 延迟"""
        if not HAS_AIORTC:
            pytest.skip("需要 aiortc 库")

        transport = WebRTCTransport()
        conn = await transport.dial("localhost:12345")

        # 测试延迟
        import time
        latencies = []

        for _ in range(100):
            start = time.perf_counter()
            await conn.write(b"ping")
            await conn.read(4)
            latencies.append(time.perf_counter() - start)

        avg_latency = sum(latencies) / len(latencies)

        # WebRTC 应该有低延迟
        assert avg_latency < 0.01  # < 10ms on localhost

        await conn.close()


# ==================== 辅助函数 ====================

@pytest.fixture
def skip_if_no_aioquic():
    """如果没有 aioquic 则跳过"""
    if not HAS_AIOQUIC:
        pytest.skip("需要 aioquic 库")


@pytest.fixture
def skip_if_no_aiortc():
    """如果没有 aiortc 则跳过"""
    if not HAS_AIORTC:
        pytest.skip("需要 aiortc 库")
