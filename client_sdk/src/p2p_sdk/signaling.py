"""
Signaling Client Implementation

Handles communication with the signaling server for device discovery,
connection coordination, and relay setup.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class SignalingEventType(Enum):
    """Signaling event types."""

    DEVICE_REGISTERED = "device_registered"
    DEVICE_DISCOVERED = "device_discovered"
    CONNECTION_REQUEST = "connection_request"
    CONNECTION_ACCEPTED = "connection_accepted"
    CONNECTION_REJECTED = "connection_rejected"
    PEER_CONNECTED = "peer_connected"
    PEER_DISCONNECTED = "peer_disconnected"
    RELAY_REQUESTED = "relay_requested"
    ERROR = "error"


@dataclass
class SignalingEvent:
    """Signaling event from server."""

    event_type: SignalingEventType
    data: Dict[str, Any]


class SignalingClient:
    """
    Client for communicating with the signaling server.

    Handles device registration, discovery, and connection coordination.
    """

    def __init__(
        self,
        server: str,
        port: int,
        did: str,
        use_tls: bool = False,
    ):
        """
        Initialize signaling client.

        Args:
            server: Signaling server hostname
            port: Signaling server port
            did: Device ID
            use_tls: Whether to use TLS/WSS
        """
        self.server = server
        self.port = port
        self.did = did
        self.use_tls = use_tls

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._running = False

        # Event handlers
        self._event_handlers: Dict[SignalingEventType, list] = {}

        # Pending requests
        self._pending: Dict[str, asyncio.Future] = {}
        self._request_id = 0

    async def connect(self) -> None:
        """Connect to signaling server."""
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.server, self.port
            )

            self._connected = True
            self._running = True

            # Start message handler
            asyncio.create_task(self._message_loop())

            # Send hello
            await self._send_request("hello", {"did": self.did})

            logger.info(f"Connected to signaling server {self.server}:{self.port}")

        except Exception as e:
            logger.error(f"Failed to connect to signaling server: {e}")
            raise ConnectionError(f"Signaling connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from signaling server."""
        self._running = False

        if self._writer:
            try:
                await self._send_request("bye", {"did": self.did})
            except (ConnectionError, OSError) as e:
                logger.debug(f"Error sending bye message: {e}")
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (ConnectionError, OSError) as e:
                logger.debug(f"Error waiting for writer close: {e}")

        self._connected = False
        logger.info("Disconnected from signaling server")

    async def register_device(
        self,
        did: str,
        public_ip: str,
        public_port: int,
        nat_type: str = "unknown",
        capabilities: list = None,
    ) -> Dict[str, Any]:
        """
        Register device with signaling server.

        Args:
            did: Device ID
            public_ip: Public IP address
            public_port: Public UDP port
            nat_type: Detected NAT type
            capabilities: List of supported capabilities

        Returns:
            Registration response
        """
        payload = {
            "did": did,
            "public_ip": public_ip,
            "public_port": public_port,
            "nat_type": nat_type,
            "capabilities": capabilities or [],
        }

        return await self._send_request("register", payload)

    async def query_device(self, did: str) -> Dict[str, Any]:
        """
        Query device information from signaling server.

        Args:
            did: Device ID to query

        Returns:
            Device information
        """
        return await self._send_request("query", {"did": did})

    async def request_connection(
        self,
        target_did: str,
        use_relay: bool = False,
    ) -> Dict[str, Any]:
        """
        Request connection to a device.

        Args:
            target_did: Target device ID
            use_relay: Whether to request relay mode

        Returns:
            Connection response with peer info
        """
        payload = {
            "source_did": self.did,
            "target_did": target_did,
            "use_relay": use_relay,
        }

        return await self._send_request("connect_request", payload)

    async def accept_connection(self, request_id: str) -> Dict[str, Any]:
        """
        Accept an incoming connection request.

        Args:
            request_id: Connection request ID

        Returns:
            Accept response
        """
        return await self._send_request("connect_accept", {"request_id": request_id})

    async def reject_connection(self, request_id: str, reason: str = "") -> Dict[str, Any]:
        """
        Reject an incoming connection request.

        Args:
            request_id: Connection request ID
            reason: Rejection reason

        Returns:
            Reject response
        """
        payload = {"request_id": request_id}
        if reason:
            payload["reason"] = reason

        return await self._send_request("connect_reject", payload)

    async def request_relay(self, target_did: str) -> Dict[str, Any]:
        """
        Request relay server for connection.

        Args:
            target_did: Target device ID

        Returns:
            Relay server information
        """
        return await self._send_request(
            "relay_request",
            {"source_did": self.did, "target_did": target_did},
        )

    def on_event(
        self,
        event_type: SignalingEventType,
        handler: Callable[[SignalingEvent], Awaitable[None]],
    ) -> None:
        """
        Register event handler.

        Args:
            event_type: Event type to handle
            handler: Async callback function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    async def _send_request(
        self,
        method: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Send request to signaling server.

        Args:
            method: Request method
            payload: Request payload

        Returns:
            Response data
        """
        if not self._writer or not self._connected:
            raise ConnectionError("Not connected to signaling server")

        # Create request
        self._request_id += 1
        request_id = f"{self.did}_{self._request_id}"

        request = {
            "id": request_id,
            "method": method,
            "payload": payload,
        }

        # Send
        message = json.dumps(request) + "\n"
        self._writer.write(message.encode())
        await self._writer.drain()

        # Wait for response
        future = asyncio.Future()
        self._pending[request_id] = future

        try:
            response = await asyncio.wait_for(future, timeout=10.0)
            return response
        except asyncio.TimeoutError:
            del self._pending[request_id]
            raise TimeoutError(f"Signaling request {method} timed out")
        finally:
            self._pending.pop(request_id, None)

    async def _message_loop(self) -> None:
        """Handle incoming messages from server."""
        while self._running and self._reader:
            try:
                line = await self._reader.readline()

                if not line:
                    break

                message = json.loads(line.decode())
                await self._handle_message(message)

            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON from signaling server: {e}")
            except Exception as e:
                if self._running:
                    logger.error(f"Error in signaling message loop: {e}")
                break

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """Handle incoming message."""
        # Check if it's a response to a request
        if "id" in message and message["id"] in self._pending:
            future = self._pending[message["id"]]
            if not future.done():
                if "error" in message:
                    future.set_exception(ConnectionError(message["error"]))
                else:
                    future.set_result(message.get("result", {}))
            return

        # It's an event/notification
        event_type_str = message.get("event")
        if not event_type_str:
            return

        try:
            event_type = SignalingEventType(event_type_str)
            event = SignalingEvent(
                event_type=event_type,
                data=message.get("data", {}),
            )

            # Trigger handlers
            if event_type in self._event_handlers:
                for handler in self._event_handlers[event_type]:
                    try:
                        await handler(event)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}")

        except ValueError:
            logger.warning(f"Unknown event type: {event_type_str}")


