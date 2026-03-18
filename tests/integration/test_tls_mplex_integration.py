"""
TLS 1.3 和 mplex 集成测试

测试 TLS 1.3 安全传输和 mplex 流复用器与传输层的完整集成。
"""
import asyncio
import logging
from typing import Optional, List
from unittest.mock import AsyncMock, MagicMock, patch

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

class MockRawConnection(Connection):
    """模拟原始 TCP 连接"""

    def __init__(self, data: bytes = b""):
        self._data = data
        self._write_buffer: list[bytes] = []
        self._closed = False
        self._remote_addr = ("127.0.0.1", 12345)
        self._local_addr = ("127.0.0.1", 54321)
        self._read_pos = 0

    async def read(self, n: int = -1) -> bytes:
        if self._closed:
            raise ConnectionError("Connection closed")
        if n == -1:
            result = self._data[self._read_pos:]
            self._read_pos = len(self._data)
            return result
        result = self._data[self._read_pos:self._read_pos + n]
        self._read_pos += len(result)
        return result

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


class MockTLSSecurity(SecurityTransport):
    """模拟 TLS 1.3 安全传输"""

    PROTOCOL_ID = "/tls/1.0.0"

    def __init__(self):
        self._handshake_count = 0
        self._connections: list = []

    async def secure_inbound(
        self,
        conn: Connection,
        peer_id: Optional[str] = None
    ) -> SecureConnection:
        await asyncio.sleep(0.005)  # 模拟 TLS 握手
        self._handshake_count += 1
        self._connections.append(conn)

        return SecureConnection(
            conn,
            peer_id or f"peer-{self._handshake_count}",
            self.PROTOCOL_ID
        )

    async def secure_outbound(
        self,
        conn: Connection,
        peer_id: str
    ) -> SecureConnection:
        await asyncio.sleep(0.005)  # 模拟 TLS 握手
        self._handshake_count += 1
        self._connections.append(conn)

        return SecureConnection(conn, peer_id, self.PROTOCOL_ID)

    def get_protocol_id(self) -> str:
        return self.PROTOCOL_ID


class MockMplexStream(Connection):
    """模拟 mplex 流"""

    def __init__(self, stream_id: int, session: 'MockMplexSession'):
        self._stream_id = stream_id
        self._session = session
        self._closed = False
        self._read_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._write_buffer: list[bytes] = []

    @property
    def stream_id(self) -> int:
        return self._stream_id

    @property
    def session(self) -> 'MockMplexSession':
        return self._session

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
        self._session._remove_stream(self._stream_id)

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

    PROTOCOL_ID = "/mplex/6.7.0"

    def __init__(self, conn: Connection, is_initiator: bool):
        self._conn = conn
        self._is_initiator = is_initiator
        self._closed = False
        self._streams: dict[int, MockMplexStream] = {}
        self._next_stream_id = 1 if is_initiator else 2
        self._lock = asyncio.Lock()

    @property
    def protocol_id(self) -> str:
        return self.PROTOCOL_ID

    @property
    def is_initiator(self) -> bool:
        return self._is_initiator

    @property
    def connection(self) -> Connection:
        return self._conn

    def is_closed(self) -> bool:
        return self._closed

    async def open_stream(self) -> MockMplexStream:
        async with self._lock:
            if self._closed:
                raise ConnectionError("Session closed")
            stream_id = self._next_stream_id
            self._next_stream_id += 2
            stream = MockMplexStream(stream_id, self)
            self._streams[stream_id] = stream
            return stream

    def _remove_stream(self, stream_id: int) -> None:
        self._streams.pop(stream_id, None)

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            for stream in list(self._streams.values()):
                await stream.close()
            self._streams.clear()


class MockMplexMuxer(StreamMuxer):
    """模拟 mplex 流复用器"""

    def __init__(self):
        self._sessions: list = []

    async def create_session(
        self,
        conn: Connection,
        is_initiator: bool
    ) -> MockMplexSession:
        await asyncio.sleep(0.002)
        session = MockMplexSession(conn, is_initiator)
        self._sessions.append(session)
        return session

    def get_protocol_id(self) -> str:
        return MockMplexSession.PROTOCOL_ID


class MockTCPTransport(Transport):
    """模拟 TCP 传输"""

    def __init__(self):
        self._closed = False
        self._connections: list = []

    async def dial(self, addr: str) -> Connection:
        await asyncio.sleep(0.001)
        conn = MockRawConnection()
        self._connections.append(conn)
        return conn

    async def listen(self, addr: str):
        from p2p_engine.transport.base import Listener
        listener = MagicMock(spec=Listener)
        listener.is_closed.return_value = False
        listener.accept = AsyncMock(return_value=MockRawConnection())
        listener.close = AsyncMock()
        listener.addresses = [(addr,)]
        return listener

    def protocols(self) -> List[str]:
        return ["/tcp/1.0.0"]

    async def close(self) -> None:
        self._closed = True


