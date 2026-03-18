"""
P2P Protocol Implementations

This package contains protocol implementations for libp2p-compatible
peer-to-peer communication.

Protocols:
- multistream-select: Protocol negotiation (/multistream/1.0.0)
- identify: Peer identity exchange protocol (/ipfs/id/1.0.0)
- identify/push: Identity push protocol (/ipfs/id/push/1.0.0)
- noise: Secure channel handshake (/noise)
- dcutr: Direct Connection Upgrade through Relay (/libp2p/dcutr/1.0.0)
- ping: Ping protocol for liveness checks (/ipfs/ping/1.0.0)
- kademlia: Distributed Hash Table (/ipfs/kad/1.0.0)
- pubsub: PubSub with GossipSub v1.1 (/meshsub/1.1.0) and FloodSub (/floodsub/1.0.0)
"""

from .messages import (
    # Varint encoding/decoding
    encode_varint,
    decode_varint,
    # Message encoding/decoding
    encode_message,
    decode_message,
    decode_message_with_offset,
    # Constants
    MULTISTREAM_PROTOCOL_ID,
    NA_RESPONSE,
    # Protocol validation
    is_valid_protocol_id,
    is_multistream_protocol,
    is_na_response,
)

from .negotiator import (
    # Connection interface
    StreamReaderWriter,
    # Exceptions
    NegotiationError,
    ProtocolNotSupportedError,
    HandshakeError,
    # Negotiator
    ProtocolNegotiator,
    NegotiationResult,
)

# Try to import identify if it exists
try:
    from .identify import (
        IdentifyMessage,
        IdentifyProtocol,
        IdentifyExtension,
        PROTOCOL_ID,
        PROTOCOL_PUSH_ID,
    )
    _has_identify = True
except ImportError:
    _has_identify = False

# Try to import integration if it exists
try:
    from .integration import (
        ProtocolHandler,
        IdentifyHandler,
        ProtocolRegistry,
        ProtocolNegotiationClient,
        IdentifyClient,
        create_default_registry,
        create_identify_client,
    )
    _has_integration = True
except ImportError:
    _has_integration = False

# Try to import dcutr if it exists
try:
    from .dcutr import (
        DCUtRProtocol,
        DCUtRMessage,
        DCUtRMessageType,
        PROTOCOL_ID as DCUTR_PROTOCOL_ID,
        DEFAULT_MAX_RETRY_ATTEMPTS,
        DEFAULT_SYNC_TIMEOUT_MS,
    )
    _has_dcutr = True
except ImportError:
    _has_dcutr = False

# Try to import noise if it exists
try:
    from .noise import (
        NoiseSecurity,
        NoiseSecurityTransport,
        NoiseHandshake,
        HandshakeConfig,
        HandshakeResult,
        PROTOCOL_ID as NOISE_PROTOCOL_ID,
        PROTOCOL_NAME as NOISE_PROTOCOL_NAME,
        NoiseError,
        HandshakeError as NoiseHandshakeError,
        CryptoError,
        InvalidSignatureError,
    )
    _has_noise = True
except ImportError:
    _has_noise = False

# Try to import tls if it exists
try:
    from .tls import (
        TLSSecurity,
        TLSSecurityTransport,
        TLSConfig,
        TLSHandshakePayload,
        CertificateConfig,
        generate_self_signed_cert,
        generate_ed25519_keypair,
        create_tls_security,
        PROTOCOL_ID as TLS_PROTOCOL_ID,
        TLSError,
        TLSHandshakeError,
        TLSCertificateError,
        TLSVerificationError,
    )
    _has_tls = True
except ImportError:
    _has_tls = False

__all__ = [
    # Messages
    "encode_varint",
    "decode_varint",
    "encode_message",
    "decode_message",
    "decode_message_with_offset",
    "MULTISTREAM_PROTOCOL_ID",
    "NA_RESPONSE",
    "is_valid_protocol_id",
    "is_multistream_protocol",
    "is_na_response",
    # Negotiator
    "StreamReaderWriter",
    "NegotiationError",
    "ProtocolNotSupportedError",
    "HandshakeError",
    "ProtocolNegotiator",
    "NegotiationResult",
]

# Add identify exports if available
if _has_identify:
    __all__.extend([
        "IdentifyMessage",
        "IdentifyProtocol",
        "IdentifyExtension",
        "PROTOCOL_ID",
        "PROTOCOL_PUSH_ID",
    ])

