"""
STUN Server Implementation

Implements a high-performance async STUN server based on RFC 5389.
"""

import asyncio
import logging
import os
import socket
from typing import Optional, Tuple

from .messages import (
    MAGIC_COOKIE,
    AttributeType,
    ErrorCode,
    MessageType,
    StunMessage,
    StunAttribute,
    create_error_response,
    create_xor_mapped_address_attr,
)
from .nat_detection import NATType, detect_nat_type, get_local_ip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("stun-server")

# Server configuration
DEFAULT_UDP_PORT = int(os.environ.get("STUN_UDP_PORT", "3478"))
DEFAULT_TCP_PORT = int(os.environ.get("STUN_TCP_PORT", "3479"))
DEFAULT_HOST = os.environ.get("STUN_HOST", "0.0.0.0")


class STUNServer:
    """
    STUN Server implementation.

    Handles both UDP and TCP STUN requests according to RFC 5389.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        udp_port: int = DEFAULT_UDP_PORT,
        tcp_port: int = DEFAULT_TCP_PORT,
    ):
        """
        Initialize STUN server.

        Args:
            host: Host address to bind to
            udp_port: UDP port for STUN requests
            tcp_port: TCP port for STUN requests
        """
        self.host = host
        self.udp_port = udp_port
        self.tcp_port = tcp_port
        self.running = False
        self._started = asyncio.Event()

    async def handle_udp_packet(self, data: bytes, addr: Tuple[str, int]) -> Optional[bytes]:
        """
        Handle incoming UDP STUN packet.

        Args:
            data: Raw packet data
            addr: (ip, port) of sender

        Returns:
            Response bytes or None
        """
        # Parse STUN message
        message = StunMessage.parse(data)

        if message is None:
            logger.warning(f"Invalid STUN message from {addr}")
            return None

        # Log request
        logger.debug(
            f"Received STUN request type=0x{message.message_type:04x} "
            f"from {addr[0]}:{addr[1]}"
        )

        # Handle binding request
        if message.message_type == MessageType.BINDING_REQUEST:
            return self._create_binding_response(message, addr)
        else:
            # Unknown message type
            logger.warning(
                f"Unknown message type 0x{message.message_type:04x} from {addr}"
            )
            return create_error_response(
                message.transaction_id,
                ErrorCode.BAD_REQUEST,
                "Unknown message type",
            )

    def _create_binding_response(
        self, request: StunMessage, client_addr: Tuple[str, int]
    ) -> bytes:
        """
        Create binding success response.

        Args:
            request: Original STUN request
            client_addr: Client's (ip, port)

        Returns:
            Serialized STUN response
        """
        client_ip, client_port = client_addr

        # Create XOR-MAPPED-ADDRESS attribute
        xor_mapped_attr = create_xor_mapped_address_attr(
            client_ip, client_port, request.transaction_id
        )

        # Build response message
        response = StunMessage(
            message_type=MessageType.BINDING_RESPONSE,
            message_length=0,  # Will be calculated during serialization
            magic_cookie=MAGIC_COOKIE,
            transaction_id=request.transaction_id,
            attributes=[
                StunAttribute(
                    type=AttributeType.XOR_MAPPED_ADDRESS,
                    value=xor_mapped_attr,
                )
            ],
        )

        return response.serialize()

    async def udp_server(self):
        """Run UDP STUN server."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        try:
            sock.bind((self.host, self.udp_port))
            logger.info(f"UDP STUN server listening on {self.host}:{self.udp_port}")
        except OSError as e:
            logger.error(f"Failed to bind UDP socket: {e}")
            raise

        sock.setblocking(False)

        self.running = True
        self._started.set()  # Signal that server is ready

        while self.running:
            try:
                data, addr = await asyncio.get_event_loop().sock_recvfrom(sock, 512)

                # Handle packet
                response = await self.handle_udp_packet(data, addr)

                if response:
                    await asyncio.get_event_loop().sock_sendto(sock, response, addr)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error handling UDP packet: {e}")

        sock.close()
        logger.info("UDP STUN server stopped")

    async def tcp_server(self):
        """Run TCP STUN server."""
        server = await asyncio.start_server(
            self._handle_tcp_client, self.host, self.tcp_port
        )

        logger.info(f"TCP STUN server listening on {self.host}:{self.tcp_port}")

        async with server:
            self.running = True
            await server.serve_forever()

    async def _handle_tcp_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle TCP STUN client connection."""
        addr = writer.get_extra_info("peername")

        try:
            # Read STUN message length (first 2 bytes after header)
            # STUN over TCP uses framing: 2-byte length + message
            header = await reader.readexactly(20)

            # Extract message length from header
            message_length = int.from_bytes(header[2:4], "big")

            # Read rest of message
            rest = await reader.readexactly(4 + message_length)
            data = header + rest

            # Parse and handle
            response = await self.handle_udp_packet(data, addr)

            if response:
                # Send response with framing
                response_length = len(response)
                framed_response = response_length.to_bytes(2, "big") + response
                writer.write(framed_response)
                await writer.drain()

        except asyncio.IncompleteReadError:
            logger.warning(f"Incomplete read from TCP client {addr}")
        except Exception as e:
            logger.error(f"Error handling TCP client {addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self, udp_only: bool = False):
        """
        Start STUN server.

        Args:
            udp_only: If True, only start UDP server (useful for testing)
        """
        self.running = True

        if udp_only:
            # Start UDP server only
            logger.info("STUN server started (UDP only)")
            await self.udp_server()
        else:
            # Start both servers
            udp_task = asyncio.create_task(self.udp_server())
            tcp_task = asyncio.create_task(self.tcp_server())

            logger.info("STUN server started")

            # Wait for either to complete (shouldn't happen)
            await asyncio.gather(udp_task, tcp_task, return_exceptions=True)

    def stop(self):
        """Stop STUN server."""
        self.running = False
        logger.info("STUN server stopping...")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="STUN Server (RFC 5389)")
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Host to bind to (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--udp-port",
        type=int,
        default=DEFAULT_UDP_PORT,
        help=f"UDP port (default: {DEFAULT_UDP_PORT})",
    )
    parser.add_argument(
        "--tcp-port",
        type=int,
        default=DEFAULT_TCP_PORT,
        help=f"TCP port (default: {DEFAULT_TCP_PORT})",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    server = STUNServer(host=args.host, udp_port=args.udp_port, tcp_port=args.tcp_port)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        server.stop()


if __name__ == "__main__":
    main()
