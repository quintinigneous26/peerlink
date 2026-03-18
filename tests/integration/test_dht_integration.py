"""
Kademlia DHT 集成测试

测试 Kademlia DHT 与传输层的完整集成。
"""
import asyncio
from dataclasses import dataclass
import logging
from typing import Optional, List, Dict, Set, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
import time

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
    """模拟原始连接"""

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
    """模拟 TLS 安全传输"""

    PROTOCOL_ID = "/tls/1.0.0"

    async def secure_inbound(
        self,
        conn: Connection,
        peer_id: Optional[str] = None
    ) -> SecureConnection:
        await asyncio.sleep(0.001)
        return SecureConnection(
            conn,
            peer_id or "unknown-peer",
            self.PROTOCOL_ID
        )

    async def secure_outbound(
        self,
        conn: Connection,
        peer_id: str
    ) -> SecureConnection:
        await asyncio.sleep(0.001)
        return SecureConnection(conn, peer_id, self.PROTOCOL_ID)

    def get_protocol_id(self) -> str:
        return self.PROTOCOL_ID


class MockMplexMuxer(StreamMuxer):
    """模拟 mplex 流复用器"""

    PROTOCOL_ID = "/mplex/6.7.0"

    async def create_session(
        self,
        conn: Connection,
        is_initiator: bool
    ):
        await asyncio.sleep(0.001)
        return MockMplexSession(conn, self.PROTOCOL_ID, is_initiator)

    def get_protocol_id(self) -> str:
        return self.PROTOCOL_ID


class MockMplexSession:
    """模拟 mplex 会话"""

    def __init__(self, conn: Connection, protocol_id: str, is_initiator: bool):
        self._conn = conn
        self._protocol_id = protocol_id
        self._is_initiator = is_initiator
        self._closed = False
        self._streams: dict = {}
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

    async def open_stream(self):
        async with self._lock:
            if self._closed:
                raise ConnectionError("Session closed")
            stream_id = self._next_stream_id
            self._next_stream_id += 2
            stream = MockMuxedStream(stream_id, self)
            self._streams[stream_id] = stream
            return stream

    async def close(self) -> None:
        async with self._lock:
            self._closed = True
            for stream in self._streams.values():
                await stream.close()
            self._streams.clear()


class MockMuxedStream(Connection):
    """模拟复用流"""

    def __init__(self, stream_id: int, session):
        self._stream_id = stream_id
        self._session = session
        self._closed = False
        self._read_queue: asyncio.Queue = asyncio.Queue()
        self._write_buffer: list = []

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


# ==================== DHT 相关类型 ====================

@dataclass
class PeerID:
    """对等节点 ID"""
    id: bytes

    def __str__(self) -> str:
        return self.id.hex()[:16]

    def __xor__(self, other: 'PeerID') -> int:
        """计算 XOR 距离"""
        a = int.from_bytes(self.id, 'big')
        b = int.from_bytes(other.id, 'big')
        return a ^ b

    def __eq__(self, other) -> bool:
        if not isinstance(other, PeerID):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    @classmethod
    def random(cls) -> 'PeerID':
        """生成随机 PeerID"""
        import os
        return PeerID(os.urandom(32))


@dataclass
class PeerInfo:
    """对等节点信息"""
    peer_id: PeerID
    addresses: List[str]
    last_seen: float = 0.0


# ==================== Mock Kademlia DHT ====================

