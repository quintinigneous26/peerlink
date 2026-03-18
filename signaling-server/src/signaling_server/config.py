"""
Signaling Server Configuration
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Signaling server configuration."""

    # Server settings
    host: str = os.getenv("SIGNALING_HOST", "0.0.0.0")
    ws_port: int = int(os.getenv("SIGNALING_WS_PORT", "8080"))
    wss_port: int = int(os.getenv("SIGNALING_WSS_PORT", "8443"))

    # Redis settings
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: str | None = os.getenv("REDIS_PASSWORD")

    # DID service
    did_service_url: str = os.getenv("DID_SERVICE_URL", "http://localhost:9000")

    # Connection settings
    heartbeat_interval: int = int(os.getenv("HEARTBEAT_INTERVAL", "30"))  # seconds
    connection_timeout: int = int(os.getenv("CONNECTION_TIMEOUT", "300"))  # seconds
    ping_timeout: int = int(os.getenv("PING_TIMEOUT", "20"))  # seconds

    # Message queue size
    message_queue_size: int = int(os.getenv("MESSAGE_QUEUE_SIZE", "100"))

    # ICE settings
    ice_timeout: int = int(os.getenv("ICE_TIMEOUT", "30"))  # seconds

    # Cluster support
    cluster_mode: bool = os.getenv("CLUSTER_MODE", "false").lower() == "true"
    cluster_node_id: str = os.getenv("CLUSTER_NODE_ID", "node-1")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


config = Config()
