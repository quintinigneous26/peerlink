"""
Transport Layer Implementation

Provides UDP and Relay transport implementations for P2P communication.
"""

import asyncio
import socket
import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class TransportBase(ABC):
    """Base class for transport implementations."""

    @abstractmethod
    async def send(self, data: bytes) -> None:
        """Send data."""
        pass

    @abstractmethod
    async def recv(self) -> bytes:
        """Receive data."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the transport."""
        pass


class UDPTransport(TransportBase):
    """
    UDP transport for direct P2P communication.

    Handles raw UDP socket operations for hole punching
    and direct peer-to-peer data transfer.
    """

    def __init__(self, local_ip: str = "0.0.0.0", local_port: int = 0):
        """
        Initialize UDP transport.

        Args:
            local_ip: Local IP to bind to
            local_port: Local port (0 for auto-assign)
        """
        self.local_ip = local_ip
        self.local_port = local_port
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._peer_addr: Optional[Tuple[str, int]] = None
        self._recv_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._recv_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the UDP transport."""
        if self._running:
            return

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.local_ip, self.local_port))

        # Get assigned port
        self.local_port = self._socket.getsockname()[1]

        # Set non-blocking
        self._socket.setblocking(False)

        self._running = True
        self._recv_task = asyncio.create_task(self._recv_loop())

        logger.info(f"UDP transport started on {self.local_ip}:{self.local_port}")

    async def stop(self) -> None:
        """Stop the UDP transport."""
        self._running = False

        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

        if self._socket:
            self._socket.close()
            self._socket = None

        logger.info("UDP transport stopped")

    def set_peer(self, ip: str, port: int) -> None:
        """Set the peer address for send operations."""
        self._peer_addr = (ip, port)
        logger.debug(f"Peer address set to {ip}:{port}")

    async def sendto(self, data: bytes, ip: str, port: int) -> None:
        """
        Send data to specific address.

        Args:
            data: Data to send
            ip: Target IP address
            port: Target port
        """
        if not self._socket:
            raise RuntimeError("UDP transport not started")

        loop = asyncio.get_event_loop()
        await loop.sock_sendto(self._socket, data, (ip, port))

    async def send(self, data: bytes) -> None:
        """
        Send data to configured peer.

        Args:
            data: Data to send

        Raises:
            RuntimeError: If peer address not set
        """
        if not self._peer_addr:
            raise RuntimeError("Peer address not set. Use sendto() instead.")

        await self.sendto(data, self._peer_addr[0], self._peer_addr[1])

    async def recvfrom(self) -> Tuple[bytes, Tuple[str, int]]:
        """
        Receive data from any source.

        Returns:
            Tuple of (data, (ip, port))
        """
        if not self._socket:
            raise RuntimeError("UDP transport not started")

        loop = asyncio.get_event_loop()
        data, addr = await loop.sock_recvfrom(self._socket, 65535)
        return data, addr

    async def recv(self) -> bytes:
        """
        Receive data from peer.

        Returns:
            Received data
        """
        return await self._recv_queue.get()

    async def _recv_loop(self) -> None:
        """Background receive loop."""
        while self._running:
            try:
                data, addr = await self.recvfrom()

                # Store peer address if not set
                if self._peer_addr is None:
                    self._peer_addr = addr

                # Put in queue if from peer
                if self._peer_addr and addr == self._peer_addr:
                    await self._recv_queue.put(data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in UDP recv loop: {e}")


class RelayTransport(TransportBase):
    """
    Relay transport for fallback communication.

    Uses a relay server when direct P2P connection is not possible.
    """

    def __init__(
        self,
        server: str,
        port: int,
        did: str,
        timeout: float = 30.0,
    ):
        """
        Initialize relay transport.

        Args:
            server: Relay server address
            port: Relay server port
            did: Device ID
            timeout: Connection timeout
        """
        self.server = server
        self.port = port
        self.did = did
        self.timeout = timeout
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._peer_did: Optional[str] = None

    async def connect(self, peer_did: str) -> None:
        """
        Connect to relay server for peer communication.

        Args:
            peer_did: Peer's device ID
        """
        self._peer_did = peer_did

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.server, self.port),
                timeout=self.timeout,
            )

            # Send registration message
            registration = f"CONNECT {self.did} {peer_did}\n"
            self._writer.write(registration.encode())
            await self._writer.drain()

            # Wait for acknowledgment
            response = await asyncio.wait_for(
                self._reader.readline(),
                timeout=self.timeout,
            )

            if b"OK" not in response:
                raise ConnectionError(f"Relay connection rejected: {response.decode()}")

            self._connected = True
            logger.info(f"Relay transport connected to {peer_did} via {self.server}:{self.port}")

        except asyncio.TimeoutError:
            raise TimeoutError(f"Relay connection timeout to {self.server}:{self.port}")

    async def send(self, data: bytes) -> None:
        """
        Send data via relay.

        Args:
            data: Data to send
        """
        if not self._connected or not self._writer:
            raise RuntimeError("Relay transport not connected")

        # Prefix with length
        length_prefix = len(data).to_bytes(4, "big")
        self._writer.write(length_prefix + data)
        await self._writer.drain()

    async def recv(self) -> bytes:
        """
        Receive data via relay.

        Returns:
            Received data
        """
        if not self._connected or not self._reader:
            raise RuntimeError("Relay transport not connected")

        # Read length prefix
        length_bytes = await self._reader.readexactly(4)
        length = int.from_bytes(length_bytes, "big")

        # Read data
        data = await self._reader.readexactly(length)
        return data

    async def close(self) -> None:
        """Close relay connection."""
        self._connected = False

        if self._writer:
            try:
                self._writer.write(b"DISCONNECT\n")
                await self._writer.drain()
            except (ConnectionError, OSError) as e:
                logger.debug(f"Error sending disconnect message: {e}")
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (ConnectionError, OSError) as e:
                logger.debug(f"Error waiting for writer close: {e}")

        self._reader = None
        self._writer = None

        logger.info("Relay transport closed")


class WebSocketTransport(TransportBase):
    """
    WebSocket transport for signaling and relay communication.

    Uses WebSocket protocol for reliable messaging over HTTP.
    """

    def __init__(
        self,
        url: str,
        did: str,
        timeout: float = 30.0,
    ):
        """
        Initialize WebSocket transport.

        Args:
            url: WebSocket server URL
            did: Device ID
            timeout: Connection timeout
        """
        self.url = url
        self.did = did
        self.timeout = timeout
        self._ws: Optional[Any] = None
        self._connected = False
        self._send_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._recv_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._send_task: Optional[asyncio.Task] = None
        self._recv_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """Connect to WebSocket server."""
        try:
            import websockets

            self._ws = await asyncio.wait_for(
                websockets.connect(self.url),
                timeout=self.timeout,
            )

            self._connected = True

            # Start background tasks
            self._send_task = asyncio.create_task(self._send_loop())
            self._recv_task = asyncio.create_task(self._recv_loop())

            logger.info(f"WebSocket transport connected to {self.url}")

        except ImportError:
            raise RuntimeError("websockets package required for WebSocketTransport")

    async def send(self, data: bytes) -> None:
        """Queue data to send."""
        await self._send_queue.put(data)

    async def recv(self) -> bytes:
        """Receive data."""
        return await self._recv_queue.get()

    async def _send_loop(self) -> None:
        """Background send loop."""
        while self._connected and self._ws:
            try:
                data = await self._send_queue.get()
                await self._ws.send(data)
            except Exception as e:
                logger.error(f"Error in WebSocket send loop: {e}")
                break

    async def _recv_loop(self) -> None:
        """Background receive loop."""
        while self._connected and self._ws:
            try:
                data = await self._ws.recv()
                if isinstance(data, str):
                    data = data.encode("utf-8")
                await self._recv_queue.put(data)
            except Exception as e:
                logger.error(f"Error in WebSocket recv loop: {e}")
                break

    async def close(self) -> None:
        """Close WebSocket connection."""
        self._connected = False

        if self._send_task:
            self._send_task.cancel()
        if self._recv_task:
            self._recv_task.cancel()

        if self._ws:
            await self._ws.close()

        logger.info("WebSocket transport closed")
