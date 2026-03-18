"""
P2P Platform Client SDK (Python)

A Python SDK for P2P device communication with NAT traversal,
UDP hole punching, and automatic relay fallback.
"""

from .client import P2PClient
from .nat_detection import NATType, detect_nat_type
from .exceptions import (
    P2PError,
    ConnectionError,
    NATDetectionError,
    RelayError,
    TimeoutError,
)

__version__ = "0.1.0"
__all__ = [
    "P2PClient",
    "NATType",
    "detect_nat_type",
    "P2PError",
    "ConnectionError",
    "NATDetectionError",
    "RelayError",
    "TimeoutError",
]
