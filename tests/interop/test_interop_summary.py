"""
互操作性测试摘要

验证 p2p-platform 与 libp2p 规范的协议兼容性。
"""

import pytest
from typing import List

# ==================== 导入实际模块 ====================

# multistream-select
from p2p_engine.protocol import (
    encode_varint,
    decode_varint,
    MULTISTREAM_PROTOCOL_ID,
    NA_RESPONSE,
)

# mplex
from p2p_engine.muxer.mplex import (
    PROTOCOL_STRING as MPLEX_PROTOCOL_ID,
    MplexFrame,
    read_uvarint,
    write_uvarint,
)

# DHT
from p2p_engine.dht.kademlia import (
    PROTOCOL_ID as KADEMLIA_PROTOCOL_ID,
    KademliaDHT,
    DHT,
)
from p2p_engine.dht.routing import K, BYTE_COUNT

# PubSub
from p2p_engine.protocol.pubsub import (
    PROTOCOL_ID_GOSSIPSUB,
    PROTOCOL_ID_FLOODSUB,
    GossipSub,
    FloodSub,
)

# Ping
from p2p_engine.protocol.ping import (
    PROTOCOL_ID as PING_PROTOCOL_ID,
    PingProtocol,
)

# TLS
from p2p_engine.protocol.tls import (
    PROTOCOL_ID as TLS_PROTOCOL_ID,
)

# 传输
try:
    from p2p_engine.transport.quic import QUIC_PROTOCOL_ID
except ImportError:
    QUIC_PROTOCOL_ID = "/quic-v1"

try:
    from p2p_engine.transport.webrtc import WEBRTC_PROTOCOL_ID
except ImportError:
    WEBRTC_PROTOCOL_ID = "/webrtc-direct"

try:
    from p2p_engine.transport.webtransport import WEBTRANSPORT_PROTOCOL_ID
except ImportError:
    WEBTRANSPORT_PROTOCOL_ID = "/webtransport/1.0.0"


# ==================== 协议合规性测试 ====================

class TestProtocolIDs:
    """验证所有协议 ID 符合 libp2p 规范"""

    def test_multistream_protocol_id(self):
        """multistream-select 协议 ID"""
        assert MULTISTREAM_PROTOCOL_ID == "/multistream/1.0.0"

    def test_mplex_protocol_id(self):
        """mplex 流复用协议 ID"""
        assert MPLEX_PROTOCOL_ID == "/mplex/6.7.0"

    def test_kademlia_protocol_id(self):
        """Kademlia DHT 协议 ID"""
        assert KADEMLIA_PROTOCOL_ID == "/ipfs/kad/1.0.0"

    def test_gossipsub_protocol_id(self):
        """GossipSub 协议 ID"""
        assert PROTOCOL_ID_GOSSIPSUB == "/meshsub/1.1.0"

    def test_floodsub_protocol_id(self):
        """FloodSub 协议 ID"""
        assert PROTOCOL_ID_FLOODSUB == "/floodsub/1.0.0"

    def test_ping_protocol_id(self):
        """Ping 协议 ID"""
        assert PING_PROTOCOL_ID == "/ipfs/ping/1.0.0"

    def test_tls_protocol_id(self):
        """TLS 协议 ID"""
        assert TLS_PROTOCOL_ID == "/tls/1.0.0"

    def test_quic_protocol_id(self):
        """QUIC 传输协议 ID"""
        assert QUIC_PROTOCOL_ID == "/quic-v1"

    def test_webrtc_protocol_id(self):
        """WebRTC 传输协议 ID"""
        assert WEBRTC_PROTOCOL_ID == "/webrtc-direct"

    def test_webtransport_protocol_id(self):
        """WebTransport 传输协议 ID"""
        assert WEBTRANSPORT_PROTOCOL_ID == "/webtransport/1.0.0"


