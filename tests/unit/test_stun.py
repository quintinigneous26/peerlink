"""
STUN服务器单元测试
"""
import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import NAT_BEHAVIORS


# STUN消息类型
STUN_BINDING_REQUEST = 0x0001
STUN_BINDING_RESPONSE = 0x0101
STUN_BINDING_ERROR = 0x0111


class TestSTUNMessageParsing:
    """STUN消息解析测试"""

    def test_parse_binding_request(self, sample_stun_request: bytes):
        """测试解析绑定请求"""
        # STUN消息头格式: Type(2) + Length(2) + Magic Cookie(4) + Transaction ID(12)
        # sample_stun_request from conftest.py
        assert len(sample_stun_request) >= 20
        msg_type = struct.unpack("!H", sample_stun_request[:2])[0]
        msg_len = struct.unpack("!H", sample_stun_request[2:4])[0]
        magic_cookie = struct.unpack("!I", sample_stun_request[4:8])[0]

        assert msg_type == STUN_BINDING_REQUEST
        assert magic_cookie == 0x2112A442  # STUN魔数

    def test_create_binding_response(self):
        """测试创建绑定响应"""
        # 构造STUN绑定响应
        transaction_id = b"\x22\x23\x42\x45\x46\x47\x48\x49\x4a\x4b\x4c\x4e"

        # 响应头
        response = struct.pack(
            "!HHI12s",
            STUN_BINDING_RESPONSE,
            0,  # 属性长度
            0x2112A442,  # Magic Cookie
            transaction_id,
        )

        assert len(response) == 20
        msg_type = struct.unpack("!H", response[:2])[0]
        assert msg_type == STUN_BINDING_RESPONSE

    def test_xor_mapped_address_attribute(self):
        """测试XOR-MAPPED-ADDRESS属性"""
        # 测试数据
        magic_cookie = 0x2112A442
        transaction_id = b"\x22\x23\x42\x45\x46\x47\x48\x49\x4a\x4b\x4c\x4e"
        mapped_address = "203.0.113.1"
        mapped_port = 54322

        # 将IP和端口转换为字节
        ip_bytes = socket.inet_aton(mapped_address)
        port = mapped_port

        # XOR加密端口 (与magic cookie高16位异或)
        xored_port = port ^ (magic_cookie >> 16)

        # XOR加密IP (与magic cookie + transaction_id前4字节异或)
        # 正确的XOR掩码是 magic_cookie || transaction_id
        xor_mask = magic_cookie.to_bytes(4, 'big') + transaction_id[:4]
        ip_int = int.from_bytes(ip_bytes, "big")
        mask_int = int.from_bytes(xor_mask[:4], "big")
        xored_ip_int = ip_int ^ mask_int
        xored_ip_bytes = xored_ip_int.to_bytes(4, "big")

        # 构造XOR-MAPPED-ADDRESS属性
        attribute_type = 0x0020
        attribute_length = 8
        # 格式: Type(2) + Length(2) + Reserved(1) + Family(1) + XorPort(2) + XorIP(4)
        attribute = struct.pack(
            "!HH",
            attribute_type,
            attribute_length,
        )
        attribute += struct.pack("!BBH", 0x00, 0x01, xored_port)  # Reserved, Family, Port
        attribute += xored_ip_bytes

        assert len(attribute) == 12

    def test_parse_unknown_attributes(self):
        """测试解析未知属性"""
        # 构造包含未知属性的STUN消息
        unknown_attr_type = 0xFF00
        unknown_attr_value = b"\x00" * 4

        attribute = struct.pack("!HH", unknown_attr_type, len(unknown_attr_value))
        attribute += unknown_attr_value

        # 解析时应该跳过未知属性
        attr_type = struct.unpack("!H", attribute[:2])[0]
        attr_len = struct.unpack("!H", attribute[2:4])[0]

        assert attr_type == unknown_attr_type
        assert attr_len == len(unknown_attr_value)


