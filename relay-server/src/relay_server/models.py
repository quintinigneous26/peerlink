"""
Relay Server Data Models
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple


class TransportProtocol(str, Enum):
    """Transport protocol types."""

    UDP = "udp"
    TCP = "tcp"


class AllocationStatus(str, Enum):
    """Allocation status."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REFRESHED = "refreshed"
    DELETED = "deleted"


@dataclass
class RelaySession:
    """
    Relay session between client and peer.

    Represents an active data relay session.
    """

    session_id: str
    client_addr: Tuple[str, int]
    relay_addr: Tuple[str, int]
    peer_addr: Optional[Tuple[str, int]] = None
    transport: TransportProtocol = TransportProtocol.UDP
    lifetime: int = 600
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    last_activity: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    status: AllocationStatus = AllocationStatus.ACTIVE
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    permissions: list = field(default_factory=list)

    def is_expired(self, timeout: int) -> bool:
        """Check if session has expired based on timeout."""
        import time
        return (time.time() - self.last_activity) > timeout

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        import time
        self.last_activity = int(time.time())

    def add_permission(self, peer_addr: Tuple[str, int]) -> bool:
        """Add permission for peer address."""
        if peer_addr not in self.permissions:
            self.permissions.append(peer_addr)
            return True
        return False

    def has_permission(self, peer_addr: Tuple[str, int]) -> bool:
        """Check if peer has permission."""
        return peer_addr in self.permissions

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "client_addr": f"{self.client_addr[0]}:{self.client_addr[1]}",
            "relay_addr": f"{self.relay_addr[0]}:{self.relay_addr[1]}",
            "peer_addr": f"{self.peer_addr[0]}:{self.peer_addr[1]}" if self.peer_addr else None,
            "transport": self.transport.value,
            "status": self.status.value,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "packets_sent": self.packets_sent,
            "packets_received": self.packets_received,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
        }


@dataclass
class BandwidthStats:
    """Bandwidth statistics."""

    current_bps: float = 0.0  # Bytes per second
    peak_bps: float = 0.0
    total_bytes: int = 0
    window_size: int = 60  # seconds
    _samples: list = field(default_factory=list)

    def add_sample(self, bytes_count: int) -> None:
        """Add a sample."""
        import time
        self._samples.append((time.time(), bytes_count))
        self.total_bytes += bytes_count

        # Clean old samples
        cutoff = time.time() - self.window_size
        self._samples = [s for s in self._samples if s[0] > cutoff]

    def get_current_rate(self) -> float:
        """Get current rate in bytes per second."""
        import time
        if not self._samples:
            return 0.0

        # Calculate rate from recent samples
        total = sum(s[1] for s in self._samples)
        if len(self._samples) < 2:
            return 0.0

        duration = self._samples[-1][0] - self._samples[0][0]
        if duration > 0:
            rate = total / duration
            if rate > self.peak_bps:
                self.peak_bps = rate
            self.current_bps = rate
            return rate

        return 0.0


@dataclass
class APIResponse:
    """Standard API response."""

    success: bool
    data: dict | None = None
    error: dict | None = None
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp,
        }
        return {k: v for k, v in result.items() if v is not None}