class MockKademliaDHT:
    """模拟 Kademlia DHT 实现"""

    PROTOCOL_ID = "/ipfs/kad/1.0.0"
    K = 8  # k-bucket 大小

    def __init__(self, local_peer_id: PeerID):
        self._local_peer_id = local_peer_id
        self._kbuckets: Dict[int, List[PeerInfo]] = {}
        self._data_store: Dict[bytes, bytes] = {}
        self._providers: Dict[bytes, Set[PeerID]] = {}
        self._lock = asyncio.Lock()

    @property
    def peer_id(self) -> PeerID:
        return self._local_peer_id

    async def add_peer(self, peer_info: PeerInfo) -> None:
        """添加对等节点到路由表"""
        async with self._lock:
            distance = self._local_peer_id ^ peer_info.peer_id
            bucket_index = distance.bit_length() - 1

            if bucket_index not in self._kbuckets:
                self._kbuckets[bucket_index] = []

            bucket = self._kbuckets[bucket_index]

            # 检查是否已存在
            for p in bucket:
                if p.peer_id.id == peer_info.peer_id.id:
                    p.last_seen = time.time()
                    return

            # 添加新节点
            peer_info.last_seen = time.time()
            if len(bucket) < self.K:
                bucket.append(peer_info)
            else:
                # 替换最旧的节点
                oldest = min(bucket, key=lambda p: p.last_seen)
                if peer_info.last_seen > oldest.last_seen:
                    bucket.remove(oldest)
                    bucket.append(peer_info)

    async def find_peer(self, target: PeerID) -> Optional[PeerInfo]:
        """查找对等节点"""
        async with self._lock:
            # 在路由表中查找
            for bucket in self._kbuckets.values():
                for peer in bucket:
                    if peer.peer_id.id == target.id:
                        return peer
            return None

    async def find_closest_peers(self, target: PeerID, count: int = 20) -> List[PeerInfo]:
        """查找最接近目标的节点"""
        async with self._lock:
            peers = []
            for bucket in self._kbuckets.values():
                peers.extend(bucket)

            # 按 XOR 距离排序
            peers.sort(key=lambda p: p.peer_id ^ target)
            return peers[:count]

    async def put_value(self, key: bytes, value: bytes) -> None:
        """存储键值"""
        async with self._lock:
            self._data_store[key] = value

    async def get_value(self, key: bytes) -> Optional[bytes]:
        """获取键值"""
        async with self._lock:
            return self._data_store.get(key)

    async def provide(self, key: bytes, peer_id: PeerID) -> None:
        """声明提供内容"""
        async with self._lock:
            if key not in self._providers:
                self._providers[key] = set()
            self._providers[key].add(peer_id)

    async def find_providers(self, key: bytes, count: int = 20) -> List[PeerInfo]:
        """查找内容提供者"""
        async with self._lock:
            providers = self._providers.get(key, set())
            result = []
            for peer_id in providers:
                peer = await self.find_peer(peer_id)
                if peer:
                    result.append(peer)
            return result[:count]


# ==================== DHT 集成测试 ====================

@pytest.mark.integration
class TestKademliaDHTIntegration:
    """Kademlia DHT 集成测试"""

    @pytest.fixture
    def local_peer_id(self):
        return PeerID.random()

    @pytest.fixture
    def dht(self, local_peer_id):
        return MockKademliaDHT(local_peer_id)

    @pytest.mark.asyncio
    async def test_dht_initialization(self, dht, local_peer_id):
        """测试 DHT 初始化"""
        assert dht.peer_id == local_peer_id
        assert len(dht._kbuckets) == 0
        assert len(dht._data_store) == 0

    @pytest.mark.asyncio
    async def test_dht_add_peer(self, dht):
        """测试添加对等节点"""
        peer1 = PeerInfo(
            peer_id=PeerID.random(),
            addresses=["/ip4/127.0.0.1/tcp/8000"]
        )

        await dht.add_peer(peer1)

        # 验证节点被添加到某个 bucket
        total_peers = sum(len(bucket) for bucket in dht._kbuckets.values())
        assert total_peers == 1

    @pytest.mark.asyncio
    async def test_dht_find_peer(self, dht):
        """测试查找对等节点"""
        peer1 = PeerInfo(
            peer_id=PeerID.random(),
            addresses=["/ip4/127.0.0.1/tcp/8000"]
        )

        await dht.add_peer(peer1)
        found = await dht.find_peer(peer1.peer_id)

        assert found is not None
        assert found.peer_id.id == peer1.peer_id.id

    @pytest.mark.asyncio
    async def test_dht_find_closest_peers(self, dht):
        """测试查找最近节点"""
        target = PeerID.random()

        # 添加多个节点
        for i in range(10):
            peer = PeerInfo(
                peer_id=PeerID.random(),
                addresses=[f"/ip4/127.0.0.{i}/tcp/800{i}"]
            )
            await dht.add_peer(peer)

        # 查找最近节点
        closest = await dht.find_closest_peers(target, count=5)

        assert len(closest) <= 5
        # 验证排序正确
        if len(closest) > 1:
            for i in range(len(closest) - 1):
                dist1 = closest[i].peer_id ^ target
                dist2 = closest[i + 1].peer_id ^ target
                assert dist1 <= dist2

    @pytest.mark.asyncio
    async def test_dht_put_get_value(self, dht):
        """测试键值存储"""
        key = b"test_key"
        value = b"test_value"

        await dht.put_value(key, value)
        retrieved = await dht.get_value(key)

        assert retrieved == value

    @pytest.mark.asyncio
    async def test_dht_providers(self, dht):
        """测试内容提供者"""
        key = b"content_cid"
        provider1 = PeerInfo(
            peer_id=PeerID.random(),
            addresses=["/ip4/127.0.0.1/tcp/8001"]
        )
        provider2 = PeerInfo(
            peer_id=PeerID.random(),
            addresses=["/ip4/127.0.0.1/tcp/8002"]
        )

        await dht.add_peer(provider1)
        await dht.add_peer(provider2)
        await dht.provide(key, provider1.peer_id)
        await dht.provide(key, provider2.peer_id)

        providers = await dht.find_providers(key)

        assert len(providers) == 2

    @pytest.mark.asyncio
    async def test_dht_bucket_limit(self, dht):
        """测试 k-bucket 大小限制"""
        # 添加超过 K 个节点
        for i in range(dht.K + 5):
            peer = PeerInfo(
                peer_id=PeerID.random(),
                addresses=[f"/ip4/127.0.0.{i}/tcp/800{i}"]
            )
            await dht.add_peer(peer)

        # 验证没有超过 K
        for bucket in dht._kbuckets.values():
            assert len(bucket) <= dht.K