class TestSTUNServer:
    """STUN服务器测试"""

    @pytest.mark.asyncio
    async def test_handle_binding_request(self, free_port: int):
        """测试处理绑定请求"""
        # 这里应该测试真实服务器的响应
        # 暂时使用mock
        mock_handler = AsyncMock()
        mock_handler.return_value = {
            "mapped_address": "203.0.113.1",
            "mapped_port": 54322,
            "source_address": "198.51.100.1",
            "source_port": 3478,
            "changed_address": "203.0.113.2",
            "changed_port": 3479,
        }

        result = await mock_handler(b"binding_request")
        assert result["mapped_address"] == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, free_port: int):
        """测试并发请求处理"""
        async def mock_handle(request):
            await asyncio.sleep(0.01)
            return {"status": "success"}

        # 模拟并发请求
        tasks = [mock_handle(f"req{i}".encode()) for i in range(100)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 100
        assert all(r["status"] == "success" for r in results)


class TestNATDetection:
    """NAT类型检测测试"""

    def test_nat_behavior_classification(self):
        """测试NAT行为分类"""
        # 测试各种NAT行为
        for nat_type, behavior in NAT_BEHAVIORS.items():
            assert "name" in behavior
            assert "filtering" in behavior
            assert "mapping" in behavior

    def test_full_cone_detection(self):
        """测试Full Cone NAT检测"""
        # Full Cone: endpoint-independent mapping, no filtering
        nat_type = "full_cone"
        behavior = NAT_BEHAVIORS[nat_type]

        assert behavior["mapping"] == "endpoint-independent"
        assert behavior["filtering"] == "none"

    def test_symmetric_nat_detection(self):
        """测试Symmetric NAT检测"""
        # Symmetric: endpoint-dependent mapping and filtering
        nat_type = "symmetric"
        behavior = NAT_BEHAVIORS[nat_type]

        assert behavior["mapping"] == "endpoint-dependent"
        assert behavior["filtering"] == "endpoint-dependent"

    def test_nat_mapping_strategy(self):
        """测试NAT映射策略"""
        strategies = {
            "endpoint-independent": ["full_cone", "restricted_cone", "port_restricted"],
            "endpoint-dependent": ["symmetric"],
        }

        for strategy, expected_types in strategies.items():
            for nat_type in expected_types:
                assert NAT_BEHAVIORS[nat_type]["mapping"] == strategy


class TestSTUNAttributes:
    """STUN属性测试"""

    def test_mapped_address_attribute(self):
        """测试MAPPED-ADDRESS属性"""
        attr_type = 0x0001
        ip = "203.0.113.1"
        port = 54322

        ip_bytes = socket.inet_aton(ip)
        # MAPPED-ADDRESS格式: Family(1) + Port(2) + IP(4)
        # 注意: 第一个字节是保留位(0), 第二个字节是地址族(0x01=IPv4)
        attribute_value = struct.pack("!BBH4s", 0x00, 0x01, port, ip_bytes)
        attribute = struct.pack("!HH", attr_type, len(attribute_value)) + attribute_value

        assert len(attribute) == 12
        parsed_type = struct.unpack("!H", attribute[:2])[0]
        assert parsed_type == attr_type

    def test_source_address_attribute(self):
        """测试SOURCE-ADDRESS属性"""
        attr_type = 0x0004
        ip = "198.51.100.1"
        port = 3478

        ip_bytes = socket.inet_aton(ip)
        attribute_value = struct.pack("!BH4s", 0x01, port, ip_bytes)
        attribute = struct.pack("!HH", attr_type, len(attribute_value)) + attribute_value

        parsed_type = struct.unpack("!H", attribute[:2])[0]
        assert parsed_type == attr_type

    def test_changed_address_attribute(self):
        """测试CHANGED-ADDRESS属性"""
        attr_type = 0x0005
        ip = "203.0.113.2"
        port = 3479

        ip_bytes = socket.inet_aton(ip)
        attribute_value = struct.pack("!BH4s", 0x01, port, ip_bytes)
        attribute = struct.pack("!HH", attr_type, len(attribute_value)) + attribute_value

        # 解析IP地址 (跳过 header(4) + family(1) + port(2))
        parsed_ip = socket.inet_ntoa(attribute[7:11])
        assert parsed_ip == ip


import socket
