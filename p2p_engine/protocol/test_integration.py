"""
Integration tests for protocol negotiation and Identify protocol.

Tests the complete flow from multistream-select negotiation to
Identify protocol execution.
"""
import asyncio
import pytest

from p2p_engine.protocol import (
    IdentifyProtocol,
    IdentifyMessage,
    IdentifyExtension,
    IdentifyClient,
    PROTOCOL_ID,
    PROTOCOL_PUSH_ID,
    IdentifyHandler,
    create_default_registry,
    create_identify_client,
    ProtocolRegistry,
)
from p2p_engine.types import ISP, NATType, DeviceVendor


# ==================== Integration Tests ====================

@pytest.mark.asyncio
class TestIdentifyProtocol:
    """Tests for Identify protocol implementation."""

    async def test_identify_message_serialization(self):
        """Test Identify message serialization with extension."""
        ext = IdentifyExtension(
            isp=ISP.CHINA_TELECOM,
            nat_type=NATType.SYMMETRIC,
            device_vendor=DeviceVendor.HUAWEI,
            nat_level=2,
            is_cgnat=True,
        )

        msg = IdentifyMessage(
            protocol_version="/ipfs/0.1.0",
            agent_version="p2p-platform/2.0.0",
            public_key=b"test_public_key",
            listen_addrs=[b"/ip4/0.0.0.0/tcp/0"],
            protocols=[PROTOCOL_ID, "/mplex/6.7.0"],
            ext=ext,
        )

        # Test JSON serialization
        json_dict = msg.to_json_dict()

        assert json_dict["protocolVersion"] == "/ipfs/0.1.0"
        assert json_dict["agentVersion"] == "p2p-platform/2.0.0"
        assert "publicKey" in json_dict
        assert "listenAddrs" in json_dict
        assert json_dict["protocols"] == [PROTOCOL_ID, "/mplex/6.7.0"]
        assert "ext" in json_dict

        # Test deserialization
        restored = IdentifyMessage.from_protobuf_dict(json_dict)

        assert restored.protocol_version == msg.protocol_version
        assert restored.agent_version == msg.agent_version
        assert restored.public_key == msg.public_key
        assert restored.protocols == msg.protocols
        assert restored.ext.isp == ISP.CHINA_TELECOM
        assert restored.ext.nat_type == NATType.SYMMETRIC
        assert restored.ext.device_vendor == DeviceVendor.HUAWEI
        assert restored.ext.nat_level == 2
        assert restored.ext.is_cgnat is True

    async def test_identify_extension_roundtrip(self):
        """Test Identify extension serialization roundtrip."""
        original = IdentifyExtension(
            isp=ISP.CHINA_MOBILE,
            nat_type=NATType.FULL_CONE,
            device_vendor=DeviceVendor.ZTE,
            nat_level=1,
            is_cgnat=False,
            ipv6_available=True,
        )

        # Serialize to bytes
        ext_bytes = original.to_bytes()

        # Deserialize from bytes
        restored = IdentifyExtension.from_bytes(ext_bytes)

        assert restored.isp == original.isp
        assert restored.nat_type == original.nat_type
        assert restored.device_vendor == original.device_vendor
        assert restored.nat_level == original.nat_level
        assert restored.is_cgnat == original.is_cgnat
        assert restored.ipv6_available == original.ipv6_available

    async def test_identify_protocol_create_local_info(self):
        """Test creating local Identify info."""
        protocol = IdentifyProtocol(
            protocol_version="/custom/1.0.0",
            agent_version="custom-agent/3.0",
        )

        ext = IdentifyExtension(isp=ISP.HKBN, nat_type=NATType.RESTRICTED_CONE)
        local_info = protocol.create_local_info(
            public_key=b"my_public_key",
            listen_addrs=[b"/ip4/0.0.0.0/tcp/0", b"/ip6::/tcp/0"],
            protocols=["/custom/proto"],
            extension=ext,
        )

        assert local_info.protocol_version == "/custom/1.0.0"
        assert local_info.agent_version == "custom-agent/3.0"
        assert local_info.public_key == b"my_public_key"
        assert len(local_info.listen_addrs) == 2
        assert local_info.protocols == ["/custom/proto"]
        assert local_info.ext.isp == ISP.HKBN


