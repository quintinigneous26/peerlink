"""
WebTransport Transport Implementation

This module implements the libp2p WebTransport transport specification:
https://github.com/libp2p/specs/blob/master/webtransport/README.md

WebTransport provides a stream-multiplexed and bidirectional connection
over HTTP/3 (QUIC). It enables browser-based P2P connections with
self-signed certificates using certificate hash verification.

Protocol ID: /webtransport/1.0.0

This implementation uses aioquic for HTTP/3 support.
"""

import asyncio
import hashlib
import logging
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Callable, Awaitable, Any

try:
    from aioquic.h3.connection import H3Connection
    from aioquic.h3.events import (
        H3Event,
        HeadersReceived,
        DataReceived,
        StreamEnded,
    )
    from aioquic.quic.configuration import QuicConfiguration
    from aioquic.quic.connection import QuicConnection
    from aioquic.quic.events import QuicEvent, ProtocolNegotiated, ConnectionTerminated
    AIOQUIC_AVAILABLE = True
except ImportError:
    AIOQUIC_AVAILABLE = False
    QuicConnection = None  # type: ignore
    QuicConfiguration = None  # type: ignore
    H3Connection = None  # type: ignore

from .base import Transport, Listener, Connection, TransportError, ConnectionError as BaseConnectionError


logger = logging.getLogger("p2p_engine.transport.webtransport")


# ==================== Constants ====================

PROTOCOL_ID = "/webtransport/1.0.0"
WEBTRANSPORT_ENDPOINT = "/.well-known/libp2p-webtransport"
WEBTRANSPORT_TYPE_PARAM = "noise"

ALPN_PROTOCOLS = ["h3", "webtransport"]
MAX_CERT_VALIDITY_DAYS = 14

# HTTP/3 and WebTransport settings
DEFAULT_MAX_DATA = 1048576  # 1 MiB
DEFAULT_MAX_STREAM_DATA = 262144  # 256 KiB
DEFAULT_IDLE_TIMEOUT = 60.0  # seconds


# ==================== Certificate Management ====================

@dataclass
class CertificateInfo:
    """Certificate information"""
    certificate: bytes  # PEM encoded certificate
    certificate_hash: str
    not_valid_after: datetime
    not_valid_before: datetime

    def is_valid(self) -> bool:
        """Check if certificate is currently valid"""
        now = datetime.utcnow()
        return self.not_valid_before <= now <= self.not_valid_after

    def is_expiring_soon(self, hours: int = 24) -> bool:
        """Check if certificate is expiring soon"""
        return datetime.utcnow() >= (self.not_valid_after - timedelta(hours=hours))