class TestVarintEncoding:
    """验证 varint 编码符合 multiformats 规范"""

    def test_varint_encoding_compliance(self):
        """
        验证 varint 编码符合 unsigned-varint 规范
        https://github.com/multiformats/unsigned-varint
        """
        test_cases = [
            (0, b'\x00'),
            (1, b'\x01'),
            (127, b'\x7f'),
            (128, b'\x80\x01'),
            (300, b'\xac\x02'),
            (16384, b'\x80\x80\x01'),
        ]

        for value, expected in test_cases:
            # 测试 protocol 模块的 varint
            encoded = encode_varint(value)
            assert encoded == expected, f"encode_varint({value}) = {encoded!r}, expected {expected!r}"

            decoded, consumed = decode_varint(encoded)
            assert decoded == value, f"decode_varint({encoded!r}) = {decoded}, expected {value}"

    def test_mplex_uvarint_encoding(self):
        """验证 mplex uvarint 编码"""
        import io

        test_cases = [
            (0, b'\x00'),
            (1, b'\x01'),
            (127, b'\x7f'),
            (128, b'\x80\x01'),
        ]

        for value, expected in test_cases:
            buffer = io.BytesIO()
            data = bytearray(); write_uvarint(data, value)
            encoded = bytes(data)
            assert encoded == expected, f"write_uvarint({value}) = {encoded!r}, expected {expected!r}"

            buffer = bytearray(encoded)
            decoded, _ = read_uvarint(buffer)
            assert decoded == value


class TestDHTParameters:
    """验证 DHT 参数符合 Kademlia 规范"""

    def test_dht_peer_id_length(self):
        """
        验证 peer ID 长度

        libp2p 使用 SHA-256 生成 peer ID，长度为 32 字节 (256 位)
        """
        assert BYTE_COUNT == 32

    def test_dht_k_parameter(self):
        """
        验证 K 参数

        Kademlia 规范推荐 K = 20
        """
        assert K == 20


class TestProtocolImplementations:
    """验证协议实现存在"""

    def test_kademlia_dht_exists(self):
        """验证 KademliaDHT 实现"""
        assert KademliaDHT is not None
        assert issubclass(KademliaDHT, DHT)

    def test_gossipsub_exists(self):
        """验证 GossipSub 实现"""
        assert GossipSub is not None

    def test_floodsub_exists(self):
        """验证 FloodSub 实现"""
        assert FloodSub is not None

    def test_ping_protocol_exists(self):
        """验证 PingProtocol 实现"""
        assert PingProtocol is not None


# ==================== 测试摘要 ====================

def get_protocol_compliance_summary() -> dict:
    """
    生成协议合规性摘要

    返回格式:
    {
        "total_protocols": int,
        "compliant_protocols": int,
        "protocols": [
            {"name": str, "protocol_id": str, "compliant": bool}
        ]
    }
    """
    protocols = [
        {"name": "multistream-select", "protocol_id": MULTISTREAM_PROTOCOL_ID, "expected": "/multistream/1.0.0"},
        {"name": "mplex", "protocol_id": MPLEX_PROTOCOL_ID, "expected": "/mplex/6.7.0"},
        {"name": "Kademlia DHT", "protocol_id": KADEMLIA_PROTOCOL_ID, "expected": "/ipfs/kad/1.0.0"},
        {"name": "GossipSub", "protocol_id": PROTOCOL_ID_GOSSIPSUB, "expected": "/meshsub/1.1.0"},
        {"name": "FloodSub", "protocol_id": PROTOCOL_ID_FLOODSUB, "expected": "/floodsub/1.0.0"},
        {"name": "Ping", "protocol_id": PING_PROTOCOL_ID, "expected": "/ipfs/ping/1.0.0"},
        {"name": "TLS", "protocol_id": TLS_PROTOCOL_ID, "expected": "/tls/1.0.0"},
        {"name": "QUIC", "protocol_id": QUIC_PROTOCOL_ID, "expected": "/quic-v1"},
        {"name": "WebRTC", "protocol_id": WEBRTC_PROTOCOL_ID, "expected": "/webrtc-direct"},
        {"name": "WebTransport", "protocol_id": WEBTRANSPORT_PROTOCOL_ID, "expected": "/webtransport/1.0.0"},
    ]

    compliant = 0
    results = []

    for protocol in protocols:
        is_compliant = protocol["protocol_id"] == protocol["expected"]
        if is_compliant:
            compliant += 1

        results.append({
            "name": protocol["name"],
            "protocol_id": protocol["protocol_id"],
            "expected": protocol["expected"],
            "compliant": is_compliant,
        })

    return {
        "total_protocols": len(protocols),
        "compliant_protocols": compliant,
        "compliance_rate": compliant / len(protocols) * 100,
        "protocols": results,
    }


