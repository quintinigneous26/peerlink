"""
PubSub Protocol Unit Tests

Tests for the PubSub protocol implementation including GossipSub v1.1
and FloodSub routers.
"""
import asyncio
import json
import struct
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from p2p_engine.protocol.pubsub import (
    PubSub,
    GossipSub,
    FloodSub,
    GossipSubConfig,
    GossipSubRouter,
    FloodSubRouter,
    PubSubMessage,
    SubOpts,
    RPC,
    ControlMessage,
    ControlIHave,
    ControlIWant,
    ControlGraft,
    ControlPrune,
    PeerInfoPB,
    Subscription,
    SignaturePolicy,
    create_pubsub,
    PROTOCOL_ID_GOSSIPSUB,
    PROTOCOL_ID_FLOODSUB,
)


# ==================== Test Fixtures ====================

@pytest.fixture
def peer_id():
    return "QmPeer123456789"


@pytest.fixture
def gossipsub_config():
    return GossipSubConfig(
        D=6,
        D_low=4,
        D_high=12,
        heartbeat_interval=0.1,  # Faster for tests
    )


@pytest.fixture
async def gossipsub(peer_id, gossipsub_config):
    pubsub = GossipSub(peer_id, gossipsub_config)
    await pubsub.start()
    yield pubsub
    await pubsub.stop()


@pytest.fixture
async def floodsub(peer_id):
    pubsub = FloodSub(peer_id)
    await pubsub.start()
    yield pubsub
    await pubsub.stop()


# ==================== PubSubMessage Tests ====================

class TestPubSubMessage:
    """Tests for PubSubMessage data class."""

    def test_create_empty_message(self):
        msg = PubSubMessage()
        assert msg.from_peer == ""
        assert msg.data == b""
        assert msg.seqno == b""
        assert msg.topic == ""

    def test_create_message_with_data(self):
        msg = PubSubMessage(
            from_peer="QmPeer123",
            data=b"test data",
            seqno=struct.pack(">Q", 1),
            topic="test-topic",
        )
        assert msg.from_peer == "QmPeer123"
        assert msg.data == b"test data"
        assert msg.topic == "test-topic"

    def test_message_id_from_seqno(self):
        msg = PubSubMessage(
            from_peer="QmPeer123",
            seqno=struct.pack(">Q", 1),
        )
        msg_id = msg.message_id()
        assert len(msg_id) == 32  # SHA256 hash

    def test_message_id_from_data(self):
        msg = PubSubMessage(
            data=b"test data",
        )
        msg_id = msg.message_id()
        assert len(msg_id) == 32

    def test_to_protobuf_dict(self):
        msg = PubSubMessage(
            from_peer="QmPeer123",
            data=b"test",
            topic="test-topic",
        )
        result = msg.to_protobuf_dict()
        assert result["from"] == "QmPeer123"
        assert result["data"] == b"test"
        assert result["topic"] == "test-topic"

    def test_from_protobuf_dict(self):
        data = {
            "from": "QmPeer123",
            "data": b"test",
            "topic": "test-topic",
        }
        msg = PubSubMessage.from_protobuf_dict(data)
        assert msg.from_peer == "QmPeer123"
        assert msg.data == b"test"
        assert msg.topic == "test-topic"

    def test_to_json_dict(self):
        msg = PubSubMessage(
            from_peer="QmPeer123",
            data=b"test",
            topic="test-topic",
        )
        result = msg.to_json_dict()
        assert result["from"] == "QmPeer123"
        assert result["data"] == "74657374"  # hex encoded
        assert result["topic"] == "test-topic"

    def test_from_json_dict(self):
        data = {
            "from": "QmPeer123",
            "data": "74657374",
            "topic": "test-topic",
        }
        msg = PubSubMessage.from_json_dict(data)
        assert msg.from_peer == "QmPeer123"
        assert msg.data == b"test"
        assert msg.topic == "test-topic"


# ==================== SubOpts Tests ====================

