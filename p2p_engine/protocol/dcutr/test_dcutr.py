"""
DCUtR Protocol Tests
"""
import asyncio
import logging
from unittest.mock import Mock, MagicMock
import pytest

from ...types import NATInfo, NATType, ISP, ConnectionType
from ..dcutr import (
    DCUtRProtocol,
    DCUtRMessage,
    DCUtRMessageType,
    DCUtRResult,
    PROTOCOL_ID,
)


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestDCUtRMessage:
    """Test DCUtR message encoding/decoding"""

    def test_connect_message_encode(self):
        """Test encoding a CONNECT message"""
        msg = DCUtRMessage(
            message_type=DCUtRMessageType.CONNECT,
            obs_addrs=[b"/ip4/127.0.0.1/tcp/1234"],
        )
        data = msg.encode()
        assert data is not None
        assert len(data) > 0

    def test_connect_message_decode(self):
        """Test decoding a CONNECT message"""
        # Create and encode a message
        original = DCUtRMessage(
            message_type=DCUtRMessageType.CONNECT,
            obs_addrs=[b"/ip4/127.0.0.1/tcp/1234", b"/ip4/127.0.0.1/tcp/5678"],
        )
        data = original.encode()

        # Skip the varint length prefix
        length, offset = DCUtRMessage.decode_varint(data)
        msg_data = data[offset:offset + length]

        # Decode
        decoded = DCUtRMessage.decode(msg_data)

        assert decoded.message_type == DCUtRMessageType.CONNECT
        assert len(decoded.obs_addrs) == 2
        assert decoded.obs_addrs[0] == b"/ip4/127.0.0.1/tcp/1234"
        assert decoded.obs_addrs[1] == b"/ip4/127.0.0.1/tcp/5678"

    def test_sync_message_encode(self):
        """Test encoding a SYNC message"""
        msg = DCUtRMessage(
            message_type=DCUtRMessageType.SYNC,
            obs_addrs=[],
        )
        data = msg.encode()
        assert data is not None

    def test_varint_encode_decode(self):
        """Test varint encoding/decoding"""
        test_values = [0, 1, 127, 128, 300, 16384, 1000000]

        for value in test_values:
            encoded = DCUtRMessage._encode_varint(value)
            decoded, _ = DCUtRMessage.decode_varint(encoded)
            assert decoded == value, f"Failed for {value}: got {decoded}"


class TestDCUtRProtocol:
    """Test DCUtR protocol"""

    @pytest.fixture
    def local_nat(self):
        """Create a test NAT info"""
        return NATInfo(
            type=NATType.PORT_RESTRICTED,
            public_ip="192.168.1.100",
            public_port=12345,
            local_ip="10.0.0.1",
            local_port=54321,
        )

    @pytest.fixture
    def protocol(self, local_nat):
        """Create a DCUtR protocol instance"""
        return DCUtRProtocol(
            local_peer_id="QmPeer1",
            local_nat=local_nat,
            local_isp=ISP.CHINA_TELECOM,
        )

    def test_protocol_init(self, protocol):
        """Test protocol initialization"""
        assert protocol.local_peer_id == "QmPeer1"
        assert protocol.PROTOCOL_ID == "/libp2p/dcutr/1.0.0" if hasattr(protocol, 'PROTOCOL_ID') else True

    def test_parse_multiaddr_tcp(self):
        """Test parsing TCP multiaddr"""
        result = DCUtRProtocol._parse_multiaddr("/ip4/127.0.0.1/tcp/1234")
        assert result is not None
        proto, ip, port = result
        assert proto == "tcp"
        assert ip == "127.0.0.1"
        assert port == 1234

    def test_parse_multiaddr_quic(self):
        """Test parsing QUIC multiaddr"""
        result = DCUtRProtocol._parse_multiaddr("/ip4/127.0.0.1/udp/5678/quic")
        assert result is not None
        proto, ip, port = result
        assert proto == "quic"
        assert ip == "127.0.0.1"
        assert port == 5678

    def test_parse_multiaddr_invalid(self):
        """Test parsing invalid multiaddr"""
        result = DCUtRProtocol._parse_multiaddr("invalid")
        assert result is None

    def test_parse_multiaddr_ipv6(self):
        """Test parsing IPv6 multiaddr"""
        result = DCUtRProtocol._parse_multiaddr("/ip6/::1/tcp/1234")
        assert result is not None
        proto, ip, port = result
        assert proto == "tcp"
        assert ip == "::1"
        assert port == 1234


@pytest.mark.asyncio
class TestDCUtRProtocolAsync:
    """Test DCUtR protocol async operations"""

    @pytest.fixture
    def mock_stream_pair(self):
        """Create a mock stream pair"""
        reader = asyncio.StreamReader()
        writer = Mock()
        writer.write = Mock()
        writer.drain = asyncio.coroutine(lambda: None)
        writer.close = Mock()
        return reader, writer

    @pytest.fixture
    def protocol(self):
        """Create a protocol instance"""
        local_nat = NATInfo(
            type=NATType.PORT_RESTRICTED,
            public_ip="192.168.1.100",
            public_port=12345,
        )
        return DCUtRProtocol(
            local_peer_id="QmPeer1",
            local_nat=local_nat,
            local_isp=ISP.CHINA_TELECOM,
        )

    async def test_close(self, protocol):
        """Test closing the protocol"""
        # Should not raise
        protocol.close()

    async def test_close_with_connections(self, protocol):
        """Test closing with active connections"""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        protocol._active_connections.append(sock)
        protocol.close()
        assert len(protocol._active_connections) == 0


def test_protocol_id():
    """Test protocol ID constant"""
    assert PROTOCOL_ID == "/libp2p/dcutr/1.0.0"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
