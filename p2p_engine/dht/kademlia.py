"""
Kademlia DHT Protocol Implementation

Implements the libp2p Kademlia DHT protocol (/ipfs/kad/1.0.0).

This module provides the main DHT interface and message handling
for peer discovery, content routing, and key-value operations.

Reference: https://github.com/libp2p/specs/tree/master/kad-dht
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Awaitable
from enum import Enum

from .routing import (
    RoutingTable,
    PeerEntry,
    calculate_peer_id,
    K,
    BYTE_COUNT,
)
from .provider import (
    ProviderManager,
    compute_key,
)
from .query import (
    QueryManager,
    QueryType,
    QueryState,
    QueryResult,
)

logger = logging.getLogger(__name__)

# Protocol ID
PROTOCOL_ID = "/ipfs/kad/1.0.0"

# Message types
class KademliaMessageType(Enum):
    """Kademlia DHT message types."""
    FIND_NODE = "FIND_NODE"
    FIND_VALUE = "FIND_VALUE"  # Also called GET_VALUE
    PUT_VALUE = "PUT_VALUE"
    ADD_PROVIDER = "ADD_PROVIDER"
    GET_PROVIDERS = "GET_PROVIDERS"
    PING = "PING"


@dataclass
class KademliaMessage:
    """
    Kademlia DHT message.

    Attributes:
        message_type: Type of message
        key: Target key (peer ID, content key, or CID)
        value: Value (for PUT_VALUE responses)
        providers: List of providers (for GET_PROVIDERS)
        peers: List of closer peers (for all responses)
        peer_id: Sender's peer ID
        record: Record-level data (optional)
    """
    message_type: KademliaMessageType
    key: Optional[bytes] = None
    value: Optional[bytes] = None
    providers: List[Dict[str, Any]] = field(default_factory=list)
    peers: List[Dict[str, bytes]] = field(default_factory=list)
    peer_id: Optional[bytes] = None
    record: Optional[Dict[str, Any]] = None
    cluster_level: int = 0  # For DHT crawling

    def to_dict(self) -> dict:
        """Convert message to dictionary for JSON encoding."""
        result = {
            "type": self.message_type.value,
            "clusterLevel": self.cluster_level,
        }

        if self.key is not None:
            result["key"] = self.key.hex()

        if self.value is not None:
            result["value"] = self.value.hex()

        if self.providers:
            # Convert peer IDs to hex encoding for JSON serialization
            result["providers"] = [
                {"id": p.get("id", b"").hex() if isinstance(p.get("id"), bytes) else p.get("id"),
                 "addrs": p.get("addrs", [])}
                for p in self.providers
            ]

        if self.peers:
            # Convert peer IDs to hex encoding for JSON serialization
            result["closerPeers"] = [
                {"id": p.get("id", b"").hex() if isinstance(p.get("id"), bytes) else p.get("id"),
                 "addrs": p.get("addrs", [])}
                for p in self.peers
            ]

        if self.peer_id is not None:
            result["peer_id"] = self.peer_id.hex()

        if self.record is not None:
            result["record"] = self.record

        return result

    def to_json(self) -> bytes:
        """Convert message to JSON bytes."""
        return json.dumps(self.to_dict()).encode("utf-8")

    @classmethod
    def from_dict(cls, data: dict) -> "KademliaMessage":
        """Create message from dictionary."""
        message_type = KademliaMessageType(data.get("type", "PING"))
        key_bytes = data.get("key")
        value_bytes = data.get("value")

        return cls(
            message_type=message_type,
            key=bytes.fromhex(key_bytes) if key_bytes else None,
            value=bytes.fromhex(value_bytes) if value_bytes else None,
            providers=data.get("providers", []),
            peers=data.get("closerPeers", []),
            peer_id=bytes.fromhex(data.get("peer_id", "")) if data.get("peer_id") else None,
            record=data.get("record"),
            cluster_level=data.get("clusterLevel", 0),
        )

    @classmethod
    def from_json(cls, data: bytes) -> "KademliaMessage":
        """Create message from JSON bytes."""
        return cls.from_dict(json.loads(data.decode("utf-8")))


class DHT(ABC):
    """
    DHT abstract base class.

    Defines the interface for DHT operations.
    """

    @abstractmethod
    async def find_peer(self, peer_id: bytes) -> Optional[PeerEntry]:
        """
        Find a peer by ID.

        Args:
            peer_id: Peer ID to find (32 bytes)

        Returns:
            Peer info if found, None otherwise
        """
        pass

    @abstractmethod
    async def provide(self, cid: bytes, announce: bool = True) -> bool:
        """
        Announce that we provide a content.

        Args:
            cid: Content ID (CID)
            announce: Whether to announce to network

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def find_providers(self, cid: bytes, count: int = 20) -> List[PeerEntry]:
        """
        Find providers for a content.

        Args:
            cid: Content ID (CID)
            count: Maximum number of providers to return

        Returns:
            List of provider peers
        """
        pass

    @abstractmethod
    async def put_value(self, key: bytes, value: bytes) -> bool:
        """
        Store a key-value pair in DHT.

        Args:
            key: Key to store under
            value: Value to store

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def get_value(self, key: bytes) -> Optional[bytes]:
        """
        Retrieve a value from DHT.

        Args:
            key: Key to retrieve

        Returns:
            Value if found, None otherwise
        """
        pass


class KademliaDHT(DHT):
    """
    Kademlia DHT implementation.

    Implements the full Kademlia DHT protocol including:
    - Node discovery (find_peer)
    - Content routing (provide, find_providers)
    - Key-value storage (put_value, get_value)
    """

    def __init__(
        self,
        local_peer_id: bytes,
        network_send_func: Optional[Callable[[bytes, bytes, str], Awaitable[bytes]]] = None,
        k_size: int = K,
    ):
        """
        Initialize Kademlia DHT.

        Args:
            local_peer_id: Local peer's ID (32 bytes)
            network_send_func: Async function to send DHT messages
                             (target_peer_id, message_bytes, protocol_id) -> response
            k_size: Bucket size parameter (default 20)
        """
        if len(local_peer_id) != BYTE_COUNT:
            raise ValueError(f"Peer ID must be {BYTE_COUNT} bytes")

        self.local_peer_id = local_peer_id
        self.protocol_id = PROTOCOL_ID
        self._send_func = network_send_func

        # Core components
        self.routing_table = RoutingTable(local_peer_id, k_size)
        self.provider_manager = ProviderManager(max_providers=k_size)
        self.query_manager = QueryManager(alpha=3, timeout_ms=60000)

        # Local key-value store
        self._local_store: Dict[bytes, tuple[bytes, float]] = {}

        # Event handlers
        self._on_peer_found: List[Callable[[PeerEntry], Awaitable[None]]] = []
        self._on_provider_found: List[Callable[[bytes, PeerEntry], Awaitable[None]]] = []

        # Background tasks
        self._running = False
        self._refresh_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start DHT background tasks."""
        if self._running:
            return

        self._running = True

        # Start periodic bucket refresh
        self._refresh_task = asyncio.create_task(self._refresh_loop())

        logger.info(f"Kademlia DHT started: peer_id={self.local_peer_id.hex()[:8]}...")

    async def stop(self) -> None:
        """Stop DHT background tasks."""
        if not self._running:
            return

        self._running = False

        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        logger.info("Kademlia DHT stopped")

    async def find_peer(self, peer_id: bytes) -> Optional[PeerEntry]:
        """
        Find a peer by ID.

        First checks local routing table, then performs iterative lookup.

        Args:
            peer_id: Peer ID to find (32 bytes)

        Returns:
            Peer info if found, None otherwise
        """
        # Check local routing table first
        local_peer = self.routing_table.find_peer(peer_id)
        if local_peer:
            return local_peer

        # Perform iterative lookup
        result = await self.query_manager.find_peer(
            peer_id,
            self.routing_table,
            self._query_find_node
        )

        if result.success:
            # Add found peers to routing table
            for peer in result.peers:
                await self.routing_table.add_peer(peer)

                # Check if we found the target
                if peer.peer_id == peer_id:
                    return peer

        return None

    async def provide(self, cid: bytes, announce: bool = True) -> bool:
        """
        Announce that we provide a content.

        Args:
            cid: Content ID (CID)
            announce: Whether to announce to network

        Returns:
            True if successful
        """
        # Add to local providers
        await self.provider_manager.add_local_provider(cid)

        if not announce or not self._send_func:
            return True

        # Announce to closest peers
        result = await self.query_manager.provide(
            cid,
            self.local_peer_id,
            self.routing_table,
            self._announce_provider
        )

        return result.success

    async def find_providers(self, cid: bytes, count: int = 20) -> List[PeerEntry]:
        """
        Find providers for a content.

        Args:
            cid: Content ID (CID)
            count: Maximum number of providers to return

        Returns:
            List of provider peers
        """
        # Check local providers first
        local_providers = await self.provider_manager.get_provider_peer_ids(cid, count)
        if local_providers:
            # Convert to PeerEntry list
            providers = []
            for peer_id in local_providers:
                peer = self.routing_table.find_peer(peer_id)
                if peer:
                    providers.append(peer)
            if providers:
                return providers[:count]

        # Perform network lookup
        result = await self.query_manager.find_providers(
            cid,
            self.routing_table,
            self._query_get_providers
        )

        if result.success:
            # Add providers to routing table and local cache
            for peer in result.providers:
                await self.routing_table.add_peer(peer)

            return result.providers[:count]

        return []

    async def put_value(self, key: bytes, value: bytes) -> bool:
        """
        Store a key-value pair in DHT.

        Args:
            key: Key to store under
            value: Value to store

        Returns:
            True if successful
        """
        dht_key = compute_key(key)

        # Store locally
        self._local_store[dht_key] = (value, time.time() + 3600)

        if not self._send_func:
            return True

        # Announce to closest peers
        closest_peers = self.routing_table.find_closest_peers(dht_key, K)

        success = True
        for peer in closest_peers:
            try:
                message = KademliaMessage(
                    message_type=KademliaMessageType.PUT_VALUE,
                    key=dht_key,
                    value=value,
                    peer_id=self.local_peer_id,
                )

                response_data = await self._send_func(
                    peer.peer_id,
                    message.to_json(),
                    self.protocol_id
                )

                if response_data:
                    response = KademliaMessage.from_json(response_data)
                    if response.message_type == KademliaMessageType.PUT_VALUE:
                        continue

            except Exception as e:
                logger.warning(f"Failed to put value to peer: {e}")
                success = False

        return success

    async def get_value(self, key: bytes) -> Optional[bytes]:
        """
        Retrieve a value from DHT.

        Args:
            key: Key to retrieve

        Returns:
            Value if found, None otherwise
        """
        dht_key = compute_key(key)

        # Check local store first
        if dht_key in self._local_store:
            value, expires = self._local_store[dht_key]
            if time.time() < expires:
                return value
            else:
                del self._local_store[dht_key]

        if not self._send_func:
            return None

        # Query network
        result = await self.query_manager.find_value(
            dht_key,
            self.routing_table,
            self._query_get_value
        )

        if result.success and result.value:
            return result.value

        return None

    async def handle_message(self, peer_id: bytes, message: bytes) -> bytes:
        """
        Handle incoming DHT message.

        Args:
            peer_id: Sender's peer ID
            message: Raw message bytes

        Returns:
            Response message bytes
        """
        try:
            msg = KademliaMessage.from_json(message)
        except Exception as e:
            logger.error(f"Failed to parse DHT message: {e}")
            return self._create_error_response("Invalid message").to_json()

        # Add sender to routing table
        await self.routing_table.add_peer(PeerEntry(peer_id=peer_id))

        # Handle based on message type
        if msg.message_type == KademliaMessageType.FIND_NODE:
            return await self._handle_find_node(msg)
        elif msg.message_type == KademliaMessageType.FIND_VALUE:
            return await self._handle_find_value(msg)
        elif msg.message_type == KademliaMessageType.PUT_VALUE:
            return await self._handle_put_value(msg)
        elif msg.message_type == KademliaMessageType.ADD_PROVIDER:
            return await self._handle_add_provider(msg, peer_id)
        elif msg.message_type == KademliaMessageType.GET_PROVIDERS:
            return await self._handle_get_providers(msg)
        elif msg.message_type == KademliaMessageType.PING:
            return self._create_pong_response().to_json()
        else:
            return self._create_error_response("Unknown message type").to_json()

    async def add_bootstrap_peer(self, peer_id: bytes, addresses: List[str]) -> None:
        """
        Add a bootstrap peer to routing table.

        Args:
            peer_id: Bootstrap peer's ID
            addresses: List of multiaddresses
        """
        peer = PeerEntry(peer_id=peer_id, addresses=addresses)
        await self.routing_table.add_peer(peer)

    async def _handle_find_node(self, msg: KademliaMessage) -> bytes:
        """Handle FIND_NODE request."""
        if msg.key is None:
            return self._create_error_response("Missing key").to_json()

        closest_peers = self.routing_table.find_closest_peers(msg.key, K)

        response = KademliaMessage(
            message_type=KademliaMessageType.FIND_NODE,
            key=msg.key,
            peers=[{
                "id": p.peer_id,
                "addrs": p.addresses,
            } for p in closest_peers],
            peer_id=self.local_peer_id,
        )

        return response.to_json()

    async def _handle_find_value(self, msg: KademliaMessage) -> bytes:
        """Handle FIND_VALUE (GET_VALUE) request."""
        if msg.key is None:
            return self._create_error_response("Missing key").to_json()

        # Check local store
        value = None
        if msg.key in self._local_store:
            stored_value, expires = self._local_store[msg.key]
            if time.time() < expires:
                value = stored_value

        # Get closest peers
        closest_peers = self.routing_table.find_closest_peers(msg.key, K)

        response = KademliaMessage(
            message_type=KademliaMessageType.FIND_VALUE,
            key=msg.key,
            value=value,
            peers=[{
                "id": p.peer_id,
                "addrs": p.addresses,
            } for p in closest_peers],
            peer_id=self.local_peer_id,
        )

        return response.to_json()

    async def _handle_put_value(self, msg: KademliaMessage) -> bytes:
        """Handle PUT_VALUE request."""
        if msg.key is None or msg.value is None:
            return self._create_error_response("Missing key or value").to_json()

        # Store value
        self._local_store[msg.key] = (msg.value, time.time() + 3600)

        # Acknowledge
        response = KademliaMessage(
            message_type=KademliaMessageType.PUT_VALUE,
            key=msg.key,
            peer_id=self.local_peer_id,
        )

        return response.to_json()

    async def _handle_add_provider(self, msg: KademliaMessage, peer_id: bytes) -> bytes:
        """Handle ADD_PROVIDER request."""
        if msg.key is None:
            return self._create_error_response("Missing key").to_json()

        await self.provider_manager.add_provider(msg.key, peer_id)

        response = KademliaMessage(
            message_type=KademliaMessageType.ADD_PROVIDER,
            key=msg.key,
            peer_id=self.local_peer_id,
        )

        return response.to_json()

    async def _handle_get_providers(self, msg: KademliaMessage) -> bytes:
        """Handle GET_PROVIDERS request."""
        if msg.key is None:
            return self._create_error_response("Missing key").to_json()

        # Hash the key for DHT operations
        import hashlib
        dht_key = hashlib.sha256(msg.key).digest()

        # Get providers
        providers = self.provider_manager.get_providers(msg.key)

        # Get closest peers using the hashed key
        closest_peers = self.routing_table.find_closest_peers(dht_key, K)

        response = KademliaMessage(
            message_type=KademliaMessageType.GET_PROVIDERS,
            key=msg.key,
            providers=[{
                "id": p.peer_id,
                "addrs": [],  # Would get from routing table
            } for p in providers],
            peers=[{
                "id": p.peer_id,
                "addrs": p.addresses,
            } for p in closest_peers],
            peer_id=self.local_peer_id,
        )

        return response.to_json()

    def _create_error_response(self, error: str) -> KademliaMessage:
        """Create an error response."""
        return KademliaMessage(
            message_type=KademliaMessageType.PING,
            record={"error": error},
            peer_id=self.local_peer_id,
        )

    def _create_pong_response(self) -> KademliaMessage:
        """Create a PONG response."""
        return KademliaMessage(
            message_type=KademliaMessageType.PING,
            peer_id=self.local_peer_id,
        )

    async def _query_find_node(self, peer_id: bytes, target: bytes) -> List[PeerEntry]:
        """Query a peer for FIND_NODE."""
        if not self._send_func:
            return []

        message = KademliaMessage(
            message_type=KademliaMessageType.FIND_NODE,
            key=target,
            peer_id=self.local_peer_id,
        )

        try:
            response_data = await self._send_func(peer_id, message.to_json(), self.protocol_id)
            response = KademliaMessage.from_json(response_data)

            peers = []
            for peer_data in response.peers:
                peer_id = peer_data.get("id")
                if isinstance(peer_id, str):
                    peer_id = bytes.fromhex(peer_id)
                if peer_id:
                    peers.append(PeerEntry(
                        peer_id=peer_id,
                        addresses=peer_data.get("addrs", [])
                    ))

            return peers

        except Exception as e:
            logger.debug(f"FIND_NODE query failed: {e}")
            return []

    async def _query_get_value(
        self,
        peer_id: bytes,
        key: bytes
    ) -> tuple[Optional[bytes], List[PeerEntry]]:
        """Query a peer for GET_VALUE."""
        if not self._send_func:
            return (None, [])

        message = KademliaMessage(
            message_type=KademliaMessageType.FIND_VALUE,
            key=key,
            peer_id=self.local_peer_id,
        )

        try:
            response_data = await self._send_func(peer_id, message.to_json(), self.protocol_id)
            response = KademliaMessage.from_json(response_data)

            closer_peers = []
            for peer_data in response.peers:
                peer_id_bytes = peer_data.get("id")
                if isinstance(peer_id_bytes, str):
                    peer_id_bytes = bytes.fromhex(peer_id_bytes)
                if peer_id_bytes:
                    closer_peers.append(PeerEntry(
                        peer_id=peer_id_bytes,
                        addresses=peer_data.get("addrs", [])
                    ))

            return (response.value, closer_peers)

        except Exception as e:
            logger.debug(f"GET_VALUE query failed: {e}")
            return (None, [])

    async def _query_get_providers(
        self,
        peer_id: bytes,
        key: bytes
    ) -> tuple[List[PeerEntry], List[PeerEntry]]:
        """Query a peer for GET_PROVIDERS."""
        if not self._send_func:
            return ([], [])

        message = KademliaMessage(
            message_type=KademliaMessageType.GET_PROVIDERS,
            key=key,
            peer_id=self.local_peer_id,
        )

        try:
            response_data = await self._send_func(peer_id, message.to_json(), self.protocol_id)
            response = KademliaMessage.from_json(response_data)

            providers = []
            for provider_data in response.providers:
                provider_id = provider_data.get("id")
                if isinstance(provider_id, str):
                    provider_id = bytes.fromhex(provider_id)
                if provider_id:
                    providers.append(PeerEntry(
                        peer_id=provider_id,
                        addresses=provider_data.get("addrs", [])
                    ))

            closer_peers = []
            for peer_data in response.peers:
                peer_id_bytes = peer_data.get("id")
                if isinstance(peer_id_bytes, str):
                    peer_id_bytes = bytes.fromhex(peer_id_bytes)
                if peer_id_bytes:
                    closer_peers.append(PeerEntry(
                        peer_id=peer_id_bytes,
                        addresses=peer_data.get("addrs", [])
                    ))

            return (providers, closer_peers)

        except Exception as e:
            logger.debug(f"GET_PROVIDERS query failed: {e}")
            return ([], [])

    async def _announce_provider(
        self,
        peer_id: bytes,
        key: bytes,
        provider_id: bytes
    ) -> bool:
        """Announce a provider to a peer."""
        if not self._send_func:
            return False

        message = KademliaMessage(
            message_type=KademliaMessageType.ADD_PROVIDER,
            key=key,
            peer_id=provider_id,
        )

        try:
            response_data = await self._send_func(peer_id, message.to_json(), self.protocol_id)
            return bool(response_data)

        except Exception as e:
            logger.debug(f"ADD_PROVIDER announcement failed: {e}")
            return False

    async def _refresh_loop(self) -> None:
        """Periodically refresh routing table buckets."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Refresh every 5 minutes

                # Cleanup stale entries
                removed = await self.routing_table.cleanup_stale()
                if removed:
                    logger.debug(f"Cleaned up {removed} stale peers from routing table")

                # Cleanup expired providers
                expired = await self.provider_manager.cleanup_expired()
                if expired:
                    logger.debug(f"Cleaned up {expired} expired provider records")

                # Cleanup expired queries
                expired_queries = await self.query_manager.cleanup_expired_queries()
                if expired_queries:
                    logger.debug(f"Cleaned up {expired_queries} expired queries")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in refresh loop: {e}")

    @property
    def peer_count(self) -> int:
        """Get number of peers in routing table."""
        return self.routing_table.peer_count
