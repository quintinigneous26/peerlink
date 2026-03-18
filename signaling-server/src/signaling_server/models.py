"""
Signaling Server Data Models
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any
import json


class MessageType(str, Enum):
    """WebSocket message types."""

    # Registration
    REGISTER = "register"
    REGISTERED = "registered"
    UNREGISTER = "unregister"

    # Connection
    CONNECT = "connect"
    CONNECT_REQUEST = "connect_request"
    CONNECT_RESPONSE = "connect_response"
    DISCONNECT = "disconnect"

    # WebRTC signaling
    OFFER = "offer"
    ANSWER = "answer"
    ICE_CANDIDATE = "ice_candidate"

    # Status
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"

    # Discovery
    QUERY_DEVICE = "query_device"
    DEVICE_INFO = "device_info"

    # Relay
    RELAY_REQUEST = "relay_request"
    RELAY_RESPONSE = "relay_response"


class ConnectionStatus(str, Enum):
    """Device connection status."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


class NATType(str, Enum):
    """NAT type for connection strategy."""

    PUBLIC = "public"
    FULL_CONE = "full_cone"
    RESTRICTED_CONE = "restricted_cone"
    PORT_RESTRICTED = "port_restricted"
    SYMMETRIC = "symmetric"
    UNKNOWN = "unknown"


@dataclass
class DeviceInfo:
    """Connected device information."""

    device_id: str
    ws: Any  # WebSocket connection
    public_key: str
    capabilities: list[str]
    nat_type: NATType = NATType.UNKNOWN
    public_ip: str | None = None
    public_port: int | None = None
    connected_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    last_heartbeat: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    status: ConnectionStatus = ConnectionStatus.CONNECTED
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary (without WebSocket)."""
        return {
            "device_id": self.device_id,
            "public_key": self.public_key,
            "capabilities": self.capabilities,
            "nat_type": self.nat_type.value,
            "public_ip": self.public_ip,
            "public_port": self.public_port,
            "connected_at": self.connected_at,
            "last_heartbeat": self.last_heartbeat,
            "status": self.status.value,
            "metadata": self.metadata,
        }


@dataclass
class Message:
    """WebSocket message."""

    type: MessageType
    data: dict
    timestamp: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    source_device_id: str | None = None
    target_device_id: str | None = None
    request_id: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "source_device_id": self.source_device_id,
            "target_device_id": self.target_device_id,
            "request_id": self.request_id,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Create from dictionary."""
        return cls(
            type=MessageType(data.get("type", "unknown")),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", int(datetime.now().timestamp())),
            source_device_id=data.get("source_device_id"),
            target_device_id=data.get("target_device_id"),
            request_id=data.get("request_id"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class ConnectionSession:
    """P2P connection session between two devices."""

    session_id: str
    device_a: str
    device_b: str
    status: ConnectionStatus = ConnectionStatus.CONNECTING
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    offer: str | None = None
    answer: str | None = None
    ice_candidates_a: list[dict] = field(default_factory=list)
    ice_candidates_b: list[dict] = field(default_factory=list)
    use_relay: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "device_a": self.device_a,
            "device_b": self.device_b,
            "status": self.status.value,
            "created_at": self.created_at,
            "use_relay": self.use_relay,
        }


@dataclass
class ErrorResponse:
    """Error response message."""

    code: str
    message: str
    request_id: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "type": MessageType.ERROR.value,
            "data": {
                "code": self.code,
                "message": self.message,
            },
            "timestamp": int(datetime.now().timestamp()),
        }
        if self.request_id:
            result["request_id"] = self.request_id
            result["data"]["request_id"] = self.request_id
        return result


# Error codes
class ErrorCode(str, Enum):
    """Error codes."""

    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
    DEVICE_ALREADY_REGISTERED = "DEVICE_ALREADY_REGISTERED"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    TIMEOUT = "TIMEOUT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
