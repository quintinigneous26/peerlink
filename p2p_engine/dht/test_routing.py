"""
Unit tests for Kademlia DHT Routing Table

Tests for k-bucket implementation, XOR distance calculation,
and routing table operations.
"""

import asyncio
import pytest
import time
from p2p_engine.dht.routing import (
    PeerEntry,
    PeerState,
    KBucket,
    RoutingTable,
    calculate_distance,
    calculate_peer_id,
    common_prefix_length,
    K,
    BYTE_COUNT,
)


class TestPeerEntry:
    """Tests for PeerEntry dataclass."""

    def test_peer_entry_creation(self):
        """Test creating a peer entry."""
        peer_id = b"\x01" * 32
        addresses = ["/ip4/127.0.0.1/tcp/1234"]

        entry = PeerEntry(peer_id=peer_id, addresses=addresses)

        assert entry.peer_id == peer_id
        assert entry.addresses == addresses
        assert entry.state == PeerState.CONNECTED
        assert entry.latency_ms == 0.0
        assert not entry.is_stale()

    def test_peer_entry_stale(self):
        """Test peer entry staleness detection."""
        peer_id = b"\x01" * 32
        entry = PeerEntry(peer_id=peer_id)

        # Fresh entry is not stale
        assert not entry.is_stale()

        # Entry with old timestamp is stale
        entry.last_seen = time.time() - 4000
        assert entry.is_stale()

    def test_peer_entry_update_seen(self):
        """Test updating last_seen timestamp."""
        peer_id = b"\x01" * 32
        entry = PeerEntry(peer_id=peer_id, last_seen=time.time() - 100)

        old_last_seen = entry.last_seen
        entry.update_seen()

        assert entry.last_seen > old_last_seen
        assert not entry.is_stale()


class TestDistanceCalculation:
    """Tests for XOR distance calculation."""

    def test_calculate_distance_same(self):
        """Test distance between identical IDs is zero."""
        id1 = b"\x01" * 32
        id2 = b"\x01" * 32

        distance = calculate_distance(id1, id2)
        assert distance == 0

    def test_calculate_distance_different(self):
        """Test distance between different IDs."""
        id1 = b"\x00" * 32
        id2 = b"\xff" * 32

        distance = calculate_distance(id1, id2)
        assert distance == 2**256 - 1

    def test_calculate_distance_invalid_length(self):
        """Test distance calculation with invalid ID length."""
        id1 = b"\x01" * 16
        id2 = b"\x02" * 32

        with pytest.raises(ValueError):
            calculate_distance(id1, id2)

    def test_common_prefix_length(self):
        """Test common prefix length calculation."""
        id1 = bytes.fromhex("00" * 16 + "ff" * 16)
        id2 = bytes.fromhex("00" * 16 + "aa" * 16)

        # First 16 bytes are identical (128 bits)
        cpl = common_prefix_length(id1, id2)
        assert cpl == 129

    def test_common_prefix_length_identical(self):
        """Test common prefix of identical IDs."""
        id1 = b"\xab" * 32
        id2 = b"\xab" * 32

        cpl = common_prefix_length(id1, id2)
        assert cpl == 256

    def test_common_prefix_length_different(self):
        """Test common prefix of completely different IDs."""
        id1 = b"\x00" * 32
        id2 = b"\xff" * 32

        cpl = common_prefix_length(id1, id2)
        assert cpl == 0


class TestKBucket:
    """Tests for k-bucket implementation."""

    def test_kbucket_creation(self):
        """Test creating a k-bucket."""
        bucket = KBucket(prefix_len=0, max_size=20)

        assert bucket.prefix_len == 0
        assert bucket.max_size == 20
        assert bucket.size == 0
        assert not bucket.is_full

    def test_kbucket_add_peer(self):
        """Test adding peers to bucket."""
        bucket = KBucket(prefix_len=0, max_size=3)

        peer1 = PeerEntry(peer_id=b"\x01" * 32)
        peer2 = PeerEntry(peer_id=b"\x02" * 32)

        assert bucket.add_peer(peer1)
        assert bucket.add_peer(peer2)
        assert bucket.size == 2

    def test_kbucket_add_duplicate_peer(self):
        """Test adding duplicate peer updates entry."""
        bucket = KBucket(prefix_len=0, max_size=3)

        peer1 = PeerEntry(peer_id=b"\x01" * 32, addresses=["/ip4/1.1.1.1/tcp/1"])
        peer2 = PeerEntry(peer_id=b"\x01" * 32, addresses=["/ip4/2.2.2.2/tcp/2"])

        bucket.add_peer(peer1)
        bucket.add_peer(peer2)

        # Should still have 1 peer
        assert bucket.size == 1

        # Address should be updated
        retrieved = bucket.get_peer(b"\x01" * 32)
        assert retrieved.addresses == ["/ip4/2.2.2.2/tcp/2"]

    def test_kbucket_full(self):
        """Test bucket full behavior."""
        bucket = KBucket(prefix_len=0, max_size=2)

        peer1 = PeerEntry(peer_id=b"\x01" * 32)
        peer2 = PeerEntry(peer_id=b"\x02" * 32)
        peer3 = PeerEntry(peer_id=b"\x03" * 32)

        bucket.add_peer(peer1)
        bucket.add_peer(peer2)

        assert bucket.is_full
        assert not bucket.add_peer(peer3)  # Should go to cache
        assert bucket.size == 2

    def test_kbucket_remove_peer(self):
        """Test removing peer from bucket."""
        bucket = KBucket(prefix_len=0, max_size=3)

        peer1 = PeerEntry(peer_id=b"\x01" * 32)
        bucket.add_peer(peer1)

        assert bucket.remove_peer(b"\x01" * 32)
        assert bucket.size == 0
        assert not bucket.remove_peer(b"\x01" * 32)  # Already removed

    def test_kbucket_split(self):
        """Test splitting a bucket."""
        local_id = b"\x80" + b"\x00" * 31  # Starts with 0x80
        bucket = KBucket(prefix_len=0, max_size=20)

        # Add peers with different first bits
        peer1 = PeerEntry(peer_id=b"\x00" * 32)  # First bit 0
        peer2 = PeerEntry(peer_id=b"\xff" * 32)  # First bit 1

        bucket.add_peer(peer1)
        bucket.add_peer(peer2)

        left, right = bucket.split(local_id)

        # Check peers were distributed
        assert peer1.peer_id in [p.peer_id for p in left.peers]
        assert peer2.peer_id in [p.peer_id for p in right.peers]

    def test_kbucket_get_closest_peers(self):
        """Test getting closest peers."""
        target = b"\x80" * 32
        bucket = KBucket(prefix_len=0, max_size=20)

        peer_close = PeerEntry(peer_id=b"\x81" * 32)
        peer_far = PeerEntry(peer_id=b"\x00" * 32)

        bucket.add_peer(peer_close)
        bucket.add_peer(peer_far)

        closest = bucket.get_closest_peers(target, count=1)

        assert len(closest) == 1
        assert closest[0].peer_id == peer_close.peer_id

    def test_kbucket_cleanup_stale(self):
        """Test cleaning up stale peers."""
        bucket = KBucket(prefix_len=0, max_size=5)

        fresh_peer = PeerEntry(peer_id=b"\x01" * 32)
        stale_peer = PeerEntry(peer_id=b"\x02" * 32, last_seen=time.time() - 5000)

        bucket.add_peer(fresh_peer)
        bucket.add_peer(stale_peer)

        removed = bucket.cleanup_stale(stale_threshold=3600)

        assert removed == 1
        assert bucket.size == 1
        assert bucket.get_peer(b"\x01" * 32) is not None


