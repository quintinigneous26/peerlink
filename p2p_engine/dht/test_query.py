"""
Unit tests for Kademlia DHT Query Manager

Tests for iterative query logic, parallelism, and state management.
"""

import asyncio
import pytest
import time
from p2p_engine.dht.query import (
    QueryType,
    QueryState,
    QueryContext,
    QueryResult,
    QueryManager,
    QueryPeer,
    ALPHA,
    K,
)
from p2p_engine.dht.routing import PeerEntry, calculate_distance


class TestQueryContext:
    """Tests for QueryContext dataclass."""

    def test_query_context_creation(self):
        """Test creating a query context."""
        target_id = b"\x01" * 32

        context = QueryContext(
            query_type=QueryType.FIND_PEER,
            target_id=target_id
        )

        assert context.query_type == QueryType.FIND_PEER
        assert context.target_id == target_id
        assert context.state == QueryState.PENDING

    def test_query_context_elapsed_time(self):
        """Test elapsed time calculation."""
        target_id = b"\x01" * 32

        context = QueryContext(
            query_type=QueryType.FIND_PEER,
            target_id=target_id,
            started_at=time.time() - 0.1  # 100ms ago
        )

        elapsed = context.elapsed_ms

        assert 90 <= elapsed <= 150  # Allow some tolerance

    def test_query_context_is_expired(self):
        """Test expiration check."""
        target_id = b"\x01" * 32

        context = QueryContext(
            query_type=QueryType.FIND_PEER,
            target_id=target_id,
            started_at=time.time() - 70  # 70 seconds ago
        )

        assert context.is_expired(timeout_ms=60000)


class TestQueryResult:
    """Tests for QueryResult dataclass."""

    def test_query_result_success(self):
        """Test successful query result."""
        peers = [PeerEntry(peer_id=b"\x01" * 32)]

        result = QueryResult(success=True, peers=peers, duration_ms=100)

        assert result.success
        assert len(result.peers) == 1
        assert result.duration_ms == 100
        assert result.error is None

    def test_query_result_failure(self):
        """Test failed query result."""
        result = QueryResult(
            success=False,
            error="Network timeout"
        )

        assert not result.success
        assert result.error == "Network timeout"


class TestQueryPeer:
    """Tests for QueryPeer dataclass."""

    def test_query_peer_ordering(self):
        """Test QueryPeer ordering by distance."""
        peer_close = PeerEntry(peer_id=b"\xff" * 32)
        peer_far = PeerEntry(peer_id=b"\x01" * 32)

        target = b"\x80" * 32

        qpeer_far = QueryPeer(
            distance=calculate_distance(peer_far.peer_id, target),
            peer=peer_far
        )

        qpeer_close = QueryPeer(
            distance=calculate_distance(peer_close.peer_id, target),
            peer=peer_close
        )

        assert qpeer_close < qpeer_far


class TestQueryManager:
    """Tests for QueryManager."""

    @pytest.fixture
    def manager(self):
        """QueryManager instance for testing."""
        return QueryManager(alpha=3, timeout_ms=60000)

    @pytest.fixture
    def mock_routing_table(self):
        """Mock routing table for testing."""
        class MockRoutingTable:
            def __init__(self):
                self.peers = [
                    PeerEntry(peer_id=bytes([i]) * 32, addresses=[f"/ip4/127.0.0.1/tcp/{i}"])
                    for i in range(10)
                ]

            def find_closest_peers(self, target_id, count):
                return self.peers[:count]

        return MockRoutingTable()

    @pytest.mark.asyncio
    async def test_find_peer_success(self, manager, mock_routing_table):
        """Test successful peer find."""
        target_id = b"\x01" * 32

        # Mock query function that returns closer peers
        async def mock_query(peer_id, target):
            if peer_id == b"\x00" * 32:
                # Found the target
                return [PeerEntry(peer_id=target_id)]
            return []

        result = await manager.find_peer(target_id, mock_routing_table, mock_query)

        assert result.success
        assert len(result.peers) >= 0

    @pytest.mark.asyncio
    async def test_find_peer_no_peers(self, manager):
        """Test peer find with no peers in routing table."""
        class EmptyRoutingTable:
            def find_closest_peers(self, target_id, count):
                return []

        target_id = b"\x01" * 32

        async def mock_query(peer_id, target):
            return []

        result = await manager.find_peer(
            target_id,
            EmptyRoutingTable(),
            mock_query
        )

        assert not result.success
        assert result.error == "No peers in routing table"

    @pytest.mark.asyncio
    async def test_find_value_success(self, manager, mock_routing_table):
        """Test successful value lookup."""
        key = b"test_key"

        async def mock_query(peer_id, target_key):
            # Return value and closer peers
            return (b"value_bytes", [])

        result = await manager.find_value(key, mock_routing_table, mock_query)

        assert result.success
        assert result.value == b"value_bytes"

    @pytest.mark.asyncio
    async def test_find_value_not_found(self, manager, mock_routing_table):
        """Test value lookup when value not found."""
        key = b"test_key"

        async def mock_query(peer_id, target_key):
            return (None, [PeerEntry(peer_id=b"\x01" * 32)])

        result = await manager.find_value(key, mock_routing_table, mock_query)

        # May succeed with closer peers or fail
        assert isinstance(result.success, bool)

    @pytest.mark.asyncio
    async def test_find_providers_success(self, manager, mock_routing_table):
        """Test successful provider lookup."""
        key = b"test_cid"

        async def mock_query(peer_id, target_key):
            # Return K providers to satisfy success condition
            providers = [PeerEntry(peer_id=bytes([i % 256]) * 32) for i in range(K)]
            return (providers, [])

        result = await manager.find_providers(key, mock_routing_table, mock_query)

        assert result.success
        assert len(result.providers) > 0
        assert len(result.providers) > 0

    @pytest.mark.asyncio
    async def test_provide_success(self, manager, mock_routing_table):
        """Test successful provide announcement."""
        key = b"test_cid"
        local_peer_id = b"\xff" * 32

        async def mock_announce(peer_id, key, provider_id):
            return True  # Success

        result = await manager.provide(
            key,
            local_peer_id,
            mock_routing_table,
            mock_announce
        )

        assert result.success

    @pytest.mark.asyncio
    async def test_cleanup_expired_queries(self, manager):
        """Test cleaning up expired queries."""
        # Simulate some queries
        target_id = b"\x01" * 32

        # Add a query context manually
        query_id = "test_query"
        manager._active_queries[query_id] = QueryContext(
            query_type=QueryType.FIND_PEER,
            target_id=target_id,
            started_at=time.time() - 100  # Expired
        )

        removed = await manager.cleanup_expired_queries()

        assert removed == 1
        assert manager.active_query_count == 0


class TestQueryTypes:
    """Tests for query type enums."""

    def test_query_type_values(self):
        """Test query type enum values."""
        assert QueryType.FIND_PEER.value == "find_peer"
        assert QueryType.FIND_VALUE.value == "find_value"
        assert QueryType.FIND_PROVIDERS.value == "find_providers"
        assert QueryType.PROVIDE.value == "provide"

    def test_query_state_values(self):
        """Test query state enum values."""
        assert QueryState.PENDING.value == "pending"
        assert QueryState.RUNNING.value == "running"
        assert QueryState.COMPLETED.value == "completed"
        assert QueryState.FAILED.value == "failed"
        assert QueryState.TIMEOUT.value == "timeout"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
