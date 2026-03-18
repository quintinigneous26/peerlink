"""
Simplified protobuf definitions for Noise handshake payload.

This file contains protobuf message definitions for the libp2p Noise
handshake protocol.

Reference: https://github.com/libp2p/specs/blob/master/noise/README.md
"""
import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NoiseExtensions:
    """
    Noise extensions for protocol negotiation.

    Contains stream muxer advertisements and other extensions.
    """
    webtransport_certhashes: list[bytes] = field(default_factory=list)
    stream_muxers: list[str] = field(default_factory=list)

    def to_bytes(self) -> bytes:
        """Serialize to bytes (JSON format for simplicity)."""
        return json.dumps({
            "webtransport_certhashes": [
                h.hex() for h in self.webtransport_certhashes
            ],
            "stream_muxers": self.stream_muxers,
        }).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "NoiseExtensions":
        """Deserialize from bytes."""
        if not data:
            return cls()
        try:
            obj = json.loads(data.decode("utf-8"))
            return cls(
                webtransport_certhashes=[
                    bytes.fromhex(h) for h in obj.get("webtransport_certhashes", [])
                ],
                stream_muxers=obj.get("stream_muxers", []),
            )
        except (json.JSONDecodeError, ValueError):
            return cls()

    def extend(self, items: list[str]) -> None:
        """Deprecated: Use direct assignment instead."""
        # For backward compatibility
        if items and isinstance(items[0], str):
            self.stream_muxers.extend(items)

    def CopyFrom(self, other: "NoiseExtensions") -> None:
        """Copy from another NoiseExtensions instance."""
        self.webtransport_certhashes = list(other.webtransport_certhashes)
        self.stream_muxers = list(other.stream_muxers)


@dataclass
class NoiseHandshakePayload:
    """
    libp2p Noise handshake payload.

    Contains identity key, signature, and extensions for
    authenticating the Noise static key and advertising capabilities.
    """
    identity_key: Optional[bytes] = None
    identity_sig: Optional[bytes] = None
    extensions: Optional[NoiseExtensions] = None

    def SerializeToString(self) -> bytes:
        """Serialize to protobuf-like format."""
        # Use a simple format for compatibility
        result = bytearray()

        if self.identity_key:
            # Field 1 (identity_key), type 2 (length-delimited)
            _encode_field(result, 1, self.identity_key)

        if self.identity_sig:
            # Field 2 (identity_sig), type 2
            _encode_field(result, 2, self.identity_sig)

        if self.extensions:
            # Field 4 (extensions), type 2
            ext_bytes = self.extensions.to_bytes()
            _encode_field(result, 4, ext_bytes)

        return bytes(result)

    def ParseFromString(self, data: bytes) -> None:
        """Parse from protobuf-like format."""
        pos = 0

        while pos < len(data):
            tag, pos = _decode_varint(data, pos)
            field_num = tag >> 3
            wire_type = tag & 0x07

            if wire_type == 2:  # Length-delimited
                length, pos = _decode_varint(data, pos)
                value = data[pos:pos + length]
                pos += length

                if field_num == 1:
                    self.identity_key = value
                elif field_num == 2:
                    self.identity_sig = value
                elif field_num == 4:
                    self.extensions = NoiseExtensions.from_bytes(value)
            else:
                # Skip unknown wire types
                if wire_type == 0:  # Varint
                    _, pos = _decode_varint(data, pos)
                elif wire_type == 5:  # 32-bit
                    pos += 4

    def HasField(self, field_name: str) -> bool:
        """Check if field is set."""
        if field_name == "identity_key":
            return self.identity_key is not None
        if field_name == "identity_sig":
            return self.identity_sig is not None
        if field_name == "extensions":
            return self.extensions is not None
        return False

    def Clear(self) -> None:
        """Clear all fields."""
        self.identity_key = None
        self.identity_sig = None
        self.extensions = None


def _encode_field(buf: bytearray, field_num: int, value: bytes) -> None:
    """Encode a length-delimited field."""
    tag = (field_num << 3) | 2  # Wire type 2 (length-delimited)
    _encode_varint(buf, tag)
    _encode_varint(buf, len(value))
    buf.extend(value)


def _encode_varint(buf: bytearray, value: int) -> None:
    """Encode a varint."""
    if value == 0:
        buf.append(0)
        return
    while value > 0x7F:
        buf.append((value & 0x7F) | 0x80)
        value >>= 7
    buf.append(value)


def _decode_varint(data: bytes, pos: int) -> tuple[int, int]:
    """Decode a varint, returns (value, new_pos)."""
    value = 0
    shift = 0

    while pos < len(data):
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7

    return value, pos
