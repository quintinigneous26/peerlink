"""
DCUtR (Direct Connection Upgrade through Relay) Protocol Implementation

This module implements the libp2p DCUtR protocol specification:
https://github.com/libp2p/specs/blob/master/relay/DCUtR.md

The protocol allows two peers to upgrade from a relay connection to a direct
connection by coordinating hole punching through the existing relay connection.
"""

import asyncio
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional, List, Tuple, Callable, Awaitable

from ...types import (
    ConnectionType,
    ConnectionState,
    NATInfo,
    ISP,
)


logger = logging.getLogger("p2p_engine.dcutr")


# ==================== Protocol Constants ====================

PROTOCOL_ID = "/libp2p/dcutr/1.0.0"
DEFAULT_MAX_RETRY_ATTEMPTS = 3
DEFAULT_SYNC_TIMEOUT_MS = 10000
MAX_MESSAGE_SIZE = 4096  # 4 KiB max as per spec


# ==================== Message Types ====================

class DCUtRMessageType(IntEnum):
    """DCUtR message types as per protobuf spec"""
    CONNECT = 100
    SYNC = 300


# ==================== Message Definition ====================

@dataclass
class DCUtRMessage:
    """
    DCUtR protocol message

    Corresponds to the HolePunch protobuf message:
    ```proto
    message HolePunch {
      enum Type {
        CONNECT = 100;
        SYNC = 300;
      }
      required Type type = 1;
      repeated bytes ObsAddrs = 2;
    }
    ```
    """
    message_type: DCUtRMessageType
    obs_addrs: List[bytes] = field(default_factory=list)

    def encode(self) -> bytes:
        """
        Encode message to bytes with varint length prefix

        Format: [varint length][protobuf message]
        """
        # Encode protobuf-style message
        msg_data = self._encode_protobuf()

        # Encode length as varint
        length = len(msg_data)
        length_bytes = self._encode_varint(length)

        return length_bytes + msg_data

    def _encode_protobuf(self) -> bytes:
        """Encode the message body in protobuf format"""
        data = bytearray()

        # Encode type field (field 1, varint)
        data.extend(self._encode_varint_field(1, self.message_type.value))

        # Encode observed addresses (field 2, repeated bytes)
        for addr in self.obs_addrs:
            data.extend(self._encode_varint_field(2, len(addr), is_length=True))
            data.extend(addr)

        return bytes(data)

    @staticmethod
    def _encode_varint(value: int) -> bytes:
        """Encode integer as unsigned varint"""
        if value < 0:
            raise ValueError("Cannot encode negative varint")

        data = bytearray()
        while value > 0x7F:
            data.append((value & 0x7F) | 0x80)
            value >>= 7
        data.append(value)
        return bytes(data) if data else b'\x00'

    @staticmethod
    def _encode_varint_field(field_number: int, value: int, is_length: bool = False) -> bytes:
        """Encode a protobuf field with varint"""
        # Compute field key: (field_number << 3) | wire_type
        # wire_type = 0 for varint, 2 for length-delimited
        wire_type = 2 if is_length else 0
        field_key = (field_number << 3) | wire_type

        result = DCUtRMessage._encode_varint(field_key)
        result += DCUtRMessage._encode_varint(value)
        return result

    @classmethod
    def decode(cls, data: bytes) -> 'DCUtRMessage':
        """
        Decode message from bytes

        Args:
            data: Message data without varint length prefix

        Returns:
            DCUtRMessage instance

        Raises:
            ValueError: If message is invalid
        """
        if not data:
            raise ValueError("Empty message data")

        msg_type = None
        obs_addrs = []

        idx = 0
        while idx < len(data):
            # Decode field key
            field_key, idx = cls.decode_varint(data, idx)
            field_number = field_key >> 3
            wire_type = field_key & 0x07

            if field_number == 1:
                # Type field (varint)
                if wire_type != 0:
                    raise ValueError(f"Invalid wire type for type field: {wire_type}")
                type_value, idx = cls.decode_varint(data, idx)
                msg_type = DCUtRMessageType(type_value)

            elif field_number == 2:
                # Observed addresses (length-delimited bytes)
                if wire_type != 2:
                    raise ValueError(f"Invalid wire type for obs_addrs field: {wire_type}")
                length, idx = cls.decode_varint(data, idx)
                addr = data[idx:idx + length]
                idx += length
                obs_addrs.append(addr)

            else:
                # Skip unknown field
                if wire_type == 0:
                    _, idx = cls.decode_varint(data, idx)
                elif wire_type == 2:
                    length, idx = cls.decode_varint(data, idx)
                    idx += length
                else:
                    raise ValueError(f"Unsupported wire type: {wire_type}")

        if msg_type is None:
            raise ValueError("Missing required type field")

        return cls(message_type=msg_type, obs_addrs=obs_addrs)

    @staticmethod
    def decode_varint(data: bytes, idx: int = 0) -> Tuple[int, int]:
        """
        Decode varint from bytes

        Returns:
            Tuple of (value, new_index)
        """
        value = 0
        shift = 0
        while idx < len(data):
            byte = data[idx]
            idx += 1
            value |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
        return value, idx


