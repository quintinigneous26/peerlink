"""
DID Service Data Models
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import secrets
import json


class DeviceStatus(str, Enum):
    """Device connection status."""

    ONLINE = "online"
    OFFLINE = "offline"


class DeviceType(str, Enum):
    """Device type classification."""

    IOS = "ios"
    ANDROID = "android"
    WEB = "web"
    DESKTOP = "desktop"


@dataclass
class DeviceInfo:
    """Device information stored in Redis."""

    device_id: str
    device_type: str
    public_key: str
    capabilities: list[str]
    status: DeviceStatus
    created_at: int
    last_seen: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "public_key": self.public_key,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceInfo":
        """Create from dictionary."""
        return cls(
            device_id=data["device_id"],
            device_type=data["device_type"],
            public_key=data["public_key"],
            capabilities=data.get("capabilities", []),
            status=DeviceStatus(data.get("status", DeviceStatus.OFFLINE)),
            created_at=data["created_at"],
            last_seen=data["last_seen"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class DeviceRegistration:
    """Result of device registration."""

    device_id: str
    public_key: str
    private_key: str
    device_type: str
    created_at: int


@dataclass
class TokenResponse:
    """JWT token response."""

    token: str
    expires_in: int
    device_id: str


@dataclass
class APIResponse:
    """Standard API response wrapper."""

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
        # Remove None values
        return {k: v for k, v in result.items() if v is not None}


@dataclass
class HeartbeatInfo:
    """Heartbeat information."""

    device_id: str
    timestamp: int
    status: DeviceStatus = DeviceStatus.ONLINE
