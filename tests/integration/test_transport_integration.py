"""
传输层集成测试

测试传输管理器、传输升级器和各种传输协议的集成。
"""
import asyncio
import socket
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from p2p_engine.transport import (
    Transport,
    Listener,
    Connection,
    TransportError,
    TransportManager,
    TransportUpgrader,
    TransportBuilder,
    DialError,
    ListenError,
    SecurityTransport,
    StreamMuxer,
    SecureConnection,
    UpgradedConnection,
)


# ==================== Mock 实现 ====================

class MockConnection(Connection):
    """模拟连接"""

    def __init__(self, reader_data: bytes = b"", remote_addr: Optional[tuple] = None):
        self._reader_data = reader_data
        self._write_buffer: list[bytes] = []
        self._closed = False
        self._remote_addr = remote_addr or ("127.0.0.1", 12345)
        self._local_addr = ("127.0.0.1", 54321)
        self._read_pos = 0

    async def read(self, n: int = -1) -> bytes:
        if self._closed:
            raise TransportError("Connection closed")
        if n == -1:
            data = self._reader_data[self._read_pos:]
            self._read_pos = len(self._reader_data)
            return data
        data = self._reader_data[self._read_pos:self._read_pos + n]
        self._read_pos += len(data)
        return data

    async def write(self, data: bytes) -> int:
        if self._closed:
            raise TransportError("Connection closed")
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


class MockListener(Listener):
    """模拟监听器"""

    def __init__(self, addr: str):
        self._addr = addr
        self._closed = False
        self._pending_connections: asyncio.Queue = asyncio.Queue()

    async def accept(self) -> Connection:
        if self._closed:
            raise TransportError("Listener closed")
        return await self._pending_connections.get()

    async def close(self) -> None:
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    @property
    def addresses(self):
        return [(self._addr,)]

    def add_connection(self, conn: Connection) -> None:
        """添加连接（用于测试）"""
        self._pending_connections.put_nowait(conn)


class MockTCPTransport(Transport):
    """模拟TCP传输"""

    def __init__(self, name: str = "tcp"):
        self._name = name
        self._closed = False
        self._listeners: dict[str, MockListener] = {}
        self._connections: dict[str, MockConnection] = {}

    async def dial(self, addr: str) -> Connection:
        if self._closed:
            raise TransportError("Transport closed")
        # 模拟延迟
        await asyncio.sleep(0.01)
        conn = MockConnection(remote_addr=(addr, 80))
        self._connections[addr] = conn
        return conn

    async def listen(self, addr: str) -> Listener:
        if self._closed:
            raise TransportError("Transport closed")
        listener = MockListener(addr)
        self._listeners[addr] = listener
        return listener

    def protocols(self) -> list[str]:
        return [f"/{self._name}/1.0.0"]

    async def close(self) -> None:
        self._closed = True


class MockSecurityTransport(SecurityTransport):
    """模拟安全传输"""

    def __init__(self, protocol_id: str = "/mock-security/1.0.0"):
        self._protocol_id = protocol_id
        self._handshake_count = 0

    async def secure_inbound(
        self,
        conn: Connection,
        peer_id: Optional[str] = None
    ) -> SecureConnection:
        await asyncio.sleep(0.01)
        self._handshake_count += 1
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
        await asyncio.sleep(0.01)
        self._handshake_count += 1
        return SecureConnection(conn, peer_id, self._protocol_id)

    def get_protocol_id(self) -> str:
        return self._protocol_id


class MockMuxer(StreamMuxer):
    """模拟流复用器"""

    def __init__(self, protocol_id: str = "/mock-muxer/1.0.0"):
        self._protocol_id = protocol_id
        self._session_count = 0

    async def create_session(
        self,
        conn: Connection,
        is_initiator: bool
    ) -> "MuxedSession":
        from p2p_engine.transport.upgrader import MuxedSession
        await asyncio.sleep(0.01)
        self._session_count += 1
        return MuxedSession(conn, self._protocol_id, is_initiator)

    def get_protocol_id(self) -> str:
        return self._protocol_id


# ==================== Transport Upgrader 测试 ====================

