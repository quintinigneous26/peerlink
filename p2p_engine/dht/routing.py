"""
Kademlia Routing Table (k-bucket) Implementation

Implements the k-bucket routing table structure for Kademlia DHT.
Uses XOR distance metric for peer discovery and routing.

Reference:
- Kademlia paper: https://pdos.csail.mit.edu/~petar/papers/maymounkov-kademlia-lncs.pdf
- libp2p DHT: https://github.com/libp2p/specs/tree/master/kad-dht
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Tuple
from enum import Enum
import struct

logger = logging.getLogger(__name__)

# Constants
ALPHA = 3  # Concurrency parameter for parallel queries
K = 20  # Bucket size
BIT_COUNT = 256  # SHA-256 hash size in bits
BYTE_COUNT = BIT_COUNT // 8  # 32 bytes for SHA-256


class PeerState(Enum):
    """Peer connection state."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


@dataclass
class PeerEntry:
    """
    Represents a peer entry in the routing table.

    Attributes:
        peer_id: Peer identifier (32 bytes)
        addresses: List of multiaddresses where peer can be reached
        last_seen: Timestamp of last successful interaction
        state: Connection state
        latency_ms: Last measured latency in milliseconds
    """
    peer_id: bytes
    addresses: List[str] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)
    state: PeerState = PeerState.CONNECTED
    latency_ms: float = 0.0

    def is_stale(self, stale_threshold: float = 3600.0) -> bool:
        """Check if peer entry is stale (not seen recently)."""
        return time.time() - self.last_seen > stale_threshold

    def update_seen(self) -> None:
        """Update last_seen timestamp to current time."""
        self.last_seen = time.time()


def calculate_peer_id(public_key: bytes) -> bytes:
    """
    Calculate peer ID from public key using SHA-256.

    Args:
        public_key: Peer's public key bytes

    Returns:
        32-byte peer ID
    """
    return hashlib.sha256(public_key).digest()


def calculate_distance(id1: bytes, id2: bytes) -> int:
    """
    Calculate XOR distance between two peer IDs.

    The XOR distance is defined as the integer value of the XOR of two IDs.
    Lower distance means closer in the DHT.

    Args:
        id1: First peer ID (32 bytes)
        id2: Second peer ID (32 bytes)

    Returns:
        Integer distance value

    Raises:
        ValueError: If IDs are not 32 bytes
    """
    if len(id1) != BYTE_COUNT or len(id2) != BYTE_COUNT:
        raise ValueError(f"Peer IDs must be {BYTE_COUNT} bytes")

    # XOR the IDs and convert to integer
    xor_result = bytes(a ^ b for a, b in zip(id1, id2))
    return int.from_bytes(xor_result, byteorder='big')


def common_prefix_length(id1: bytes, id2: bytes) -> int:
    """
    Calculate the number of leading bits that are identical.

    Used to determine which k-bucket a peer belongs to.

    Args:
        id1: First peer ID (32 bytes)
        id2: Second peer ID (32 bytes)

    Returns:
        Number of leading identical bits (0-256)
    """
    xor_bytes = bytes(a ^ b for a, b in zip(id1, id2))

    # Count leading zero bits
    for i, byte in enumerate(xor_bytes):
        if byte != 0:
            # Find first set bit in this byte
            # Count leading zeros in the byte
            leading_zeros = 0
            for bit in range(7, -1, -1):
                if byte & (1 << bit):
                    break
                leading_zeros += 1
            return i * 8 + leading_zeros

    return BIT_COUNT  # IDs are identical