class TestSubOpts:
    """Tests for SubOpts data class."""

    def test_create_subscribe(self):
        sub = SubOpts(subscribe=True, topicid="test-topic")
        assert sub.subscribe is True
        assert sub.topicid == "test-topic"

    def test_create_unsubscribe(self):
        sub = SubOpts(subscribe=False, topicid="test-topic")
        assert sub.subscribe is False

    def test_to_dict(self):
        sub = SubOpts(subscribe=True, topicid="test-topic")
        result = sub.to_dict()
        assert result["subscribe"] is True
        assert result["topicid"] == "test-topic"

    def test_from_dict(self):
        data = {"subscribe": True, "topicid": "test-topic"}
        sub = SubOpts.from_dict(data)
        assert sub.subscribe is True
        assert sub.topicid == "test-topic"


# ==================== RPC Tests ====================

class TestRPC:
    """Tests for RPC data class."""

    def test_create_empty_rpc(self):
        rpc = RPC()
        assert rpc.subscriptions == []
        assert rpc.publish == []
        assert rpc.control is None

    def test_create_with_subscriptions(self):
        subs = [SubOpts(subscribe=True, topicid="topic1")]
        rpc = RPC(subscriptions=subs)
        assert len(rpc.subscriptions) == 1
        assert rpc.subscriptions[0].topicid == "topic1"

    def test_create_with_messages(self):
        msgs = [PubSubMessage(topic="topic1", data=b"test")]
        rpc = RPC(publish=msgs)
        assert len(rpc.publish) == 1
        assert rpc.publish[0].topic == "topic1"

    def test_create_with_control(self):
        ctrl = ControlMessage()
        rpc = RPC(control=ctrl)
        assert rpc.control is not None

    def test_to_json_dict(self):
        rpc = RPC(
            subscriptions=[SubOpts(subscribe=True, topicid="topic1")],
            publish=[PubSubMessage(topic="topic1", data=b"test")],
        )
        result = rpc.to_json_dict()
        assert "subscriptions" in result
        assert "publish" in result

    def test_from_json_dict(self):
        data = {
            "subscriptions": [{"subscribe": True, "topicid": "topic1"}],
            "publish": [{"topic": "topic1", "data": "74657374"}],
        }
        rpc = RPC.from_json_dict(data)
        assert len(rpc.subscriptions) == 1
        assert len(rpc.publish) == 1


# ==================== Control Message Tests ====================

class TestControlMessage:
    """Tests for GossipSub control messages."""

    def test_create_empty_control(self):
        ctrl = ControlMessage()
        assert ctrl.ihave == []
        assert ctrl.iwant == []
        assert ctrl.graft == []
        assert ctrl.prune == []

    def test_create_with_ihave(self):
        ihave = ControlIHave(topic_id="topic1", message_ids=[b"msg1", b"msg2"])
        ctrl = ControlMessage(ihave=[ihave])
        assert len(ctrl.ihave) == 1
        assert ctrl.ihave[0].topic_id == "topic1"

    def test_create_with_iwant(self):
        iwant = ControlIWant(message_ids=[b"msg1"])
        ctrl = ControlMessage(iwant=[iwant])
        assert len(ctrl.iwant) == 1

    def test_create_with_graft(self):
        graft = ControlGraft(topic_id="topic1")
        ctrl = ControlMessage(graft=[graft])
        assert len(ctrl.graft) == 1

    def test_create_with_prune(self):
        prune = ControlPrune(topic_id="topic1")
        ctrl = ControlMessage(prune=[prune])
        assert len(ctrl.prune) == 1


# ==================== GossipSubRouter Tests ====================

