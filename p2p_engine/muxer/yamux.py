"""
Yamux 流复用协议实现

基于 libp2p yamux 规范: https://github.com/hashicorp/yamux/blob/master/spec.md

协议字符串: /yamux/1.0.0

特性:
- 多路复用: 在单个连接上复用多个逻辑流
- 背压: 基于窗口的流控制
- 半关闭: 支持流的一端关闭而另一端继续发送
"""

import asyncio
import struct
import logging
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import Optional, Dict, Callable, Awaitable, Tuple
from collections import deque

logger = logging.getLogger("p2p_engine.muxer.yamux")


# ==================== 常量定义 ====================

PROTOCOL_STRING = "/yamux/1.0.0"
VERSION = 0
HEADER_SIZE = 12

# 窗口大小
DEFAULT_WINDOW_SIZE = 256 * 1024  # 256KB
MAX_WINDOW_SIZE = 16 * 1024 * 1024  # 16MB

# 流ID分配
INITIAL_CLIENT_STREAM_ID = 1
INITIAL_SERVER_STREAM_ID = 2
STREAM_ID_INCREMENT = 2

# 缓冲区大小
STREAM_BUFFER_SIZE = 64 * 1024  # 64KB

# 最大未确认流数量
MAX_UNACKED_STREAMS = 256

# 连接配置
DEFAULT_CONNECTION_TIMEOUT = 30.0
DEFAULT_KEEPALIVE_INTERVAL = 30.0


# ==================== 帧类型枚举 ====================

class FrameType(IntEnum):
    """Yamux 帧类型"""
    DATA = 0x0          # 数据帧
    WINDOW_UPDATE = 0x1 # 窗口更新
    PING = 0x2          # Ping
    GO_AWAY = 0x3       # 会话终止


# ==================== 帧标志枚举 ====================

class FrameFlag(IntFlag):
    """Yamux 帧标志"""
    SYN = 0x1  # 新流开始
    ACK = 0x2  # 确认新流
    FIN = 0x4  # 半关闭
    RST = 0x8  # 立即重置流


# ==================== GoAway 错误码 ====================

class GoAwayCode(IntEnum):
    """会话终止错误码"""
    NORMAL = 0x0      # 正常终止
    PROTOCOL_ERROR = 0x1  # 协议错误
    INTERNAL_ERROR = 0x2  # 内部错误


# ==================== 流状态 ====================

class StreamState(IntEnum):
    """流状态"""
    INIT = 0          # 初始化
    SYN_SENT = 1      # SYN 已发送
    SYN_RECEIVED = 2  # SYN 已接收
    ESTABLISHED = 3   # 已建立
    LOCAL_CLOSE = 4   # 本地已关闭
    REMOTE_CLOSE = 5  # 远程已关闭
    CLOSED = 6        # 已关闭
    RESET = 7         # 已重置


# ==================== 帧数据结构 ====================

@dataclass
class YamuxFrame:
    """Yamux 帧结构"""
    version: int = VERSION
    type: FrameType = FrameType.DATA
    flags: int = 0
    stream_id: int = 0
    length: int = 0
    data: bytes = b""

    def pack(self) -> bytes:
        """打包帧为字节"""
        header = struct.pack(
            ">BBHII",
            self.version,
            self.type,
            self.flags,
            self.stream_id,
            self.length
        )
        return header + self.data

    @classmethod
    def unpack(cls, data: bytes) -> 'YamuxFrame':
        """从字节解包帧"""
        if len(data) < HEADER_SIZE:
            raise ValueError(f"帧数据过短: {len(data)} < {HEADER_SIZE}")

        version, type_val, flags, stream_id, length = struct.unpack(">BBHII", data[:HEADER_SIZE])

        frame = cls(
            version=version,
            type=FrameType(type_val),
            flags=flags,
            stream_id=stream_id,
            length=length,
            data=data[HEADER_SIZE:HEADER_SIZE + length] if len(data) > HEADER_SIZE else b""
        )

        return frame

    def has_flag(self, flag: FrameFlag) -> bool:
        """检查是否包含指定标志"""
        return (self.flags & flag) != 0

    def add_flag(self, flag: FrameFlag) -> None:
        """添加标志"""
        self.flags |= flag

    def __repr__(self) -> str:
        flags_str = []
        if self.has_flag(FrameFlag.SYN):
            flags_str.append("SYN")
        if self.has_flag(FrameFlag.ACK):
            flags_str.append("ACK")
        if self.has_flag(FrameFlag.FIN):
            flags_str.append("FIN")
        if self.has_flag(FrameFlag.RST):
            flags_str.append("RST")

        return (f"YamuxFrame(type={self.type.name}, "
                f"flags={'|'.join(flags_str) if flags_str else '0'}, "
                f"stream_id={self.stream_id}, length={self.length})")