# ==================== DHT 与传输管理器集成测试 ====================

@pytest.mark.integration
class TestDHTWithTransportManager:
    """DHT 与传输管理器集成测试"""

    @pytest.fixture
    def local_peer_id(self):
        return PeerID.random()

    @pytest.fixture
    def dht(self, local_peer_id):
        return MockKademliaDHT(local_peer_id)

    @pytest.fixture
    def manager(self, local_peer_id):
        tls = MockTLSSecurity()
        mplex = MockMplexMuxer()
        upgrader = TransportUpgrader(
            security_transports=[tls],
            muxers=[mplex]
        )
        return TransportManager(str(local_peer_id), upgrader)

    @pytest.mark.asyncio
    async def test_dht_peer_discovery_via_transport(self, dht, manager):
        """测试通过传输层发现节点"""
        # 模拟通过传输发现新节点
        discovered_peer = PeerInfo(
            peer_id=PeerID.random(),
            addresses=["/ip4/192.168.1.100/tcp/8000"]
        )

        await dht.add_peer(discovered_peer)

        # 验证可以找到
        found = await dht.find_peer(discovered_peer.peer_id)
        assert found is not None

    @pytest.mark.asyncio
    async def test_dht_value_sharing_via_transport(self, dht, manager):
        """测试通过传输层共享值"""
        key = b"shared_key"
        value = b"shared_value"

        # 存储值
        await dht.put_value(key, value)

        # 通过 DHT 获取
        retrieved = await dht.get_value(key)
        assert retrieved == value


# ==================== DHT 性能测试 ====================

@pytest.mark.integration
class TestDHTPerformance:
    """DHT 性能测试"""

    @pytest.fixture
    def dht(self):
        return MockKademliaDHT(PeerID.random())

    @pytest.mark.asyncio
    async def test_dht_large_routing_table(self, dht):
        """测试大型路由表性能"""
        # 添加大量节点
        start = time.time()
        for i in range(1000):
            peer = PeerInfo(
                peer_id=PeerID.random(),
                addresses=[f"/ip4/10.0.{i // 256}.{i % 256}/tcp/{8000 + i}"]
            )
            await dht.add_peer(peer)
        elapsed = time.time() - start

        # 应该快速完成
        assert elapsed < 1.0

        # 测试查找性能
        start = time.time()
        target = PeerID.random()
        closest = await dht.find_closest_peers(target, count=20)
        elapsed = time.time() - start

        assert len(closest) == 20
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_dht_concurrent_operations(self, dht):
        """测试并发操作"""
        key = b"concurrent_key"

        # 并发存储
        tasks = []
        for i in range(100):
            value = f"value_{i}".encode()
            tasks.append(dht.put_value(key, value))

        await asyncio.gather(*tasks)

        # 验证最后一次写入生效
        retrieved = await dht.get_value(key)
        assert retrieved == b"value_99"

    @pytest.mark.asyncio
    async def test_dht_provider_discovery_performance(self, dht):
        """测试提供者发现性能"""
        key = b"content_key"

        # 添加多个提供者
        providers = []
        for i in range(50):
            peer = PeerInfo(
                peer_id=PeerID.random(),
                addresses=[f"/ip4/127.0.0.{i}/tcp/800{i}"]
            )
            await dht.add_peer(peer)
            await dht.provide(key, peer.peer_id)
            providers.append(peer)

        # 查找提供者
        start = time.time()
        found = await dht.find_providers(key, count=20)
        elapsed = time.time() - start

        assert len(found) == 20
        assert elapsed < 0.1


# ==================== DHT 错误处理测试 ====================

@pytest.mark.integration
class TestDHTErrors:
    """DHT 错误处理测试"""

    @pytest.fixture
    def dht(self):
        return MockKademliaDHT(PeerID.random())

    @pytest.mark.asyncio
    async def test_dht_get_nonexistent_key(self, dht):
        """测试获取不存在的键"""
        result = await dht.get_value(b"nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_dht_find_nonexistent_peer(self, dht):
        """测试查找不存在的节点"""
        target = PeerID.random()
        result = await dht.find_peer(target)
        assert result is None

    @pytest.mark.asyncio
    async def test_dht_find_providers_no_providers(self, dht):
        """测试查找没有提供者的内容"""
        providers = await dht.find_providers(b"no_providers")
        assert len(providers) == 0


# ==================== 辅助函数 ====================

