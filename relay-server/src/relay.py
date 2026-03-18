"""
TURN Relay Server

Implements a TURN-like relay server for P2P data relay when direct connection fails.
"""

import asyncio
import logging
import os
import socket
import struct
from typing import Dict, Optional, Tuple, List

from .allocation import AllocationManager, DEFAULT_ALLOCATION_LIFETIME
from .bandwidth import BandwidthLimiter, ThroughputMonitor
from .messages import (
    TurnAllocation,
    TurnAttributeType,
    TurnErrorCode,
    TurnMethod,
    MAGIC_COOKIE,
    AttributeType,
    ErrorCode,
    MessageType,
    StunAttribute,
    StunMessage,
    create_lifetime_attr,
    create_xor_address_attr,
    parse_lifetime_attr,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("relay-server")

# Server configuration
DEFAULT_RELAY_HOST = os.environ.get("RELAY_HOST", "0.0.0.0")
DEFAULT_RELAY_PORT = int(os.environ.get("RELAY_PORT", "9001"))  # Control port
RELAY_PUBLIC_IP = os.environ.get("RELAY_PUBLIC_IP", "127.0.0.1")


# STUN/TURN message parsing helper functions
def parse_stun_message(data: bytes) -> Optional[StunMessage]:
    """Parse STUN message from bytes."""
    if len(data) < 20:
        return None

    message_type, message_length, magic_cookie = struct.unpack("!HHI", data[:8])

    if magic_cookie != MAGIC_COOKIE:
        return None

    transaction_id = data[8:20]

    # Parse attributes
    attributes: List[StunAttribute] = []
    offset = 20
    remaining = message_length

    while remaining > 0 and offset + 4 <= len(data):
        attr_type, attr_length = struct.unpack("!HH", data[offset:offset + 4])
        offset += 4

        padded_length = (attr_length + 3) & ~3

        if offset + padded_length > len(data):
            break

        attr_value = data[offset:offset + attr_length]
        attributes.append(StunAttribute(type=attr_type, value=attr_value))

        offset += padded_length
        remaining -= (4 + padded_length)

    return StunMessage(
        message_type=message_type,
        message_length=message_length,
        magic_cookie=magic_cookie,
        transaction_id=transaction_id,
        attributes=attributes,
    )


def create_error_response(transaction_id: bytes, error_code: ErrorCode, message: str) -> bytes:
    """Create STUN error response."""
    class_digit = error_code // 100
    number = error_code % 100

    reason = message.encode("utf-8")
    error_attr = struct.pack(
        "!HHBB",
        AttributeType.ERROR_CODE,
        len(reason) + 4,
        0,
        class_digit
    )
    error_attr += struct.pack("!B", number) + reason

    padding = (4 - ((len(reason) + 4) % 4)) % 4
    error_attr += b"\x00" * padding

    msg = StunMessage(
        message_type=MessageType.BINDING_ERROR_RESPONSE,
        message_length=len(error_attr),
        magic_cookie=MAGIC_COOKIE,
        transaction_id=transaction_id,
        attributes=[
            StunAttribute(type=AttributeType.ERROR_CODE, value=error_attr[4:])
        ],
    )

    return _serialize_stun_message(msg)


def _serialize_stun_message(msg: StunMessage) -> bytes:
    """Serialize STUN message to bytes."""
    attr_data = b""
    for attr in msg.attributes:
        attr_header = struct.pack("!HH", attr.type, len(attr.value))
        attr_data += attr_header + attr.value
        padding = (4 - (len(attr.value) % 4)) % 4
        attr_data += b"\x00" * padding

    message_length = len(attr_data)
    header = struct.pack(
        "!HHI",
        msg.message_type,
        message_length,
        msg.magic_cookie,
    )

    return header + msg.transaction_id + attr_data


# Add parse method to StunMessage
StunMessage.parse = staticmethod(parse_stun_message)
StunMessage.serialize = lambda self: _serialize_stun_message(self)
StunMessage.get_attribute = lambda self, attr_type: next(
    (attr for attr in self.attributes if attr.type == attr_type), None
)


class RelayServer:
    """
    TURN Relay Server implementation.

    Handles allocation requests and relays data between clients and peers.
    """

    def __init__(
        self,
        host: str = DEFAULT_RELAY_HOST,
        port: int = DEFAULT_RELAY_PORT,
        public_ip: str = RELAY_PUBLIC_IP,
        min_port: int = 50000,
        max_port: int = 50010,
        default_lifetime: int = DEFAULT_ALLOCATION_LIFETIME,
    ):
        """
        Initialize relay server.

        Args:
            host: Host to bind control channel
            port: Port for control channel
            public_ip: Public IP address for relay addresses
            min_port: Minimum relay port
            max_port: Maximum relay port
            default_lifetime: Default allocation lifetime
        """
        self.host = host
        self.port = port
        self.public_ip = public_ip
        self.relay_addr_base = (public_ip, 0)  # Port will be dynamic
        self.allocation_manager = AllocationManager(
            min_port=min_port,
            max_port=max_port,
            default_lifetime=default_lifetime,
        )
        self.bandwidth_limiter = BandwidthLimiter()
        self.throughput_monitor = ThroughputMonitor()
        self.running = False
        self._control_socket: Optional[socket.socket] = None
        self._relay_sockets: Dict[int, socket.socket] = {}

    async def start(self):
        """Start relay server."""
        await self.allocation_manager.start()
        self.running = True

        # Start control channel
        await self._start_control_channel()

        logger.info("Relay server started")

    async def _start_control_channel(self):
        """Start control channel for TURN messages."""
        self._control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._control_socket.bind((self.host, self.port))
        self._control_socket.setblocking(False)

        logger.info(f"Control channel listening on {self.host}:{self.port}")

        asyncio.create_task(self._control_loop())

    async def _control_loop(self):
        """Handle control channel messages."""
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                data, addr = await loop.sock_recvfrom(self._control_socket, 2048)

                # Parse and handle TURN message
                response = await self._handle_control_message(data, addr)

                if response:
                    await loop.sock_sendto(self._control_socket, response, addr)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in control loop: {e}")

    async def _handle_control_message(
        self, data: bytes, client_addr: Tuple[str, int]
    ) -> Optional[bytes]:
        """
        Handle TURN control message.

        Args:
            data: Message data
            client_addr: Client's (ip, port)

        Returns:
            Response bytes or None
        """
        # Parse STUN message
        message = StunMessage.parse(data)

        if message is None:
            logger.warning(f"Invalid STUN message from {client_addr}")
            return None

        # Handle based on message class (method)
        message_class = message.message_type >> 6

        if message_class == 0x01:  # Binding request (STUN)
            # Return binding response
            return self._create_binding_response(message, client_addr)

        elif message_class == 0x03:  # ALLOCATE
            return await self._handle_allocate(message, client_addr)

        elif message_class == 0x04:  # REFRESH
            return await self._handle_refresh(message, client_addr)

        elif message_class == 0x06:  # SEND
            return await self._handle_send(message, client_addr)

        elif message_class == 0x08:  # CREATE_PERMISSION
            return await self._handle_create_permission(message, client_addr)

        else:
            logger.warning(f"Unknown message class {message_class} from {client_addr}")
            return create_error_response(
                message.transaction_id,
                ErrorCode.BAD_REQUEST,
                f"Unknown message class: {message_class}",
            )

    def _create_binding_response(
        self, request: StunMessage, client_addr: Tuple[str, int]
    ) -> bytes:
        """Create STUN binding response."""
        xor_mapped = create_xor_address_attr(
            client_addr[0], client_addr[1], request.transaction_id
        )

        response = StunMessage(
            message_type=MessageType.BINDING_RESPONSE,
            message_length=0,
            magic_cookie=MAGIC_COOKIE,
            transaction_id=request.transaction_id,
            attributes=[
                StunAttribute(
                    type=AttributeType.XOR_MAPPED_ADDRESS,
                    value=xor_mapped,
                )
            ],
        )

        return _serialize_stun_message(response)

    async def _handle_allocate(
        self, request: StunMessage, client_addr: Tuple[str, int]
    ) -> bytes:
        """Handle ALLOCATE request."""
        # Check if client already has allocation
        existing = await self.allocation_manager.get_allocation_by_client(client_addr)
        if existing:
            return create_error_response(
                request.transaction_id,
                TurnErrorCode.ALLOCATION_MISMATCH,
                "Client already has allocation",
            )

        # Get requested lifetime
        lifetime_attr = request.get_attribute(TurnAttributeType.LIFETIME)
        lifetime = None
        if lifetime_attr:
            lifetime = parse_lifetime_attr(lifetime_attr.value)

        # Create allocation
        allocation = await self.allocation_manager.create_allocation(
            client_addr=client_addr,
            relay_addr=(self.public_ip, 0),  # Port assigned by manager
            transport="udp",
            lifetime=lifetime,
        )

        if not allocation:
            return create_error_response(
                request.transaction_id,
                TurnErrorCode.INSUFFICIENT_CAPACITY,
                "No resources available",
            )

        # Create relay socket for this allocation
        await self._create_relay_socket(allocation)

        # Build success response
        xor_relayed = create_xor_address_attr(
            allocation.relay_addr[0],
            allocation.relay_addr[1],
            request.transaction_id,
        )

        lifetime_value = create_lifetime_attr(allocation.get_remaining_time())

        xor_mapped = create_xor_address_attr(
            client_addr[0], client_addr[1], request.transaction_id
        )

        response = StunMessage(
            message_type=0x0103,  # ALLOCATE response
            message_length=0,
            magic_cookie=MAGIC_COOKIE,
            transaction_id=request.transaction_id,
            attributes=[
                StunAttribute(
                    type=TurnAttributeType.XOR_RELAYED_ADDRESS,
                    value=xor_relayed,
                ),
                StunAttribute(
                    type=TurnAttributeType.LIFETIME,
                    value=lifetime_value,
                ),
                StunAttribute(
                    type=AttributeType.XOR_MAPPED_ADDRESS,
                    value=xor_mapped,
                ),
            ],
        )

        logger.info(f"Created allocation {allocation.allocation_id} for {client_addr}")

        return _serialize_stun_message(response)

    async def _handle_refresh(
        self, request: StunMessage, client_addr: Tuple[str, int]
    ) -> bytes:
        """Handle REFRESH request."""
        allocation = await self.allocation_manager.get_allocation_by_client(client_addr)

        if not allocation:
            return create_error_response(
                request.transaction_id,
                TurnErrorCode.ALLOCATION_MISMATCH,
                "No allocation found",
            )

        # Get requested lifetime
        lifetime_attr = request.get_attribute(TurnAttributeType.LIFETIME)
        lifetime = None
        if lifetime_attr:
            lifetime = parse_lifetime_attr(lifetime_attr.value)

        # Refresh allocation
        await self.allocation_manager.refresh_allocation(allocation.allocation_id, lifetime)

        # Build response
        lifetime_value = create_lifetime_attr(allocation.get_remaining_time())

        response = StunMessage(
            message_type=0x0104,  # REFRESH response
            message_length=0,
            magic_cookie=MAGIC_COOKIE,
            transaction_id=request.transaction_id,
            attributes=[
                StunAttribute(
                    type=TurnAttributeType.LIFETIME,
                    value=lifetime_value,
                ),
            ],
        )

        logger.debug(f"Refreshed allocation {allocation.allocation_id}")

        return _serialize_stun_message(response)

    async def _handle_create_permission(
        self, request: StunMessage, client_addr: Tuple[str, int]
    ) -> bytes:
        """Handle CREATE_PERMISSION request."""
        allocation = await self.allocation_manager.get_allocation_by_client(client_addr)

        if not allocation:
            return create_error_response(
                request.transaction_id,
                TurnErrorCode.ALLOCATION_MISMATCH,
                "No allocation found",
            )

        # Process all XOR-PEER-ADDRESS attributes
        for attr in request.attributes:
            if attr.type == TurnAttributeType.XOR_PEER_ADDRESS:
                # Parse peer address (simplified - should use proper parser)
                if len(attr.value) >= 8:
                    family = attr.value[1]
                    if family == 0x01:  # IPv4
                        port = int.from_bytes(attr.value[2:4], "big")
                        ip = ".".join(str(b) for b in attr.value[4:8])
                        await self.allocation_manager.add_permission(
                            allocation.allocation_id, (ip, port)
                        )
                        logger.debug(f"Added permission for {ip}:{port}")

        # Success response
        response = StunMessage(
            message_type=0x0108,  # CREATE_PERMISSION response
            message_length=0,
            magic_cookie=MAGIC_COOKIE,
            transaction_id=request.transaction_id,
            attributes=[],
        )

        return _serialize_stun_message(response)

    async def _handle_send(
        self, request: StunMessage, client_addr: Tuple[str, int]
    ) -> bytes:
        """Handle SEND indication (data from client to peer)."""
        allocation = await self.allocation_manager.get_allocation_by_client(client_addr)

        if not allocation:
            return None  # Indications don't get error responses

        # Get DATA attribute
        data_attr = request.get_attribute(TurnAttributeType.DATA)
        if not data_attr:
            return None

        # Get peer address
        peer_attr = request.get_attribute(TurnAttributeType.XOR_PEER_ADDRESS)
        if not peer_attr:
            return None

        # Parse peer address (simplified)
        peer_value = peer_attr.value
        if len(peer_value) >= 8:
            family = peer_value[1]
            if family == 0x01:  # IPv4
                port = int.from_bytes(peer_value[2:4], "big")
                ip = ".".join(str(b) for b in peer_value[4:8])

                # Check permission
                if not allocation.has_permission((ip, port)):
                    logger.warning(f"No permission for peer {ip}:{port}")
                    return None

                # Check bandwidth
                if not await self.bandwidth_limiter.throttle_write(
                    allocation.allocation_id, len(data_attr.value)
                ):
                    logger.warning(f"Bandwidth limit exceeded for {allocation.allocation_id}")
                    return None

                # Relay data to peer
                # In real implementation, this would use the relay socket
                allocation.record_sent(len(data_attr.value))
                await self.throughput_monitor.record_write(len(data_attr.value))

        # Indications don't get responses
        return None

    async def _create_relay_socket(self, allocation: TurnAllocation):
        """
        Create relay socket for allocation.

        Args:
            allocation: Turn allocation
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", allocation.relay_addr[1]))
        sock.setblocking(False)

        self._relay_sockets[allocation.relay_addr[1]] = sock

        # Start relay loop for this socket
        asyncio.create_task(self._relay_loop(allocation, sock))

        logger.debug(f"Created relay socket on port {allocation.relay_addr[1]}")

    async def _relay_loop(self, allocation: TurnAllocation, sock: socket.socket):
        """Relay data loop for an allocation."""
        loop = asyncio.get_event_loop()

        while not allocation.is_expired():
            try:
                data, peer_addr = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 1500),
                    timeout=1.0,
                )

                # Check bandwidth
                if not await self.bandwidth_limiter.throttle_read(
                    allocation.allocation_id, len(data)
                ):
                    continue

                # Update stats
                allocation.record_received(len(data))
                allocation.peer_addr = peer_addr
                await self.throughput_monitor.record_read(len(data))

                # In real implementation, relay data to client
                # This would send a DATA indication back to the client

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in relay loop: {e}")

        sock.close()
        self._relay_sockets.pop(allocation.relay_addr[1], None)

    def stop(self):
        """Stop relay server."""
        self.running = False

        # Close sockets
        if self._control_socket:
            self._control_socket.close()

        for sock in self._relay_sockets.values():
            sock.close()
        self._relay_sockets.clear()

        logger.info("Relay server stopped")

    def get_stats(self) -> dict:
        """Get relay server statistics."""
        allocation_stats = self.allocation_manager.get_stats()
        bandwidth_stats = self.bandwidth_limiter.get_global_stats()

        return {
            "allocations": allocation_stats,
            "bandwidth": bandwidth_stats,
            "relay_sockets": len(self._relay_sockets),
        }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="TURN Relay Server")
    parser.add_argument(
        "--host",
        default=DEFAULT_RELAY_HOST,
        help=f"Host to bind to (default: {DEFAULT_RELAY_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_RELAY_PORT,
        help=f"Control port (default: {DEFAULT_RELAY_PORT})",
    )
    parser.add_argument(
        "--public-ip",
        default=RELAY_PUBLIC_IP,
        help=f"Public IP address (default: {RELAY_PUBLIC_IP})",
    )
    parser.add_argument(
        "--min-port",
        type=int,
        default=50000,
        help="Minimum relay port",
    )
    parser.add_argument(
        "--max-port",
        type=int,
        default=50010,
        help="Maximum relay port",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    server = RelayServer(
        host=args.host,
        port=args.port,
        public_ip=args.public_ip,
        min_port=args.min_port,
        max_port=args.max_port,
    )

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        server.stop()


if __name__ == "__main__":
    main()
