"""
P2P Protocol Integration

Integration layer for combining protocol negotiation (multistream-select)
with application protocols (Identify).

This module provides a unified interface for protocol negotiation and
protocol execution, handling the complete flow from handshake to
application-level communication.
"""
import asyncio
import logging
from typing import Optional, Callable, Awaitable, Any, Dict

from .negotiator import ProtocolNegotiator, StreamReaderWriter, NegotiationError
from .identify import IdentifyProtocol, IdentifyMessage, PROTOCOL_ID, PROTOCOL_PUSH_ID
from ..types import ISP, NATType, DeviceVendor


logger = logging.getLogger(__name__)


# ==================== 协议处理器注册表 ====================

class ProtocolHandler:
    """Base class for protocol handlers."""

    async def handle(self, conn: StreamReaderWriter) -> Any:
        """
        Handle the protocol execution.

        Args:
            conn: Connection wrapper

        Returns:
            Protocol-specific result
        """
        raise NotImplementedError


class IdentifyHandler(ProtocolHandler):
    """Handler for Identify protocol."""

    def __init__(
        self,
        protocol_version: str = "/ipfs/0.1.0",
        agent_version: str = "p2p-platform/2.0.0",
        local_info: Optional[IdentifyMessage] = None,
    ):
        self.protocol = IdentifyProtocol(protocol_version, agent_version)
        self.local_info = local_info

    async def handle(self, conn: StreamReaderWriter) -> IdentifyMessage:
        """
        Handle Identify protocol as responder.

        Args:
            conn: Connection wrapper

        Returns:
            Remote peer's Identify message
        """
        # Wrap the connection for Identify protocol
        from .identify import ConnectionWrapper
        identify_conn = ConnectionWrapper(conn.reader, conn.writer)

        # Use provided local info or create default
        if self.local_info is None:
            self.local_info = self.protocol.create_local_info(
                public_key=b"",
                listen_addrs=[],
            )

        # Handle query and send local info
        await self.protocol.handle_query(identify_conn, self.local_info)

        # Return empty remote info (we don't receive in query mode)
        return IdentifyMessage()


# ==================== 统一协议协商接口 ====================

