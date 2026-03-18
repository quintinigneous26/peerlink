"""
Relay Server Bandwidth Control Tests
"""

import asyncio
import pytest

from src.bandwidth import (
    BandwidthLimit,
    BandwidthLimiter,
    BandwidthStats,
    ThroughputMonitor,
    TokenBucket,
)


@pytest.mark.asyncio
class TestTokenBucket:
    """Test token bucket rate limiter."""

    async def test_token_bucket_consume(self):
        """Test consuming tokens."""
        bucket = TokenBucket(rate=1000, capacity=5000)

        # Initial tokens should equal capacity
        assert bucket.get_available_tokens() == 5000

        # Consume some tokens
        success = await bucket.consume(1000)
        assert success is True
        assert bucket.get_available_tokens() == 4000

    async def test_token_bucket_rate_limit(self):
        """Test rate limiting."""
        bucket = TokenBucket(rate=1000, capacity=1000)

        # Consume all tokens
        success = await bucket.consume(1000)
        assert success is True

        # Should be rate limited
        success = await bucket.consume(1)
        assert success is False

        # Wait for refill
        await asyncio.sleep(0.1)

        # Should have some tokens now
        success = await bucket.consume(50)
        assert success is True

    async def test_token_bucket_wait_for_tokens(self):
        """Test waiting for tokens."""
        bucket = TokenBucket(rate=1000, capacity=1000)

        # Consume all tokens
        await bucket.consume(1000)

        # Wait for tokens (should take about 0.5 seconds for 500 tokens)
        start = asyncio.get_event_loop().time()
        success = await bucket.wait_for_tokens(500)
        elapsed = asyncio.get_event_loop().time() - start

        assert success is True
        assert elapsed >= 0.4  # Should have waited

    async def test_token_bucket_refill(self):
        """Test token refill over time."""
        bucket = TokenBucket(rate=1000, capacity=2000)

        # Consume half
        await bucket.consume(1000)

        # Wait for refill
        await asyncio.sleep(0.5)

        # Should have approximately 1500 tokens (initial - consumed + refill)
        tokens = bucket.get_available_tokens()
        assert 1400 <= tokens <= 1600  # Allow some variance


@pytest.mark.asyncio
class TestBandwidthLimiter:
    """Test bandwidth limiter."""

    async def test_limiter_read(self):
        """Test read throttling."""
        limiter = BandwidthLimiter(
            BandwidthLimit(read_bps=1000, write_bps=1000, burst_bps=2000)
        )

        # Should succeed initially
        success = await limiter.throttle_read("alloc-1", 500)
        assert success is True

        # Still within burst
        success = await limiter.throttle_read("alloc-1", 1000)
        assert success is True

    async def test_limiter_write(self):
        """Test write throttling."""
        limiter = BandwidthLimiter(
            BandwidthLimit(read_bps=1000, write_bps=1000, burst_bps=2000)
        )

        # Should succeed initially
        success = await limiter.throttle_write("alloc-1", 500)
        assert success is True

        # Still within burst
        success = await limiter.throttle_write("alloc-1", 1000)
        assert success is True

    async def test_limiter_rate_limit(self):
        """Test rate limiting behavior."""
        limiter = BandwidthLimiter(
            BandwidthLimit(read_bps=100, write_bps=100, burst_bps=100)
        )

        # Consume all burst
        success = await limiter.throttle_read("alloc-1", 100)
        assert success is True

        # Should be rate limited
        success = await limiter.throttle_read("alloc-1", 1)
        assert success is False

    async def test_limiter_stats(self):
        """Test bandwidth statistics."""
        limiter = BandwidthLimiter(
            BandwidthLimit(read_bps=10000, write_bps=10000, burst_bps=20000)
        )

        await limiter.throttle_read("alloc-1", 1000)
        await limiter.throttle_write("alloc-1", 2000)

        stats = limiter.get_stats("alloc-1")
        assert stats.bytes_read == 1000
        assert stats.bytes_written == 2000

    async def test_limiter_set_limit(self):
        """Test setting custom limit."""
        limiter = BandwidthLimiter()

        custom_limit = BandwidthLimit(read_bps=500, write_bps=500, burst_bps=1000)
        limiter.set_limit("alloc-1", custom_limit)

        # Should use custom limit
        success = await limiter.throttle_read("alloc-1", 600)
        assert success is False  # Over burst

    async def test_limiter_remove_allocation(self):
        """Test removing allocation."""
        limiter = BandwidthLimiter()

        await limiter.throttle_read("alloc-1", 100)

        # Remove allocation
        limiter.remove_allocation("alloc-1")

        # Stats should be cleared
        stats = limiter.get_stats("alloc-1")
        assert stats.bytes_read == 0

    async def test_global_stats(self):
        """Test global statistics."""
        limiter = BandwidthLimiter()

        stats = limiter.get_global_stats()
        assert "available_read_tokens" in stats
        assert "available_write_tokens" in stats
        assert "active_allocations" in stats


@pytest.mark.asyncio
class TestThroughputMonitor:
    """Test throughput monitor."""

    async def test_monitor_record(self):
        """Test recording throughput."""
        monitor = ThroughputMonitor(window_seconds=5)

        await monitor.record_read(1000)
        await monitor.record_write(2000)

        # Stats should be available
        stats = await monitor.get_stats()
        assert stats["read_rate_bps"] >= 0
        assert stats["write_rate_bps"] >= 0

    async def test_monitor_rate_calculation(self):
        """Test rate calculation."""
        monitor = ThroughputMonitor(window_seconds=1)

        # Record some reads
        for _ in range(5):
            await monitor.record_read(100)
            await asyncio.sleep(0.1)

        # Get rate
        rate = await monitor.get_read_rate()
        # Should be around 500 bytes/sec (5 * 100 / 1 sec)
        assert 300 <= rate <= 700  # Allow variance

    async def test_monitor_window_cleanup(self):
        """Test old sample cleanup."""
        monitor = ThroughputMonitor(window_seconds=1)

        # Record samples
        await monitor.record_read(1000)

        # Wait for window to expire
        await asyncio.sleep(1.1)

        # Rate should be zero now
        rate = await monitor.get_read_rate()
        assert rate == 0.0

    async def test_monitor_stats_dict(self):
        """Test statistics dictionary."""
        monitor = ThroughputMonitor()

        await monitor.record_read(1_000_000)  # 1 MB
        await monitor.record_write(2_000_000)  # 2 MB

        stats = await monitor.get_stats()
        assert "read_rate_bps" in stats
        assert "write_rate_bps" in stats
        assert "read_rate_mbps" in stats
        assert "write_rate_mbps" in stats
