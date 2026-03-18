"""
Unit tests for Transport Upgrader and MuxedSession.

Tests the stream multiplexing session implementation.
"""
import asyncio
import pytest
from p2p_engine.transport.upgrader import (
    MuxedSession,
    MuxedStream,
    SecureConnection,
    TransportError,
)
from p2p_engine.transport.base import Connection


class MockConnection(Connection):
    """Mock connection for testing."""

    def __init__(self):
        self._closed = False
        self._data = b""

    async def read(self, n: int = -1) -> bytes:
        return self._data

    async def write(self, data: bytes) -> int:
        self._data += data
        return len(data)

    async def close(self) -> None:
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    @property
    def remote_address(self):
        return ("127.0.0.1", 12345)

    @property
    def local_address(self):
        return ("127.0.0.1", 54321)


@pytest.mark.asyncio
async def test_muxed_session_open_stream():
    """Test opening a new stream from MuxedSession."""
    conn = MockConnection()
    session = MuxedSession(conn, "/yamux/1.0.0", is_initiator=True)

    # Open first stream (initiator uses odd IDs: 1, 3, 5, ...)
    stream1 = await session.open_stream()
    assert stream1.stream_id == 1
    assert isinstance(stream1, MuxedStream)
    assert not session.is_closed()

    # Open second stream
    stream2 = await session.open_stream()
    assert stream2.stream_id == 3

    await session.close()


@pytest.mark.asyncio
async def test_muxed_session_open_stream_responder():
    """Test opening streams as responder (even IDs)."""
    conn = MockConnection()
    session = MuxedSession(conn, "/yamux/1.0.0", is_initiator=False)

    # Responder uses even IDs: 2, 4, 6, ...
    stream1 = await session.open_stream()
    assert stream1.stream_id == 2

    stream2 = await session.open_stream()
    assert stream2.stream_id == 4

    await session.close()


@pytest.mark.asyncio
async def test_muxed_session_open_stream_closed():
    """Test that opening stream on closed session raises error."""
    conn = MockConnection()
    session = MuxedSession(conn, "/yamux/1.0.0", is_initiator=True)
    await session.close()

    with pytest.raises(TransportError, match="Session is closed"):
        await session.open_stream()


@pytest.mark.asyncio
async def test_muxed_session_accept_stream():
    """Test accepting incoming streams."""
    conn = MockConnection()
    session = MuxedSession(conn, "/yamux/1.0.0", is_initiator=True)

    # Simulate incoming stream in background
    async def simulate_incoming():
        await asyncio.sleep(0.1)
        await session._handle_incoming_stream(stream_id=2)

    # Start accept and simulation in parallel
    accept_task = asyncio.create_task(session.accept_stream())
    simulate_task = asyncio.create_task(simulate_incoming())

    # Wait for both to complete
    stream = await accept_task
    await simulate_task

    assert stream.stream_id == 2
    assert isinstance(stream, MuxedStream)

    await session.close()


@pytest.mark.asyncio
async def test_muxed_session_accept_stream_timeout():
    """Test that accept_stream times out when session closes."""
    conn = MockConnection()
    session = MuxedSession(conn, "/yamux/1.0.0", is_initiator=True)

    # Start accept in background
    accept_task = asyncio.create_task(session.accept_stream())

    # Wait a bit then close session
    await asyncio.sleep(0.1)
    await session.close()

    # Accept should raise error
    with pytest.raises(TransportError, match="Session is closed"):
        await accept_task


@pytest.mark.asyncio
async def test_muxed_session_multiple_accept():
    """Test accepting multiple streams sequentially."""
    conn = MockConnection()
    session = MuxedSession(conn, "/yamux/1.0.0", is_initiator=False)

    async def accept_and_verify():
        # Accept first stream
        stream1_task = asyncio.create_task(session.accept_stream())
        await session._handle_incoming_stream(stream_id=1)
        stream1 = await stream1_task
        assert stream1.stream_id == 1

        # Accept second stream
        stream2_task = asyncio.create_task(session.accept_stream())
        await session._handle_incoming_stream(stream_id=3)
        stream2 = await stream2_task
        assert stream2.stream_id == 3

    await accept_and_verify()
    await session.close()


@pytest.mark.asyncio
async def test_muxed_session_close_cleans_streams():
    """Test that closing session cleans up all streams."""
    conn = MockConnection()
    session = MuxedSession(conn, "/yamux/1.0.0", is_initiator=True)

    # Open multiple streams
    stream1 = await session.open_stream()
    stream2 = await session.open_stream()
    stream3 = await session.open_stream()

    # Close session
    await session.close()

    # Verify session is closed
    assert session.is_closed()
    assert conn.is_closed()


@pytest.mark.asyncio
async def test_muxed_session_concurrent_operations():
    """Test concurrent open and accept operations."""
    conn = MockConnection()
    session = MuxedSession(conn, "/yamux/1.0.0", is_initiator=True)

    async def open_streams():
        for i in range(3):
            await session.open_stream()

    async def accept_streams():
        for i in range(3):
            # Simulate incoming stream
            await session._handle_incoming_stream(stream_id=(i + 1) * 2)

    # Run operations concurrently
    await asyncio.gather(open_streams(), accept_streams())
    await session.close()


@pytest.mark.asyncio
async def test_secure_connection_wrapper():
    """Test SecureConnection wrapper."""
    inner_conn = MockConnection()
    secure_conn = SecureConnection(inner_conn, "peer123", "/noise/XX")

    assert secure_conn.peer_id == "peer123"
    assert secure_conn.protocol_id == "/noise/XX"
    assert not secure_conn.is_closed()

    await secure_conn.close()
    assert secure_conn.is_closed()
    assert inner_conn.is_closed()


@pytest.mark.asyncio
async def test_muxed_stream_properties():
    """Test MuxedStream properties."""
    reader = asyncio.StreamReader()
    writer = asyncio.StreamWriter(
        asyncio.open_connection(
            ("127.0.0.1", 12345)
        )[1]
    )

    # Create a simple mock writer since we can't use real connection
    class MockWriter:
        def __init__(self):
            self.data = b""

        def write(self, data):
            self.data += data
            return len(data)

        async def drain(self):
            pass

        def close(self):
            pass

        async def wait_closed(self):
            pass

        def is_closing(self):
            return False

    mock_writer = MockWriter()
    stream = MuxedStream(42, reader, mock_writer)

    assert stream.stream_id == 42
    assert stream.remote_address is None
    assert stream.local_address is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
