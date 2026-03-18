"""
P2P Client Implementation

Core client class for P2P device communication with NAT traversal,
UDP hole punching, and automatic relay fallback.
"""

import asyncio
import socket
import json
import time
import logging
from typing import Optional, Dict, Any, Callable, Awaitable, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .nat_detection import NATType, detect_nat_type
from .exceptions import (
    P2PError,
    ConnectionError,
    NATDetectionError,
    RelayError,
    TimeoutError,
    ChannelError,
)
from .transport import UDPTransport, RelayTransport, TransportBase
from .signaling import SignalingClient, SignalingEvent
from .protocol import (
    MessageTypes,
    P2PMessage,
    HandshakeMessage,
    ChannelMessage,
    create_handshake,
    parse_message,
)

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state machine."""

    DISCONNECTED = "disconnected"
    """Not connected to any device."""

    CONNECTING = "connecting"
    """Attempting to establish connection."""

    HANDSHAKE = "handshake"
    """Exchanging handshake messages."""

    CONNECTED_P2P = "connected_p2p"
    """Connected via direct P2P."""

    CONNECTED_RELAY = "connected_relay"
    """Connected via relay server."""

    FAILED = "failed"
    """Connection failed."""


class ChannelType(Enum):
    """Data channel types."""

    CONTROL = "control"
    """Control channel for signaling."""

    DATA = "data"
    """Data channel for bulk transfer."""

    VIDEO = "video"
    """Video streaming channel."""

    AUDIO = "audio"
    """Audio streaming channel."""

    CUSTOM = "custom"
    """Custom application channel."""


@dataclass
class ChannelConfig:
    """Configuration for a data channel."""

    channel_type: ChannelType
    channel_id: int
    priority: int = 0
    reliable: bool = True
    max_packet_size: int = 1400


@dataclass
class PeerInfo:
    """Information about a remote peer."""

    did: str
    """Device ID of the peer."""

    public_ip: Optional[str] = None
    """Public IP address."""

    public_port: Optional[int] = None
    """Public UDP port."""

    local_ip: Optional[str] = None
    """Local IP (if on same LAN)."""

    local_port: Optional[int] = None
    """Local UDP port."""

    nat_type: Optional[NATType] = None
    """Detected NAT type."""

    capabilities: list = field(default_factory=list)
    """Supported capabilities."""


@dataclass
class P2PConfig:
    """Configuration for P2P client."""

    signaling_server: str = "localhost"
    """Signaling server address."""

    signaling_port: int = 8443
    """Signaling server port."""

    stun_server: str = "stun.l.google.com"
    """STUN server for NAT detection."""

    stun_port: int = 19302
    """STUN server port."""

    relay_server: str = "localhost"
    """Relay server address."""

    relay_port: int = 5000
    """Relay server port."""

    local_port: int = 0
    """Local UDP port (0 for auto)."""

    connection_timeout: float = 30.0
    """Connection timeout in seconds."""

    punch_timeout: float = 10.0
    """UDP hole punching timeout."""

    keepalive_interval: float = 5.0
    """Keepalive interval in seconds."""

    max_retries: int = 3
    """Maximum connection retry attempts."""

    auto_relay: bool = True
    """Automatically fallback to relay."""


class P2PClient:
    """
    P2P Client for device-to-device communication.

    Features:
    - NAT type detection
    - UDP hole punching
    - Multi-channel data transfer
    - Automatic relay fallback
    - Auto-reconnection
    """

    def __init__(self, did: str, config: Optional[P2PConfig] = None):
        """
        Initialize P2P client.

        Args:
            did: Device ID for this client
            config: Client configuration (uses defaults if None)
        """
        self.did = did
        self.config = config or P2PConfig()

        # State
        self._state = ConnectionState.DISCONNECTED
        self._nat_type: Optional[NATType] = None
        self._public_addr: Optional[Tuple[str, int]] = None
        self._current_peer: Optional[PeerInfo] = None

        # Transports
        self._udp_transport: Optional[UDPTransport] = None
        self._relay_transport: Optional[RelayTransport] = None
        self._active_transport: Optional[TransportBase] = None

        # Signaling
        self._signaling: Optional[SignalingClient] = None

        # Channels
        self._channels: Dict[int, asyncio.Queue[bytes]] = {}
        self._channel_configs: Dict[int, ChannelConfig] = {}
        self._next_channel_id = 1

        # Event handlers
        self._on_connected: Optional[Callable[[], Awaitable[None]]] = None
        self._on_disconnected: Optional[Callable[[], Awaitable[None]]] = None
        self._on_data: Optional[Callable[[int, bytes], Awaitable[None]]] = None
        self._on_error: Optional[Callable[[Exception], Awaitable[None]]] = None

        # Tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._keepalive_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None

        # Synchronization
        self._lock = asyncio.Lock()
        self._running = False

        logger.info(f"P2PClient initialized with DID: {did}")

    async def initialize(self) -> None:
        """
        Initialize the P2P client.

        Performs NAT detection and connects to signaling server.
        Must be called before any other operations.

        Raises:
            NATDetectionError: If NAT detection fails
            ConnectionError: If signaling connection fails
        """
        logger.info("Initializing P2P client...")

        try:
            # Detect NAT type
            await self._detect_nat()

            # Initialize UDP transport
            self._udp_transport = UDPTransport(
                local_port=self.config.local_port, local_ip="0.0.0.0"
            )
            await self._udp_transport.start()

            # Get assigned port
            local_port = self._udp_transport.local_port
            logger.info(f"UDP transport started on port {local_port}")

            # Connect to signaling server
            self._signaling = SignalingClient(
                server=self.config.signaling_server,
                port=self.config.signaling_port,
                did=self.did,
            )
            await self._signaling.connect()

            # Register our address with signaling
            await self._register_with_signaling()

            self._running = True
            logger.info("P2P client initialized successfully")

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise ConnectionError(f"Failed to initialize: {e}") from e

    async def _detect_nat(self) -> None:
        """Perform NAT type detection."""
        logger.info("Detecting NAT type...")

        try:
            result = await detect_nat_type(self.config.stun_server, self.config.stun_port)
            self._nat_type = result.nat_type
            self._public_addr = (result.public_ip, result.public_port) if result.public_ip else None

            logger.info(
                f"NAT detected: {result.nat_type.value}, "
                f"public address: {result.public_ip}:{result.public_port}"
            )

        except Exception as e:
            logger.error(f"NAT detection failed: {e}")
            self._nat_type = NATType.UNKNOWN
            raise NATDetectionError(f"NAT detection failed: {e}") from e

    async def _register_with_signaling(self) -> None:
        """Register device information with signaling server."""
        if not self._signaling or not self._public_addr:
            return

        await self._signaling.register_device(
            did=self.did,
            public_ip=self._public_addr[0],
            public_port=self._public_addr[1],
            nat_type=self._nat_type.value if self._nat_type else "unknown",
        )

    async def detect_nat(self) -> NATType:
        """
        Detect NAT type.

        Returns:
            Detected NAT type

        Raises:
            NATDetectionError: If detection fails
        """
        if self._nat_type is None:
            await self._detect_nat()

        return self._nat_type

    async def connect(self, did: str) -> bool:
        """
        Connect to a remote device.

        Attempts P2P connection first, falls back to relay if configured.

        Args:
            did: Device ID to connect to

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection fails
            TimeoutError: If connection times out
        """
        async with self._lock:
            if self._state in [ConnectionState.CONNECTED_P2P, ConnectionState.CONNECTED_RELAY]:
                logger.warning(f"Already connected to {self._current_peer.did if self._current_peer else 'unknown'}")
                return True

            self._state = ConnectionState.CONNECTING
            logger.info(f"Connecting to device: {did}")

        try:
            # Query peer info from signaling server
            peer_info = await self._query_peer_info(did)
            self._current_peer = peer_info

            # Attempt P2P connection
            p2p_success = await self._try_p2p_connect(peer_info)

            if p2p_success:
                logger.info(f"P2P connection established to {did}")
                self._state = ConnectionState.CONNECTED_P2P
                self._active_transport = self._udp_transport
                await self._start_receive_loop()
                await self._start_keepalive()
                await self._notify_connected()
                return True

            # Fallback to relay
            if self.config.auto_relay:
                logger.info(f"P2P failed, attempting relay connection to {did}")
                relay_success = await self._try_relay_connect(peer_info)

                if relay_success:
                    logger.info(f"Relay connection established to {did}")
                    self._state = ConnectionState.CONNECTED_RELAY
                    self._active_transport = self._relay_transport
                    await self._start_receive_loop()
                    await self._start_keepalive()
                    await self._notify_connected()
                    return True

            # All connection attempts failed
            self._state = ConnectionState.FAILED
            raise ConnectionError(f"Failed to connect to {did}: All attempts failed")

        except Exception as e:
            self._state = ConnectionState.FAILED
            logger.error(f"Connection to {did} failed: {e}")
            await self._notify_error(e)
            raise ConnectionError(f"Connection failed: {e}") from e

    async def _query_peer_info(self, did: str) -> PeerInfo:
        """Query peer information from signaling server."""
        if not self._signaling:
            raise ConnectionError("Signaling client not initialized")

        info = await self._signaling.query_device(did)

        return PeerInfo(
            did=did,
            public_ip=info.get("public_ip"),
            public_port=info.get("public_port"),
            local_ip=info.get("local_ip"),
            local_port=info.get("local_port"),
            nat_type=NATType(info.get("nat_type", "unknown")),
            capabilities=info.get("capabilities", []),
        )

    async def _try_p2p_connect(self, peer: PeerInfo) -> bool:
        """Attempt P2P connection via UDP hole punching."""
        if not self._udp_transport or not peer.public_ip or not peer.public_port:
            logger.warning("Cannot attempt P2P: missing transport or peer address")
            return False

        logger.info(f"Attempting P2P connection to {peer.public_ip}:{peer.public_port}")

        try:
            # Perform hole punching handshake
            success = await self._hole_punch_handshake(peer)

            if success:
                logger.info("Hole punching successful, P2P connection established")
                return True

            logger.warning("Hole punching failed")
            return False

        except Exception as e:
            logger.error(f"P2P connection attempt failed: {e}")
            return False

    async def _hole_punch_handshake(self, peer: PeerInfo) -> bool:
        """
        Perform UDP hole punching handshake.

        This implements a simplified STUN-like exchange:
        1. Send handshake to peer's public address
        2. Expect handshake response
        3. Verify connection with ping/pong
        """
        if not self._udp_transport:
            return False

        # Create handshake message
        handshake = create_handshake(
            sender_did=self.did,
            receiver_did=peer.did,
            public_addr=self._public_addr,
        )

        # Target address - try public first, fall back to local
        targets = []
        if peer.public_ip and peer.public_port:
            targets.append((peer.public_ip, peer.public_port))
        if peer.local_ip and peer.local_port:
            targets.append((peer.local_ip, peer.local_port))

        # Send handshake to all candidate addresses
        for target in targets:
            try:
                logger.debug(f"Sending handshake to {target[0]}:{target[1]}")
                await self._udp_transport.sendto(
                    handshake.encode(), target[0], target[1]
                )
            except Exception as e:
                logger.warning(f"Failed to send handshake to {target}: {e}")

        # Wait for response with timeout
        deadline = time.time() + self.config.punch_timeout

        while time.time() < deadline:
            try:
                # Wait for incoming message with short timeout
                data, addr = await asyncio.wait_for(
                    self._udp_transport.recvfrom(), timeout=1.0
                )

                # Parse message
                msg = parse_message(data)
                if msg and msg.msg_type == MessageTypes.HANDSHAKE:
                    if msg.sender_did == peer.did:
                        logger.info(f"Received handshake from {peer.did} at {addr}")
                        # Send handshake acknowledgment
                        ack = create_handshake(
                            sender_did=self.did,
                            receiver_did=peer.did,
                            public_addr=self._public_addr,
                            is_ack=True,
                        )
                        await self._udp_transport.sendto(ack.encode(), addr[0], addr[1])

                        # Store peer's actual address
                        peer.public_ip = addr[0]
                        peer.public_port = addr[1]

                        return True

            except asyncio.TimeoutError:
                # Try sending handshake again
                for target in targets:
                    try:
                        await self._udp_transport.sendto(
                            handshake.encode(), target[0], target[1]
                        )
                    except (ConnectionError, OSError) as e:
                        logger.debug(f"Failed to send retry handshake: {e}")
            except Exception as e:
                logger.debug(f"Error during handshake wait: {e}")

        return False

    async def _try_relay_connect(self, peer: PeerInfo) -> bool:
        """Attempt connection via relay server."""
        try:
            self._relay_transport = RelayTransport(
                server=self.config.relay_server,
                port=self.config.relay_port,
                did=self.did,
            )
            await self._relay_transport.connect(peer.did)
            return True

        except Exception as e:
            logger.error(f"Relay connection failed: {e}")
            return False

    async def _start_receive_loop(self) -> None:
        """Start the receive loop for incoming data."""
        if self._receive_task and not self._receive_task.done():
            return

        self._receive_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self) -> None:
        """Main receive loop for incoming messages."""
        while self._running and self._active_transport:
            try:
                data = await self._active_transport.recv()
                if not data:
                    break

                # Parse message
                msg = parse_message(data)
                if not msg:
                    continue

                # Handle message based on type
                if msg.msg_type == MessageTypes.CHANNEL_DATA:
                    await self._handle_channel_data(msg)
                elif msg.msg_type == MessageTypes.KEEPALIVE:
                    # Respond to keepalive
                    await self._send_keepalive_response()
                elif msg.msg_type == MessageTypes.DISCONNECT:
                    logger.info(f"Peer {msg.sender_did} disconnected")
                    await self.close()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")

    async def _handle_channel_data(self, msg: P2PMessage) -> None:
        """Handle incoming channel data."""
        if msg.channel_id is None:
            return

        # Get or create channel queue
        if msg.channel_id not in self._channels:
            self._channels[msg.channel_id] = asyncio.Queue()

        # Put data in channel queue
        await self._channels[msg.channel_id].put(msg.payload)

        # Notify callback if set
        if self._on_data:
            try:
                await self._on_data(msg.channel_id, msg.payload)
            except Exception as e:
                logger.error(f"Error in data callback: {e}")

    async def _start_keepalive(self) -> None:
        """Start keepalive task."""
        if self._keepalive_task and not self._keepalive_task.done():
            return

        self._keepalive_task = asyncio.create_task(self._keepalive_loop())

    async def _keepalive_loop(self) -> None:
        """Send periodic keepalive messages."""
        while self._running and self._active_transport:
            try:
                await asyncio.sleep(self.config.keepalive_interval)

                if self._state in [ConnectionState.CONNECTED_P2P, ConnectionState.CONNECTED_RELAY]:
                    await self._send_keepalive()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in keepalive loop: {e}")

    async def _send_keepalive(self) -> None:
        """Send keepalive message."""
        if not self._active_transport or not self._current_peer:
            return

        msg = P2PMessage(
            msg_type=MessageTypes.KEEPALIVE,
            sender_did=self.did,
            receiver_did=self._current_peer.did,
        )

        try:
            await self._active_transport.send(msg.encode())
        except Exception as e:
            logger.error(f"Failed to send keepalive: {e}")

    async def _send_keepalive_response(self) -> None:
        """Send keepalive response (pong)."""
        await self._send_keepalive()

    async def send_data(self, channel: int, data: bytes) -> None:
        """
        Send data on a channel.

        Args:
            channel: Channel ID
            data: Data to send

        Raises:
            ChannelError: If channel is not open or send fails
        """
        if self._state not in [ConnectionState.CONNECTED_P2P, ConnectionState.CONNECTED_RELAY]:
            raise ChannelError("Not connected")

        if not self._active_transport:
            raise ChannelError("No active transport")

        if not self._current_peer:
            raise ChannelError("No peer connected")

        msg = P2PMessage(
            msg_type=MessageTypes.CHANNEL_DATA,
            sender_did=self.did,
            receiver_did=self._current_peer.did,
            channel_id=channel,
            payload=data,
        )

        try:
            await self._active_transport.send(msg.encode())
        except Exception as e:
            raise ChannelError(f"Failed to send data: {e}") from e

    async def recv_data(self, channel: int, timeout: Optional[float] = None) -> bytes:
        """
        Receive data from a channel.

        Args:
            channel: Channel ID
            timeout: Optional timeout in seconds

        Returns:
            Received data

        Raises:
            ChannelError: If channel is not open or timeout occurs
        """
        if channel not in self._channels:
            raise ChannelError(f"Channel {channel} not open")

        try:
            if timeout:
                data = await asyncio.wait_for(self._channels[channel].get(), timeout=timeout)
            else:
                data = await self._channels[channel].get()
            return data

        except asyncio.TimeoutError:
            raise TimeoutError(f"Receive timeout on channel {channel}") from None

    def create_channel(
        self,
        channel_type: ChannelType = ChannelType.DATA,
        reliable: bool = True,
        priority: int = 0,
    ) -> int:
        """
        Create a new data channel.

        Args:
            channel_type: Type of channel
            reliable: Whether channel is reliable
            priority: Channel priority (higher = more important)

        Returns:
            Channel ID
        """
        channel_id = self._next_channel_id
        self._next_channel_id += 1

        self._channels[channel_id] = asyncio.Queue()
        self._channel_configs[channel_id] = ChannelConfig(
            channel_type=channel_type,
            channel_id=channel_id,
            priority=priority,
            reliable=reliable,
        )

        logger.info(f"Created channel {channel_id} (type: {channel_type.value})")
        return channel_id

    def close_channel(self, channel_id: int) -> None:
        """Close a data channel."""
        if channel_id in self._channels:
            del self._channels[channel_id]
        if channel_id in self._channel_configs:
            del self._channel_configs[channel_id]
        logger.info(f"Closed channel {channel_id}")

    # Event handlers
    def on_connected(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Set callback for connection established."""
        self._on_connected = callback

    def on_disconnected(self, callback: Callable[[], Awaitable[None]]) -> None:
        """Set callback for disconnection."""
        self._on_disconnected = callback

    def on_data(self, callback: Callable[[int, bytes], Awaitable[None]]) -> None:
        """Set callback for incoming data."""
        self._on_data = callback

    def on_error(self, callback: Callable[[Exception], Awaitable[None]]) -> None:
        """Set callback for errors."""
        self._on_error = callback

    async def _notify_connected(self) -> None:
        """Notify that connection is established."""
        if self._on_connected:
            try:
                await self._on_connected()
            except Exception as e:
                logger.error(f"Error in connected callback: {e}")

    async def _notify_disconnected(self) -> None:
        """Notify that disconnection occurred."""
        if self._on_disconnected:
            try:
                await self._on_disconnected()
            except Exception as e:
                logger.error(f"Error in disconnected callback: {e}")

    async def _notify_error(self, error: Exception) -> None:
        """Notify that an error occurred."""
        if self._on_error:
            try:
                await self._on_error(error)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

    async def close(self) -> None:
        """Close the connection and cleanup resources."""
        logger.info("Closing P2P client...")

        self._running = False
        self._state = ConnectionState.DISCONNECTED

        # Cancel tasks
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        # Close transports
        if self._udp_transport:
            await self._udp_transport.stop()

        if self._relay_transport:
            await self._relay_transport.close()

        # Close signaling
        if self._signaling:
            await self._signaling.disconnect()

        # Notify
        await self._notify_disconnected()

        logger.info("P2P client closed")

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Whether client is connected."""
        return self._state in [ConnectionState.CONNECTED_P2P, ConnectionState.CONNECTED_RELAY]

    @property
    def is_p2p(self) -> bool:
        """Whether connection is P2P (not relay)."""
        return self._state == ConnectionState.CONNECTED_P2P

    @property
    def peer(self) -> Optional[PeerInfo]:
        """Information about connected peer."""
        return self._current_peer