@pytest.mark.integration
class TestTransportUpgrader:
    """传输升级器测试"""

    @pytest.fixture
    def security(self):
        return MockSecurityTransport("/noise/xx/1.0.0")

    @pytest.fixture
    def muxer(self):
        return MockMuxer("/yamux/1.0.0")

    @pytest.fixture
    def upgrader(self, security, muxer):
        return TransportUpgrader(
            security_transports=[security],
            muxers=[muxer]
        )

    @pytest.mark.asyncio
    async def test_upgrade_outbound(self, upgrader):
        """测试出站连接升级"""
        conn = MockConnection(b"test data")
        peer_id = "peer-123"

        upgraded = await upgrader.upgrade_outbound(conn, peer_id)

        assert isinstance(upgraded, UpgradedConnection)
        assert upgraded.peer_id == peer_id
        assert upgraded.security_protocol == "/noise/xx/1.0.0"
        assert upgraded.muxer_protocol == "/yamux/1.0.0"

    @pytest.mark.asyncio
    async def test_upgrade_inbound(self, upgrader):
        """测试入站连接升级"""
        conn = MockConnection(b"test data")

        upgraded = await upgrader.upgrade_inbound(conn, "peer-456")

        assert isinstance(upgraded, UpgradedConnection)
        assert upgraded.peer_id == "peer-456"

    @pytest.mark.asyncio
    async def test_upgrade_without_security(self):
        """测试无安全传输的升级"""
        upgrader = TransportUpgrader(
            security_transports=[],
            muxers=[MockMuxer()]
        )

        conn = MockConnection()
        upgraded = await upgrader.upgrade_outbound(conn, "peer-789")

        assert upgraded.security_protocol == "/insecure/1.0.0"

    @pytest.mark.asyncio
    async def test_upgrade_failure_no_muxer(self):
        """测试无复用器时升级失败"""
        upgrader = TransportUpgrader(
            security_transports=[MockSecurityTransport()],
            muxers=[]
        )

        conn = MockConnection()

        with pytest.raises(TransportError, match="No muxers available"):
            await upgrader.upgrade_outbound(conn, "peer-000")

    @pytest.mark.asyncio
    async def test_upgrade_fallback_security(self):
        """测试安全传输降级"""
        failing_security = MockSecurityTransport("/failing/1.0.0")

        async def failing_secure_inbound(conn, peer_id):
            raise TransportError("Security handshake failed")

        failing_security.secure_inbound = failing_secure_inbound
        failing_security.secure_outbound = failing_secure_inbound

        working_security = MockSecurityTransport("/working/1.0.0")

        upgrader = TransportUpgrader(
            security_transports=[failing_security, working_security],
            muxers=[MockMuxer()]
        )

        conn = MockConnection()
        upgraded = await upgrader.upgrade_outbound(conn, "peer-fallback")

        assert upgraded.security_protocol == "/working/1.0.0"


# ==================== Transport Manager 测试 ====================

