"""
STUN Server - NAT Traversal Server

Implements RFC 5389 STUN protocol for NAT detection and public IP discovery.
"""

__version__ = "0.1.0"

from .messages import (
    ErrorCode,
    MAGIC_COOKIE,
    AttributeType,
    MessageType,
    StunMessage,
    StunAttribute,
)
from .nat_detection import NATType, detect_nat_type, get_local_ip
from .server import STUNServer

__all__ = [
    "STUNServer",
    "NATType",
    "detect_nat_type",
    "get_local_ip",
    "ErrorCode",
    "MAGIC_COOKIE",
    "AttributeType",
    "MessageType",
    "StunMessage",
    "StunAttribute",
]
