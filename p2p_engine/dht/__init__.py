"""
Kademlia DHT Implementation

This module implements the Kademlia Distributed Hash Table (DHT) protocol
compatible with libp2p (/ipfs/kad/1.0.0).

Key components:
- k-bucket routing table with XOR distance metric
- Node discovery and peer lookup
- Content provider tracking
- Key-value storage operations

Reference: https://docs.libp2p.io/concepts/dht/
"""

from .routing import (
    RoutingTable,
    KBucket,
    PeerEntry,
    calculate_distance,
    calculate_peer_id,
)

from .provider import (
    ProviderManager,
    ProviderRecord,
)

from .query import (
    QueryManager,
    QueryType,
    QueryState,
)

from .kademlia import (
    DHT,
    KademliaDHT,
    KademliaMessage,
    KademliaMessageType,
)

# Compatibility alias for tests
DHTRoutingTable = RoutingTable

__all__ = [
    # Routing
    "RoutingTable",
    "KBucket",
    "PeerEntry",
    "calculate_distance",
    "calculate_peer_id",
    # Providers
    "ProviderManager",
    "ProviderRecord",
    # Query
    "QueryManager",
    "QueryType",
    "QueryState",
    # Kademlia
    "DHT",
    "KademliaDHT",
    "KademliaMessage",
    "KademliaMessageType",
]

# Export compatibility alias
__all__.append("DHTRoutingTable")
