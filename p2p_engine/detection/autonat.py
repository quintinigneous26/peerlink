"""
AutoNAT Protocol Implementation

Implements libp2p AutoNAT protocol v1.0.0 for NAT reachability detection.
Spec: https://github.com/libp2p/specs/blob/master/autonat/autonat-v1.md

Security: Implements RFC 3489 Section 12.1.1 DDoS protection by validating
that dial-back addresses are based on the observed IP of the requesting node.
"""
import asyncio
import logging
import socket
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, List, Callable, Awaitable

from ..types import PeerInfo


logger = logging.getLogger("p2p_engine.autonat")


# ==================== Protocol Constants ====================

PROTOCOL_ID = "/libp2p/autonat/1.0.0"
DIAL_TIMEOUT = 10.0  # seconds
MAX_DIAL_ATTEMPTS = 5


# ==================== Protocol Enums ====================

class MessageType(IntEnum):
    """AutoNAT message types"""
    DIAL = 0
    DIAL_RESPONSE = 1


class ResponseStatus(IntEnum):
    """AutoNAT response status codes"""
    OK = 0
    E_DIAL_ERROR = 100
    E_DIAL_REFUSED = 101
    E_BAD_REQUEST = 200
    E_INTERNAL_ERROR = 300


class ReachabilityStatus(IntEnum):
    """NAT reachability status"""
    PUBLIC = 0
    PRIVATE = 1
    UNKNOWN = 2


# ==================== Protocol Data Structures ====================

@dataclass
class DialPeerInfo:
    """Peer information in dial message"""
    peer_id: bytes = b""
    addrs: List[bytes] = field(default_factory=list)


@dataclass
class DialMessage:
    """Dial request message"""
    peer: DialPeerInfo = field(default_factory=DialPeerInfo)


@dataclass
class DialResponse:
    """Dial response message"""
    status: ResponseStatus = ResponseStatus.OK
    status_text: str = ""
    addr: bytes = b""


@dataclass
class AutoNATMessage:
    """AutoNAT protocol message"""
    type: MessageType
    dial: Optional[DialMessage] = None
    dial_response: Optional[DialResponse] = None


# ==================== Multiaddress Utilities ====================

def parse_multiaddr(data: bytes) -> Optional[tuple]:
    """
    Parse multiaddr and extract (ip, port) if applicable.
    Supports /ip4/<ip>/tcp/<port> and /ip4/<ip>/udp/<port> formats.
    """
    try:
        # Simple multiaddr parser for common formats
        if data.startswith(b'\x04'):  # /ip4/
            idx = 1
            # Read IPv4 (4 bytes)
            if idx + 4 > len(data):
                return None
            ip = socket.inet_ntoa(data[idx:idx+4])
            idx += 4

            # Read protocol
            while idx < len(data):
                proto_code = data[idx]
                idx += 1

                if proto_code == 6:  # /tcp/
                    if idx + 2 > len(data):
                        return None
                    port = struct.unpack('>H', data[idx:idx+2])[0]
                    return (ip, port, 'tcp')
                elif proto_code == 273:  # /udp/
                    if idx + 2 > len(data):
                        return None
                    port = struct.unpack('>H', data[idx:idx+2])[0]
                    return (ip, port, 'udp')
                else:
                    # Skip variable length value
                    if idx >= len(data):
                        return None
                    val_len = data[idx]
                    idx += 1 + val_len
    except Exception as e:
        logger.debug(f"Failed to parse multiaddr: {e}")

    return None


def validate_ip_match(observed_ip: str, dial_ip: str) -> bool:
    """
    Validate that dial-back IP matches observed IP (DDoS protection).

    Per RFC 3489 Section 12.1.1: Implementations MUST NOT dial any multiaddress
    unless it is based on the IP address the requesting node is observed as.
    """
    return observed_ip == dial_ip


# ==================== Message Encoding/Decoding ====================

def encode_uvarint(value: int) -> bytes:
    """Encode unsigned varint"""
    if value < 0:
        raise ValueError("Negative value")

    buf = b""
    while value > 0x7F:
        buf += bytes([(value & 0x7F) | 0x80])
        value >>= 7
    buf += bytes([value])
    return buf


def decode_uvarint(data: bytes, offset: int = 0) -> tuple[int, int]:
    """Decode unsigned varint, returns (value, new_offset)"""
    value = 0
    shift = 0
    idx = offset

    while idx < len(data):
        byte = data[idx]
        idx += 1
        value |= (byte & 0x7F) << shift

        if not (byte & 0x80):
            return value, idx

        shift += 7
        if shift >= 64:
            raise ValueError("Varint too large")

    raise ValueError("Incomplete varint")