# ==================== Connection Result ====================

@dataclass
class DCUtRResult:
    """Result of DCUtR connection upgrade attempt"""
    success: bool
    connection_type: ConnectionType = ConnectionType.FAILED
    direct_connection: Optional[socket.socket] = None
    latency_ms: float = 0.0
    error: str = ""
    attempts: int = 0


# ==================== Main Protocol Class ====================

class DCUtRProtocol:
    """
    DCUtR Protocol Implementation

    Manages the upgrade from relay connections to direct connections
    using coordinated hole punching.
    """

    def __init__(
        self,
        local_peer_id: str,
        local_nat: NATInfo,
        local_isp: ISP,
        max_retry_attempts: int = DEFAULT_MAX_RETRY_ATTEMPTS,
        sync_timeout_ms: int = DEFAULT_SYNC_TIMEOUT_MS,
    ):
        """
        Initialize DCUtR protocol

        Args:
            local_peer_id: Local peer ID
            local_nat: Local NAT information
            local_isp: Local ISP
            max_retry_attempts: Maximum number of retry attempts
            sync_timeout_ms: Timeout for synchronous operations
        """
        self.local_peer_id = local_peer_id
        self.local_nat = local_nat
        self.local_isp = local_isp
        self.max_retry_attempts = max_retry_attempts
        self.sync_timeout_ms = sync_timeout_ms

        self._relay_conn: Optional[asyncio.StreamWriter] = None
        self._relay_reader: Optional[asyncio.StreamReader] = None
        self._active_connections: List[socket.socket] = []

    async def upgrade_to_direct(
        self,
        relay_reader: asyncio.StreamReader,
        relay_writer: asyncio.StreamWriter,
        local_addrs: List[str],
        remote_peer_id: str,
    ) -> DCUtRResult:
        """
        Attempt to upgrade relay connection to direct connection

        This method initiates the DCUtR protocol as the active peer
        (the peer that initiates the upgrade).

        Args:
            relay_reader: Reader for relay connection
            relay_writer: Writer for relay connection
            local_addrs: Local observed/predicted addresses
            remote_peer_id: Remote peer ID

        Returns:
            DCUtRResult with connection details
        """
        self._relay_reader = relay_reader
        self._relay_conn = relay_writer

        start_time = time.time()

        logger.info(f"[DCUtR] Initiating upgrade to {remote_peer_id}")

        for attempt in range(self.max_retry_attempts):
            try:
                logger.debug(f"[DCUtR] Upgrade attempt {attempt + 1}/{self.max_retry_attempts}")

                result = await self._perform_upgrade_attempt(local_addrs)
                result.attempts = attempt + 1

                if result.success:
                    logger.info(f"[DCUtR] Upgrade successful after {result.attempts} attempts")
                    return result
                else:
                    logger.debug(f"[DCUtR] Attempt {attempt + 1} failed: {result.error}")

            except Exception as e:
                logger.error(f"[DCUtR] Attempt {attempt + 1} error: {e}")
                continue

        # All attempts failed
        return DCUtRResult(
            success=False,
            error="max_retries_exceeded",
            attempts=self.max_retry_attempts,
        )

    async def _perform_upgrade_attempt(self, local_addrs: List[str]) -> DCUtRResult:
        """
        Perform a single upgrade attempt

        Args:
            local_addrs: Local addresses to share

        Returns:
            DCUtRResult
        """
        try:
            # Step 1: Send CONNECT message
            connect_msg = DCUtRMessage(
                message_type=DCUtRMessageType.CONNECT,
                obs_addrs=[addr.encode() for addr in local_addrs],
            )

            await self._send_message(connect_msg)
            logger.debug("[DCUtR] Sent CONNECT message")

            # Step 2: Receive CONNECT response (with RTT measurement)
            connect_start = time.time()
            response_msg = await self._receive_message()
            rtt_ms = (time.time() - connect_start) * 1000

            if response_msg.message_type != DCUtRMessageType.CONNECT:
                return DCUtRResult(success=False, error="expected_connect_response")

            logger.debug(f"[DCUtR] Received CONNECT response (RTT: {rtt_ms:.1f}ms)")

            # Decode remote addresses
            remote_addrs = [addr.decode() for addr in response_msg.obs_addrs]
            logger.debug(f"[DCUtR] Remote addresses: {remote_addrs}")

            # Step 3: Send SYNC message
            sync_msg = DCUtRMessage(message_type=DCUtRMessageType.SYNC)
            await self._send_message(sync_msg)
            logger.debug("[DCUtR] Sent SYNC message")

            # Step 4: Calculate delay (half RTT + small buffer)
            delay_sec = (rtt_ms / 2 / 1000) + 0.05  # Add 50ms buffer

            # Step 5: Perform simultaneous connect
            return await self._simultaneous_connect(remote_addrs, delay_sec)

        except asyncio.TimeoutError:
            return DCUtRResult(success=False, error="timeout")
        except Exception as e:
            return DCUtRResult(success=False, error=str(e))

    async def _simultaneous_connect(
        self,
        addrs: List[str],
        delay_sec: float,
    ) -> DCUtRResult:
        """
        Perform simultaneous connection attempt

        Implements TCP Simultaneous Open for TCP addresses
        Implements QUIC hole punching for QUIC addresses

        Args:
            addrs: Remote addresses to connect to
            delay_sec: Delay before initiating connection (for synchronization)

        Returns:
            DCUtRResult
        """
        tasks = []
        timeout = self.sync_timeout_ms / 1000

        for addr_str in addrs:
            try:
                # Parse multiaddr format
                # Expected format: /ip4/<ip>/tcp/<port> or /ip4/<ip>/udp/<port>/quic
                parsed = self._parse_multiaddr(addr_str)
                if parsed is None:
                    continue

                proto, ip, port = parsed

                if proto == "tcp":
                    task = self._tcp_connect(ip, port, delay_sec, timeout)
                    tasks.append(task)
                elif proto == "quic":
                    task = self._quic_connect(ip, port, delay_sec, timeout)
                    tasks.append(task)

            except Exception as e:
                logger.debug(f"[DCUtR] Failed to parse address {addr_str}: {e}")

        if not tasks:
            return DCUtRResult(success=False, error="no_valid_addresses")

        # Try all connections in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Find first successful connection
        for result in results:
            if isinstance(result, DCUtRResult) and result.success:
                return result

        return DCUtRResult(success=False, error="all_connections_failed")

    async def _tcp_connect(
        self,
        ip: str,
        port: int,
        delay_sec: float,
        timeout: float,
    ) -> DCUtRResult:
        """
        Attempt TCP simultaneous open connection

        Args:
            ip: Remote IP address
            port: Remote port
            delay_sec: Delay before connecting
            timeout: Connection timeout

        Returns:
            DCUtRResult
        """
        await asyncio.sleep(delay_sec)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)

        try:
            # Bind to local port
            sock.bind(("0.0.0.0", 0))

            # Initiate connection (non-blocking)
            try:
                sock.connect((ip, port))
            except (BlockingIOError, ConnectionRefusedError):
                pass  # Expected for simultaneous open

            # Wait for connection with timeout
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.sock_connect(sock, (ip, port)),
                timeout=timeout,
            )

            # Connection successful
            self._active_connections.append(sock)
            local_addr = sock.getsockname()
            peer_addr = sock.getpeername()

            logger.info(f"[DCUtR] TCP connected: {local_addr} -> {peer_addr}")

            return DCUtRResult(
                success=True,
                connection_type=ConnectionType.P2P_TCP,
                direct_connection=sock,
            )

        except asyncio.TimeoutError:
            sock.close()
            return DCUtRResult(success=False, error="tcp_timeout")
        except Exception as e:
            sock.close()
            return DCUtRResult(success=False, error=f"tcp_error: {e}")

    async def _quic_connect(
        self,
        ip: str,
        port: int,
        delay_sec: float,
        timeout: float,
    ) -> DCUtRResult:
        """
        Attempt QUIC hole punching connection

        For QUIC, sends UDP packets to punch through NAT

        Args:
            ip: Remote IP address
            port: Remote port
            delay_sec: Delay before connecting
            timeout: Operation timeout

        Returns:
            DCUtRResult
        """
        await asyncio.sleep(delay_sec)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)

        try:
            # Bind to local port
            sock.bind(("0.0.0.0", 0))

            # Send random UDP packets for hole punching
            import os
            end_time = time.time() + timeout
            packet_interval = 0.1  # Start with 100ms

            while time.time() < end_time:
                # Send random data packet
                random_data = os.urandom(64)
                try:
                    sock.sendto(random_data, (ip, port))
                except Exception:
                    pass

                # Random interval between 10-200ms as per spec
                await asyncio.sleep(packet_interval)
                packet_interval = 0.01 + (random_data[0] / 255) * 0.19

                # Check for response
                try:
                    loop = asyncio.get_event_loop()
                    data, addr = await asyncio.wait_for(
                        loop.sock_recvfrom(sock, 1024),
                        timeout=0.1,
                    )
                    if data:
                        logger.info(f"[DCUtR] QUIC response from {addr}")
                        self._active_connections.append(sock)
                        return DCUtRResult(
                            success=True,
                            connection_type=ConnectionType.P2P_UDP,
                            direct_connection=sock,
                        )
                except asyncio.TimeoutError:
                    continue

            sock.close()
            return DCUtRResult(success=False, error="quic_no_response")

        except Exception as e:
            sock.close()
            return DCUtRResult(success=False, error=f"quic_error: {e}")

    async def handle_incoming_upgrade(
        self,
        relay_reader: asyncio.StreamReader,
        relay_writer: asyncio.StreamWriter,
        local_addrs: List[str],
    ) -> DCUtRResult:
        """
        Handle incoming DCUtR upgrade request (passive side)

        This method handles the DCUtR protocol as the passive peer
        (the peer that receives the upgrade request).

        Args:
            relay_reader: Reader for relay connection
            relay_writer: Writer for relay connection
            local_addrs: Local observed/predicted addresses

        Returns:
            DCUtRResult with connection details
        """
        self._relay_reader = relay_reader
        self._relay_conn = relay_writer

        try:
            # Step 1: Receive CONNECT message
            connect_msg = await self._receive_message()
            if connect_msg.message_type != DCUtRMessageType.CONNECT:
                return DCUtRResult(success=False, error="expected_connect")

            logger.debug("[DCUtR] Received CONNECT request")

            # Record time for RTT measurement
            connect_recv_time = time.time()

            # Step 2: Send CONNECT response with our addresses
            response = DCUtRMessage(
                message_type=DCUtRMessageType.CONNECT,
                obs_addrs=[addr.encode() for addr in local_addrs],
            )
            await self._send_message(response)
            logger.debug("[DCUtR] Sent CONNECT response")

            # Step 3: Receive SYNC message
            sync_msg = await self._receive_message()
            if sync_msg.message_type != DCUtRMessageType.SYNC:
                return DCUtRResult(success=False, error="expected_sync")

            logger.debug("[DCUtR] Received SYNC message")

            # Step 4: Immediately connect (no delay for passive side)
            remote_addrs = [addr.decode() for addr in connect_msg.obs_addrs]
            logger.debug(f"[DCUtR] Remote addresses: {remote_addrs}")

            return await self._simultaneous_connect(remote_addrs, 0)

        except asyncio.TimeoutError:
            return DCUtRResult(success=False, error="timeout")
        except Exception as e:
            return DCUtRResult(success=False, error=str(e))

    async def _send_message(self, message: DCUtRMessage) -> None:
        """Send message over relay connection"""
        if self._relay_conn is None:
            raise RuntimeError("No active relay connection")

        data = message.encode()
        self._relay_conn.write(data)
        await self._relay_conn.drain()
        logger.debug(f"[DCUtR] Sent message: {message.message_type.name} ({len(data)} bytes)")

    async def _receive_message(self) -> DCUtRMessage:
        """Receive message from relay connection"""
        if self._relay_reader is None:
            raise RuntimeError("No active relay connection")

        # Read varint length (may be multiple bytes)
        length_bytes = bytearray()
        while True:
            byte = await asyncio.wait_for(
                self._relay_reader.read(1),
                timeout=self.sync_timeout_ms / 1000,
            )
            if not byte:
                raise EOFError("Connection closed while reading varint")
            length_bytes.extend(byte)
            # Check if we've read the complete varint (last byte has high bit clear)
            if not (byte[0] & 0x80):
                break

        length, _ = DCUtRMessage.decode_varint(bytes(length_bytes))

        # Check message size limit
        if length > MAX_MESSAGE_SIZE:
            raise ValueError(f"Message too large: {length} > {MAX_MESSAGE_SIZE}")

        # Read message data
        data = await asyncio.wait_for(
            self._relay_reader.readexactly(length),
            timeout=self.sync_timeout_ms / 1000,
        )

        message = DCUtRMessage.decode(data)
        logger.debug(f"[DCUtR] Received message: {message.message_type.name} ({len(data)} bytes)")

        return message

    @staticmethod
    def _parse_multiaddr(addr: str) -> Optional[Tuple[str, str, int]]:
        """
        Parse multiaddr string

        Supports:
        - /ip4/<ip>/tcp/<port>
        - /ip6/<ip>/tcp/<port>
        - /ip4/<ip>/udp/<port>/quic

        Returns:
            Tuple of (protocol, ip, port) or None
        """
        try:
            # Remove leading/trailing slashes and split
            addr = addr.strip()
            if not addr.startswith('/'):
                return None

            parts = addr[1:].split('/')  # Skip first empty element from leading slash
            if len(parts) < 4:
                return None

            proto = parts[0]  # ip4 or ip6
            ip = parts[1]
            transport = parts[2]  # tcp or udp
            port = int(parts[3]) if len(parts) > 3 else 0

            if transport == "tcp":
                return ("tcp", ip, port)
            elif transport == "udp" and len(parts) > 4 and parts[4] == "quic":
                return ("quic", ip, port)

            return None

        except (ValueError, IndexError):
            return None

    def close(self) -> None:
        """Close all active connections"""
        for conn in self._active_connections:
            try:
                conn.close()
            except Exception:
                pass
        self._active_connections.clear()

        if self._relay_conn:
            try:
                self._relay_conn.close()
            except Exception:
                pass
            self._relay_conn = None
            self._relay_reader = None

    def __del__(self):
        """Cleanup on deletion"""
        self.close()
