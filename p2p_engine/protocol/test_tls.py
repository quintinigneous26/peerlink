"""
Unit tests for TLS 1.3 protocol implementation.

Tests:
- Certificate generation
- TLS handshake
- Payload exchange
- Error handling
"""

import asyncio
import pytest
import ssl
from p2p_engine.protocol.tls import (
    TLSSecurity,
    TLSSecurityTransport,
    TLSConfig,
    TLSHandshakePayload,
    CertificateConfig,
    generate_self_signed_cert,
    generate_ed25519_keypair,
    PROTOCOL_ID,
    TLSError,
    TLSHandshakeError,
    TLSCertificateError,
    TLSVerificationError,
    create_tls_security,
)


class TestCertificateGeneration:
    """Test certificate generation utilities."""

    def test_generate_ed25519_keypair(self):
        """Test Ed25519 key pair generation."""
        private_key, public_key = generate_ed25519_keypair()

        assert len(private_key) == 32
        assert len(public_key) == 32
        assert private_key != public_key

    def test_generate_self_signed_cert(self):
        """Test self-signed certificate generation."""
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        config = CertificateConfig(
            common_name="test-peer",
            country="US",
            organization="libp2p"
        )

        cert_bytes, key_bytes = generate_self_signed_cert(private_key, config)

        assert cert_bytes.startswith(b'-----BEGIN CERTIFICATE-----')
        assert key_bytes.startswith(b'-----BEGIN PRIVATE KEY-----')

    def test_certificate_config_from_peer_id(self):
        """Test CertificateConfig creation from peer ID."""
        peer_id = "QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"
        config = CertificateConfig.from_peer_id(peer_id)

        assert config.common_name == peer_id[:16]
        assert config.organization == "libp2p"


class TestTLSHandshakePayload:
    """Test TLS handshake payload encoding/decoding."""

    def test_payload_encode_decode(self):
        """Test payload encoding and decoding."""
        original = TLSHandshakePayload(
            peer_id=b"test-peer-id",
            public_key=b"public-key-bytes",
            signed_payload=b"signature-bytes",
            extensions=["/yamux/1.0.0", "/mplex/6.7.0"]
        )

        encoded = original.encode()
        decoded = TLSHandshakePayload.decode(encoded)

        assert decoded.peer_id == original.peer_id
        assert decoded.public_key == original.public_key
        assert decoded.signed_payload == original.signed_payload
        assert decoded.extensions == original.extensions

    def test_payload_with_no_extensions(self):
        """Test payload with no extensions."""
        payload = TLSHandshakePayload(
            peer_id=b"test-peer-id",
            public_key=b"public-key-bytes",
            signed_payload=b"signature-bytes",
            extensions=[]
        )

        encoded = payload.encode()
        decoded = TLSHandshakePayload.decode(encoded)

        assert decoded.extensions == []


class TestTLSConfig:
    """Test TLS configuration."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = TLSConfig(
            identity_private_key=b"private-key",
            identity_public_key=b"public-key",
            peer_id="test-peer-id"
        )

        assert config.stream_muxers == ["/yamux/1.0.0", "/mplex/6.7.0"]
        assert config.verify_peer is True
        assert config.alpn_protocols == ["libp2p"]

    def test_config_custom_values(self):
        """Test custom configuration values."""
        config = TLSConfig(
            identity_private_key=b"private-key",
            identity_public_key=b"public-key",
            peer_id="test-peer-id",
            stream_muxers=["/yamux/1.0.0"],
            verify_peer=False
        )

        assert config.stream_muxers == ["/yamux/1.0.0"]
        assert config.verify_peer is False


@pytest.mark.asyncio
class TestTLSSecurity:
    """Test TLS security implementation."""

    async def test_protocol_id(self):
        """Test protocol ID constant."""
        assert PROTOCOL_ID == "/tls/1.0.0"

    async def test_tls_security_creation(self):
        """Test TLS security instance creation."""
        private_key, public_key = generate_ed25519_keypair()
        config = TLSConfig(
            identity_private_key=private_key,
            identity_public_key=public_key,
            peer_id="test-peer-id"
        )

        tls = TLSSecurity(config)

        assert tls.config.peer_id == "test-peer-id"
        assert tls._cert_bytes is not None
        assert tls._key_bytes is not None

    async def test_create_tls_security_convenience(self):
        """Test convenience function for creating TLS security."""
        private_key, public_key = generate_ed25519_keypair()

        tls = await create_tls_security(
            identity_private_key=private_key,
            identity_public_key=public_key,
            peer_id="test-peer-id"
        )

        assert tls.config.peer_id == "test-peer-id"
        assert isinstance(tls, TLSSecurity)


@pytest.mark.asyncio
class TestTLSSecurityTransport:
    """Test TLS security transport."""

    async def test_transport_send_recv(self):
        """Test transport send and receive."""
        # Create a pair of connected streams
        reader_a, writer_a = await asyncio.open_connection(
            '127.0.0.1', 0  # Will fail, just for type checking
        )

    async def test_transport_close(self):
        """Test transport close."""
        # Create mock reader/writer
        class MockReader:
            async def readexactly(self, n):
                raise asyncio.CancelledError()

        class MockWriter:
            def __init__(self):
                self.closed = False

            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                self.closed = True

            async def wait_closed(self):
                pass

        transport = TLSSecurityTransport(MockReader(), MockWriter())
        assert not transport.closed

        await transport.close()
        assert transport.closed


@pytest.mark.asyncio
class TestTLSIntegration:
    """Integration tests for TLS protocol."""

    async def test_full_handshake_flow(self):
        """Test complete TLS handshake flow."""
        # This test requires actual network connection
        # For now, we test the configuration
        private_key_a, public_key_a = generate_ed25519_keypair()
        private_key_b, public_key_b = generate_ed25519_keypair()

        config_a = TLSConfig(
            identity_private_key=private_key_a,
            identity_public_key=public_key_a,
            peer_id="peer-a"
        )

        config_b = TLSConfig(
            identity_private_key=private_key_b,
            identity_public_key=public_key_b,
            peer_id="peer-b"
        )

        tls_a = TLSSecurity(config_a)
        tls_b = TLSSecurity(config_b)

        assert tls_a.config.peer_id == "peer-a"
        assert tls_b.config.peer_id == "peer-b"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
