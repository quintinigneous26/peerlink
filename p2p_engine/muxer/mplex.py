"""
Mplex Stream Multiplexer Implementation for libp2p

Based on libp2p mplex specification:
https://github.com/libp2p/specs/blob/master/mplex.md

Protocol string: /mplex/6.7.0

Features:
- Stream multiplexing over a single connection
- Simple framing with variable-length integer encoding
- Backpressure via receive window
- Half-close support

Mplex uses a tag-based framing system:
- Tag format: [MSB flag][stream ID]
- MSB flag: 0 for initiator, 1 for receiver
- Stream ID: Variable-length integer
"""

import asyncio
import struct
import logging
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import Optional, Dict, Deque, Callable, Awaitable
from collections import deque

logger = logging.getLogger("p2p_engine.muxer.mplex")


# ==================== Constants ====================

PROTOCOL_STRING = "/mplex/6.7.0"

# Stream ID allocation
INITIAL_CLIENT_STREAM_ID = 0
INITIAL_SERVER_STREAM_ID = 1

# Buffer sizes
DEFAULT_BUFFER_SIZE = 64 * 1024  # 64KB
MAX_BUFFER_SIZE = 16 * 1024 * 1024  # 16MB

# Receive window
DEFAULT_WINDOW_SIZE = 256 * 1024  # 256KB

# Timeout
DEFAULT_ACCEPT_TIMEOUT = 30.0

# Maximum stream ID (to prevent overflow)
MAX_STREAM_ID = 2**63 - 1


# ==================== Frame Flags ====================

class MplexFlag(IntEnum):
    """Mplex frame type flags."""
    NEW_STREAM = 0   # New stream
    MESSAGE = 1      # Message data
    CLOSE = 2        # Close stream (half-close)
    RESET = 3        # Reset stream


# ==================== Stream State ====================

class StreamState(IntEnum):
    """Stream state machine."""
    INIT = 0           # Initialized
    OPENING = 1        # Opening (waiting for ack)
    OPEN = 2           # Open
    CLOSED_LOCAL = 3   # Locally closed
    CLOSED_REMOTE = 4  # Remotely closed
    CLOSED = 5         # Fully closed
    RESET = 6          # Reset


# ==================== Exceptions ====================

class MplexError(Exception):
    """Base exception for mplex errors."""
    pass


class MplexProtocolError(MplexError):
    """Protocol error."""
    pass


class MplexClosedError(MplexError):
    """Session closed."""
    pass


class MplexStreamClosed(MplexError):
    """Stream closed."""
    pass


class MplexStreamReset(MplexError):
    """Stream reset."""
    pass


class MplexWindowExceeded(MplexError):
    """Window exceeded."""
    pass


# ==================== Variable-Length Integer ====================

def write_uvarint(data: bytearray, value: int) -> None:
    """
    Write a variable-length integer to bytearray.

    Uses unsigned LEB128 encoding.

    Args:
        data: Bytearray to write to
        value: Integer value to encode
    """
    while value >= 0x80:
        data.append((value & 0x7F) | 0x80)
        value >>= 7
    data.append(value)


def read_uvarint(data: bytes, offset: int = 0) -> tuple[int, int]:
    """
    Read a variable-length integer from bytes.

    Args:
        data: Bytes to read from
        offset: Starting offset

    Returns:
        Tuple of (value, bytes_consumed)

    Raises:
        MplexProtocolError: If encoding is invalid
    """
    value = 0
    shift = 0
    idx = offset

    while idx < len(data):
        byte = data[idx]
        idx += 1
        value |= (byte & 0x7F) << shift

        if (byte & 0x80) == 0:
            return value, idx - offset

        shift += 7
        if shift >= 64:
            raise MplexProtocolError("Invalid uvarint encoding")

    raise MplexProtocolError("Incomplete uvarint")


# ==================== Mplex Frame ====================

