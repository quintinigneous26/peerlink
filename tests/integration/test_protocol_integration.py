"""
协议集成测试

测试新协议（TLS、mplex、DHT）与传输层的集成。
"""
import asyncio
import logging
from typing import Optional, List
from unittest.mock import AsyncMock, MagicMock, Mock
from unittest.mock import patch

import pytest
import pytest_asyncio

from p2p_engine.transport import (
    Transport,
    Connection,
    TransportManager,
    TransportUpgrader,
    SecurityTransport,
    StreamMuxer,
    SecureConnection,
    UpgradedConnection,
)

logger = logging.getLogger(__name__)


# ==================== Mock 实现 ====================

class MockConnection(Connection):
    """模拟原始连接"""

    def __init__(self, reader_data: bytes = b"", remote_addr: Optional[tuple] = None):
        self._reader_data = reader_data
        self._write_buffer: list[bytes] = []
        self._closed = False
        self._remote_addr = remote_addr or ("127.0.0.1", 12345)
        self._local_addr = ("127.0.0.1", 54321)
        self._read_pos = 0

    async def read(self, n: int = -1) -> bytes:
        if self._closed:
            raise ConnectionError("Connection closed")
        if n == -1:
            data = self._reader_data[self._read_pos:]
            self._read_pos = len(self._reader_data)
            return data
        data = self._reader_data[self._read_pos:self._read_pos + n]
        self._read_pos += len(data)
        return data

    async def write(self, data: bytes) -> int:
        if self._closed:
            raise ConnectionError("Connection closed")
        self._write_buffer.append(data)
        return len(data)

    async def close(self) -> None:
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    @property
    def remote_address(self):
        return self._remote_addr

    @property
    def local_address(self):
        return self._local_addr


class MockTLSConnection(Connection):
    """模拟 TLS 连接"""

    def __init__(self, inner: Connection, peer_id: str):
        self._inner = inner
        self._peer_id = peer_id
        self._closed = False

    async def read(self, n: int = -1) -> bytes:
        return await self._inner.read(n)

    async def write(self, data: bytes) -> int:
        return await self._inner.write(data)

    async def close(self) -> None:
        self._closed = True
        await self._inner.close()

    def is_closed(self) -> bool:
        return self._closed or self._inner.is_closed()

    @property
    def remote_address(self):
        return self._inner.remote_address

    @property
    def local_address(self):
        return self._inner.local_address

    @property
    def peer_id(self) -> str:
        return self._peer_id

    @property
    def protocol_id(self) -> str:
        return "/tls/1.0.0"


class MockTLSSecurity(SecurityTransport):
    """模拟 TLS 安全传输"""

    def __init__(self, protocol_id: str = "/tls/1.0.0"):
        self._protocol_id = protocol_id
        self._handshake_count = 0

    async def secure_inbound(
        self,
        conn: Connection,
        peer_id: Optional[str] = None
    ) -> SecureConnection:
        await asyncio.sleep(0.001)  # 模拟握手延迟
        self._handshake_count += 1

        from p2p_engine.transport.upgrader import SecureConnection
        return SecureConnection(
            conn,
            peer_id or "unknown-peer",
            self._protocol_id
        )

    async def secure_outbound(
        self,
        conn: Connection,
        peer_id: str
    ) -> SecureConnection:
        await asyncio.sleep(0.001)  # 模拟握手延迟
        self._handshake_count += 1

        from p2p_engine.transport.upgrader import SecureConnection
        return SecureConnection(conn, peer_id, self._protocol_id)

    def get_protocol_id(self) -> str:
        return self._protocol_id

    @property
    def handshake_count(self) -> int:
        return self._handshake_count