@pytest.mark.asyncio
class TestIdentifyClient:
    """Tests for Identify client."""

    def test_identify_client_initialization(self):
        """Test Identify client initialization."""
        client = IdentifyClient(
            agent_version="test-agent/1.0.0",
            timeout=10.0,
        )

        assert client.agent_version == "test-agent/1.0.0"
        assert client.protocol.agent_version == "test-agent/1.0.0"
        assert client.negotiator.timeout == 10.0

    async def test_identify_client_factory(self):
        """Test Identify client factory function."""
        client = create_identify_client(
            public_key=b"test_key",
            listen_addrs=[b"/ip4/127.0.0.1/tcp/0"],
            isp=ISP.CHINA_UNICOM,
            nat_type=NATType.FULL_CONE,
            device_vendor=DeviceVendor.CISCO,
        )

        # Check client has local info
        assert hasattr(client, "_local_info")
        assert client._local_info.public_key == b"test_key"
        assert client._local_info.listen_addrs == [b"/ip4/127.0.0.1/tcp/0"]
        assert client._local_info.ext.isp == ISP.CHINA_UNICOM
        assert client._local_info.ext.nat_type == NATType.FULL_CONE
        assert client._local_info.ext.device_vendor == DeviceVendor.CISCO


@pytest.mark.asyncio
class TestProtocolRegistry:
    """Tests for protocol registry and negotiation client."""

    async def test_registry_basic(self):
        """Test basic registry operations."""
        registry = ProtocolRegistry()

        # Register Identify handler
        registry.register(PROTOCOL_ID, lambda: IdentifyHandler())

        # Check supported protocols
        assert PROTOCOL_ID in registry.get_supported_protocols()
        assert registry.is_supported(PROTOCOL_ID)

        # Create handler
        handler = registry.create_handler(PROTOCOL_ID)
        assert isinstance(handler, IdentifyHandler)

        # Unregister
        registry.unregister(PROTOCOL_ID)
        assert not registry.is_supported(PROTOCOL_ID)

        # Recreate after unregister
        assert registry.create_handler(PROTOCOL_ID) is None

    async def test_registry_multiple_protocols(self):
        """Test registry with multiple protocols."""
        registry = ProtocolRegistry()

        # Register multiple handlers
        registry.register(PROTOCOL_ID, lambda: IdentifyHandler())
        registry.register(PROTOCOL_PUSH_ID, lambda: IdentifyHandler())
        registry.register("/custom/protocol", lambda: IdentifyHandler())

        # Check all are registered
        supported = registry.get_supported_protocols()
        assert len(supported) == 3
        assert PROTOCOL_ID in supported
        assert PROTOCOL_PUSH_ID in supported
        assert "/custom/protocol" in supported

    async def test_default_registry(self):
        """Test default registry creation."""
        registry = create_default_registry()

        # Should have Identify protocols registered
        supported = registry.get_supported_protocols()
        assert PROTOCOL_ID in supported
        assert PROTOCOL_PUSH_ID in supported

        # Should be able to create handlers
        handler = registry.create_handler(PROTOCOL_ID)
        assert isinstance(handler, IdentifyHandler)


