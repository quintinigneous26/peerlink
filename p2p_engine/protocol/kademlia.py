"""
Kademlia DHT Protocol Handler

Integrates the Kademlia DHT implementation with the p2p_engine protocol layer.
This module provides the protocol handler interface for DHT operations.

Compatible with libp2p Kademlia DHT specification:
https://github.com/libp2p/specs/tree/master/kad-dht
"""

import asyncio
import logging
from typing import Optional, List, Callable, Awaitable

from ..dht import (
    KademliaDHT,
    DHT,
    KademliaMessage,
    KademliaMessageType,
    PeerEntry,
    calculate_peer_id,
)

logger = logging.getLogger(__name__)

# Protocol ID
PROTOCOL_ID = "/ipfs/kad/1.0.0"


class KademliaProtocolHandler:
    """
    Protocol handler for Kademlia DHT.

    Integrates with the p2p_engine protocol layer and provides
    DHT functionality for peer discovery and content routing.
    """

    def __init__(
        self,
        local_peer_id: bytes,
        local_public_key: bytes,
        network_send_func: Optional[Callable[[bytes, bytes, str], Awaitable[bytes]]] = None,
    ):
        """
        Initialize Kademlia protocol handler.

        Args:
            local_peer_id: Local peer's ID (32 bytes)
            local_public_key: Local peer's public key (for deriving peer ID)
            network_send_func: Async function to send DHT messages
        """
        # Calculate peer ID from public key if not provided
        if not local_peer_id:
            local_peer_id = calculate_peer_id(local_public_key)

        self.local_peer_id = local_peer_id
        self.local_public_key = local_public_key

        # Create DHT instance
        self.dht = KademliaDHT(
            local_peer_id=local_peer_id,
            network_send_func=network_send_func,
        )

        # Protocol metadata
        self.protocol_id = PROTOCOL_ID
        self._started = False

    async def start(self) -> None:
        """Start the DHT protocol handler."""
        if self._started:
            return

        await self.dht.start()
        self._started = True
        logger.info(f"Kademlia DHT protocol started: {self.protocol_id}")

    async def stop(self) -> None:
        """Stop the DHT protocol handler."""
        if not self._started:
            return

        await self.dht.stop()
        self._started = False
        logger.info("Kademlia DHT protocol stopped")

    async def handle_stream(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """
        Handle incoming DHT stream.

        Args:
            reader: Stream reader
            writer: Stream writer
        """
        peer_addr = writer.get_extra_info("peername")

        try:
            # Read message length (varint)
            length = 0
            shift = 0
            while True:
                byte_buf = await reader.readexactly(1)
                byte = byte_buf[0]
                length |= (byte & 0x7F) << shift
                if not (byte & 0x80):
                    break
                shift += 7

            # Read message
            if length > 10 * 1024 * 1024:  # 10MB limit
                logger.warning(f"Message too large: {length} bytes from {peer_addr}")
                return

            message_data = await reader.readexactly(length)

            # Get peer ID from connection (would normally come from Identify)
            # For now, use a placeholder
            peer_id = b"\x00" * 32  # Should get from Identify protocol

            # Handle message
            response = await self.dht.handle_message(peer_id, message_data)

            # Send response
            if response:
                # Encode response length
                response_length = len(response)
                length_bytes = bytearray()
                while response_length > 0x7F:
                    length_bytes.append((response_length & 0x7F) | 0x80)
                    response_length >>= 7
                length_bytes.append(response_length)

                writer.write(bytes(length_bytes))
                writer.write(response)
                await writer.drain()

        except asyncio.IncompleteReadError:
            logger.debug(f"Incomplete read from {peer_addr}")
        except Exception as e:
            logger.error(f"Error handling DHT stream: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    # DHT Operation Wrappers

    async def find_peer(self, peer_id: bytes) -> Optional[PeerEntry]:
        """
        Find a peer by ID.

        Args:
            peer_id: Peer ID to find (32 bytes)

        Returns:
            Peer entry if found, None otherwise
        """
        if not self._started:
            await self.start()

        return await self.dht.find_peer(peer_id)

    async def provide(self, cid: bytes, announce: bool = True) -> bool:
        """
        Announce that we provide a content.

        Args:
            cid: Content ID (CID)
            announce: Whether to announce to network

        Returns:
            True if successful
        """
        if not self._started:
            await self.start()

        return await self.dht.provide(cid, announce)

    async def find_providers(self, cid: bytes, count: int = 20) -> List[PeerEntry]:
        """
        Find providers for a content.

        Args:
            cid: Content ID (CID)
            count: Maximum number of providers to return

        Returns:
            List of provider peers
        """
        if not self._started:
            await self.start()

        return await self.dht.find_providers(cid, count)

    async def put_value(self, key: bytes, value: bytes) -> bool:
        """
        Store a key-value pair in DHT.

        Args:
            key: Key to store under
            value: Value to store

        Returns:
            True if successful
        """
        if not self._started:
            await self.start()

        return await self.dht.put_value(key, value)

    async def get_value(self, key: bytes) -> Optional[bytes]:
        """
        Retrieve a value from DHT.

        Args:
            key: Key to retrieve

        Returns:
            Value if found, None otherwise
        """
        if not self._started:
            await self.start()

        return await self.dht.get_value(key)

    async def add_bootstrap_peer(
        self,
        peer_id: bytes,
        addresses: List[str]
    ) -> None:
        """
        Add a bootstrap peer to routing table.

        Args:
            peer_id: Bootstrap peer's ID
            addresses: List of multiaddresses
        """
        await self.dht.add_bootstrap_peer(peer_id, addresses)

    # Properties

    @property
    def peer_count(self) -> int:
        """Get number of peers in routing table."""
        return self.dht.peer_count

    @property
    def is_running(self) -> bool:
        """Check if DHT is running."""
        return self._started

    @property
    def supported_protocols(self) -> List[str]:
        """Get list of supported protocols."""
        return [PROTOCOL_ID]


def create_kademlia_handler(
    local_peer_id: bytes,
    local_public_key: bytes,
    network_send_func: Optional[Callable[[bytes, bytes, str], Awaitable[bytes]]] = None,
) -> KademliaProtocolHandler:
    """
    Factory function to create a Kademlia protocol handler.

    Args:
        local_peer_id: Local peer's ID (32 bytes)
        local_public_key: Local peer's public key
        network_send_func: Async function to send DHT messages

    Returns:
        KademliaProtocolHandler instance
    """
    return KademliaProtocolHandler(
        local_peer_id=local_peer_id,
        local_public_key=local_public_key,
        network_send_func=network_send_func,
    )


# Convenience function for quick DHT operations

async def find_peer_async(
    local_peer_id: bytes,
    target_peer_id: bytes,
    bootstrap_peers: List[tuple[bytes, List[str]]],
    network_send_func: Callable[[bytes, bytes, str], Awaitable[bytes]],
) -> Optional[PeerEntry]:
    """
    Convenience function to find a peer without persistent DHT instance.

    Args:
        local_peer_id: Local peer ID
        target_peer_id: Target peer ID to find
        bootstrap_peers: List of (peer_id, addresses) tuples
        network_send_func: Function to send DHT messages

    Returns:
        Peer entry if found, None otherwise
    """
    handler = create_kademlia_handler(
        local_peer_id=local_peer_id,
        local_public_key=b"",  # Not used for transient lookup
        network_send_func=network_send_func,
    )

    # Add bootstrap peers
    for peer_id, addresses in bootstrap_peers:
        await handler.add_bootstrap_peer(peer_id, addresses)

    # Find peer
    return await handler.find_peer(target_peer_id)
