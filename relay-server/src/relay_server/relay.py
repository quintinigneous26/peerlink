"""
UDP Relay Handler
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Tuple

from .models import RelaySession, TransportProtocol, AllocationStatus, BandwidthStats
from .config import config

logger = logging.getLogger(__name__)


class RelayHandler:
    """
    Handles UDP data relay between clients and peers.
    """

    def __init__(self):
        """Initialize relay handler."""
        self._sessions: Dict[str, RelaySession] = {}
        self._client_to_session: Dict[Tuple[str, int], str] = {}
        self._relay_to_session: Dict[Tuple[str, int], str] = {}
        self._lock = asyncio.Lock()
        self._socket: Optional[asyncio.DatagramProtocol] = None
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._bandwidth_stats = BandwidthStats()

    async def start(self, host: str, port_range: Tuple[int, int]) -> None:
        """
        Start relay server.

        Args:
            host: Host to bind to
            port_range: (min_port, max_port) for relay ports
        """
        # Create UDP socket for relay
        loop = asyncio.get_event_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: RelayProtocol(self),
            local_addr=(host, 0),  # Bind to any available port
        )

        logger.info(f"Relay handler started on {self._transport.get_extra_info('sockname')}")

    async def stop(self) -> None:
        """Stop relay handler."""
        if self._transport:
            self._transport.close()
        logger.info("Relay handler stopped")

    async def create_session(
        self,
        client_addr: Tuple[str, int],
        relay_addr: Tuple[str, int],
        lifetime: int = 600,
        transport: TransportProtocol = TransportProtocol.UDP,
    ) -> Optional[RelaySession]:
        """
        Create a new relay session.

        Args:
            client_addr: Client (ip, port)
            relay_addr: Relay (ip, port)
            lifetime: Session lifetime in seconds
            transport: Transport protocol

        Returns:
            RelaySession or None
        """
        async with self._lock:
            # Check if client already has a session
            if client_addr in self._client_to_session:
                logger.warning(f"Client {client_addr} already has a session")
                return None

            # Create session
            import uuid
            session_id = str(uuid.uuid4())

            session = RelaySession(
                session_id=session_id,
                client_addr=client_addr,
                relay_addr=relay_addr,
                transport=transport,
                lifetime=lifetime,
            )

            self._sessions[session_id] = session
            self._client_to_session[client_addr] = session_id
            self._relay_to_session[relay_addr] = session_id

            logger.info(f"Created relay session {session_id} for {client_addr}")
            return session

    async def get_session(self, session_id: str) -> Optional[RelaySession]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    async def get_session_by_client(self, client_addr: Tuple[str, int]) -> Optional[RelaySession]:
        """Get session by client address."""
        session_id = self._client_to_session.get(client_addr)
        if session_id:
            return self._sessions.get(session_id)
        return None

    async def get_session_by_relay(self, relay_addr: Tuple[str, int]) -> Optional[RelaySession]:
        """Get session by relay address."""
        session_id = self._relay_to_session.get(relay_addr)
        if session_id:
            return self._sessions.get(session_id)
        return None

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a relay session.

        Args:
            session_id: Session ID

        Returns:
            True if session was deleted
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            # Remove from indexes
            self._client_to_session.pop(session.client_addr, None)
            self._relay_to_session.pop(session.relay_addr, None)
            self._sessions.pop(session_id, None)

            logger.info(f"Deleted relay session {session_id}")
            return True

    async def add_permission(self, session_id: str, peer_addr: Tuple[str, int]) -> bool:
        """Add permission for peer to send data."""
        session = self._sessions.get(session_id)
        if session:
            return session.add_permission(peer_addr)
        return False

    async def handle_client_data(self, client_addr: Tuple[str, int], data: bytes, peer_addr: Tuple[str, int]) -> bool:
        """
        Handle data from client to relay to peer.

        Args:
            client_addr: Client address
            data: Data to relay
            peer_addr: Destination peer address

        Returns:
            True if data was relayed
        """
        session = await self.get_session_by_client(client_addr)
        if not session:
            logger.warning(f"No session found for client {client_addr}")
            return False

        # Check permissions
        if not session.has_permission(peer_addr):
            logger.warning(f"Client {client_addr} has no permission for peer {peer_addr}")
            return False

        # Check if session is expired
        if session.is_expired(session.lifetime):
            logger.warning(f"Session {session.session_id} has expired")
            await self.delete_session(session.session_id)
            return False

        # Update session
        session.update_activity()
        session.packets_sent += 1
        session.bytes_sent += len(data)

        # Update bandwidth stats
        self._bandwidth_stats.add_sample(len(data))

        # Send data to peer via UDP socket
        try:
            if not self._transport:
                logger.error("Transport not initialized")
                return False

            self._transport.sendto(data, peer_addr)
            logger.debug(f"Relayed {len(data)} bytes from {client_addr} to {peer_addr}")
            return True
        except Exception as e:
            logger.error(f"Failed to send data to peer {peer_addr}: {e}")
            return False

    async def handle_peer_data(self, relay_addr: Tuple[str, int], data: bytes) -> bool:
        """
        Handle data from peer to relay to client.

        Args:
            relay_addr: Relay address
            data: Data to relay

        Returns:
            True if data was relayed
        """
        session = await self.get_session_by_relay(relay_addr)
        if not session:
            logger.warning(f"No session found for relay addr {relay_addr}")
            return False

        # Check if session is expired
        if session.is_expired(session.lifetime):
            logger.warning(f"Session {session.session_id} has expired")
            await self.delete_session(session.session_id)
            return False

        # Update session
        session.update_activity()
        session.packets_received += 1
        session.bytes_received += len(data)

        # Send data to client via UDP socket
        try:
            if not self._transport:
                logger.error("Transport not initialized")
                return False

            self._transport.sendto(data, session.client_addr)
            logger.debug(f"Relayed {len(data)} bytes from peer to {session.client_addr}")
            return True
        except Exception as e:
            logger.error(f"Failed to send data to client {session.client_addr}: {e}")
            return False

    async def cleanup_expired(self) -> int:
        """
        Clean up expired sessions.

        Returns:
            Number of sessions removed
        """
        expired = []

        async with self._lock:
            for session_id, session in self._sessions.items():
                if session.is_expired(session.lifetime):
                    expired.append(session_id)

        for session_id in expired:
            await self.delete_session(session_id)

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired relay sessions")

        return len(expired)

    def get_stats(self) -> dict:
        """Get relay statistics."""
        active_sessions = [s for s in self._sessions.values() if s.status == AllocationStatus.ACTIVE]

        total_bytes_sent = sum(s.bytes_sent for s in active_sessions)
        total_bytes_received = sum(s.bytes_received for s in active_sessions)
        total_packets = sum(s.packets_sent + s.packets_received for s in active_sessions)

        return {
            "active_sessions": len(active_sessions),
            "total_bytes_sent": total_bytes_sent,
            "total_bytes_received": total_bytes_received,
            "total_packets": total_packets,
            "current_bandwidth_bps": self._bandwidth_stats.get_current_rate(),
            "peak_bandwidth_bps": self._bandwidth_stats.peak_bps,
        }


class RelayProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for relay."""

    def __init__(self, handler: RelayHandler):
        """Initialize protocol."""
        self.handler = handler
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        """Called when connection is made."""
        self.transport = transport
        logger.info("Relay UDP protocol connected")

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Called when datagram is received."""
        # Route to appropriate handler
        asyncio.create_task(self._handle_datagram(data, addr))

    async def _handle_datagram(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle incoming datagram."""
        # Check if this is from a client or peer
        session = await self.handler.get_session_by_client(addr)

        if session:
            # Data from client - need peer address from data
            # For TURN, peer info is in the message
            # This is simplified - actual TURN protocol parsing needed
            logger.debug(f"Received {len(data)} bytes from client {addr}")
        else:
            # Data from peer - relay to client
            session = await self.handler.get_session_by_relay(addr)
            if session:
                await self.handler.handle_peer_data(addr, data)

    def error_received(self, exc: Exception) -> None:
        """Called when error is received."""
        logger.error(f"Relay protocol error: {exc}")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Called when connection is lost."""
        logger.info("Relay UDP protocol disconnected")


# Global relay handler
_handler: Optional[RelayHandler] = None


def get_relay_handler() -> RelayHandler:
    """Get global relay handler instance."""
    global _handler
    if _handler is None:
        _handler = RelayHandler()
    return _handler
