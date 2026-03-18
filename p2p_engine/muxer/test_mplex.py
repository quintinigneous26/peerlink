"""
Unit tests for Mplex stream multiplexer implementation.

Tests:
- Variable-length integer encoding/decoding
- Frame encoding/decoding
- Stream operations
- Session management
"""

import asyncio
import pytest
from p2p_engine.muxer.mplex import (
    MplexSession,
    MplexStream,
    MplexFrame,
    MplexFlag,
    StreamState,
    write_uvarint,
    read_uvarint,
    PROTOCOL_STRING,
    MplexError,
    MplexProtocolError,
    MplexClosedError,
    MplexStreamClosed,
    MplexStreamReset,
    MplexWindowExceeded,
)


class TestUvarint:
    """Test variable-length integer encoding/decoding."""

    def test_write_single_byte(self):
        """Test encoding single-byte value."""
        data = bytearray()
        write_uvarint(data, 0)
        assert data == b'\x00'

        data.clear()
        write_uvarint(data, 127)
        assert data == b'\x7f'

    def test_write_multi_byte(self):
        """Test encoding multi-byte value."""
        data = bytearray()
        write_uvarint(data, 128)
        assert data == b'\x80\x01'

        data.clear()
        write_uvarint(data, 16383)
        assert data == b'\xff\x7f'

    def test_read_single_byte(self):
        """Test decoding single-byte value."""
        value, n = read_uvarint(b'\x00')
        assert value == 0
        assert n == 1

        value, n = read_uvarint(b'\x7f')
        assert value == 127
        assert n == 1

    def test_read_multi_byte(self):
        """Test decoding multi-byte value."""
        value, n = read_uvarint(b'\x80\x01')
        assert value == 128
        assert n == 2

        value, n = read_uvarint(b'\xff\x7f')
        assert value == 16383
        assert n == 2

    def test_write_read_roundtrip(self):
        """Test roundtrip encoding/decoding."""
        test_values = [0, 1, 127, 128, 255, 256, 16383, 16384, 2097151]

        for val in test_values:
            data = bytearray()
            write_uvarint(data, val)
            decoded, n = read_uvarint(bytes(data))
            assert decoded == val
            assert n == len(data)

    def test_read_with_offset(self):
        """Test reading with offset."""
        data = b'\xff\x80\x01'
        value, n = read_uvarint(data, offset=1)
        assert value == 128
        assert n == 2


class TestMplexFrame:
    """Test Mplex frame encoding/decoding."""

    def test_frame_new_stream(self):
        """Test NEW_STREAM frame."""
        frame = MplexFrame(
            flag=MplexFlag.NEW_STREAM,
            stream_id=0,
        )

        encoded = frame.pack()
        decoded, offset = MplexFrame.unpack(encoded)

        assert decoded.flag == MplexFlag.NEW_STREAM
        assert decoded.stream_id == 0
        assert decoded.data == b""

    def test_frame_with_data(self):
        """Test frame with data payload."""
        frame = MplexFrame(
            flag=MplexFlag.MESSAGE,
            stream_id=1,
            data=b"Hello, world!"
        )

        encoded = frame.pack()
        decoded, offset = MplexFrame.unpack(encoded)

        assert decoded.flag == MplexFlag.MESSAGE
        assert decoded.stream_id == 1
        assert decoded.data == b"Hello, world!"

    def test_frame_close(self):
        """Test CLOSE frame."""
        frame = MplexFrame(
            flag=MplexFlag.CLOSE,
            stream_id=2,
        )

        encoded = frame.pack()
        decoded, offset = MplexFrame.unpack(encoded)

        assert decoded.flag == MplexFlag.CLOSE

    def test_frame_reset(self):
        """Test RESET frame."""
        frame = MplexFrame(
            flag=MplexFlag.RESET,
            stream_id=3,
        )

        encoded = frame.pack()
        decoded, offset = MplexFrame.unpack(encoded)

        assert decoded.flag == MplexFlag.RESET


class TestMplexStream:
    """Test Mplex stream operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock session for testing."""
        class MockSession:
            def __init__(self):
                self.sent_frames = []

            async def _send_frame(self, frame):
                self.sent_frames.append(frame)

        return MockSession()

    def test_stream_creation(self, mock_session):
        """Test stream creation."""
        stream = MplexStream(
            stream_id=0,
            session=mock_session,
            is_initiator=True
        )

        assert stream.id == 0
        assert stream.state == StreamState.INIT
        assert not stream.is_closed

    @pytest.mark.asyncio
    async def test_stream_close(self, mock_session):
        """Test stream close operation."""
        stream = MplexStream(
            stream_id=0,
            session=mock_session,
            is_initiator=True
        )

        await stream.close()

        assert stream._local_closed is True
        assert len(mock_session.sent_frames) == 1
        assert mock_session.sent_frames[0].flag == MplexFlag.CLOSE

    @pytest.mark.asyncio
    async def test_stream_reset(self, mock_session):
        """Test stream reset operation."""
        stream = MplexStream(
            stream_id=0,
            session=mock_session,
            is_initiator=True
        )

        await stream.reset()

        assert stream._reset is True
        assert stream.state == StreamState.RESET
        assert len(mock_session.sent_frames) == 1
        assert mock_session.sent_frames[0].flag == MplexFlag.RESET

    @pytest.mark.asyncio
    async def test_stream_handle_data(self, mock_session):
        """Test handling received data."""
        stream = MplexStream(
            stream_id=0,
            session=mock_session,
            is_initiator=True
        )

        await stream._handle_data(b"test-data")

        assert stream._recv_size == 9
        assert len(stream._recv_buffer) == 1

    @pytest.mark.asyncio
    async def test_stream_read_after_close(self, mock_session):
        """Test reading after remote close."""
        stream = MplexStream(
            stream_id=0,
            session=mock_session,
            is_initiator=True
        )

        stream._remote_closed = True
        data = await stream.read()

        assert data == b""

    @pytest.mark.asyncio
    async def test_stream_write_after_close(self, mock_session):
        """Test writing after local close raises error."""
        stream = MplexStream(
            stream_id=0,
            session=mock_session,
            is_initiator=True
        )

        await stream.close()

        with pytest.raises(MplexStreamClosed):
            await stream.write(b"test-data")

    @pytest.mark.asyncio
    async def test_stream_write_after_reset(self, mock_session):
        """Test writing after reset raises error."""
        stream = MplexStream(
            stream_id=0,
            session=mock_session,
            is_initiator=True
        )

        await stream.reset()

        with pytest.raises(MplexStreamReset):
            await stream.write(b"test-data")