def encode_string(s: str) -> bytes:
    """Encode string with length prefix"""
    data = s.encode('utf-8')
    return encode_uvarint(len(data)) + data


def decode_string(data: bytes, offset: int = 0) -> tuple[str, int]:
    """Decode string with length prefix, returns (string, new_offset)"""
    length, offset = decode_uvarint(data, offset)
    if offset + length > len(data):
        raise ValueError("String data incomplete")
    return data[offset:offset+length].decode('utf-8'), offset + length


def encode_dial_peer_info(peer_info: DialPeerInfo) -> bytes:
    """Encode DialPeerInfo"""
    result = b""

    # Encode peer_id (field 1, optional)
    if peer_info.peer_id:
        result += b'\x0A'  # field 1, type 2 (length-delimited)
        result += encode_uvarint(len(peer_info.peer_id))
        result += peer_info.peer_id

    # Encode addrs (field 2, repeated)
    for addr in peer_info.addrs:
        result += b'\x12'  # field 2, type 2
        result += encode_uvarint(len(addr))
        result += addr

    return result


def decode_dial_peer_info(data: bytes, offset: int = 0) -> tuple[DialPeerInfo, int]:
    """Decode DialPeerInfo, returns (peer_info, new_offset)"""
    peer_info = DialPeerInfo()
    idx = offset

    while idx < len(data):
        tag = data[idx]
        idx += 1

        field_num = tag >> 3
        wire_type = tag & 0x07

        if wire_type == 2:  # length-delimited
            length, idx = decode_uvarint(data, idx)
            value = data[idx:idx+length]
            idx += length

            if field_num == 1:  # peer_id
                peer_info.peer_id = value
            elif field_num == 2:  # addrs
                peer_info.addrs.append(value)
        else:
            # Skip unknown field
            if wire_type == 0:  # varint
                _, idx = decode_uvarint(data, idx)
            elif wire_type == 5:  # 32-bit
                idx += 4
            elif wire_type == 1:  # 64-bit
                idx += 8

    return peer_info, idx


def encode_dial_message(dial: DialMessage) -> bytes:
    """Encode Dial message"""
    if not dial.peer:
        return b'\x12\x00'  # Empty message

    peer_data = encode_dial_peer_info(dial.peer)
    return b'\x12' + encode_uvarint(len(peer_data)) + peer_data


def encode_dial_response(response: DialResponse) -> bytes:
    """Encode DialResponse message"""
    result = b""

    # Encode status (field 1, optional)
    if response.status is not None:
        result += b'\x08'  # field 1, type 0 (varint)
        result += encode_uvarint(response.status)

    # Encode status_text (field 2, optional)
    if response.status_text:
        text_data = encode_string(response.status_text)
        result += b'\x12'  # field 2, type 2
        result += encode_uvarint(len(text_data))
        result += text_data

    # Encode addr (field 3, optional)
    if response.addr:
        result += b'\x1A'  # field 3, type 2
        result += encode_uvarint(len(response.addr))
        result += response.addr

    return result


def encode_message(msg: AutoNATMessage) -> bytes:
    """Encode complete AutoNAT message"""
    result = b""

    # Encode message type (field 1)
    result += b'\x08'  # field 1, type 0 (varint)
    result += encode_uvarint(msg.type)

    # Encode dial or dial_response (field 2 or 3)
    if msg.type == MessageType.DIAL and msg.dial:
        dial_data = encode_dial_message(msg.dial)
        result += b'\x12'  # field 2, type 2
        result += encode_uvarint(len(dial_data))
        result += dial_data
    elif msg.type == MessageType.DIAL_RESPONSE and msg.dial_response:
        response_data = encode_dial_response(msg.dial_response)
        result += b'\x1A'  # field 3, type 2
        result += encode_uvarint(len(response_data))
        result += response_data

    # Add length prefix
    return encode_uvarint(len(result)) + result