# ==================== TLS 1.3 集成测试 ====================

@pytest.mark.integration
class TestTLS13Integration:
    """TLS 1.3 协议集成测试"""

    @pytest.fixture
    def tls_security(self):
        return MockTLSSecurity()

    @pytest.fixture
    def upgrader(self, tls_security):
        muxer = MockMplexMuxer()
        return TransportUpgrader(
            security_transports=[tls_security],
            muxers=[muxer]
        )

    @pytest.mark.asyncio
    async def test_tls_outbound_connection(self, upgrader, tls_security):
        """测试 TLS 出站连接"""
        raw_conn = MockRawConnection(b"server hello")
        peer_id = "QmPeer123"

        secure_conn = await tls_security.secure_outbound(raw_conn, peer_id)

        assert isinstance(secure_conn, SecureConnection)
        assert secure_conn.peer_id == peer_id
        assert secure_conn.protocol_id == "/tls/1.0.0"
        assert tls_security._handshake_count == 1

    @pytest.mark.asyncio
    async def test_tls_inbound_connection(self, upgrader, tls_security):
        """测试 TLS 入站连接"""
        raw_conn = MockRawConnection(b"client hello")

        secure_conn = await tls_security.secure_inbound(raw_conn)

        assert isinstance(secure_conn, SecureConnection)
        assert secure_conn.protocol_id == "/tls/1.0.0"

    @pytest.mark.asyncio
    async def test_tls_data_transfer(self, tls_security):
        """测试 TLS 加密数据传输"""
        raw_conn = MockRawConnection()
        secure_conn = await tls_security.secure_outbound(raw_conn, "peer-data")

        # 写入数据
        data = b"encrypted message"
        await secure_conn.write(data)

        # 验证数据写入到原始连接
        assert len(raw_conn._write_buffer) > 0
        assert raw_conn._write_buffer[-1] == data

    @pytest.mark.asyncio
    async def test_tls_connection_close(self, tls_security):
        """测试 TLS 连接关闭"""
        raw_conn = MockRawConnection()
        secure_conn = await tls_security.secure_outbound(raw_conn, "peer-close")

        assert not secure_conn.is_closed()
        await secure_conn.close()
        assert secure_conn.is_closed()


# ==================== mplex 集成测试 ====================

@pytest.mark.integration
class TestMplexIntegration:
    """mplex 流复用集成测试"""

    @pytest.fixture
    def mplex_muxer(self):
        return MockMplexMuxer()

    @pytest.fixture
    def upgrader(self, mplex_muxer):
        tls = MockTLSSecurity()
        return TransportUpgrader(
            security_transports=[tls],
            muxers=[mplex_muxer]
        )

    @pytest.mark.asyncio
    async def test_mlex_session_creation(self, mplex_muxer):
        """测试 mplex 会话创建"""
        conn = MockRawConnection()
        session = await mplex_muxer.create_session(conn, is_initiator=True)

        assert session.protocol_id == "/mplex/6.7.0"
        assert session.is_initiator is True
        assert not session.is_closed()

    @pytest.mark.asyncio
    async def test_mlex_stream_opening(self, mplex_muxer):
        """测试 mplex 流打开"""
        conn = MockRawConnection()
        session = await mplex_muxer.create_session(conn, is_initiator=True)

        stream1 = await session.open_stream()
        stream2 = await session.open_stream()
        stream3 = await session.open_stream()

        # 验证流 ID (奇数序列)
        assert stream1.stream_id == 1
        assert stream2.stream_id == 3
        assert stream3.stream_id == 5

    @pytest.mark.asyncio
    async def test_mlex_stream_data_transfer(self, mplex_muxer):
        """测试 mplex 流数据传输"""
        conn = MockRawConnection()
        session = await mplex_muxer.create_session(conn, is_initiator=True)
        stream = await session.open_stream()

        # 写入数据
        data = b"stream data"
        written = await stream.write(data)

        assert written == len(data)
        assert stream._write_buffer[-1] == data

    @pytest.mark.asyncio
    async def test_mlex_stream_isolation(self, mplex_muxer):
        """测试 mplex 流隔离"""
        conn = MockRawConnection()
        session = await mplex_muxer.create_session(conn, is_initiator=True)

        stream1 = await session.open_stream()
        stream2 = await session.open_stream()

        # 不同流的数据应该隔离
        await stream1.write(b"stream 1 data")
        await stream2.write(b"stream 2 data")

        assert stream1._write_buffer[-1] == b"stream 1 data"
        assert stream2._write_buffer[-1] == b"stream 2 data"

    @pytest.mark.asyncio
    async def test_mlex_stream_close(self, mplex_muxer):
        """测试 mplex 流关闭"""
        conn = MockRawConnection()
        session = await mplex_muxer.create_session(conn, is_initiator=True)
        stream = await session.open_stream()

        assert not stream.is_closed()
        await stream.close()
        assert stream.is_closed()