class MockMuxedStream(Connection):
    """模拟 mplex 流"""

    def __init__(self, stream_id: int):
        self._stream_id = stream_id
        self._closed = False
        self._read_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._write_buffer: list[bytes] = []

    @property
    def stream_id(self) -> int:
        return self._stream_id

    async def read(self, n: int = -1) -> bytes:
        if self._closed:
            raise ConnectionError("Stream closed")
        data = await self._read_queue.get()
        if data is None:
            return b""
        return data[:n] if n > 0 else data

    async def write(self, data: bytes) -> int:
        if self._closed:
            raise ConnectionError("Stream closed")
        self._write_buffer.append(data)
        return len(data)

    async def close(self) -> None:
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    @property
    def remote_address(self):
        return None

    @property
    def local_address(self):
        return None


class MockMplexSession:
    """模拟 mplex 会话"""

    def __init__(self, conn: Connection, protocol_id: str, is_initiator: bool):
        self._conn = conn
        self._protocol_id = protocol_id
        self._is_initiator = is_initiator
        self._closed = False
        self._streams: dict[int, MockMuxedStream] = {}
        self._next_stream_id = 1 if is_initiator else 2
        self._lock = asyncio.Lock()

    @property
    def protocol_id(self) -> str:
        return self._protocol_id

    @property
    def is_initiator(self) -> bool:
        return self._is_initiator

    @property
    def connection(self) -> Connection:
        return self._conn

    def is_closed(self) -> bool:
        return self._closed

    async def open_stream(self) -> MockMuxedStream:
        async with self._lock:
            if self._closed:
                raise ConnectionError("Session closed")

            stream_id = self._next_stream_id
            self._next_stream_id += 2

            stream = MockMuxedStream(stream_id)
            self._streams[stream_id] = stream
            return stream

    async def accept_stream(self) -> MockMuxedStream:
        # 模拟接受流
        await asyncio.sleep(0.001)
        raise NotImplementedError("Use open_stream in tests")

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            for stream in self._streams.values():
                await stream.close()
            self._streams.clear()


class MockMplexMuxer(StreamMuxer):
    """模拟 mplex 流复用器"""

    def __init__(self, protocol_id: str = "/mplex/6.7.0"):
        self._protocol_id = protocol_id
        self._session_count = 0

    async def create_session(
        self,
        conn: Connection,
        is_initiator: bool
    ) -> MockMplexSession:
        await asyncio.sleep(0.001)
        self._session_count += 1
        return MockMplexSession(conn, self._protocol_id, is_initiator)

    def get_protocol_id(self) -> str:
        return self._protocol_id

    @property
    def session_count(self) -> int:
        return self._session_count


# ==================== TLS 集成测试 ====================

@pytest.mark.integration
class TestTLSIntegration:
    """TLS 协议集成测试"""

    @pytest.fixture
    def tls_security(self):
        return MockTLSSecurity("/tls/1.0.0")

    @pytest.fixture
    def upgrader(self, tls_security):
        mock_muxer = MockMplexMuxer("/mplex/6.7.0")
        return TransportUpgrader(
            security_transports=[tls_security],
            muxers=[mock_muxer]
        )

    @pytest.mark.asyncio
    async def test_tls_outbound_handshake(self, upgrader, tls_security):
        """测试 TLS 出站握手"""
        raw_conn = MockConnection(b"test data")
        peer_id = "peer-tls-1"

        upgraded = await upgrader.upgrade_outbound(raw_conn, peer_id)

        assert isinstance(upgraded, UpgradedConnection)
        assert upgraded.peer_id == peer_id
        assert upgraded.security_protocol == "/tls/1.0.0"
        assert tls_security.handshake_count == 1

    @pytest.mark.asyncio
    async def test_tls_inbound_handshake(self, upgrader, tls_security):
        """测试 TLS 入站握手"""
        raw_conn = MockConnection(b"incoming data")

        upgraded = await upgrader.upgrade_inbound(raw_conn, "peer-tls-2")

        assert isinstance(upgraded, UpgradedConnection)
        assert upgraded.security_protocol == "/tls/1.0.0"
        assert tls_security.handshake_count == 1

    @pytest.mark.asyncio
    async def test_tls_priority_over_noise(self):
        """测试 TLS 优先级高于 Noise"""
        noise_security = MockTLSSecurity("/noise/xx/1.0.0")
        tls_security = MockTLSSecurity("/tls/1.0.0")

        # TLS 优先
        upgrader = TransportUpgrader(
            security_transports=[tls_security, noise_security],
            muxers=[MockMplexMuxer()]
        )

        raw_conn = MockConnection()
        upgraded = await upgrader.upgrade_outbound(raw_conn, "peer-priority")

        assert upgraded.security_protocol == "/tls/1.0.0"


