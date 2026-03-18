"""
WebSocket connection management
"""

import asyncio
import logging
from typing import Dict, Optional, Set
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from .models import DeviceInfo, Message, ConnectionSession, ConnectionStatus, MessageType, ErrorResponse, ErrorCode
from .config import config

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections and device sessions."""

    def __init__(self):
        """Initialize connection manager."""
        # Active device connections: device_id -> DeviceInfo
        self._devices: Dict[str, DeviceInfo] = {}

        # Active connection sessions: session_id -> ConnectionSession
        self._sessions: Dict[str, ConnectionSession] = {}

        # Pending connection requests: session_id -> requester_device_id
        self._pending_requests: Dict[str, str] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(
        self,
        device_id: str,
        ws: WebSocket,
        public_key: str,
        capabilities: list[str],
        metadata: dict | None = None,
    ) -> DeviceInfo:
        """
        Register a new device connection.

        Args:
            device_id: Device identifier
            ws: WebSocket connection
            public_key: Device public key
            capabilities: List of device capabilities
            metadata: Optional metadata

        Returns:
            DeviceInfo
        """
        async with self._lock:
            # Check if device already connected
            if device_id in self._devices:
                # Close old connection
                old_device = self._devices[device_id]
                try:
                    await old_device.ws.close()
                except Exception:
                    pass

            device = DeviceInfo(
                device_id=device_id,
                ws=ws,
                public_key=public_key,
                capabilities=capabilities,
                metadata=metadata or {},
            )

            self._devices[device_id] = device
            logger.info(f"Device connected: {device_id} ({len(self._devices)} total)")

            return device

    async def disconnect(self, device_id: str) -> None:
        """
        Disconnect a device.

        Args:
            device_id: Device identifier
        """
        async with self._lock:
            if device_id in self._devices:
                device = self._devices[device_id]

                # Close any pending connection requests
                to_remove = [
                    session_id
                    for session_id, requester in self._pending_requests.items()
                    if requester == device_id
                ]
                for session_id in to_remove:
                    del self._pending_requests[session_id]

                # Update related sessions
                for session in self._sessions.values():
                    if session.device_a == device_id or session.device_b == device_id:
                        session.status = ConnectionStatus.DISCONNECTED

                del self._devices[device_id]
                logger.info(f"Device disconnected: {device_id} ({len(self._devices)} total)")

    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """
        Get device info.

        Args:
            device_id: Device identifier

        Returns:
            DeviceInfo or None
        """
        return self._devices.get(device_id)

    def is_connected(self, device_id: str) -> bool:
        """
        Check if device is connected.

        Args:
            device_id: Device identifier

        Returns:
            True if connected
        """
        return device_id in self._devices

    def get_all_devices(self) -> Set[str]:
        """Get set of all connected device IDs."""
        return set(self._devices.keys())

    async def send_message(self, device_id: str, message: dict) -> bool:
        """
        Send a message to a device.

        Args:
            device_id: Target device ID
            message: Message dictionary

        Returns:
            True if sent successfully
        """
        device = self.get_device(device_id)
        if not device:
            return False

        try:
            await device.ws.send_json(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {device_id}: {e}")
            await self.disconnect(device_id)
            return False

    async def broadcast(self, message: dict, exclude: set[str] | None = None) -> int:
        """
        Broadcast a message to all connected devices.

        Args:
            message: Message dictionary
            exclude: Device IDs to exclude

        Returns:
            Number of devices message was sent to
        """
        exclude = exclude or set()
        count = 0

        for device_id in self._devices:
            if device_id not in exclude:
                if await self.send_message(device_id, message):
                    count += 1

        return count

    async def send_error(
        self,
        device_id: str,
        code: ErrorCode,
        message: str,
        request_id: str | None = None,
    ) -> bool:
        """
        Send an error message to a device.

        Args:
            device_id: Target device ID
            code: Error code
            message: Error message
            request_id: Optional request ID

        Returns:
            True if sent successfully
        """
        error = ErrorResponse(code=code.value, message=message, request_id=request_id)
        return await self.send_message(device_id, error.to_dict())

    # ===== Session Management =====

    def create_session(
        self,
        device_a: str,
        device_b: str,
    ) -> ConnectionSession:
        """
        Create a new connection session.

        Args:
            device_a: First device ID
            device_b: Second device ID

        Returns:
            ConnectionSession
        """
        session_id = str(uuid.uuid4())
        session = ConnectionSession(
            session_id=session_id,
            device_a=device_a,
            device_b=device_b,
        )

        self._sessions[session_id] = session
        logger.info(f"Session created: {session_id} between {device_a} and {device_b}")

        return session

    def get_session(self, session_id: str) -> Optional[ConnectionSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def get_session_by_devices(self, device_a: str, device_b: str) -> Optional[ConnectionSession]:
        """Get session between two devices."""
        for session in self._sessions.values():
            if (session.device_a == device_a and session.device_b == device_b) or \
               (session.device_a == device_b and session.device_b == device_a):
                return session
        return None

    def update_session_status(self, session_id: str, status: ConnectionStatus) -> None:
        """Update session status."""
        if session_id in self._sessions:
            self._sessions[session_id].status = status

    def set_session_offer(self, session_id: str, offer: str) -> None:
        """Set session offer (SDP)."""
        if session_id in self._sessions:
            self._sessions[session_id].offer = offer

    def set_session_answer(self, session_id: str, answer: str) -> None:
        """Set session answer (SDP)."""
        if session_id in self._sessions:
            self._sessions[session_id].answer = answer

    def add_ice_candidate(self, session_id: str, device_id: str, candidate: dict) -> None:
        """Add ICE candidate for a device."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            if session.device_a == device_id:
                session.ice_candidates_a.append(candidate)
            elif session.device_b == device_id:
                session.ice_candidates_b.append(candidate)

    def set_relay_mode(self, session_id: str) -> None:
        """Mark session to use relay."""
        if session_id in self._sessions:
            self._sessions[session_id].use_relay = True

    # ===== Pending Requests =====

    def add_pending_request(self, session_id: str, requester: str) -> None:
        """Add a pending connection request."""
        self._pending_requests[session_id] = requester

    def get_pending_requester(self, session_id: str) -> Optional[str]:
        """Get requester for pending connection."""
        return self._pending_requests.get(session_id)

    def remove_pending_request(self, session_id: str) -> None:
        """Remove pending connection request."""
        if session_id in self._pending_requests:
            del self._pending_requests[session_id]

    # ===== Heartbeat =====

    async def update_heartbeat(self, device_id: str) -> bool:
        """
        Update device heartbeat timestamp.

        Args:
            device_id: Device identifier

        Returns:
            True if device exists
        """
        if device_id in self._devices:
            import time
            self._devices[device_id].last_heartbeat = int(time.time())
            return True
        return False

    async def cleanup_stale(self, timeout: int) -> int:
        """
        Clean up stale connections.

        Args:
            timeout: Seconds since last heartbeat

        Returns:
            Number of devices disconnected
        """
        import time
        now = int(time.time())
        count = 0

        async with self._lock:
            to_remove = []
            for device_id, device in self._devices.items():
                if now - device.last_heartbeat > timeout:
                    to_remove.append(device_id)

            for device_id in to_remove:
                await self.disconnect(device_id)
                count += 1

        return count


# Global connection manager
_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get global connection manager instance."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
