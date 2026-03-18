"""
Unit tests for P2P Protocol module.
"""

import pytest
import asyncio

from p2p_sdk.protocol import (
    MessageTypes,
    P2PMessage,
    HandshakeMessage,
    create_handshake,
    create_channel_data,
    create_keepalive,
    create_disconnect,
    parse_message,
)


class TestP2PMessage:
    """Test P2P message encoding/decoding."""

    def test_message_encode_decode(self):
        """Test basic message encoding and decoding."""
        msg = P2PMessage(
            msg_type=MessageTypes.CHANNEL_DATA,
            sender_did="device1",
            receiver_did="device2",
            channel_id=1,
            payload=b"test data",
        )

        encoded = msg.encode()
        decoded = P2PMessage.decode(encoded)

        assert decoded is not None
        assert decoded.msg_type == MessageTypes.CHANNEL_DATA
        assert decoded.sender_did == "device1"
        assert decoded.receiver_did == "device2"
        assert decoded.channel_id == 1
        assert decoded.payload == b"test data"

    def test_message_with_metadata(self):
        """Test message with metadata."""
        msg = P2PMessage(
            msg_type=MessageTypes.KEEPALIVE,
            sender_did="device1",
            receiver_did="device2",
            metadata={"key": "value", "number": 42},
        )

        encoded = msg.encode()
        decoded = P2PMessage.decode(encoded)

        assert decoded is not None
        assert decoded.metadata == {"key": "value", "number": 42}

    def test_empty_payload(self):
        """Test message with empty payload."""
        msg = P2PMessage(
            msg_type=MessageTypes.KEEPALIVE,
            sender_did="device1",
            receiver_did="device2",
        )

        encoded = msg.encode()
        decoded = P2PMessage.decode(encoded)

        assert decoded is not None
        assert decoded.payload == b""

    def test_large_payload(self):
        """Test message with large payload."""
        large_data = b"x" * 10000
        msg = P2PMessage(
            msg_type=MessageTypes.CHANNEL_DATA,
            sender_did="device1",
            receiver_did="device2",
            channel_id=1,
            payload=large_data,
        )

        encoded = msg.encode()
        decoded = P2PMessage.decode(encoded)

        assert decoded is not None
        assert decoded.payload == large_data


class TestHandshakeMessage:
    """Test handshake message creation."""

    def test_create_handshake(self):
        """Test handshake message creation."""
        handshake = create_handshake(
            sender_did="device1",
            receiver_did="device2",
            public_ip="1.2.3.4",
            public_port=12345,
            nat_type="full_cone",
        )

        assert handshake.msg_type == MessageTypes.HANDSHAKE
        assert handshake.sender_did == "device1"
        assert handshake.receiver_did == "device2"
        assert handshake.public_ip == "1.2.3.4"
        assert handshake.public_port == 12345
        assert handshake.nat_type == "full_cone"
        assert not handshake.is_ack

    def test_create_handshake_ack(self):
        """Test handshake ACK creation."""
        ack = create_handshake(
            sender_did="device2",
            receiver_did="device1",
            is_ack=True,
        )

        assert ack.msg_type == MessageTypes.HANDSHAKE_ACK
        assert ack.is_ack

    def test_handshake_encode_decode(self):
        """Test handshake encoding/decoding."""
        handshake = create_handshake(
            sender_did="device1",
            receiver_did="device2",
            public_ip="1.2.3.4",
            public_port=12345,
        )

        encoded = handshake.encode()
        decoded = P2PMessage.decode(encoded)

        assert decoded is not None
        assert decoded.msg_type == MessageTypes.HANDSHAKE
        assert decoded.metadata["public_ip"] == "1.2.3.4"
        assert decoded.metadata["public_port"] == 12345


class TestMessageFactories:
    """Test message factory functions."""

    def test_create_channel_data(self):
        """Test channel data message creation."""
        msg = create_channel_data(
            sender_did="device1",
            receiver_did="device2",
            channel_id=5,
            payload=b"data",
        )

        assert msg.msg_type == MessageTypes.CHANNEL_DATA
        assert msg.channel_id == 5
        assert msg.payload == b"data"

    def test_create_keepalive(self):
        """Test keepalive message creation."""
        msg = create_keepalive(
            sender_did="device1",
            receiver_did="device2",
        )

        assert msg.msg_type == MessageTypes.KEEPALIVE

    def test_create_disconnect(self):
        """Test disconnect message creation."""
        msg = create_disconnect(
            sender_did="device1",
            receiver_did="device2",
            reason="test",
        )

        assert msg.msg_type == MessageTypes.DISCONNECT
        assert msg.metadata.get("reason") == "test"


class TestParseMessage:
    """Test message parsing utility."""

    def test_parse_valid_message(self):
        """Test parsing valid message."""
        msg = create_keepalive(sender_did="device1", receiver_did="device2")
        encoded = msg.encode()

        parsed = parse_message(encoded)

        assert parsed is not None
        assert parsed.msg_type == MessageTypes.KEEPALIVE

    def test_parse_invalid_message(self):
        """Test parsing invalid message."""
        invalid_data = b"invalid message data"

        parsed = parse_message(invalid_data)

        assert parsed is None

    def test_parse_truncated_message(self):
        """Test parsing truncated message."""
        truncated_data = b"\x00\x00\x00\x01"  # Valid header but truncated

        parsed = parse_message(truncated_data)

        assert parsed is None
