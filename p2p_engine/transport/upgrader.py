"""
Transport Upgrader - 传输升级器

负责将原始传输连接升级为支持安全通道和流复用的完整连接。

升级流程:
Raw Connection → Security Connection → Muxed Connection
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Any, Callable, Awaitable

from .base import Connection, TransportError

logger = logging.getLogger("p2p_engine.transport.upgrader")


class SecurityTransport(ABC):
    """安全传输抽象接口"""

    @abstractmethod
    async def secure_inbound(
        self,
        conn: Connection,
        peer_id: Optional[str] = None
    ) -> "SecureConnection":
        """
        作为接收方，升级入站连接为安全连接

        Args:
            conn: 原始连接
            peer_id: 可选的对等节点ID

        Returns:
            安全连接
        """
        pass

    @abstractmethod
    async def secure_outbound(
        self,
        conn: Connection,
        peer_id: str
    ) -> "SecureConnection":
        """
        作为发起方，升级出站连接为安全连接

        Args:
            conn: 原始连接
            peer_id: 目标对等节点ID

        Returns:
            安全连接
        """
        pass

    @abstractmethod
    def get_protocol_id(self) -> str:
        """返回协议ID"""
        pass


class StreamMuxer(ABC):
    """流复用器抽象接口"""

    @abstractmethod
    async def create_session(
        self,
        conn: Connection,
        is_initiator: bool
    ) -> "MuxedSession":
        """
        在连接上创建复用会话

        Args:
            conn: 安全连接
            is_initiator: 是否为发起方

        Returns:
            复用会话
        """
        pass

    @abstractmethod
    def get_protocol_id(self) -> str:
        """返回协议ID"""
        pass


class SecureConnection(Connection):
    """
    安全连接包装器

    包装已通过安全握手的连接，提供加密通信。
    """

    def __init__(self, inner: Connection, peer_id: str, protocol_id: str):
        self._inner = inner
        self._peer_id = peer_id
        self._protocol_id = protocol_id

    async def read(self, n: int = -1) -> bytes:
        return await self._inner.read(n)

    async def write(self, data: bytes) -> int:
        return await self._inner.write(data)

    async def close(self) -> None:
        await self._inner.close()

    def is_closed(self) -> bool:
        return self._inner.is_closed()

    @property
    def remote_address(self):
        return self._inner.remote_address

    @property
    def local_address(self):
        return self._inner.local_address

    @property
    def peer_id(self) -> str:
        """对等节点ID"""
        return self._peer_id

    @property
    def protocol_id(self) -> str:
        """使用的安全协议ID"""
        return self._protocol_id


class MuxedStream(Connection):
    """
    复用流

    在复用会话中的单个逻辑流。
    """

    def __init__(
        self,
        stream_id: int,
        read_stream: asyncio.StreamReader,
        write_stream: asyncio.StreamWriter
    ):
        self._stream_id = stream_id
        self._reader = read_stream
        self._writer = write_stream

    @property
    def stream_id(self) -> int:
        """流ID"""
        return self._stream_id

    async def read(self, n: int = -1) -> bytes:
        data = self._reader.read(n)
        if isinstance(data, bytes):
            return data
        # StreamReader.read() returns coroutine in some cases
        return await data

    async def write(self, data: bytes) -> int:
        self._writer.write(data)
        await self._writer.drain()
        return len(data)

    async def close(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()

    def is_closed(self) -> bool:
        return self._writer.is_closing()

    @property
    def remote_address(self):
        return None

    @property
    def local_address(self):
        return None


class MuxedSession:
    """
    复用会话

    管理多个复用流。
    """

    def __init__(
        self,
        conn: Connection,
        protocol_id: str,
        is_initiator: bool
    ):
        self._conn = conn
        self._protocol_id = protocol_id
        self._is_initiator = is_initiator
        self._streams: dict[int, MuxedStream] = {}
        self._next_stream_id = 1 if is_initiator else 2
        self._closed = False
        self._lock = asyncio.Lock()
        self._incoming_queue: asyncio.Queue[MuxedStream] = asyncio.Queue()
        self._accept_timeout = 30.0

    @property
    def protocol_id(self) -> str:
        return self._protocol_id

    @property
    def is_initiator(self) -> bool:
        return self._is_initiator

    @property
    def connection(self) -> Connection:
        return self._conn

    def is_closed(self) -> bool:
        return self._closed

    async def open_stream(self) -> MuxedStream:
        """打开新的复用流"""
        async with self._lock:
            if self._closed:
                raise TransportError("Session is closed")

            stream_id = self._next_stream_id
            self._next_stream_id += 2

            # 创建流
            reader = asyncio.StreamReader()
            stream = MuxedStream(stream_id, reader, asyncio.StreamWriter())
            self._streams[stream_id] = stream
            return stream

    async def accept_stream(self) -> MuxedStream:
        """
        接受传入的复用流

        等待并返回下一个传入的流。此方法会阻塞直到有新流到达
        或会话关闭。

        Returns:
            传入的复用流

        Raises:
            TransportError: 如果会话已关闭
        """
        while not self._closed:
            try:
                stream = await asyncio.wait_for(
                    self._incoming_queue.get(),
                    timeout=1.0
                )
                return stream
            except asyncio.TimeoutError:
                # 继续等待，除非会话已关闭
                if self._closed:
                    raise TransportError("Session is closed")
                continue
            except asyncio.CancelledError:
                # 任务被取消，优雅退出
                raise TransportError("Accept stream cancelled")

        raise TransportError("Session is closed")

    async def _handle_incoming_stream(self, stream_id: int) -> MuxedStream:
        """
        处理传入流，由复用器协议调用

        Args:
            stream_id: 流ID

        Returns:
            创建的传入流
        """
        async with self._lock:
            if self._closed:
                raise TransportError("Session is closed")

            # 创建传入流
            reader = asyncio.StreamReader()
            stream = MuxedStream(stream_id, reader, asyncio.StreamWriter())
            self._streams[stream_id] = stream

            # 通知 accept_stream 等待者
            await self._incoming_queue.put(stream)

            logger.debug(f"Accepted incoming stream: {stream_id}")
            return stream

    async def close(self) -> None:
        """关闭会话"""
        async with self._lock:
            if self._closed:
                return

            self._closed = True

            # 关闭所有流
            for stream in list(self._streams.values()):
                try:
                    await stream.close()
                except Exception:
                    pass

            self._streams.clear()

            # 清理传入队列，唤醒等待的 accept_stream
            try:
                # 发送哨兵值唤醒等待者
                while not self._incoming_queue.empty():
                    self._incoming_queue.get_nowait()
            except Exception:
                pass

            # 关闭底层连接
            await self._conn.close()


class TransportUpgrader:
    """
    传输升级器

    负责将原始传输连接升级为支持安全通道和流复用的完整连接。
    """

    def __init__(
        self,
        security_transports: Optional[List[SecurityTransport]] = None,
        muxers: Optional[List[StreamMuxer]] = None
    ):
        """
        初始化传输升级器

        Args:
            security_transports: 支持的安全传输列表（按优先级排序）
            muxers: 支持的流复用器列表（按优先级排序）
        """
        self._security_transports = security_transports or []
        self._muxers = muxers or []
        self._upgrade_callbacks: List[Callable[[], Awaitable[None]]] = []

    def add_security_transport(self, transport: SecurityTransport) -> None:
        """添加安全传输"""
        self._security_transports.append(transport)

    def add_muxer(self, muxer: StreamMuxer) -> None:
        """添加流复用器"""
        self._muxers.append(muxer)

    def on_upgrade(self, callback: Callable[[], Awaitable[None]]) -> None:
        """注册升级完成回调"""
        self._upgrade_callbacks.append(callback)

    async def upgrade_inbound(
        self,
        conn: Connection,
        peer_id: Optional[str] = None
    ) -> "UpgradedConnection":
        """
        升级入站连接

        Args:
            conn: 原始连接
            peer_id: 可选的对等节点ID

        Returns:
            升级后的连接
        """
        logger.debug("Upgrading inbound connection")

        # 安全升级
        secure_conn = await self._upgrade_security_inbound(conn, peer_id)

        # 流复用升级
        muxed_session = await self._upgrade_muxer(secure_conn, is_initiator=False)

        # 触发回调
        for callback in self._upgrade_callbacks:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Upgrade callback error: {e}")

        return UpgradedConnection(secure_conn, muxed_session)

    async def upgrade_outbound(
        self,
        conn: Connection,
        peer_id: str
    ) -> "UpgradedConnection":
        """
        升级出站连接

        Args:
            conn: 原始连接
            peer_id: 目标对等节点ID

        Returns:
            升级后的连接
        """
        logger.debug(f"Upgrading outbound connection to {peer_id}")

        # 安全升级
        secure_conn = await self._upgrade_security_outbound(conn, peer_id)

        # 流复用升级
        muxed_session = await self._upgrade_muxer(secure_conn, is_initiator=True)

        # 触发回调
        for callback in self._upgrade_callbacks:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Upgrade callback error: {e}")

        return UpgradedConnection(secure_conn, muxed_session)

    async def _upgrade_security_inbound(
        self,
        conn: Connection,
        peer_id: Optional[str]
    ) -> SecureConnection:
        """入站安全升级"""
        if not self._security_transports:
            # 无安全传输，返回包装的连接
            return SecureConnection(
                conn,
                peer_id or "unknown",
                "/insecure/1.0.0"
            )

        last_error = None
        for security in self._security_transports:
            try:
                logger.debug(f"Attempting security upgrade: {security.get_protocol_id()}")
                return await security.secure_inbound(conn, peer_id)
            except Exception as e:
                logger.debug(f"Security upgrade failed: {security.get_protocol_id()}: {e}")
                last_error = e

        raise TransportError(
            f"All security transports failed. Last error: {last_error}"
        )

    async def _upgrade_security_outbound(
        self,
        conn: Connection,
        peer_id: str
    ) -> SecureConnection:
        """出站安全升级"""
        if not self._security_transports:
            return SecureConnection(conn, peer_id, "/insecure/1.0.0")

        last_error = None
        for security in self._security_transports:
            try:
                logger.debug(f"Attempting security upgrade: {security.get_protocol_id()}")
                return await security.secure_outbound(conn, peer_id)
            except Exception as e:
                logger.debug(f"Security upgrade failed: {security.get_protocol_id()}: {e}")
                last_error = e

        raise TransportError(
            f"All security transports failed. Last error: {last_error}"
        )

    async def _upgrade_muxer(
        self,
        conn: SecureConnection,
        is_initiator: bool
    ) -> MuxedSession:
        """流复用升级"""
        if not self._muxers:
            raise TransportError("No muxers available")

        last_error = None
        for muxer in self._muxers:
            try:
                logger.debug(f"Attempting muxer upgrade: {muxer.get_protocol_id()}")
                return await muxer.create_session(conn, is_initiator)
            except Exception as e:
                logger.debug(f"Muxer upgrade failed: {muxer.get_protocol_id()}: {e}")
                last_error = e

        raise TransportError(
            f"All muxers failed. Last error: {last_error}"
        )


class UpgradedConnection(Connection):
    """
    升级后的连接

    包含安全连接和复用会话的完整连接。
    """

    def __init__(
        self,
        secure_conn: SecureConnection,
        muxed_session: MuxedSession
    ):
        self._secure_conn = secure_conn
        self._muxed_session = muxed_session

    @property
    def secure_connection(self) -> SecureConnection:
        """安全连接"""
        return self._secure_conn

    @property
    def muxed_session(self) -> MuxedSession:
        """复用会话"""
        return self._muxed_session

    @property
    def peer_id(self) -> str:
        """对等节点ID"""
        return self._secure_conn.peer_id

    @property
    def security_protocol(self) -> str:
        """安全协议ID"""
        return self._secure_conn.protocol_id

    @property
    def muxer_protocol(self) -> str:
        """复用协议ID"""
        return self._muxed_session.protocol_id

    async def open_stream(self) -> MuxedStream:
        """打开新的复用流"""
        return await self._muxed_session.open_stream()

    async def accept_stream(self) -> MuxedStream:
        """接受传入的复用流"""
        return await self._muxed_session.accept_stream()

    async def read(self, n: int = -1) -> bytes:
        """直接从安全连接读取（不推荐，应使用流）"""
        return await self._secure_conn.read(n)

    async def write(self, data: bytes) -> int:
        """直接写入安全连接（不推荐，应使用流）"""
        return await self._secure_conn.write(data)

    async def close(self) -> None:
        """关闭连接"""
        await self._muxed_session.close()
        await self._secure_conn.close()

    def is_closed(self) -> bool:
        return self._secure_conn.is_closed()

    @property
    def remote_address(self):
        return self._secure_conn.remote_address

    @property
    def local_address(self):
        return self._secure_conn.local_address
