"""
QUIC 0-RTT Connection Optimization

This module implements 0-RTT (zero round-trip time) connection
establishment for QUIC, allowing faster connection resumption.

Key features:
- Session ticket caching and reuse
- Early data sending
- Connection migration support
- Optimized handshake for repeated connections

Reference: RFC 9000 (QUIC), RFC 8446 (TLS 1.3)
"""

import asyncio
import logging
import time
import hashlib
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass, field
from enum import Enum
from ipaddress import ip_address

logger = logging.getLogger("p2p_engine.transport.quic_0rtt")


# ==================== Constants ====================

# 0-RTT settings
MAX_SESSION_TICKETS = 100
SESSION_TICKET_LIFETIME = 604800  # 7 days in seconds
0RTT_MAX_EARLY_DATA_SIZE = 65536  # 64KB

# Connection migration
MIGRATION_TIMEOUT = 10.0  # seconds
MAX_MIGRATION_ATTEMPTS = 3


# ==================== Session Ticket Storage ====================

class SessionTicketStatus(Enum):
    """Status of a session ticket."""
    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    USED = "used"


@dataclass
class CachedSessionTicket:
    """
    Cached QUIC session ticket for 0-RTT.

    Attributes:
        ticket_data: Raw ticket data
        server_name: Server hostname
        transport_params: Transport parameters
        created_at: Creation timestamp
        expires_at: Expiration timestamp
        last_used: Last usage timestamp
        usage_count: Number of times used
        status: Ticket status
    """
    ticket_data: bytes
    server_name: str
    transport_params: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    last_used: float = 0.0
    usage_count: int = 0
    status: SessionTicketStatus = SessionTicketStatus.VALID

    def __post_init__(self):
        if self.expires_at == 0.0:
            self.expires_at = self.created_at + SESSION_TICKET_LIFETIME

    @property
    def is_expired(self) -> bool:
        """Check if ticket is expired."""
        return time.time() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if ticket is valid for use."""
        return (
            self.status == SessionTicketStatus.VALID and
            not self.is_expired
        )

    @property
    def age_seconds(self) -> float:
        """Get ticket age in seconds."""
        return time.time() - self.created_at

    def mark_used(self) -> None:
        """Mark ticket as used."""
        self.last_used = time.time()
        self.usage_count += 1

    def revoke(self) -> None:
        """Revoke ticket."""
        self.status = SessionTicketStatus.REVOKED


class SessionTicketStore:
    """
    Storage for QUIC session tickets.

    Implements LRU eviction and automatic cleanup.
    """

    def __init__(self, max_tickets: int = MAX_SESSION_TICKETS):
        self._max_tickets = max_tickets
        self._tickets: Dict[str, CachedSessionTicket] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Start background cleanup task."""
        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def get_ticket(
        self,
        server_name: str,
    ) -> Optional[CachedSessionTicket]:
        """
        Get a valid ticket for the server.

        Args:
            server_name: Server hostname

        Returns:
            CachedSessionTicket if available, None otherwise
        """
        async with self._lock:
            ticket = self._tickets.get(server_name)

            if ticket and ticket.is_valid:
                ticket.mark_used()
                return ticket

            # Remove invalid ticket
            if ticket:
                del self._tickets[server_name]

            return None

    async def store_ticket(
        self,
        server_name: str,
        ticket_data: bytes,
        transport_params: Dict[str, Any],
    ) -> CachedSessionTicket:
        """
        Store a new session ticket.

        Args:
            server_name: Server hostname
            ticket_data: Raw ticket data
            transport_params: QUIC transport parameters

        Returns:
            CachedSessionTicket instance
        """
        async with self._lock:
            # Evict oldest if at capacity
            if len(self._tickets) >= self._max_tickets:
                oldest_key = min(
                    self._tickets.keys(),
                    key=lambda k: self._tickets[k].last_used
                )
                del self._tickets[oldest_key]

            ticket = CachedSessionTicket(
                ticket_data=ticket_data,
                server_name=server_name,
                transport_params=transport_params,
            )

            self._tickets[server_name] = ticket
            logger.debug(f"Stored session ticket for {server_name}")

            return ticket

    async def revoke_ticket(self, server_name: str) -> None:
        """Revoke ticket for server."""
        async with self._lock:
            ticket = self._tickets.get(server_name)
            if ticket:
                ticket.revoke()

    async def clear_tickets(self) -> None:
        """Clear all tickets."""
        async with self._lock:
            self._tickets.clear()

    async def _cleanup_loop(self) -> None:
        """Periodically cleanup expired tickets."""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour

                async with self._lock:
                    expired = [
                        server_name
                        for server_name, ticket in self._tickets.items()
                        if ticket.is_expired or ticket.status != SessionTicketStatus.VALID
                    ]

                    for server_name in expired:
                        del self._tickets[server_name]

                    if expired:
                        logger.debug(f"Cleaned up {len(expired)} expired tickets")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Session ticket cleanup error: {e}")

    @property
    def ticket_count(self) -> int:
        """Get number of stored tickets."""
        return len(self._tickets)