class WebSocketSignalingClient(SignalingClient):
    """
    WebSocket-based signaling client.

    Uses WebSocket instead of raw TCP for signaling communication.
    """

    def __init__(
        self,
        url: str,
        did: str,
    ):
        """
        Initialize WebSocket signaling client.

        Args:
            url: WebSocket server URL (ws:// or wss://)
            did: Device ID
        """
        # Parse URL
        from urllib.parse import urlparse

        parsed = urlparse(url)
        super().__init__(
            server=parsed.hostname,
            port=parsed.port or (443 if parsed.scheme == "wss" else 80),
            did=did,
            use_tls=parsed.scheme == "wss",
        )

        self.url = url
        self._ws: Optional[Any] = None

    async def connect(self) -> None:
        """Connect using WebSocket."""
        try:
            import websockets

            self._ws = await websockets.connect(self.url)
            self._connected = True
            self._running = True

            # Start message handler
            asyncio.create_task(self._ws_message_loop())

            # Send hello
            await self._send_ws_request("hello", {"did": self.did})

            logger.info(f"Connected to signaling server via WebSocket: {self.url}")

        except ImportError:
            raise RuntimeError("websockets package required for WebSocketSignalingClient")
        except Exception as e:
            logger.error(f"Failed to connect to signaling server: {e}")
            raise ConnectionError(f"WebSocket signaling connection failed: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect WebSocket."""
        self._running = False

        if self._ws:
            try:
                await self._send_ws_request("bye", {"did": self.did})
            except (ConnectionError, OSError) as e:
                logger.debug(f"Error sending bye message: {e}")
            await self._ws.close()

        self._connected = False
        logger.info("Disconnected from WebSocket signaling server")

    async def _send_ws_request(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send request via WebSocket."""
        if not self._ws or not self._connected:
            raise ConnectionError("Not connected to signaling server")

        self._request_id += 1
        request_id = f"{self.did}_{self._request_id}"

        request = {
            "id": request_id,
            "method": method,
            "payload": payload,
        }

        await self._ws.send(json.dumps(request))

        future = asyncio.Future()
        self._pending[request_id] = future

        try:
            # Response will be handled in message loop
            response = await asyncio.wait_for(future, timeout=10.0)
            return response
        except asyncio.TimeoutError:
            del self._pending[request_id]
            raise TimeoutError(f"Signaling request {method} timed out")
        finally:
            self._pending.pop(request_id, None)

    async def _ws_message_loop(self) -> None:
        """Handle WebSocket messages."""
        while self._running and self._ws:
            try:
                message_str = await self._ws.recv()
                message = json.loads(message_str)
                await self._handle_message(message)

            except Exception as e:
                if self._running:
                    logger.error(f"Error in WebSocket message loop: {e}")
                break
