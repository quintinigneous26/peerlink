"""
Unit tests for Identify protocol implementation.

Tests cover:
- Message serialization/deserialization
- Extension data handling
- Protocol exchange (query mode)
- Protocol push
- libp2p compatibility
"""
import asyncio
import json
import pytest
from p2p_engine.protocol.identify import (
    IdentifyMessage,
    IdentifyExtension,
    IdentifyProtocol,
    ConnectionWrapper,
    PROTOCOL_ID,
    PROTOCOL_PUSH_ID,
)
from p2p_engine.types import ISP, NATType, DeviceVendor, Region


class TestIdentifyExtension:
    """Tests for IdentifyExtension data class."""

    def test_to_dict_default(self):
        """Test default extension converts to dict correctly."""
        ext = IdentifyExtension()
        result = ext.to_dict()

        assert result["isp"] == "unknown"
        assert result["nat_type"] == "unknown"
        assert result["device_vendor"] == "unknown"
        assert result["nat_level"] == 1
        assert result["is_cgnat"] is False
        assert result["ipv6_available"] is False
        assert result["region"] == "overseas"

    def test_to_dict_with_values(self):
        """Test extension with values converts to dict correctly."""
        ext = IdentifyExtension(
            isp=ISP.CHINA_TELECOM,
            nat_type=NATType.SYMMETRIC,
            device_vendor=DeviceVendor.HUAWEI,
            nat_level=2,
            is_cgnat=True,
            ipv6_available=True,
            region=Region.MAINLAND,
        )
        result = ext.to_dict()

        assert result["isp"] == "china_telecom"
        assert result["nat_type"] == "symmetric"
        assert result["device_vendor"] == "huawei"
        assert result["nat_level"] == 2
        assert result["is_cgnat"] is True
        assert result["ipv6_available"] is True
        assert result["region"] == "mainland"

    def test_from_dict(self):
        """Test creating extension from dict."""
        data = {
            "isp": "china_mobile",
            "nat_type": "full_cone",
            "device_vendor": "zte",
            "nat_level": 1,
            "is_cgnat": False,
            "ipv6_available": False,
            "region": "hongkong",
        }
        ext = IdentifyExtension.from_dict(data)

        assert ext.isp == ISP.CHINA_MOBILE
        assert ext.nat_type == NATType.FULL_CONE
        assert ext.device_vendor == DeviceVendor.ZTE
        assert ext.nat_level == 1
        assert ext.is_cgnat is False
        assert ext.ipv6_available is False
        assert ext.region == Region.HONGKONG

    def test_from_dict_missing_fields(self):
        """Test extension from dict with missing fields uses defaults."""
        data = {"isp": "att"}
        ext = IdentifyExtension.from_dict(data)

        assert ext.isp == ISP.ATT
        assert ext.nat_type == NATType.UNKNOWN
        assert ext.device_vendor == DeviceVendor.UNKNOWN
        assert ext.nat_level == 1
        assert ext.is_cgnat is False

    def test_serialize_deserialize_roundtrip(self):
        """Test extension bytes roundtrip."""
        original = IdentifyExtension(
            isp=ISP.SINGTEL,
            nat_type=NATType.PORT_RESTRICTED,
            device_vendor=DeviceVendor.CISCO,
        )

        bytes_data = original.to_bytes()
        restored = IdentifyExtension.from_bytes(bytes_data)

        assert restored.isp == original.isp
        assert restored.nat_type == original.nat_type
        assert restored.device_vendor == original.device_vendor

    def test_from_bytes_empty(self):
        """Test extension from empty bytes returns default."""
        ext = IdentifyExtension.from_bytes(b"")
        assert ext.isp == ISP.UNKNOWN
        assert ext.nat_type == NATType.UNKNOWN

    def test_from_bytes_invalid(self):
        """Test extension from invalid bytes returns default."""
        ext = IdentifyExtension.from_bytes(b"invalid json")
        assert ext.isp == ISP.UNKNOWN


