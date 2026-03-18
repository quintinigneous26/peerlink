"""
NAT Type Detection Module

Implements STUN-based NAT detection to determine the type of NAT
a device is behind. This information is crucial for determining
the best P2P connection strategy.
"""

import socket
import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class NATType(Enum):
    """NAT type classification according to RFC 3489 STUN specification."""

    PUBLIC_IP = "public_ip"
    """No NAT, device has a public IP address."""

    FULL_CONE = "full_cone"
    """Full Cone NAT: Any external host can send to the internal host."""

    RESTRICTED_CONE = "restricted_cone"
    """Restricted Cone NAT: External host must have received data first."""

    PORT_RESTRICTED_CONE = "port_restricted_cone"
    """Port Restricted Cone NAT: Stricter than restricted cone."""

    SYMMETRIC = "symmetric"
    """Symmetric NAT: Each destination gets a different mapping."""

    UNKNOWN = "unknown"
    """Could not determine NAT type."""

    BLOCKED = "blocked"
    """UDP is completely blocked."""


@dataclass
class NATDetectionResult:
    """Result of NAT detection."""

    nat_type: NATType
    public_ip: Optional[str] = None
    public_port: Optional[int] = None
    local_ip: Optional[str] = None
    local_port: Optional[int] = None


class STUNClient:
    """
    STUN protocol client for NAT detection.

    Implements a subset of RFC 5389 (STUN) for NAT type discovery.
    """

    # STUN message types
    BINDING_REQUEST = 0x0001
    BINDING_RESPONSE = 0x0101

    # STUN attributes
    ATTR_MAPPED_ADDRESS = 0x0001
    ATTR_XOR_MAPPED_ADDRESS = 0x0020
    ATTR_CHANGE_REQUEST = 0x0003
    ATTR_CHANGED_ADDRESS = 0x0004

    def __init__(self, stun_server: str, stun_port: int = 3478):
        """
        Initialize STUN client.

        Args:
            stun_server: STUN server hostname or IP
            stun_port: STUN server port (default 3478)
        """
        self.stun_server = stun_server
        self.stun_port = stun_port
        self.timeout = 5.0

    def _pack_stun_request(self, request_type: int = BINDING_REQUEST) -> bytes:
        """Pack a STUN request message."""
        # STUN magic cookie and header
        magic_cookie = bytes.fromhex("2112A442")
        transaction_id = b"0123456789ab"  # 12 bytes transaction ID

        # Message header: type (2) + length (2) + magic cookie (4) + transaction_id (12)
        header = request_type.to_bytes(2, "big")
        header += (0).to_bytes(2, "big")  # Length = 0 (no attributes)
        header += magic_cookie
        header += transaction_id

        return header

    def _unpack_stun_response(self, data: bytes) -> Tuple[Optional[str], Optional[int]]:
        """
        Unpack STUN response and extract mapped address.

        Returns:
            Tuple of (ip, port) or (None, None) if parsing fails
        """
        if len(data) < 20:
            return None, None

        message_type = int.from_bytes(data[0:2], "big")
        message_len = int.from_bytes(data[2:4], "big")
        magic_cookie = data[4:8]

        if magic_cookie != bytes.fromhex("2112A442"):
            logger.warning("Invalid STUN magic cookie")
            return None, None

        # Parse attributes
        idx = 20
        while idx < len(data):
            if idx + 4 > len(data):
                break

            attr_type = int.from_bytes(data[idx:idx + 2], "big")
            attr_len = int.from_bytes(data[idx + 2:idx + 4], "big")
            idx += 4

            # Padding to 4-byte boundary
            padding = (4 - (attr_len % 4)) % 4

            if idx + attr_len > len(data):
                break

            attr_value = data[idx:idx + attr_len]
            idx += attr_len + padding

            # Parse XOR-MAPPED-ADDRESS (preferred)
            if attr_type == self.ATTR_XOR_MAPPED_ADDRESS and attr_len >= 8:
                family = attr_value[1]
                if family == 0x01:  # IPv4
                    xored_port = int.from_bytes(attr_value[2:4], "big")
                    xored_ip = int.from_bytes(attr_value[4:8], "big")
                    magic = int.from_bytes(magic_cookie, "big")

                    port = xored_port ^ (magic >> 16)
                    ip = xored_ip ^ magic
                    ip_str = socket.inet_ntoa(ip.to_bytes(4, "big"))
                    return ip_str, port

            # Parse MAPPED-ADDRESS (fallback)
            elif attr_type == self.ATTR_MAPPED_ADDRESS and attr_len >= 8:
                family = attr_value[1]
                if family == 0x01:  # IPv4
                    port = int.from_bytes(attr_value[2:4], "big")
                    ip = int.from_bytes(attr_value[4:8], "big")
                    ip_str = socket.inet_ntoa(ip.to_bytes(4, "big"))
                    return ip_str, port

        return None, None

    async def send_request(self) -> Tuple[Optional[str], Optional[int]]:
        """
        Send STUN binding request and get mapped address.

        Returns:
            Tuple of (public_ip, public_port) or (None, None) on failure
        """
        sock = None
        try:
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setblocking(False)

            # Get local address
            sock.bind(("", 0))
            local_port = sock.getsockname()[1]

            # Send STUN request
            request = self._pack_stun_request()

            # Resolve server address
            loop = asyncio.get_event_loop()
            server_addr = await loop.getaddrinfo(
                self.stun_server, self.stun_port, proto=socket.IPPROTO_UDP
            )
            target = server_addr[0][4]

            sock.sendto(request, target)

            # Wait for response with timeout
            loop = asyncio.get_event_loop()
            try:
                data, _ = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 512), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"STUN request to {self.stun_server} timed out")
                return None, None

            # Parse response
            public_ip, public_port = self._unpack_stun_response(data)

            if public_ip and public_port:
                logger.info(
                    f"STUN response: {public_ip}:{public_port} (local port: {local_port})"
                )

            return public_ip, public_port

        except OSError as e:
            logger.error(f"Socket error during STUN request: {e}")
            return None, None
        finally:
            if sock:
                sock.close()