class ProtocolRegistry:
    """
    Registry for supported protocols and their handlers.

    Maps protocol IDs to their handler implementations.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable[[], ProtocolHandler]] = {}

    def register(self, protocol_id: str, handler_factory: Callable[[], ProtocolHandler]) -> None:
        """
        Register a protocol handler.

        Args:
            protocol_id: Protocol ID (e.g., "/ipfs/id/1.0.0")
            handler_factory: Factory function to create handler instances
        """
        self._handlers[protocol_id] = handler_factory
        logger.debug(f"Registered protocol: {protocol_id}")

    def unregister(self, protocol_id: str) -> None:
        """Unregister a protocol."""
        if protocol_id in self._handlers:
            del self._handlers[protocol_id]
            logger.debug(f"Unregistered protocol: {protocol_id}")

    def get_supported_protocols(self) -> list[str]:
        """Get list of supported protocol IDs."""
        return list(self._handlers.keys())

    def create_handler(self, protocol_id: str) -> Optional[ProtocolHandler]:
        """
        Create a handler instance for the given protocol.

        Args:
            protocol_id: Protocol ID

        Returns:
            Handler instance or None if not supported
        """
        factory = self._handlers.get(protocol_id)
        if factory:
            return factory()
        return None

    def is_supported(self, protocol_id: str) -> bool:
        """Check if a protocol is supported."""
        return protocol_id in self._handlers


class ProtocolNegotiationClient:
    """
    High-level client for protocol negotiation and execution.

    Combines multistream-select negotiation with protocol handler execution.
    """

    def __init__(
        self,
        registry: ProtocolRegistry,
        timeout: float = 30.0,
    ):
        """
        Initialize the negotiation client.

        Args:
            registry: Protocol registry
            timeout: Negotiation timeout in seconds
        """
        self.registry = registry
        self.negotiator = ProtocolNegotiator(timeout=timeout)

    async def dial(
        self,
        conn: StreamReaderWriter,
        protocols: list[str],
    ) -> tuple[str, Any]:
        """
        Dial a peer and negotiate a protocol.

        Acts as the initiator in the negotiation.

        Args:
            conn: Connection to the peer
            protocols: Preferred protocols (in priority order)

        Returns:
            Tuple of (negotiated_protocol, handler_result)

        Raises:
            NegotiationError: If negotiation fails
        """
        # Perform protocol negotiation
        protocol = await self.negotiator.negotiate(conn, protocols)
        logger.info(f"Negotiated protocol: {protocol}")

        # Execute the protocol
        handler = self.registry.create_handler(protocol)
        if handler is None:
            raise NegotiationError(f"No handler for protocol: {protocol}")

        result = await handler.handle(conn)
        return protocol, result

    async def accept(
        self,
        conn: StreamReaderWriter,
    ) -> tuple[str, Any]:
        """
        Accept an incoming connection and handle protocol negotiation.

        Acts as the responder in the negotiation.

        Args:
            conn: Incoming connection

        Returns:
            Tuple of (negotiated_protocol, handler_result)

        Raises:
            NegotiationError: If negotiation fails
        """
        supported = self.registry.get_supported_protocols()

        async def protocol_handler(protocol_id: str, conn: StreamReaderWriter):
            """Handler called after successful negotiation."""
            handler = self.registry.create_handler(protocol_id)
            if handler is None:
                raise NegotiationError(f"No handler for protocol: {protocol_id}")
            return await handler.handle(conn)

        # Perform protocol negotiation as responder
        protocol = await self.negotiator.handle_negotiate(
            conn,
            supported,
            protocol_handler,
        )
        logger.info(f"Accepted protocol: {protocol}")

        # Result is already returned by protocol_handler
        return protocol, None


# ==================== Identify 专用客户端 ====================

class IdentifyClient:
    """
    High-level client for Identify protocol operations.

    Provides convenience methods for common Identify operations
    with automatic protocol negotiation.
    """

    def __init__(
        self,
        agent_version: str = "p2p-platform/2.0.0",
        timeout: float = 30.0,
    ):
        """
        Initialize the Identify client.

        Args:
            agent_version: Agent version string
            timeout: Operation timeout in seconds
        """
        self.agent_version = agent_version
        self.protocol = IdentifyProtocol(agent_version=agent_version)
        self.negotiator = ProtocolNegotiator(timeout=timeout)

    async def query_peer(
        self,
        conn: StreamReaderWriter,
        local_info: Optional[IdentifyMessage] = None,
    ) -> IdentifyMessage:
        """
        Query a remote peer for their identity information.

        Performs protocol negotiation followed by Identify exchange.

        Args:
            conn: Connection to the peer
            local_info: Optional local identity to send

        Returns:
            Remote peer's Identify message
        """
        # Negotiate Identify protocol
        logger.debug("Negotiating Identify protocol...")
        await self.negotiator.negotiate(conn, [PROTOCOL_ID])

        # Wrap connection for Identify protocol
        from .identify import ConnectionWrapper
        identify_conn = ConnectionWrapper(conn.reader, conn.writer)

        # Perform Identify exchange
        logger.debug("Performing Identify exchange...")
        remote_info = await self.protocol.exchange(identify_conn, local_info)

        return remote_info

    async def push_identity(
        self,
        conn: StreamReaderWriter,
        info: IdentifyMessage,
    ) -> None:
        """
        Push identity information to a peer.

        Performs protocol negotiation followed by Identify push.

        Args:
            conn: Connection to the peer
            info: Identity information to push
        """
        # Negotiate Identify push protocol
        logger.debug("Negotiating Identify push protocol...")
        await self.negotiator.negotiate(conn, [PROTOCOL_PUSH_ID])

        # Wrap connection for Identify protocol
        from .identify import ConnectionWrapper
        identify_conn = ConnectionWrapper(conn.reader, conn.writer)

        # Perform Identify push
        logger.debug("Pushing Identify update...")
        await self.protocol.push(identify_conn, info)

    async def handle_query(
        self,
        conn: StreamReaderWriter,
        local_info: IdentifyMessage,
    ) -> None:
        """
        Handle an incoming Identify query.

        Waits for protocol negotiation and responds with local identity.

        Args:
            conn: Incoming connection
            local_info: Local identity to send
        """
        # Accept protocol negotiation
        logger.debug("Waiting for Identify protocol negotiation...")
        await self.negotiator.handle_negotiate(
            conn,
            [PROTOCOL_ID, PROTOCOL_PUSH_ID],
        )

        # Wrap connection for Identify protocol
        from .identify import ConnectionWrapper
        identify_conn = ConnectionWrapper(conn.reader, conn.writer)

        # Handle Identify query
        logger.debug("Handling Identify query...")
        await self.protocol.handle_query(identify_conn, local_info)


# ==================== 工厂函数 ====================

def create_default_registry(local_info: Optional[IdentifyMessage] = None) -> ProtocolRegistry:
    """
    Create a protocol registry with default handlers.

    Args:
        local_info: Local Identify information (optional)

    Returns:
        Configured protocol registry
    """
    registry = ProtocolRegistry()

    # Register Identify protocol handler
    def create_identify_handler():
        return IdentifyHandler(local_info=local_info)

    registry.register(PROTOCOL_ID, create_identify_handler)
    registry.register(PROTOCOL_PUSH_ID, create_identify_handler)

    return registry


def create_identify_client(
    public_key: bytes = b"",
    listen_addrs: list[bytes] = None,
    isp: ISP = ISP.UNKNOWN,
    nat_type: NATType = NATType.UNKNOWN,
    device_vendor: DeviceVendor = DeviceVendor.UNKNOWN,
) -> IdentifyClient:
    """
    Create an Identify client with local identity.

    Args:
        public_key: Local public key
        listen_addrs: Local listen addresses
        isp: Local ISP
        nat_type: Local NAT type
        device_vendor: Local device vendor

    Returns:
        Configured Identify client
    """
    protocol = IdentifyProtocol()
    extension = IdentifyExtension(
        isp=isp,
        nat_type=nat_type,
        device_vendor=device_vendor,
    )
    local_info = protocol.create_local_info(
        public_key=public_key,
        listen_addrs=listen_addrs or [],
        extension=extension,
    )

    client = IdentifyClient()
    client.protocol = protocol
    client._local_info = local_info

    return client


# 导入 IdentifyExtension 以便在工厂函数中使用
from .identify import IdentifyExtension