# ==================== mplex 集成测试 ====================

@pytest.mark.integration
class TestMplexIntegration:
    """mplex 流复用集成测试"""

    @pytest.fixture
    def mplex_muxer(self):
        return MockMplexMuxer("/mplex/6.7.0")

    @pytest.fixture
    def upgrader(self, mplex_muxer):
        tls_security = MockTLSSecurity("/tls/1.0.0")
        return TransportUpgrader(
            security_transports=[tls_security],
            muxers=[mplex_muxer]
        )

    @pytest.mark.asyncio
    async def test_mplex_stream_multiplexing(self, upgrader, mplex_muxer):
        """测试 mplex 流复用"""
        raw_conn = MockConnection()

        upgraded = await upgrader.upgrade_outbound(raw_conn, "peer-mplex")

        # 打开多个流
        stream1 = await upgraded.open_stream()
        stream2 = await upgraded.open_stream()
        stream3 = await upgraded.open_stream()

        assert stream1.stream_id == 1
        assert stream2.stream_id == 3
        assert stream3.stream_id == 5
        assert mplex_muxer.session_count == 1

    @pytest.mark.asyncio
    async def test_mplex_stream_isolation(self, upgrader):
        """测试 mplex 流隔离"""
        raw_conn = MockConnection()
        upgraded = await upgrader.upgrade_outbound(raw_conn, "peer-isolation")

        stream1 = await upgraded.open_stream()
        stream2 = await upgraded.open_stream()

        # 写入不同数据
        await stream1.write(b"stream1 data")
        await stream2.write(b"stream2 data")

        # 流之间应该隔离
        assert stream1._write_buffer[-1] == b"stream1 data"
        assert stream2._write_buffer[-1] == b"stream2 data"

    @pytest.mark.asyncio
    async def test_mplex_priority_over_yamux(self):
        """测试 mplex 优先级高于 yamux"""
        mplex = MockMplexMuxer("/mplex/6.7.0")
        yamux = MockMplexMuxer("/yamux/1.0.0")

        upgrader = TransportUpgrader(
            security_transports=[MockTLSSecurity()],
            muxers=[mplex, yamux]
        )

        raw_conn = MockConnection()
        upgraded = await upgrader.upgrade_outbound(raw_conn, "peer-mux-priority")

        # 应该使用 mplex
        assert upgraded.muxer_protocol == "/mplex/6.7.0"


# ==================== TLS + mplex 组合测试 ====================

@pytest.mark.integration
class TestTLSMplexCombined:
    """TLS + mplex 组合测试"""

    @pytest.fixture
    def full_upgrader(self):
        tls = MockTLSSecurity("/tls/1.0.0")
        mplex = MockMplexMuxer("/mplex/6.7.0")
        return TransportUpgrader(
            security_transports=[tls],
            muxers=[mplex]
        )

    @pytest.mark.asyncio
    async def test_full_upgrade_chain(self, full_upgrader):
        """测试完整的升级链: Raw → TLS → mplex"""
        raw_conn = MockConnection(b"raw data")

        upgraded = await full_upgrader.upgrade_outbound(raw_conn, "peer-full")

        # 验证完整升级链
        assert upgraded.security_protocol == "/tls/1.0.0"
        assert upgraded.muxer_protocol == "/mplex/6.7.0"

        # 可以打开流
        stream = await upgraded.open_stream()
        assert stream.stream_id == 1

    @pytest.mark.asyncio
    async def test_concurrent_streams(self, full_upgrader):
        """测试并发流操作"""
        raw_conn = MockConnection()
        upgraded = await full_upgrader.upgrade_outbound(raw_conn, "peer-concurrent")

        # 并发打开多个流
        streams = await asyncio.gather(*[
            upgraded.open_stream() for _ in range(10)
        ])

        assert len(streams) == 10
        stream_ids = [s.stream_id for s in streams]
        assert stream_ids == [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]


