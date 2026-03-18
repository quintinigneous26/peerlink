"""
Relay Server Allocation Manager Tests
"""

import asyncio
import pytest

from src.allocation import AllocationManager, PortPool, TurnAllocation


@pytest.mark.asyncio
class TestPortPool:
    """Test port pool management."""

    async def test_port_pool_acquire_release(self):
        """Test acquiring and releasing ports."""
        pool = PortPool(min_port=10000, max_port=10009)

        # Acquire a port
        port = await pool.acquire()
        assert port is not None
        assert 10000 <= port <= 10009

        # Pool should have one less port
        assert pool.available_count() == 9

        # Release the port
        released = await pool.release(port)
        assert released is True
        assert pool.available_count() == 10

    async def test_port_pool_exhaustion(self):
        """Test port pool exhaustion."""
        pool = PortPool(min_port=10000, max_port=10002)  # Only 3 ports

        # Acquire all ports
        ports = []
        for _ in range(3):
            port = await pool.acquire()
            assert port is not None
            ports.append(port)

        # Next acquire should fail
        port = await pool.acquire()
        assert port is None

        # Release one port
        await pool.release(ports[0])

        # Should be able to acquire again
        port = await pool.acquire()
        assert port is not None

    async def test_port_pool_usage_percentage(self):
        """Test port pool usage calculation."""
        pool = PortPool(min_port=10000, max_port=10009)  # 10 ports

        assert pool.usage_percentage() == 0.0

        await pool.acquire()
        assert pool.usage_percentage() == 10.0

        await pool.acquire()
        assert pool.usage_percentage() == 20.0


@pytest.mark.asyncio
class TestTurnAllocation:
    """Test TurnAllocation dataclass."""

    async def test_allocation_creation(self):
        """Test creating a turn allocation."""
        allocation = TurnAllocation(
            allocation_id="test-id",
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
            lifetime=600,
        )

        assert allocation.allocation_id == "test-id"
        assert allocation.client_addr == ("192.168.1.1", 12345)
        assert allocation.relay_addr == ("10.0.0.1", 50000)
        assert allocation.lifetime == 600
        assert allocation.bytes_sent == 0
        assert allocation.bytes_received == 0

    async def test_allocation_expiration(self):
        """Test allocation expiration."""
        allocation = TurnAllocation(
            allocation_id="test-id",
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
            lifetime=1,  # 1 second
        )

        assert not allocation.is_expired()

        await asyncio.sleep(1.1)

        assert allocation.is_expired()

    async def test_allocation_permissions(self):
        """Test permission management."""
        allocation = TurnAllocation(
            allocation_id="test-id",
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
        )

        # Add permission
        added = allocation.add_permission(("10.0.0.2", 60000))
        assert added is True

        # Check permission exists
        assert allocation.has_permission(("10.0.0.2", 60000)) is True
        assert allocation.has_permission(("10.0.0.3", 60000)) is False

        # Add duplicate permission
        added = allocation.add_permission(("10.0.0.2", 60000))
        assert added is False

    async def test_allocation_stats(self):
        """Test allocation statistics."""
        allocation = TurnAllocation(
            allocation_id="test-id",
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 50000),
            lifetime=600,
        )

        allocation.record_sent(1000)
        allocation.record_received(2000)

        stats = allocation.get_stats()
        assert stats["bytes_sent"] == 1000
        assert stats["bytes_received"] == 2000
        assert stats["allocation_id"] == "test-id"


@pytest.mark.asyncio
class TestAllocationManager:
    """Test allocation manager."""

    async def test_manager_start_stop(self):
        """Test starting and stopping manager."""
        manager = AllocationManager(min_port=10000, max_port=10009)

        await manager.start()
        assert manager._cleanup_task is not None

        await manager.stop()
        # Cleanup task should be cancelled

    async def test_create_allocation(self):
        """Test creating allocation."""
        manager = AllocationManager(min_port=10000, max_port=10009)

        allocation = await manager.create_allocation(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 0),  # Port assigned by manager
        )

        assert allocation is not None
        assert allocation.allocation_id is not None
        assert allocation.client_addr == ("192.168.1.1", 12345)
        assert 10000 <= allocation.relay_addr[1] <= 10009

    async def test_get_allocation_by_client(self):
        """Test getting allocation by client address."""
        manager = AllocationManager(min_port=10000, max_port=10009)

        allocation = await manager.create_allocation(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 0),
        )

        # Get by client address
        found = await manager.get_allocation_by_client(("192.168.1.1", 12345))
        assert found is not None
        assert found.allocation_id == allocation.allocation_id

        # Non-existent client
        found = await manager.get_allocation_by_client(("192.168.1.2", 12346))
        assert found is None

    async def test_refresh_allocation(self):
        """Test refreshing allocation."""
        manager = AllocationManager(min_port=10000, max_port=10009)

        allocation = await manager.create_allocation(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 0),
            lifetime=10,
        )

        # Wait a bit
        await asyncio.sleep(0.1)

        # Refresh with new lifetime
        refreshed = await manager.refresh_allocation(allocation.allocation_id, lifetime=100)

        assert refreshed is not None
        assert refreshed.get_remaining_time() > 90

    async def test_delete_allocation(self):
        """Test deleting allocation."""
        manager = AllocationManager(min_port=10000, max_port=10009)

        allocation = await manager.create_allocation(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 0),
        )

        allocation_id = allocation.allocation_id

        # Delete allocation
        deleted = await manager.delete_allocation(allocation_id)
        assert deleted is True

        # Should not exist anymore
        found = await manager.get_allocation(allocation_id)
        assert found is None

    async def test_cleanup_expired(self):
        """Test cleanup of expired allocations."""
        manager = AllocationManager(min_port=10000, max_port=10009)

        # Create allocation with short lifetime
        allocation = await manager.create_allocation(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 0),
            lifetime=1,
        )

        # Wait for expiration
        await asyncio.sleep(1.1)

        # Cleanup
        cleaned = await manager.cleanup_expired()
        assert cleaned == 1

        # Allocation should be gone
        found = await manager.get_allocation(allocation.allocation_id)
        assert found is None

    async def test_manager_stats(self):
        """Test manager statistics."""
        manager = AllocationManager(min_port=10000, max_port=10009)

        # Create some allocations
        await manager.create_allocation(
            client_addr=("192.168.1.1", 12345),
            relay_addr=("10.0.0.1", 0),
        )
        await manager.create_allocation(
            client_addr=("192.168.1.2", 12346),
            relay_addr=("10.0.0.1", 0),
        )

        stats = manager.get_stats()
        assert stats["total_allocations"] == 2
        assert stats["active_allocations"] == 2
        assert stats["port_pool_available"] == 8  # 10 - 2