@pytest.mark.integration
class TestTransportManager:
    """传输管理器测试"""

    @pytest.fixture
    def transport(self):
        return MockTCPTransport("tcp")

    @pytest.fixture
    def upgrader(self):
        return TransportUpgrader(
            security_transports=[MockSecurityTransport()],
            muxers=[MockMuxer()]
        )

    @pytest.fixture
    def manager(self, upgrader):
        return TransportManager("local-peer-123", upgrader)

    @pytest.mark.asyncio
    async def test_add_transport(self, manager, transport):
        """测试添加传输"""
        manager.add_transport(transport, priority=0)

        protocols = manager.list_transports()
        assert "/tcp/1.0.0" in protocols

    @pytest.mark.asyncio
    async def test_listen(self, manager, transport):
        """测试监听"""
        manager.add_transport(transport, priority=0)

        listener = await manager.listen("0.0.0.0:8080")
        assert not listener.is_closed()

        await manager.close()

    @pytest.mark.asyncio
    async def test_dial(self, manager, transport):
        """测试拨号"""
        manager.add_transport(transport, priority=0)

        conn = await manager.dial("127.0.0.1:9999", "remote-peer-456")

        assert conn.peer_id == "remote-peer-456"
        assert not conn.is_closed()

    @pytest.mark.asyncio
    async def test_dial_timeout(self, manager):
        """测试拨号超时"""
        class SlowTransport(Transport):
            async def dial(self, addr: str) -> Connection:
                await asyncio.sleep(100)
                return MockConnection()

            async def listen(self, addr: str) -> Listener:
                pass

            def protocols(self) -> list[str]:
                return ["/slow/1.0.0"]

            async def close(self) -> None:
                pass

        manager.add_transport(SlowTransport(), priority=0)
        manager.set_dial_timeout(0.1)

        with pytest.raises(DialError, match="timeout"):
            await manager.dial("slow-address", "peer-timeout")

    @pytest.mark.asyncio
    async def test_accept_connection(self, manager, transport):
        """测试接受连接"""
        manager.add_transport(transport, priority=0)

        # 开始监听
        listener = await manager.listen("0.0.0.0:8081")

        # 在另一个任务中接受连接
        accepted = False

        async def accept_task():
            nonlocal accepted
            peer_id, conn = await manager.accept()
            assert peer_id == "unknown-peer"  # SecureConnection default
            accepted = True

        task = asyncio.create_task(accept_task())

        # 等待监听器准备好
        await asyncio.sleep(0.01)

        # 模拟传入连接
        if isinstance(listener, MockListener):
            incoming_conn = MockConnection(b"incoming data")
            listener.add_connection(incoming_conn)

        # 等待接受完成
        await asyncio.wait_for(task, timeout=1.0)

        assert accepted

        await manager.close()

    @pytest.mark.asyncio
    async def test_transport_priority(self, manager):
        """测试传输优先级"""
        high_priority = MockTCPTransport("high")
        low_priority = MockTCPTransport("low")

        manager.add_transport(low_priority, priority=10)
        manager.add_transport(high_priority, priority=1)

        # 应该使用高优先级的传输
        conn = await manager.dial("test-address", "peer-priority")
        assert conn is not None

    @pytest.mark.asyncio
    async def test_close_manager(self, manager, transport):
        """测试关闭管理器"""
        manager.add_transport(transport, priority=0)

        await manager.listen("0.0.0.0:8082")
        await manager.close()

        # 关闭后不能拨号
        with pytest.raises(DialError, match="closed"):
            await manager.dial("any-address", "any-peer")


# ==================== Transport Builder 测试 ====================

@pytest.mark.integration
class TestTransportBuilder:
    """传输构建器测试"""

    @pytest.mark.asyncio
    async def test_build_manager(self):
        """测试构建传输管理器"""
        builder = TransportBuilder("local-peer-456")

        builder.add_transport(MockTCPTransport("tcp"), priority=0)
        builder.add_security(MockSecurityTransport("/noise/1.0.0"))
        builder.add_muxer(MockMuxer("/yamux/1.0.0"))

        manager = builder.build()

        assert manager.local_peer_id == "local-peer-456"
        assert manager.upgrader is not None

        conn = await manager.dial("test-addr", "remote-peer")
        assert conn.peer_id == "remote-peer"

        await manager.close()


# ==================== 端到端集成测试 ====================

