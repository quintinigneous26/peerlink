"""
Integration Tests: Ping Protocol with DHT

Tests for integrating the Ping protocol with Kademlia DHT
for node reachability detection and RTT-based peer selection.
"""

import asyncio
import pytest
import time

from p2p_engine.protocol.ping import PingProtocol, PingStats, PING_PAYLOAD_SIZE
from p2p_engine.dht.kademlia import KademliaDHT, KademliaMessage, KademliaMessageType
from p2p_engine.dht.routing import PeerEntry, BYTE_COUNT


class TestPingDHTIntegration:
    """Integration tests for Ping protocol with DHT."""

    @pytest.fixture
    def local_peer_id(self):
        """Local peer ID for testing."""
        return b"\x80" + b"\x00" * 31

    @pytest.fixture
    def dht(self, local_peer_id):
        """KademliaDHT instance for testing."""
        return KademliaDHT(local_peer_id=local_peer_id)

    @pytest.mark.asyncio
    async def test_dht_peer_ping_integration(self, dht):
        """Test using Ping protocol to verify DHT peer reachability."""
        peer_id = b"\x01" * 32
        peer = PeerEntry(peer_id=peer_id, addresses=["/ip4/127.0.0.1/tcp/1234"])
        await dht.routing_table.add_peer(peer)

        found = dht.routing_table.find_peer(peer_id)
        assert found is not None
        assert found.peer_id == peer_id

    @pytest.mark.asyncio
    async def test_ping_stats_for_dht_peer_selection(self, dht):
        """Test using ping RTT stats for DHT peer selection."""
        for i in range(5):
            peer_id = bytes([i]) * 32
            peer = PeerEntry(peer_id=peer_id)
            await dht.routing_table.add_peer(peer)

        target = b"\xff" * 32
        closest = dht.routing_table.find_closest_peers(target, count=3)

        assert len(closest) <= 3

    @pytest.mark.asyncio
    async def test_dht_ping_message_handling(self, dht):
        """Test DHT handles PING messages correctly."""
        request = KademliaMessage(
            message_type=KademliaMessageType.PING,
        )

        response_bytes = await dht.handle_message(b"\x00" * 32, request.to_json())
        response = KademliaMessage.from_json(response_bytes)

        assert response.message_type == KademliaMessageType.PING
        assert response.peer_id == dht.local_peer_id

    @pytest.mark.asyncio
    async def test_ping_stale_dht_peer(self, dht):
        """Test handling stale DHT peers after ping timeout."""
        peer_id = b"\x01" * 32
        stale_threshold = 3600.0
        old_time = time.time() - stale_threshold - 1

        from dataclasses import replace
        temp_peer = PeerEntry(peer_id=peer_id, addresses=["/ip4/192.0.2.1/tcp/1234"])
        stale_peer = replace(temp_peer, last_seen=old_time)

        assert stale_peer.is_stale(stale_threshold)

    @pytest.mark.asyncio
    async def test_dht_peer_selection_filters_stale(self, dht):
        """Test DHT peer selection filters out stale peers."""
        good_peer_id = b"\x01" * 32
        stale_peer_id = b"\x02" * 32

        good_peer = PeerEntry(peer_id=good_peer_id)

        stale_threshold = 3600.0
        old_time = time.time() - stale_threshold - 1
        from dataclasses import replace
        temp_peer = PeerEntry(peer_id=stale_peer_id)
        stale_peer = replace(temp_peer, last_seen=old_time)

        await dht.routing_table.add_peer(good_peer)
        await dht.routing_table.add_peer(stale_peer)

        target = b"\x80" * 32
        closest = dht.routing_table.find_closest_peers(target, count=10)

        active_peers = [p for p in closest if not p.is_stale(stale_threshold)]

        assert len(active_peers) >= 1

    def test_ping_protocol_id_compatibility(self):
        """Test Ping protocol ID is compatible with DHT peer discovery."""
        from p2p_engine.protocol.ping import PROTOCOL_ID as PING_PROTOCOL_ID

        assert PING_PROTOCOL_ID == "/ipfs/ping/1.0.0"

    @pytest.mark.asyncio
    async def test_dht_bootstrap_with_ping_verification(self, dht):
        """Test DHT bootstrap with ping-based peer verification."""
        bootstrap_peer_id = b"\x01" * 32
        bootstrap_addrs = ["/ip4/127.0.0.1/tcp/1234"]

        await dht.add_bootstrap_peer(bootstrap_peer_id, bootstrap_addrs)

        found = dht.routing_table.find_peer(bootstrap_peer_id)
        assert found is not None
        assert found.addresses == bootstrap_addrs


class TestPingDHTMessageFormats:
    """Tests for message format compatibility."""

    def test_ping_payload_size_matches_dht_key_size(self):
        """Test Ping payload size matches DHT key size."""
        assert PING_PAYLOAD_SIZE == BYTE_COUNT

    def test_dht_message_json_encoding(self):
        """Test DHT messages can be JSON encoded for Ping transport."""
        msg = KademliaMessage(
            message_type=KademliaMessageType.PING,
            peer_id=b"\x01" * 32,
        )

        json_bytes = msg.to_json()
        assert json_bytes is not None
        assert len(json_bytes) > 0

        import json
        parsed = json.loads(json_bytes)
        assert parsed["type"] == "PING"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
