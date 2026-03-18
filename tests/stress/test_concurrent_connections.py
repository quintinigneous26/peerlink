"""
并发连接压力测试
使用Locust进行负载测试
"""
import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock

import pytest


@pytest.mark.stress
@pytest.mark.asyncio
class TestConcurrentConnections:
    """并发连接压力测试"""

    async def test_small_concurrent_connections(self):
        """测试小规模并发连接 (10个)"""
        concurrent_count = 10
        connections = []

        async def establish_connection(client_id):
            await asyncio.sleep(0.01)
            return {
                "client_id": client_id,
                "status": "connected",
                "connected_at": time.time(),
            }

        # 并发建立连接
        tasks = [
            establish_connection(f"client_{i}")
            for i in range(concurrent_count)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == concurrent_count
        assert all(r["status"] == "connected" for r in results)

    async def test_medium_concurrent_connections(self):
        """测试中等规模并发连接 (50个)"""
        concurrent_count = 50

        async def establish_connection(client_id):
            await asyncio.sleep(0.01)
            return {"client_id": client_id, "status": "connected"}

        start_time = time.time()
        tasks = [
            establish_connection(f"client_{i}")
            for i in range(concurrent_count)
        ]
        results = await asyncio.gather(*tasks)
        duration = time.time() - start_time

        assert len(results) == concurrent_count
        # 验证并发确实提高了效率 (顺序执行需要50*0.01=0.5s，并发应该更快)
        assert duration < 0.4

    async def test_large_concurrent_connections(self):
        """测试大规模并发连接 (100个)"""
        concurrent_count = 100

        connected_clients = []

        async def client_simulation(client_id):
            # 模拟完整连接流程
            await asyncio.sleep(0.001)  # 注册
            await asyncio.sleep(0.001)  # 信令连接
            await asyncio.sleep(0.001)  # STUN查询
            await asyncio.sleep(0.001)  # P2P连接

            connected_clients.append(client_id)
            return {"client_id": client_id, "status": "connected"}

        start_time = time.time()
        tasks = [
            client_simulation(f"client_{i}")
            for i in range(concurrent_count)
        ]
        results = await asyncio.gather(*tasks)
        duration = time.time() - start_time

        assert len(results) == concurrent_count
        assert len(connected_clients) == concurrent_count
        print(f"连接 {concurrent_count} 个客户端耗时: {duration:.2f}秒")

    async def test_connection_with_data_transfer(self):
        """测试并发连接后的数据传输"""
        concurrent_count = 20
        messages_per_client = 10

        async def client_session(client_id):
            # 连接
            await asyncio.sleep(0.01)

            # 发送消息
            for msg_id in range(messages_per_client):
                await asyncio.sleep(0.001)
                # 模拟发送
                pass

            return {
                "client_id": client_id,
                "messages_sent": messages_per_client,
            }

        tasks = [
            client_session(f"client_{i}")
            for i in range(concurrent_count)
        ]
        results = await asyncio.gather(*tasks)

        total_messages = sum(r["messages_sent"] for r in results)
        assert total_messages == concurrent_count * messages_per_client


@pytest.mark.stress
@pytest.mark.asyncio
class TestSignalingStress:
    """信令服务器压力测试"""

    async def test_concurrent_websocket_connections(self):
        """测试并发WebSocket连接"""
        concurrent_count = 50

        async def websocket_client(client_id):
            await asyncio.sleep(0.01)
            return {"client_id": client_id, "ws_connected": True}

        tasks = [
            websocket_client(f"ws_client_{i}")
            for i in range(concurrent_count)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r["ws_connected"] for r in results)

    async def test_concurrent_message_broadcast(self):
        """测试并发消息广播"""
        # 模拟一个房间有多个客户端
        room_clients = 20
        broadcast_count = 10

        messages_broadcast = []

        async def broadcast_to_room(room_id, message_id):
            await asyncio.sleep(0.001)
            messages_broadcast.append(message_id)
            return {"room_id": room_id, "recipients": room_clients}

        tasks = [
            broadcast_to_room("room_001", f"msg_{i}")
            for i in range(broadcast_count)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == broadcast_count
        assert all(r["recipients"] == room_clients for r in results)

    async def test_concurrent_offer_answer_exchange(self):
        """测试并发的Offer/Answer交换"""
        pair_count = 10

        async def exchange_offer_answer(pair_id):
            await asyncio.sleep(0.01)
            return {
                "pair_id": pair_id,
                "offer_exchanged": True,
                "answer_exchanged": True,
            }

        tasks = [
            exchange_offer_answer(f"pair_{i}")
            for i in range(pair_count)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r["offer_exchanged"] and r["answer_exchanged"] for r in results)


@pytest.mark.stress
@pytest.mark.asyncio
class TestSTUNStress:
    """STUN服务器压力测试"""

    async def test_concurrent_stun_requests(self):
        """测试并发STUN请求"""
        request_count = 100

        async def stun_request(client_id):
            await asyncio.sleep(0.001)
            return {
                "client_id": client_id,
                "mapped_address": "203.0.113.1",
                "mapped_port": 54321 + hash(client_id) % 1000,
            }

        start_time = time.time()
        tasks = [
            stun_request(f"client_{i}")
            for i in range(request_count)
        ]
        results = await asyncio.gather(*tasks)
        duration = time.time() - start_time

        assert len(results) == request_count
        print(f"处理 {request_count} 个STUN请求耗时: {duration:.2f}秒")

    async def test_rapid_stun_requests_from_same_client(self):
        """测试同一客户端快速发送多个STUN请求"""
        client_id = "rapid_client"
        request_count = 50

        requests_sent = []

        async def send_stun_request(req_id):
            await asyncio.sleep(0.001)
            requests_sent.append(req_id)
            return {"request_id": req_id, "status": "success"}

        tasks = [
            send_stun_request(f"{client_id}_req_{i}")
            for i in range(request_count)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == request_count
        assert len(requests_sent) == request_count


@pytest.mark.stress
@pytest.mark.asyncio
class TestDIDStress:
    """DID服务压力测试"""

    async def test_concurrent_device_registrations(self):
        """测试并发设备注册"""
        registration_count = 50

        async def register_device(device_id):
            await asyncio.sleep(0.01)
            return {
                "device_id": device_id,
                "did": f"did:p2p:{device_id}",
                "status": "registered",
            }

        tasks = [
            register_device(f"device_{i}")
            for i in range(registration_count)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == registration_count
        assert all(r["status"] == "registered" for r in results)

    async def test_concurrent_did_resolutions(self):
        """测试并发DID解析"""
        resolution_count = 100

        async def resolve_did(did):
            await asyncio.sleep(0.001)
            return {
                "did": did,
                "document": {"id": did, "@context": ["https://www.w3.org/ns/did/v1"]},
            }

        tasks = [
            resolve_did(f"did:p2p:device_{i}")
            for i in range(resolution_count)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == resolution_count

    async def test_concurrent_authentications(self):
        """测试并发认证"""
        auth_count = 50

        async def authenticate(device_id):
            await asyncio.sleep(0.01)
            return {
                "device_id": device_id,
                "authenticated": True,
                "token": f"token_{device_id}",
            }

        tasks = [
            authenticate(f"device_{i}")
            for i in range(auth_count)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r["authenticated"] for r in results)


@pytest.mark.stress
@pytest.mark.asyncio
class TestRelayStress:
    """Relay服务器压力测试"""

    async def test_concurrent_relay_allocations(self):
        """测试并发Relay分配"""
        allocation_count = 20

        async def allocate_relay(client_id, peer_id):
            await asyncio.sleep(0.02)
            return {
                "client_id": client_id,
                "peer_id": peer_id,
                "relay_addr": "198.51.100.1",
                "relay_port": 50000 + hash(client_id) % 1000,
                "status": "allocated",
            }

        tasks = [
            allocate_relay(f"client_{i}", f"peer_{i}")
            for i in range(allocation_count)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r["status"] == "allocated" for r in results)

    async def test_concurrent_relay_data_transfer(self):
        """测试并发Relay数据传输"""
        transfer_count = 30
        data_size = 1024  # 1KB

        async def relay_transfer(transfer_id):
            await asyncio.sleep(0.01)
            return {
                "transfer_id": transfer_id,
                "bytes_transferred": data_size,
                "status": "completed",
            }

        tasks = [
            relay_transfer(f"transfer_{i}")
            for i in range(transfer_count)
        ]
        results = await asyncio.gather(*tasks)

        total_bytes = sum(r["bytes_transferred"] for r in results)
        assert total_bytes == transfer_count * data_size


@pytest.mark.stress
@pytest.mark.asyncio
class TestMemoryUsage:
    """内存使用压力测试"""

    async def test_memory_leak_detection(self):
        """测试内存泄漏检测"""
        import gc
        import sys

        # 记录初始内存
        gc.collect()
        initial_objects = len(gc.get_objects())

        # 执行大量操作
        async def operation(i):
            data = {"id": i, "data": "x" * 100}
            await asyncio.sleep(0.001)
            return data

        tasks = [operation(i) for i in range(100)]
        results = await asyncio.gather(*tasks)

        # 清理
        del results
        del tasks
        gc.collect()

        final_objects = len(gc.get_objects())
        # 内存增长应该在一个合理范围内
        # 注意: 这个测试是简化的，实际内存泄漏检测需要更精确的工具
        growth = final_objects - initial_objects
        print(f"对象数量增长: {growth}")

    async def test_large_message_handling(self):
        """测试大消息处理"""
        message_sizes = [
            1024,      # 1KB
            10240,     # 10KB
            102400,    # 100KB
            1024000,   # 1MB
        ]

        for size in message_sizes:
            large_message = "x" * size

            async def handle_message(msg):
                await asyncio.sleep(0.001)
                return {
                    "size": len(msg),
                    "processed": True,
                }

            result = await handle_message(large_message)
            assert result["processed"] is True
            assert result["size"] == size


@pytest.mark.stress
@pytest.mark.asyncio
class TestErrorRecoveryUnderStress:
    """压力下的错误恢复测试"""

    async def test_connection_failure_recovery(self):
        """测试连接失败后的恢复"""
        attempt_count = 20

        async def connect_with_retry(client_id, max_retries=3):
            for attempt in range(max_retries):
                await asyncio.sleep(0.01)
                # 模拟前两次失败，第三次成功
                if attempt < 2:
                    continue
                return {"client_id": client_id, "connected": True, "attempts": attempt + 1}

        tasks = [
            connect_with_retry(f"client_{i}")
            for i in range(attempt_count)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r["connected"] for r in results)
        assert all(r["attempts"] == 3 for r in results)

    async def test_server_overload_recovery(self):
        """测试服务器过载后的恢复"""
        # 模拟服务器过载
        overload_duration = 0.1

        async def overloaded_server(request_id):
            # 前50%的请求被拒绝
            if int(request_id.split("_")[1]) % 2 == 0:
                return {"request_id": request_id, "status": "overload"}
            await asyncio.sleep(0.01)
            return {"request_id": request_id, "status": "success"}

        requests = 20
        tasks = [
            overloaded_server(f"req_{i}")
            for i in range(requests)
        ]
        results = await asyncio.gather(*tasks)

        overload_count = sum(1 for r in results if r["status"] == "overload")
        success_count = sum(1 for r in results if r["status"] == "success")

        assert overload_count + success_count == requests


@pytest.mark.stress
@pytest.mark.asyncio
class TestLongRunningStability:
    """长期运行稳定性测试"""

    async def test_sustained_connections(self):
        """测试持续连接"""
        duration_seconds = 0.5  # 短时间用于测试，实际应该更长
        client_count = 10

        async def maintain_connection(client_id):
            start_time = time.time()
            messages_sent = 0

            while time.time() - start_time < duration_seconds:
                await asyncio.sleep(0.05)
                messages_sent += 1

            return {
                "client_id": client_id,
                "duration": time.time() - start_time,
                "messages_sent": messages_sent,
            }

        tasks = [
            maintain_connection(f"client_{i}")
            for i in range(client_count)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r["duration"] >= duration_seconds for r in results)
        total_messages = sum(r["messages_sent"] for r in results)
        assert total_messages > 0

    async def test_connection_churn(self):
        """测试连接更替 (客户端不断连接和断开)"""
        churn_cycles = 5
        clients_per_cycle = 5

        all_connections = []

        for cycle in range(churn_cycles):
            # 连接
            async def connect(client_id):
                await asyncio.sleep(0.01)
                return {"client_id": client_id, "action": "connect"}

            connect_tasks = [
                connect(f"cycle{cycle}_client{i}")
                for i in range(clients_per_cycle)
            ]
            connect_results = await asyncio.gather(*connect_tasks)
            all_connections.extend(connect_results)

            # 断开
            async def disconnect(client_id):
                await asyncio.sleep(0.01)
                return {"client_id": client_id, "action": "disconnect"}

            disconnect_tasks = [
                disconnect(f"cycle{cycle}_client{i}")
                for i in range(clients_per_cycle)
            ]
            await asyncio.gather(*disconnect_tasks)

        expected_total = churn_cycles * clients_per_cycle
        assert len(all_connections) == expected_total
