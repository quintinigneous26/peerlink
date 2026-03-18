"""
Unit tests for NAT Detection module.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from p2p_sdk.nat_detection import (
    NATType,
    NATDetectionResult,
    STUNClient,
    detect_nat_type,
    is_nat_p2p_capable,
)


class TestNATType:
    """Test NATType enum."""

    def test_nat_type_values(self):
        """Test NAT type enum values."""
        assert NATType.PUBLIC_IP.value == "public_ip"
        assert NATType.FULL_CONE.value == "full_cone"
        assert NATType.RESTRICTED_CONE.value == "restricted_cone"
        assert NATType.PORT_RESTRICTED_CONE.value == "port_restricted_cone"
        assert NATType.SYMMETRIC.value == "symmetric"
        assert NATType.UNKNOWN.value == "unknown"
        assert NATType.BLOCKED.value == "blocked"


class TestNATDetectionResult:
    """Test NATDetectionResult dataclass."""

    def test_create_result(self):
        """Test creating detection result."""
        result = NATDetectionResult(
            nat_type=NATType.FULL_CONE,
            public_ip="1.2.3.4",
            public_port=12345,
        )

        assert result.nat_type == NATType.FULL_CONE
        assert result.public_ip == "1.2.3.4"
        assert result.public_port == 12345


class TestSTUNClient:
    """Test STUN client."""

    def test_init(self):
        """Test STUN client initialization."""
        client = STUNClient("stun.example.com", 3478)

        assert client.stun_server == "stun.example.com"
        assert client.stun_port == 3478
        assert client.timeout == 5.0

    def test_pack_stun_request(self):
        """Test STUN request packing."""
        client = STUNClient("stun.example.com")
        request = client._pack_stun_request()

        assert len(request) == 20
        assert request[0:2] == STUNClient.BINDING_REQUEST.to_bytes(2, "big")

    def test_unpack_stun_response_invalid_magic(self):
        """Test unpacking response with invalid magic cookie."""
        client = STUNClient("stun.example.com")
        invalid_response = b"\x01\x01\x00\x00" + b"INVALID" + b"0123456789ab"

        result = client._unpack_stun_response(invalid_response)

        assert result == (None, None)

    def test_unpack_stun_response_too_short(self):
        """Test unpacking response that's too short."""
        client = STUNClient("stun.example.com")
        short_response = b"\x01\x01\x00\x00"

        result = client._unpack_stun_response(short_response)

        assert result == (None, None)


class TestIsNATP2PCapable:
    """Test NAT P2P capability check."""

    def test_public_ip_capable(self):
        """Test public IP is P2P capable."""
        assert is_nat_p2p_capable(NATType.PUBLIC_IP) is True

    def test_full_cone_capable(self):
        """Test full cone NAT is P2P capable."""
        assert is_nat_p2p_capable(NATType.FULL_CONE) is True

    def test_restricted_cone_capable(self):
        """Test restricted cone NAT is P2P capable."""
        assert is_nat_p2p_capable(NATType.RESTRICTED_CONE) is True

    def test_port_restricted_cone_capable(self):
        """Test port restricted cone NAT is P2P capable."""
        assert is_nat_p2p_capable(NATType.PORT_RESTRICTED_CONE) is True

    def test_symmetric_not_capable(self):
        """Test symmetric NAT is not P2P capable."""
        assert is_nat_p2p_capable(NATType.SYMMETRIC) is False

    def test_blocked_not_capable(self):
        """Test blocked is not P2P capable."""
        assert is_nat_p2p_capable(NATType.BLOCKED) is False

    def test_unknown_not_capable(self):
        """Test unknown is not P2P capable."""
        assert is_nat_p2p_capable(NATType.UNKNOWN) is False


class TestDetectNATType:
    """Test NAT type detection."""

    @pytest.mark.asyncio
    async def test_detect_nat_timeout(self):
        """Test NAT detection with timeout."""
        # Mock STUN client that times out
        with patch.object(STUNClient, "send_request", return_value=(None, None)):
            result = await detect_nat_type("stun.example.com")

            assert result.nat_type == NATType.BLOCKED
            assert result.public_ip is None

    @pytest.mark.asyncio
    async def test_detect_nat_success(self):
        """Test successful NAT detection."""
        # Mock STUN client that returns valid address
        with patch.object(STUNClient, "send_request", return_value=("1.2.3.4", 12345)):
            with patch("socket.gethostbyname", return_value="192.168.1.100"):
                result = await detect_nat_type("stun.example.com")

                assert result.public_ip == "1.2.3.4"
                assert result.public_port == 12345
