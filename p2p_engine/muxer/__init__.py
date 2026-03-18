"""
P2P 流复用模块

支持多种流复用协议：yamux, mplex
"""

from .yamux import (
    YamuxSession,
    YamuxStream,
    YamuxConfig,
    YamuxFrame,
    FrameType,
    FrameFlag,
    GoAwayCode,
)

from .mplex_adapter import (
    MplexMuxerAdapter,
    MplexMuxedSession,
    MplexMuxedStream,
)

from .mplex import (
    MplexSession,
    MplexStream,
    MplexFrame,
    MplexFlag,
    write_uvarint,
    read_uvarint,
    PROTOCOL_STRING as MPLEX_PROTOCOL_STRING,
    MPLEX_PROTOCOL_ID,
    encode_uvarint,
    decode_uvarint,
    MplexError,
    MplexProtocolError,
    MplexClosedError,
    MplexStreamClosed,
    MplexStreamReset,
    MplexWindowExceeded,
)

__all__ = [
    # Yamux
    "YamuxSession",
    "YamuxStream",
    "YamuxConfig",
    "YamuxFrame",
    "FrameType",
    "FrameFlag",
    "GoAwayCode",
    # Mplex
    "MplexSession",
    "MplexStream",
    "MplexFrame",
    "MplexFlag",
    "write_uvarint",
    "read_uvarint",
    "encode_uvarint",
    "decode_uvarint",
    "MPLEX_PROTOCOL_STRING",
    "MPLEX_PROTOCOL_ID",
    "MplexError",
    "MplexProtocolError",
    "MplexClosedError",
    "MplexStreamClosed",
    "MplexStreamReset",
    "MplexWindowExceeded",
    # Mplex Adapter
    "MplexMuxerAdapter",
    "MplexMuxedSession",
    "MplexMuxedStream",
]
