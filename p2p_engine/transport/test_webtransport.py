"""
WebTransport Transport Tests

Tests for the WebTransport transport implementation.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch

from p2p_engine.transport.webtransport import (
    PROTOCOL_ID,
    WEBTRANSPORT_ENDPOINT,
    WEBTRANSPORT_TYPE_PARAM,
    MAX_CERT_VALIDITY_DAYS,
    CertificateManager,
    CertificateInfo,
    WebTransportConnection,
    WebTransportListener,
    WebTransportTransport,
    create_webtransport_transport,
    get_webtransport_multiaddr,
    AIOQUIC_AVAILABLE,
)
from p2p_engine.transport.base import TransportError, ConnectionError


class TestCertificateManager:
    """Test certificate management"""

    def test_init(self):
        """Test certificate manager initialization"""
        manager = CertificateManager()
        assert manager.get_primary_certificate_hash() is None
        assert manager.get_all_certificate_hashes() == []

    @pytest.mark.skipif(not AIOQUIC_AVAILABLE, reason="aioquic not available")
    def test_generate_certificate(self):
        """Test certificate generation"""
        manager = CertificateManager()

        cert_info = manager.generate_certificate(validity_days=14)

        assert isinstance(cert_info, CertificateInfo)
        assert cert_info.certificate_hash is not None
        assert cert_info.is_valid()
        assert not cert_info.is_expiring_soon()

        # Verify primary cert hash is set
        primary_hash = manager.get_primary_certificate_hash()
        assert primary_hash == cert_info.certificate_hash

    @pytest.mark.skipif(not AIOQUIC_AVAILABLE, reason="aioquic not available")
    def test_max_validity_days(self):
        """Test that max validity is capped at 14 days"""
        manager = CertificateManager()

        # Try to generate with 30 days, should cap at 14
        cert_info = manager.generate_certificate(validity_days=30)

        # Verify the certificate is valid for at most 14 days
        from datetime import timedelta
        validity = cert_info.not_valid_after - cert_info.not_valid_before
        assert validity.days <= MAX_CERT_VALIDITY_DAYS

    def test_get_certificate(self):
        """Test retrieving certificate by hash"""
        manager = CertificateManager()
        manager._certificates["test_hash"] = CertificateInfo(
            certificate=b"test_cert",
            certificate_hash="test_hash",
            not_valid_after=None,
            not_valid_before=None,
        )

        cert = manager.get_certificate("test_hash")
        assert cert is not None
        assert cert.certificate_hash == "test_hash"

    def test_validate_certificate_hashes(self):
        """Test certificate hash validation"""
        manager = CertificateManager()
        manager._primary_cert_hash = "hash1"
        manager._certificates = {
            "hash1": CertificateInfo(
                certificate=b"cert1",
                certificate_hash="hash1",
                not_valid_after=None,
                not_valid_before=None,
            )
        }

        assert manager.validate_certificate_hashes(["hash1", "hash2"]) is True
        assert manager.validate_certificate_hashes(["hash2", "hash3"]) is False


class TestMultiaddrParsing:
    """Test multiaddr parsing"""

    def test_parse_basic_webtransport_addr(self):
        """Test parsing basic WebTransport multiaddr"""
        result = WebTransportTransport._parse_multiaddr(
            "/ip4/192.0.2.0/udp/443/quic/webtransport"
        )

        assert result is not None
        host, port, cert_hashes = result
        assert host == "192.0.2.0"
        assert port == 443
        assert cert_hashes == []

    def test_parse_webtransport_with_certhashes(self):
        """Test parsing WebTransport multiaddr with certificate hashes"""
        result = WebTransportTransport._parse_multiaddr(
            "/ip4/192.0.2.0/udp/443/quic/webtransport/certhash/abc123/certhash/def456"
        )

        assert result is not None
        host, port, cert_hashes = result
        assert host == "192.0.2.0"
        assert port == 443
        assert len(cert_hashes) == 2
        assert "abc123" in cert_hashes
        assert "def456" in cert_hashes

    def test_parse_ipv6_addr(self):
        """Test parsing IPv6 WebTransport multiaddr"""
        result = WebTransportTransport._parse_multiaddr(
            "/ip6/fe80::1/udp/443/quic/webtransport"
        )

        assert result is not None
        host, port, cert_hashes = result
        assert host == "fe80::1"
        assert port == 443

    def test_parse_invalid_addr(self):
        """Test parsing invalid multiaddr"""
        result = WebTransportTransport._parse_multiaddr("invalid-address")
        assert result is None

    def test_parse_non_webtransport_addr(self):
        """Test parsing non-WebTransport multiaddr"""
        result = WebTransportTransport._parse_multiaddr(
            "/ip4/192.0.2.0/tcp/1234"
        )
        assert result is None


class TestWebTransportTransport:
    """Test WebTransport transport"""

    def test_init(self):
        """Test transport initialization"""
        transport = WebTransportTransport()

        assert transport.protocols() == [PROTOCOL_ID]
        assert not transport._closed

    def test_init_with_custom_cert_manager(self):
        """Test transport with custom certificate manager"""
        cert_manager = CertificateManager()
        transport = WebTransportTransport(certificate_manager=cert_manager)

        assert transport._cert_manager == cert_manager

    @pytest.mark.skipif(not AIOQUIC_AVAILABLE, reason="aioquic not available")
    def test_certificate_generated_on_init(self):
        """Test that certificate is auto-generated on init"""
        cert_manager = CertificateManager()
        transport = WebTransportTransport(certificate_manager=cert_manager)

        primary_hash = cert_manager.get_primary_certificate_hash()
        assert primary_hash is not None

    def test_get_certificate_hashes(self):
        """Test getting certificate hashes"""
        cert_manager = CertificateManager()
        cert_manager._certificates = {
            "hash1": Mock(),
            "hash2": Mock(),
        }
        cert_manager._primary_cert_hash = "hash1"

        transport = WebTransportTransport(certificate_manager=cert_manager)

        hashes = transport.get_certificate_hashes()
        assert "hash1" in hashes
        assert "hash2" in hashes

    @pytest.mark.skipif(not AIOQUIC_AVAILABLE, reason="aioquic not available")
    @pytest.mark.asyncio
    async def test_dial_requires_aioquic(self):
        """Test that dial fails gracefully without aioquic"""
        with patch('p2p_engine.transport.webtransport.AIOQUIC_AVAILABLE', False):
            with pytest.raises(TransportError, match="aioquic is required"):
                WebTransportTransport()

    @pytest.mark.skipif(AIOQUIC_AVAILABLE, reason="Testing without aioquic")
    @pytest.mark.asyncio
    async def test_dial_without_aioquic(self):
        """Test that dial fails when aioquic is not available"""
        transport = WebTransportTransport()

        with pytest.raises(TransportError):
            await transport.dial("/ip4/192.0.2.0/udp/443/quic/webtransport")

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing transport"""
        transport = WebTransportTransport()

        # Add a mock listener
        listener = Mock(spec=WebTransportListener)
        listener.close = AsyncMock()
        transport._listeners.append(listener)

        await transport.close()

        assert transport._closed is True
        assert len(transport._listeners) == 0
        listener.close.assert_called_once()


