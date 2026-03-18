"""
WebSocket message handlers
"""

import asyncio
import logging
import time
import uuid
from typing import Optional

from .models import (
    Message, MessageType, ErrorCode, NATType,
    ConnectionStatus, ErrorResponse
)
from .connection import get_connection_manager
from .config import config

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handle WebSocket messages from clients."""

    def __init__(self):
        """Initialize message handler."""
        self.manager = get_connection_manager()

    async def handle_message(
        self,
        device_id: str,
        message: Message,
    ) -> Optional[dict]:
        """
        Route message to appropriate handler.

        Args:
            device_id: Sender device ID
            message: Received message

        Returns:
            Optional response message
        """
        handlers = {
            MessageType.REGISTER: self._handle_register,
            MessageType.UNREGISTER: self._handle_unregister,
            MessageType.CONNECT: self._handle_connect,
            MessageType.OFFER: self._handle_offer,
            MessageType.ANSWER: self._handle_answer,
            MessageType.ICE_CANDIDATE: self._handle_ice_candidate,
            MessageType.HEARTBEAT: self._handle_heartbeat,
            MessageType.PING: self._handle_ping,
            MessageType.QUERY_DEVICE: self._handle_query_device,
            MessageType.RELAY_REQUEST: self._handle_relay_request,
        }

        handler = handlers.get(message.type)
        if not handler:
            logger.warning(f"Unknown message type: {message.type}")
            return ErrorResponse(
                code=ErrorCode.INVALID_REQUEST,
                message=f"Unknown message type: {message.type}",
            ).to_dict()

        try:
            return await handler(device_id, message)
        except Exception as e:
            logger.error(f"Error handling message {message.type}: {e}")
            return ErrorResponse(
                code=ErrorCode.INTERNAL_ERROR,
                message=str(e),
                request_id=message.request_id,
            ).to_dict()

    async def _handle_register(self, device_id: str, message: Message) -> dict:
        """Handle device registration (handled during connection)."""
        # Device is already registered when WebSocket connects
        return {
            "type": MessageType.REGISTERED.value,
            "data": {"device_id": device_id},
            "timestamp": int(time.time()),
        }

    async def _handle_unregister(self, device_id: str, message: Message) -> dict:
        """Handle device unregistration."""
        await self.manager.disconnect(device_id)
        return {
            "type": MessageType.UNREGISTER.value,
            "data": {"device_id": device_id},
            "timestamp": int(time.time()),
        }

    async def _handle_connect(self, device_id: str, message: Message) -> Optional[dict]:
        """
        Handle connection request to another device.

        Initiates P2P connection between two devices.
        """
        target_device_id = message.data.get("target_device_id")
        if not target_device_id:
            return ErrorResponse(
                code=ErrorCode.INVALID_REQUEST,
                message="Missing target_device_id",
                request_id=message.request_id,
            ).to_dict()

        # Check if target device is connected
        if not self.manager.is_connected(target_device_id):
            return ErrorResponse(
                code=ErrorCode.DEVICE_NOT_FOUND,
                message=f"Target device {target_device_id} not found",
                request_id=message.request_id,
            ).to_dict()

        # Check if session already exists
        existing = self.manager.get_session_by_devices(device_id, target_device_id)
        if existing and existing.status != ConnectionStatus.DISCONNECTED:
            return {
                "type": MessageType.CONNECT_RESPONSE.value,
                "data": {
                    "session_id": existing.session_id,
                    "status": existing.status.value,
                    "existing": True,
                },
                "timestamp": int(time.time()),
                "request_id": message.request_id,
            }

        # Create new session
        session = self.manager.create_session(device_id, target_device_id)
        self.manager.add_pending_request(session.session_id, device_id)

        # Forward connection request to target device
        connect_request = {
            "type": MessageType.CONNECT_REQUEST.value,
            "data": {
                "source_device_id": device_id,
                "session_id": session.session_id,
                "capabilities": message.data.get("capabilities", []),
            },
            "timestamp": int(time.time()),
            "request_id": str(uuid.uuid4()),
        }

        sent = await self.manager.send_message(target_device_id, connect_request)

        if not sent:
            return ErrorResponse(
                code=ErrorCode.CONNECTION_FAILED,
                message="Failed to reach target device",
                request_id=message.request_id,
            ).to_dict()

        return {
            "type": MessageType.CONNECT_RESPONSE.value,
            "data": {
                "session_id": session.session_id,
                "status": ConnectionStatus.CONNECTING.value,
            },
            "timestamp": int(time.time()),
            "request_id": message.request_id,
        }

    async def _handle_offer(self, device_id: str, message: Message) -> dict:
        """
        Handle SDP offer from caller.

        Forwards offer to callee.
        """
        session_id = message.data.get("session_id")
        offer = message.data.get("offer")

        if not session_id or not offer:
            return ErrorResponse(
                code=ErrorCode.INVALID_REQUEST,
                message="Missing session_id or offer",
                request_id=message.request_id,
            ).to_dict()

        session = self.manager.get_session(session_id)
        if not session:
            return ErrorResponse(
                code=ErrorCode.INVALID_REQUEST,
                message="Invalid session_id",
                request_id=message.request_id,
            ).to_dict()

        # Store offer
        self.manager.set_session_offer(session_id, offer)

        # Determine target (other device in session)
        target_device_id = session.device_b if device_id == session.device_a else session.device_a

        # Forward offer
        offer_msg = {
            "type": MessageType.OFFER.value,
            "data": {
                "session_id": session_id,
                "offer": offer,
                "source_device_id": device_id,
            },
            "timestamp": int(time.time()),
        }

        await self.manager.send_message(target_device_id, offer_msg)

        return {
            "type": MessageType.OFFER.value,
            "data": {"session_id": session_id, "status": "forwarded"},
            "timestamp": int(time.time()),
            "request_id": message.request_id,
        }

    async def _handle_answer(self, device_id: str, message: Message) -> dict:
        """
        Handle SDP answer from callee.

        Forwards answer to caller.
        """
        session_id = message.data.get("session_id")
        answer = message.data.get("answer")

        if not session_id or not answer:
            return ErrorResponse(
                code=ErrorCode.INVALID_REQUEST,
                message="Missing session_id or answer",
                request_id=message.request_id,
            ).to_dict()

        session = self.manager.get_session(session_id)
        if not session:
            return ErrorResponse(
                code=ErrorCode.INVALID_REQUEST,
                message="Invalid session_id",
                request_id=message.request_id,
            ).to_dict()

        # Store answer
        self.manager.set_session_answer(session_id, answer)

        # Determine target (other device in session)
        target_device_id = session.device_a if device_id == session.device_b else session.device_b

        # Forward answer
        answer_msg = {
            "type": MessageType.ANSWER.value,
            "data": {
                "session_id": session_id,
                "answer": answer,
                "source_device_id": device_id,
            },
            "timestamp": int(time.time()),
        }

        await self.manager.send_message(target_device_id, answer_msg)

        # Update session status
        self.manager.update_session_status(session_id, ConnectionStatus.CONNECTED)

        return {
            "type": MessageType.ANSWER.value,
            "data": {"session_id": session_id, "status": "forwarded"},
            "timestamp": int(time.time()),
            "request_id": message.request_id,
        }

    async def _handle_ice_candidate(self, device_id: str, message: Message) -> dict:
        """
        Handle ICE candidate.

        Forwards candidate to the other peer.
        """
        session_id = message.data.get("session_id")
        candidate = message.data.get("candidate")
        sdp_mid = message.data.get("sdpMid")
        sdp_mline_index = message.data.get("sdpMLineIndex")

        if not session_id or not candidate:
            return ErrorResponse(
                code=ErrorCode.INVALID_REQUEST,
                message="Missing session_id or candidate",
                request_id=message.request_id,
            ).to_dict()

        session = self.manager.get_session(session_id)
        if not session:
            return ErrorResponse(
                code=ErrorCode.INVALID_REQUEST,
                message="Invalid session_id",
                request_id=message.request_id,
            ).to_dict()

        # Store candidate
        candidate_data = {
            "candidate": candidate,
            "sdpMid": sdp_mid,
            "sdpMLineIndex": sdp_mline_index,
        }
        self.manager.add_ice_candidate(session_id, device_id, candidate_data)

        # Forward to target
        target_device_id = session.device_b if device_id == session.device_a else session.device_a

        ice_msg = {
            "type": MessageType.ICE_CANDIDATE.value,
            "data": {
                "session_id": session_id,
                "candidate": candidate,
                "sdpMid": sdp_mid,
                "sdpMLineIndex": sdp_mline_index,
                "source_device_id": device_id,
            },
            "timestamp": int(time.time()),
        }

        await self.manager.send_message(target_device_id, ice_msg)

        return {
            "type": MessageType.ICE_CANDIDATE.value,
            "data": {"session_id": session_id, "status": "forwarded"},
            "timestamp": int(time.time()),
            "request_id": message.request_id,
        }

    async def _handle_heartbeat(self, device_id: str, message: Message) -> dict:
        """Handle heartbeat message."""
        await self.manager.update_heartbeat(device_id)

        return {
            "type": MessageType.HEARTBEAT_ACK.value,
            "data": {"device_id": device_id},
            "timestamp": int(time.time()),
        }

    async def _handle_ping(self, device_id: str, message: Message) -> dict:
        """Handle ping message."""
        return {
            "type": MessageType.PONG.value,
            "data": {"device_id": device_id},
            "timestamp": int(time.time()),
        }

    async def _handle_query_device(self, device_id: str, message: Message) -> dict:
        """
        Handle query for device information.

        Returns info about whether a device is online and its capabilities.
        """
        target_device_id = message.data.get("target_device_id")
        if not target_device_id:
            return ErrorResponse(
                code=ErrorCode.INVALID_REQUEST,
                message="Missing target_device_id",
                request_id=message.request_id,
            ).to_dict()

        device = self.manager.get_device(target_device_id)

        if not device:
            return {
                "type": MessageType.DEVICE_INFO.value,
                "data": {
                    "device_id": target_device_id,
                    "online": False,
                },
                "timestamp": int(time.time()),
                "request_id": message.request_id,
            }

        return {
            "type": MessageType.DEVICE_INFO.value,
            "data": {
                "device_id": target_device_id,
                "online": True,
                "capabilities": device.capabilities,
                "nat_type": device.nat_type.value,
            },
            "timestamp": int(time.time()),
            "request_id": message.request_id,
        }

    async def _handle_relay_request(self, device_id: str, message: Message) -> dict:
        """
        Handle request to use relay server.

        Called when P2P connection fails.
        """
        session_id = message.data.get("session_id")
        if not session_id:
            return ErrorResponse(
                code=ErrorCode.INVALID_REQUEST,
                message="Missing session_id",
                request_id=message.request_id,
            ).to_dict()

        session = self.manager.get_session(session_id)
        if not session:
            return ErrorResponse(
                code=ErrorCode.INVALID_REQUEST,
                message="Invalid session_id",
                request_id=message.request_id,
            ).to_dict()

        # Mark session to use relay
        self.manager.set_relay_mode(session_id)

        # Notify both devices
        relay_msg = {
            "type": MessageType.RELAY_RESPONSE.value,
            "data": {
                "session_id": session_id,
                "use_relay": True,
                "relay_info": {
                    # This would come from relay server
                    "host": "relay.example.com",
                    "port": 50000,
                },
            },
            "timestamp": int(time.time()),
        }

        await self.manager.send_message(session.device_a, relay_msg)
        await self.manager.send_message(session.device_b, relay_msg)

        return {
            "type": MessageType.RELAY_RESPONSE.value,
            "data": {"session_id": session_id, "status": "requested"},
            "timestamp": int(time.time()),
            "request_id": message.request_id,
        }
