"""
TURN Allocation Manager

Manages TURN allocations, port allocation, and permission handling.
"""

import asyncio
import logging
import os
import random
import time
import uuid
from typing import Dict, Optional, Set, Tuple

from .messages import TurnAllocation

logger = logging.getLogger("relay-server")

# Configuration
DEFAULT_MIN_PORT = int(os.environ.get("RELAY_MIN_PORT", "50000"))
DEFAULT_MAX_PORT = int(os.environ.get("RELAY_MAX_PORT", "50100"))
DEFAULT_ALLOCATION_LIFETIME = int(os.environ.get("RELAY_ALLOCATION_LIFETIME", "600"))
DEFAULT_MAX_ALLOCATIONS = int(os.environ.get("RELAY_MAX_ALLOCATIONS", "1000"))


class PortPool:
    """
    Manages a pool of available relay ports.

    Uses a bitmap to track port availability for efficient allocation.
    """

    def __init__(self, min_port: int = DEFAULT_MIN_PORT, max_port: int = DEFAULT_MAX_PORT):
        """
        Initialize port pool.

        Args:
            min_port: Minimum port number
            max_port: Maximum port number (inclusive)
        """
        self.min_port = min_port
        self.max_port = max_port
        self.total_ports = max_port - min_port + 1
        self._available_ports: Set[int] = set(range(min_port, max_port + 1))
        self._lock = asyncio.Lock()

    async def acquire(self) -> Optional[int]:
        """
        Acquire a port from the pool.

        Returns:
            Port number or None if pool exhausted
        """
        async with self._lock:
            if not self._available_ports:
                return None
            # Random selection for load distribution
            port = random.choice(tuple(self._available_ports))
            self._available_ports.remove(port)
            logger.debug(f"Acquired port {port}, {len(self._available_ports)} remaining")
            return port

    async def release(self, port: int) -> bool:
        """
        Release a port back to the pool.

        Args:
            port: Port to release

        Returns:
            True if port was released, False if not in pool
        """
        async with self._lock:
            if self.min_port <= port <= self.max_port:
                if port not in self._available_ports:
                    self._available_ports.add(port)
                    logger.debug(f"Released port {port}, {len(self._available_ports)} available")
                    return True
            return False

    def available_count(self) -> int:
        """Get number of available ports."""
        return len(self._available_ports)

    def usage_percentage(self) -> float:
        """Get port pool usage as percentage."""
        used = self.total_ports - len(self._available_ports)
        return (used / self.total_ports) * 100