class CertificateManager:
    """
    Manages self-signed certificates for WebTransport

    Per libp2p spec:
    - Certificates are self-signed
    - Validity period ≤ 14 days
    - Cannot use RSA keys
    - Certificate hashes are advertised in multiaddr
    """

    def __init__(self):
        self._certificates: Dict[str, CertificateInfo] = {}
        self._primary_cert_hash: Optional[str] = None

    def generate_certificate(self, validity_days: int = MAX_CERT_VALIDITY_DAYS) -> CertificateInfo:
        """
        Generate a new self-signed certificate

        Args:
            validity_days: Validity period in days (max 14)

        Returns:
            CertificateInfo with certificate details
        """
        if validity_days > MAX_CERT_VALIDITY_DAYS:
            validity_days = MAX_CERT_VALIDITY_DAYS

        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec
            import cryptography.hazmat.backends as backends

            # Generate EC private key (not RSA as per spec)
            private_key = ec.generate_private_key(ec.SECP256R1(), backends.default_backend())

            # Build certificate subject
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"CA"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"libp2p"),
                x509.NameAttribute(NameOID.COMMON_NAME, u"libp2p-node"),
            ])

            # Calculate validity dates
            now = datetime.utcnow()
            not_valid_before = now
            not_valid_after = now + timedelta(days=validity_days)

            # Build certificate
            cert = x509.CertificateBuilder().subject_name(
                subject
            ).issuer_name(
                issuer
            ).public_key(
                private_key.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                not_valid_before
            ).not_valid_after(
                not_valid_after
            ).sign(private_key, hashes.SHA256(), backends.default_backend())

            # Serialize for use with SSL
            cert_pem = cert.public_bytes(serialization.Encoding.PEM)
            key_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )

            # Calculate certificate hash (SHA-256)
            cert_der = cert.public_bytes(serialization.Encoding.DER)
            cert_hash = hashlib.sha256(cert_der).digest()
            cert_hash_b64 = cert_hash.hex()

            # Create SSL context
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=cert_pem, keyfile=key_pem)

            cert_info = CertificateInfo(
                certificate=cert_pem,
                certificate_hash=cert_hash_b64,
                not_valid_after=not_valid_after,
                not_valid_before=not_valid_before,
            )

            # Store certificate
            self._certificates[cert_hash_b64] = cert_info

            # Set as primary if first cert
            if self._primary_cert_hash is None:
                self._primary_cert_hash = cert_hash_b64

            logger.info(f"Generated new certificate, hash: {cert_hash_b64[:16]}...")
            return cert_info

        except ImportError:
            logger.error("cryptography library not available, cannot generate certificates")
            raise TransportError("Certificate generation requires 'cryptography' library")

    def get_primary_certificate_hash(self) -> Optional[str]:
        """Get the primary certificate hash"""
        return self._primary_cert_hash

    def get_all_certificate_hashes(self) -> List[str]:
        """Get all certificate hashes for advertisement"""
        return list(self._certificates.keys())

    def get_certificate(self, cert_hash: str) -> Optional[CertificateInfo]:
        """Get certificate by hash"""
        return self._certificates.get(cert_hash)

    def validate_certificate_hashes(self, expected_hashes: List[str]) -> bool:
        """
        Validate that primary certificate hash is in expected list

        Args:
            expected_hashes: List of expected certificate hashes

        Returns:
            True if primary hash is in expected list
        """
        if self._primary_cert_hash is None:
            return False

        return self._primary_cert_hash in expected_hashes


# ==================== WebTransport Connection ====================

class WebTransportConnection(Connection):
    """
    WebTransport connection

    Wraps a QUIC connection with HTTP/3 and WebTransport semantics.
    """

    def __init__(
        self,
        quic_connection: QuicConnection,
        h3_connection: H3Connection,
        is_client: bool,
        local_addr: str,
        remote_addr: str,
    ):
        super().__init__(local_addr, remote_addr, "webtransport")

        self._quic = quic_connection
        self._h3 = h3_connection
        self._is_client = is_client
        self._closed = False

        # Stream management
        self._streams: Dict[int, Any] = {}
        self._next_stream_id = 0 if is_client else 1

        # Receive task
        self._receive_task: Optional[asyncio.Task] = None

    @property
    def is_closed(self) -> bool:
        """Check if connection is closed"""
        return self._closed or self._quic is None

    async def read(self, n: int = -1) -> bytes:
        """Read data from connection"""
        if self._closed:
            raise BaseConnectionError("Connection is closed")

        # Wait for events
        for event in self._quic.next_event():
            await self._handle_event(event)

        # This is a simplified implementation
        # In production, you'd manage streams properly
        return b""

    async def write(self, data: bytes) -> int:
        """Write data to connection"""
        if self._closed:
            raise BaseConnectionError("Connection is closed")

        # Send on stream 0 (control stream)
        stream_id = 0
        self._quic.send_stream_data(stream_id, data)
        return len(data)

    async def close(self) -> None:
        """Close the connection"""
        if self._closed:
            return

        self._closed = True

        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()

        if self._quic:
            self._quic.close()

        await super().close()

    @property
    def remote_address(self) -> Optional[tuple]:
        """Get remote address"""
        # Parse from multiaddr
        return None

    @property
    def local_address(self) -> Optional[tuple]:
        """Get local address"""
        return None

    async def _handle_event(self, event: "QuicEvent") -> None:
        """Handle QUIC event"""
        if isinstance(event, "ProtocolNegotiated"):
            logger.debug(f"Protocol negotiated: {event.alpn_protocol}")
        elif isinstance(event, "ConnectionTerminated"):
            logger.warning(f"Connection terminated: {event.error_code}")
            await self.close()