# ==================== TLS + mplex 组合测试 ====================

@pytest.mark.integration
class TestTLSMplexCombined:
    """TLS + mplex 完整集成测试"""

    @pytest.fixture
    def full_upgrader(self):
        tls = MockTLSSecurity()
        mplex = MockMplexMuxer()
        return TransportUpgrader(
            security_transports=[tls],
            muxers=[mplex]
        )

    @pytest.mark.asyncio
    async def test_full_upgrade_chain(self, full_upgrader):
        """测试完整升级链: Raw → TLS → mplex"""
        raw_conn = MockRawConnection(b"initial data")

        upgraded = await full_upgrader.upgrade_outbound(raw_conn, "peer-full")

        # 验证完整升级
        assert isinstance(upgraded, UpgradedConnection)
        assert upgraded.security_protocol == "/tls/1.0.0"
        assert upgraded.muxer_protocol == "/mplex/6.7.0"
        assert upgraded.peer_id == "peer-full"

    @pytest.mark.asyncio
    async def test_stream_over_secure_connection(self, full_upgrader):
        """测试在安全连接上打开流"""
        raw_conn = MockRawConnection()
        upgraded = await full_upgrader.upgrade_outbound(raw_conn, "peer-stream")

        # 打开多个流
        stream1 = await upgraded.open_stream()
        stream2 = await upgraded.open_stream()

        assert stream1.stream_id == 1
        assert stream2.stream_id == 3
        assert not stream1.is_closed()
        assert not stream2.is_closed()

    @pytest.mark.asyncio
    async def test_concurrent_streams(self, full_upgrader):
        """测试并发流操作"""
        raw_conn = MockRawConnection()
        upgraded = await full_upgrader.upgrade_outbound(raw_conn, "peer-concurrent")

        # 并发打开 10 个流
        streams = await asyncio.gather(*[
            upgraded.open_stream() for _ in range(10)
        ])

        assert len(streams) == 10
        stream_ids = [s.stream_id for s in streams]
        assert stream_ids == [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]

    @pytest.mark.asyncio
    async def test_upgrade_inbound(self, full_upgrader):
        """测试入站连接升级"""
        raw_conn = MockRawConnection(b"incoming data")

        upgraded = await full_upgrader.upgrade_inbound(raw_conn, "incoming-peer")

        assert isinstance(upgraded, UpgradedConnection)
        assert upgraded.peer_id == "incoming-peer"
        assert upgraded.security_protocol == "/tls/1.0.0"
        assert upgraded.muxer_protocol == "/mplex/6.7.0"


# ==================== 传输管理器集成测试 ====================

@pytest.mark.integration
class TestTransportManagerTLSMplex:
    """传输管理器与 TLS/mplex 集成测试"""

    @pytest.fixture
    def manager(self):
        tls = MockTLSSecurity()
        mplex = MockMplexMuxer()
        upgrader = TransportUpgrader(
            security_transports=[tls],
            muxers=[mplex]
        )
        return TransportManager("local-peer-tls-mplex", upgrader)

    @pytest.mark.asyncio
    async def test_manager_dial_with_tls_mplex(self, manager):
        """测试管理器使用 TLS 和 mplex 拨号"""
        tcp = MockTCPTransport()
        manager.add_transport(tcp, priority=0)

        conn = await manager.dial("127.0.0.1:8000", "remote-peer")

        assert conn.peer_id == "remote-peer"
        assert conn.security_protocol == "/tls/1.0.0"
        assert conn.muxer_protocol == "/mplex/6.7.0"

    @pytest.mark.asyncio
    async def test_manager_listen_and_accept(self, manager):
        """测试管理器监听和接受"""
        tcp = MockTCPTransport()
        manager.add_transport(tcp, priority=0)

        listener = await manager.listen("0.0.0.0:9000")
        assert not listener.is_closed()

        await manager.close()

    @pytest.mark.asyncio
    async def test_multiple_connections(self, manager):
        """测试多连接管理"""
        tcp = MockTCPTransport()
        manager.add_transport(tcp, priority=0)

        # 建立多个连接
        conn1 = await manager.dial("peer1:8000", "peer1")
        conn2 = await manager.dial("peer2:8000", "peer2")
        conn3 = await manager.dial("peer3:8000", "peer3")

        assert conn1.peer_id == "peer1"
        assert conn2.peer_id == "peer2"
        assert conn3.peer_id == "peer3"

        # 每个连接都可以打开流
        stream1 = await conn1.open_stream()
        stream2 = await conn2.open_stream()
        stream3 = await conn3.open_stream()

        assert stream1.stream_id == 1
        assert stream2.stream_id == 1
        assert stream3.stream_id == 1