class KBucket:
    """
    A k-bucket holds up to K peers.

    KBuckets are arranged in a binary tree structure where each bucket
    covers a range of the ID space. Peers are placed in buckets based on
    their common prefix length with the local node.
    """

    def __init__(self, prefix_len: int, max_size: int = K):
        """
        Initialize a k-bucket.

        Args:
            prefix_len: The prefix length this bucket covers
            max_size: Maximum number of peers in bucket (default K=20)
        """
        self.prefix_len = prefix_len
        self.max_size = max_size
        self._peers: Dict[bytes, PeerEntry] = {}
        self._replacement_cache: List[PeerEntry] = []
        self._last_refresh: float = time.time()

    @property
    def peers(self) -> List[PeerEntry]:
        """Get list of peers in the bucket."""
        return list(self._peers.values())

    @property
    def size(self) -> int:
        """Get current bucket size."""
        return len(self._peers)

    @property
    def is_full(self) -> bool:
        """Check if bucket is full."""
        return self.size >= self.max_size

    def add_peer(self, peer: PeerEntry) -> bool:
        """
        Add a peer to the bucket.

        If bucket is full, peer is added to replacement cache.
        If peer already exists, it's moved to the end (LRU).

        Args:
            peer: Peer entry to add

        Returns:
            True if peer was added, False if cached
        """
        peer_id = peer.peer_id

        if peer_id in self._peers:
            # Peer exists, update and move to end (LRU)
            self._peers[peer_id].update_seen()
            self._peers[peer_id].addresses = peer.addresses
            self._peers[peer_id].state = peer.state
            return True

        if self.is_full:
            # Add to replacement cache
            if len(self._replacement_cache) < self.max_size:
                self._replacement_cache.append(peer)
            return False

        # Add new peer
        self._peers[peer_id] = peer
        return True

    def remove_peer(self, peer_id: bytes) -> bool:
        """
        Remove a peer from the bucket.

        If replacement cache has entries, the most recent is promoted.

        Args:
            peer_id: ID of peer to remove

        Returns:
            True if peer was removed
        """
        if peer_id not in self._peers:
            return False

        del self._peers[peer_id]

        # Promote from replacement cache
        if self._replacement_cache:
            replacement = self._replacement_cache.pop(0)
            self._peers[replacement.peer_id] = replacement

        return True

    def get_peer(self, peer_id: bytes) -> Optional[PeerEntry]:
        """Get peer by ID."""
        return self._peers.get(peer_id)

    def has_peer(self, peer_id: bytes) -> bool:
        """Check if peer exists in bucket."""
        return peer_id in self._peers

    def split(self, local_id: bytes) -> Tuple['KBucket', 'KBucket']:
        """
        Split the bucket into two new buckets.

        Used when a bucket is full and needs to be split to maintain
        the k-bucket tree structure.

        Args:
            local_id: Local peer's ID for determining split direction

        Returns:
            Tuple of (left_bucket, right_bucket)
        """
        new_prefix_len = self.prefix_len + 1
        left = KBucket(new_prefix_len, self.max_size)
        right = KBucket(new_prefix_len, self.max_size)

        # Determine the split bit position
        byte_index = (new_prefix_len - 1) // 8
        bit_mask = 1 << (7 - (new_prefix_len - 1) % 8)

        for peer in self.peers:
            if peer.peer_id[byte_index] & bit_mask:
                right.add_peer(peer)
            else:
                left.add_peer(peer)

        return left, right

    def get_furthest_peers(
        self,
        target_id: bytes,
        count: int = ALPHA
    ) -> List[PeerEntry]:
        """
        Get peers furthest from target ID.

        Used for iterative queries to find close nodes.

        Args:
            target_id: Target peer ID
            count: Maximum number of peers to return

        Returns:
            List of peers sorted by distance (furthest first)
        """
        peers_with_dist = [
            (calculate_distance(peer.peer_id, target_id), peer)
            for peer in self.peers
        ]
        peers_with_dist.sort(key=lambda x: x[0], reverse=True)
        return [peer for _, peer in peers_with_dist[:count]]

    def get_closest_peers(
        self,
        target_id: bytes,
        count: int = K
    ) -> List[PeerEntry]:
        """
        Get peers closest to target ID.

        Args:
            target_id: Target peer ID
            count: Maximum number of peers to return

        Returns:
            List of peers sorted by distance (closest first)
        """
        peers_with_dist = [
            (calculate_distance(peer.peer_id, target_id), peer)
            for peer in self.peers
        ]
        peers_with_dist.sort(key=lambda x: x[0])
        return [peer for _, peer in peers_with_dist[:count]]

    def cleanup_stale(self, stale_threshold: float = 3600.0) -> int:
        """
        Remove stale peers from bucket.

        Args:
            stale_threshold: Seconds after which peer is considered stale

        Returns:
            Number of peers removed
        """
        to_remove = [
            peer_id for peer_id, peer in self._peers.items()
            if peer.is_stale(stale_threshold)
        ]

        for peer_id in to_remove:
            self.remove_peer(peer_id)

        return len(to_remove)