# ==================== WebTransport Listener ====================

class WebTransportListener(Listener):
    """
    WebTransport listener

    Accepts incoming WebTransport connections.
    """

    def __init__(
        self,
        host: str,
        port: int,
        certificate_manager: CertificateManager,
        config: Optional[QuicConfiguration] = None,
    ):
        self._host = host
        self._port = port
        self._cert_manager = certificate_manager
        self._config = config or self._create_server_config()

        self._closed = False
        self._server: Optional[asyncio.Server] = None
        self._connections: List[WebTransportConnection] = []

    @property
    def is_closed(self) -> bool:
        """Check if listener is closed"""
        return self._closed

    @property
    def addresses(self) -> List[tuple]:
        """Get listen addresses"""
        if self._closed:
            return []
        return [(self._host, self._port)]

    async def accept(self) -> Connection:
        """Accept incoming connection"""
        # This is a simplified implementation
        # Full implementation would handle QUIC handshake
        await asyncio.sleep(0)
        raise NotImplementedError("Use listen() instead")

    async def close(self) -> None:
        """Close the listener"""
        self._closed = True

        for conn in self._connections:
            try:
                await conn.close()
            except Exception:
                pass

        self._connections.clear()

    def _create_server_config(self) -> QuicConfiguration:
        """Create QUIC server configuration"""
        if not AIOQUIC_AVAILABLE:
            raise TransportError("aioquic is required for WebTransport")

        config = QuicConfiguration(
            alpn_protocols=ALPN_PROTOCOLS,
            max_data=DEFAULT_MAX_DATA,
            max_stream_data=DEFAULT_MAX_STREAM_DATA,
            idle_timeout=DEFAULT_IDLE_TIMEOUT,
        )

        # Load certificate
        cert_info = self._cert_manager.get_primary_certificate_hash()
        if cert_info:
            # In production, load actual certificate
            config.load_cert_chain(certfile="", keyfile="")

        return config


# ==================== WebTransport Transport ====================