class TestGossipSubRouter:
    """Tests for GossipSubRouter."""

    def test_create_router(self, peer_id):
        config = GossipSubConfig()
        router = GossipSubRouter(peer_id, config)
        assert router.peer_id == peer_id
        assert router.my_topics == set()
        assert router.peers == set()

    def test_add_peer(self, peer_id):
        router = GossipSubRouter(peer_id)
        router.add_peer("QmPeer1")
        assert "QmPeer1" in router.peers

    def test_remove_peer(self, peer_id):
        router = GossipSubRouter(peer_id)
        router.add_peer("QmPeer1")
        router.remove_peer("QmPeer1")
        assert "QmPeer1" not in router.peers

    def test_handle_subscription(self, peer_id):
        router = GossipSubRouter(peer_id)
        router.add_peer("QmPeer1")

        sub = SubOpts(subscribe=True, topicid="topic1")
        router.handle_subscription("QmPeer1", sub)

        assert "topic1" in router.peer_topics["QmPeer1"]

    def test_get_peers(self, peer_id):
        router = GossipSubRouter(peer_id)
        router.add_peer("QmPeer1")
        router.add_peer("QmPeer2")

        router.handle_subscription("QmPeer1", SubOpts(subscribe=True, topicid="topic1"))
        router.handle_subscription("QmPeer2", SubOpts(subscribe=True, topicid="topic1"))

        peers = router.get_peers("topic1")
        assert "QmPeer1" in peers
        assert "QmPeer2" in peers

    @pytest.mark.asyncio
    async def test_join_topic(self, peer_id):
        router = GossipSubRouter(peer_id)
        router.add_peer("QmPeer1")
        router.handle_subscription("QmPeer1", SubOpts(subscribe=True, topicid="topic1"))

        await router.join_topic("topic1")

        assert "topic1" in router.my_topics
        # Peer should be in mesh
        assert "QmPeer1" in router.mesh.get("topic1", set())

    @pytest.mark.asyncio
    async def test_leave_topic(self, peer_id):
        router = GossipSubRouter(peer_id)
        await router.join_topic("topic1")
        await router.leave_topic("topic1")

        assert "topic1" not in router.my_topics
        assert "topic1" not in router.mesh

    def test_handle_message_new(self, peer_id):
        router = GossipSubRouter(peer_id)
        msg = PubSubMessage(
            from_peer="QmOtherPeer",
            data=b"test data",
            seqno=struct.pack(">Q", 1),
            topic="topic1",
        )

        result = router.handle_message(msg, "QmOtherPeer")
        assert result is True  # Should forward

    def test_handle_message_seen(self, peer_id):
        router = GossipSubRouter(peer_id)
        msg = PubSubMessage(
            from_peer="QmOtherPeer",
            data=b"test data",
            seqno=struct.pack(">Q", 1),
            topic="topic1",
        )

        # First time
        router.handle_message(msg, "QmOtherPeer")
        # Second time - should be seen
        result = router.handle_message(msg, "QmOtherPeer")
        assert result is False  # Should not forward

    def test_handle_message_own(self, peer_id):
        router = GossipSubRouter(peer_id)
        msg = PubSubMessage(
            from_peer=peer_id,
            data=b"test data",
            seqno=struct.pack(">Q", 1),
            topic="topic1",
        )

        result = router.handle_message(msg, peer_id)
        assert result is False  # Should not forward own messages

    def test_heartbeat(self, peer_id):
        router = GossipSubRouter(peer_id)
        router.add_peer("QmPeer1")
        router.handle_subscription("QmPeer1", SubOpts(subscribe=True, topicid="topic1"))

        # Join topic
        asyncio.run(router.join_topic("topic1"))

        # Run heartbeat
        control = router.heartbeat()
        assert control is not None

    def test_handle_graft_subscribed(self, peer_id):
        router = GossipSubRouter(peer_id)
        asyncio.run(router.join_topic("topic1"))

        prune = router.handle_graft("topic1", "QmPeer1")
        assert prune is None  # Should accept graft
        assert "QmPeer1" in router.mesh["topic1"]

    def test_handle_graft_not_subscribed(self, peer_id):
        router = GossipSubRouter(peer_id)

        prune = router.handle_graft("topic1", "QmPeer1")
        assert prune is not None  # Should reject with PRUNE
        assert prune.topic_id == "topic1"

    def test_handle_prune(self, peer_id):
        router = GossipSubRouter(peer_id)
        asyncio.run(router.join_topic("topic1"))
        router.mesh["topic1"].add("QmPeer1")

        prune_msg = ControlPrune(topic_id="topic1")
        router.handle_prune("topic1", "QmPeer1", prune_msg)

        assert "QmPeer1" not in router.mesh["topic1"]