class RoutingTable:
    """
    Kademlia routing table with k-bucket tree structure.

    Maintains peers in a binary tree of k-buckets based on XOR distance.
    Each bucket covers a range of the ID space.
    """

    def __init__(self, local_id: bytes, k_size: int = K):
        """
        Initialize routing table.

        Args:
            local_id: Local peer's ID (32 bytes)
            k_size: Bucket size parameter (default 20)
        """
        if len(local_id) != BYTE_COUNT:
            raise ValueError(f"Peer ID must be {BYTE_COUNT} bytes")

        self.local_id = local_id
        self.k_size = k_size
        self._buckets: List[KBucket] = [KBucket(0, k_size)]
        self._lock = asyncio.Lock()

    async def add_peer(self, peer: PeerEntry) -> bool:
        """
        Add a peer to the routing table.

        Args:
            peer: Peer entry to add

        Returns:
            True if peer was added successfully
        """
        async with self._lock:
            # Find appropriate bucket
            bucket = self._find_bucket(peer.peer_id)

            if not bucket.is_full or bucket.has_peer(peer.peer_id):
                return bucket.add_peer(peer)

            # Split full bucket
            if bucket.prefix_len < BIT_COUNT - 1:
                left, right = bucket.split(self.local_id)
                idx = self._buckets.index(bucket)
                self._buckets.pop(idx)
                self._buckets.insert(idx, left)
                self._buckets.insert(idx + 1, right)

                # Retry add with new buckets
                new_bucket = self._find_bucket(peer.peer_id)
                return new_bucket.add_peer(peer)

            # Use replacement cache
            return bucket.add_peer(peer)

    async def remove_peer(self, peer_id: bytes) -> bool:
        """
        Remove a peer from routing table.

        Args:
            peer_id: ID of peer to remove

        Returns:
            True if peer was found and removed
        """
        async with self._lock:
            bucket = self._find_bucket(peer_id)
            return bucket.remove_peer(peer_id)

    def find_peer(self, peer_id: bytes) -> Optional[PeerEntry]:
        """
        Find a peer by ID.

        Args:
            peer_id: ID to search for

        Returns:
            Peer entry if found, None otherwise
        """
        bucket = self._find_bucket(peer_id)
        return bucket.get_peer(peer_id)

    def find_closest_peers(
        self,
        target_id: bytes,
        count: int = K
    ) -> List[PeerEntry]:
        """
        Find peers closest to target ID.

        This is the core lookup operation for Kademlia.

        Args:
            target_id: Target ID to find close peers for
            count: Maximum number of peers to return

        Returns:
            List of closest peers sorted by distance
        """
        all_peers: List[PeerEntry] = []

        for bucket in self._buckets:
            all_peers.extend(bucket.peers)

        # Sort by distance and return closest
        peers_with_dist = [
            (calculate_distance(peer.peer_id, target_id), peer)
            for peer in all_peers
        ]
        peers_with_dist.sort(key=lambda x: x[0])

        return [peer for _, peer in peers_with_dist[:count]]

    def _find_bucket(self, peer_id: bytes) -> KBucket:
        """Find the bucket containing a given peer ID."""
        prefix_len = common_prefix_length(self.local_id, peer_id)

        for bucket in self._buckets:
            if bucket.prefix_len == prefix_len:
                return bucket

        # If bucket doesn't exist yet, find closest
        closest = self._buckets[0]
        for bucket in self._buckets:
            if abs(bucket.prefix_len - prefix_len) < abs(closest.prefix_len - prefix_len):
                closest = bucket

        return closest

    @property
    def peer_count(self) -> int:
        """Get total number of peers in routing table."""
        return sum(bucket.size for bucket in self._buckets)

    @property
    def buckets(self) -> List[KBucket]:
        """Get all buckets."""
        return self._buckets.copy()

    async def cleanup_stale(self, stale_threshold: float = 3600.0) -> int:
        """
        Remove stale peers from all buckets.

        Args:
            stale_threshold: Seconds after which peer is considered stale

        Returns:
            Total number of peers removed
        """
        async with self._lock:
            total = 0
            for bucket in self._buckets:
                total += bucket.cleanup_stale(stale_threshold)
            return total

    def get_random_peers(self, count: int = 1) -> List[PeerEntry]:
        """
        Get random peers from routing table.

        Useful for bootstrapping and periodic refresh.

        Args:
            count: Number of random peers to return

        Returns:
            List of random peers
        """
        import random

        all_peers: List[PeerEntry] = []
        for bucket in self._buckets:
            all_peers.extend(bucket.peers)

        if len(all_peers) <= count:
            return all_peers

        return random.sample(all_peers, count)
