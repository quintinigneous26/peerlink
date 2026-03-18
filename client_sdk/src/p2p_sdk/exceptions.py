"""
P2P SDK Exception Classes
"""


class P2PError(Exception):
    """Base exception for all P2P SDK errors."""

    pass


class ConnectionError(P2PError):
    """Raised when connection establishment fails."""

    pass


class NATDetectionError(P2PError):
    """Raised when NAT type detection fails."""

    pass


class RelayError(P2PError):
    """Raised when relay connection fails."""

    pass


class TimeoutError(P2PError):
    """Raised when an operation times out."""

    pass


class ChannelError(P2PError):
    """Raised when channel operation fails."""

    pass


class AuthenticationError(P2PError):
    """Raised when authentication fails."""

    pass
