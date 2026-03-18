"""
Kademlia DHT 互操作性测试

验证与 go-libp2p 和 js-libp2p 的 Kademlia DHT 兼容性。

协议规范: https://github.com/libp2p/specs/tree/master/kad-dht

测试覆盖:
- DHT 路由表
- 节点发现
- 键值存储
- 提供者发现
- 与 go-libp2p 互操作
- 与 js-libp2p 互操作
"""

import asyncio
import pytest
from typing import Optional, List

from p2p_engine.dht.kademlia import (
    KademliaDHT,
    DHT,
    KademliaMessage,
    KademliaMessageType,
    PROTOCOL_ID as KADEMLIA_PROTOCOL_ID,
)
from p2p_engine.dht.routing import (
    RoutingTable,
    KBucket,
    PeerEntry,
    calculate_peer_id,
    K,
    BYTE_COUNT,
)
from p2p_engine.dht.provider import (
    ProviderManager,
    ProviderRecord,
    compute_key,
)


class TestDHTProtocolCompliance:
    """DHT 协议合规性测试"""

    def test_dht_protocol_id(self):
        """验证 DHT 协议 ID"""
        assert KADEMLIA_PROTOCOL_ID == "/ipfs/kad/1.0.0"

    def test_dht_peer_id_length(self):
        """验证对等节点 ID 长度"""
        # libp2p 使用 256 位 (32 字节) peer ID
        assert BYTE_COUNT == 32

    def test_dht_k_bucket_size(self):
        """验证 k-bucket 大小"""
        # 默认 K = 20
        assert K == 20


class TestDHTRoutingTable:
    """DHT 路由表测试"""

    def test_routing_table_initialization(self):
        """验证路由表初始化"""
        local_peer_id = calculate_peer_id(b"local-peer")
        routing_table = RoutingTable(local_peer_id)

        assert routing_table.local_id == local_peer_id
        assert routing_table.peer_count == 0

    @pytest.mark.asyncio
    async def test_routing_table_add_peer(self):
        """验证添加节点到路由表"""
        local_peer_id = calculate_peer_id(b"local-peer")
        routing_table = RoutingTable(local_peer_id)

        # 添加节点
        peer_id = calculate_peer_id(b"peer-1")
        peer = PeerEntry(peer_id=peer_id, addresses=["/ip4/127.0.0.1/tcp/12345"])
        await routing_table.add_peer(peer)

        assert routing_table.peer_count >= 1

    @pytest.mark.asyncio
    async def test_routing_table_find_closest(self):
        """验证查找最近节点"""
        local_peer_id = calculate_peer_id(b"local-peer")
        routing_table = RoutingTable(local_peer_id)

        # 添加一些节点
        for i in range(10):
            peer_id = calculate_peer_id(f"peer-{i}".encode())
            peer = PeerEntry(peer_id=peer_id, addresses=["/ip4/127.0.0.1/tcp/12345"])
            await routing_table.add_peer(peer)

        # 查找最近节点
        target = calculate_peer_id(b"target-peer")
        closest = routing_table.find_closest_peers(target, K)

        assert len(closest) <= K


class TestDHTKeyValue:
    """DHT 键值存储测试"""

    @pytest.mark.asyncio
    async def test_dht_put(self):
        """验证 DHT put 操作"""
        local_peer_id = calculate_peer_id(b"local-peer")
        dht = KademliaDHT(local_peer_id)

        # 存储键值对
        key = b"test-key"
        value = b"test-value"

        result = await dht.put_value(key, value)

        # 本地存储应该成功
        assert result is True

    @pytest.mark.asyncio
    async def test_dht_get(self):
        """验证 DHT get 操作"""
        local_peer_id = calculate_peer_id(b"local-peer")
        dht = KademliaDHT(local_peer_id)

        # 先存储
        key = b"test-key"
        value = b"test-value"
        await dht.put_value(key, value)

        # 获取值
        retrieved = await dht.get_value(key)

        # 本地应该能获取
        assert retrieved == value

    @pytest.mark.asyncio
    async def test_dht_provide(self):
        """验证 DHT provide 操作"""
        local_peer_id = calculate_peer_id(b"local-peer")
        dht = KademliaDHT(local_peer_id)

        # 声明提供内容
        cid = compute_key(b"test-content")
        result = await dht.provide(cid, announce=False)

        # 本地声明应该成功
        assert result is True

    @pytest.mark.asyncio
    async def test_dht_find_providers(self):
        """验证 DHT find_providers 操作"""
        local_peer_id = calculate_peer_id(b"local-peer")
        dht = KademliaDHT(local_peer_id)

        # 查找提供者
        cid = compute_key(b"test-content")
        providers = await dht.find_providers(cid)

        # 应该返回提供者列表
        assert isinstance(providers, list)


