"""
PubSub Protocol Implementation

This module implements the libp2p PubSub protocol with GossipSub v1.1 router.
It provides a publish/subscribe interface for peer-to-peer messaging.

Protocol IDs:
- /meshsub/1.1.0 (GossipSub v1.1)
- /floodsub/1.0.0 (FloodSub - fallback)

References:
- https://github.com/libp2p/specs/blob/master/pubsub/README.md
- https://github.com/libp2p/specs/blob/master/pubsub/gossipsub/gossipsub-v1.1.md
"""
import asyncio
import hashlib
import json
import logging
import random
import struct
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

from .messages import encode_varint, decode_varint

logger = logging.getLogger(__name__)


# ==================== Protocol IDs ====================

PROTOCOL_ID_GOSSIPSUB = "/meshsub/1.1.0"
PROTOCOL_ID_FLOODSUB = "/floodsub/1.0.0"
PROTOCOL_IDS = [PROTOCOL_ID_GOSSIPSUB, PROTOCOL_ID_FLOODSUB]


# ==================== Message Types ====================

class SignaturePolicy(Enum):
    """Message signature policy."""
    STRICT_SIGN = "strict_sign"      # Sign all messages, require signatures
    STRICT_NO_SIGN = "strict_no_sign"  # No signing, reject signed messages
    LAX_SIGN = "lax_sign"            # Sign, accept unsigned (legacy, insecure)
    LAX_NO_SIGN = "lax_no_sign"      # No signing, accept signed (legacy, insecure)


# ==================== Data Classes ====================

@dataclass
class PubSubMessage:
    """PubSub message data structure."""
    from_peer: str = ""
    data: bytes = b""
    seqno: bytes = b""
    topic: str = ""
    signature: bytes = b""
    key: bytes = b""

    def to_protobuf_dict(self) -> dict:
        """Convert to protobuf-compatible dictionary."""
        result = {}

        if self.from_peer:
            result["from"] = self.from_peer
        if self.data:
            result["data"] = self.data
        if self.seqno:
            result["seqno"] = self.seqno
        if self.topic:
            result["topic"] = self.topic
        if self.signature:
            result["signature"] = self.signature
        if self.key:
            result["key"] = self.key

        return result

    def to_json_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        result = {}

        if self.from_peer:
            result["from"] = self.from_peer
        if self.data:
            result["data"] = self.data.hex()
        if self.seqno:
            result["seqno"] = self.seqno.hex()
        if self.topic:
            result["topic"] = self.topic
        if self.signature:
            result["signature"] = self.signature.hex()
        if self.key:
            result["key"] = self.key.hex()

        return result

    @classmethod
    def from_protobuf_dict(cls, data: dict) -> "PubSubMessage":
        """Create PubSubMessage from protobuf dictionary."""
        return cls(
            from_peer=data.get("from", ""),
            data=data.get("data", b""),
            seqno=data.get("seqno", b""),
            topic=data.get("topic", ""),
            signature=data.get("signature", b""),
            key=data.get("key", b""),
        )

    @classmethod
    def from_json_dict(cls, data: dict) -> "PubSubMessage":
        """Create PubSubMessage from JSON dictionary."""
        return cls(
            from_peer=data.get("from", ""),
            data=bytes.fromhex(data.get("data", "")) if data.get("data") else b"",
            seqno=bytes.fromhex(data.get("seqno", "")) if data.get("seqno") else b"",
            topic=data.get("topic", ""),
            signature=bytes.fromhex(data.get("signature", "")) if data.get("signature") else b"",
            key=bytes.fromhex(data.get("key", "")) if data.get("key") else b"",
        )

    def message_id(self) -> bytes:
        """Calculate message ID from from and seqno."""
        if self.from_peer and self.seqno:
            return hashlib.sha256(self.from_peer.encode() + self.seqno).digest()
        # Fallback to content-based ID
        return hashlib.sha256(self.data).digest()


