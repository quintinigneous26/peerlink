"""
TURN Protocol Messages (RFC 8656)

Implements TURN protocol messages for relay allocation and data relay.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Tuple


# STUN/TURN shared constants
MAGIC_COOKIE = 0x2112A442


class MessageType(IntEnum):
    """STUN Message Types."""

    BINDING_REQUEST = 0x0001
    BINDING_RESPONSE = 0x0101
    BINDING_ERROR_RESPONSE = 0x0111


class AttributeType(IntEnum):
    """STUN Attribute Types."""

    MAPPED_ADDRESS = 0x0001
    XOR_MAPPED_ADDRESS = 0x0020
    ERROR_CODE = 0x0009
    UNKNOWN_ATTRIBUTES = 0x000A
    SOFTWARE = 0x8022
    ALTERNATE_SERVER = 0x8023
    FINGERPRINT = 0x8028


class ErrorCode(IntEnum):
    """STUN Error Codes."""

    TRY_ALTERNATE = 300
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    UNKNOWN_ATTRIBUTE = 420
    STALE_NONCE = 438
    SERVER_ERROR = 500


@dataclass
class StunAttribute:
    """STUN Attribute."""

    type: int
    value: bytes


@dataclass
class StunMessage:
    """STUN Message."""

    message_type: int
    message_length: int
    magic_cookie: int
    transaction_id: bytes
    attributes: List[StunAttribute]


class TurnMethod(IntEnum):
    """TURN methods."""

    ALLOCATE = 0x0003
    REFRESH = 0x0004
    SEND = 0x0006
    DATA = 0x0007
    CREATE_PERMISSION = 0x0008
    CHANNEL_BIND = 0x0009


class TurnAttributeType(IntEnum):
    """TURN-specific attributes."""

    CHANNEL_NUMBER = 0x000C
    LIFETIME = 0x000D
    XOR_PEER_ADDRESS = 0x0012
    DATA = 0x0013
    XOR_RELAYED_ADDRESS = 0x0016
    EVEN_PORT = 0x0018
    REQUESTED_TRANSPORT = 0x0019
    DONT_FRAGMENT = 0x001A
    TIMER_VAL = 0x0021
    RESERVATION_TOKEN = 0x0022


class TurnErrorCode(IntEnum):
    """TURN error codes."""

    ALLOCATION_MISMATCH = 437
    STALE_NONCE = 438
    WRONG_CREDENTIALS = 441
    UNSUPPORTED_TRANSPORT_PROTOCOL = 442
    ALLOCATION_QUOTA_REACHED = 486
    INSUFFICIENT_CAPACITY = 508


@dataclass
class TurnAllocation:
    """
    TURN allocation represents a relay session.

    Attributes:
        allocation_id: Unique allocation identifier
        client_addr: Client's (ip, port)
        relay_addr: Relay server's (ip, port) for this allocation
        peer_addr: Peer's (ip, port) if connected
        lifetime: Allocation lifetime in seconds
        transport: Transport protocol (UDP/TCP)
        channel_number: Channel number if using channel binding
        permissions: List of allowed peer addresses
        bytes_received: Total bytes received from peer
        bytes_sent: Total bytes sent to peer
        created_at: Timestamp when allocation was created
    """

    allocation_id: str
    client_addr: Tuple[str, int]
    relay_addr: Tuple[str, int]
    peer_addr: Optional[Tuple[str, int]] = None
    lifetime: int = 600  # 10 minutes default
    transport: str = "udp"
    channel_number: Optional[int] = None
    permissions: List[Tuple[str, int]] = None
    bytes_received: int = 0
    bytes_sent: int = 0
    created_at: float = 0

    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []
        if self.created_at == 0:
            import time
            self.created_at = time.time()

    def is_expired(self) -> bool:
        """Check if allocation has expired."""
        import time
        return time.time() - self.created_at > self.lifetime

    def get_remaining_time(self) -> int:
        """Get remaining lifetime in seconds."""
        import time
        return max(0, self.lifetime - int(time.time() - self.created_at))

    def add_permission(self, peer_addr: Tuple[str, int]) -> bool:
        """
        Add permission for a peer address.

        Args:
            peer_addr: Peer's (ip, port)

        Returns:
            True if permission was added, False if already exists
        """
        if peer_addr not in self.permissions:
            self.permissions.append(peer_addr)
            return True
        return False

    def has_permission(self, peer_addr: Tuple[str, int]) -> bool:
        """
        Check if peer has permission.

        Args:
            peer_addr: Peer's (ip, port)

        Returns:
            True if permission exists
        """
        return peer_addr in self.permissions

    def record_received(self, bytes_count: int):
        """Record received bytes."""
        self.bytes_received += bytes_count

    def record_sent(self, bytes_count: int):
        """Record sent bytes."""
        self.bytes_sent += bytes_count

    def get_stats(self) -> dict:
        """Get allocation statistics."""
        import time
        return {
            "allocation_id": self.allocation_id,
            "client_addr": f"{self.client_addr[0]}:{self.client_addr[1]}",
            "relay_addr": f"{self.relay_addr[0]}:{self.relay_addr[1]}",
            "peer_addr": f"{self.peer_addr[0]}:{self.peer_addr[1]}" if self.peer_addr else None,
            "lifetime": self.lifetime,
            "remaining": self.get_remaining_time(),
            "transport": self.transport,
            "bytes_received": self.bytes_received,
            "bytes_sent": self.bytes_sent,
            "uptime": int(time.time() - self.created_at),
        }


def create_xor_address_attr(ip: str, port: int, transaction_id: bytes) -> bytes:
    """
    Create XOR address attribute (for XOR-MAPPED-ADDRESS, XOR-PEER-ADDRESS, XOR-RELAYED-ADDRESS).

    Args:
        ip: IP address string
        port: Port number
        transaction_id: 96-bit transaction ID

    Returns:
        Attribute value bytes
    """
    cookie_bytes = struct.pack("!I", MAGIC_COOKIE)

    # Determine IP family
    if "." in ip:
        family = 0x01  # IPv4
        ip_bytes = bytes(map(int, ip.split(".")))

        # XOR port with (magic_cookie >> 16)
        xor_port = port ^ ((MAGIC_COOKIE >> 16) & 0xFFFF)

        # XOR IP with magic cookie
        xor_ip = bytes(ip_bytes[i] ^ cookie_bytes[i] for i in range(4))
    else:
        family = 0x02  # IPv6
        ip_bytes = bytes.fromhex(ip.replace(":", ""))

        # XOR port
        xor_port = port ^ ((MAGIC_COOKIE >> 16) & 0xFFFF)

        # XOR IP with magic cookie + transaction ID
        xor_ip = bytes(
            ip_bytes[i] ^ (cookie_bytes[i % 4] if i < 4 else transaction_id[i - 4])
            for i in range(16)
        )

    return struct.pack("!BBH", 0, family, xor_port) + xor_ip


def create_lifetime_attr(lifetime: int) -> bytes:
    """
    Create LIFETIME attribute.

    Args:
        lifetime: Lifetime in seconds

    Returns:
        Attribute value bytes
    """
    return struct.pack("!I", lifetime)


def create_requested_transport_attr(protocol: int = 17) -> bytes:
    """
    Create REQUESTED-TRANSPORT attribute.

    Args:
        protocol: Protocol number (17 = UDP)

    Returns:
        Attribute value bytes
    """
    return struct.pack("!I", protocol)


def parse_lifetime_attr(data: bytes) -> int:
    """
    Parse LIFETIME attribute.

    Args:
        data: Attribute value bytes

    Returns:
        Lifetime in seconds
    """
    if len(data) >= 4:
        return struct.unpack("!I", data[:4])[0]
    return 0