# ==================== 传输管理器集成测试 ====================

@pytest.mark.integration
class TestTransportManagerWithNewProtocols:
    """传输管理器与新协议集成测试"""

    @pytest.fixture
    def manager(self):
        tls = MockTLSSecurity("/tls/1.0.0")
        mplex = MockMplexMuxer("/mplex/6.7.0")
        upgrader = TransportUpgrader(
            security_transports=[tls],
            muxers=[mplex]
        )
        return TransportManager("local-peer-integration", upgrader)

    @pytest.mark.asyncio
    async def test_manager_with_tls_mplex(self, manager):
        """测试管理器使用 TLS 和 mplex"""
        # 添加模拟传输
        mock_transport = MockTCPTransport()
        manager.add_transport(mock_transport, priority=0)

        # 拨号应该自动使用 TLS + mplex 升级
        conn = await manager.dial("test-addr", "remote-peer")

        assert conn.peer_id == "remote-peer"
        assert conn.security_protocol == "/tls/1.0.0"
        assert conn.muxer_protocol == "/mplex/6.7.0"

    @pytest.mark.asyncio
    async def test_stream_operations(self, manager):
        """测试流操作"""
        mock_transport = MockTCPTransport()
        manager.add_transport(mock_transport, priority=0)

        conn = await manager.dial("stream-test", "stream-peer")

        # 测试流操作
        stream = await conn.open_stream()
        await stream.write(b"test message")

        assert not stream.is_closed()
        await stream.close()
        assert stream.is_closed()


# ==================== 辅助类 ====================

class MockTCPTransport(Transport):
    """模拟 TCP 传输"""

    def __init__(self):
        self._closed = False

    async def dial(self, addr: str) -> Connection:
        await asyncio.sleep(0.001)
        return MockConnection(remote_addr=(addr, 80))

    async def listen(self, addr: str):
        from p2p_engine.transport.base import Listener
        listener = MagicMock(spec=Listener)
        listener.is_closed.return_value = False
        listener.accept = AsyncMock(return_value=MockConnection())
        listener.close = AsyncMock()
        listener.addresses = [(addr,)]
        return listener

    def protocols(self) -> List[str]:
        return ["/tcp/1.0.0"]

    async def close(self) -> None:
        self._closed = True


# ==================== 性能测试 ====================

@pytest.mark.integration
class TestProtocolPerformance:
    """协议性能测试"""

    @pytest.mark.asyncio
    async def test_tls_handshake_latency(self):
        """测试 TLS 握手延迟"""
        tls = MockTLSSecurity()

        start = asyncio.get_event_loop().time()
        conn = MockConnection()
        await tls.secure_outbound(conn, "peer")
        elapsed = asyncio.get_event_loop().time() - start

        # 握手应该很快（模拟延迟很小）
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_mlex_stream_open_latency(self):
        """测试 mplex 流打开延迟"""
        mplex = MockMplexMuxer()
        conn = MockConnection()

        start = asyncio.get_event_loop().time()
        session = await mplex.create_session(conn, is_initiator=True)
        stream = await session.open_stream()
        elapsed = asyncio.get_event_loop().time() - start

        # 流打开应该很快
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_concurrent_stream_performance(self):
        """测试并发流性能"""
        mplex = MockMplexMuxer()
        conn = MockConnection()
        session = await mplex.create_session(conn, is_initiator=True)

        start = asyncio.get_event_loop().time()
        streams = await asyncio.gather(*[
            session.open_stream() for _ in range(100)
        ])
        elapsed = asyncio.get_event_loop().time() - start

        assert len(streams) == 100
        # 100 个流应该在合理时间内完成
        assert elapsed < 1.0