@dataclass
class SubOpts:
    """Subscription options."""
    subscribe: bool = True
    topicid: str = ""

    def to_dict(self) -> dict:
        return {
            "subscribe": self.subscribe,
            "topicid": self.topicid,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubOpts":
        return cls(
            subscribe=data.get("subscribe", True),
            topicid=data.get("topicid", ""),
        )


@dataclass
class RPC:
    """RPC message exchanged between peers."""
    subscriptions: List[SubOpts] = field(default_factory=list)
    publish: List[PubSubMessage] = field(default_factory=list)

    # GossipSub control messages
    control: Optional["ControlMessage"] = None

    def to_json_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        result = {}

        if self.subscriptions:
            result["subscriptions"] = [s.to_dict() for s in self.subscriptions]
        if self.publish:
            result["publish"] = [m.to_json_dict() for m in self.publish]
        if self.control:
            result["control"] = self.control.to_json_dict()

        return result

    @classmethod
    def from_json_dict(cls, data: dict) -> "RPC":
        """Create RPC from JSON dictionary."""
        rpc = cls()

        if "subscriptions" in data:
            rpc.subscriptions = [SubOpts.from_dict(s) for s in data["subscriptions"]]
        if "publish" in data:
            rpc.publish = [PubSubMessage.from_json_dict(m) for m in data["publish"]]
        if "control" in data:
            rpc.control = ControlMessage.from_json_dict(data["control"])

        return rpc


@dataclass
class ControlMessage:
    """GossipSub control message."""
    ihave: List["ControlIHave"] = field(default_factory=list)
    iwant: List["ControlIWant"] = field(default_factory=list)
    graft: List["ControlGraft"] = field(default_factory=list)
    prune: List["ControlPrune"] = field(default_factory=list)

    def to_json_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        result = {}

        if self.ihave:
            result["ihave"] = [m.to_dict() for m in self.ihave]
        if self.iwant:
            result["iwant"] = [m.to_dict() for m in self.iwant]
        if self.graft:
            result["graft"] = [m.to_dict() for m in self.graft]
        if self.prune:
            result["prune"] = [m.to_dict() for m in self.prune]

        return result

    @classmethod
    def from_json_dict(cls, data: dict) -> "ControlMessage":
        """Create ControlMessage from JSON dictionary."""
        ctrl = cls()

        if "ihave" in data:
            ctrl.ihave = [ControlIHave.from_dict(d) for d in data["ihave"]]
        if "iwant" in data:
            ctrl.iwant = [ControlIWant.from_dict(d) for d in data["iwant"]]
        if "graft" in data:
            ctrl.graft = [ControlGraft.from_dict(d) for d in data["graft"]]
        if "prune" in data:
            ctrl.prune = [ControlPrune.from_dict(d) for d in data["prune"]]

        return ctrl


@dataclass
class ControlIHave:
    """IHAVE control message - announces available messages."""
    topic_id: str = ""
    message_ids: List[bytes] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "topicID": self.topic_id,
            "messageIDs": [m.hex() for m in self.message_ids],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ControlIHave":
        msg_ids = data.get("messageIDs", [])
        if isinstance(msg_ids, list):
            msg_ids = [bytes.fromhex(m) if isinstance(m, str) else m for m in msg_ids]
        return cls(
            topic_id=data.get("topicID", ""),
            message_ids=msg_ids,
        )


@dataclass
class ControlIWant:
    """IWANT control message - requests specific messages."""
    message_ids: List[bytes] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "messageIDs": [m.hex() for m in self.message_ids],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ControlIWant":
        msg_ids = data.get("messageIDs", [])
        if isinstance(msg_ids, list):
            msg_ids = [bytes.fromhex(m) if isinstance(m, str) else m for m in msg_ids]
        return cls(message_ids=msg_ids)


@dataclass
class ControlGraft:
    """GRAFT control message - adds peer to mesh."""
    topic_id: str = ""

    def to_dict(self) -> dict:
        return {"topicID": self.topic_id}

    @classmethod
    def from_dict(cls, data: dict) -> "ControlGraft":
        return cls(topic_id=data.get("topicID", ""))


@dataclass
class ControlPrune:
    """PRUNE control message - removes peer from mesh."""
    topic_id: str = ""

    # GossipSub v1.1 extensions
    peers: List["PeerInfoPB"] = field(default_factory=list)
    backoff: int = 60  # backoff time in seconds

    def to_dict(self) -> dict:
        return {
            "topicID": self.topic_id,
            "peers": [p.to_dict() for p in self.peers],
            "backoff": self.backoff,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ControlPrune":
        peers_data = data.get("peers", [])
        peers = [PeerInfoPB.from_dict(p) for p in peers_data] if peers_data else []
        return cls(
            topic_id=data.get("topicID", ""),
            peers=peers,
            backoff=data.get("backoff", 60),
        )


@dataclass
class PeerInfoPB:
    """Peer info for peer exchange (PX)."""
    peer_id: bytes = b""
    signed_peer_record: bytes = b""

    def to_dict(self) -> dict:
        return {
            "peerID": self.peer_id.hex() if isinstance(self.peer_id, bytes) else self.peer_id,
            "signedPeerRecord": self.signed_peer_record.hex() if isinstance(self.signed_peer_record, bytes) else self.signed_peer_record,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PeerInfoPB":
        peer_id = data.get("peerID", b"")
        if isinstance(peer_id, str):
            peer_id = bytes.fromhex(peer_id)

        spr = data.get("signedPeerRecord", b"")
        if isinstance(spr, str):
            spr = bytes.fromhex(spr)

        return cls(peer_id=peer_id, signed_peer_record=spr)


# ==================== Subscription ====================

@dataclass
class Subscription:
    """Active subscription to a topic."""
    topic: str
    pubsub: "PubSub"

    async def cancel(self) -> None:
        """Cancel the subscription."""
        await self.pubsub.unsubscribe(self.topic)

    def __aiter__(self):
        """Async iterator over messages."""
        return self

    async def __anext__(self) -> PubSubMessage:
        """Get next message from subscription."""
        # This will be implemented by the PubSub class
        while True:
            msg = await self.pubsub._get_next_message(self.topic)
            if msg:
                return msg
            await asyncio.sleep(0.1)


# ==================== PubSub Abstract Base ====================

class PubSub(ABC):
    """PubSub abstract base class."""

    @abstractmethod
    async def subscribe(self, topic: str) -> Subscription:
        """Subscribe to a topic."""
        pass

    @abstractmethod
    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        pass

    @abstractmethod
    async def publish(self, topic: str, data: bytes) -> None:
        """Publish a message to a topic."""
        pass

    @abstractmethod
    def list_peers(self, topic: str) -> List[str]:
        """List peers subscribed to a topic."""
        pass

    @abstractmethod
    def get_topics(self) -> List[str]:
        """Get list of known topics."""
        pass


# ==================== GossipSub Router ====================

@dataclass
class GossipSubConfig:
    """GossipSub configuration parameters."""
    # Mesh degree parameters
    D: int = 6                # Desired mesh degree
    D_low: int = 4            # Lower bound
    D_high: int = 12          # Upper bound
    D_out: int = 2            # Outbound connections
    D_score: int = 4          # Peers to retain by score
    D_lazy: int = 6           # Gossip emission degree

    # Timing parameters
    heartbeat_interval: float = 1.0  # Heartbeat interval in seconds
    fanout_ttl: float = 60.0         # Fanout TTL in seconds
    seen_ttl: float = 120.0          # Seen cache TTL in seconds

    # Message cache
    mcache_len: int = 5       # Number of history windows
    mcache_gossip: int = 3    # Windows for gossip

    # GossipSub v1.1 parameters
    prune_backoff: float = 60.0       # Prune backoff
    unsubscribe_backoff: float = 10.0 # Unsubscribe backoff
    flood_publish: bool = True        # Enable flood publishing
    gossip_factor: float = 0.25       # Adaptive gossip factor

    # Peer scoring thresholds
    gossip_threshold: float = -100.0
    publish_threshold: float = -200.0
    graylist_threshold: float = -400.0
    accept_px_threshold: float = 100.0
    opportunistic_graft_threshold: float = 5.0


class MessageCache:
    """Message cache for gossip."""

    def __init__(self, mcache_len: int = 5):
        self.mcache_len = mcache_len
        self.windows: List[Dict[bytes, PubSubMessage]] = [defaultdict(lambda: None)]
        self.current = 0

    def put(self, msg: PubSubMessage) -> None:
        """Add message to current window."""
        msg_id = msg.message_id()
        self.windows[self.current][msg_id] = msg

    def get(self, msg_id: bytes) -> Optional[PubSubMessage]:
        """Get message from cache."""
        for window in self.windows:
            if msg_id in window:
                return window[msg_id]
        return None

    def get_gossip_ids(self, topic: str, gossip_count: int) -> List[bytes]:
        """Get message IDs for gossip from recent windows."""
        ids = []
        for i, window in enumerate(self.windows):
            if i >= gossip_count:
                break
            for msg_id, msg in window.items():
                if msg.topic == topic:
                    ids.append(msg_id)
        return ids

    def shift(self) -> None:
        """Shift to next window."""
        self.current = (self.current + 1) % self.mcache_len

        # Clear the new current window and reinitialize
        if len(self.windows) <= self.current:
            self.windows.append(defaultdict(lambda: None))
        else:
            self.windows[self.current].clear()


class SeenCache:
    """LRU cache for seen message IDs."""

    def __init__(self, ttl: float = 120.0):
        self.ttl = ttl
        self.cache: Dict[bytes, float] = {}

    def seen(self, msg_id: bytes) -> bool:
        """Check if message ID was seen."""
        now = time.time()
        # Clean expired entries
        expired = [k for k, v in self.cache.items() if now - v > self.ttl]
        for k in expired:
            del self.cache[k]

        if msg_id in self.cache:
            return True

        self.cache[msg_id] = now
        return False

    def has(self, msg_id: bytes) -> bool:
        """Check if message ID is in cache without updating."""
        return msg_id in self.cache


class GossipSubRouter:
    """GossipSub v1.1 router implementation."""

    def __init__(self, peer_id: str, config: Optional[GossipSubConfig] = None):
        self.peer_id = peer_id
        self.config = config or GossipSubConfig()

        # Topic subscriptions
        self.my_topics: Set[str] = set()

        # Peer tracking
        self.peers: Set[str] = set()  # All known pubsub peers
        self.peer_topics: Dict[str, Set[str]] = defaultdict(set)  # Topics each peer is subscribed to

        # Mesh and fanout
        self.mesh: Dict[str, Set[str]] = defaultdict(set)  # Subscribed topics mesh
        self.fanout: Dict[str, Set[str]] = defaultdict(set)  # Unsubscribed topics
        self.fanout_last_pub: Dict[str, float] = {}  # Last publish time for fanout

        # Message cache
        self.mcache = MessageCache(self.config.mcache_len)
        self.seen_cache = SeenCache(self.config.seen_ttl)

        # Backoff state
        self.backoff: Dict[Tuple[str, str], float] = {}  # (topic, peer) -> expiry

        # Peer scores (basic implementation)
        self.peer_scores: Dict[str, float] = defaultdict(float)

        # Sequence number for publishing
        self.seqno: int = 0
        self._seqno_lock = asyncio.Lock()

    def add_peer(self, peer_id: str) -> None:
        """Add a known pubsub peer."""
        self.peers.add(peer_id)

    def remove_peer(self, peer_id: str) -> None:
        """Remove a peer."""
        self.peers.discard(peer_id)
        self.peer_topics.pop(peer_id, None)

        # Remove from all meshes and fanouts
        for topic in list(self.mesh.keys()):
            self.mesh[topic].discard(peer_id)
        for topic in list(self.fanout.keys()):
            self.fanout[topic].discard(peer_id)

    def handle_subscription(self, peer_id: str, sub: SubOpts) -> None:
        """Handle subscription announcement from peer."""
        if sub.subscribe:
            self.peer_topics[peer_id].add(sub.topicid)
        else:
            self.peer_topics[peer_id].discard(sub.topicid)

    def get_peers(self, topic: str, exclude: Optional[Set[str]] = None) -> Set[str]:
        """Get peers subscribed to a topic."""
        exclude = exclude or set()
        return {
            p for p in self.peers
            if topic in self.peer_topics[p] and p not in exclude
        }

    async def join_topic(self, topic: str) -> None:
        """Join a topic (subscribe)."""
        if topic in self.my_topics:
            return

        self.my_topics.add(topic)

        # Move from fanout if exists
        if topic in self.fanout:
            self.mesh[topic] = self.fanout.pop(topic)
            self.fanout_last_pub.pop(topic, None)
        else:
            # Select D peers to graft
            topic_peers = self.get_peers(topic)
            to_graft = random.sample(list(topic_peers), min(self.config.D, len(topic_peers)))
            self.mesh[topic] = set(to_graft)

    async def leave_topic(self, topic: str) -> None:
        """Leave a topic (unsubscribe)."""
        if topic not in self.my_topics:
            return

        self.my_topics.discard(topic)
        self.mesh.pop(topic, None)

    def get_mesh_peers(self, topic: str) -> Set[str]:
        """Get mesh peers for a topic."""
        return self.mesh.get(topic, set())

    def get_fanout_peers(self, topic: str) -> Set[str]:
        """Get fanout peers for a topic."""
        return self.fanout.get(topic, set())

    async def publish(self, topic: str, data: bytes, from_peer: str) -> Tuple[List[str], List[str]]:
        """Get target peers for publishing. Returns (mesh_targets, fanout_targets)."""
        async with self._seqno_lock:
            self.seqno += 1
            seqno_bytes = struct.pack(">Q", self.seqno)

        # Create message
        msg = PubSubMessage(
            from_peer=from_peer,
            data=data,
            seqno=seqno_bytes,
            topic=topic,
        )

        # Add to cache
        self.mcache.put(msg)
        self.seen_cache.seen(msg.message_id())

        # Get targets
        mesh_targets: List[str] = []
        fanout_targets: List[str] = []

        if topic in self.my_topics:
            # Subscribed: send to mesh
            mesh_targets = list(self.mesh.get(topic, set()))
        elif topic in self.fanout:
            # Has fanout
            fanout_targets = list(self.fanout[topic])
            self.fanout_last_pub[topic] = time.time()
        else:
            # Create new fanout
            topic_peers = self.get_peers(topic)
            to_add = random.sample(list(topic_peers), min(self.config.D, len(topic_peers)))
            self.fanout[topic] = set(to_add)
            self.fanout_last_pub[topic] = time.time()
            fanout_targets = to_add

        return mesh_targets, fanout_targets

    def handle_message(self, msg: PubSubMessage, from_peer: str) -> bool:
        """Handle incoming message. Returns True if message should be processed."""
        msg_id = msg.message_id()

        # Check if seen
        if self.seen_cache.seen(msg_id):
            return False

        # Add to cache
        self.mcache.put(msg)

        # Don't forward our own messages
        if msg.from_peer == self.peer_id:
            return False

        return True

    def get_forward_targets(self, topic: str, from_peer: str) -> List[str]:
        """Get targets for forwarding a message."""
        targets = set()

        # Add mesh peers
        if topic in self.mesh:
            targets.update(self.mesh[topic])

        # Remove source peer
        targets.discard(from_peer)

        return list(targets)

    def heartbeat(self) -> ControlMessage:
        """Perform heartbeat and return control messages to send."""
        control = ControlMessage()

        # Mesh maintenance
        for topic, mesh_peers in list(self.mesh.items()):
            # Check undersubscription
            if len(mesh_peers) < self.config.D_low:
                topic_peers = self.get_peers(topic, exclude=mesh_peers)
                to_graft = random.sample(
                    list(topic_peers),
                    min(self.config.D - len(mesh_peers), len(topic_peers))
                )
                for peer in to_graft:
                    mesh_peers.add(peer)
                    control.graft.append(ControlGraft(topic_id=topic))

            # Check oversubscription
            elif len(mesh_peers) > self.config.D_high:
                to_remove_count = len(mesh_peers) - self.config.D
                to_remove = random.sample(list(mesh_peers), to_remove_count)
                for peer in to_remove:
                    mesh_peers.remove(peer)
                    self._add_backoff(topic, peer)
                    prune = ControlPrune(topic_id=topic)
                    # Could add PX peers here
                    control.prune.append(prune)

        # Fanout maintenance
        now = time.time()
        for topic, fanout_peers in list(self.fanout.items()):
            # Check TTL
            last_pub = self.fanout_last_pub.get(topic, 0)
            if now - last_pub > self.config.fanout_ttl:
                self.fanout.pop(topic, None)
                self.fanout_last_pub.pop(topic, None)
                continue

            # Ensure minimum size
            if len(fanout_peers) < self.config.D:
                topic_peers = self.get_peers(topic, exclude=fanout_peers)
                to_add = random.sample(
                    list(topic_peers),
                    min(self.config.D - len(fanout_peers), len(topic_peers))
                )
                fanout_peers.update(to_add)

        # Gossip emission
        all_topics = set(self.mesh.keys()) | set(self.fanout.keys())
        for topic in all_topics:
            mids = self.mcache.get_gossip_ids(topic, self.config.mcache_gossip)
            if mids:
                # Select D random peers for gossip
                topic_peers = self.get_peers(topic)
                mesh_peers = self.mesh.get(topic, set())
                fanout_peers = self.fanout.get(topic, set())

                gossip_targets = list(topic_peers - mesh_peers - fanout_peers)
                gossip_targets = random.sample(
                    gossip_targets,
                    min(self.config.D, len(gossip_targets))
                )

                if gossip_targets:
                    ihave = ControlIHave(topic_id=topic, message_ids=mids)
                    control.ihave.append(ihave)

        # Shift message cache
        self.mcache.shift()

        return control

    def handle_graft(self, topic: str, from_peer: str) -> Optional[ControlPrune]:
        """Handle GRAFT control message."""
        if topic not in self.my_topics:
            # Not subscribed, prune
            prune = ControlPrune(topic_id=topic)
            self._add_backoff(topic, from_peer)
            return prune

        # Check backoff
        if self._in_backoff(topic, from_peer):
            prune = ControlPrune(topic_id=topic)
            return prune

        # Add to mesh
        self.mesh[topic].add(from_peer)
        return None

    def handle_prune(self, topic: str, from_peer: str, prune: ControlPrune) -> None:
        """Handle PRUNE control message."""
        self.mesh[topic].discard(from_peer)
        self.fanout[topic].discard(from_peer)
        self._add_backoff(topic, from_peer, duration=prune.backoff)

    def handle_ihave(self, topic: str, msg_ids: List[bytes]) -> List[bytes]:
        """Handle IHAVE control message. Returns message IDs to request."""
        want = []
        for msg_id in msg_ids:
            if not self.seen_cache.has(msg_id):
                want.append(msg_id)
        return want

    def handle_iwant(self, msg_ids: List[bytes]) -> List[PubSubMessage]:
        """Handle IWANT control message. Returns requested messages."""
        messages = []
        for msg_id in msg_ids:
            msg = self.mcache.get(msg_id)
            if msg:
                messages.append(msg)
        return messages

    def _add_backoff(self, topic: str, peer: str, duration: Optional[float] = None) -> None:
        """Add backoff for topic-peer pair."""
        duration = duration or self.config.prune_backoff
        self.backoff[(topic, peer)] = time.time() + duration

    def _in_backoff(self, topic: str, peer: str) -> bool:
        """Check if topic-peer pair is in backoff."""
        expiry = self.backoff.get((topic, peer), 0)
        return time.time() < expiry


# ==================== GossipSub Implementation ====================

class GossipSub(PubSub):
    """GossipSub v1.1 implementation."""

    def __init__(
        self,
        peer_id: str,
        config: Optional[GossipSubConfig] = None,
        signature_policy: SignaturePolicy = SignaturePolicy.STRICT_NO_SIGN,
    ):
        self.peer_id = peer_id
        self.router = GossipSubRouter(peer_id, config)
        self.signature_policy = signature_policy

        # Message handlers per topic
        self._topic_handlers: Dict[str, List[Callable[[PubSubMessage], Awaitable[None]]]] = {}
        self._message_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

        # Heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

        # Peer connections (for sending RPCs)
        self._peer_connections: Dict[str, Any] = {}

        # Sequence lock
        self._seqno_lock = asyncio.Lock()
        self._seqno: int = 0

    async def start(self) -> None:
        """Start the GossipSub router."""
        if self._running:
            return

        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"GossipSub started for peer {self.peer_id}")

    async def stop(self) -> None:
        """Stop the GossipSub router."""
        if not self._running:
            return

        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        logger.info(f"GossipSub stopped for peer {self.peer_id}")

    async def subscribe(self, topic: str) -> Subscription:
        """Subscribe to a topic."""
        await self.router.join_topic(topic)

        # Announce subscription to all peers
        await self._announce_subscription(topic, True)

        return Subscription(topic=topic, pubsub=self)

    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        await self.router.leave_topic(topic)

        # Announce unsubscription to all peers
        await self._announce_subscription(topic, False)

        # Clean up handlers
        self._topic_handlers.pop(topic, None)
        self._message_queues.pop(topic, None)

    async def publish(self, topic: str, data: bytes) -> None:
        """Publish a message to a topic."""
        async with self._seqno_lock:
            self._seqno += 1
            seqno_bytes = struct.pack(">Q", self._seqno)

        msg = PubSubMessage(
            from_peer=self.peer_id,
            data=data,
            seqno=seqno_bytes,
            topic=topic,
        )

        # Get targets
        mesh_targets = []
        fanout_targets = []

        if topic in self.router.my_topics:
            mesh_targets = list(self.router.mesh.get(topic, set()))
        else:
            # Use fanout or create new one
            if topic in self.router.fanout:
                fanout_targets = list(self.router.fanout[topic])
            else:
                topic_peers = self.router.get_peers(topic)
                to_add = random.sample(
                    list(topic_peers),
                    min(self.router.config.D, len(topic_peers))
                )
                self.router.fanout[topic] = set(to_add)
                fanout_targets = to_add

            self.router.fanout_last_pub[topic] = time.time()

        # Add to cache
        self.router.mcache.put(msg)
        self.router.seen_cache.seen(msg.message_id())

        # Publish to targets
        targets = mesh_targets + fanout_targets
        if targets:
            rpc = RPC(publish=[msg])
            await self._send_rpc_to_peers(targets, rpc)

    def list_peers(self, topic: str) -> List[str]:
        """List peers subscribed to a topic."""
        return list(self.router.get_peers(topic))

    def get_topics(self) -> List[str]:
        """Get list of known topics."""
        return list(self.router.my_topics)

    def add_peer(self, peer_id: str, connection: Any) -> None:
        """Add a peer connection."""
        self.router.add_peer(peer_id)
        self._peer_connections[peer_id] = connection

    def remove_peer(self, peer_id: str) -> None:
        """Remove a peer."""
        self.router.remove_peer(peer_id)
        self._peer_connections.pop(peer_id, None)

    async def handle_rpc(self, rpc: RPC, from_peer: str) -> Optional[RPC]:
        """Handle incoming RPC from peer. Returns optional response RPC."""
        response_msgs = []

        # Handle subscriptions
        for sub in rpc.subscriptions:
            self.router.handle_subscription(from_peer, sub)

        # Handle published messages
        for msg in rpc.publish:
            if self.router.handle_message(msg, from_peer):
                # Forward to mesh
                forward_targets = self.router.get_forward_targets(msg.topic, from_peer)
                if forward_targets:
                    await self._send_rpc_to_peers(forward_targets, RPC(publish=[msg]))

                # Add to topic queue
                await self._message_queues[msg.topic].put(msg)

                # Call handlers
                for handler in self._topic_handlers.get(msg.topic, []):
                    try:
                        await handler(msg)
                    except Exception as e:
                        logger.error(f"Handler error for topic {msg.topic}: {e}")

        # Handle control messages
        if rpc.control:
            response = await self._handle_control(rpc.control, from_peer)
            if response:
                response_msgs.append(response)

        # Combine responses
        if response_msgs:
            result = RPC()
            for resp in response_msgs:
                if resp.publish:
                    result.publish.extend(resp.publish)
                if resp.control:
                    if not result.control:
                        result.control = ControlMessage()
                    if resp.control.ihave:
                        result.control.ihave.extend(resp.control.ihave)
                    if resp.control.iwant:
                        result.control.iwant.extend(resp.control.iwant)
                    if resp.control.graft:
                        result.control.graft.extend(resp.control.graft)
                    if resp.control.prune:
                        result.control.prune.extend(resp.control.prune)
            return result

        return None

    async def _handle_control(self, control: ControlMessage, from_peer: str) -> Optional[RPC]:
        """Handle control messages."""
        rpc = RPC()
        response_control = ControlMessage()

        # Handle GRAFT
        for graft in control.graft:
            prune = self.router.handle_graft(graft.topic_id, from_peer)
            if prune:
                response_control.prune.append(prune)

        # Handle PRUNE
        for prune in control.prune:
            self.router.handle_prune(prune.topic_id, from_peer, prune)

        # Handle IHAVE
        for ihave in control.ihave:
            want_ids = self.router.handle_ihave(ihave.topic_id, ihave.message_ids)
            if want_ids:
                response_control.iwant.append(ControlIWant(message_ids=want_ids))

        # Handle IWANT
        for iwant in control.iwant:
            messages = self.router.handle_iwant(iwant.message_ids)
            if messages:
                rpc.publish.extend(messages)

        if response_control.ihave or response_control.iwant or response_control.graft or response_control.prune:
            rpc.control = response_control

        if rpc.publish or rpc.control:
            return rpc

        return None

    async def _announce_subscription(self, topic: str, subscribe: bool) -> None:
        """Announce subscription to all peers."""
        sub = SubOpts(subscribe=subscribe, topicid=topic)
        rpc = RPC(subscriptions=[sub])
        await self._send_rpc_to_peers(list(self.router.peers), rpc)

    async def _send_rpc_to_peers(self, peers: List[str], rpc: RPC) -> None:
        """Send RPC to multiple peers."""
        for peer in peers:
            if peer in self._peer_connections:
                try:
                    await self._send_rpc(peer, rpc)
                except Exception as e:
                    logger.error(f"Failed to send RPC to {peer}: {e}")

    async def _send_rpc(self, peer_id: str, rpc: RPC) -> None:
        """Send RPC to a specific peer."""
        connection = self._peer_connections.get(peer_id)
        if not connection:
            logger.warning(f"No connection for peer {peer_id}")
            return

        # Serialize RPC
        data = json.dumps(rpc.to_json_dict()).encode("utf-8")

        # Send with length prefix (varint)
        length_bytes = encode_varint(len(data))
        full_data = length_bytes + data

        # This would use the actual connection stream
        # await connection.write(full_data)
        logger.debug(f"Would send RPC to {peer_id}: {len(data)} bytes")

    async def _heartbeat_loop(self) -> None:
        """Heartbeat loop."""
        while self._running:
            try:
                control = self.router.heartbeat()

                if control.ihave or control.iwant or control.graft or control.prune:
                    rpc = RPC(control=control)
                    await self._send_rpc_to_peers(list(self.router.peers), rpc)

                await asyncio.sleep(self.router.config.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(self.router.config.heartbeat_interval)

    async def _get_next_message(self, topic: str) -> Optional[PubSubMessage]:
        """Get next message from topic queue (for subscription iteration)."""
        try:
            return await asyncio.wait_for(
                self._message_queues[topic].get(),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            return None

    def add_topic_handler(self, topic: str, handler: Callable[[PubSubMessage], Awaitable[None]]) -> None:
        """Add a message handler for a topic."""
        if topic not in self._topic_handlers:
            self._topic_handlers[topic] = []
        self._topic_handlers[topic].append(handler)

    def remove_topic_handler(self, topic: str, handler: Callable[[PubSubMessage], Awaitable[None]]) -> None:
        """Remove a message handler for a topic."""
        if topic in self._topic_handlers:
            self._topic_handlers[topic].remove(handler)


# ==================== FloodSub Router ====================

class FloodSubRouter:
    """FloodSub router - simple flooding implementation."""

    def __init__(self, peer_id: str, seen_ttl: float = 120.0):
        self.peer_id = peer_id
        self.my_topics: Set[str] = set()
        self.peers: Set[str] = set()
        self.peer_topics: Dict[str, Set[str]] = defaultdict(set)
        self.seen_cache = SeenCache(seen_ttl)

    def add_peer(self, peer_id: str) -> None:
        self.peers.add(peer_id)

    def remove_peer(self, peer_id: str) -> None:
        self.peers.discard(peer_id)
        self.peer_topics.pop(peer_id, None)

    def handle_subscription(self, peer_id: str, sub: SubOpts) -> None:
        if sub.subscribe:
            self.peer_topics[peer_id].add(sub.topicid)
        else:
            self.peer_topics[peer_id].discard(sub.topicid)

    def join_topic(self, topic: str) -> None:
        self.my_topics.add(topic)

    def leave_topic(self, topic: str) -> None:
        self.my_topics.discard(topic)

    def handle_message(self, msg: PubSubMessage, from_peer: str) -> bool:
        msg_id = msg.message_id()
        if self.seen_cache.seen(msg_id):
            return False
        return True

    def get_forward_targets(self, topic: str, from_peer: str) -> List[str]:
        targets = []
        for peer in self.peers:
            if topic in self.peer_topics[peer] and peer != from_peer:
                targets.append(peer)
        return targets


class FloodSub(PubSub):
    """FloodSub implementation - simple flooding."""

    def __init__(self, peer_id: str):
        self.peer_id = peer_id
        self.router = FloodSubRouter(peer_id)
        self._message_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        self._peer_connections: Dict[str, Any] = {}
        self._seqno = 0
        self._seqno_lock = asyncio.Lock()

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def subscribe(self, topic: str) -> Subscription:
        self.router.join_topic(topic)

        # Announce subscription
        sub = SubOpts(subscribe=True, topicid=topic)
        rpc = RPC(subscriptions=[sub])
        await self._send_rpc_to_peers(list(self.router.peers), rpc)

        return Subscription(topic=topic, pubsub=self)

    async def unsubscribe(self, topic: str) -> None:
        self.router.leave_topic(topic)

        # Announce unsubscription
        sub = SubOpts(subscribe=False, topicid=topic)
        rpc = RPC(subscriptions=[sub])
        await self._send_rpc_to_peers(list(self.router.peers), rpc)

        self._message_queues.pop(topic, None)

    async def publish(self, topic: str, data: bytes) -> None:
        async with self._seqno_lock:
            self._seqno += 1
            seqno_bytes = struct.pack(">Q", self._seqno)

        msg = PubSubMessage(
            from_peer=self.peer_id,
            data=data,
            seqno=seqno_bytes,
            topic=topic,
        )

        self.router.seen_cache.seen(msg.message_id())

        targets = self.router.get_forward_targets(topic, "")
        if targets:
            rpc = RPC(publish=[msg])
            await self._send_rpc_to_peers(targets, rpc)

    def list_peers(self, topic: str) -> List[str]:
        return [p for p in self.router.peers if topic in self.router.peer_topics[p]]

    def get_topics(self) -> List[str]:
        return list(self.router.my_topics)

    def add_peer(self, peer_id: str, connection: Any) -> None:
        self.router.add_peer(peer_id)
        self._peer_connections[peer_id] = connection

    def remove_peer(self, peer_id: str) -> None:
        self.router.remove_peer(peer_id)
        self._peer_connections.pop(peer_id, None)

    async def handle_rpc(self, rpc: RPC, from_peer: str) -> Optional[RPC]:
        for sub in rpc.subscriptions:
            self.router.handle_subscription(from_peer, sub)

        for msg in rpc.publish:
            if self.router.handle_message(msg, from_peer):
                forward_targets = self.router.get_forward_targets(msg.topic, from_peer)
                if forward_targets:
                    await self._send_rpc_to_peers(forward_targets, RPC(publish=[msg]))

                await self._message_queues[msg.topic].put(msg)

        return None

    async def _send_rpc_to_peers(self, peers: List[str], rpc: RPC) -> None:
        for peer in peers:
            if peer in self._peer_connections:
                try:
                    await self._send_rpc(peer, rpc)
                except Exception as e:
                    logger.error(f"Failed to send RPC to {peer}: {e}")

    async def _send_rpc(self, peer_id: str, rpc: RPC) -> None:
        connection = self._peer_connections.get(peer_id)
        if not connection:
            return

        data = json.dumps(rpc.to_json_dict()).encode("utf-8")
        length_bytes = encode_varint(len(data))
        full_data = length_bytes + data
        # await connection.write(full_data)
        logger.debug(f"Would send FloodSub RPC to {peer_id}: {len(data)} bytes")

    async def _get_next_message(self, topic: str) -> Optional[PubSubMessage]:
        try:
            return await asyncio.wait_for(
                self._message_queues[topic].get(),
                timeout=1.0
            )
        except asyncio.TimeoutError:
            return None


# ==================== Factory ====================

def create_pubsub(
    peer_id: str,
    protocol: str = PROTOCOL_ID_GOSSIPSUB,
    config: Optional[GossipSubConfig] = None,
) -> PubSub:
    """
    Create a PubSub instance.

    Args:
        peer_id: Local peer ID
        protocol: Protocol ID (default: GossipSub v1.1)
        config: Optional GossipSub configuration

    Returns:
        PubSub instance (GossipSub or FloodSub)
    """
    if protocol == PROTOCOL_ID_GOSSIPSUB:
        return GossipSub(peer_id, config)
    elif protocol == PROTOCOL_ID_FLOODSUB:
        return FloodSub(peer_id)
    else:
        raise ValueError(f"Unknown protocol: {protocol}")


# ==================== Protocol Handler ====================

class PubSubProtocolHandler:
    """Protocol handler for integrating PubSub with libp2p protocol negotiation."""

    def __init__(self, peer_id: str, config: Optional[GossipSubConfig] = None):
        self.peer_id = peer_id
        self.pubsub = create_pubsub(peer_id, PROTOCOL_ID_GOSSIPSUB, config)
        self._running = False

    @property
    def protocol_ids(self) -> List[str]:
        """Return supported protocol IDs."""
        return PROTOCOL_IDS

    async def start(self) -> None:
        """Start the PubSub handler."""
        await self.pubsub.start()
        self._running = True

    async def stop(self) -> None:
        """Stop the PubSub handler."""
        await self.pubsub.stop()
        self._running = False

    async def handle_stream(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming stream."""
        peer_id = writer.get_extra_info("peername", ("unknown", 0))[0]

        # Read length prefix
        length = 0
        shift = 0
        while True:
            byte = await reader.readexactly(1)
            b = ord(byte)
            length |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7

        # Read RPC data
        data = await reader.readexactly(length)

        # Parse RPC
        try:
            rpc_dict = json.loads(data.decode("utf-8"))
            rpc = RPC.from_json_dict(rpc_dict)

            # Handle RPC
            response = await self.pubsub.handle_rpc(rpc, peer_id)

            # Send response if any
            if response:
                response_data = json.dumps(response.to_json_dict()).encode("utf-8")
                response_length = encode_varint(len(response_data))
                writer.write(response_length + response_data)
                await writer.drain()

        except Exception as e:
            logger.error(f"Error handling PubSub stream: {e}")

        finally:
            writer.close()
            await writer.wait_closed()


# ==================== Exports ====================


# ==================== Compatibility Aliases ====================

PubSubConfig = GossipSubConfig
Message = PubSubMessage
Topic = str  # Topic is just a string in this implementation
GOSSIPSUB_PROTOCOL_ID = PROTOCOL_ID_GOSSIPSUB
FLOODSUB_PROTOCOL_ID = PROTOCOL_ID_FLOODSUB


# ==================== Compatibility Aliases ====================

# Alias for GossipSubConfig
PubSubConfig = GossipSubConfig

# Alias for PubSubMessage
Message = PubSubMessage

# Topic is just a string
Topic = str

# Protocol ID aliases
GOSSIPSUB_PROTOCOL_ID = PROTOCOL_ID_GOSSIPSUB
FLOODSUB_PROTOCOL_ID = PROTOCOL_ID_FLOODSUB

__all__ = [
    # Protocol IDs
    "PROTOCOL_ID_GOSSIPSUB",
    "PROTOCOL_ID_FLOODSUB",
    "PROTOCOL_IDS",
    # Main classes
    "PubSub",
    "GossipSub",
    "FloodSub",
    "GossipSubConfig",
    "GossipSubRouter",
    "FloodSubRouter",
    # Data classes
    "PubSubMessage",
    "SubOpts",
    "RPC",
    "ControlMessage",
    "ControlIHave",
    "ControlIWant",
    "ControlGraft",
    "ControlPrune",
    "PeerInfoPB",
    "Subscription",
    "SignaturePolicy",
    # Factory
    "create_pubsub",
    "PubSubConfig",
    "Message",
    "Topic",
    "GOSSIPSUB_PROTOCOL_ID",
    "FLOODSUB_PROTOCOL_ID",
    # Handler
    "PubSubProtocolHandler",
]


# ==================== Configuration Aliases ====================



# ==================== Additional Aliases for Test Compatibility ====================

# Export aliases that tests expect


# Update __all__ to include these aliases
__all__.extend([
    "Message", 
    "Topic",
])