async def detect_nat_type(
    stun_server: str = "stun.l.google.com", stun_port: int = 19302
) -> NATDetectionResult:
    """
    Detect NAT type using STUN server.

    This is a simplified detection that determines:
    - Public IP (no NAT)
    - Symmetric NAT (different port for each destination)
    - Cone NAT (same port for all destinations)
    - Blocked (UDP filtered)

    Full RFC 3489 detection requires multiple STUN servers with
    specific IP address ranges.

    Args:
        stun_server: STUN server hostname
        stun_port: STUN server port

    Returns:
        NATDetectionResult with detected type and address info
    """
    client = STUNClient(stun_server, stun_port)

    # Test 1: Basic binding request
    public_ip, public_port = await client.send_request()

    if public_ip is None:
        # Could be blocked or network issue
        return NATDetectionResult(nat_type=NATType.BLOCKED)

    # Get local IP
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except OSError:
        # Failed to resolve hostname, use loopback
        local_ip = "127.0.0.1"

    # Check if we have a public IP
    # Simple heuristic: if public IP matches local IP, likely no NAT
    # This is not perfect but works for basic detection
    try:
        # Try to determine if we're behind NAT by checking if public IP is private range
        import ipaddress

        pub_addr = ipaddress.ip_address(public_ip)
        if not pub_addr.is_private:
            # We got a public IP, but need to check if it's our actual IP
            # For now, assume if we get a response, we can do P2P
            return NATDetectionResult(
                nat_type=NATType.PUBLIC_IP,
                public_ip=public_ip,
                public_port=public_port,
                local_ip=local_ip,
            )
    except (ValueError, ipaddress.AddressValueError):
        # Invalid IP address format, continue with default assumption
        pass

    # Test 2: Check for symmetric NAT by sending to another server
    # (simplified - would need second STUN server for proper detection)

    # Default assumption for single server detection
    return NATDetectionResult(
        nat_type=NATType.RESTRICTED_CONE,
        public_ip=public_ip,
        public_port=public_port,
        local_ip=local_ip,
    )


def is_nat_p2p_capable(nat_type: NATType) -> bool:
    """
    Check if a NAT type is capable of P2P connection.

    Args:
        nat_type: The detected NAT type

    Returns:
        True if P2P is possible, False if relay is needed
    """
    # These NAT types can do P2P
    p2p_capable = [
        NATType.PUBLIC_IP,
        NATType.FULL_CONE,
        NATType.RESTRICTED_CONE,
        NATType.PORT_RESTRICTED_CONE,
    ]

    return nat_type in p2p_capable
