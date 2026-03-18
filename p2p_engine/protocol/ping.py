"""
Ping Protocol Implementation

This module implements the libp2p ping protocol specification:
https://github.com/libp2p/specs/blob/master/ping/ping.md

The ping protocol is a simple liveness check that peers can use to test
the connectivity and performance between two peers. It operates on an
already established libp2p connection.

Protocol ID: /ipfs/ping/1.0.0
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable

logger = logging.getLogger("p2p_engine.protocol.ping")


# ==================== Protocol Constants ====================

PROTOCOL_ID = "/ipfs/ping/1.0.0"
PING_PAYLOAD_SIZE = 32  # 32 bytes as per spec


# ==================== Statistics ====================

@dataclass
class PingStats:
    """Ping statistics"""
    total_sent: int = 0
    total_received: int = 0
    consecutive_success: int = 0
    consecutive_failure: int = 0
    last_rtt_ms: float = 0.0
    avg_rtt_ms: float = 0.0
    min_rtt_ms: float = float('inf')
    max_rtt_ms: float = 0.0
    last_success_time: float = 0.0


# ==================== Ping Protocol ====================

class PingProtocol:
    """
    libp2p Ping Protocol Implementation

    The ping protocol measures RTT (Round Trip Time) between peers by:
    1. Dialing peer sends 32 random bytes
    2. Listening peer echoes back the same bytes
    3. Dialing peer measures RTT from send to receive

    The dialing peer may repeat the process on the same stream.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        is_dialer: bool = True,
        timeout: float = 30.0,
        on_stats_update: Optional[Callable[[PingStats], Awaitable[None]]] = None,
    ):
        """
        Initialize ping protocol

        Args:
            reader: Stream reader for the connection
            writer: Stream writer for the connection
            is_dialer: True if this peer initiated the connection
            timeout: Default timeout for ping operations (seconds)
            on_stats_update: Optional callback when stats are updated
        """
        self._reader = reader
        self._writer = writer
        self._is_dialer = is_dialer
        self._timeout = timeout
        self._on_stats_update = on_stats_update

        self._stats = PingStats()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Per-peer stream limit as per spec
        self._max_streams_per_peer = 1 if is_dialer else 2

    @property
    def stats(self) -> PingStats:
        """Get ping statistics"""
        return self._stats

    @property
    def is_running(self) -> bool:
        """Check if ping is running"""
        return self._running

    async def ping(self, count: int = 1, interval: float = 1.0) -> PingStats:
        """
        Send ping requests and measure RTT

        Args:
            count: Number of ping requests to send
            interval: Interval between pings in seconds

        Returns:
            Updated PingStats

        Raises:
            RuntimeError: If not the dialing peer
            asyncio.TimeoutError: If ping times out
            ConnectionError: If connection fails
        """
        if not self._is_dialer:
            raise RuntimeError("Only dialing peer can initiate ping")

        if self._running:
            raise RuntimeError("Ping already running")

        self._running = True

        try:
            for i in range(count):
                if not self._running:
                    break

                try:
                    rtt = await self._send_ping()
                    self._on_ping_success(rtt)

                    if i < count - 1 and interval > 0:
                        await asyncio.sleep(interval)

                except asyncio.TimeoutError:
                    self._on_ping_failure("timeout")
                    if count == 1:
                        raise
                except Exception as e:
                    self._on_ping_failure(str(e))
                    if count == 1:
                        raise ConnectionError(f"Ping failed: {e}")

            return self._stats

        finally:
            self._running = False

    async def _send_ping(self) -> float:
        """
        Send a single ping request

        Returns:
            RTT in seconds

        Raises:
            asyncio.TimeoutError: If response times out
            ConnectionError: If connection fails
        """
        # Generate 32 random bytes
        payload = os.urandom(PING_PAYLOAD_SIZE)

        start_time = time.time()

        try:
            # Send payload
            self._writer.write(payload)
            await self._writer.drain()
            self._stats.total_sent += 1

            logger.debug(f"[Ping] Sent {len(payload)} bytes")

            # Receive echo
            response = await asyncio.wait_for(
                self._reader.readexactly(PING_PAYLOAD_SIZE),
                timeout=self._timeout
            )

            rtt = time.time() - start_time

            # Verify response matches
            if response != payload:
                raise ConnectionError("Ping response mismatch")

            self._stats.total_received += 1
            logger.debug(f"[Ping] Received echo, RTT: {rtt*1000:.2f}ms")

            return rtt

        except asyncio.TimeoutError:
            raise
        except asyncio.IncompleteReadError:
            raise ConnectionError("Connection closed")
        except ConnectionError:
            raise
        except Exception as e:
            raise ConnectionError(f"Ping error: {e}")

    def _on_ping_success(self, rtt: float) -> None:
        """Handle successful ping"""
        rtt_ms = rtt * 1000

        self._stats.last_rtt_ms = rtt_ms
        self._stats.last_success_time = time.time()
        self._stats.consecutive_success += 1
        self._stats.consecutive_failure = 0

        # Update min/max
        if rtt_ms < self._stats.min_rtt_ms:
            self._stats.min_rtt_ms = rtt_ms
        if rtt_ms > self._stats.max_rtt_ms:
            self._stats.max_rtt_ms = rtt_ms

        # Update average (exponential moving average)
        if self._stats.avg_rtt_ms == 0:
            self._stats.avg_rtt_ms = rtt_ms
        else:
            alpha = 0.2
            self._stats.avg_rtt_ms = (
                alpha * rtt_ms + (1 - alpha) * self._stats.avg_rtt_ms
            )

    def _on_ping_failure(self, reason: str) -> None:
        """Handle failed ping"""
        self._stats.consecutive_failure += 1
        self._stats.consecutive_success = 0
        logger.warning(f"[Ping] Failed: {reason}")

    async def serve(self) -> None:
        """
        Handle incoming ping requests (server side)

        This method echoes back received payloads. It runs until
        the connection is closed or stop() is called.

        Raises:
            RuntimeError: If already running
        """
        if self._running:
            raise RuntimeError("Ping server already running")

        self._running = False  # Will be set to True in the task

        async def serve_loop():
            self._running = True
            try:
                while self._running:
                    try:
                        await self._handle_ping_request()
                    except asyncio.IncompleteReadError:
                        logger.debug("[Ping] Client closed connection")
                        break
                    except Exception as e:
                        if self._running:
                            logger.error(f"[Ping] Error handling request: {e}")
                        break
            finally:
                self._running = False

        self._task = asyncio.create_task(serve_loop())

        # Wait for serve loop to complete
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def _handle_ping_request(self) -> None:
        """Handle a single ping request"""
        # Read 32 bytes
        payload = await asyncio.wait_for(
            self._reader.readexactly(PING_PAYLOAD_SIZE),
            timeout=self._timeout
        )

        logger.debug(f"[Ping] Received {len(payload)} bytes, echoing back")

        # Echo back
        self._writer.write(payload)
        await self._writer.drain()

        self._stats.total_received += 1
        self._stats.total_sent += 1

    async def stop(self) -> None:
        """Stop ping operation"""
        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:
            pass

    def reset_stats(self) -> None:
        """Reset statistics"""
        self._stats = PingStats()