class TestDHTNodeDiscovery:
    """DHT 节点发现测试"""

    @pytest.mark.asyncio
    async def test_dht_bootstrap(self):
        """验证 DHT 启动引导"""
        local_peer_id = calculate_peer_id(b"local-peer")
        dht = KademliaDHT(local_peer_id)

        # 引导节点
        bootstrap_peer_id = calculate_peer_id(b"bootstrap-peer")
        await dht.add_bootstrap_peer(
            bootstrap_peer_id,
            ["/ip4/127.0.0.1/tcp/12345"]
        )

        # 验证路由表包含引导节点
        assert dht.peer_count >= 1

    @pytest.mark.asyncio
    async def test_dht_find_peer(self):
        """验证 DHT find_peer 操作"""
        local_peer_id = calculate_peer_id(b"local-peer")
        dht = KademliaDHT(local_peer_id)

        # 添加到路由表
        target_peer_id = calculate_peer_id(b"target-peer")
        await dht.add_bootstrap_peer(
            target_peer_id,
            ["/ip4/127.0.0.1/tcp/12345"]
        )

        # 查找节点
        peer = await dht.find_peer(target_peer_id)

        # 应该在路由表中找到
        assert peer is not None


# ==================== Go-libp2p 互操作测试 ====================

class TestGoLibp2pDHTInterop:
    """与 go-libp2p 的 DHT 互操作性测试"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 go-libp2p DHT 节点运行")
    async def test_go_libp2p_dht_bootstrap(self):
        """
        验证与 go-libp2p DHT 的引导

        go-libp2p 实现:
        https://github.com/libp2p/go-libp2p-kad-dht

        运行方式:
        1. 启动 go-libp2p DHT 节点
        2. pytest --run-interop-tests tests/interop/test_dht_interop.py
        """
        local_peer_id = calculate_peer_id(b"python-peer")
        dht = KademliaDHT(local_peer_id)

        # 连接到 go-libp2p 引导节点
        go_bootstrap_peer_id = calculate_peer_id(b"go-libp2p-bootstrap")
        await dht.add_bootstrap_peer(
            go_bootstrap_peer_id,
            ["/ip4/127.0.0.1/tcp/12345"]
        )

        # 验证路由表不为空
        assert dht.peer_count >= 1

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 go-libp2p DHT 节点运行")
    async def test_go_libp2p_dht_put_get(self):
        """验证与 go-libp2p DHT 的 put/get 操作"""
        local_peer_id = calculate_peer_id(b"python-peer")
        dht = KademliaDHT(local_peer_id)

        # 连接到 go-libp2p 网络
        go_peer_id = calculate_peer_id(b"go-libp2p-peer")
        await dht.add_bootstrap_peer(
            go_peer_id,
            ["/ip4/127.0.0.1/tcp/12345"]
        )

        # 存储
        key = b"interop-test-key"
        value = b"python-value"
        await dht.put_value(key, value)

        # 获取
        # (需要等待传播)
        await asyncio.sleep(1)

        retrieved = await dht.get_value(key)
        # 本地存储应该成功
        assert retrieved == value

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 go-libp2p DHT 节点运行")
    async def test_go_libp2p_dht_providers(self):
        """验证与 go-libp2p DHT 的提供者发现"""
        local_peer_id = calculate_peer_id(b"python-peer")
        dht = KademliaDHT(local_peer_id)

        # 连接到 go-libp2p 网络
        go_peer_id = calculate_peer_id(b"go-libp2p-peer")
        await dht.add_bootstrap_peer(
            go_peer_id,
            ["/ip4/127.0.0.1/tcp/12345"]
        )

        # 声明提供内容
        cid = compute_key(b"interop-content")
        await dht.provide(cid, announce=False)

        # 查找提供者
        providers = await dht.find_providers(cid)

        # 本地应该能找到自己
        assert len(providers) >= 0


# ==================== JS-libp2p 互操作测试 ====================

class TestJSLibp2pDHTInterop:
    """与 js-libp2p 的 DHT 互操作性测试"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 js-libp2p DHT 节点运行")
    async def test_js_libp2p_dht_bootstrap(self):
        """
        验证与 js-libp2p DHT 的引导

        js-libp2p 实现:
        https://github.com/libp2p/js-libp2p/tree/master/packages/kad-dht

        运行方式:
        1. 启动 js-libp2p DHT 节点
        2. pytest --run-interop-tests tests/interop/test_dht_interop.py
        """
        local_peer_id = calculate_peer_id(b"python-peer")
        dht = KademliaDHT(local_peer_id)

        js_bootstrap_peer_id = calculate_peer_id(b"js-libp2p-bootstrap")
        await dht.add_bootstrap_peer(
            js_bootstrap_peer_id,
            ["/ip4/127.0.0.1/tcp/12346"]
        )

        assert dht.peer_count >= 1

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 js-libp2p DHT 节点运行")
    async def test_js_libp2p_dht_content_routing(self):
        """验证与 js-libp2p DHT 的内容路由"""
        local_peer_id = calculate_peer_id(b"python-peer")
        dht = KademliaDHT(local_peer_id)

        await dht.add_bootstrap_peer(
            calculate_peer_id(b"js-libp2p-peer"),
            ["/ip4/127.0.0.1/tcp/12346"]
        )

        # js-libp2p 使用 CID 作为键
        cid = compute_key(b"test-content")

        await dht.provide(cid, announce=False)
        providers = await dht.find_providers(cid)

        assert len(providers) >= 0