# ==================== 配置 ====================

@dataclass
class YamuxConfig:
    """Yamux 配置"""
    window_size: int = DEFAULT_WINDOW_SIZE
    max_window_size: int = MAX_WINDOW_SIZE
    max_unacked_streams: int = MAX_UNACKED_STREAMS
    connection_timeout: float = DEFAULT_CONNECTION_TIMEOUT
    keepalive_interval: float = DEFAULT_KEEPALIVE_INTERVAL
    accept_backlog: int = 256
    buffer_size: int = STREAM_BUFFER_SIZE


# ==================== 异常 ====================

class YamuxError(Exception):
    """Yamux 基础异常"""
    pass


class YamuxProtocolError(YamuxError):
    """协议错误"""
    pass


class YamuxClosedError(YamuxError):
    """会话已关闭"""
    pass


class YamuxStreamReset(YamuxError):
    """流被重置"""
    pass


class YamuxStreamClosed(YamuxError):
    """流已关闭"""
    pass


class YamuxWindowExceeded(YamuxError):
    """窗口溢出"""
    pass


# ==================== Yamux 流 ====================

class YamuxStream:
    """
    Yamux 逻辑流

    实现:
    - 读写操作
    - 半关闭
    - 流控
    - 重置
    """

    def __init__(
        self,
        stream_id: int,
        session: 'YamuxSession',
        is_initiator: bool = False,
        config: Optional[YamuxConfig] = None
    ):
        self._id = stream_id
        self._session = session
        self._is_initiator = is_initiator
        self._config = config or YamuxConfig()

        # 状态
        self._state = StreamState.INIT
        self._read_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()

        # 接收窗口 (远程发送给我们的数据)
        self._recv_window = self._config.window_size
        self._recv_buffer = bytearray()
        self._recv_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()

        # 发送窗口 (我们发送给远程的数据)
        self._send_window = self._config.window_size
        self._send_window_update = asyncio.Event()

        # 关闭标志
        self._local_closed = False
        self._remote_closed = False
        self._reset = False

        # 等待建立
        self._established = asyncio.Event()

    @property
    def id(self) -> int:
        return self._id

    @property
    def state(self) -> StreamState:
        return self._state

    @property
    def is_closed(self) -> bool:
        return self._state in (StreamState.CLOSED, StreamState.RESET)

    @property
    def is_established(self) -> bool:
        return self._state == StreamState.ESTABLISHED

    async def read(self, n: int = -1) -> bytes:
        """
        读取流数据

        Args:
            n: 读取字节数，-1 表示读取所有可用数据

        Returns:
            读取的数据

        Raises:
            YamuxStreamClosed: 流已关闭
            YamuxStreamReset: 流被重置
        """
        async with self._read_lock:
            if self._reset:
                raise YamuxStreamReset("流已被重置")

            if self._remote_closed and not self._recv_buffer:
                return b""

            data = bytearray()

            if n < 0:
                # 读取所有可用数据
                while True:
                    if self._recv_buffer:
                        data.extend(self._recv_buffer)
                        self._recv_buffer.clear()

                    if self._remote_closed:
                        break

                    try:
                        chunk = await asyncio.wait_for(
                            self._recv_queue.get(),
                            timeout=0.1
                        )
                        if chunk is None:
                            break
                        data.extend(chunk)
                    except asyncio.TimeoutError:
                        if data:
                            break
                        continue
            else:
                # 读取指定字节数
                while len(data) < n:
                    if self._recv_buffer:
                        needed = n - len(data)
                        available = len(self._recv_buffer)
                        to_read = min(needed, available)
                        data.extend(self._recv_buffer[:to_read])
                        del self._recv_buffer[:to_read]
                        continue

                    if self._remote_closed:
                        break

                    try:
                        chunk = await asyncio.wait_for(
                            self._recv_queue.get(),
                            timeout=0.1
                        )
                        if chunk is None:
                            break
                        self._recv_buffer.extend(chunk)
                    except asyncio.TimeoutError:
                        if data:
                            break
                        continue

            # 发送窗口更新
            if data:
                await self._send_window_update_internal(len(data))

            return bytes(data)

    async def write(self, data: bytes) -> int:
        """
        写入流数据

        Args:
            data: 要写入的数据

        Returns:
            写入的字节数

        Raises:
            YamuxStreamClosed: 流已关闭
            YamuxStreamReset: 流被重置
            YamuxWindowExceeded: 发送窗口已满
        """
        async with self._write_lock:
            if self._reset:
                raise YamuxStreamReset("流已被重置")

            if self._local_closed:
                raise YamuxStreamClosed("本地已关闭")

            if not data:
                return 0

            # 等待流建立
            if not self._established.is_set():
                await self._established.wait()

            written = 0
            total_len = len(data)
            offset = 0

            while offset < total_len:
                # 等待窗口
                while self._send_window <= 0:
                    if self._reset or self._local_closed:
                        raise YamuxStreamClosed("写入时流已关闭")
                    self._send_window_update.clear()
                    await self._send_window_update.wait()

                # 计算可发送大小
                chunk_size = min(self._send_window, total_len - offset)
                chunk = data[offset:offset + chunk_size]

                # 发送数据帧
                frame = YamuxFrame(
                    type=FrameType.DATA,
                    stream_id=self._id,
                    length=len(chunk),
                    data=chunk
                )
                await self._session._send_frame(frame)

                # 更新状态
                self._send_window -= len(chunk)
                offset += chunk_size
                written = offset

            return written

    async def close(self) -> None:
        """
        半关闭流 (关闭写端)

        发送 FIN 标志表示不再发送数据，但仍可接收。
        """
        async with self._write_lock:
            if self._local_closed:
                return

            self._local_closed = True

            frame = YamuxFrame(
                type=FrameType.DATA,
                flags=FrameFlag.FIN,
                stream_id=self._id,
                length=0
            )
            await self._session._send_frame(frame)

            # 检查是否完全关闭
            if self._remote_closed:
                self._state = StreamState.CLOSED

    async def reset(self) -> None:
        """
        立即重置流

        发送 RST 标志立即关闭流，丢弃所有缓冲数据。
        """
        self._reset = True
        self._state = StreamState.RESET

        frame = YamuxFrame(
            type=FrameType.DATA,
            flags=FrameFlag.RST,
            stream_id=self._id,
            length=0
        )
        await self._session._send_frame(frame)

        # 清空接收队列
        while not self._recv_queue.empty():
            try:
                self._recv_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # 通知等待的读者
        await self._recv_queue.put(None)

    async def _handle_data(self, frame: YamuxFrame) -> None:
        """处理接收到的数据帧"""
        if self._reset:
            return

        if frame.has_flag(FrameFlag.RST):
            self._reset = True
            self._state = StreamState.RESET
            await self._recv_queue.put(None)
            return

        if frame.has_flag(FrameFlag.FIN):
            self._remote_closed = True
            self._state = StreamState.LOCAL_CLOSE if self._local_closed else StreamState.REMOTE_CLOSE
            await self._recv_queue.put(None)
            return

        if frame.data:
            self._recv_window -= len(frame.data)
            await self._recv_queue.put(frame.data)

    async def _handle_window_update(self, frame: YamuxFrame) -> None:
        """处理窗口更新"""
        delta = frame.length
        self._send_window += delta
        self._send_window_update.set()

    async def _send_window_update_internal(self, delta: int) -> None:
        """发送窗口更新"""
        frame = YamuxFrame(
            type=FrameType.WINDOW_UPDATE,
            stream_id=self._id,
            length=delta
        )
        await self._session._send_frame(frame)
        self._recv_window += delta

    def _set_state(self, state: StreamState) -> None:
        """设置流状态"""
        self._state = state
        if state == StreamState.ESTABLISHED:
            self._established.set()


