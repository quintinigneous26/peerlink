"""
Relay Server - FastAPI application
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, status, Query
from pydantic import BaseModel, Field

from .config import config
from .models import RelaySession, APIResponse, TransportProtocol
from .relay import get_relay_handler
from .allocation import AllocationManager

logger = logging.getLogger(__name__)


# ===== Request/Response Models =====


class AllocationRequest(BaseModel):
    """Request to allocate a relay session."""

    device_id: str = Field(..., description="Device identifier")
    transport: str = Field(default="udp", description="Transport protocol")
    lifetime: int = Field(default=600, description="Session lifetime in seconds")


class RefreshRequest(BaseModel):
    """Request to refresh a relay session."""

    allocation_id: str = Field(..., description="Allocation ID")
    lifetime: int = Field(default=600, description="New lifetime in seconds")


class PermissionRequest(BaseModel):
    """Request to add peer permission."""

    allocation_id: str = Field(..., description="Allocation ID")
    peer_ip: str = Field(..., description="Peer IP address")
    peer_port: int = Field(..., description="Peer port")


# ===== Lifespan Management =====


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    logger.info("Starting Relay Server...")

    # Start components
    relay_handler = get_relay_handler()
    await relay_handler.start(config.host, (config.min_port, config.max_port))

    # Start cleanup task
    async def cleanup_task():
        """Periodically cleanup expired sessions."""
        while True:
            await asyncio.sleep(60)
            await relay_handler.cleanup_expired()

    cleanup = asyncio.create_task(cleanup_task())

    logger.info(f"Relay Server started on {config.host}:{config.port}")

    yield

    # Shutdown
    logger.info("Shutting down Relay Server...")
    cleanup.cancel()
    await relay_handler.stop()
    logger.info("Relay Server shut down")


# ===== Application =====


app = FastAPI(
    title="Relay Server",
    description="TURN-like relay server for P2P connections",
    version="0.1.0",
    lifespan=lifespan,
)


# ===== Health Check =====


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    handler = get_relay_handler()
    stats = handler.get_stats()

    return {
        "status": "healthy",
        "service": "relay-server",
        "active_sessions": stats["active_sessions"],
    }


# ===== REST Endpoints =====


@app.post("/api/v1/relay/allocate")
async def allocate_relay(request: AllocationRequest):
    """
    Allocate a relay session.

    Creates a new relay allocation for the device.
    """
    handler = get_relay_handler()

    # For this API, we use device_id to identify client
    # In production, this would use the actual client IP:port from the connection
    import uuid
    client_addr = (request.device_id, 0)  # Simplified

    # Get available port
    import socket
    sock = socket.socket()
    sock.bind((config.host, 0))
    relay_port = sock.getsockname()[1]
    sock.close()

    relay_addr = (config.host, relay_port)

    session = await handler.create_session(
        client_addr=client_addr,
        relay_addr=relay_addr,
        lifetime=request.lifetime,
        transport=TransportProtocol(request.transport),
    )

    if not session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to allocate relay session",
        )

    response = APIResponse(
        success=True,
        data={
            "allocation_id": session.session_id,
            "relay_addr": f"{relay_addr[0]}:{relay_addr[1]}",
            "relay_host": relay_addr[0],
            "relay_port": relay_addr[1],
            "lifetime": session.lifetime,
            "transport": session.transport.value,
            "expires_at": session.created_at + session.lifetime,
        },
    )

    return response.to_dict()


@app.post("/api/v1/relay/refresh")
async def refresh_allocation(request: RefreshRequest):
    """
    Refresh a relay session.

    Extends the lifetime of an existing allocation.
    """
    handler = get_relay_handler()
    session = await handler.get_session(request.allocation_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allocation not found",
        )

    # Update lifetime (simulated)
    import time
    session.created_at = int(time.time())
    session.update_activity()

    response = APIResponse(
        success=True,
        data={
            "allocation_id": session.session_id,
            "lifetime": session.lifetime,
            "expires_at": session.created_at + session.lifetime,
        },
    )

    return response.to_dict()


@app.post("/api/v1/relay/permission")
async def add_permission(request: PermissionRequest):
    """
    Add permission for a peer.

    Allows a specific peer to send data through the relay.
    """
    handler = get_relay_handler()
    session = await handler.get_session(request.allocation_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allocation not found",
        )

    peer_addr = (request.peer_ip, request.peer_port)
    added = await handler.add_permission(request.allocation_id, peer_addr)

    if not added:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission already exists or failed to add",
        )

    response = APIResponse(
        success=True,
        data={
            "allocation_id": request.allocation_id,
            "peer_addr": f"{peer_addr[0]}:{peer_addr[1]}",
        },
    )

    return response.to_dict()


@app.delete("/api/v1/relay/{allocation_id}")
async def delete_allocation(allocation_id: str):
    """
    Delete a relay session.

    Releases the relay port and cleans up resources.
    """
    handler = get_relay_handler()
    deleted = await handler.delete_session(allocation_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allocation not found",
        )

    response = APIResponse(
        success=True,
        data={"allocation_id": allocation_id},
    )

    return response.to_dict()


@app.get("/api/v1/relay/{allocation_id}")
async def get_allocation(allocation_id: str):
    """
    Get information about a relay session.
    """
    handler = get_relay_handler()
    session = await handler.get_session(allocation_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allocation not found",
        )

    import time
    remaining = max(0, session.lifetime - (time.time() - session.created_at))

    response = APIResponse(
        success=True,
        data={
            "allocation_id": session.session_id,
            "client_addr": session.client_addr,
            "relay_addr": session.relay_addr,
            "peer_addr": session.peer_addr,
            "transport": session.transport.value,
            "status": session.status.value,
            "lifetime": session.lifetime,
            "remaining": int(remaining),
            "bytes_sent": session.bytes_sent,
            "bytes_received": session.bytes_received,
            "packets_sent": session.packets_sent,
            "packets_received": session.packets_received,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
        },
    )

    return response.to_dict()


@app.get("/api/v1/relay")
async def list_allocations():
    """
    List all active relay sessions.
    """
    handler = get_relay_handler()
    stats = handler.get_stats()

    sessions = []
    for session_id, session in handler._sessions.items():
        import time
        remaining = max(0, session.lifetime - (time.time() - session.created_at))
        sessions.append({
            "allocation_id": session_id,
            "client_addr": f"{session.client_addr[0]}:{session.client_addr[1]}",
            "relay_addr": f"{session.relay_addr[0]}:{session.relay_addr[1]}",
            "status": session.status.value,
            "remaining": int(remaining),
        })

    response = APIResponse(
        success=True,
        data={
            "sessions": sessions,
            "count": len(sessions),
            "stats": stats,
        },
    )

    return response.to_dict()


@app.get("/api/v1/metrics")
async def get_metrics():
    """
    Get relay server metrics.
    """
    handler = get_relay_handler()
    stats = handler.get_stats()

    return {
        "active_sessions": stats["active_sessions"],
        "total_bytes_sent": stats["total_bytes_sent"],
        "total_bytes_received": stats["total_bytes_received"],
        "total_packets": stats["total_packets"],
        "current_bandwidth_bps": stats["current_bandwidth_bps"],
        "peak_bandwidth_bps": stats["peak_bandwidth_bps"],
    }
