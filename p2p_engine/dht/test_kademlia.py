"""
Integration tests for Kademlia DHT Protocol

Tests for the complete Kademlia protocol implementation including
message handling, protocol operations, and protocol integration.
"""

import asyncio
import pytest
import json
from p2p_engine.dht.kademlia import (
    DHT,
    KademliaDHT,
    KademliaMessage,
    KademliaMessageType,
    PROTOCOL_ID,
    calculate_peer_id,
    PeerEntry,
    K,
    BYTE_COUNT,
)
from p2p_engine.dht.provider import ProviderManager
from p2p_engine.dht.routing import RoutingTable


class TestKademliaMessage:
    """Tests for Kademlia message encoding/decoding."""

    def test_message_creation(self):
        """Test creating Kademlia message."""
        msg = KademliaMessage(
            message_type=KademliaMessageType.FIND_NODE,
            key=b"\x01" * 32,
        )

        assert msg.message_type == KademliaMessageType.FIND_NODE
        assert msg.key == b"\x01" * 32

    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        msg = KademliaMessage(
            message_type=KademliaMessageType.FIND_NODE,
            key=b"\x01" * 32,
            peer_id=b"\x02" * 32,
        )

        msg_dict = msg.to_dict()

        assert msg_dict["type"] == "FIND_NODE"
        assert msg_dict["key"] == (b"\x01" * 32).hex()
        assert msg_dict["peer_id"] == (b"\x02" * 32).hex()

    def test_message_from_dict(self):
        """Test creating message from dictionary."""
        msg_dict = {
            "type": "FIND_NODE",
            "key": (b"\x01" * 32).hex(),
            "clusterLevel": 0,
        }

        msg = KademliaMessage.from_dict(msg_dict)

        assert msg.message_type == KademliaMessageType.FIND_NODE
        assert msg.key == b"\x01" * 32

    def test_message_json_roundtrip(self):
        """Test JSON encoding/decoding roundtrip."""
        original = KademliaMessage(
            message_type=KademliaMessageType.FIND_NODE,
            key=b"\x01" * 32,
            value=b"test_value",
            peer_id=b"\x02" * 32,
        )

        json_bytes = original.to_json()
        decoded = KademliaMessage.from_json(json_bytes)

        assert decoded.message_type == original.message_type
        assert decoded.key == original.key
        assert decoded.value == original.value
        assert decoded.peer_id == original.peer_id

    def test_message_with_peers(self):
        """Test message with closer peers."""
        msg = KademliaMessage(
            message_type=KademliaMessageType.FIND_NODE,
            peers=[
                {"id": b"\x01" * 32, "addrs": ["/ip4/127.0.0.1/tcp/1234"]},
                {"id": b"\x02" * 32, "addrs": ["/ip4/127.0.0.1/tcp/5678"]},
            ],
        )

        msg_dict = msg.to_dict()

        assert len(msg_dict["closerPeers"]) == 2
        assert msg_dict["closerPeers"][0]["id"] == (b"\x01" * 32).hex()

    def test_message_with_providers(self):
        """Test message with providers."""
        msg = KademliaMessage(
            message_type=KademliaMessageType.GET_PROVIDERS,
            key=b"\x01" * 32,
            providers=[
                {"id": b"\x01" * 32, "addrs": []},
                {"id": b"\x02" * 32, "addrs": []},
            ],
        )

        msg_dict = msg.to_dict()

        assert "providers" in msg_dict
        assert len(msg_dict["providers"]) == 2


