"""
Transport Layer - 传输层抽象

提供统一的传输层接口，支持多种传输协议：
- TCP (内置)
- UDP (内置)
- QUIC
- WebRTC
- WebTransport
"""

from .base import (
    # 抽象基类
    Transport,
    Listener,
    Connection,

    # 异常
    TransportError,
    ConnectionError,
    ListenerError,
)

from .upgrader import (
    # 安全传输接口
    SecurityTransport,
    SecureConnection,

    # 流复用接口
    StreamMuxer,
    MuxedStream,
    MuxedSession,

    # 传输升级器
    TransportUpgrader,

    # 升级后的连接
    UpgradedConnection,
)

from .manager import (
    # 传输管理器
    TransportManager,
    TransportBuilder,
    create_transport_manager,

    # 异常
    DialError,
    ListenError,
)

# 尝试导入 WebRTC 传输
try:
    from .webrtc import (
        WebRTCTransport,
        WebRTCConnection,
        WebRTCListener,
        SignalingMessage,
        SignalingMessageType,
        ICEServer,
        PROTOCOL_ID as WEBRTC_PROTOCOL_ID,
        HAS_AIORTC,
    )
    _has_webrtc = True
except ImportError:
    _has_webrtc = False
    HAS_AIORTC = False

# 尝试导入 WebTransport 传输
try:
    from .webtransport import (
        WebTransportTransport,
        WebTransportConnection,
        WebTransportListener,
        PROTOCOL_ID as WEBTRANSPORT_PROTOCOL_ID,
        HAS_AIOQUIC,
    )
    _has_webtransport = True
except ImportError:
    _has_webtransport = False
    HAS_AIOQUIC = False

# 尝试导入 QUIC 传输
try:
    from .quic import (
        QUICTransport,
        QUICConnection,
        QUICListener,
        QUICStream,
        QuicStreamType,
        QuicProtocolFactory,
        PROTOCOL_ID as QUIC_PROTOCOL_ID,
        HAS_AIOQUIC,
        create_quic_transport,
        is_quic_available,
    )
    _has_quic = True
except ImportError:
    _has_quic = False
    HAS_AIOQUIC = False

__all__ = [
    # 抽象基类
    "Transport",
    "Listener",
    "Connection",

    # 异常
    "TransportError",
    "ConnectionError",
    "ListenerError",
    "DialError",
    "ListenError",

    # 安全传输接口
    "SecurityTransport",
    "SecureConnection",

    # 流复用接口
    "StreamMuxer",
    "MuxedStream",
    "MuxedSession",

    # 传输升级器
    "TransportUpgrader",
    "UpgradedConnection",

    # 传输管理器
    "TransportManager",
    "TransportBuilder",
    "create_transport_manager",

    # WebRTC
    "WebRTCTransport",
    "WebRTCConnection",
    "WebRTCListener",
    "SignalingMessage",
    "SignalingMessageType",
    "ICEServer",
    "WEBRTC_PROTOCOL_ID",
    "HAS_AIORTC",

    # WebTransport
    "WebTransportTransport",
    "WebTransportConnection",
    "WebTransportListener",
    "WEBTRANSPORT_PROTOCOL_ID",
    "HAS_AIOQUIC",

    # QUIC
    "QUICTransport",
    "QUICConnection",
    "QUICListener",
    "QUICStream",
    "QuicStreamType",
    "QuicProtocolFactory",
    "QUIC_PROTOCOL_ID",
    "create_quic_transport",
    "is_quic_available",
]
