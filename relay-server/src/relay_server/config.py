"""
Relay Server Configuration
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Relay server configuration."""

    # Server settings
    host: str = os.getenv("RELAY_HOST", "0.0.0.0")
    port: int = int(os.getenv("RELAY_PORT", "5000"))
    api_port: int = int(os.getenv("RELAY_API_PORT", "5001"))

    # Port pool settings
    min_port: int = int(os.getenv("RELAY_MIN_PORT", "50000"))
    max_port: int = int(os.getenv("RELAY_MAX_PORT", "50100"))

    # Allocation settings
    allocation_lifetime: int = int(os.getenv("RELAY_ALLOCATION_LIFETIME", "600"))
    max_allocations: int = int(os.getenv("RELAY_MAX_ALLOCATIONS", "1000"))

    # Rate limiting
    bandwidth_limit: int = int(os.getenv("RELAY_BANDWIDTH_LIMIT", "10485760"))  # 10MB/s
    packet_rate_limit: int = int(os.getenv("RELAY_PACKET_RATE_LIMIT", "1000"))  # packets/s

    # Performance monitoring
    enable_metrics: bool = os.getenv("RELAY_ENABLE_METRICS", "true").lower() == "true"
    metrics_port: int = int(os.getenv("RELAY_METRICS_PORT", "9090"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