# ==================== 0-RTT Connection Manager ====================

@dataclass
class ConnectionMetrics:
    """Metrics for 0-RTT connections."""
    total_connections: int = 0
    zero_rtt_connections: int = 0
    zero_rtt_success_rate: float = 0.0
    avg_handshake_time_ms: float = 0.0
    avg_0rtt_handshake_time_ms: float = 0.0
    early_data_bytes_sent: int = 0


class ZeroRTTConnectionManager:
    """
    Manages 0-RTT connections for QUIC.

    Provides:
    - Session ticket caching
    - Early data transmission
    - Connection establishment optimization
    """

    def __init__(
        self,
        ticket_store: Optional[SessionTicketStore] = None,
        enable_0rtt: bool = True,
        max_early_data_size: int = 0RTT_MAX_EARLY_DATA_SIZE,
    ):
        self._ticket_store = ticket_store or SessionTicketStore()
        self._enable_0rtt = enable_0rtt
        self._max_early_data_size = max_early_data_size

        # Metrics
        self._metrics = ConnectionMetrics()
        self._handshake_times: List[float] = []
        self._0rtt_handshake_times: List[float] = []

        # Start cleanup
        self._ticket_store.start()

    async def stop(self) -> None:
        """Stop the manager."""
        await self._ticket_store.stop()

    async def connect_with_0rtt(
        self,
        host: str,
        port: int,
        configuration: Any,
        early_data: Optional[bytes] = None,
        protocol_factory: Optional[Callable] = None,
    ) -> Tuple[Any, bool]:
        """
        Establish QUIC connection with 0-RTT if possible.

        Args:
            host: Target host
            port: Target port
            configuration: QUIC configuration
            early_data: Data to send in 0-RTT
            protocol_factory: Protocol factory function

        Returns:
            Tuple of (connection, used_0rtt)
        """
        start_time = time.time()
        used_0rtt = False

        if not self._enable_0rtt:
            # Regular connection
            from aioquic.asyncio import connect
            connection = await connect(
                host,
                port,
                configuration=configuration,
                create_protocol=protocol_factory,
            )
            self._record_handshake(time.time() - start_time, used_0rtt)
            return connection, False

        # Try to get session ticket
        ticket = await self._ticket_store.get_ticket(host)

        if ticket and early_data and len(early_data) <= self._max_early_data_size:
            # 0-RTT connection with early data
            try:
                from aioquic.asyncio import connect

                # Add session ticket to configuration
                configuration.session_ticket = ticket.ticket_data

                connection = await connect(
                    host,
                    port,
                    configuration=configuration,
                    create_protocol=protocol_factory,
                )

                # Send early data
                if early_data and hasattr(connection, 'send_early_data'):
                    connection.send_early_data(early_data)
                    self._metrics.early_data_bytes_sent += len(early_data)

                used_0rtt = True
                logger.debug(f"Established 0-RTT connection to {host}:{port}")

            except Exception as e:
                logger.warning(f"0-RTT connection failed: {e}, falling back to regular")
                # Fallback to regular connection
                from aioquic.asyncio import connect
                connection = await connect(
                    host,
                    port,
                    configuration=configuration,
                    create_protocol=protocol_factory,
                )
        else:
            # Regular connection (no ticket or no early data)
            from aioquic.asyncio import connect
            connection = await connect(
                host,
                port,
                configuration=configuration,
                create_protocol=protocol_factory,
            )

        self._record_handshake(time.time() - start_time, used_0rtt)
        return connection, used_0rtt

    async def store_session_ticket(
        self,
        server_name: str,
        ticket_data: bytes,
        transport_params: Dict[str, Any],
    ) -> None:
        """
        Store session ticket from server.

        Args:
            server_name: Server hostname
            ticket_data: Raw ticket data
            transport_params: QUIC transport parameters
        """
        await self._ticket_store.store_ticket(
            server_name,
            ticket_data,
            transport_params,
        )

    def _record_handshake(self, duration_sec: float, used_0rtt: bool) -> None:
        """Record handshake metrics."""
        duration_ms = duration_sec * 1000

        self._metrics.total_connections += 1
        self._handshake_times.append(duration_ms)

        if used_0rtt:
            self._metrics.zero_rtt_connections += 1
            self._0rtt_handshake_times.append(duration_ms)

        # Update averages
        self._metrics.avg_handshake_time_ms = statistics.mean(self._handshake_times)

        if self._0rtt_handshake_times:
            self._metrics.avg_0rtt_handshake_time_ms = statistics.mean(
                self._0rtt_handshake_times
            )

        self._metrics.zero_rtt_success_rate = (
            self._metrics.zero_rtt_connections / self._metrics.total_connections
        )

    @property
    def metrics(self) -> ConnectionMetrics:
        """Get connection metrics."""
        return self._metrics

    def get_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics."""
        return {
            "total_connections": self._metrics.total_connections,
            "zero_rtt_connections": self._metrics.zero_rtt_connections,
            "zero_rtt_success_rate": f"{self._metrics.zero_rtt_success_rate:.1%}",
            "avg_handshake_time_ms": self._metrics.avg_handshake_time_ms,
            "avg_0rtt_handshake_time_ms": self._metrics.avg_0rtt_handshake_time_ms,
            "early_data_bytes_sent": self._metrics.early_data_bytes_sent,
            "session_tickets": self._ticket_store.ticket_count,
            "handshake_speedup": (
                self._metrics.avg_handshake_time_ms /
                max(self._metrics.avg_0rtt_handshake_time_ms, 0.1)
                if self._metrics.avg_0rtt_handshake_time_ms > 0
                else 1.0
            ),
        }


# ==================== Connection Migration ====================

class ConnectionMigration:
    """
    QUIC connection migration support.

    Allows connections to survive network changes (e.g., WiFi to cellular).
    """

    def __init__(self, max_attempts: int = MAX_MIGRATION_ATTEMPTS):
        self._max_attempts = max_attempts
        self._active_migrations: Dict[str, asyncio.Task] = {}

    async def migrate_connection(
        self,
        connection: Any,
        new_address: Tuple[str, int],
        timeout: float = MIGRATION_TIMEOUT,
    ) -> bool:
        """
        Migrate connection to new address.

        Args:
            connection: QUIC connection to migrate
            new_address: New (host, port) address
            timeout: Migration timeout

        Returns:
            True if migration succeeded
        """
        connection_id = id(connection)

        # Cancel any existing migration
        if connection_id in self._active_migrations:
            self._active_migrations[connection_id].cancel()

        # Start migration
        task = asyncio.create_task(
            self._do_migration(connection, new_address, timeout)
        )
        self._active_migrations[connection_id] = task

        try:
            result = await asyncio.wait_for(task, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.error(f"Connection migration to {new_address} timed out")
            return False
        finally:
            self._active_migrations.pop(connection_id, None)

    async def _do_migration(
        self,
        connection: Any,
        new_address: Tuple[str, int],
        timeout: float,
    ) -> bool:
        """Perform connection migration."""
        host, port = new_address

        for attempt in range(self._max_attempts):
            try:
                # Initiate path validation
                if hasattr(connection, 'initiate_path_validation'):
                    await connection.initiate_path_validation(host, port)

                # Wait for path to be validated
                if hasattr(connection, 'wait_path_validated'):
                    await asyncio.wait_for(
                        connection.wait_path_validated(),
                        timeout=timeout / self._max_attempts
                    )

                logger.debug(f"Connection migrated to {host}:{port}")
                return True

            except Exception as e:
                logger.warning(
                    f"Migration attempt {attempt + 1} failed: {e}"
                )
                await asyncio.sleep(0.5)

        return False

    def cancel_migration(self, connection: Any) -> None:
        """Cancel ongoing migration for connection."""
        connection_id = id(connection)
        task = self._active_migrations.pop(connection_id, None)
        if task:
            task.cancel()


__all__ = [
    "SessionTicketStore",
    "CachedSessionTicket",
    "SessionTicketStatus",
    "ZeroRTTConnectionManager",
    "ConnectionMigration",
    "ConnectionMetrics",
]