# ==================== Yamux 会话 ====================

class YamuxSession:
    """
    Yamux 会话

    管理 yamux 连接上的多个逻辑流。

    功能:
    - 打开新流
    - 接受入站流
    - 处理帧
    - 流控管理
    - 会话关闭
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        is_client: bool = True,
        config: Optional[YamuxConfig] = None
    ):
        self._reader = reader
        self._writer = writer
        self._is_client = is_client
        self._config = config or YamuxConfig()

        # 流管理
        self._streams: Dict[int, YamuxStream] = {}
        self._streams_lock = asyncio.Lock()

        # 流ID分配
        self._next_stream_id = INITIAL_CLIENT_STREAM_ID if is_client else INITIAL_SERVER_STREAM_ID
        self._stream_id_lock = asyncio.Lock()

        # 接受队列
        self._accept_queue: asyncio.Queue[YamuxStream] = asyncio.Queue(
            maxsize=self._config.accept_backlog
        )

        # 未确认流计数
        self._unacked_streams = 0

        # 会话状态
        self._closed = False
        self._close_lock = asyncio.Lock()
        self._goaway_code: Optional[GoAwayCode] = None

        # Ping处理
        self._pending_pings: Dict[int, asyncio.Future] = {}
        self._ping_counter = 0
        self._ping_lock = asyncio.Lock()

        # 读取循环任务
        self._read_task: Optional[asyncio.Task] = None
        self._keepalive_task: Optional[asyncio.Task] = None

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def is_client(self) -> bool:
        return self._is_client

    @classmethod
    async def create_client(
        cls,
        host: str,
        port: int,
        config: Optional[YamuxConfig] = None
    ) -> 'YamuxSession':
        """创建客户端会话"""
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=config.connection_timeout if config else DEFAULT_CONNECTION_TIMEOUT
        )
        session = cls(reader, writer, is_client=True, config=config)
        session._start_read_loop()
        session._start_keepalive()
        return session

    @classmethod
    def create_server_session(
        cls,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        config: Optional[YamuxConfig] = None
    ) -> 'YamuxSession':
        """创建服务端会话"""
        session = cls(reader, writer, is_client=False, config=config)
        session._start_read_loop()
        session._start_keepalive()
        return session

    async def open_stream(self) -> YamuxStream:
        """
        打开新流

        发送 SYN 标志初始化新流。

        Returns:
            新的 YamuxStream 实例

        Raises:
            YamuxClosedError: 会话已关闭
            YamuxProtocolError: 协议错误
        """
        if self._closed:
            raise YamuxClosedError("会话已关闭")

        async with self._stream_id_lock:
            stream_id = self._next_stream_id
            self._next_stream_id += STREAM_ID_INCREMENT

        async with self._streams_lock:
            if stream_id in self._streams:
                raise YamuxProtocolError(f"流ID冲突: {stream_id}")

            stream = YamuxStream(
                stream_id=stream_id,
                session=self,
                is_initiator=True,
                config=self._config
            )
            self._streams[stream_id] = stream

        # 发送 SYN
        frame = YamuxFrame(
            type=FrameType.DATA,
            flags=FrameFlag.SYN,
            stream_id=stream_id,
            length=0
        )
        await self._send_frame(frame)

        stream._set_state(StreamState.SYN_SENT)
        self._unacked_streams += 1

        return stream

    async def accept_stream(self) -> YamuxStream:
        """
        接受入站流

        Returns:
            被接受的 YamuxStream 实例

        Raises:
            YamuxClosedError: 会话已关闭
        """
        if self._closed:
            raise YamuxClosedError("会话已关闭")

        return await self._accept_queue.get()

    async def close(self, code: GoAwayCode = GoAwayCode.NORMAL) -> None:
        """
        关闭会话

        Args:
            code: 关闭原因码
        """
        async with self._close_lock:
            if self._closed:
                return

            self._closed = True
            self._goaway_code = code

            # 发送 GoAway
            frame = YamuxFrame(
                type=FrameType.GO_AWAY,
                stream_id=0,
                length=code
            )
            await self._send_frame(frame)

            # 关闭所有流
            async with self._streams_lock:
                for stream in self._streams.values():
                    if not stream.is_closed:
                        await stream.reset()

            # 停止任务
            if self._read_task:
                self._read_task.cancel()
            if self._keepalive_task:
                self._keepalive_task.cancel()

            # 关闭连接
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

    async def ping(self, timeout: float = 5.0) -> float:
        """
        发送 Ping 测量 RTT

        Args:
            timeout: 超时时间(秒)

        Returns:
            往返时间(秒)

        Raises:
            YamuxClosedError: 会话已关闭
            asyncio.TimeoutError: Ping 超时
        """
        if self._closed:
            raise YamuxClosedError("会话已关闭")

        async with self._ping_lock:
            ping_id = self._ping_counter
            self._ping_counter = (self._ping_counter + 1) & 0xFFFFFFFF

            future: asyncio.Future[float] = asyncio.Future()
            self._pending_pings[ping_id] = future

        frame = YamuxFrame(
            type=FrameType.PING,
            flags=FrameFlag.SYN,
            stream_id=0,
            length=ping_id
        )
        start_time = asyncio.get_event_loop().time()
        await self._send_frame(frame)

        try:
            await asyncio.wait_for(future, timeout=timeout)
            rtt = asyncio.get_event_loop().time() - start_time
            return rtt
        except asyncio.TimeoutError:
            self._pending_pings.pop(ping_id, None)
            raise

    async def _send_frame(self, frame: YamuxFrame) -> None:
        """发送帧"""
        if self._closed:
            raise YamuxClosedError("会话已关闭")

        data = frame.pack()
        self._writer.write(data)
        await self._writer.drain()

        logger.debug(f"发送帧: {frame}")

    def _start_read_loop(self) -> None:
        """启动读取循环"""
        async def read_loop():
            try:
                await self._read_loop()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"读取循环错误: {e}")
                await self.close(GoAwayCode.PROTOCOL_ERROR)

        self._read_task = asyncio.create_task(read_loop())

    def _start_keepalive(self) -> None:
        """启动保活"""
        async def keepalive():
            while not self._closed:
                try:
                    await asyncio.sleep(self._config.keepalive_interval)
                    if not self._closed:
                        await self.ping()
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass

        self._keepalive_task = asyncio.create_task(keepalive())

    async def _read_loop(self) -> None:
        """读取循环"""
        buffer = bytearray()

        while not self._closed:
            # 读取头部
            header = await self._reader.readexactly(HEADER_SIZE)
            buffer.extend(header)

            # 解析头部
            version, type_val, flags, stream_id, length = struct.unpack(">BBHII", buffer[:HEADER_SIZE])

            frame_type = FrameType(type_val)

            # 读取数据
            data = b""
            if length > 0:
                data = await self._reader.readexactly(length)

            frame = YamuxFrame(
                version=version,
                type=frame_type,
                flags=flags,
                stream_id=stream_id,
                length=length,
                data=data
            )

            logger.debug(f"接收帧: {frame}")

            # 处理帧
            await self._handle_frame(frame)

            buffer.clear()

    async def _handle_frame(self, frame: YamuxFrame) -> None:
        """处理接收到的帧"""
        # 检查版本
        if frame.version != VERSION:
            logger.warning(f"不支持的版本: {frame.version}")
            await self.close(GoAwayCode.PROTOCOL_ERROR)
            return

        # 处理会话级消息
        if frame.stream_id == 0:
            await self._handle_session_frame(frame)
            return

        # 获取或创建流
        async with self._streams_lock:
            stream = self._streams.get(frame.stream_id)

            # 新流 (SYN)
            if stream is None and frame.has_flag(FrameFlag.SYN):
                if not self._is_client and (frame.stream_id % 2) != 0:
                    # 服务端接收奇数ID
                    stream = YamuxStream(
                        stream_id=frame.stream_id,
                        session=self,
                        is_initiator=False,
                        config=self._config
                    )
                    self._streams[frame.stream_id] = stream

                    # 发送 ACK
                    ack_frame = YamuxFrame(
                        type=frame.type,
                        flags=frame.flags | FrameFlag.ACK,
                        stream_id=frame.stream_id,
                        length=0
                    )
                    await self._send_frame(ack_frame)

                    stream._set_state(StreamState.ESTABLISHED)

                    try:
                        self._accept_queue.put_nowait(stream)
                    except asyncio.QueueFull:
                        # 拒绝流
                        rst_frame = YamuxFrame(
                            type=FrameType.DATA,
                            flags=FrameFlag.RST,
                            stream_id=frame.stream_id,
                            length=0
                        )
                        await self._send_frame(rst_frame)
                        return

                elif self._is_client and (frame.stream_id % 2) == 0:
                    # 客户端接收偶数ID
                    stream = YamuxStream(
                        stream_id=frame.stream_id,
                        session=self,
                        is_initiator=False,
                        config=self._config
                    )
                    self._streams[frame.stream_id] = stream

                    # 发送 ACK
                    ack_frame = YamuxFrame(
                        type=frame.type,
                        flags=frame.flags | FrameFlag.ACK,
                        stream_id=frame.stream_id,
                        length=0
                    )
                    await self._send_frame(ack_frame)

                    stream._set_state(StreamState.ESTABLISHED)

                    try:
                        self._accept_queue.put_nowait(stream)
                    except asyncio.QueueFull:
                        # 拒绝流
                        rst_frame = YamuxFrame(
                            type=FrameType.DATA,
                            flags=FrameFlag.RST,
                            stream_id=frame.stream_id,
                            length=0
                        )
                        await self._send_frame(rst_frame)
                        return
                else:
                    logger.warning(f"无效的流ID: {frame.stream_id}")
                    return

            if stream is None:
                logger.warning(f"未知流ID: {frame.stream_id}")
                return

        # 处理 ACK
        if frame.has_flag(FrameFlag.ACK):
            self._unacked_streams -= 1
            if stream._state == StreamState.SYN_SENT:
                stream._set_state(StreamState.ESTABLISHED)

        # 根据帧类型处理
        if frame.type == FrameType.DATA:
            await stream._handle_data(frame)
        elif frame.type == FrameType.WINDOW_UPDATE:
            await stream._handle_window_update(frame)
        elif frame.type == FrameType.PING:
            # 流级别的PING不应该出现
            pass

        # 清理已关闭的流
        async with self._streams_lock:
            if stream.is_closed and stream._recv_queue.empty():
                self._streams.pop(frame.stream_id, None)

    async def _handle_session_frame(self, frame: YamuxFrame) -> None:
        """处理会话级帧"""
        if frame.type == FrameType.PING:
            if frame.has_flag(FrameFlag.SYN):
                # 响应 PING
                response = YamuxFrame(
                    type=FrameType.PING,
                    flags=FrameFlag.ACK,
                    stream_id=0,
                    length=frame.length
                )
                await self._send_frame(response)
            elif frame.has_flag(FrameFlag.ACK):
                # 处理 PING 响应
                ping_id = frame.length
                future = self._pending_pings.pop(ping_id, None)
                if future and not future.done():
                    future.set_result(True)

        elif frame.type == FrameType.GO_AWAY:
            self._closed = True
            self._goaway_code = GoAwayCode(frame.length)
            logger.info(f"接收到 GoAway: {self._goaway_code.name}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