# ==================== 性能和压力测试 ====================

@pytest.mark.integration
class TestTLSMplexPerformance:
    """TLS 和 mplex 性能测试"""

    @pytest.mark.asyncio
    async def test_tls_handshake_performance(self):
        """测试 TLS 握手性能"""
        tls = MockTLSSecurity()
        raw_conn = MockRawConnection()

        start = asyncio.get_event_loop().time()
        await tls.secure_outbound(raw_conn, "peer-perf")
        elapsed = asyncio.get_event_loop().time() - start

        # TLS 握手应该快速完成（模拟延迟 < 10ms）
        assert elapsed < 0.01

    @pytest.mark.asyncio
    async def test_mlex_stream_open_performance(self):
        """测试 mplex 流打开性能"""
        mplex = MockMplexMuxer()
        conn = MockRawConnection()
        session = await mplex.create_session(conn, is_initiator=True)

        start = asyncio.get_event_loop().time()
        stream = await session.open_stream()
        elapsed = asyncio.get_event_loop().time() - start

        # 流打开应该快速（模拟延迟 < 5ms）
        assert elapsed < 0.005

    @pytest.mark.asyncio
    async def test_concurrent_stream_performance(self):
        """测试并发流性能"""
        mplex = MockMplexMuxer()
        conn = MockRawConnection()
        session = await mplex.create_session(conn, is_initiator=True)

        start = asyncio.get_event_loop().time()
        streams = await asyncio.gather(*[
            session.open_stream() for _ in range(100)
        ])
        elapsed = asyncio.get_event_loop().time() - start

        assert len(streams) == 100
        # 100 个流应该在合理时间内完成
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_full_upgrade_chain_performance(self):
        """测试完整升级链性能"""
        tls = MockTLSSecurity()
        mplex = MockMplexMuxer()
        upgrader = TransportUpgrader(
            security_transports=[tls],
            muxers=[mplex]
        )

        raw_conn = MockRawConnection()

        start = asyncio.get_event_loop().time()
        upgraded = await upgrader.upgrade_outbound(raw_conn, "peer-perf")
        stream = await upgraded.open_stream()
        elapsed = asyncio.get_event_loop().time() - start

        # 完整升级链 + 流打开应该快速
        assert elapsed < 0.02


# ==================== 错误处理测试 ====================

@pytest.mark.integration
class TestTLSMplexErrorHandling:
    """TLS 和 mplex 错误处理测试"""

    @pytest.mark.asyncio
    async def test_tls_connection_failure(self):
        """测试 TLS 连接失败处理"""
        class FailingTLS(SecurityTransport):
            async def secure_inbound(self, conn, peer_id=None):
                raise ConnectionError("TLS handshake failed")

            async def secure_outbound(self, conn, peer_id):
                raise ConnectionError("TLS handshake failed")

            def get_protocol_id(self):
                return "/failing/1.0.0"

        failing_tls = FailingTLS()
        working_tls = MockTLSSecurity()

        upgrader = TransportUpgrader(
            security_transports=[failing_tls, working_tls],
            muxers=[MockMplexMuxer()]
        )

        raw_conn = MockRawConnection()
        # 应该降级到工作的 TLS
        upgraded = await upgrader.upgrade_outbound(raw_conn, "peer-fallback")

        assert upgraded.security_protocol == "/tls/1.0.0"

    @pytest.mark.asyncio
    async def test_mlex_session_close(self):
        """测试 mplex 会话关闭"""
        mplex = MockMplexMuxer()
        conn = MockRawConnection()
        session = await mplex.create_session(conn, is_initiator=True)

        # 打开一些流
        stream1 = await session.open_stream()
        stream2 = await session.open_stream()

        assert not session.is_closed()

        # 关闭会话
        await session.close()

        assert session.is_closed()
        assert stream1.is_closed()
        assert stream2.is_closed()

    @pytest.mark.asyncio
    async def test_closed_stream_operations(self):
        """测试关闭流上的操作"""
        mplex = MockMplexMuxer()
        conn = MockRawConnection()
        session = await mplex.create_session(conn, is_initiator=True)
        stream = await session.open_stream()

        await stream.close()

        # 关闭后写入应该失败
        with pytest.raises(ConnectionError):
            await stream.write(b"should fail")
