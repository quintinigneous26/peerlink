"""
Signaling Server - FastAPI application
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status, HTTPException, Query
from fastapi.responses import JSONResponse

from .config import config
from .models import Message, MessageType, ErrorResponse, ErrorCode, DeviceInfo
from .connection import get_connection_manager
from .handlers import MessageHandler

logger = logging.getLogger(__name__)


# ===== Lifespan Management =====


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    logger.info("Starting Signaling Server...")

    # Start heartbeat cleanup task
    manager = get_connection_manager()

    async def cleanup_task():
        """Periodically cleanup stale connections."""
        while True:
            await asyncio.sleep(config.heartbeat_interval)
            cleaned = await manager.cleanup_stale(config.connection_timeout)
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} stale connections")

    cleanup = asyncio.create_task(cleanup_task())

    logger.info(f"Signaling Server started on ws://{config.host}:{config.ws_port}")

    yield

    # Shutdown
    logger.info("Shutting down Signaling Server...")
    cleanup.cancel()
    logger.info("Signaling Server shut down")


# ===== Application =====


app = FastAPI(
    title="Signaling Server",
    description="WebSocket signaling server for P2P connection coordination",
    version="0.1.0",
    lifespan=lifespan,
)


# ===== REST Endpoints =====


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    manager = get_connection_manager()
    return {
        "status": "healthy",
        "service": "signaling-server",
        "connected_devices": len(manager.get_all_devices()),
    }


@app.get("/api/v1/devices")
async def list_devices():
    """List all connected devices."""
    manager = get_connection_manager()
    devices = []

    for device_id in manager.get_all_devices():
        device = manager.get_device(device_id)
        if device:
            devices.append(device.to_dict())

    return {
        "success": True,
        "data": {
            "devices": devices,
            "count": len(devices),
        },
        "timestamp": int(asyncio.get_event_loop().time()),
    }


@app.get("/api/v1/devices/{device_id}")
async def get_device_info(device_id: str):
    """Get information about a specific device."""
    manager = get_connection_manager()
    device = manager.get_device(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    return {
        "success": True,
        "data": device.to_dict(),
        "timestamp": int(asyncio.get_event_loop().time()),
    }


@app.get("/api/v1/sessions")
async def list_sessions():
    """List all active connection sessions."""
    manager = get_connection_manager()

    sessions = []
    for session_id, session in manager._sessions.items():
        sessions.append(session.to_dict())

    return {
        "success": True,
        "data": {
            "sessions": sessions,
            "count": len(sessions),
        },
        "timestamp": int(asyncio.get_event_loop().time()),
    }


# ===== WebSocket Endpoint =====


@app.websocket("/v1/signaling")
async def websocket_endpoint(
    websocket: WebSocket,
    device_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for device signaling.

    Query parameters:
    - device_id: Device identifier (required)
    - token: Optional authentication token
    """
    manager = get_connection_manager()
    handler = MessageHandler()

    # Validate device_id
    if not device_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # TODO: Verify token with DID service if provided

    # Accept connection
    await websocket.accept()

    logger.info(f"WebSocket connection request from {device_id}")

    try:
        # Register device (temporary - will be replaced by proper register message)
        device_info = await manager.connect(
            device_id=device_id,
            ws=websocket,
            public_key="",  # Will be filled in register message
            capabilities=[],
        )

        # Send registration confirmation
        await websocket.send_json({
            "type": MessageType.REGISTERED.value,
            "data": {
                "device_id": device_id,
                "server_time": int(asyncio.get_event_loop().time()),
            },
        })

        # Message loop
        while True:
            try:
                # Receive message with timeout
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=config.ping_timeout,
                )

                # Parse message
                message = Message.from_dict(data)

                # Set source device ID
                message.source_device_id = device_id

                # Handle message
                response = await handler.handle_message(device_id, message)

                # Send response if any
                if response:
                    await websocket.send_json(response)

            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_json({
                    "type": MessageType.PING.value,
                    "data": {},
                    "timestamp": int(asyncio.get_event_loop().time()),
                })

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {device_id}")
                break

            except Exception as e:
                logger.error(f"Error processing message from {device_id}: {e}")

                # Send error response
                error = ErrorResponse(
                    code=ErrorCode.INTERNAL_ERROR,
                    message=str(e),
                )
                try:
                    await websocket.send_json(error.to_dict())
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected during handshake: {device_id}")

    except Exception as e:
        logger.error(f"WebSocket error for {device_id}: {e}")

    finally:
        # Cleanup
        await manager.disconnect(device_id)
        logger.info(f"Connection closed for {device_id}")
