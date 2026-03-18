"""
STUN Protocol Messages (RFC 5389)

Implements STUN message format and attribute parsing.
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import List, Optional, Tuple


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


# STUN Magic Cookie
MAGIC_COOKIE = 0x2112A442


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

    @classmethod
    def parse(cls, data: bytes) -> Optional["StunMessage"]:
        """
        Parse STUN message from bytes.

        Args:
            data: Raw message bytes

        Returns:
            StunMessage or None if invalid
        """
        if len(data) < 20:
            return None

        # Parse header
        message_type, message_length, magic_cookie = struct.unpack(
            "!HHI", data[:8]
        )

        if magic_cookie != MAGIC_COOKIE:
            return None

        # Extract transaction ID
        transaction_id = data[8:20]

        # Parse attributes
        attributes = []
        offset = 20
        remaining = message_length

        while remaining > 0 and offset + 4 <= len(data):
            attr_type, attr_length = struct.unpack("!HH", data[offset:offset + 4])
            offset += 4

            # Attributes are padded to 4-byte boundary
            padded_length = (attr_length + 3) & ~3

            if offset + padded_length > len(data):
                break

            attr_value = data[offset:offset + attr_length]
            attributes.append(StunAttribute(type=attr_type, value=attr_value))

            offset += padded_length
            remaining -= (4 + padded_length)

        return cls(
            message_type=message_type,
            message_length=message_length,
            magic_cookie=magic_cookie,
            transaction_id=transaction_id,
            attributes=attributes,
        )

    def serialize(self) -> bytes:
        """
        Serialize STUN message to bytes.

        Returns:
            Raw message bytes
        """
        # Serialize attributes
        attr_data = b""
        for attr in self.attributes:
            attr_header = struct.pack("!HH", attr.type, len(attr.value))
            attr_data += attr_header + attr.value
            # Pad to 4-byte boundary
            padding = (4 - (len(attr.value) % 4)) % 4
            attr_data += b"\x00" * padding

        # Update message length
        message_length = len(attr_data)

        # Serialize header
        header = struct.pack(
            "!HHI",
            self.message_type,
            message_length,
            self.magic_cookie,
        )

        return header + self.transaction_id + attr_data

    def get_attribute(self, attr_type: int) -> Optional[StunAttribute]:
        """
        Get attribute by type.

        Args:
            attr_type: Attribute type

        Returns:
            StunAttribute or None
        """
        for attr in self.attributes:
            if attr.type == attr_type:
                return attr
        return None


def parse_mapped_address(data: bytes) -> Optional[Tuple[str, int]]:
    """
    Parse MAPPED-ADDRESS or XOR-MAPPED-ADDRESS attribute.

    Args:
        data: Attribute value bytes

    Returns:
        Tuple of (ip_address, port) or None
    """
    if len(data) < 8:
        return None

    family = data[1]
    if family == 0x01:  # IPv4
        if len(data) < 8:
            return None
        port = struct.unpack("!H", data[2:4])[0]
        ip_bytes = data[4:8]
        ip = ".".join(str(b) for b in ip_bytes)
        return (ip, port)
    elif family == 0x02:  # IPv6
        if len(data) < 20:
            return None
        port = struct.unpack("!H", data[2:4])[0]
        ip_bytes = data[4:20]
        # Convert IPv6 bytes to string
        ip = ":".join(f"{b:02x}{b+1:02x}" for b in range(0, 16, 2))
        return (ip, port)

    return None


def create_mapped_address_attr(ip: str, port: int) -> bytes:
    """
    Create MAPPED-ADDRESS attribute.

    Args:
        ip: IP address string
        port: Port number

    Returns:
        Attribute value bytes
    """
    # Determine IP family
    if "." in ip:
        family = 0x01  # IPv4
        ip_bytes = bytes(map(int, ip.split(".")))
    else:
        family = 0x02  # IPv6
        # Parse IPv6 (simplified)
        ip_bytes = bytes.fromhex(ip.replace(":", ""))

    return struct.pack("!BBHI", 0, family, port, 0) + ip_bytes


def create_xor_mapped_address_attr(
    ip: str, port: int, transaction_id: bytes
) -> bytes:
    """
    Create XOR-MAPPED-ADDRESS attribute (RFC 5389 Section 15.2).

    Args:
        ip: IP address string
        port: Port number
        transaction_id: 96-bit transaction ID

    Returns:
        Attribute value bytes
    """
    # Pack magic cookie and transaction ID into bytes for XOR
    cookie_bytes = struct.pack("!I", MAGIC_COOKIE)

    # Determine IP family
    if "." in ip:
        family = 0x01  # IPv4
        ip_bytes = bytes(map(int, ip.split(".")))

        # XOR port with (magic_cookie >> 16)
        xor_port = port ^ ((MAGIC_COOKIE >> 16) & 0xFFFF)

        # XOR IP with magic cookie (for IPv4, only first 4 bytes of cookie)
        xor_ip = bytes(ip_bytes[i] ^ cookie_bytes[i] for i in range(4))
    else:
        family = 0x02  # IPv6
        # Parse IPv6 (simplified)
        ip_bytes = bytes.fromhex(ip.replace(":", ""))

        # XOR port with (magic_cookie >> 16)
        xor_port = port ^ ((MAGIC_COOKIE >> 16) & 0xFFFF)

        # XOR IP with magic cookie + transaction ID
        xor_ip = bytes(
            ip_bytes[i] ^ (cookie_bytes[i % 4] if i < 4 else transaction_id[i - 4])
            for i in range(16)
        )

    return struct.pack("!BBH", 0, family, xor_port) + xor_ip


def create_error_response(
    transaction_id: bytes, error_code: ErrorCode, message: str
) -> bytes:
    """
    Create STUN error response.

    Args:
        transaction_id: Transaction ID from request
        error_code: Error code
        message: Error message

    Returns:
        Serialized error response
    """
    # Error code attribute format:
    # 0x00 0x00 class (hundreds) number
    class_digit = error_code // 100
    number = error_code % 100

    reason = message.encode("utf-8")
    error_attr = struct.pack("!HHBB", AttributeType.ERROR_CODE, len(reason) + 4, 0, class_digit)
    error_attr += struct.pack("!B", number) + reason

    # Pad to 4-byte boundary
    padding = (4 - ((len(reason) + 4) % 4)) % 4
    error_attr += b"\x00" * padding

    msg = StunMessage(
        message_type=MessageType.BINDING_ERROR_RESPONSE,
        message_length=len(error_attr),
        magic_cookie=MAGIC_COOKIE,
        transaction_id=transaction_id,
        attributes=[StunAttribute(type=AttributeType.ERROR_CODE, value=error_attr[4:])],
    )

    return msg.serialize()