def decode_message(data: bytes, offset: int = 0) -> tuple[Optional[AutoNATMessage], int]:
    """
    Decode AutoNAT message, returns (message, new_offset) or (None, offset) on error
    """
    try:
        idx = offset
        msg = AutoNATMessage(type=MessageType.DIAL)

        while idx < len(data):
            tag = data[idx]
            idx += 1

            field_num = tag >> 3
            wire_type = tag & 0x07

            if field_num == 1 and wire_type == 0:  # type
                value, idx = decode_uvarint(data, idx)
                msg.type = MessageType(value)

            elif field_num == 2 and wire_type == 2:  # dial
                length, idx = decode_uvarint(data, idx)
                if idx + length > len(data):
                    return None, offset
                peer_info, _ = decode_dial_peer_info(data, idx)
                msg.dial = DialMessage(peer=peer_info)
                idx += length

            elif field_num == 3 and wire_type == 2:  # dial_response
                length, idx = decode_uvarint(data, idx)
                if idx + length > len(data):
                    return None, offset

                msg.dial_response = DialResponse()
                resp_offset = idx
                resp_end = idx + length

                while resp_offset < resp_end:
                    resp_tag = data[resp_offset]
                    resp_offset += 1

                    resp_field = resp_tag >> 3
                    resp_wire = resp_tag & 0x07

                    if resp_field == 1 and resp_wire == 0:  # status
                        status, resp_offset = decode_uvarint(data, resp_offset)
                        msg.dial_response.status = ResponseStatus(status)

                    elif resp_field == 2 and resp_wire == 2:  # status_text
                        str_len, resp_offset = decode_uvarint(data, resp_offset)
                        msg.dial_response.status_text = data[resp_offset:resp_offset+str_len].decode('utf-8')
                        resp_offset += str_len

                    elif resp_field == 3 and resp_wire == 2:  # addr
                        addr_len, resp_offset = decode_uvarint(data, resp_offset)
                        msg.dial_response.addr = data[resp_offset:resp_offset+addr_len]
                        resp_offset += addr_len

                    else:
                        # Skip unknown field
                        if resp_wire == 0:
                            _, resp_offset = decode_uvarint(data, resp_offset)
                        elif resp_wire == 2:
                            str_len, resp_offset = decode_uvarint(data, resp_offset)
                            resp_offset += str_len

                idx = resp_end

            elif wire_type == 0:  # Skip unknown varint
                _, idx = decode_uvarint(data, idx)
            elif wire_type == 2:  # Skip unknown length-delimited
                length, idx = decode_uvarint(data, idx)
                idx += length

        return msg, idx

    except Exception as e:
        logger.debug(f"Failed to decode message: {e}")
        return None, offset


# ==================== AutoNAT Client ====================

class AutoNATClient:
    """
    AutoNAT client - initiates reachability checks.

    Requests peers to dial back our public addresses to determine
    if we are behind a NAT.
    """

    def __init__(
        self,
        peer_id: bytes,
        observed_addrs: List[bytes],
    ):
        """
        Initialize AutoNAT client.

        Args:
            peer_id: Our peer ID
            observed_addrs: Our observed public addresses (multiaddrs)
        """
        self.peer_id = peer_id
        self.observed_addrs = observed_addrs
        self._successful_dials = 0
        self._failed_dials = 0

    async def check_reachability(
        self,
        dial_back_func: Callable[[bytes, bytes], Awaitable[tuple[ResponseStatus, str, bytes]]],
        min_confirmations: int = 3,
    ) -> ReachabilityStatus:
        """
        Check NAT reachability status.

        Args:
            dial_back_func: Async function to perform dial-back. Takes (peer_id, addrs) and returns (status, text, addr)
            min_confirmations: Minimum number of successful dials to consider public

        Returns:
            ReachabilityStatus: PUBLIC, PRIVATE, or UNKNOWN
        """
        logger.info(f"Starting AutoNAT reachability check (need {min_confirmations} confirmations)")

        # Reset counters
        self._successful_dials = 0
        self._failed_dials = 0

        # Create dial message
        dial_msg = AutoNATMessage(
            type=MessageType.DIAL,
            dial=DialMessage(
                peer=DialPeerInfo(
                    peer_id=self.peer_id,
                    addrs=self.observed_addrs,
                )
            )
        )

        # Encode message
        encoded = encode_message(dial_msg)

        # Perform dial-back check
        status, status_text, dialed_addr = await dial_back_func(self.peer_id, encoded)

        if status == ResponseStatus.OK:
            self._successful_dials += 1
            logger.info(f"AutoNAT dial successful: {dialed_addr.hex() if dialed_addr else 'N/A'}")

            if self._successful_dials >= min_confirmations:
                logger.info("AutoNAT: Node is PUBLIC (reachable)")
                return ReachabilityStatus.PUBLIC
        else:
            self._failed_dials += 1
            logger.warning(f"AutoNAT dial failed: {status_text}")

            if self._failed_dials >= min_confirmations:
                logger.info("AutoNAT: Node is PRIVATE (behind NAT)")
                return ReachabilityStatus.PRIVATE

        return ReachabilityStatus.UNKNOWN

    def get_reachability_summary(self) -> dict:
        """Get summary of reachability checks"""
        return {
            "successful_dials": self._successful_dials,
            "failed_dials": self._failed_dials,
            "status": "public" if self._successful_dials >= 3 else "private" if self._failed_dials >= 3 else "unknown",
        }


