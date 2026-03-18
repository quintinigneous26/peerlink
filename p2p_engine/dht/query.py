"""
Query Manager for Kademlia DHT Operations

Implements iterative query logic for peer discovery and value lookups.
Handles concurrent queries and manages query state.

Reference: https://github.com/libp2p/specs/tree/master/kad-dht
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set, Callable, Awaitable
from enum import Enum
import heapq

from .routing import PeerEntry, calculate_distance, K, ALPHA

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Type of DHT query."""
    FIND_PEER = "find_peer"
    FIND_VALUE = "find_value"
    FIND_PROVIDERS = "find_providers"
    PROVIDE = "provide"


class QueryState(Enum):
    """State of a query."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass(order=True)
class QueryPeer:
    """
    A peer being queried with its distance.

    Used for priority queue in iterative queries.
    """
    distance: int
    peer: PeerEntry = field(compare=False)
    queried: bool = field(default=False, compare=False)


@dataclass
class QueryResult:
    """
    Result of a DHT query.

    Attributes:
        success: Whether query was successful
        peers: List of peers found
        value: Value found (for FIND_VALUE queries)
        providers: Providers found (for FIND_PROVIDERS queries)
        error: Error message if failed
        duration_ms: Query duration in milliseconds
    """
    success: bool
    peers: List[PeerEntry] = field(default_factory=list)
    value: Optional[bytes] = None
    providers: List[PeerEntry] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class QueryContext:
    """
    Context for an active query.

    Maintains query state, contacted peers, and results.
    """
    query_type: QueryType
    target_id: bytes
    target_key: Optional[bytes] = None
    started_at: float = field(default_factory=time.time)

    # Query state
    state: QueryState = QueryState.PENDING

    # Peer tracking
    contacted: Set[bytes] = field(default_factory=set)
    pending: List[QueryPeer] = field(default_factory=list)
    results: List[PeerEntry] = field(default_factory=list)

    # Value results (for FIND_VALUE)
    value: Optional[bytes] = None

    # Provider results (for FIND_PROVIDERS)
    providers: List[PeerEntry] = field(default_factory=list)

    # Error tracking
    error: Optional[str] = None
    retries: int = 0

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return (time.time() - self.started_at) * 1000

    def is_expired(self, timeout_ms: float = 60000.0) -> bool:
        """Check if query has timed out."""
        return self.elapsed_ms > timeout_ms


class QueryManager:
    """
    Manages Kademlia DHT queries.

    Implements iterative query logic with parallelism ALPHA.
    """

    def __init__(
        self,
        alpha: int = ALPHA,
        timeout_ms: float = 60000.0,
        max_retries: int = 3
    ):
        """
        Initialize query manager.

        Args:
            alpha: Parallelism parameter (default 3)
            timeout_ms: Query timeout in milliseconds
            max_retries: Maximum retries per query
        """
        self.alpha = alpha
        self.timeout_ms = timeout_ms
        self.max_retries = max_retries
        self._active_queries: Dict[str, QueryContext] = {}
        self._query_id_counter = 0
        self._lock = asyncio.Lock()

    async def find_peer(
        self,
        target_id: bytes,
        routing_table,
        query_func: Callable[[bytes, bytes], Awaitable[List[PeerEntry]]]
    ) -> QueryResult:
        """
        Find a peer by ID using iterative lookup.

        Args:
            target_id: Peer ID to find
            routing_table: Routing table to use for initial peers
            query_func: Async function to query a peer (peer_id, target) -> List[PeerEntry]

        Returns:
            Query result with closest peers
        """
        # Get initial closest peers from routing table
        initial_peers = routing_table.find_closest_peers(target_id, K)

        if not initial_peers:
            return QueryResult(
                success=False,
                error="No peers in routing table",
                duration_ms=0.0
            )

        context = QueryContext(
            query_type=QueryType.FIND_PEER,
            target_id=target_id
        )

        return await self._execute_iterative_query(
            context,
            initial_peers,
            query_func
        )

    async def find_value(
        self,
        key: bytes,
        routing_table,
        query_func: Callable[[bytes, bytes], Awaitable[tuple[Optional[bytes], List[PeerEntry]]]]
    ) -> QueryResult:
        """
        Find a value by key using iterative lookup.

        Args:
            key: Content key to find
            routing_table: Routing table to use for initial peers
            query_func: Async function returning (value, closer_peers)

        Returns:
            Query result with value or closest peers
        """
        # Use key hash as target
        import hashlib
        target_id = hashlib.sha256(key).digest()

        initial_peers = routing_table.find_closest_peers(target_id, K)

        if not initial_peers:
            return QueryResult(
                success=False,
                error="No peers in routing table",
                duration_ms=0.0
            )

        context = QueryContext(
            query_type=QueryType.FIND_VALUE,
            target_id=target_id,
            target_key=key
        )

        return await self._execute_iterative_query(
            context,
            initial_peers,
            query_func,
            find_value=True
        )

    async def find_providers(
        self,
        key: bytes,
        routing_table,
        query_func: Callable[[bytes, bytes], Awaitable[tuple[List[PeerEntry], List[PeerEntry]]]]
    ) -> QueryResult:
        """
        Find providers for a content key.

        Args:
            key: Content key (CID)
            routing_table: Routing table to use
            query_func: Async function returning (providers, closer_peers)

        Returns:
            Query result with providers
        """
        import hashlib
        target_id = hashlib.sha256(key).digest()

        initial_peers = routing_table.find_closest_peers(target_id, K)

        if not initial_peers:
            return QueryResult(
                success=False,
                error="No peers in routing table",
                duration_ms=0.0
            )

        context = QueryContext(
            query_type=QueryType.FIND_PROVIDERS,
            target_id=target_id,
            target_key=key
        )

        return await self._execute_iterative_query(
            context,
            initial_peers,
            query_func,
            find_providers=True
        )

    async def provide(
        self,
        key: bytes,
        local_peer_id: bytes,
        routing_table,
        query_func: Callable[[bytes, bytes, bytes], Awaitable[bool]]
    ) -> QueryResult:
        """
        Announce that we provide a content key.

        Args:
            key: Content key (CID)
            local_peer_id: Our peer ID
            routing_table: Routing table to use
            query_func: Async function to announce to peer

        Returns:
            Query result
        """
        import hashlib
        target_id = hashlib.sha256(key).digest()

        # Find closest peers to announce to
        closest_peers = routing_table.find_closest_peers(target_id, K)

        if not closest_peers:
            return QueryResult(
                success=False,
                error="No peers in routing table",
                duration_ms=0.0
            )

        # Announce to all closest peers
        announced = 0
        start_time = time.time()

        tasks = [
            query_func(peer.peer_id, key, local_peer_id)
            for peer in closest_peers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to announce to peer: {result}")
            elif result:
                announced += 1

        return QueryResult(
            success=announced > 0,
            peers=closest_peers,
            duration_ms=(time.time() - start_time) * 1000
        )

    async def _execute_iterative_query(
        self,
        context: QueryContext,
        initial_peers: List[PeerEntry],
        query_func: Callable,
        find_value: bool = False,
        find_providers: bool = False
    ) -> QueryResult:
        """
        Execute an iterative Kademlia query.

        Args:
            context: Query context
            initial_peers: Initial peers to query
            query_func: Function to query peers
            find_value: Whether this is a value lookup
            find_providers: Whether this is a provider lookup

        Returns:
            Query result
        """
        context.state = QueryState.RUNNING

        # Initialize query queue with initial peers
        for peer in initial_peers:
            distance = calculate_distance(peer.peer_id, context.target_id)
            heapq.heappush(context.pending, QueryPeer(distance, peer))

        # Track closest peer distance
        closest_distance = min((p.distance for p in context.pending), default=None)

        while context.pending and not context.is_expired(self.timeout_ms):
            # Get ALPHA closest unqueried peers
            to_query: List[QueryPeer] = []

            while len(to_query) < self.alpha and context.pending:
                peer_info = heapq.heappop(context.pending)

                if peer_info.peer.peer_id not in context.contacted:
                    to_query.append(peer_info)

            if not to_query:
                break

            # Query peers in parallel
            tasks = [
                self._query_peer(peer, context, query_func, find_value, find_providers)
                for peer in to_query
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

            # Check if we found what we're looking for
            if find_value and context.value:
                context.state = QueryState.COMPLETED
                break

            # Check if we have enough providers
            if find_providers and len(context.providers) >= K:
                context.state = QueryState.COMPLETED
                break

            # Check if we've found the target peer
            if context.query_type == QueryType.FIND_PEER:
                for peer in context.results:
                    if peer.peer_id == context.target_id:
                        context.state = QueryState.COMPLETED
                        break

            # Stop if we've exhausted closer peers
            if context.pending:
                current_closest = context.pending[0].distance
                if current_closest >= closest_distance:
                    # No closer peers found
                    break
                closest_distance = current_closest

        # Finalize result
        duration = context.elapsed_ms

        if context.state == QueryState.RUNNING:
            context.state = QueryState.COMPLETED if context.results else QueryState.TIMEOUT

        return QueryResult(
            success=context.state == QueryState.COMPLETED,
            peers=context.results[:K],
            value=context.value,
            providers=context.providers[:K],
            error=context.error,
            duration_ms=duration
        )

    async def _query_peer(
        self,
        peer_info: QueryPeer,
        context: QueryContext,
        query_func: Callable,
        find_value: bool,
        find_providers: bool
    ) -> None:
        """
        Query a single peer and update context.

        Args:
            peer_info: Peer to query with distance
            context: Query context to update
            query_func: Query function
            find_value: Whether looking for value
            find_providers: Whether looking for providers
        """
        peer_id = peer_info.peer.peer_id
        context.contacted.add(peer_id)
        peer_info.queried = True

        try:
            if find_value:
                # Query for value
                result = await query_func(peer_id, context.target_key)
                if isinstance(result, tuple):
                    value, closer_peers = result
                else:
                    value, closer_peers = result, []

                if value:
                    context.value = value
                    context.results.append(peer_info.peer)

            elif find_providers:
                # Query for providers
                result = await query_func(peer_id, context.target_key)
                if isinstance(result, tuple):
                    providers, closer_peers = result
                else:
                    providers, closer_peers = [], result

                context.providers.extend(providers)

                # Add closer peers
                for peer in closer_peers:
                    distance = calculate_distance(peer.peer_id, context.target_id)
                    heapq.heappush(context.pending, QueryPeer(distance, peer))

            else:
                # Regular peer lookup
                closer_peers = await query_func(peer_id, context.target_id)

                # Add closer peers to results and pending queue
                for peer in closer_peers:
                    context.results.append(peer)
                    distance = calculate_distance(peer.peer_id, context.target_id)
                    heapq.heappush(context.pending, QueryPeer(distance, peer))

        except Exception as e:
            logger.debug(f"Query to peer {peer_id.hex()[:8]} failed: {e}")
            context.retries += 1

    async def cleanup_expired_queries(self) -> int:
        """
        Remove expired queries from active list.

        Returns:
            Number of queries removed
        """
        async with self._lock:
            to_remove = [
                query_id
                for query_id, ctx in self._active_queries.items()
                if ctx.is_expired(self.timeout_ms)
            ]

            for query_id in to_remove:
                del self._active_queries[query_id]

            return len(to_remove)


    @property
    def active_query_count(self) -> int:
        """Get number of active queries."""
        return len(self._active_queries)
