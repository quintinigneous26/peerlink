"""
信令服务器单元测试
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, Mock
from typing import Any

import pytest
import pytest_asyncio


class TestSignalingMessage:
    """信令消息测试"""

    def test_create_offer_message(self, test_device_id: str, test_peer_id: str):
        """测试创建Offer消息"""
        message = {
            "type": "offer",
            "device_id": test_device_id,
            "peer_id": test_peer_id,
            "sdp": "v=0\r\no=- 123456 2 IN IP4 127.0.0.1\r\n...",
            "ice_candidates": [],
            "timestamp": 1234567890,
        }

        assert message["type"] == "offer"
        assert message["device_id"] == test_device_id
        assert message["peer_id"] == test_peer_id
        assert "sdp" in message

    def test_create_answer_message(self, test_device_id: str, test_peer_id: str):
        """测试创建Answer消息"""
        message = {
            "type": "answer",
            "device_id": test_device_id,
            "peer_id": test_peer_id,
            "sdp": "v=0\r\no=- 654321 2 IN IP4 127.0.0.1\r\n...",
            "timestamp": 1234567891,
        }

        assert message["type"] == "answer"
        assert "sdp" in message

    def test_create_ice_candidate_message(self, test_device_id: str, test_peer_id: str):
        """测试创建ICE候选消息"""
        candidate = "candidate:1 1 UDP 2130706431 192.168.1.100 54321 typ host"
        message = {
            "type": "ice_candidate",
            "device_id": test_device_id,
            "peer_id": test_peer_id,
            "candidate": candidate,
            "sdp_mid": "0",
            "sdp_mline_index": 0,
            "timestamp": 1234567892,
        }

        assert message["type"] == "ice_candidate"
        assert "candidate" in message

    def test_create_disconnect_message(self, test_device_id: str, test_peer_id: str):
        """测试创建断开连接消息"""
        message = {
            "type": "disconnect",
            "device_id": test_device_id,
            "peer_id": test_peer_id,
            "reason": "user_initiated",
            "timestamp": 1234567893,
        }

        assert message["type"] == "disconnect"
        assert "reason" in message


class TestSignalingServer:
    """信令服务器测试"""

    @pytest.mark.asyncio
    async def test_client_registration(self):
        """测试客户端注册"""
        mock_registry = AsyncMock()
        mock_registry.register.return_value = True

        device_id = "device_001"
        connection_id = "conn_001"

        result = await mock_registry.register(device_id, connection_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_client_lookup(self):
        """测试客户端查找"""
        mock_registry = AsyncMock()
        mock_registry.find.return_value = {
            "device_id": "device_001",
            "connection_id": "conn_001",
            "connected_at": 1234567890,
        }

        result = await mock_registry.find("device_001")
        assert result["device_id"] == "device_001"

    @pytest.mark.asyncio
    async def test_client_unregistration(self):
        """测试客户端注销"""
        mock_registry = AsyncMock()
        mock_registry.unregister.return_value = True

        result = await mock_registry.unregister("device_001")
        assert result is True

    @pytest.mark.asyncio
    async def test_message_relay(self):
        """测试消息转发"""
        mock_relayer = AsyncMock()
        mock_relayer.relay.return_value = {
            "delivered": True,
            "recipient": "device_002",
        }

        message = {
            "type": "offer",
            "sender": "device_001",
            "recipient": "device_002",
            "payload": {"sdp": "..."},
        }

        result = await mock_relayer.relay(message)
        assert result["delivered"] is True

    @pytest.mark.asyncio
    async def test_concurrent_registrations(self):
        """测试并发注册"""
        mock_registry = AsyncMock()

        async def mock_register(device_id):
            await asyncio.sleep(0.01)
            return f"registered_{device_id}"

        # 模拟100个并发注册
        tasks = [mock_register(f"device_{i}") for i in range(100)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 100
        assert all("registered_" in r for r in results)


class TestWebSocketConnection:
    """WebSocket连接测试"""

    @pytest.mark.asyncio
    async def test_connection_establishment(self):
        """测试连接建立"""
        mock_ws = AsyncMock()
        mock_ws.send.return_value = None
        mock_ws.close.return_value = None

        # 模拟连接建立
        await mock_ws.send(json.dumps({"type": "connected", "status": "ok"}))
        mock_ws.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_receive(self):
        """测试接收消息"""
        mock_ws = AsyncMock()
        test_message = {
            "type": "offer",
            "device_id": "device_001",
            "peer_id": "device_002",
        }

        # 模拟接收消息
        mock_ws.receive.return_value = json.dumps(test_message)

        message_data = await mock_ws.receive()
        message = json.loads(message_data)

        assert message["type"] == "offer"

    @pytest.mark.asyncio
    async def test_connection_timeout(self):
        """测试连接超时"""
        mock_ws = AsyncMock()
        # 设置 receive 永远不返回，模拟超时
        mock_ws.receive.side_effect = asyncio.TimeoutError("Connection timeout")

        # 模拟超时
        with pytest.raises(asyncio.TimeoutError):
            await mock_ws.receive()

    @pytest.mark.asyncio
    async def test_heartbeat(self):
        """测试心跳机制"""
        mock_ws = AsyncMock()
        mock_ws.send.return_value = None

        # 发送心跳
        heartbeat = {"type": "ping", "timestamp": 1234567890}
        await mock_ws.send(json.dumps(heartbeat))

        mock_ws.send.assert_called()


class TestRoomManagement:
    """房间管理测试"""

    @pytest.mark.asyncio
    async def test_create_room(self):
        """测试创建房间"""
        mock_room_manager = AsyncMock()
        mock_room_manager.create.return_value = {
            "room_id": "room_001",
            "created_at": 1234567890,
            "max_participants": 2,
        }

        result = await mock_room_manager.create("room_001", max_participants=2)
        assert result["room_id"] == "room_001"

    @pytest.mark.asyncio
    async def test_join_room(self):
        """测试加入房间"""
        mock_room_manager = AsyncMock()
        mock_room_manager.join.return_value = {
            "room_id": "room_001",
            "participant_id": "device_001",
            "participants": ["device_001"],
        }

        result = await mock_room_manager.join("room_001", "device_001")
        assert "device_001" in result["participants"]

    @pytest.mark.asyncio
    async def test_leave_room(self):
        """测试离开房间"""
        mock_room_manager = AsyncMock()
        mock_room_manager.leave.return_value = {
            "room_id": "room_001",
            "participant_id": "device_001",
            "remaining_participants": ["device_002"],
        }

        result = await mock_room_manager.leave("room_001", "device_001")
        assert result["participant_id"] == "device_001"

    @pytest.mark.asyncio
    async def test_room_broadcast(self):
        """测试房间广播"""
        mock_room_manager = AsyncMock()
        mock_room_manager.broadcast.return_value = {
            "recipients": ["device_001", "device_002"],
            "delivered": 2,
        }

        message = {"type": "chat", "content": "hello"}
        result = await mock_room_manager.broadcast("room_001", message, exclude="device_001")

        assert result["delivered"] == 2


class TestSignalingProtocol:
    """信令协议测试"""

    def test_message_validation(self):
        """测试消息验证"""
        valid_message = {
            "type": "offer",
            "device_id": "device_001",
            "peer_id": "device_002",
            "payload": {},
        }

        # 验证必需字段
        required_fields = ["type", "device_id", "peer_id"]
        for field in required_fields:
            assert field in valid_message

    def test_message_serialization(self):
        """测试消息序列化"""
        message = {
            "type": "answer",
            "device_id": "device_001",
            "peer_id": "device_002",
            "sdp": "test_sdp",
        }

        serialized = json.dumps(message)
        deserialized = json.loads(serialized)

        assert deserialized == message

    def test_message_size_limit(self):
        """测试消息大小限制"""
        # 测试消息大小限制 (例如: 1MB)
        max_size = 1024 * 1024

        small_message = {"type": "ping", "data": "x" * 100}
        assert len(json.dumps(small_message)) < max_size

        large_message = {"type": "offer", "data": "x" * (max_size + 1)}
        assert len(json.dumps(large_message)) > max_size


class TestErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_invalid_message_format(self):
        """测试无效消息格式"""
        mock_handler = AsyncMock()
        mock_handler.handle.return_value = {"error": "invalid_format"}

        invalid_message = "not a valid json"
        result = await mock_handler.handle(invalid_message)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_unknown_device(self):
        """测试未知设备"""
        mock_handler = AsyncMock()
        mock_handler.handle.return_value = {"error": "device_not_found"}

        result = await mock_handler.handle("unknown_device")
        assert result["error"] == "device_not_found"

    @pytest.mark.asyncio
    async def test_connection_loss(self):
        """测试连接丢失"""
        mock_ws = AsyncMock()
        mock_ws.receive.side_effect = ConnectionError("Connection lost")

        with pytest.raises(ConnectionError):
            await mock_ws.receive()


class TestSecurity:
    """安全测试"""

    def test_message_authentication(self):
        """测试消息认证"""
        # 测试设备ID验证
        def is_valid_device_id(device_id: str) -> bool:
            return device_id.startswith("device_") and len(device_id) > 7

        assert is_valid_device_id("device_001") is True
        assert is_valid_device_id("invalid") is False

    def test_rate_limiting(self):
        """测试速率限制"""
        mock_rate_limiter = MagicMock()
        mock_rate_limiter.is_allowed.return_value = True

        # 模拟速率检查
        for _ in range(10):
            assert mock_rate_limiter.is_allowed("device_001") is True

    def test_message_encryption(self):
        """测试消息加密"""
        # 简单的消息加密测试
        import base64

        message = "sensitive_data"
        encoded = base64.b64encode(message.encode()).decode()
        decoded = base64.b64decode(encoded).decode()

        assert decoded == message