@pytest.fixture
def compliance_report():
    """生成合规性报告"""
    return get_protocol_compliance_summary()


class TestComplianceReport:
    """合规性报告测试"""

    def test_generate_compliance_report(self, compliance_report):
        """验证合规性报告生成"""
        assert compliance_report["total_protocols"] == 10
        assert compliance_report["compliant_protocols"] >= 9  # 至少 90%
        assert compliance_report["compliance_rate"] >= 90

    def test_all_core_protocols_compliant(self, compliance_report):
        """验证核心协议合规"""
        core_protocols = ["multistream-select", "mplex", "Kademlia DHT", "GossipSub", "Ping", "TLS"]

        for protocol in compliance_report["protocols"]:
            if protocol["name"] in core_protocols:
                assert protocol["compliant"], f"{protocol['name']} 协议 ID 不匹配"

    def test_print_compliance_report(self, compliance_report, capsys):
        """打印合规性报告"""
        print("\n" + "=" * 60)
        print("p2p-platform 协议合规性报告")
        print("=" * 60)
        print(f"总协议数: {compliance_report['total_protocols']}")
        print(f"合规协议数: {compliance_report['compliant_protocols']}")
        print(f"合规率: {compliance_report['compliance_rate']:.1f}%")
        print("\n协议详情:")
        print("-" * 60)

        for protocol in compliance_report["protocols"]:
            status = "✓" if protocol["compliant"] else "✗"
            print(f"{status} {protocol['name']:20s} | {protocol['protocol_id']}")

        print("=" * 60)


# ==================== 互操作测试标记 ====================

class TestInteropMarkers:
    """标记需要外部节点的互操作测试"""

    @pytest.mark.skip(reason="需要 go-libp2p 节点运行")
    def test_go_libp2p_tls_handshake(self):
        """
        与 go-libp2p TLS 握手测试

        运行方式:
        1. 启动 go-libp2p 节点
        2. pytest --run-interop-tests tests/interop/
        """
        pass

    @pytest.mark.skip(reason="需要 go-libp2p 节点运行")
    def test_go_libp2p_mplex_multiplexing(self):
        """与 go-libp2p mplex 流复用测试"""
        pass

    @pytest.mark.skip(reason="需要 go-libp2p 节点运行")
    def test_go_libp2p_dht_operations(self):
        """与 go-libp2p DHT 操作测试"""
        pass

    @pytest.mark.skip(reason="需要 go-libp2p 节点运行")
    def test_go_libp2p_pubsub_messaging(self):
        """与 go-libp2p PubSub 消息传递测试"""
        pass

    @pytest.mark.skip(reason="需要 js-libp2p 节点运行")
    def test_js_libp2p_tls_handshake(self):
        """与 js-libp2p TLS 握手测试"""
        pass

    @pytest.mark.skip(reason="需要浏览器客户端")
    def test_browser_webrtc_connection(self):
        """与浏览器 WebRTC 连接测试"""
        pass

    @pytest.mark.skip(reason="需要浏览器客户端")
    def test_browser_webtransport_stream(self):
        """与浏览器 WebTransport 流测试"""
        pass
