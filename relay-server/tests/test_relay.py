"""
Relay Handler Tests
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.relay_server.relay import RelayHandler, RelayProtocol
from src.relay_server.models import TransportProtocol


@pytest.mark.asyncio
class TestRelayHandler:
    """Test relay handler functionality."""

    async def test_handler_start_stop(self):
        """Test starting and stopping relay handler."""
        handler = RelayHandler()

        await handler.start("127.0.0.1", (10000, 10009))
        assert handler._transport is not None

        await handler.stop()

    async def test_create_session(self):
        """Test creating a relay session."""
        handler = RelayHandler()

        session = await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
            lifetime=600,
        )

        assert session is not None
        assert session.client_addr == ("192.168.1.1", 12345)
        assert session.relay_addr == ("10.0.0.1", 50000)
        assert session.lifetime == 600

    async def test_get_session_by_client(self):
        """Test getting session by client address."""
        handler = RelayHandler()

        session = await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
        )

        # Get by client address
        found = await handler.get_session_by_client(("192.168.1.1", 12345))
        assert found is not None
        assert found.session_id == session.session_id

        # Non-existent client
        found = await handler.get_session_by_client(("192.168.1.2", 12346))
        assert found is None

    async def test_delete_session(self):
        """Test deleting a session."""
        handler = RelayHandler()

        session = await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
        )

        session_id = session.session_id

        # Delete session
        deleted = await handler.delete_session(session_id)
        assert deleted is True

        # Should not exist anymore
        found = await handler.get_session(session_id)
        assert found is None

    async def test_add_permission(self):
        """Test adding peer permission."""
        handler = RelayHandler()

        session = await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
        )

        # Add permission
        added = await handler.add_permission(
            session.session_id,
            ("10.0.0.2", 60000)
        )
        assert added is True

        # Check permission
        assert session.has_permission(("10.0.0.2", 60000)) is True

    async def test_handle_client_data_success(self):
        """Test handling client data with UDP send."""
        handler = RelayHandler()

        # Create mock transport
        mock_transport = Mock()
        mock_transport.sendto = Mock()
        handler._transport = mock_transport

        # Create session with permission
        session = await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
        )
        peer_addr = ("10.0.0.2", 60000)
        await handler.add_permission(session.session_id, peer_addr)

        # Handle client data
        data = b"test data"
        result = await handler.handle_client_data(
            ("192.168.1.1", 12345),
            data,
            peer_addr
        )

        assert result is True
        mock_transport.sendto.assert_called_once_with(data, peer_addr)
        assert session.packets_sent == 1
        assert session.bytes_sent == len(data)

    async def test_handle_client_data_no_session(self):
        """Test handling client data without session."""
        handler = RelayHandler()

        result = await handler.handle_client_data(
            ("192.168.1.1", 12345),
            b"test data",
            ("10.0.0.2", 60000)
        )

        assert result is False

    async def test_handle_client_data_no_permission(self):
        """Test handling client data without permission."""
        handler = RelayHandler()

        # Create session without permission
        await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
        )

        result = await handler.handle_client_data(
            ("192.168.1.1", 12345),
            b"test data",
            ("10.0.0.2", 60000)  # No permission for this peer
        )

        assert result is False

    async def test_handle_client_data_no_transport(self):
        """Test handling client data without transport."""
        handler = RelayHandler()

        # Create session with permission
        session = await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
        )
        peer_addr = ("10.0.0.2", 60000)
        await handler.add_permission(session.session_id, peer_addr)

        # No transport set
        handler._transport = None

        result = await handler.handle_client_data(
            ("192.168.1.1", 12345),
            b"test data",
            peer_addr
        )

        assert result is False

    async def test_handle_peer_data_success(self):
        """Test handling peer data with UDP send."""
        handler = RelayHandler()

        # Create mock transport
        mock_transport = Mock()
        mock_transport.sendto = Mock()
        handler._transport = mock_transport

        # Create session
        session = await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
        )

        # Handle peer data
        data = b"peer response"
        result = await handler.handle_peer_data(
            ("10.0.0.1", 50000),
            data
        )

        assert result is True
        mock_transport.sendto.assert_called_once_with(data, ("192.168.1.1", 12345))
        assert session.packets_received == 1
        assert session.bytes_received == len(data)

    async def test_handle_peer_data_no_session(self):
        """Test handling peer data without session."""
        handler = RelayHandler()

        result = await handler.handle_peer_data(
            ("10.0.0.1", 50000),
            b"peer data"
        )

        assert result is False

    async def test_handle_peer_data_no_transport(self):
        """Test handling peer data without transport."""
        handler = RelayHandler()

        # Create session
        await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
        )

        # No transport set
        handler._transport = None

        result = await handler.handle_peer_data(
            ("10.0.0.1", 50000),
            b"peer data"
        )

        assert result is False

    async def test_cleanup_expired(self):
        """Test cleanup of expired sessions."""
        handler = RelayHandler()

        # Create session with short lifetime
        session = await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
            lifetime=1,
        )

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Cleanup
        cleaned = await handler.cleanup_expired()
        assert cleaned == 1

        # Session should be gone
        found = await handler.get_session(session.session_id)
        assert found is None

    async def test_get_stats(self):
        """Test getting relay statistics."""
        handler = RelayHandler()

        # Create mock transport
        mock_transport = Mock()
        mock_transport.sendto = Mock()
        handler._transport = mock_transport

        # Create session
        session = await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
        )
        peer_addr = ("10.0.0.2", 60000)
        await handler.add_permission(session.session_id, peer_addr)

        # Send some data
        await handler.handle_client_data(
            ("192.168.1.1", 12345),
            b"test data 1",
            peer_addr
        )
        await handler.handle_peer_data(
            ("10.0.0.1", 50000),
            b"test data 2"
        )

        stats = handler.get_stats()
        assert stats["active_sessions"] == 1
        assert stats["total_bytes_sent"] > 0
        assert stats["total_bytes_received"] > 0
        assert stats["total_packets"] == 2


@pytest.mark.asyncio
class TestRelayProtocol:
    """Test relay protocol."""

    async def test_protocol_connection(self):
        """Test protocol connection."""
        handler = RelayHandler()
        protocol = RelayProtocol(handler)

        # Mock transport
        mock_transport = Mock()
        protocol.connection_made(mock_transport)

        assert protocol.transport is not None

    async def test_protocol_datagram_received(self):
        """Test receiving datagram."""
        handler = RelayHandler()
        protocol = RelayProtocol(handler)

        # Create session
        await handler.create_session(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
        )

        # Mock transport
        mock_transport = Mock()
        mock_transport.sendto = Mock()
        handler._transport = mock_transport

        # Receive datagram from peer
        protocol.datagram_received(b"test data", ("10.0.0.1", 50000))

        # Give async task time to execute
        await asyncio.sleep(0.1)

        # Should have relayed to client
        mock_transport.sendto.assert_called()