class TestIdentifyMessage:
    """Tests for IdentifyMessage data class."""

    def test_default_message(self):
        """Test default message values."""
        msg = IdentifyMessage()

        assert msg.protocol_version == "/ipfs/0.1.0"
        assert msg.agent_version == "p2p-platform/2.0.0"
        assert msg.public_key == b""
        assert msg.listen_addrs == []
        assert msg.observed_addr == b""
        assert msg.protocols == []
        assert isinstance(msg.ext, IdentifyExtension)

    def test_to_protobuf_dict_empty(self):
        """Test converting empty message to protobuf dict."""
        msg = IdentifyMessage()
        result = msg.to_protobuf_dict()

        # Should have agent and protocol version
        assert "protocolVersion" in result
        assert "agentVersion" in result
        # Extension should be present but empty
        assert "ext" in result

    def test_to_protobuf_dict_with_values(self):
        """Test converting message with values to protobuf dict."""
        msg = IdentifyMessage(
            protocol_version="/ipfs/0.2.0",
            agent_version="test/1.0.0",
            public_key=b"public_key_bytes",
            listen_addrs=[b"/ip4/127.0.0.1/tcp/0"],
            observed_addr=b"/ip4/1.2.3.4/tcp/5678",
            protocols=["/ipfs/id/1.0.0", "/mplex/6.7.0"],
            ext=IdentifyExtension(isp=ISP.CHINA_UNICOM),
        )
        result = msg.to_protobuf_dict()

        assert result["protocolVersion"] == "/ipfs/0.2.0"
        assert result["agentVersion"] == "test/1.0.0"
        assert result["publicKey"] == b"public_key_bytes"
        assert result["listenAddrs"] == [b"/ip4/127.0.0.1/tcp/0"]
        assert result["observedAddr"] == b"/ip4/1.2.3.4/tcp/5678"
        assert result["protocols"] == ["/ipfs/id/1.0.0", "/mplex/6.7.0"]
        assert "ext" in result

    def test_from_protobuf_dict(self):
        """Test creating message from protobuf dict."""
        data = {
            "protocolVersion": "/test/1.0.0",
            "agentVersion": "agent/2.0",
            "publicKey": b"key",
            "listenAddrs": [b"addr1", b"addr2"],
            "observedAddr": b"obs",
            "protocols": ["/p1", "/p2"],
        }
        msg = IdentifyMessage.from_protobuf_dict(data)

        assert msg.protocol_version == "/test/1.0.0"
        assert msg.agent_version == "agent/2.0"
        assert msg.public_key == b"key"
        assert msg.listen_addrs == [b"addr1", b"addr2"]
        assert msg.observed_addr == b"obs"
        assert msg.protocols == ["/p1", "/p2"]

    def test_from_protobuf_dict_with_extension(self):
        """Test creating message with extension from protobuf dict."""
        ext = IdentifyExtension(isp=ISP.HKBN, nat_type=NATType.FULL_CONE)
        data = {
            "protocolVersion": "/ipfs/0.1.0",
            "ext": ext.to_bytes(),
        }
        msg = IdentifyMessage.from_protobuf_dict(data)

        assert msg.ext.isp == ISP.HKBN
        assert msg.ext.nat_type == NATType.FULL_CONE


class TestIdentifyProtocol:
    """Tests for IdentifyProtocol handler."""

    def test_default_initialization(self):
        """Test protocol with default values."""
        proto = IdentifyProtocol()

        assert proto.protocol_version == "/ipfs/0.1.0"
        assert proto.agent_version == "p2p-platform/2.0.0"

    def test_custom_initialization(self):
        """Test protocol with custom values."""
        proto = IdentifyProtocol(
            protocol_version="/custom/1.0.0",
            agent_version="custom-agent/3.0",
        )

        assert proto.protocol_version == "/custom/1.0.0"
        assert proto.agent_version == "custom-agent/3.0"

    def test_create_local_info(self):
        """Test creating local Identify message."""
        proto = IdentifyProtocol()
        ext = IdentifyExtension(isp=ISP.CHINA_TELECOM)

        msg = proto.create_local_info(
            public_key=b"public_key",
            listen_addrs=[b"/ip4/0.0.0.0/tcp/0"],
            protocols=["/custom/protocol"],
            extension=ext,
        )

        assert msg.protocol_version == "/ipfs/0.1.0"
        assert msg.agent_version == "p2p-platform/2.0.0"
        assert msg.public_key == b"public_key"
        assert msg.listen_addrs == [b"/ip4/0.0.0.0/tcp/0"]
        assert msg.protocols == ["/custom/protocol"]
        assert msg.ext.isp == ISP.CHINA_TELECOM

    def test_update_protocols(self):
        """Test updating supported protocols list."""
        proto = IdentifyProtocol()
        new_protocols = ["/p1", "/p2", "/p3"]

        proto.update_protocols(new_protocols)

        assert proto._supported_protocols == new_protocols


class MockConnection:
    """Mock connection for testing."""

    def __init__(self):
        self.sent_data = []
        self.recv_queue = asyncio.Queue()
        self._closed = False

    async def send(self, data: bytes):
        """Mock send."""
        if self._closed:
            raise RuntimeError("Connection closed")
        self.sent_data.append(data)

    async def recv(self):
        """Mock recv."""
        if self._closed:
            raise RuntimeError("Connection closed")
        return await self.recv_queue.get()

    async def close(self):
        """Mock close."""
        self._closed = True

    def feed_recv(self, data: bytes):
        """Add data to receive queue."""
        self.recv_queue.put_nowait(data)