# ==================== GossipSub Tests ====================

class TestGossipSub:
    """Tests for GossipSub implementation."""

    @pytest.mark.asyncio
    async def test_start_stop(self, gossipsub):
        assert gossipsub._running is True

    @pytest.mark.asyncio
    async def test_subscribe(self, gossipsub):
        subscription = await gossipsub.subscribe("test-topic")

        assert isinstance(subscription, Subscription)
        assert subscription.topic == "test-topic"
        assert "test-topic" in gossipsub.get_topics()

    @pytest.mark.asyncio
    async def test_unsubscribe(self, gossipsub):
        await gossipsub.subscribe("test-topic")
        await gossipsub.unsubscribe("test-topic")

        assert "test-topic" not in gossipsub.get_topics()

    @pytest.mark.asyncio
    async def test_publish(self, gossipsub):
        # Add a peer connection
        mock_conn = MagicMock()
        gossipsub.add_peer("QmPeer1", mock_conn)
        gossipsub.router.handle_subscription("QmPeer1", SubOpts(subscribe=True, topicid="test-topic"))

        # Publish (won't actually send due to mock)
        await gossipsub.publish("test-topic", b"test data")

    @pytest.mark.asyncio
    async def test_list_peers(self, gossipsub):
        gossipsub.add_peer("QmPeer1", MagicMock())
        gossipsub.router.handle_subscription("QmPeer1", SubOpts(subscribe=True, topicid="test-topic"))

        peers = gossipsub.list_peers("test-topic")
        assert "QmPeer1" in peers

    @pytest.mark.asyncio
    async def test_add_remove_peer(self, gossipsub):
        mock_conn = MagicMock()
        gossipsub.add_peer("QmPeer1", mock_conn)
        assert "QmPeer1" in gossipsub.router.peers

        gossipsub.remove_peer("QmPeer1")
        assert "QmPeer1" not in gossipsub.router.peers

    @pytest.mark.asyncio
    async def test_handle_rpc_subscription(self, gossipsub):
        rpc = RPC(subscriptions=[
            SubOpts(subscribe=True, topicid="test-topic")
        ])

        response = await gossipsub.handle_rpc(rpc, "QmPeer1")
        # Subscription should be tracked
        assert "test-topic" in gossipsub.router.peer_topics["QmPeer1"]

    @pytest.mark.asyncio
    async def test_handle_rpc_message(self, gossipsub):
        await gossipsub.subscribe("test-topic")

        msg = PubSubMessage(
            from_peer="QmOtherPeer",
            data=b"test data",
            seqno=struct.pack(">Q", 1),
            topic="test-topic",
        )
        rpc = RPC(publish=[msg])

        response = await gossipsub.handle_rpc(rpc, "QmOtherPeer")
        # Message should be queued
        assert not gossipsub._message_queues["test-topic"].empty()

    @pytest.mark.asyncio
    async def test_handle_rpc_control_graft(self, gossipsub):
        await gossipsub.subscribe("test-topic")

        control = ControlMessage(graft=[ControlGraft(topic_id="test-topic")])
        rpc = RPC(control=control)

        response = await gossipsub.handle_rpc(rpc, "QmPeer1")
        # Peer should be added to mesh
        assert "QmPeer1" in gossipsub.router.mesh["test-topic"]

    @pytest.mark.asyncio
    async def test_handle_rpc_control_prune(self, gossipsub):
        await gossipsub.subscribe("test-topic")
        gossipsub.router.mesh["test-topic"].add("QmPeer1")

        control = ControlMessage(prune=[ControlPrune(topic_id="test-topic")])
        rpc = RPC(control=control)

        response = await gossipsub.handle_rpc(rpc, "QmPeer1")
        # Peer should be removed from mesh
        assert "QmPeer1" not in gossipsub.router.mesh["test-topic"]


# ==================== FloodSub Tests ====================

