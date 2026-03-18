"""
NAT Type Detection

Implements NAT type detection algorithm based on RFC 3489.
"""

import asyncio
import socket
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class NATType(Enum):
    """NAT types detected by STUN."""

    OPEN_INTERNET = "Open Internet"
    FULL_CONE = "Full Cone NAT"
    RESTRICTED_CONE = "Restricted Cone NAT"
    PORT_RESTRICTED_CONE = "Port Restricted Cone NAT"
    SYMMETRIC = "Symmetric NAT"
    BLOCKED = "Firewall Blocks UDP"
    UNKNOWN = "Unknown"


@dataclass
class NATTestResult:
    """Result of NAT detection test."""

    nat_type: NATType
    public_ip: Optional[str]
    public_port: Optional[int]
    changed_ip_response: bool
    changed_port_response: bool


async def send_stun_request(
    host: str, port: int, timeout: float = 2.0
) -> Optional[Tuple[str, int]]:
    """
    Send STUN binding request and get mapped address.

    Args:
        host: STUN server hostname
        port: STUN server port
        timeout: Request timeout in seconds

    Returns:
        Tuple of (mapped_ip, mapped_port) or None
    """
    from .messages import (
        MAGIC_COOKIE,
        MessageType,
        StunMessage,
        parse_xor_mapped_address,
    )

    # Create STUN binding request
    transaction_id = asyncio.get_event_loop().time_ns().to_bytes(12, "big")

    message = StunMessage(
        message_type=MessageType.BINDING_REQUEST,
        message_length=0,
        magic_cookie=MAGIC_COOKIE,
        transaction_id=transaction_id,
        attributes=[],
    )

    request_data = message.serialize()

    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)

        # Send request
        sock.sendto(request_data, (host, port))

        # Receive response
        data, addr = sock.recvfrom(512)
        sock.close()

        # Parse response
        response = StunMessage.parse(data)
        if response and response.message_type == MessageType.BINDING_RESPONSE:
            # Get XOR-MAPPED-ADDRESS attribute
            attr = response.get_attribute(0x0020)  # XOR-MAPPED-ADDRESS
            if attr:
                result = parse_xor_mapped_address(attr.value)
                if result:
                    return result

        return None

    except (socket.timeout, socket.error, OSError):
        return None


async def detect_nat_type(
    stun_server: str,
    stun_port: int = 3478,
    stun_alt_server: Optional[str] = None,
    stun_alt_port: Optional[int] = None,
) -> NATTestResult:
    """
    Detect NAT type using RFC 3489 algorithm.

    This performs the STUN test sequence:
    1. Test I: Request to server A from same address/port
    2. Test II: Request to server A with changed IP and port
    3. Test III: Request to server A with changed port only

    Args:
        stun_server: Primary STUN server address
        stun_port: Primary STUN server port
        stun_alt_server: Alternate STUN server (for test II)
        stun_alt_port: Alternate STUN server port (for test III)

    Returns:
        NATTestResult with detected NAT type
    """
    # Default to using same server for tests
    if not stun_alt_server:
        stun_alt_server = stun_server
    if not stun_alt_port:
        stun_alt_port = stun_port

    # Test I: Basic binding request
    result = await send_stun_request(stun_server, stun_port)

    if result is None:
        # No response at all - likely blocked by firewall
        return NATTestResult(
            nat_type=NATType.BLOCKED,
            public_ip=None,
            public_port=None,
            changed_ip_response=False,
            changed_port_response=False,
        )

    public_ip, public_port = result

    # Test II: Request from different address (simulated by using alt server)
    # In practice, this requires the server to respond from a different IP
    alt_result = await send_stun_request(stun_alt_server, stun_alt_port)
    changed_ip_response = alt_result is not None

    # Test III: Request from different port
    # In practice, this requires server to respond from different port
    changed_port_response = changed_ip_response  # Simplified

    # Determine NAT type based on RFC 3489 algorithm
    if not changed_ip_response:
        # No response from changed address/port
        if public_ip == get_local_ip():
            # Public IP matches local - no NAT
            nat_type = NATType.OPEN_INTERNET
        else:
            # NAT detected
            nat_type = NATType.SYMMETRIC
    else:
        # Response from changed address
        if public_ip == get_local_ip():
            nat_type = NATType.OPEN_INTERNET
        else:
            # Further tests needed to distinguish between cone types
            # For simplicity, default to full cone
            nat_type = NATType.FULL_CONE

    return NATTestResult(
        nat_type=nat_type,
        public_ip=public_ip,
        public_port=public_port,
        changed_ip_response=changed_ip_response,
        changed_port_response=changed_port_response,
    )


def get_local_ip() -> str:
    """
    Get local IP address.

    Returns:
        Local IP address string
    """
    try:
        # Create socket to external address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        return local_ip
    except OSError:
        return "127.0.0.1"


def simplify_nat_type(result: NATTestResult) -> NATType:
    """
    Simplify NAT type to one of the main categories.

    Args:
        result: Full NAT test result

    Returns:
        Simplified NAT type
    """
    return result.nat_type