# ==================== Convenience Functions ====================

async def ping_peer(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    count: int = 1,
    timeout: float = 30.0,
) -> PingStats:
    """
    Convenience function to ping a peer

    Args:
        reader: Stream reader
        writer: Stream writer
        count: Number of pings to send
        timeout: Timeout per ping

    Returns:
        PingStats with results
    """
    protocol = PingProtocol(reader, writer, is_dialer=True, timeout=timeout)
    return await protocol.ping(count=count)


async def serve_ping(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    timeout: float = 30.0,
) -> None:
    """
    Convenience function to serve ping requests

    Args:
        reader: Stream reader
        writer: Stream writer
        timeout: Timeout for read operations
    """
    protocol = PingProtocol(reader, writer, is_dialer=False, timeout=timeout)
    await protocol.serve()


# ==================== Configuration ====================

@dataclass
class PingConfig:
    """Configuration for ping protocol."""
    timeout: float = 30.0
    ping_interval: float = 1.0
    max_idle_time: float = 60.0


# ==================== Compatibility for Tests ====================

@dataclass
class PingMessage:
    """Ping message with sequence number for compatibility."""
    seq_no: int


# Protocol ID alias
PING_PROTOCOL_ID = PROTOCOL_ID


__all__ = [
    # Protocol identifier
    "PROTOCOL_ID",
    "PING_PROTOCOL_ID",

    # Statistics
    "PingStats",

    # Configuration
    "PingConfig",

    # Messages
    "PingMessage",

    # Main API
    "PingProtocol",

    # Convenience
    "ping_peer",
    "serve_ping",
]