class AllocationManager:
    """
    Manages TURN allocations.

    Handles allocation creation, refresh, permission management, and cleanup.
    """

    def __init__(
        self,
        min_port: int = DEFAULT_MIN_PORT,
        max_port: int = DEFAULT_MAX_PORT,
        default_lifetime: int = DEFAULT_ALLOCATION_LIFETIME,
        max_allocations: int = DEFAULT_MAX_ALLOCATIONS,
    ):
        """
        Initialize allocation manager.

        Args:
            min_port: Minimum relay port
            max_port: Maximum relay port
            default_lifetime: Default allocation lifetime in seconds
            max_allocations: Maximum concurrent allocations
        """
        self.port_pool = PortPool(min_port, max_port)
        self.default_lifetime = default_lifetime
        self.max_allocations = max_allocations
        self._allocations: Dict[str, TurnAllocation] = {}
        self._client_to_allocation: Dict[Tuple[str, int], str] = {}
        self._relay_to_allocation: Dict[Tuple[str, int], str] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start allocation manager and cleanup task."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Allocation manager started")

    async def stop(self):
        """Stop allocation manager."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Allocation manager stopped")

    async def _cleanup_loop(self):
        """Periodically cleanup expired allocations."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def create_allocation(
        self,
        client_addr: Tuple[str, int],
        relay_addr: Tuple[str, int],
        transport: str = "udp",
        lifetime: Optional[int] = None,
    ) -> Optional[TurnAllocation]:
        """
        Create a new allocation.

        Args:
            client_addr: Client's (ip, port)
            relay_addr: Relay server's (ip, port)
            transport: Transport protocol
            lifetime: Requested lifetime (uses default if None)

        Returns:
            TurnAllocation or None if max allocations reached
        """
        async with self._lock:
            # Check allocation limit
            if len(self._allocations) >= self.max_allocations:
                logger.warning(f"Max allocations ({self.max_allocations}) reached")
                return None

            # Check if client already has allocation
            if client_addr in self._client_to_allocation:
                logger.warning(f"Client {client_addr} already has allocation")
                return None

            # Allocate port
            port = await self.port_pool.acquire()
            if port is None:
                logger.warning("No available ports for allocation")
                return None

            # Create allocation
            allocation_id = str(uuid.uuid4())
            lifetime = lifetime or self.default_lifetime

            allocation = TurnAllocation(
                allocation_id=allocation_id,
                client_addr=client_addr,
                relay_addr=(relay_addr[0], port),
                lifetime=lifetime,
                transport=transport,
            )

            # Store allocation
            self._allocations[allocation_id] = allocation
            self._client_to_allocation[client_addr] = allocation_id
            self._relay_to_allocation[allocation.relay_addr] = allocation_id

            logger.info(
                f"Created allocation {allocation_id} for {client_addr} -> {allocation.relay_addr}"
            )

            return allocation

    async def get_allocation(self, allocation_id: str) -> Optional[TurnAllocation]:
        """
        Get allocation by ID.

        Args:
            allocation_id: Allocation ID

        Returns:
            TurnAllocation or None
        """
        return self._allocations.get(allocation_id)

    async def get_allocation_by_client(self, client_addr: Tuple[str, int]) -> Optional[TurnAllocation]:
        """
        Get allocation by client address.

        Args:
            client_addr: Client's (ip, port)

        Returns:
            TurnAllocation or None
        """
        allocation_id = self._client_to_allocation.get(client_addr)
        if allocation_id:
            return self._allocations.get(allocation_id)
        return None

    async def get_allocation_by_relay(self, relay_addr: Tuple[str, int]) -> Optional[TurnAllocation]:
        """
        Get allocation by relay address.

        Args:
            relay_addr: Relay's (ip, port)

        Returns:
            TurnAllocation or None
        """
        allocation_id = self._relay_to_allocation.get(relay_addr)
        if allocation_id:
            return self._allocations.get(allocation_id)
        return None

    async def refresh_allocation(
        self, allocation_id: str, lifetime: Optional[int] = None
    ) -> Optional[TurnAllocation]:
        """
        Refresh an allocation's lifetime.

        Args:
            allocation_id: Allocation ID
            lifetime: New lifetime (uses default if None)

        Returns:
            Updated TurnAllocation or None
        """
        async with self._lock:
            allocation = self._allocations.get(allocation_id)
            if not allocation:
                return None

            # Update lifetime (extends from now)
            allocation.lifetime = lifetime or self.default_lifetime
            allocation.created_at = time.time()

            logger.debug(f"Refreshed allocation {allocation_id}")
            return allocation

    async def delete_allocation(self, allocation_id: str) -> bool:
        """
        Delete an allocation.

        Args:
            allocation_id: Allocation ID

        Returns:
            True if allocation was deleted
        """
        async with self._lock:
            allocation = self._allocations.get(allocation_id)
            if not allocation:
                return False

            # Release port
            await self.port_pool.release(allocation.relay_addr[1])

            # Remove from indexes
            self._client_to_allocation.pop(allocation.client_addr, None)
            self._relay_to_allocation.pop(allocation.relay_addr, None)
            self._allocations.pop(allocation_id, None)

            logger.info(f"Deleted allocation {allocation_id}")
            return True

    async def add_permission(
        self, allocation_id: str, peer_addr: Tuple[str, int]
    ) -> bool:
        """
        Add permission for a peer.

        Args:
            allocation_id: Allocation ID
            peer_addr: Peer's (ip, port)

        Returns:
            True if permission was added
        """
        allocation = self._allocations.get(allocation_id)
        if not allocation:
            return False

        return allocation.add_permission(peer_addr)

    async def cleanup_expired(self) -> int:
        """
        Remove all expired allocations.

        Returns:
            Number of allocations removed
        """
        expired_ids = []

        async with self._lock:
            for allocation_id, allocation in self._allocations.items():
                if allocation.is_expired():
                    expired_ids.append(allocation_id)

        for allocation_id in expired_ids:
            await self.delete_allocation(allocation_id)

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired allocations")

        return len(expired_ids)

    def get_stats(self) -> dict:
        """
        Get allocation manager statistics.

        Returns:
            Statistics dictionary
        """
        active_allocations = [a for a in self._allocations.values() if not a.is_expired()]

        total_bytes_sent = sum(a.bytes_sent for a in active_allocations)
        total_bytes_received = sum(a.bytes_received for a in active_allocations)

        return {
            "total_allocations": len(self._allocations),
            "active_allocations": len(active_allocations),
            "max_allocations": self.max_allocations,
            "port_pool_available": self.port_pool.available_count(),
            "port_pool_usage": f"{self.port_pool.usage_percentage():.1f}%",
            "total_bytes_sent": total_bytes_sent,
            "total_bytes_received": total_bytes_received,
        }
