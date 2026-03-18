"""
P2P Protocol Definition

Defines the message formats and protocol for P2P communication.
"""

import json
import struct
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, Tuple


class MessageTypes(Enum):
    """Message type identifiers."""

    HANDSHAKE = "handshake"
    """Connection establishment handshake."""

    HANDSHAKE_ACK = "handshake_ack"
    """Handshake acknowledgment."""

    KEEPALIVE = "keepalive"
    """Keepalive/ping message."""

    CHANNEL_DATA = "channel_data"
    """Data on a specific channel."""

    CHANNEL_OPEN = "channel_open"
    """Open a new channel."""

    CHANNEL_CLOSE = "channel_close"
    """Close a channel."""

    DISCONNECT = "disconnect"
    """Graceful disconnection."""

    ERROR = "error"
    """Error message."""


@dataclass
class P2PMessage:
    """Base P2P message."""

    msg_type: MessageTypes
    sender_did: str
    receiver_did: str
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: Optional[int] = None
    payload: bytes = b""
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def encode(self) -> bytes:
        """Encode message to bytes for transmission."""
        # Create message dict
        msg_dict = {
            "msg_type": self.msg_type.value,
            "sender_did": self.sender_did,
            "receiver_did": self.receiver_did,
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

        # Convert to JSON
        json_bytes = json.dumps(msg_dict).encode("utf-8")

        # Format: [length(4)][json_length(4)][json_bytes][payload]
        header = struct.pack(">II", len(json_bytes) + len(self.payload), len(json_bytes))

        return header + json_bytes + self.payload

    @classmethod
    def decode(cls, data: bytes) -> Optional["P2PMessage"]:
        """Decode message from bytes."""
        try:
            if len(data) < 8:
                return None

            # Parse header
            total_length, json_length = struct.unpack(">II", data[:8])

            if len(data) < total_length + 8:
                return None

            # Parse JSON
            json_bytes = data[8 : 8 + json_length]
            msg_dict = json.loads(json_bytes.decode("utf-8"))

            # Extract payload
            payload = data[8 + json_length : 8 + total_length]

            # Create message
            return cls(
                msg_type=MessageTypes(msg_dict["msg_type"]),
                sender_did=msg_dict["sender_did"],
                receiver_did=msg_dict["receiver_did"],
                message_id=msg_dict.get("message_id", str(uuid.uuid4())),
                channel_id=msg_dict.get("channel_id"),
                payload=payload,
                timestamp=msg_dict.get("timestamp", 0.0),
                metadata=msg_dict.get("metadata", {}),
            )

        except Exception:
            return None


@dataclass
class HandshakeMessage(P2PMessage):
    """Handshake message for connection establishment."""

    public_ip: Optional[str] = None
    public_port: Optional[int] = None
    local_ip: Optional[str] = None
    local_port: Optional[int] = None
    nat_type: Optional[str] = None
    is_ack: bool = False
    capabilities: list = field(default_factory=list)


@dataclass
class ChannelMessage(P2PMessage):
    """Channel-specific message."""

    channel_type: Optional[str] = None
    reliable: bool = True
    priority: int = 0


def create_handshake(
    sender_did: str,
    receiver_did: str,
    public_ip: Optional[str] = None,
    public_port: Optional[int] = None,
    local_ip: Optional[str] = None,
    local_port: Optional[int] = None,
    nat_type: Optional[str] = None,
    is_ack: bool = False,
    capabilities: list = None,
) -> HandshakeMessage:
    """Create a handshake message."""
    msg = HandshakeMessage(
        msg_type=MessageTypes.HANDSHAKE_ACK if is_ack else MessageTypes.HANDSHAKE,
        sender_did=sender_did,
        receiver_did=receiver_did,
        public_ip=public_ip,
        public_port=public_port,
        local_ip=local_ip,
        local_port=local_port,
        nat_type=nat_type,
        is_ack=is_ack,
        capabilities=capabilities or [],
    )
    msg.metadata.update({
        "public_ip": public_ip,
        "public_port": public_port,
        "local_ip": local_ip,
        "local_port": local_port,
        "nat_type": nat_type,
        "is_ack": is_ack,
        "capabilities": capabilities or [],
    })
    return msg


def parse_message(data: bytes) -> Optional[P2PMessage]:
    """Parse incoming message data."""
    return P2PMessage.decode(data)


def create_channel_data(
    sender_did: str,
    receiver_did: str,
    channel_id: int,
    payload: bytes,
) -> P2PMessage:
    """Create a channel data message."""
    return P2PMessage(
        msg_type=MessageTypes.CHANNEL_DATA,
        sender_did=sender_did,
        receiver_did=receiver_did,
        channel_id=channel_id,
        payload=payload,
    )


def create_keepalive(sender_did: str, receiver_did: str) -> P2PMessage:
    """Create a keepalive message."""
    return P2PMessage(
        msg_type=MessageTypes.KEEPALIVE,
        sender_did=sender_did,
        receiver_did=receiver_did,
    )


def create_disconnect(sender_did: str, receiver_did: str, reason: str = "") -> P2PMessage:
    """Create a disconnect message."""
    msg = P2PMessage(
        msg_type=MessageTypes.DISCONNECT,
        sender_did=sender_did,
        receiver_did=receiver_did,
    )
    if reason:
        msg.metadata["reason"] = reason
    return msg