class TestFloodSub:
    """Tests for FloodSub implementation."""

    @pytest.mark.asyncio
    async def test_subscribe(self, floodsub):
        subscription = await floodsub.subscribe("test-topic")

        assert isinstance(subscription, Subscription)
        assert "test-topic" in floodsub.get_topics()

    @pytest.mark.asyncio
    async def test_unsubscribe(self, floodsub):
        await floodsub.subscribe("test-topic")
        await floodsub.unsubscribe("test-topic")

        assert "test-topic" not in floodsub.get_topics()

    @pytest.mark.asyncio
    async def test_publish(self, floodsub):
        mock_conn = MagicMock()
        floodsub.add_peer("QmPeer1", mock_conn)
        floodsub.router.handle_subscription("QmPeer1", SubOpts(subscribe=True, topicid="test-topic"))

        await floodsub.publish("test-topic", b"test data")

    @pytest.mark.asyncio
    async def test_handle_rpc_message(self, floodsub):
        await floodsub.subscribe("test-topic")

        msg = PubSubMessage(
            from_peer="QmOtherPeer",
            data=b"test data",
            seqno=struct.pack(">Q", 1),
            topic="test-topic",
        )
        rpc = RPC(publish=[msg])

        await floodsub.handle_rpc(rpc, "QmOtherPeer")
        # Message should be queued
        assert not floodsub._message_queues["test-topic"].empty()


# ==================== Factory Tests ====================

class TestCreatePubSub:
    """Tests for create_pubsub factory function."""

    def test_create_gossipsub(self):
        pubsub = create_pubsub("QmPeer123", PROTOCOL_ID_GOSSIPSUB)
        assert isinstance(pubsub, GossipSub)

    def test_create_floodsub(self):
        pubsub = create_pubsub("QmPeer123", PROTOCOL_ID_FLOODSUB)
        assert isinstance(pubsub, FloodSub)

    def test_create_unknown_protocol(self):
        with pytest.raises(ValueError):
            create_pubsub("QmPeer123", "/unknown/protocol")


# ==================== Integration Tests ====================

class TestPubSubIntegration:
    """Integration tests for PubSub functionality."""

    @pytest.mark.asyncio
    async def test_gossipsub_message_flow(self):
        """Test complete message flow through GossipSub."""
        # Create two pubsub instances
        peer1 = GossipSub("QmPeer1", GossipSubConfig(heartbeat_interval=0.1))
        peer2 = GossipSub("QmPeer2", GossipSubConfig(heartbeat_interval=0.1))

        await peer1.start()
        await peer2.start()

        try:
            # Connect peers (mock connection)
            mock_conn1 = MagicMock()
            mock_conn2 = MagicMock()
            peer1.add_peer("QmPeer2", mock_conn1)
            peer2.add_peer("QmPeer1", mock_conn2)

            # Subscribe both to topic
            await peer1.subscribe("test-topic")
            await peer2.subscribe("test-topic")

            # Publish from peer1
            await peer1.publish("test-topic", b"test message")

            # Wait for propagation
            await asyncio.sleep(0.2)

            # Verify message was queued
            assert not peer2._message_queues["test-topic"].empty()

        finally:
            await peer1.stop()
            await peer2.stop()

    @pytest.mark.asyncio
    async def test_floodsub_message_flow(self):
        """Test complete message flow through FloodSub."""
        peer1 = FloodSub("QmPeer1")
        peer2 = FloodSub("QmPeer2")

        await peer1.start()
        await peer2.start()

        try:
            # Connect peers
            mock_conn1 = MagicMock()
            mock_conn2 = MagicMock()
            peer1.add_peer("QmPeer2", mock_conn1)
            peer2.add_peer("QmPeer1", mock_conn2)

            # Subscribe both to topic
            await peer1.subscribe("test-topic")
            await peer2.subscribe("test-topic")

            # Publish from peer1
            await peer1.publish("test-topic", b"test message")

            # Wait for processing
            await asyncio.sleep(0.1)

            # Verify message was queued
            assert not peer2._message_queues["test-topic"].empty()

        finally:
            await peer1.stop()
            await peer2.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