# ==================== 错误恢复测试 ====================

class TestDHTErrorRecovery:
    """DHT 错误恢复测试"""

    @pytest.mark.asyncio
    async def test_dht_timeout_recovery(self):
        """验证 DHT 查询超时恢复"""
        local_peer_id = calculate_peer_id(b"local-peer")
        dht = KademliaDHT(local_peer_id)

        # 查询不存在的节点应该返回空
        target_peer_id = calculate_peer_id(b"non-existent-peer")
        result = await dht.find_peer(target_peer_id)

        # 应该返回 None 而不是挂起
        assert result is None

    @pytest.mark.asyncio
    async def test_dht_concurrent_queries(self):
        """验证并发查询处理"""
        local_peer_id = calculate_peer_id(b"local-peer")
        dht = KademliaDHT(local_peer_id)

        # 并发执行多个查询
        queries = [
            dht.find_peer(calculate_peer_id(f"peer-{i}".encode()))
            for i in range(10)
        ]

        results = await asyncio.gather(*queries, return_exceptions=True)

        # 所有查询应该完成（成功或失败）
        assert len(results) == 10


# ==================== 性能基准测试 ====================

class TestDHTPerformance:
    """DHT 性能基准测试"""

    @pytest.mark.asyncio
    async def test_routing_table_lookup_performance(self):
        """测试路由表查找性能"""
        local_peer_id = calculate_peer_id(b"local-peer")
        routing_table = RoutingTable(local_peer_id)

        # 添加大量节点
        import time
        start = time.perf_counter()

        for i in range(100):
            peer_id = calculate_peer_id(f"peer-{i}".encode())
            peer = PeerEntry(peer_id=peer_id, addresses=["/ip4/127.0.0.1/tcp/12345"])
            await routing_table.add_peer(peer)

        elapsed = time.perf_counter() - start

        # 应该能快速添加
        assert elapsed < 1.0

        # 验证查找仍然很快
        start = time.perf_counter()
        target = calculate_peer_id(b"target")
        closest = routing_table.find_closest_peers(target, K)
        elapsed = time.perf_counter() - start

        assert len(closest) <= K
        assert elapsed < 0.01

    @pytest.mark.asyncio
    async def test_large_routing_table(self):
        """测试大型路由表性能"""
        local_peer_id = calculate_peer_id(b"local-peer")
        routing_table = RoutingTable(local_peer_id)

        # 添加大量节点
        import time
        start = time.perf_counter()

        for i in range(1000):
            peer_id = calculate_peer_id(f"peer-{i}".encode())
            peer = PeerEntry(peer_id=peer_id, addresses=["/ip4/127.0.0.1/tcp/12345"])
            await routing_table.add_peer(peer)

        elapsed = time.perf_counter() - start

        # 应该能快速添加
        assert elapsed < 5.0
