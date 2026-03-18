"""
P2P Engine - 运营商差异化穿透模块

基于专家架构设计的 P2P 网络穿透模块
支持全球主流运营商和网络环境
"""

from .types import (
    # 区域和运营商
    Region,
    ISP,

    # 设备厂商
    DeviceVendor,

    # NAT 相关
    NATType,
    NATInfo,

    # 网络环境
    NetworkEnvironment,

    # 连接状态
    ConnectionState,
    ConnectionType,
    ConnectionResult,

    # 事件
    Event,
    EventType,

    # 对端信息
    PeerInfo,
)

from .config import ConfigLoader, DEFAULT_CONFIG, ISPProfile, get_isp_profile

from .event import (
    EventBus,
    EventTopic,
    P2PEvent,
    P2PEventType,
    EventBuilder,
    get_global_event_bus,
)

# Try to import identify protocol if it exists
try:
    from .protocol import (
        IdentifyMessage,
        IdentifyProtocol,
        IdentifyExtension,
        PROTOCOL_ID,
        PROTOCOL_PUSH_ID,
    )
    _has_identify = True
except ImportError:
    _has_identify = False

# Try to import muxer if it exists
try:
    from .muxer import (
        YamuxSession,
        YamuxStream,
        YamuxConfig,
        YamuxFrame,
        FrameType,
        FrameFlag,
        GoAwayCode,
    )
    _has_muxer = True
except ImportError:
    _has_muxer = False

# Try to import transport if it exists
try:
    from .transport import (
        Transport,
        Connection,
        Listener,
        TransportError,
        WebRTCTransport,
        WebRTCConnection,
        WebRTCListener,
    )
    _has_transport = True
except ImportError:
    _has_transport = False

__all__ = [
    # Types
    "Region",
    "ISP",
    "DeviceVendor",
    "NATType",
    "NATInfo",
    "NetworkEnvironment",
    "ConnectionState",
    "ConnectionType",
    "ConnectionResult",
    "Event",
    "EventType",
    "PeerInfo",

    # Config
    "ConfigLoader",
    "DEFAULT_CONFIG",
    "ISPProfile",
    "get_isp_profile",

    # Event
    "EventBus",
    "EventTopic",
    "P2PEvent",
    "P2PEventType",
    "EventBuilder",
    "get_global_event_bus",
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

# Add muxer exports if available
if _has_muxer:
    __all__.extend([
        "YamuxSession",
        "YamuxStream",
        "YamuxConfig",
        "YamuxFrame",
        "FrameType",
        "FrameFlag",
        "GoAwayCode",
    ])

# Add transport exports if available
if _has_transport:
    __all__.extend([
        "Transport",
        "Connection",
        "Listener",
        "TransportError",
        "WebRTCTransport",
        "WebRTCConnection",
        "WebRTCListener",
    ])

__version__ = "2.0.0"