@pytest.mark.asyncio
class TestIdentifyWithCarrierData:
    """Tests for Identify with carrier-specific data."""

    async def test_all_isp_types(self):
        """Test Identify with all ISP types."""
        for isp in ISP:
            ext = IdentifyExtension(isp=isp)
            msg = IdentifyMessage(ext=ext)

            # Serialize and deserialize
            json_dict = msg.to_json_dict()
            restored = IdentifyMessage.from_protobuf_dict(json_dict)

            assert restored.ext.isp == isp

    async def test_all_nat_types(self):
        """Test Identify with all NAT types."""
        for nat_type in NATType:
            ext = IdentifyExtension(nat_type=nat_type)
            msg = IdentifyMessage(ext=ext)

            # Serialize and deserialize
            json_dict = msg.to_json_dict()
            restored = IdentifyMessage.from_protobuf_dict(json_dict)

            assert restored.ext.nat_type == nat_type

    async def test_all_device_vendors(self):
        """Test Identify with all device vendors."""
        for vendor in DeviceVendor:
            ext = IdentifyExtension(device_vendor=vendor)
            msg = IdentifyMessage(ext=ext)

            # Serialize and deserialize
            json_dict = msg.to_json_dict()
            restored = IdentifyMessage.from_protobuf_dict(json_dict)

            assert restored.ext.device_vendor == vendor

    async def test_complex_extension_data(self):
        """Test Identify with complex extension data."""
        ext = IdentifyExtension(
            isp=ISP.SINGTEL,
            nat_type=NATType.PORT_RESTRICTED,
            device_vendor=DeviceVendor.PALO_ALTO,
            nat_level=3,
            is_cgnat=True,
            ipv6_available=True,
        )

        msg = IdentifyMessage(
            agent_version="enterprise-gateway/1.0.0",
            public_key=b"enterprise_key",
            listen_addrs=[b"/ip4/10.0.0.1/tcp/0"],
            protocols=[PROTOCOL_ID, "/yamux/1.0.0"],
            ext=ext,
        )

        # Full roundtrip test
        json_dict = msg.to_json_dict()
        restored = IdentifyMessage.from_protobuf_dict(json_dict)

        assert restored.agent_version == "enterprise-gateway/1.0.0"
        assert restored.ext.isp == ISP.SINGTEL
        assert restored.ext.nat_type == NATType.PORT_RESTRICTED
        assert restored.ext.device_vendor == DeviceVendor.PALO_ALTO
        assert restored.ext.nat_level == 3
        assert restored.ext.is_cgnat is True
        assert restored.ext.ipv6_available is True


@pytest.mark.asyncio
class TestLibp2pCompatibility:
    """Tests for libp2p compatibility."""

    def test_protocol_ids(self):
        """Test protocol IDs match libp2p spec."""
        assert PROTOCOL_ID == "/ipfs/id/1.0.0"
        assert PROTOCOL_PUSH_ID == "/ipfs/id/push/1.0.0"

    async def test_backward_compatible_empty_fields(self):
        """Test that empty optional fields don't break compatibility."""
        msg = IdentifyMessage(
            protocol_version="/ipfs/0.1.0",
            agent_version="test/1.0.0",
            # All other fields empty/default
        )

        json_dict = msg.to_json_dict()
        restored = IdentifyMessage.from_protobuf_dict(json_dict)

        assert restored.protocol_version == "/ipfs/0.1.0"
        assert restored.agent_version == "test/1.0.0"
        assert restored.public_key == b""
        assert restored.listen_addrs == []
        assert restored.observed_addr == b""
        assert restored.protocols == []

    async def test_extension_field_separate_from_core(self):
        """Test that extension field doesn't interfere with core fields."""
        msg = IdentifyMessage(
            protocol_version="/ipfs/0.1.0",
            agent_version="test/1.0.0",
            public_key=b"key",
            listen_addrs=[b"addr1", b"addr2"],
            protocols=["/p1", "/p2"],
            ext=IdentifyExtension(isp=ISP.ATT),
        )

        json_dict = msg.to_json_dict()

        # Core fields should be present
        assert "protocolVersion" in json_dict
        assert "agentVersion" in json_dict
        assert "publicKey" in json_dict
        assert "listenAddrs" in json_dict
        assert "protocols" in json_dict

        # Extension should be separate
        assert "ext" in json_dict

        # Deserialization should work correctly
        restored = IdentifyMessage.from_protobuf_dict(json_dict)
        assert restored.protocol_version == "/ipfs/0.1.0"
        assert restored.agent_version == "test/1.0.0"
        assert restored.ext.isp == ISP.ATT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