@pytest.mark.integration
class TestE2ETransportIntegration:
    """端到端传输集成测试"""

    @pytest.mark.asyncio
    async def test_full_connection_flow(self):
        """测试完整的连接流程"""
        # 创建两个节点
        node1_upgrader = TransportUpgrader(
            security_transports=[MockSecurityTransport("/noise/1.0.0")],
            muxers=[MockMuxer("/yamux/1.0.0")]
        )
        node1 = TransportManager("node-1", node1_upgrader)
        node1.add_transport(MockTCPTransport("tcp"), priority=0)

        node2_upgrader = TransportUpgrader(
            security_transports=[MockSecurityTransport("/noise/1.0.0")],
            muxers=[MockMuxer("/yamux/1.0.0")]
        )
        node2 = TransportManager("node-2", node2_upgrader)
        node2.add_transport(MockTCPTransport("tcp"), priority=0)

        # Node 2 监听
        listener = await node2.listen("0.0.0.0:9000")

        # 在另一个任务中接受连接
        accepted_conn = None

        async def accept_task():
            nonlocal accepted_conn
            peer_id, conn = await node2.accept()
            accepted_conn = conn

        task = asyncio.create_task(accept_task())

        # 等待监听器准备好
        await asyncio.sleep(0.01)

        # 模拟传入连接到 node 2
        if isinstance(listener, MockListener):
            incoming_raw = MockConnection(b"hello from node 1")
            listener.add_connection(incoming_raw)

        # 等待接受完成
        await asyncio.wait_for(task, timeout=1.0)

        assert accepted_conn is not None
        assert accepted_conn.peer_id == "unknown-peer"

        # Node 1 拨号到 Node 2
        conn1 = await node1.dial("127.0.0.1:9000", "node-2")
        assert conn1.peer_id == "node-2"

        # 清理
        await node1.close()
        await node2.close()

    @pytest.mark.asyncio
    async def test_multi_protocol_selection(self):
        """测试多协议选择"""
        builder = TransportBuilder("multi-proto-node")

        # 添加多个传输，优先级不同
        builder.add_transport(MockTCPTransport("tcp"), priority=10)
        builder.add_transport(MockTCPTransport("quic"), priority=1)
        builder.add_transport(MockTCPTransport("webrtc"), priority=5)

        builder.add_security(MockSecurityTransport())
        builder.add_muxer(MockMuxer())

        manager = builder.build()

        # 应该使用最高优先级的传输 (quic, priority=1)
        protocols = manager.list_transports()
        assert len(protocols) == 3

        await manager.close()

    @pytest.mark.asyncio
    async def test_connection_upgrade_chain(self):
        """测试连接升级链"""
        upgrader = TransportUpgrader(
            security_transports=[MockSecurityTransport("/tls/1.0.0")],
            muxers=[MockMuxer("/mplex/6.7.0")]
        )

        raw_conn = MockConnection(b"raw data")
        upgraded = await upgrader.upgrade_outbound(raw_conn, "peer-upgrade")

        # 验证升级链
        assert isinstance(upgraded, UpgradedConnection)
        assert isinstance(upgraded.secure_connection, SecureConnection)
        assert upgraded.muxed_session is not None

        # 验证协议
        assert upgraded.security_protocol == "/tls/1.0.0"
        assert upgraded.muxer_protocol == "/mplex/6.7.0"

        # 关闭连接
        await upgraded.close()
        assert upgraded.is_closed()


# ==================== 错误恢复测试 ====================

@pytest.mark.integration
class TestErrorRecovery:
    """错误恢复测试"""

    @pytest.mark.asyncio
    async def test_dial_retry_with_different_transport(self):
        """测试使用不同传输重试拨号"""
        class FailingTransport(Transport):
            async def dial(self, addr: str) -> Connection:
                raise TransportError("Connection refused")

            async def listen(self, addr: str) -> Listener:
                pass

            def protocols(self) -> list[str]:
                return ["/failing/1.0.0"]

            async def close(self) -> None:
                pass

        upgrader = TransportUpgrader(
            security_transports=[MockSecurityTransport()],
            muxers=[MockMuxer()]
        )
        manager = TransportManager("test-peer", upgrader)

        # 添加失败和成功的传输
        manager.add_transport(FailingTransport(), priority=0)
        manager.add_transport(MockTCPTransport("tcp"), priority=1)

        # 应该降级到成功的传输
        conn = await manager.dial("test-addr", "remote-peer")
        assert conn is not None

        await manager.close()

    @pytest.mark.asyncio
    async def test_security_upgrade_fallback(self):
        """测试安全升级降级"""
        class FailingSecurity(SecurityTransport):
            async def secure_inbound(self, conn, peer_id=None):
                raise TransportError("Handshake failed")

            async def secure_outbound(self, conn, peer_id):
                raise TransportError("Handshake failed")

            def get_protocol_id(self) -> str:
                return "/failing/1.0.0"

        upgrader = TransportUpgrader(
            security_transports=[
                FailingSecurity(),
                MockSecurityTransport("/working/1.0.0")
            ],
            muxers=[MockMuxer()]
        )

        raw_conn = MockConnection()
        upgraded = await upgrader.upgrade_outbound(raw_conn, "peer-test")

        # 应该使用工作的安全传输
        assert upgraded.security_protocol == "/working/1.0.0"