@pytest.mark.asyncio
class TestIdentifyProtocolAsync:
    """Async tests for IdentifyProtocol."""

    async def test_exchange_success(self):
        """Test successful Identify exchange."""
        proto = IdentifyProtocol()
        mock_conn = MockConnection()

        # Prepare remote response - use to_json_dict() for JSON serialization
        remote_msg = IdentifyMessage(
            agent_version="remote/1.0.0",
            protocols=["/p1", "/p2"],
        )
        response_data = json.dumps(remote_msg.to_json_dict()).encode()
        mock_conn.feed_recv(response_data)

        # Perform exchange
        result = await proto.exchange(mock_conn)

        assert result.agent_version == "remote/1.0.0"
        assert result.protocols == ["/p1", "/p2"]

    async def test_exchange_with_local_info(self):
        """Test exchange with local info sent."""
        proto = IdentifyProtocol()
        mock_conn = MockConnection()

        local_info = IdentifyMessage(agent_version="local/1.0.0")
        remote_msg = IdentifyMessage(agent_version="remote/1.0.0")
        # Use to_json_dict() for JSON serialization
        response_data = json.dumps(remote_msg.to_json_dict()).encode()
        mock_conn.feed_recv(response_data)

        result = await proto.exchange(mock_conn, local_info)

        # Check local info was sent
        assert len(mock_conn.sent_data) == 1
        assert result.agent_version == "remote/1.0.0"

    async def test_push_success(self):
        """Test successful Identify push."""
        proto = IdentifyProtocol()
        mock_conn = MockConnection()

        push_info = IdentifyMessage(
            agent_version="updated/2.0.0",
            protocols=["/new"],
        )

        await proto.push(mock_conn, push_info)

        assert len(mock_conn.sent_data) == 1

    async def test_handle_query(self):
        """Test handling incoming Identify query."""
        proto = IdentifyProtocol()
        mock_conn = MockConnection()

        local_info = IdentifyMessage(
            agent_version="server/1.0.0",
            protocols=["/server/protocol"],
        )

        # Simulate empty query
        mock_conn.feed_recv(b"")

        await proto.handle_query(mock_conn, local_info)

        # Check response was sent
        assert len(mock_conn.sent_data) == 1
        sent_json = json.loads(mock_conn.sent_data[0].decode())
        assert sent_json["agentVersion"] == "server/1.0.0"

    async def test_exchange_timeout(self):
        """Test exchange timeout handling."""
        proto = IdentifyProtocol()
        mock_conn = MockConnection()

        # Don't feed any data - will timeout
        with pytest.raises(RuntimeError, match="timeout"):
            # Use a very short timeout for testing
            async def _exchange_with_timeout():
                try:
                    return await asyncio.wait_for(proto.exchange(mock_conn), timeout=0.01)
                except asyncio.TimeoutError:
                    raise RuntimeError("timeout")

            await _exchange_with_timeout()


class TestLibp2pCompatibility:
    """Tests for libp2p compatibility."""

    def test_protocol_ids_match_spec(self):
        """Test protocol IDs match libp2p spec."""
        assert PROTOCOL_ID == "/ipfs/id/1.0.0"
        assert PROTOCOL_PUSH_ID == "/ipfs/id/push/1.0.0"

    def test_message_fields_match_spec(self):
        """Test message structure matches libp2p spec."""
        msg = IdentifyMessage()

        # Check all spec fields are present
        assert hasattr(msg, "protocol_version")
        assert hasattr(msg, "agent_version")
        assert hasattr(msg, "public_key")
        assert hasattr(msg, "listen_addrs")
        assert hasattr(msg, "observed_addr")
        assert hasattr(msg, "protocols")

    def test_extension_doesnt_break_core_fields(self):
        """Test extension field doesn't interfere with core fields."""
        msg = IdentifyMessage(
            protocol_version="/ipfs/0.1.0",
            agent_version="test/1.0",
            public_key=b"key",
            listen_addrs=[b"addr"],
            observed_addr=b"obs",
            protocols=["/p1"],
            ext=IdentifyExtension(isp=ISP.CHINA_TELECOM),
        )

        result = msg.to_protobuf_dict()

        # All core fields should be present
        assert result["protocolVersion"] == "/ipfs/0.1.0"
        assert result["agentVersion"] == "test/1.0"
        assert result["publicKey"] == b"key"
        assert result["listenAddrs"] == [b"addr"]
        assert result["observedAddr"] == b"obs"
        assert result["protocols"] == ["/p1"]
        # Extension is separate
        assert "ext" in result

    def test_empty_extension_backward_compat(self):
        """Test messages with empty extension are backward compatible."""
        msg = IdentifyMessage(
            protocol_version="/ipfs/0.1.0",
            agent_version="test/1.0",
        )

        result = msg.to_protobuf_dict()

        # Empty extension shouldn't break parsing
        assert "ext" in result
        parsed = IdentifyMessage.from_protobuf_dict(result)
        assert parsed.protocol_version == "/ipfs/0.1.0"
        assert parsed.agent_version == "test/1.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