@dataclass
class MplexFrame:
    """Mplex frame structure."""
    flag: MplexFlag
    stream_id: int
    data: bytes = b""

    def pack(self) -> bytes:
        """Pack frame to bytes."""
        # Construct tag: [MSB][stream_id][flag]
        # MSB is set for remote-initiated streams
        msb = (self.stream_id & 1) == 0
        tag = self.stream_id << 3 | self.flag

        if msb:
            tag |= 0x80

        result = bytearray()
        write_uvarint(result, tag)

        if self.data:
            # Add length prefix for data
            write_uvarint(result, len(self.data))
            result.extend(self.data)

        return bytes(result)

    @classmethod
    def unpack(cls, data: bytes) -> tuple['MplexFrame', int]:
        """
        Unpack frame from bytes.

        Returns:
            Tuple of (frame, bytes_consumed)
        """
        tag, offset = read_uvarint(data)

        flag = MplexFlag(tag & 0x07)
        msb = (tag & 0x80) != 0

        # Stream ID is encoded in the bits between flag and MSB
        # Format: [MSB][stream_id << 3][flag]
        # According to mplex spec: stream_id = (tag >> 3)
        stream_id = tag >> 3

        frame_data = b""
        remaining = data[offset:]

        # Check if there's a data length
        if remaining:
            try:
                length, data_offset = read_uvarint(remaining)
                if data_offset + length <= len(remaining):
                    frame_data = remaining[data_offset:data_offset + length]
                    offset += data_offset + length
            except (MplexProtocolError, ValueError):
                pass

        return cls(flag=flag, stream_id=stream_id, data=frame_data), offset

    def __repr__(self) -> str:
        return (f"MplexFrame(flag={self.flag.name}, "
                f"stream_id={self.stream_id}, "
                f"data_len={len(self.data)})")


# ==================== Mplex Stream ====================

class MplexStream:
    """
    Mplex logical stream.

    Implements:
    - Read/write operations
    - Half-close
    - Flow control
    - Reset
    """

    def __init__(
        self,
        stream_id: int,
        session: 'MplexSession',
        is_initiator: bool = False,
    ):
        self._id = stream_id
        self._session = session
        self._is_initiator = is_initiator

        # State
        self._state = StreamState.INIT
        self._read_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()

        # Receive buffer
        self._recv_buffer: Deque[bytes] = deque()
        self._recv_size = 0
        self._recv_event = asyncio.Event()
        self._recv_window = DEFAULT_WINDOW_SIZE

        # Send window
        self._send_window = DEFAULT_WINDOW_SIZE
        self._send_event = asyncio.Event()

        # Close flags
        self._local_closed = False
        self._remote_closed = False
        self._reset = False

        # Established flag
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
        return self._state == StreamState.OPEN

    async def read(self, n: int = -1) -> bytes:
        """
        Read data from stream.

        Args:
            n: Number of bytes to read, -1 for all available

        Returns:
            Read data

        Raises:
            MplexStreamClosed: Stream is closed
            MplexStreamReset: Stream was reset
        """
        async with self._read_lock:
            if self._reset:
                raise MplexStreamReset("Stream was reset")

            if self._remote_closed and not self._recv_buffer:
                return b""

            data = bytearray()

            if n < 0:
                # Read all available data
                while self._recv_buffer:
                    chunk = self._recv_buffer.popleft()
                    data.extend(chunk)
                    self._recv_size -= len(chunk)

                    if not self._remote_closed:
                        self._send_window_update()

                if not data and not self._remote_closed:
                    await self._recv_event.wait()
                    self._recv_event.clear()
                    return await self.read(-1)
            else:
                # Read specific number of bytes
                while len(data) < n:
                    if not self._recv_buffer:
                        if self._remote_closed:
                            break
                        await self._recv_event.wait()
                        self._recv_event.clear()
                        continue

                    chunk = self._recv_buffer[0]
                    needed = n - len(data)
                    if len(chunk) <= needed:
                        data.extend(self._recv_buffer.popleft())
                        self._recv_size -= len(chunk)
                    else:
                        data.extend(chunk[:needed])
                        self._recv_buffer[0] = chunk[needed:]
                        self._recv_size -= needed

                    if not self._remote_closed:
                        self._send_window_update()

            # Send window update if we consumed data
            if data and not self._remote_closed:
                await self._send_window_update()

            return bytes(data)

    async def write(self, data: bytes) -> int:
        """
        Write data to stream.

        Args:
            data: Data to write

        Returns:
            Number of bytes written

        Raises:
            MplexStreamClosed: Stream is closed
            MplexStreamReset: Stream was reset
        """
        async with self._write_lock:
            if self._reset:
                raise MplexStreamReset("Stream was reset")

            if self._local_closed:
                raise MplexStreamClosed("Local side already closed")

            if not data:
                return 0

            # Wait for stream to be established
            if not self._established.is_set():
                await self._established.wait()

            # Split into chunks if needed
            chunk_size = min(DEFAULT_BUFFER_SIZE, len(data))
            written = 0

            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                frame = MplexFrame(
                    flag=MplexFlag.MESSAGE,
                    stream_id=self._id,
                    data=chunk
                )
                await self._session._send_frame(frame)
                written += len(chunk)

            return written

    async def close(self) -> None:
        """
        Half-close stream (close write side).

        Send CLOSE flag to indicate no more data will be sent.
        """
        async with self._write_lock:
            if self._local_closed:
                return

            self._local_closed = True

            frame = MplexFrame(
                flag=MplexFlag.CLOSE,
                stream_id=self._id,
            )
            await self._session._send_frame(frame)

            if self._remote_closed:
                self._state = StreamState.CLOSED
            else:
                self._state = StreamState.CLOSED_LOCAL

    async def reset(self) -> None:
        """
        Immediately reset stream.

        Send RESET flag to abort stream.
        """
        self._reset = True
        self._state = StreamState.RESET

        frame = MplexFrame(
            flag=MplexFlag.RESET,
            stream_id=self._id,
        )
        await self._session._send_frame(frame)

        # Clear receive buffer
        self._recv_buffer.clear()
        self._recv_size = 0
        self._recv_event.set()

    async def _handle_data(self, data: bytes) -> None:
        """Handle received data."""
        if self._reset:
            return

        if self._recv_size + len(data) > MAX_BUFFER_SIZE:
            # Buffer overflow, reset stream
            await self.reset()
            raise MplexWindowExceeded("Receive buffer exceeded")

        self._recv_buffer.append(data)
        self._recv_size += len(data)
        self._recv_event.set()

    def _handle_close(self) -> None:
        """Handle remote close."""
        self._remote_closed = True
        self._recv_event.set()

        if self._local_closed:
            self._state = StreamState.CLOSED
        else:
            self._state = StreamState.CLOSED_REMOTE

    def _handle_reset(self) -> None:
        """Handle remote reset."""
        self._reset = True
        self._state = StreamState.RESET
        self._recv_event.set()

    async def _send_window_update(self) -> None:
        """Send window update (implicit in mplex via backpressure)."""
        # Mplex doesn't have explicit window updates like yamux
        # Backpressure is handled by not reading from underlying transport
        pass

    def _set_state(self, state: StreamState) -> None:
        """Set stream state."""
        self._state = state
        if state == StreamState.OPEN:
            self._established.set()


