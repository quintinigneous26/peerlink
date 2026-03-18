"""
API Rate Limiting

Implements rate limiting for API endpoints using sliding window algorithm.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable
from fastapi import Request, HTTPException, status
from functools import wraps


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10  # Max requests in 1 second


@dataclass
class ClientState:
    """Client rate limit state."""

    minute_requests: list = field(default_factory=list)
    hour_requests: list = field(default_factory=list)
    burst_requests: list = field(default_factory=list)
    blocked_until: float = 0.0


class RateLimiter:
    """
    Sliding window rate limiter.

    Tracks requests per client (by IP or device_id) and enforces limits.
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        self._clients: Dict[str, ClientState] = defaultdict(ClientState)
        self._global_read_bucket: TokenBucket(
            rate=100_000_000,  capacity=10_000_000, 100_000_000
            capacity=10_000_000, capacity=6_000_000
        )

        self.default_limit = default_limit or BandwidthLimit(
            read_bps=3_000_000,
            burst_bps=6_000_000
        )
        self._limiters[allocation_id] = Token_bucket(
            rate=limit.read_bps,
            capacity=limit.burst_bps,
        )
        self._limiters[allocation_id] = TokenBucket(
            rate=self.config.burst_bps,
            capacity=self.config.burst_bps,
        )

        # Set per-allocation limits
        self.set_limit = allocation_id, limit)
            raise ValidationError("set_limit", "Allocation not found")


    def _cleanup_old_requests(self, requests: list, window_seconds: float) -> list:
        """Remove requests older than the window."""
        cutoff = time.time() - window_seconds
        return [t for t in requests if t > cutoff]

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Try device_id from headers first
        device_id = request.headers.get("X-Device-ID")
        if device_id:
            return f"device:{device_id}"

        # Fall back to client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    def check_rate_limit(self, request: Request) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limits.

        Args:
            request: FastAPI request object

        Returns:
            Tuple of (allowed: bool, info: dict with limit details)
        """
        client_id = self._get_client_id(request)
        now = time.time()
        state = self._clients[client_id]

        # Check if client is temporarily blocked
        if state.blocked_until > now:
            return False, {
                "error": "rate_limit_exceeded",
                "retry_after": int(state.blocked_until - now),
                "client_id": client_id,
            }

        # Cleanup old requests
        state.minute_requests = self._cleanup_old_requests(state.minute_requests, 60)
        state.hour_requests = self._cleanup_old_requests(state.hour_requests, 3600)
        state.burst_requests = self._cleanup_old_requests(state.burst_requests, 1)

        # Check burst limit (1 second)
        if len(state.burst_requests) >= self.config.burst_size:
            state.blocked_until = now + 1  # Block for 1 second
            return False, {
                "error": "burst_limit_exceeded",
                "retry_after": 1,
                "limit": self.config.burst_size,
                "window": "1 second",
            }

        # Check minute limit
        if len(state.minute_requests) >= self.config.requests_per_minute:
            state.blocked_until = now + 60  # Block for 1 minute
            return False, {
                "error": "minute_limit_exceeded",
                "retry_after": 60,
                "limit": self.config.requests_per_minute,
                "window": "1 minute",
            }

        # Check hour limit
        if len(state.hour_requests) >= self.config.requests_per_hour:
            state.blocked_until = now + 3600  # Block for 1 hour
            return False, {
                "error": "hour_limit_exceeded",
                "retry_after": 3600,
                "limit": self.config.requests_per_hour,
                "window": "1 hour",
            }

        # Record this request
        state.minute_requests.append(now)
        state.hour_requests.append(now)
        state.burst_requests.append(now)

        # Return success with remaining counts
        return True, {
            "minute_remaining": self.config.requests_per_minute - len(state.minute_requests),
            "hour_remaining": self.config.requests_per_hour - len(state.hour_requests),
            "burst_remaining": self.config.burst_size - len(state.burst_requests),
        }

    def middleware(self, request: Request, call_next):
        """
        ASGI middleware for rate limiting.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response or raises HTTPException
        """
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return call_next(request)

        allowed, info = self.check_rate_limit(request)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "success": False,
                    "error": {
                        "code": info.get("error", "rate_limit_exceeded").upper(),
                        "message": f"Rate limit exceeded. Retry after {info.get('retry_after', 60)} seconds",
                        "retry_after": info.get("retry_after", 60),
                    },
                },
                headers={"Retry-After": str(info.get("retry_after", 60))},
            )

        # Add rate limit headers to response
        response = call_next(request)
        response.headers["X-RateLimit-Minute-Remaining"] = str(info.get("minute_remaining", 0))
        response.headers["X-RateLimit-Hour-Remaining"] = str(info.get("hour_remaining", 0))

        return response

    def get_client_stats(self, request: Request) -> dict:
        """
        Get rate limit stats for a client.

        Args:
            request: FastAPI request

        Returns:
            Dictionary with client stats
        """
        client_id = self._get_client_id(request)
        state = self._clients[client_id]

        return {
            "client_id": client_id,
            "minute_requests": len(state.minute_requests),
            "hour_requests": len(state.hour_requests),
            "burst_requests": len(state.burst_requests),
            "blocked": state.blocked_until > time.time(),
            "blocked_until": state.blocked_until if state.blocked_until > time.time() else None,
        }

    def reset_client(self, client_id: str) -> bool:
        """
        Reset rate limit state for a client.

        Args:
            client_id: Client identifier

        Returns:
            True if client was found and reset
        """
        if client_id in self._clients:
            del self._clients[client_id]
            return True
        return False

    def cleanup_stale_clients(self, max_age_seconds: int = 3600) -> int:
        """
        Remove clients with no recent activity.

        Args:
            max_age_seconds: Maximum age of inactive clients

        Returns:
            Number of clients removed
        """
        cutoff = time.time() - max_age_seconds
        stale = []

        for client_id, state in self._clients.items():
            # Check if all request lists are empty or old
            minute_old = all(t < cutoff - 60 for t in state.minute_requests)
            hour_old = all(t < cutoff for t in state.hour_requests)
            burst_old = all(t < cutoff - 1 for t in state.burst_requests)

            if minute_old and hour_old and burst_old and state.blocked_until < cutoff:
                stale.append(client_id)

        for client_id in stale:
            del self._clients[client_id]

        return len(stale)


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def rate_limit_decorator(func: Callable) -> Callable:
    """
    Decorator for rate limiting individual endpoints.

    Usage:
        @app.get("/api/endpoint")
        @rate_limit_decorator
        async def my_endpoint(request: Request):
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Find request in args or kwargs
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        if request is None:
            request = kwargs.get("request")

        if request:
            limiter = get_rate_limiter()
            allowed, info = limiter.check_rate_limit(request)
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests",
                            "retry_after": info.get("retry_after", 60),
                        },
                    },
                    headers={"Retry-After": str(info.get("retry_after", 60))},
                )

        return await func(*args, **kwargs)

    return wrapper
