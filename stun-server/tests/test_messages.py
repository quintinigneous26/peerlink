"""
STUN Protocol Message Tests
"""

import pytest

from src.messages import (
    MAGIC_COOKIE,
    AttributeType,
    ErrorCode,
    MessageType,
    StunMessage,
    StunAttribute,
    create_xor_mapped_address_attr,
    create_error_response,
    parse_mapped_address,
)


class TestStunMessage:
    """Test STUN message parsing and serialization."""

    def test_parse_binding_request(self):
        """Test parsing a valid STUN binding request."""
        # Create a valid STUN binding request
        transaction_id = b"\x12\x34\x56\x78" * 3  # 12 bytes

        header = (
            MessageType.BINDING_REQUEST.to_bytes(2, "big")
            + (0).to_bytes(2, "big")  # Message length
            + MAGIC_COOKIE.to_bytes(4, "big")
            + transaction_id
        )

        message = StunMessage.parse(header)

        assert message is not None
        assert message.message_type == MessageType.BINDING_REQUEST
        assert message.message_length == 0
        assert message.magic_cookie == MAGIC_COOKIE
        assert message.transaction_id == transaction_id
        assert len(message.attributes) == 0

    def test_parse_invalid_message_too_short(self):
        """Test parsing a message that's too short."""
        data = b"\x00\x01\x00\x00\x21\x12\xA4\x42"
        message = StunMessage.parse(data)
        assert message is None

    def test_parse_invalid_magic_cookie(self):
        """Test parsing a message with invalid magic cookie."""
        transaction_id = b"\x00" * 12
        header = (
            MessageType.BINDING_REQUEST.to_bytes(2, "big")
            + (0).to_bytes(2, "big")
            + (0).to_bytes(4, "big")  # Wrong magic cookie
            + transaction_id
        )

        message = StunMessage.parse(header)
        assert message is None

    def test_serialize_message(self):
        """Test serializing a STUN message."""
        transaction_id = b"\x12\x34\x56\x78" * 3

        message = StunMessage(
            message_type=MessageType.BINDING_REQUEST,
            message_length=0,
            magic_cookie=MAGIC_COOKIE,
            transaction_id=transaction_id,
            attributes=[],
        )

        data = message.serialize()

        assert len(data) == 20  # Header only
        assert data[0:2] == MessageType.BINDING_REQUEST.to_bytes(2, "big")
        assert data[4:8] == MAGIC_COOKIE.to_bytes(4, "big")

    def test_message_with_attributes(self):
        """Test parsing message with attributes."""
        transaction_id = b"\x12\x34\x56\x78" * 3

        # Create attribute
        attr_value = b"\x00\x01\x01\x90\x7f\x00\x00\x01"  # IPv4 127.0.0.1:400
        attr_header = AttributeType.MAPPED_ADDRESS.to_bytes(2, "big") + len(
            attr_value
        ).to_bytes(2, "big")

        data = (
            MessageType.BINDING_REQUEST.to_bytes(2, "big")
            + (8).to_bytes(2, "big")  # Attribute length
            + MAGIC_COOKIE.to_bytes(4, "big")
            + transaction_id
            + attr_header
            + attr_value
        )

        message = StunMessage.parse(data)

        assert message is not None
        assert len(message.attributes) == 1
        assert message.attributes[0].type == AttributeType.MAPPED_ADDRESS


class TestAttributes:
    """Test STUN attribute handling."""

    def test_get_attribute(self):
        """Test retrieving an attribute by type."""
        transaction_id = b"\x12\x34\x56\x78" * 3

        message = StunMessage(
            message_type=MessageType.BINDING_RESPONSE,
            message_length=0,
            magic_cookie=MAGIC_COOKIE,
            transaction_id=transaction_id,
            attributes=[
                StunAttribute(type=AttributeType.SOFTWARE, value=b"STUN Server v1.0")
            ],
        )

        attr = message.get_attribute(AttributeType.SOFTWARE)
        assert attr is not None
        assert attr.value == b"STUN Server v1.0"

        attr = message.get_attribute(AttributeType.ERROR_CODE)
        assert attr is None


class TestXorMappedAddress:
    """Test XOR-MAPPED-ADDRESS attribute."""

    def test_create_xor_mapped_address_ipv4(self):
        """Test creating XOR-MAPPED-ADDRESS for IPv4."""
        transaction_id = b"\x12\x34\x56\x78" * 3
        ip = "192.168.1.1"
        port = 12345

        attr = create_xor_mapped_address_attr(ip, port, transaction_id)

        assert len(attr) >= 8
        assert attr[1] == 0x01  # IPv4 family

    def test_parse_mapped_address_ipv4(self):
        """Test parsing MAPPED-ADDRESS for IPv4."""
        # Format: 0 (unused) + family (1) + port + IP
        data = b"\x00\x01\x30\x39" + bytes([192, 168, 1, 1])
        result = parse_mapped_address(data)

        assert result is not None
        assert result[0] == "192.168.1.1"
        assert result[1] == 12345  # 0x3039

    def test_parse_mapped_address_ipv6(self):
        """Test parsing MAPPED-ADDRESS for IPv6."""
        # Simplified IPv6 test
        data = b"\x00\x02\x30\x39" + bytes([0xFE, 0x80] * 8)
        result = parse_mapped_address(data)

        assert result is not None
        assert result[1] == 12345


class TestErrorResponse:
    """Test STUN error response creation."""

    def test_create_error_response(self):
        """Test creating an error response."""
        transaction_id = b"\x12\x34\x56\x78" * 3

        data = create_error_response(
            transaction_id, ErrorCode.BAD_REQUEST, "Invalid request"
        )

        assert len(data) >= 20  # At least header

        # Parse to verify
        message = StunMessage.parse(data)
        assert message is not None
        assert message.message_type == MessageType.BINDING_ERROR_RESPONSE
        assert message.transaction_id == transaction_id


class TestRoundTrip:
    """Test message round-trip serialization."""

    def test_binding_request_roundtrip(self):
        """Test serialize -> parse for binding request."""
        original = StunMessage(
            message_type=MessageType.BINDING_REQUEST,
            message_length=0,
            magic_cookie=MAGIC_COOKIE,
            transaction_id=b"\xAA\xBB\xCC\xDD" * 3,
            attributes=[],
        )

        data = original.serialize()
        parsed = StunMessage.parse(data)

        assert parsed is not None
        assert parsed.message_type == original.message_type
        assert parsed.transaction_id == original.transaction_id