# ==================== Mplex Session ====================

class MplexSession:
    """
    Mplex session for multiplexing streams.

    Manages multiple logical streams over a single connection.

    Features:
    - Open new streams
    - Accept inbound streams
    - Frame handling
    - Session management
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        is_client: bool = True,
    ):
        self._reader = reader
        self._writer = writer
        self._is_client = is_client

        # Stream management
        self._streams: Dict[int, MplexStream] = {}
        self._streams_lock = asyncio.Lock()

        # Stream ID allocation
        self._next_stream_id = INITIAL_CLIENT_STREAM_ID if is_client else INITIAL_SERVER_STREAM_ID
        self._stream_id_lock = asyncio.Lock()

        # Accept queue
        self._accept_queue: asyncio.Queue[MplexStream] = asyncio.Queue()

        # Session state
        self._closed = False
        self._close_lock = asyncio.Lock()

        # Read loop task
        self._read_task: Optional[asyncio.Task] = None

        # Start read loop
        self._start_read_loop()

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
    ) -> 'MplexSession':
        """Create client session."""
        reader, writer = await asyncio.open_connection(host, port)
        session = cls(reader, writer, is_client=True)
        return session

    @classmethod
    def create_server_session(
        cls,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> 'MplexSession':
        """Create server session."""
        session = cls(reader, writer, is_client=False)
        return session

    async def open_stream(self) -> MplexStream:
        """
        Open new stream.

        Returns:
            New MplexStream instance

        Raises:
            MplexClosedError: Session is closed
        """
        if self._closed:
            raise MplexClosedError("Session is closed")

        async with self._stream_id_lock:
            stream_id = self._next_stream_id
            self._next_stream_id += 2  # Odd/even based on client/server

            if stream_id > MAX_STREAM_ID:
                raise MplexProtocolError("Stream ID exhausted")

        async with self._streams_lock:
            if stream_id in self._streams:
                raise MplexProtocolError(f"Stream ID conflict: {stream_id}")

            stream = MplexStream(
                stream_id=stream_id,
                session=self,
                is_initiator=True,
            )
            self._streams[stream_id] = stream

        # Send NEW_STREAM frame
        frame = MplexFrame(
            flag=MplexFlag.NEW_STREAM,
            stream_id=stream_id,
        )
        await self._send_frame(frame)

        stream._set_state(StreamState.OPEN)

        logger.debug(f"Opened new stream: {stream_id}")

        return stream

    async def accept_stream(self, timeout: float = DEFAULT_ACCEPT_TIMEOUT) -> MplexStream:
        """
        Accept inbound stream.

        Args:
            timeout: Accept timeout in seconds

        Returns:
            Accepted MplexStream

        Raises:
            MplexClosedError: Session is closed
            asyncio.TimeoutError: Accept timeout
        """
        if self._closed:
            raise MplexClosedError("Session is closed")

        return await asyncio.wait_for(
            self._accept_queue.get(),
            timeout=timeout
        )

    async def close(self) -> None:
        """Close session and all streams."""
        async with self._close_lock:
            if self._closed:
                return

            self._closed = True

            # Close all streams
            async with self._streams_lock:
                for stream in list(self._streams.values()):
                    if not stream.is_closed:
                        await stream.reset()
                self._streams.clear()

            # Stop read loop
            if self._read_task:
                self._read_task.cancel()
                try:
                    await self._read_task
                except asyncio.CancelledError:
                    pass

            # Close connection
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

            logger.debug("Mplex session closed")

    async def _send_frame(self, frame: MplexFrame) -> None:
        """Send frame."""
        if self._closed:
            raise MplexClosedError("Session is closed")

        data = frame.pack()
        self._writer.write(data)
        await self._writer.drain()

        logger.debug(f"Sent frame: {frame}")

    def _start_read_loop(self) -> None:
        """Start read loop task."""
        async def read_loop():
            try:
                await self._read_loop()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Read loop error: {e}")
                await self.close()

        self._read_task = asyncio.create_task(read_loop())

    async def _read_loop(self) -> None:
        """Read loop for incoming frames."""
        buffer = bytearray()

        while not self._closed:
            try:
                # Read at least one byte for uvarint
                data = await self._reader.read(1)
                if not data:
                    logger.debug("Connection closed by peer")
                    await self.close()
                    return

                buffer.extend(data)

                # Try to read tag
                try:
                    tag, tag_len = read_uvarint(bytes(buffer))
                    flag = MplexFlag(tag & 0x07)
                    # Stream ID: tag >> 3 (after removing the 3-bit flag)
                    stream_id = tag >> 3

                    # Check if data follows
                    remaining = buffer[tag_len:]
                    if remaining:
                        try:
                            length, len_len = read_uvarint(remaining)
                            total_len = tag_len + len_len + length

                            # Read more data if needed
                            while len(buffer) < total_len:
                                data = await self._reader.read(total_len - len(buffer))
                                if not data:
                                    await self.close()
                                    return
                                buffer.extend(data)

                            frame_data = remaining[len_len:len_len + length]
                            frame = MplexFrame(flag=flag, stream_id=stream_id, data=frame_data)
                        except (MplexProtocolError, ValueError):
                            # Not enough data yet
                            continue
                    else:
                        frame = MplexFrame(flag=flag, stream_id=stream_id)

                    buffer.clear()

                    await self._handle_frame(frame)

                except MplexProtocolError:
                    # Need more data
                    continue

            except Exception as e:
                if not self._closed:
                    logger.error(f"Read error: {e}")
                    await self.close()
                return

    async def _handle_frame(self, frame: MplexFrame) -> None:
        """Handle incoming frame."""
        logger.debug(f"Received frame: {frame}")

        async with self._streams_lock:
            stream = self._streams.get(frame.stream_id)

            # New stream
            if frame.flag == MplexFlag.NEW_STREAM:
                if stream is None:
                    stream = MplexStream(
                        stream_id=frame.stream_id,
                        session=self,
                        is_initiator=False,
                    )
                    self._streams[frame.stream_id] = stream
                    stream._set_state(StreamState.OPEN)

                    try:
                        self._accept_queue.put_nowait(stream)
                    except asyncio.QueueFull:
                        # Reject stream
                        await stream.reset()
                        return

                    logger.debug(f"Accepted new stream: {frame.stream_id}")
                return

            if stream is None:
                logger.warning(f"Unknown stream ID: {frame.stream_id}")
                return

        # Handle frame based on flag
        if frame.flag == MplexFlag.MESSAGE:
            if frame.data:
                await stream._handle_data(frame.data)

        elif frame.flag == MplexFlag.CLOSE:
            stream._handle_close()

        elif frame.flag == MplexFlag.RESET:
            stream._handle_reset()

        # Cleanup closed streams
        async with self._streams_lock:
            if stream.is_closed and stream._recv_size == 0:
                self._streams.pop(frame.stream_id, None)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


__all__ = [
    # Protocol identifier
    "PROTOCOL_STRING",
    "MPLEX_PROTOCOL_ID",

    # Exceptions
    "MplexError",
    "MplexProtocolError",
    "MplexClosedError",
    "MplexStreamClosed",
    "MplexStreamReset",
    "MplexWindowExceeded",

    # Main API
    "MplexSession",
    "MplexStream",
    "MplexFrame",

    # Utilities
    "write_uvarint",
    "read_uvarint",
    "encode_uvarint",
    "decode_uvarint",
]


# Backward compatibility aliases
MPLEX_PROTOCOL_ID = PROTOCOL_STRING
encode_uvarint = write_uvarint
decode_uvarint = read_uvarint
