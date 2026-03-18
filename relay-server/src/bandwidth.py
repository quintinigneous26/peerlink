"""
Bandwidth Control and Rate Limiting

Implements token bucket rate limiting and bandwidth monitoring.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class BandwidthLimit:
    """Bandwidth limit configuration."""

    read_bps: int  # Read bytes per second
    write_bps: int  # Write bytes per second
    burst_bps: int  # Burst allowance


@dataclass
class BandwidthStats:
    """Bandwidth statistics."""

    bytes_read: int = 0
    bytes_written: int = 0
    current_read_rate: float = 0.0
    current_write_rate: float = 0.0
    peak_read_rate: float = 0.0
    peak_write_rate: float = 0.0


class TokenBucket:
    """
    Token bucket rate limiter.

    Allows bursts up to bucket capacity while maintaining average rate.
    """

    def __init__(self, rate: int, capacity: int):
        """
        Initialize token bucket.

        Args:
            rate: Tokens per second (bytes per second)
            capacity: Maximum bucket size (burst allowance)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def consume(self, tokens: int) -> bool:
        """
        Try to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update

            # Add new tokens based on elapsed time
            self.tokens += elapsed * self.rate
            self.tokens = min(self.tokens, self.capacity)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def wait_for_tokens(self, tokens: int) -> bool:
        """
        Wait until enough tokens are available.

        Args:
            tokens: Number of tokens needed

        Returns:
            True if tokens acquired, False if rate is zero
        """
        if self.rate <= 0:
            return False

        while not await self.consume(tokens):
            # Calculate wait time
            async with self._lock:
                deficit = tokens - self.tokens
                wait_time = deficit / self.rate
                self.last_update = time.time()

            await asyncio.sleep(min(wait_time, 1.0))

        return True

    def get_available_tokens(self) -> int:
        """Get currently available tokens."""
        return int(self.tokens)


class BandwidthLimiter:
    """
    Bandwidth limiter using token bucket algorithm.

    Per-allocation and global limits support.
    """

    def __init__(self, default_limit: Optional[BandwidthLimit] = None):
        """
        Initialize bandwidth limiter.

        Args:
            default_limit: Default bandwidth limit for all allocations
        """
        self.default_limit = default_limit or BandwidthLimit(
            read_bps=3_000_000,  # 3 Mbps
            write_bps=3_000_000,  # 3 Mbps
            burst_bps=6_000_000,  # 6 Mbps burst
        )
        self._limiters: Dict[str, Dict[str, TokenBucket]] = {}
        self._stats: Dict[str, BandwidthStats] = defaultdict(BandwidthStats)
        self._global_read_bucket = TokenBucket(
            rate=100_000_000,  # 100 Mbps global
            capacity=200_000_000,  # 200 MB burst
        )
        self._global_write_bucket = TokenBucket(
            rate=100_000_000,
            capacity=200_000_000,
        )

    async def throttle_read(self, allocation_id: str, size: int) -> bool:
        """
        Throttle read operation.

        Args:
            allocation_id: Allocation ID
            size: Number of bytes to read

        Returns:
            True if read allowed, False if rate limited
        """
        # Check global limit
        if not await self._global_read_bucket.consume(size):
            return False

        # Check per-allocation limit
        limiters = self._limiters.setdefault(allocation_id, {})
        if "read" not in limiters:
            limiters["read"] = TokenBucket(
                rate=self.default_limit.read_bps,
                capacity=self.default_limit.burst_bps,
            )

        if await limiters["read"].consume(size):
            stats = self._stats[allocation_id]
            stats.bytes_read += size
            return True

        return False

    async def throttle_write(self, allocation_id: str, size: int) -> bool:
        """
        Throttle write operation.

        Args:
            allocation_id: Allocation ID
            size: Number of bytes to write

        Returns:
            True if write allowed, False if rate limited
        """
        # Check global limit
        if not await self._global_write_bucket.consume(size):
            return False

        # Check per-allocation limit
        limiters = self._limiters.setdefault(allocation_id, {})
        if "write" not in limiters:
            limiters["write"] = TokenBucket(
                rate=self.default_limit.write_bps,
                capacity=self.default_limit.burst_bps,
            )

        if await limiters["write"].consume(size):
            stats = self._stats[allocation_id]
            stats.bytes_written += size
            return True

        return False

    def set_limit(self, allocation_id: str, limit: BandwidthLimit):
        """
        Set bandwidth limit for an allocation.

        Args:
            allocation_id: Allocation ID
            limit: Bandwidth limit
        """
        limiters = self._limiters.setdefault(allocation_id, {})

        limiters["read"] = TokenBucket(
            rate=limit.read_bps,
            capacity=limit.burst_bps,
        )
        limiters["write"] = TokenBucket(
            rate=limit.write_bps,
            capacity=limit.burst_bps,
        )

    def remove_allocation(self, allocation_id: str):
        """
        Remove bandwidth limiter for allocation.

        Args:
            allocation_id: Allocation ID
        """
        self._limiters.pop(allocation_id, None)
        self._stats.pop(allocation_id, None)

    def get_stats(self, allocation_id: str) -> BandwidthStats:
        """
        Get bandwidth statistics for allocation.

        Args:
            allocation_id: Allocation ID

        Returns:
            Bandwidth statistics
        """
        return self._stats.get(allocation_id, BandwidthStats())

    def get_global_stats(self) -> Dict[str, int]:
        """
        Get global bandwidth statistics.

        Returns:
            Dictionary with global stats
        """
        return {
            "available_read_tokens": self._global_read_bucket.get_available_tokens(),
            "available_write_tokens": self._global_write_bucket.get_available_tokens(),
            "active_allocations": len(self._limiters),
        }


class ThroughputMonitor:
    """
    Monitor throughput rates.

    Tracks bytes transferred and calculates current rates.
    """

    def __init__(self, window_seconds: int = 5):
        """
        Initialize throughput monitor.

        Args:
            window_seconds: Time window for rate calculation
        """
        self.window = window_seconds
        self._read_samples: list = []
        self._write_samples: list = []
        self._lock = asyncio.Lock()

    async def record_read(self, bytes_count: int):
        """
        Record read operation.

        Args:
            bytes_count: Number of bytes read
        """
        async with self._lock:
            self._read_samples.append((time.time(), bytes_count))
            await self._cleanup_old_samples()

    async def record_write(self, bytes_count: int):
        """
        Record write operation.

        Args:
            bytes_count: Number of bytes written
        """
        async with self._lock:
            self._write_samples.append((time.time(), bytes_count))
            await self._cleanup_old_samples()

    async def _cleanup_old_samples(self):
        """Remove samples older than window."""
        cutoff = time.time() - self.window

        self._read_samples = [(t, b) for t, b in self._read_samples if t > cutoff]
        self._write_samples = [(t, b) for t, b in self._write_samples if t > cutoff]

    async def get_read_rate(self) -> float:
        """
        Get current read rate (bytes/second).

        Returns:
            Read rate
        """
        async with self._lock:
            await self._cleanup_old_samples()
            if not self._read_samples:
                return 0.0

            total = sum(b for _, b in self._read_samples)
            return total / self.window

    async def get_write_rate(self) -> float:
        """
        Get current write rate (bytes/second).

        Returns:
            Write rate
        """
        async with self._lock:
            await self._cleanup_old_samples()
            if not self._write_samples:
                return 0.0

            total = sum(b for _, b in self._write_samples)
            return total / self.window

    async def get_stats(self) -> Dict[str, float]:
        """
        Get throughput statistics.

        Returns:
            Dictionary with stats
        """
        read_rate = await self.get_read_rate()
        write_rate = await self.get_write_rate()

        return {
            "read_rate_bps": read_rate,
            "write_rate_bps": write_rate,
            "read_rate_mbps": read_rate / 1_000_000,
            "write_rate_mbps": write_rate / 1_000_000,
        }
