"""
Identify Protocol Implementation

This module implements the libp2p Identify protocol v1.0.0 for peer
identity exchange. It supports both query (/ipfs/id/1.0.0) and
push (/ipfs/id/push/1.0.0) modes.

The implementation extends the standard libp2p Identify message with
carrier-specific information (ISP, NAT type, device vendor) through
an extension field, maintaining backward compatibility.
"""
import asyncio
import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Any

from ..types import ISP, NATType, DeviceVendor, Region

logger = logging.getLogger(__name__)

# Protocol IDs
PROTOCOL_ID = "/ipfs/id/1.0.0"
PROTOCOL_PUSH_ID = "/ipfs/id/push/1.0.0"

# Default agent version
DEFAULT_AGENT_VERSION = "p2p-platform/2.0.0"
DEFAULT_PROTOCOL_VERSION = "/ipfs/0.1.0"


@dataclass
class IdentifyExtension:
    """
    Extension data for Identify message.

    Contains carrier-specific and network environment information
    that extends the standard libp2p Identify protocol.
    """
    isp: ISP = ISP.UNKNOWN
    nat_type: NATType = NATType.UNKNOWN
    device_vendor: DeviceVendor = DeviceVendor.UNKNOWN
    nat_level: int = 1
    is_cgnat: bool = False
    ipv6_available: bool = False
    region: Region = Region.OVERSEAS

    def to_dict(self) -> dict:
        """Convert extension to dictionary for serialization."""
        return {
            "isp": self.isp.value,
            "nat_type": self.nat_type.value,
            "device_vendor": self.device_vendor.value,
            "nat_level": self.nat_level,
            "is_cgnat": self.is_cgnat,
            "ipv6_available": self.ipv6_available,
            "region": self.region.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IdentifyExtension":
        """Create extension from dictionary."""
        return cls(
            isp=ISP(data.get("isp", "unknown")),
            nat_type=NATType(data.get("nat_type", "unknown")),
            device_vendor=DeviceVendor(data.get("device_vendor", "unknown")),
            nat_level=data.get("nat_level", 1),
            is_cgnat=data.get("is_cgnat", False),
            ipv6_available=data.get("ipv6_available", False),
            region=Region(data.get("region", "overseas")),
        )

    def to_bytes(self) -> bytes:
        """Serialize extension to bytes (JSON format)."""
        return json.dumps(self.to_dict()).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> "IdentifyExtension":
        """Deserialize extension from bytes."""
        if not data:
            return cls()
        try:
            return cls.from_dict(json.loads(data.decode("utf-8")))
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse Identify extension: {e}")
            return cls()


@dataclass
class IdentifyMessage:
    """
    Identify message data structure.

    Represents the complete identity information exchanged between peers.
    Includes standard libp2p fields plus custom extension data.
    """
    protocol_version: str = DEFAULT_PROTOCOL_VERSION
    agent_version: str = DEFAULT_AGENT_VERSION
    public_key: bytes = b""
    listen_addrs: list[bytes] = field(default_factory=list)
    observed_addr: bytes = b""
    protocols: list[str] = field(default_factory=list)

    # Extension fields for carrier-specific info
    ext: IdentifyExtension = field(default_factory=IdentifyExtension)

    def to_protobuf_dict(self) -> dict:
        """
        Convert to protobuf-compatible dictionary.

        Returns a dict with optional fields set only if they have values,
        following protobuf semantics.
        """
        result = {}

        if self.protocol_version:
            result["protocolVersion"] = self.protocol_version
        if self.agent_version:
            result["agentVersion"] = self.agent_version
        if self.public_key:
            result["publicKey"] = self.public_key
        if self.listen_addrs:
            result["listenAddrs"] = self.listen_addrs
        if self.observed_addr:
            result["observedAddr"] = self.observed_addr
        if self.protocols:
            result["protocols"] = self.protocols

        # Always include extension data (even if empty) for compatibility
        ext_bytes = self.ext.to_bytes()
        if ext_bytes:
            result["ext"] = ext_bytes

        return result

    def to_json_dict(self) -> dict:
        """
        Convert to JSON-serializable dictionary.

        Similar to to_protobuf_dict but encodes bytes fields as base64 strings
        for JSON serialization.
        """
        result = {}

        if self.protocol_version:
            result["protocolVersion"] = self.protocol_version
        if self.agent_version:
            result["agentVersion"] = self.agent_version
        if self.public_key:
            result["publicKey"] = base64.b64encode(self.public_key).decode("ascii")
        if self.listen_addrs:
            result["listenAddrs"] = [
                base64.b64encode(addr).decode("ascii") for addr in self.listen_addrs
            ]
        if self.observed_addr:
            result["observedAddr"] = base64.b64encode(self.observed_addr).decode("ascii")
        if self.protocols:
            result["protocols"] = self.protocols

        # Extension data
        ext_bytes = self.ext.to_bytes()
        if ext_bytes:
            result["ext"] = base64.b64encode(ext_bytes).decode("ascii")

        return result

    @classmethod
    def from_protobuf_dict(cls, data: dict) -> "IdentifyMessage":
        """Create IdentifyMessage from protobuf dictionary."""
        ext_data = data.get("ext", b"")
        # Handle both bytes and base64-encoded strings
        if isinstance(ext_data, str):
            ext_data = base64.b64decode(ext_data)
        extension = IdentifyExtension.from_bytes(ext_data)

        # Handle bytes fields that might be base64-encoded
        public_key = data.get("publicKey", b"")
        if isinstance(public_key, str):
            public_key = base64.b64decode(public_key)

        listen_addrs = data.get("listenAddrs", [])
        decoded_listen_addrs = []
        for addr in listen_addrs:
            if isinstance(addr, str):
                decoded_listen_addrs.append(base64.b64decode(addr))
            else:
                decoded_listen_addrs.append(addr)

        observed_addr = data.get("observedAddr", b"")
        if isinstance(observed_addr, str):
            observed_addr = base64.b64decode(observed_addr)

        return cls(
            protocol_version=data.get("protocolVersion", DEFAULT_PROTOCOL_VERSION),
            agent_version=data.get("agentVersion", ""),
            public_key=public_key,
            listen_addrs=decoded_listen_addrs,
            observed_addr=observed_addr,
            protocols=data.get("protocols", []),
            ext=extension,
        )


class ConnectionWrapper:
    """
    Wrapper for network connections.

    Abstracts the underlying transport (TCP, WebSocket, etc.)
    to provide a consistent interface for protocol operations.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._closed = False

    async def send(self, data: bytes) -> None:
        """Send data with length prefix."""
        if self._closed:
            raise RuntimeError("Connection is closed")

        # Use variable-length length prefix (varint)
        length = len(data)
        length_bytes = bytearray()
        while length > 0x7F:
            length_bytes.append((length & 0x7F) | 0x80)
            length >>= 7
        length_bytes.append(length)

        self.writer.write(bytes(length_bytes))
        self.writer.write(data)
        await self.writer.drain()

    async def recv(self) -> bytes:
        """Receive data with length prefix."""
        if self._closed:
            raise RuntimeError("Connection is closed")

        # Read varint length
        length = 0
        shift = 0
        while True:
            byte = await self.reader.readexactly(1)
            b = ord(byte)
            length |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7

        # Read data
        if length > 0:
            return await self.reader.readexactly(length)
        return b""

    async def close(self) -> None:
        """Close the connection."""
        if self._closed:
            return

        self._closed = True
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as e:
            logger.debug(f"Error closing connection: {e}")

    @property
    def closed(self) -> bool:
        """Check if connection is closed."""
        return self._closed

    def get_remote_address(self) -> tuple[str, int]:
        """Get remote address."""
        return self.writer.get_extra_info("peername") or ("", 0)


class IdentifyProtocol:
    """
    Identify protocol handler.

    Implements both the query and push variants of the Identify protocol.
    """

    def __init__(
        self,
        protocol_version: str = DEFAULT_PROTOCOL_VERSION,
        agent_version: str = DEFAULT_AGENT_VERSION,
    ):
        self.protocol_version = protocol_version
        self.agent_version = agent_version
        self._supported_protocols: list[str] = [
            PROTOCOL_ID,
            PROTOCOL_PUSH_ID,
            "/mplex/6.7.0",
            "/yamux/1.0.0",
        ]

    async def exchange(
        self,
        conn: ConnectionWrapper,
        local_info: Optional[IdentifyMessage] = None,
    ) -> IdentifyMessage:
        """
        Perform Identify exchange (query mode).

        Opens a stream to the remote peer and sends an empty message
        to request their identity information.

        Args:
            conn: Connection wrapper for the network stream
            local_info: Optional local identity info to send

        Returns:
            IdentifyMessage from the remote peer

        Raises:
            RuntimeError: If connection fails or times out
        """
        logger.debug("Starting Identify exchange")

        try:
            # Send local info if provided (for future bidirectional exchange)
            if local_info:
                await self._send_message(conn, local_info)

            # Receive remote identity
            remote_info = await self._recv_message(conn)

            logger.debug(
                f"Identify exchange completed: "
                f"agent={remote_info.agent_version}, "
                f"protocols={len(remote_info.protocols)}"
            )

            return remote_info

        except asyncio.TimeoutError:
            logger.error("Identify exchange timed out")
            raise RuntimeError("Identify exchange timeout")
        except Exception as e:
            logger.error(f"Identify exchange failed: {e}")
            raise RuntimeError(f"Identify exchange failed: {e}")

    async def push(
        self,
        conn: ConnectionWrapper,
        info: IdentifyMessage,
    ) -> None:
        """
        Push identity information to remote peer.

        Sends local identity information without expecting a response.
        Used to notify peers of runtime changes.

        Args:
            conn: Connection wrapper for the network stream
            info: Local identity information to push

        Raises:
            RuntimeError: If push fails
        """
        logger.debug("Pushing Identify update")

        try:
            await self._send_message(conn, info)
            logger.debug("Identify push completed")

        except Exception as e:
            logger.error(f"Identify push failed: {e}")
            raise RuntimeError(f"Identify push failed: {e}")

    async def handle_query(
        self,
        conn: ConnectionWrapper,
        local_info: IdentifyMessage,
    ) -> None:
        """
        Handle incoming Identify query.

        Responds to a remote peer's identity request with local information.

        Args:
            conn: Connection wrapper for the network stream
            local_info: Local identity information to send

        Raises:
            RuntimeError: If handler fails
        """
        logger.debug("Handling Identify query")

        try:
            # Receive request (may be empty)
            try:
                await self._recv_message(conn)
            except asyncio.IncompleteReadError:
                # Empty request is valid
                pass

            # Send local identity
            await self._send_message(conn, local_info)

            logger.debug("Identify query handled")

        except Exception as e:
            logger.error(f"Failed to handle Identify query: {e}")
            raise RuntimeError(f"Failed to handle Identify query: {e}")

    async def _send_message(self, conn: ConnectionWrapper, info: IdentifyMessage) -> None:
        """Send Identify message over connection."""
        # Use JSON encoding with base64 for bytes fields
        msg_dict = info.to_json_dict()
        json_bytes = json.dumps(msg_dict).encode("utf-8")

        await conn.send(json_bytes)

    async def _recv_message(self, conn: ConnectionWrapper) -> IdentifyMessage:
        """Receive Identify message from connection."""
        data = await conn.recv()

        if not data:
            return IdentifyMessage()

        msg_dict = json.loads(data.decode("utf-8"))
        return IdentifyMessage.from_protobuf_dict(msg_dict)

    def create_local_info(
        self,
        public_key: bytes,
        listen_addrs: list[bytes],
        protocols: Optional[list[str]] = None,
        extension: Optional[IdentifyExtension] = None,
    ) -> IdentifyMessage:
        """
        Create local Identify message.

        Args:
            public_key: Local public key
            listen_addrs: List of listen addresses (multiaddr encoded)
            protocols: Supported protocols (defaults to configured list)
            extension: Extension data (defaults to empty extension)

        Returns:
            IdentifyMessage with local information
        """
        return IdentifyMessage(
            protocol_version=self.protocol_version,
            agent_version=self.agent_version,
            public_key=public_key,
            listen_addrs=listen_addrs,
            protocols=protocols or self._supported_protocols,
            ext=extension or IdentifyExtension(),
        )

    def update_protocols(self, protocols: list[str]) -> None:
        """Update list of supported protocols."""
        self._supported_protocols = protocols.copy()