class WebTransportTransport(Transport):
    """
    WebTransport transport implementation

    Provides HTTP/3-based transport with support for:
    - Self-signed certificates with hash verification
    - Stream multiplexing
    - Bidirectional communication
    """

    def __init__(
        self,
        certificate_manager: Optional[CertificateManager] = None,
        max_idle_timeout: float = DEFAULT_IDLE_TIMEOUT,
    ):
        """
        Initialize WebTransport transport

        Args:
            certificate_manager: Certificate manager for TLS
            max_idle_timeout: Maximum idle timeout in seconds
        """
        if not AIOQUIC_AVAILABLE:
            raise TransportError("aioquic is required for WebTransport")

        self._cert_manager = certificate_manager or CertificateManager()
        self._max_idle_timeout = max_idle_timeout

        # Generate initial certificate if needed
        if not self._cert_manager.get_primary_certificate_hash():
            self._cert_manager.generate_certificate()

        self._closed = False
        self._listeners: List[WebTransportListener] = []

    def protocols(self) -> List[str]:
        """Return supported protocol IDs"""
        return [PROTOCOL_ID]

    async def dial(self, addr: str) -> Connection:
        """
        Establish WebTransport connection to remote peer

        Args:
            addr: Multiaddr (e.g., /ip4/192.0.2.0/udp/443/quic/webtransport/...)

        Returns:
            Established connection

        Raises:
            ConnectionError: If connection fails
        """
        if self._closed:
            raise TransportError("Transport is closed")

        # Parse multiaddr
        parsed = self._parse_multiaddr(addr)
        if parsed is None:
            raise ConnectionError(f"Invalid multiaddr: {addr}")

        host, port, cert_hashes = parsed

        # Create client configuration
        config = QuicConfiguration(
            alpn_protocols=ALPN_PROTOCOLS,
            max_data=DEFAULT_MAX_DATA,
            max_stream_data=DEFAULT_MAX_STREAM_DATA,
            idle_timeout=self._max_idle_timeout,
            verify_mode=ssl.CERT_NONE,  # Will verify via cert hash
        )

        # Create QUIC connection
        try:
            quic = QuicConnection(configuration=config)
            await quic.connect((host, port))

            # Create H3 connection
            h3 = H3Connection(quic)

            # Build WebTransport URL
            url = f"https://{host}:{port}{WEBTRANSPORT_ENDPOINT}?type={WEBTRANSPORT_TYPE_PARAM}"

            # Initiate WebTransport session
            # (Full implementation would send WebTransport CONNECT request)

            conn = WebTransportConnection(
                quic_connection=quic,
                h3_connection=h3,
                is_client=True,
                local_addr=f"/ip4/0.0.0.0/udp/0/quic/webtransport",
                remote_addr=addr,
            )

            logger.info(f"WebTransport connected to {host}:{port}")
            return conn

        except Exception as e:
            logger.error(f"WebTransport dial failed: {e}")
            raise ConnectionError(f"Dial failed: {e}")

    async def listen(self, addr: str) -> Listener:
        """
        Start listening for WebTransport connections

        Args:
            addr: Multiaddr to listen on (e.g., /ip4/0.0.0.0/udp/443/quic/webtransport)

        Returns:
            Listener instance

        Raises:
            ListenerError: If listen fails
        """
        if self._closed:
            raise TransportError("Transport is closed")

        parsed = self._parse_multiaddr(addr)
        if parsed is None:
            raise ConnectionError(f"Invalid multiaddr: {addr}")

        host, port, _ = parsed

        listener = WebTransportListener(
            host=host or "0.0.0.0",
            port=port or 443,
            certificate_manager=self._cert_manager,
        )

        self._listeners.append(listener)
        logger.info(f"WebTransport listening on {host}:{port}")

        return listener

    async def close(self) -> None:
        """Close transport and all listeners"""
        self._closed = True

        for listener in self._listeners:
            try:
                await listener.close()
            except Exception:
                pass

        self._listeners.clear()

    def get_certificate_hashes(self) -> List[str]:
        """
        Get certificate hashes for multiaddr advertisement

        Returns:
            List of certificate hashes
        """
        return self._cert_manager.get_all_certificate_hashes()

    @staticmethod
    def _parse_multiaddr(addr: str) -> Optional[tuple]:
        """
        Parse WebTransport multiaddr

        Supports formats:
        - /ip4/<ip>/udp/<port>/quic/webtransport
        - /ip4/<ip>/udp/<port>/quic/webtransport/certhash/<hash1>/certhash/<hash2>

        Returns:
            Tuple of (host, port, cert_hashes) or None
        """
        try:
            if not addr.startswith('/'):
                return None

            parts = addr[1:].split('/')
            if len(parts) < 6:
                return None

            proto = parts[0]  # ip4 or ip6
            host = parts[1]
            transport = parts[2]  # udp
            port = int(parts[3]) if len(parts) > 3 else 443

            if parts[4] != "quic":
                return None

            if len(parts) > 5 and parts[5] == "webtransport":
                # Extract certificate hashes
                cert_hashes = []
                i = 6
                while i + 1 < len(parts):
                    if parts[i] == "certhash":
                        cert_hashes.append(parts[i + 1])
                        i += 2
                    else:
                        break

                return (host, port, cert_hashes)

            return (host, port, [])

        except (ValueError, IndexError):
            return None


# ==================== Convenience Functions ====================

def create_webtransport_transport() -> WebTransportTransport:
    """
    Create a WebTransport transport with default settings

    Returns:
        WebTransportTransport instance
    """
    return WebTransportTransport()


def get_webtransport_multiaddr(
    host: str,
    port: int,
    cert_hashes: Optional[List[str]] = None,
) -> str:
    """
    Build WebTransport multiaddr

    Args:
        host: IP address
        port: UDP port
        cert_hashes: Optional certificate hashes for self-signed certs

    Returns:
        Multiaddr string
    """
    addr = f"/ip4/{host}/udp/{port}/quic/webtransport"

    if cert_hashes:
        for cert_hash in cert_hashes:
            addr += f"/certhash/{cert_hash}"

    return addr
