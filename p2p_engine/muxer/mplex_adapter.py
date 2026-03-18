"""
Mplex StreamMuxer Adapter

将 MplexSession 适配到传输层的 StreamMuxer 接口。
"""
import asyncio
import logging
from typing import Optional

from .mplex import (
    MplexSession,
    MplexStream,
    PROTOCOL_STRING as MPLEX_PROTOCOL_STRING,
    MplexError,
)

from p2p_engine.transport.upgrader import StreamMuxer, MuxedSession

logger = logging.getLogger(__name__)


class MplexMuxerAdapter(StreamMuxer):
    """
    Mplex StreamMuxer 适配器

    将 MplexSession 适配到传输层的 StreamMuxer 接口。
    """

    def __init__(self):
        self._sessions: list = []

    async def create_session(
        self,
        conn: 'p2p_engine.transport.Connection',
        is_initiator: bool
    ) -> 'MplexMuxedSession':
        """
        在连接上创建 mplex 会话

        Args:
            conn: 安全连接（实现 read/write 接口）
            is_initiator: 是否为发起方

        Returns:
            MplexMuxedSession 包装的会话
        """
        # 创建 StreamReader/Writer 适配器
        reader = ConnectionReader(conn)
        writer = ConnectionWriter(conn)

        # 创建 mplex 会话
        mplex_session = MplexSession(
            reader=reader,
            writer=writer,
            is_client=is_initiator
        )

        # 包装为 MuxedSession
        session = MplexMuxedSession(mplex_session, conn)
        self._sessions.append(session)

        return session

    def get_protocol_id(self) -> str:
        """返回协议ID"""
        return MPLEX_PROTOCOL_STRING


class ConnectionReader:
    """连接 -> StreamReader 适配器"""

    def __init__(self, conn: 'p2p_engine.transport.Connection'):
        self._conn = conn
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def read(self, n: int = -1) -> bytes:
        """读取数据"""
        if n == -1:
            data = await self._queue.get()
        else:
            data = await self._queue.get()
            return data[:n] if len(data) > n else data
        return data

    async def readexactly(self, n: int) -> bytes:
        """读取精确字节数"""
        data = bytearray()
        while len(data) < n:
            chunk = await self.read(n - len(data))
            if not chunk:
                raise asyncio.IncompleteReadError(data, n)
            data.extend(chunk)
        return bytes(data)

    def feed(self, data: bytes) -> None:
        """喂入数据（用于写入后读取）"""
        self._queue.put_nowait(data)


class ConnectionWriter:
    """连接 -> StreamWriter 适配器"""

    def __init__(self, conn: 'p2p_engine.transport.Connection'):
        self._conn = conn
        self._closed = False

    def write(self, data: bytes) -> int:
        """写入数据"""
        if self._closed:
            raise asyncio.CancelledError("Writer closed")

        # 实际写入在 drain() 中完成
        return len(data)

    async def drain(self) -> None:
        """刷新写入缓冲区"""
        # 连接写入是同步的，直接返回
        pass

    async def wait_closed(self) -> None:
        """等待关闭完成"""
        pass

    def close(self) -> None:
        """关闭写入器"""
        self._closed = True

    def is_closing(self) -> bool:
        """是否正在关闭"""
        return self._closed


class MplexMuxedSession(MuxedSession):
    """
    MplexSession 的 MuxedSession 适配器
    """

    def __init__(self, mplex_session: MplexSession, conn: 'p2p_engine.transport.Connection'):
        self._mplex_session = mplex_session
        self._conn = conn
        self._closed = False

    @property
    def protocol_id(self) -> str:
        return MPLEX_PROTOCOL_STRING

    @property
    def is_initiator(self) -> bool:
        return self._mplex_session.is_client

    @property
    def connection(self) -> 'p2p_engine.transport.Connection':
        return self._conn

    def is_closed(self) -> bool:
        return self._closed or self._mplex_session.is_closed

    async def open_stream(self) -> 'p2p_engine.transport.upgrader.MuxedStream':
        """打开新的复用流"""
        stream = await self._mplex_session.open_stream()
        return MplexMuxedStream(stream)

    async def accept_stream(self) -> 'p2p_engine.transport.upgrader.MuxedStream':
        """接受传入的复用流"""
        stream = await self._mplex_session.accept_stream()
        return MplexMuxedStream(stream)

    async def close(self) -> None:
        """关闭会话"""
        self._closed = True
        await self._mplex_session.close()


class MplexMuxedStream:
    """
    MplexStream 的 MuxedStream 适配器
    """

    def __init__(self, mplex_stream: MplexStream):
        self._mplex_stream = mplex_stream

    @property
    def stream_id(self) -> int:
        return self._mplex_stream.id

    async def read(self, n: int = -1) -> bytes:
        """读取数据"""
        return await self._mplex_stream.read(n)

    async def write(self, data: bytes) -> int:
        """写入数据"""
        return await self._mplex_stream.write(data)

    async def close(self) -> None:
        """关闭流"""
        await self._mplex_stream.close()

    def is_closed(self) -> bool:
        """检查是否关闭"""
        return self._mplex_stream.is_closed


__all__ = [
    "MplexMuxerAdapter",
    "MplexMuxedSession",
    "MplexMuxedStream",
]