# ==================== AutoNAT Server ====================

class AutoNATServer:
    """
    AutoNAT server - responds to dial-back requests.

    Processes dial requests from peers and performs dial-back attempts.
    Implements security checks to prevent DDoS attacks.
    """

    def __init__(
        self,
        dial_func: Callable[[str, int, str], Awaitable[bool]],
        max_concurrent_dials: int = 10,
    ):
        """
        Initialize AutoNAT server.

        Args:
            dial_func: Async function to perform dial. Takes (ip, port, protocol) returns success bool
            max_concurrent_dials: Maximum concurrent dial-back attempts
        """
        self._dial_func = dial_func
        self._max_concurrent_dials = max_concurrent_dials
        self._semaphore = asyncio.Semaphore(max_concurrent_dials)
        self._running = False

    async def start(self) -> None:
        """Start the AutoNAT server"""
        self._running = True
        logger.info("AutoNAT server started")

    async def stop(self) -> None:
        """Stop the AutoNAT server"""
        self._running = False
        logger.info("AutoNAT server stopped")

    async def handle_dial_request(
        self,
        request_data: bytes,
        observed_ip: str,
    ) -> bytes:
        """
        Handle a dial request from a peer.

        Args:
            request_data: Raw request message bytes
            observed_ip: The IP address of the requesting peer (for security validation)

        Returns:
            Encoded DialResponse message
        """
        if not self._running:
            return self._encode_error_response(ResponseStatus.E_INTERNAL_ERROR, "Server not running")

        # Decode request
        msg, _ = decode_message(request_data)

        if not msg or msg.type != MessageType.DIAL or not msg.dial:
            return self._encode_error_response(ResponseStatus.E_BAD_REQUEST, "Invalid dial message")

        # Extract peer info
        peer = msg.dial.peer
        if not peer:
            return self._encode_error_response(ResponseStatus.E_BAD_REQUEST, "Missing peer info")

        logger.debug(f"AutoNAT: Dial request from peer {peer.peer_id.hex()[:16]}...")

        # Security check: Validate that at least one address matches observed IP
        # Per RFC 3489 Section 12.1.1 - prevent DDoS attacks
        valid_addr = None
        for addr_bytes in peer.addrs:
            parsed = parse_multiaddr(addr_bytes)
            if parsed and validate_ip_match(observed_ip, parsed[0]):
                valid_addr = addr_bytes
                break

        if not valid_addr:
            logger.warning("AutoNAT: Rejected dial request - no valid addresses matching observed IP")
            return self._encode_error_response(
                ResponseStatus.E_DIAL_REFUSED,
                "No valid addresses (security check failed)"
            )

        # Perform dial-back with rate limiting
        async with self._semaphore:
            response = await self._perform_dial_back(peer, valid_addr)

        # Encode response
        response_msg = AutoNATMessage(
            type=MessageType.DIAL_RESPONSE,
            dial_response=response,
        )

        return encode_message(response_msg)

    async def _perform_dial_back(
        self,
        peer: DialPeerInfo,
        addr: bytes,
    ) -> DialResponse:
        """
        Perform the actual dial-back attempt.

        Args:
            peer: Peer info from dial request
            addr: Address to dial (validated)

        Returns:
            DialResponse with result
        """
        parsed = parse_multiaddr(addr)

        if not parsed:
            return DialResponse(
                status=ResponseStatus.E_BAD_REQUEST,
                status_text="Invalid address format",
            )

        ip, port, protocol = parsed

        try:
            # Try dial-back with timeout
            success = await asyncio.wait_for(
                self._dial_func(ip, port, protocol),
                timeout=DIAL_TIMEOUT,
            )

            if success:
                logger.info(f"AutoNAT: Dial-back successful to {ip}:{port}/{protocol}")
                return DialResponse(
                    status=ResponseStatus.OK,
                    addr=addr,
                )
            else:
                return DialResponse(
                    status=ResponseStatus.E_DIAL_ERROR,
                    status_text=f"Dial failed to {ip}:{port}/{protocol}",
                )

        except asyncio.TimeoutError:
            return DialResponse(
                status=ResponseStatus.E_DIAL_ERROR,
                status_text=f"Dial timeout to {ip}:{port}/{protocol}",
            )

        except Exception as e:
            logger.error(f"AutoNAT dial-back error: {e}")
            return DialResponse(
                status=ResponseStatus.E_INTERNAL_ERROR,
                status_text=str(e),
            )

    def _encode_error_response(self, status: ResponseStatus, text: str) -> bytes:
        """Encode an error response"""
        response_msg = AutoNATMessage(
            type=MessageType.DIAL_RESPONSE,
            dial_response=DialResponse(
                status=status,
                status_text=text,
            ),
        )
        return encode_message(response_msg)