class TestWebTransportListener:
    """Test WebTransport listener"""

    def test_init(self):
        """Test listener initialization"""
        cert_manager = CertificateManager()
        listener = WebTransportListener(
            host="0.0.0.0",
            port=443,
            certificate_manager=cert_manager,
        )

        assert listener._host == "0.0.0.0"
        assert listener._port == 443
        assert listener._cert_manager == cert_manager

    def test_addresses(self):
        """Test getting listener addresses"""
        cert_manager = CertificateManager()
        listener = WebTransportListener(
            host="192.0.2.0",
            port=8443,
            certificate_manager=cert_manager,
        )

        assert not listener.is_closed
        assert listener.addresses == [("192.0.2.0", 8443)]


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_create_webtransport_transport(self):
        """Test creating transport with default settings"""
        transport = create_webtransport_transport()

        assert isinstance(transport, WebTransportTransport)
        assert PROTOCOL_ID in transport.protocols()

    def test_get_webtransport_multiaddr_basic(self):
        """Test building basic multiaddr"""
        addr = get_webtransport_multiaddr("192.0.2.0", 443)

        assert addr == "/ip4/192.0.2.0/udp/443/quic/webtransport"

    def test_get_webtransport_multiaddr_with_certs(self):
        """Test building multiaddr with certificate hashes"""
        addr = get_webtransport_multiaddr(
            "192.0.2.0",
            443,
            cert_hashes=["abc123", "def456"]
        )

        assert addr == "/ip4/192.0.2.0/udp/443/quic/webtransport/certhash/abc123/certhash/def456"


class TestConstants:
    """Test protocol constants"""

    def test_protocol_id(self):
        """Test protocol ID"""
        assert PROTOCOL_ID == "/webtransport/1.0.0"

    def test_webtransport_endpoint(self):
        """Test WebTransport endpoint"""
        assert WEBTRANSPORT_ENDPOINT == "/.well-known/libp2p-webtransport"

    def test_webtransport_type_param(self):
        """Test WebTransport type parameter"""
        assert WEBTRANSPORT_TYPE_PARAM == "noise"

    def test_max_validity_days(self):
        """Test max certificate validity"""
        assert MAX_CERT_VALIDITY_DAYS == 14


@pytest.mark.skipif(not AIOQUIC_AVAILABLE, reason="aioquic not available")
class TestIntegration:
    """Integration tests (require aioquic)"""

    @pytest.mark.asyncio
    async def test_listen_and_dial(self):
        """Test listening and dialing (requires aioquic)"""
        # This is a placeholder for full integration test
        # In production, would test actual QUIC connection
        transport = WebTransportTransport()

        # Test listen
        listener = await transport.listen("/ip4/127.0.0.1/udp/0/quic/webtransport")
        assert isinstance(listener, WebTransportListener)

        await transport.close()
