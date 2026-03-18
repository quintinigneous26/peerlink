"""
STUN Server Integration Tests
"""

import asyncio
import socket
import pytest

from src.messages import MessageType, MAGIC_COOKIE, StunMessage
from src.server import STUNServer


@pytest.mark.asyncio
class TestSTUNServer:
    """Test STUN server functionality."""

    async def test_server_start_stop(self):
        """Test starting and stopping the server."""
        server = STUNServer(host="127.0.0.1", udp_port=13478, tcp_port=13479)

        # Start server in background (UDP only for faster test)
        task = asyncio.create_task(server.start(udp_only=True))

        # Wait for server to be ready
        await server._started.wait()

        # Stop server
        server.stop()

        # Wait for task to complete
        try:
            await asyncio.wait_for(task, timeout=1.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

    async def test_udp_binding_request(self):
        """Test UDP binding request handling."""
        server = STUNServer(host="127.0.0.1", udp_port=13478, tcp_port=13479)

        # Start server in background (UDP only)
        task = asyncio.create_task(server.start(udp_only=True))

        # Wait for server to be ready
        await server._started.wait()

        try:
            # Create STUN binding request
            transaction_id = b"\x11\x22\x33\x44" * 3
            request_data = (
                MessageType.BINDING_REQUEST.to_bytes(2, "big")
                + (0).to_bytes(2, "big")
                + MAGIC_COOKIE.to_bytes(4, "big")
                + transaction_id
            )

            # Use asyncio UDP socket instead of blocking socket
            loop = asyncio.get_event_loop()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: asyncio.DatagramProtocol(),
                local_addr=("127.0.0.1", 0),  # Bind to any available port
            )

            # Send request
            transport.sendto(request_data, ("127.0.0.1", 13478))

            # Wait for response
            future = asyncio.Future()

            def protocol_factory():
                class TestProtocol:
                    def __init__(self):
                        self.data = []

                    def connection_made(self, transport):
                        self.transport = transport

                    def datagram_received(self, data, addr):
                        if not future.done():
                            future.set_result((data, addr))

                    def error_received(self, exc):
                        if not future.done():
                            future.set_exception(exc)

                return TestProtocol()

            # Close the old endpoint and create a new one with protocol
            transport.close()

            transport, protocol = await loop.create_datagram_endpoint(
                protocol_factory,
                local_addr=("127.0.0.1", 0),
            )
            transport.sendto(request_data, ("127.0.0.1", 13478))

            try:
                data, addr = await asyncio.wait_for(future, timeout=2.0)

                # Verify response
                assert len(data) >= 20
                assert data[0:2] == MessageType.BINDING_RESPONSE.to_bytes(2, "big")
                assert data[4:8] == MAGIC_COOKIE.to_bytes(4, "big")
                assert data[8:20] == transaction_id
            finally:
                transport.close()

        finally:
            server.stop()
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass


@pytest.mark.asyncio
class TestNATDetection:
    """Test NAT type detection."""

    async def test_get_local_ip(self):
        """Test getting local IP address."""
        from src.nat_detection import get_local_ip

        ip = get_local_ip()
        assert ip is not None
        assert isinstance(ip, str)
        assert len(ip.split(".")) == 4  # IPv4