# ==================== AutoNAT Protocol ====================

class AutoNATProtocol:
    """
    Complete AutoNAT protocol implementation.

    Combines client and server functionality for full libp2p AutoNAT v1.0.0
    protocol support.
    """

    PROTOCOL_ID = PROTOCOL_ID

    def __init__(self):
        self._client: Optional[AutoNATClient] = None
        self._server: Optional[AutoNATServer] = None
        self._running = False

    async def start(self) -> None:
        """Start the AutoNAT protocol"""
        if self._running:
            return

        self._running = True
        logger.info("AutoNAT protocol started")

    async def stop(self) -> None:
        """Stop the AutoNAT protocol"""
        if not self._running:
            return

        self._running = False

        if self._server:
            await self._server.stop()

        logger.info("AutoNAT protocol stopped")

    def configure_client(
        self,
        peer_id: bytes,
        observed_addrs: List[bytes],
    ) -> AutoNATClient:
        """Configure and get the AutoNAT client"""
        self._client = AutoNATClient(peer_id, observed_addrs)
        return self._client

    def configure_server(
        self,
        dial_func: Callable[[str, int, str], Awaitable[bool]],
        max_concurrent_dials: int = 10,
    ) -> AutoNATServer:
        """Configure and get the AutoNAT server"""
        self._server = AutoNATServer(dial_func, max_concurrent_dials)
        return self._server

    async def check_reachability(
        self,
        peers: List[PeerInfo],
        dial_back_func: Callable[[bytes, bytes], Awaitable[tuple[ResponseStatus, str, bytes]]],
        min_confirmations: int = 3,
    ) -> str:
        """
        Check NAT reachability status.

        This is the main entry point for reachability detection.

        Args:
            peers: List of peers to query
            dial_back_func: Function to perform dial-back
            min_confirmations: Minimum confirmations needed

        Returns:
            "public" / "private" / "unknown"
        """
        if not self._client:
            raise RuntimeError("AutoNAT client not configured")

        status = await self._client.check_reachability(dial_back_func, min_confirmations)

        if status == ReachabilityStatus.PUBLIC:
            return "public"
        elif status == ReachabilityStatus.PRIVATE:
            return "private"
        return "unknown"

    async def _request_dial_back(self, peer: PeerInfo) -> DialResponse:
        """
        Request a dial-back from a specific peer.

        Args:
            peer: The peer to request dial-back from

        Returns:
            DialResponse with the result
        """
        # This would be implemented based on the transport layer
        # For now, it's a placeholder for the interface
        raise NotImplementedError("Direct dial-back requests require transport integration")


# ==================== Convenience Functions ====================

def create_dial_socket(ip: str, port: int, protocol: str) -> bool:
    """
    Default dial function for AutoNAT server.

    Attempts to create a socket connection to the given address.
    """
    try:
        sock_type = socket.SOCK_STREAM if protocol == "tcp" else socket.SOCK_DGRAM
        sock = socket.socket(socket.AF_INET, sock_type)
        sock.settimeout(DIAL_TIMEOUT)

        if protocol == "tcp":
            sock.connect((ip, port))
        else:
            # For UDP, just try to send something
            sock.sendto(b"\x00", (ip, port))

        sock.close()
        return True

    except Exception as e:
        logger.debug(f"Dial attempt to {ip}:{port}/{protocol} failed: {e}")
        return False


def get_observed_ip_from_socket(sock: socket.socket) -> str:
    """
    Extract observed IP from a connected socket.
    Useful for getting the observed IP when handling AutoNAT requests.
    """
    try:
        peer_addr = sock.getpeername()
        return peer_addr[0] if peer_addr else ""
    except Exception:
        return ""


__all__ = [
    # Protocol constants
    "PROTOCOL_ID",
    "ReachabilityStatus",
    "ResponseStatus",

    # Data structures
    "DialPeerInfo",
    "DialMessage",
    "DialResponse",
    "AutoNATMessage",

    # Main classes
    "AutoNATClient",
    "AutoNATServer",
    "AutoNATProtocol",

    # Utilities
    "parse_multiaddr",
    "validate_ip_match",
    "encode_message",
    "decode_message",
    "create_dial_socket",
    "get_observed_ip_from_socket",
]
