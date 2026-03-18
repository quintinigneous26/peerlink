"""
Provider Manager for Content Routing

Tracks which peers provide which content (CID) in the DHT.
Implements provider records and announcements.

Reference: https://github.com/libp2p/specs/tree/master/kad-dht
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set
from collections import defaultdict
import struct

logger = logging.getLogger(__name__)

# Constants
PROVIDER_EXPIRATION = 3600.0  # Providers expire after 1 hour
MAX_PROVIDERS_PER_KEY = 20  # Maximum providers to track per key


@dataclass
class ProviderRecord:
    """
    Record of a peer providing a specific content key.

    Attributes:
        peer_id: ID of the provider peer
        key: Content key (CID hash)
        timestamp: When this record was created
        expires: When this record expires
    """
    peer_id: bytes
    key: bytes
    timestamp: float = field(default_factory=time.time)
    expires: float = field(default_factory=lambda: time.time() + PROVIDER_EXPIRATION)

    def is_expired(self) -> bool:
        """Check if provider record has expired."""
        return time.time() > self.expires

    def refresh(self, ttl: float = PROVIDER_EXPIRATION) -> None:
        """Refresh the provider record."""
        self.timestamp = time.time()
        self.expires = time.time() + ttl


def compute_key(key: bytes) -> bytes:
    """
    Compute the DHT key for content.

    Uses SHA-256 hash of the input key.

    Args:
        key: Input key (can be CID bytes or any content identifier)

    Returns:
        32-byte DHT key
    """
    return hashlib.sha256(key).digest()


class ProviderManager:
    """
    Manages provider records for content routing.

    Tracks which peers provide which content and handles
    provider announcements and lookups.
    """

    def __init__(self, max_providers: int = MAX_PROVIDERS_PER_KEY):
        """
        Initialize provider manager.

        Args:
            max_providers: Maximum providers to track per key
        """
        self.max_providers = max_providers
        self._providers: Dict[bytes, Set[bytes]] = defaultdict(set)  # key -> peer_ids
        self._records: Dict[tuple[bytes, bytes], ProviderRecord] = {}  # (key, peer_id) -> record
        self._lock = asyncio.Lock()
        self._local_providers: Set[bytes] = set()  # Keys we're providing

    async def add_provider(
        self,
        key: bytes,
        peer_id: bytes,
        ttl: float = PROVIDER_EXPIRATION
    ) -> bool:
        """
        Add a provider record.

        Args:
            key: Content key (CID)
            peer_id: ID of the provider peer
            ttl: Time to live for this record

        Returns:
            True if provider was added
        """
        dht_key = compute_key(key)
        record_key = (dht_key, peer_id)

        async with self._lock:
            # Check if key has too many providers
            if len(self._providers[dht_key]) >= self.max_providers:
                if peer_id not in self._providers[dht_key]:
                    # Replace oldest provider
                    oldest = None
                    oldest_time = float('inf')
                    for pid in self._providers[dht_key]:
                        rec = self._records.get((dht_key, pid))
                        if rec and rec.timestamp < oldest_time:
                            oldest_time = rec.timestamp
                            oldest = pid

                    if oldest:
                        self._providers[dht_key].remove(oldest)
                        del self._records[(dht_key, oldest)]

            # Add or update record
            if peer_id in self._providers[dht_key]:
                # Update existing record
                self._records[record_key].refresh(ttl)
            else:
                # Create new record
                self._providers[dht_key].add(peer_id)
                self._records[record_key] = ProviderRecord(
                    peer_id=peer_id,
                    key=dht_key,
                    expires=time.time() + ttl
                )

            return True

    async def remove_provider(self, key: bytes, peer_id: bytes) -> bool:
        """
        Remove a provider record.

        Args:
            key: Content key (CID)
            peer_id: ID of the provider peer

        Returns:
            True if provider was found and removed
        """
        dht_key = compute_key(key)
        record_key = (dht_key, peer_id)

        async with self._lock:
            if record_key in self._records:
                del self._records[record_key]
                self._providers[dht_key].discard(peer_id)

                # Clean up empty sets
                if not self._providers[dht_key]:
                    del self._providers[dht_key]

                return True

            return False

    def get_providers(self, key: bytes, max_count: int = 20) -> List[ProviderRecord]:
        """
        Get providers for a content key.

        Args:
            key: Content key (CID)
            max_count: Maximum number of providers to return

        Returns:
            List of provider records
        """
        dht_key = compute_key(key)

        # Get provider IDs for this key
        peer_ids = list(self._providers.get(dht_key, set()))

        # Build list of records
        records: List[ProviderRecord] = []
        for peer_id in peer_ids[:max_count]:
            record = self._records.get((dht_key, peer_id))
            if record and not record.is_expired():
                records.append(record)

        return records

    async def get_provider_peer_ids(self, key: bytes, max_count: int = 20) -> List[bytes]:
        """
        Get provider peer IDs for a content key.

        Args:
            key: Content key (CID)
            max_count: Maximum number of providers to return

        Returns:
            List of peer IDs
        """
        records = self.get_providers(key, max_count)
        return [r.peer_id for r in records]

    async def add_local_provider(self, key: bytes) -> None:
        """
        Add a local provider record (we provide this content).

        Args:
            key: Content key (CID)
        """
        self._local_providers.add(key)

    async def remove_local_provider(self, key: bytes) -> None:
        """
        Remove a local provider record.

        Args:
            key: Content key (CID)
        """
        self._local_providers.discard(key)

    def get_local_providers(self) -> List[bytes]:
        """
        Get all keys we're providing.

        Returns:
            List of content keys
        """
        return list(self._local_providers)

    def is_providing(self, key: bytes) -> bool:
        """
        Check if we're providing a specific key.

        Args:
            key: Content key (CID)

        Returns:
            True if we're providing this key
        """
        return key in self._local_providers

    async def cleanup_expired(self) -> int:
        """
        Remove expired provider records.

        Returns:
            Number of records removed
        """
        async with self._lock:
            now = time.time()
            to_remove: List[tuple[bytes, bytes]] = []

            for record_key, record in self._records.items():
                if record.expires < now:
                    to_remove.append(record_key)

            for dht_key, peer_id in to_remove:
                del self._records[(dht_key, peer_id)]
                self._providers[dht_key].discard(peer_id)

                # Clean up empty sets
                if not self._providers[dht_key]:
                    del self._providers[dht_key]

            return len(to_remove)

    @property
    def provider_count(self) -> int:
        """Get total number of provider records."""
        return len(self._records)

    @property
    def key_count(self) -> int:
        """Get number of keys with providers."""
        return len(self._providers)

    async def get_all_providers_for_keys(
        self,
        keys: List[bytes]
    ) -> Dict[bytes, List[bytes]]:
        """
        Get providers for multiple keys efficiently.

        Args:
            keys: List of content keys

        Returns:
            Dict mapping key to list of peer IDs
        """
        result: Dict[bytes, List[bytes]] = {}

        for key in keys:
            peer_ids = await self.get_provider_peer_ids(key)
            if peer_ids:
                result[key] = peer_ids

        return result


def create_provider_message(
    key: bytes,
    peer_id: bytes
) -> bytes:
    """
    Create a provider announcement message.

    Args:
        key: Content key being provided
        peer_id: ID of the provider peer

    Returns:
        Encoded message bytes
    """
    # Simple encoding: key_len (1 byte) + key + peer_id (32 bytes)
    key_len = len(key)
    if key_len > 255:
        raise ValueError("Key too long")

    return struct.pack('>B', key_len) + key + peer_id


def parse_provider_message(data: bytes) -> tuple[bytes, bytes]:
    """
    Parse a provider announcement message.

    Args:
        data: Encoded message bytes

    Returns:
        Tuple of (key, peer_id)

    Raises:
        ValueError: If message is invalid
    """
    if len(data) < 33:
        raise ValueError("Invalid provider message")

    key_len = data[0]
    key = data[1:1 + key_len]

    if len(data) < 1 + key_len + 32:
        raise ValueError("Invalid provider message")

    peer_id = data[1 + key_len:1 + key_len + 32]

    return key, peer_id