# Add integration exports if available
if _has_integration:
    __all__.extend([
        "ProtocolHandler",
        "IdentifyHandler",
        "ProtocolRegistry",
        "ProtocolNegotiationClient",
        "IdentifyClient",
        "create_default_registry",
        "create_identify_client",
    ])

# Add dcutr exports if available
if _has_dcutr:
    __all__.extend([
        "DCUtRProtocol",
        "DCUtRMessage",
        "DCUtRMessageType",
        "DCUTR_PROTOCOL_ID",
        "DEFAULT_MAX_RETRY_ATTEMPTS",
        "DEFAULT_SYNC_TIMEOUT_MS",
    ])

# Add noise exports if available
if _has_noise:
    __all__.extend([
        "NoiseSecurity",
        "NoiseSecurityTransport",
        "NoiseHandshake",
        "HandshakeConfig",
        "HandshakeResult",
        "NOISE_PROTOCOL_ID",
        "NOISE_PROTOCOL_NAME",
        "NoiseError",
        "NoiseHandshakeError",
        "CryptoError",
        "InvalidSignatureError",
    ])

# Add tls exports if available
if _has_tls:
    __all__.extend([
        "TLSSecurity",
        "TLSSecurityTransport",
        "TLSConfig",
        "TLSHandshakePayload",
        "CertificateConfig",
        "generate_self_signed_cert",
        "generate_ed25519_keypair",
        "create_tls_security",
        "TLS_PROTOCOL_ID",
        "TLSError",
        "TLSHandshakeError",
        "TLSCertificateError",
        "TLSVerificationError",
    ])

# Try to import ping if it exists
try:
    from .ping import (
        PingProtocol,
        PingStats,
        PingConfig,
        PingMessage,
        ping_peer,
        serve_ping,
        PROTOCOL_ID as PING_PROTOCOL_ID_ORIG,
        PING_PROTOCOL_ID,
        PING_PAYLOAD_SIZE,
    )
    _has_ping = True
except ImportError:
    _has_ping = False

# Add ping exports if available
if _has_ping:
    __all__.extend([
        "PingProtocol",
        "PingStats",
        "PingConfig",
        "PingMessage",
        "ping_peer",
        "serve_ping",
        "PING_PROTOCOL_ID",
        "PING_PROTOCOL_ID_ORIG",
        "PING_PAYLOAD_SIZE",
    ])

# Try to import kademlia if it exists
try:
    from .kademlia import (
        KademliaProtocolHandler,
        create_kademlia_handler,
        find_peer_async,
        PROTOCOL_ID as KADEMLIA_PROTOCOL_ID,
    )
    _has_kademlia = True
except ImportError:
    _has_kademlia = False

# Add kademlia exports if available
if _has_kademlia:
    __all__.extend([
        "KademliaProtocolHandler",
        "create_kademlia_handler",
        "find_peer_async",
        "KADEMLIA_PROTOCOL_ID",
    ])

# Try to import pubsub if it exists
try:
    from .pubsub import (
        PubSub,
        GossipSub,
        FloodSub,
        GossipSubConfig,
        PubSubConfig,
        GossipSubRouter,
        FloodSubRouter,
        PubSubMessage,
        Message,
        Topic,
        SubOpts,
        RPC,
        ControlMessage,
        ControlIHave,
        ControlIWant,
        ControlGraft,
        ControlPrune,
        PeerInfoPB,
        Subscription,
        SignaturePolicy,
        create_pubsub,
        PubSubProtocolHandler,
        PROTOCOL_ID_GOSSIPSUB,
        PROTOCOL_ID_FLOODSUB,
        PROTOCOL_IDS,
        GOSSIPSUB_PROTOCOL_ID,
        FLOODSUB_PROTOCOL_ID,
    )
    _has_pubsub = True
except ImportError:
    _has_pubsub = False

# Add pubsub exports if available
if _has_pubsub:
    __all__.extend([
        "PubSub",
        "GossipSub",
        "FloodSub",
        "GossipSubConfig",
        "PubSubConfig",
        "GossipSubRouter",
        "FloodSubRouter",
        "PubSubMessage",
        "Message",
        "Topic",
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
        "create_pubsub",
        "PubSubProtocolHandler",
        "PROTOCOL_ID_GOSSIPSUB",
        "PROTOCOL_ID_FLOODSUB",
        "PROTOCOL_IDS",
        "GOSSIPSUB_PROTOCOL_ID",
        "FLOODSUB_PROTOCOL_ID",
    ])