class TestKademliaDHT:
    """Integration tests for Kademlia DHT."""

    @pytest.fixture
    def local_peer_id(self):
        """Local peer ID for testing."""
        return b"\x80" + b"\x00" * 31

    @pytest.fixture
    def dht(self, local_peer_id):
        """KademliaDHT instance for testing."""
        return KademliaDHT(local_peer_id=local_peer_id)

    def test_dht_creation(self, dht, local_peer_id):
        """Test creating DHT instance."""
        assert dht.local_peer_id == local_peer_id
        assert dht.protocol_id == PROTOCOL_ID
        assert dht.peer_count == 0

    def test_dht_invalid_peer_id(self):
        """Test DHT creation with invalid peer ID."""
        with pytest.raises(ValueError):
            KademliaDHT(local_peer_id=b"\x01" * 16)  # Wrong length

    @pytest.mark.asyncio
    async def test_dht_start_stop(self, dht):
        """Test starting and stopping DHT."""
        await dht.start()
        assert dht._running is True

        await dht.stop()
        assert dht._running is False

    @pytest.mark.asyncio
    async def test_add_bootstrap_peer(self, dht):
        """Test adding bootstrap peer."""
        peer_id = b"\x01" * 32
        addresses = ["/ip4/127.0.0.1/tcp/1234"]

        await dht.add_bootstrap_peer(peer_id, addresses)

        # Should be in routing table
        found = dht.routing_table.find_peer(peer_id)
        assert found is not None
        assert found.addresses == addresses

    @pytest.mark.asyncio
    async def test_handle_find_node(self, dht, local_peer_id):
        """Test handling FIND_NODE message."""
        # Add some peers to routing table
        for i in range(5):
            peer = PeerEntry(peer_id=bytes([i]) * 32)
            await dht.routing_table.add_peer(peer)

        # Create FIND_NODE request
        target = b"\x01" * 32
        request = KademliaMessage(
            message_type=KademliaMessageType.FIND_NODE,
            key=target,
        )

        # Handle message
        response_bytes = await dht.handle_message(b"\x00" * 32, request.to_json())
        response = KademliaMessage.from_json(response_bytes)

        assert response.message_type == KademliaMessageType.FIND_NODE
        assert len(response.peers) > 0

    @pytest.mark.asyncio
    async def test_handle_put_value(self, dht):
        """Test handling PUT_VALUE message."""
        import hashlib
        key = b"test_key"
        dht_key = hashlib.sha256(key).digest()  # DHT uses hashed keys
        value = b"test_value"

        request = KademliaMessage(
            message_type=KademliaMessageType.PUT_VALUE,
            key=dht_key,  # Send the hashed key
            value=value,
        )

        response_bytes = await dht.handle_message(b"\x00" * 32, request.to_json())
        response = KademliaMessage.from_json(response_bytes)

        assert response.message_type == KademliaMessageType.PUT_VALUE

        # Value should be stored under the hashed key
        assert dht_key in dht._local_store

    @pytest.mark.asyncio
    async def test_handle_find_value(self, dht):
        """Test handling FIND_VALUE message."""
        key = b"test_key"
        value = b"test_value"

        # Store a value first
        import hashlib
        dht_key = hashlib.sha256(key).digest()
        dht._local_store[dht_key] = (value, float('inf'))

        request = KademliaMessage(
            message_type=KademliaMessageType.FIND_VALUE,
            key=dht_key,
        )

        response_bytes = await dht.handle_message(b"\x00" * 32, request.to_json())
        response = KademliaMessage.from_json(response_bytes)

        assert response.message_type == KademliaMessageType.FIND_VALUE
        assert response.value == value

    @pytest.mark.asyncio
    async def test_handle_add_provider(self, dht):
        """Test handling ADD_PROVIDER message."""
        key = b"test_cid"
        peer_id = b"\x01" * 32

        request = KademliaMessage(
            message_type=KademliaMessageType.ADD_PROVIDER,
            key=key,
            peer_id=peer_id,
        )

        response_bytes = await dht.handle_message(peer_id, request.to_json())
        response = KademliaMessage.from_json(response_bytes)

        assert response.message_type == KademliaMessageType.ADD_PROVIDER

        # Provider should be recorded
        providers = dht.provider_manager.get_providers(key)
        assert len(providers) > 0

    @pytest.mark.asyncio
    async def test_handle_get_providers(self, dht):
        """Test handling GET_PROVIDERS message."""
        key = b"test_cid"

        # Add some providers
        for i in range(3):
            peer_id = bytes([i]) * 32
            await dht.provider_manager.add_provider(key, peer_id)

        request = KademliaMessage(
            message_type=KademliaMessageType.GET_PROVIDERS,
            key=key,
        )

        response_bytes = await dht.handle_message(b"\x00" * 32, request.to_json())
        response = KademliaMessage.from_json(response_bytes)

        assert response.message_type == KademliaMessageType.GET_PROVIDERS
        assert len(response.providers) > 0

    @pytest.mark.asyncio
    async def test_handle_ping(self, dht):
        """Test handling PING message."""
        request = KademliaMessage(
            message_type=KademliaMessageType.PING,
        )

        response_bytes = await dht.handle_message(b"\x00" * 32, request.to_json())
        response = KademliaMessage.from_json(response_bytes)

        assert response.message_type == KademliaMessageType.PING
        assert response.peer_id == dht.local_peer_id

    @pytest.mark.asyncio
    async def test_handle_invalid_message(self, dht):
        """Test handling invalid message."""
        invalid_json = b"invalid json"

        response_bytes = await dht.handle_message(b"\x00" * 32, invalid_json)
        response = KademliaMessage.from_json(response_bytes)

        # Should return error response
        assert response.record is not None or response.message_type == KademliaMessageType.PING

    @pytest.mark.asyncio
    async def test_put_value_local(self, dht):
        """Test putting value locally."""
        key = b"test_key"
        value = b"test_value"

        result = await dht.put_value(key, value)

        # Should succeed (stored locally)
        assert result is True

        # Value should be retrievable
        retrieved = await dht.get_value(key)
        assert retrieved == value

    @pytest.mark.asyncio
    async def test_get_value_from_local_store(self, dht):
        """Test getting value from local store."""
        key = b"test_key"
        value = b"test_value"

        # Store value
        import hashlib
        dht_key = hashlib.sha256(key).digest()
        dht._local_store[dht_key] = (value, float('inf'))

        # Retrieve value
        retrieved = await dht.get_value(key)

        assert retrieved == value

    @pytest.mark.asyncio
    async def test_get_value_not_found(self, dht):
        """Test getting non-existent value."""
        key = b"nonexistent_key"

        # No network send function, should return None
        retrieved = await dht.get_value(key)

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_provide_local(self, dht):
        """Test providing content locally."""
        cid = b"test_cid"

        result = await dht.provide(cid, announce=False)

        assert result is True
        assert dht.provider_manager.is_providing(cid)

    @pytest.mark.asyncio
    async def test_find_providers_local(self, dht):
        """Test finding providers from local cache."""
        cid = b"test_cid"

        # Add some providers
        for i in range(3):
            peer_id = bytes([i]) * 32
            await dht.provider_manager.add_provider(cid, peer_id)
            await dht.routing_table.add_peer(PeerEntry(peer_id=peer_id))

        providers = await dht.find_providers(cid)

        assert len(providers) > 0


class TestDHTInterface:
    """Tests for DHT abstract interface compliance."""

    def test_dht_is_abstract(self):
        """Test that DHT cannot be instantiated directly."""
        with pytest.raises(TypeError):
            DHT()

    def test_kademlia_implements_dht(self):
        """Test that KademliaDHT implements DHT interface."""
        local_peer_id = b"\x80" + b"\x00" * 31
        dht = KademliaDHT(local_peer_id=local_peer_id)

        assert isinstance(dht, DHT)

        # Check all required methods exist
        assert hasattr(dht, 'find_peer')
        assert hasattr(dht, 'provide')
        assert hasattr(dht, 'find_providers')
        assert hasattr(dht, 'put_value')
        assert hasattr(dht, 'get_value')


class TestProtocolConstants:
    """Tests for protocol constants."""

    def test_protocol_id(self):
        """Test protocol ID constant."""
        assert PROTOCOL_ID == "/ipfs/kad/1.0.0"

    def test_bucket_size(self):
        """Test bucket size constant."""
        assert K == 20

    def test_byte_count(self):
        """Test byte count for peer IDs."""
        assert BYTE_COUNT == 32  # SHA-256


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