class TestMplexSession:
    """Test Mplex session management."""

    @pytest.fixture
    async def connected_streams(self):
        """Create a pair of connected streams for testing."""
        # Create a socket pair
        reader_a = asyncio.StreamReader()
        reader_b = asyncio.StreamReader()

        class MockWriter:
            def __init__(self, reader, peer):
                self.reader = reader
                self.peer = peer
                self.data = bytearray()
                self.closed = False

            def write(self, data):
                self.data.extend(data)
                self.reader.feed_data(data)

            async def drain(self):
                pass

            def close(self):
                self.closed = True
                self.reader.feed_eof()

            async def wait_closed(self):
                pass

            def get_extra_info(self, name):
                return None

        writer_a = MockWriter(reader_b, None)
        writer_b = MockWriter(reader_a, None)

        return (reader_a, writer_a), (reader_b, writer_b)

    @pytest.mark.asyncio
    async def test_session_creation(self, connected_streams):
        """Test session creation."""
        (reader_a, writer_a), _ = connected_streams

        session = MplexSession(reader_a, writer_a, is_client=True)

        assert session.is_client is True
        assert not session.is_closed

        # Clean up
        await session.close()

    @pytest.mark.asyncio
    async def test_session_close(self, connected_streams):
        """Test session close."""
        (reader_a, writer_a), (reader_b, writer_b) = connected_streams

        session = MplexSession(reader_a, writer_a, is_client=True)
        await session.close()

        assert session.is_closed

    @pytest.mark.asyncio
    async def test_open_stream(self, connected_streams):
        """Test opening a new stream."""
        (reader_a, writer_a), (reader_b, writer_b) = connected_streams

        session = MplexSession(reader_a, writer_a, is_client=True)

        stream = await session.open_stream()

        assert stream is not None
        assert stream.id == 0  # First client stream ID
        assert stream.is_established

    @pytest.mark.asyncio
    async def test_open_stream_after_session_close(self, connected_streams):
        """Test opening stream after session close raises error."""
        (reader_a, writer_a), _ = connected_streams

        session = MplexSession(reader_a, writer_a, is_client=True)
        await session.close()

        with pytest.raises(MplexClosedError):
            await session.open_stream()

    @pytest.mark.asyncio
    async def test_send_frame(self, connected_streams):
        """Test sending frame through session."""
        (reader_a, writer_a), (reader_b, writer_b) = connected_streams

        session = MplexSession(reader_a, writer_a, is_client=True)

        frame = MplexFrame(
            flag=MplexFlag.NEW_STREAM,
            stream_id=0
        )

        await session._send_frame(frame)

        # Verify data was written
        assert len(writer_a.data) > 0


class TestProtocolConstants:
    """Test protocol constants."""

    def test_protocol_string(self):
        """Test protocol string constant."""
        assert PROTOCOL_STRING == "/mplex/6.7.0"

    def test_stream_states(self):
        """Test stream state enum values."""
        assert StreamState.INIT == 0
        assert StreamState.OPEN == 2
        assert StreamState.CLOSED == 5
        assert StreamState.RESET == 6

    def test_frame_flags(self):
        """Test frame flag enum values."""
        assert MplexFlag.NEW_STREAM == 0
        assert MplexFlag.MESSAGE == 1
        assert MplexFlag.CLOSE == 2
        assert MplexFlag.RESET == 3


class TestExceptions:
    """Test mplex exceptions."""

    def test_mplex_error(self):
        """Test base MplexError."""
        error = MplexError("test error")
        assert str(error) == "test error"

    def test_mplex_protocol_error(self):
        """Test MplexProtocolError."""
        error = MplexProtocolError("protocol error")
        assert isinstance(error, MplexError)

    def test_mplex_closed_error(self):
        """Test MplexClosedError."""
        error = MplexClosedError("session closed")
        assert isinstance(error, MplexError)

    def test_mplex_stream_closed(self):
        """Test MplexStreamClosed."""
        error = MplexStreamClosed("stream closed")
        assert isinstance(error, MplexError)

    def test_mplex_stream_reset(self):
        """Test MplexStreamReset."""
        error = MplexStreamReset("stream reset")
        assert isinstance(error, MplexError)

    def test_mplex_window_exceeded(self):
        """Test MplexWindowExceeded."""
        error = MplexWindowExceeded("window exceeded")
        assert isinstance(error, MplexError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