class TestRoutingTable:
    """Tests for routing table implementation."""

    @pytest.fixture
    def local_id(self):
        """Local peer ID for testing."""
        return b"\x80" + b"\x00" * 31

    @pytest.fixture
    def routing_table(self, local_id):
        """Routing table instance for testing."""
        return RoutingTable(local_id=local_id, k_size=20)

    def test_routing_table_creation(self, routing_table, local_id):
        """Test creating routing table."""
        assert routing_table.local_id == local_id
        assert routing_table.k_size == 20
        assert routing_table.peer_count == 0

    def test_routing_table_add_peer(self, routing_table):
        """Test adding peer to routing table."""
        peer = PeerEntry(peer_id=b"\x01" * 32)

        asyncio.run(routing_table.add_peer(peer))

        assert routing_table.peer_count == 1

    def test_routing_table_remove_peer(self, routing_table):
        """Test removing peer from routing table."""
        peer = PeerEntry(peer_id=b"\x01" * 32)

        asyncio.run(routing_table.add_peer(peer))
        asyncio.run(routing_table.remove_peer(b"\x01" * 32))

        assert routing_table.peer_count == 0

    def test_routing_table_find_peer(self, routing_table):
        """Test finding peer in routing table."""
        peer = PeerEntry(peer_id=b"\x01" * 32)

        asyncio.run(routing_table.add_peer(peer))

        found = routing_table.find_peer(b"\x01" * 32)
        assert found is not None
        assert found.peer_id == b"\x01" * 32

    def test_routing_table_find_closest_peers(self, routing_table, local_id):
        """Test finding closest peers."""
        peer_close = PeerEntry(peer_id=b"\x81" * 32)
        peer_far = PeerEntry(peer_id=b"\x00" * 32)

        asyncio.run(routing_table.add_peer(peer_close))
        asyncio.run(routing_table.add_peer(peer_far))

        target = b"\x80" * 32
        closest = routing_table.find_closest_peers(target, count=1)

        assert len(closest) == 1
        assert closest[0].peer_id == peer_close.peer_id

    def test_routing_table_cleanup_stale(self, routing_table):
        """Test cleaning up stale peers."""
        fresh_peer = PeerEntry(peer_id=b"\x01" * 32)
        stale_peer = PeerEntry(peer_id=b"\x02" * 32, last_seen=time.time() - 5000)

        asyncio.run(routing_table.add_peer(fresh_peer))
        asyncio.run(routing_table.add_peer(stale_peer))

        removed = asyncio.run(routing_table.cleanup_stale(stale_threshold=3600))

        assert removed == 1
        assert routing_table.peer_count == 1


class TestPeerIDCalculation:
    """Tests for peer ID calculation."""

    def test_calculate_peer_id_from_key(self):
        """Test calculating peer ID from public key."""
        public_key = b"test_public_key_bytes"

        peer_id = calculate_peer_id(public_key)

        assert len(peer_id) == BYTE_COUNT
        assert isinstance(peer_id, bytes)

    def test_peer_id_deterministic(self):
        """Test peer ID calculation is deterministic."""
        public_key = b"test_public_key_bytes"

        id1 = calculate_peer_id(public_key)
        id2 = calculate_peer_id(public_key)

        assert id1 == id2

    def test_peer_id_unique(self):
        """Test different keys produce different IDs."""
        key1 = b"public_key_1"
        key2 = b"public_key_2"

        id1 = calculate_peer_id(key1)
        id2 = calculate_peer_id(key2)

        assert id1 != id2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
