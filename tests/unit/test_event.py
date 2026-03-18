"""
Unit tests for P2P Event Bus system.

Tests event publishing, subscription, filtering, and lifecycle management.
"""
import asyncio
import pytest
import time
from unittest.mock import Mock, AsyncMock

from p2p_engine.event import (
    # Topics and types
    EventTopic,
    P2PEventType,

    # Event data
    P2PEvent,

    # Event handlers
    EventHandler,
    EventSubscriber,

    # Event bus
    EventBus,

    # Event builder
    EventBuilder,

    # Global event bus
    get_global_event_bus,
    start_global_event_bus,
    stop_global_event_bus,

    # Decorators
    subscribe_to,
)


class TestEventTopicsAndTypes:
    """Test event topic and type enums"""

    def test_event_topics(self):
        """Test all event topics are defined"""
        assert EventTopic.CONNECTION.value == "connection"
        assert EventTopic.STREAM.value == "stream"
        assert EventTopic.PROTOCOL.value == "protocol"
        assert EventTopic.NETWORK.value == "network"
        assert EventTopic.RELAY.value == "relay"
        assert EventTopic.NAT.value == "nat"
        assert EventTopic.ERROR.value == "error"
        assert EventTopic.METRIC.value == "metric"
        assert EventTopic.CUSTOM.value == "custom"

    def test_event_types(self):
        """Test important event types are defined"""
        assert P2PEventType.PEER_CONNECTED.value == "peer_connected"
        assert P2PEventType.STREAM_OPENED.value == "stream_opened"
        assert P2PEventType.NAT_DETECTED.value == "nat_detected"
        assert P2PEventType.RELAY_CONNECTED.value == "relay_connected"


class TestP2PEvent:
    """Test P2PEvent data structure"""

    def test_event_creation(self):
        """Test creating a basic event"""
        event = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
            data={"peer_id": "test-peer"},
        )

        assert event.topic == EventTopic.CONNECTION
        assert event.event_type == P2PEventType.PEER_CONNECTED
        assert event.data["peer_id"] == "test-peer"
        assert event.timestamp > 0

    def test_event_with_peer_id(self):
        """Test event with peer ID"""
        event = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
            peer_id="peer-123",
        )

        assert event.peer_id == "peer-123"

    def test_event_with_correlation_id(self):
        """Test event with correlation ID"""
        event = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
            correlation_id="corr-abc",
        )

        assert event.correlation_id == "corr-abc"

    def test_event_timestamp_default(self):
        """Test event timestamp is set by default"""
        before = time.time()
        event = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
        )
        after = time.time()

        assert before <= event.timestamp <= after


class TestEventSubscriber:
    """Test EventSubscriber filtering"""

    def test_subscriber_matches_no_filter(self):
        """Test subscriber matches when no filters applied"""
        handler = AsyncMock()
        subscriber = EventSubscriber(handler=handler)

        event = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
        )

        assert subscriber.matches(event) is True

    def test_subscriber_filters_by_topic(self):
        """Test subscriber filters by topic"""
        handler = AsyncMock()
        subscriber = EventSubscriber(
            handler=handler,
            filter_topics={EventTopic.CONNECTION},
        )

        # Matching topic
        event1 = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
        )
        assert subscriber.matches(event1) is True

        # Non-matching topic
        event2 = P2PEvent(
            topic=EventTopic.NAT,
            event_type=P2PEventType.NAT_DETECTED,
        )
        assert subscriber.matches(event2) is False

    def test_subscriber_filters_by_type(self):
        """Test subscriber filters by event type"""
        handler = AsyncMock()
        subscriber = EventSubscriber(
            handler=handler,
            filter_types={P2PEventType.PEER_CONNECTED},
        )

        # Matching type
        event1 = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
        )
        assert subscriber.matches(event1) is True

        # Non-matching type
        event2 = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_DISCONNECTED,
        )
        assert subscriber.matches(event2) is False

    def test_subscriber_filters_by_peer(self):
        """Test subscriber filters by peer ID"""
        handler = AsyncMock()
        subscriber = EventSubscriber(
            handler=handler,
            filter_peer="peer-123",
        )

        # Matching peer
        event1 = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
            peer_id="peer-123",
        )
        assert subscriber.matches(event1) is True

        # Non-matching peer
        event2 = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
            peer_id="peer-456",
        )
        assert subscriber.matches(event2) is False

    def test_subscriber_combined_filters(self):
        """Test subscriber with multiple filters"""
        handler = AsyncMock()
        subscriber = EventSubscriber(
            handler=handler,
            filter_topics={EventTopic.CONNECTION},
            filter_types={P2PEventType.PEER_CONNECTED},
            filter_peer="peer-123",
        )

        # All match
        event1 = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
            peer_id="peer-123",
        )
        assert subscriber.matches(event1) is True

        # Topic mismatch
        event2 = P2PEvent(
            topic=EventTopic.NAT,
            event_type=P2PEventType.PEER_CONNECTED,
            peer_id="peer-123",
        )
        assert subscriber.matches(event2) is False

        # Type mismatch
        event3 = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_DISCONNECTED,
            peer_id="peer-123",
        )
        assert subscriber.matches(event3) is False


class TestEventBus:
    """Test EventBus functionality"""

    @pytest.fixture
    async def event_bus(self):
        """Create an event bus for testing"""
        bus = EventBus(max_queue_size=100, worker_count=2)
        await bus.start()
        yield bus
        await bus.stop()

    @pytest.mark.asyncio
    async def test_event_bus_start_stop(self, event_bus):
        """Test event bus start and stop"""
        assert event_bus._running is True

        await event_bus.stop()
        assert event_bus._running is False

    @pytest.mark.asyncio
    async def test_event_bus_restart(self, event_bus):
        """Test restarting event bus"""
        await event_bus.stop()
        assert event_bus._running is False

        await event_bus.start()
        assert event_bus._running is True

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self, event_bus):
        """Test basic subscription and publishing"""
        received_events = []

        async def handler(event: P2PEvent):
            received_events.append(event)

        # Subscribe
        event_bus.subscribe(EventTopic.CONNECTION, handler)

        # Publish event
        test_event = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
            data={"peer_id": "test-peer"},
        )
        await event_bus.publish(test_event)

        # Wait for processing
        await asyncio.sleep(0.1)

        assert len(received_events) == 1
        assert received_events[0].data["peer_id"] == "test-peer"

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, event_bus):
        """Test multiple subscribers to same topic"""
        results = []

        async def handler1(event: P2PEvent):
            results.append("handler1")

        async def handler2(event: P2PEvent):
            results.append("handler2")

        event_bus.subscribe(EventTopic.CONNECTION, handler1)
        event_bus.subscribe(EventTopic.CONNECTION, handler2)

        test_event = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
        )
        await event_bus.publish(test_event)

        await asyncio.sleep(0.1)

        assert len(results) == 2
        assert "handler1" in results
        assert "handler2" in results

    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus):
        """Test unsubscribing"""
        received = []

        async def handler(event: P2PEvent):
            received.append(event)

        subscriber = event_bus.subscribe(EventTopic.CONNECTION, handler)

        # First event should be received
        test_event = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
        )
        await event_bus.publish(test_event)
        await asyncio.sleep(0.1)
        assert len(received) == 1

        # Unsubscribe
        event_bus.unsubscribe(subscriber)

        # Second event should not be received
        await event_bus.publish(test_event)
        await asyncio.sleep(0.1)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_topic_filtering(self, event_bus):
        """Test that events only go to matching topic subscribers"""
        connection_events = []
        nat_events = []

        async def connection_handler(event: P2PEvent):
            connection_events.append(event)

        async def nat_handler(event: P2PEvent):
            nat_events.append(event)

        event_bus.subscribe(EventTopic.CONNECTION, connection_handler)
        event_bus.subscribe(EventTopic.NAT, nat_handler)

        # Publish connection event
        conn_event = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
        )
        await event_bus.publish(conn_event)

        # Publish NAT event
        nat_event = P2PEvent(
            topic=EventTopic.NAT,
            event_type=P2PEventType.NAT_DETECTED,
        )
        await event_bus.publish(nat_event)

        await asyncio.sleep(0.1)

        assert len(connection_events) == 1
        assert len(nat_events) == 1
        assert connection_events[0].topic == EventTopic.CONNECTION
        assert nat_events[0].topic == EventTopic.NAT

    @pytest.mark.asyncio
    async def test_subscribe_all(self, event_bus):
        """Test subscribing to all topics"""
        received = []

        async def handler(event: P2PEvent):
            received.append(event.topic)

        # Subscribe to all events
        event_bus.subscribe_all(handler)

        # Publish different topic events
        for topic in [EventTopic.CONNECTION, EventTopic.NAT, EventTopic.RELAY]:
            event = P2PEvent(
                topic=topic,
                event_type=P2PEventType.PEER_CONNECTED,
            )
            await event_bus.publish(event)

        await asyncio.sleep(0.1)

        assert len(received) == 3
        assert EventTopic.CONNECTION in received
        assert EventTopic.NAT in received
        assert EventTopic.RELAY in received

    @pytest.mark.asyncio
    async def test_event_type_filtering(self, event_bus):
        """Test filtering by event type"""
        received = []

        async def handler(event: P2PEvent):
            received.append(event.event_type)

        event_bus.subscribe(
            EventTopic.CONNECTION,
            handler,
            filter_types={P2PEventType.PEER_CONNECTED},
        )

        # Publish matching event
        event1 = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
        )
        await event_bus.publish(event1)

        # Publish non-matching event
        event2 = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_DISCONNECTED,
        )
        await event_bus.publish(event2)

        await asyncio.sleep(0.1)

        assert len(received) == 1
        assert received[0] == P2PEventType.PEER_CONNECTED

    @pytest.mark.asyncio
    async def test_peer_filtering(self, event_bus):
        """Test filtering by peer ID"""
        received = []

        async def handler(event: P2PEvent):
            received.append(event.peer_id)

        event_bus.subscribe(
            EventTopic.CONNECTION,
            handler,
            filter_peer="peer-123",
        )

        # Publish matching peer event
        event1 = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
            peer_id="peer-123",
        )
        await event_bus.publish(event1)

        # Publish non-matching peer event
        event2 = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
            peer_id="peer-456",
        )
        await event_bus.publish(event2)

        await asyncio.sleep(0.1)

        assert len(received) == 1
        assert received[0] == "peer-123"

    @pytest.mark.asyncio
    async def test_publish_when_not_running(self, event_bus):
        """Test publishing when event bus is not running"""
        await event_bus.stop()

        event = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
        )
        result = await event_bus.publish(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_handler_error_handling(self, event_bus):
        """Test that handler errors don't crash the event bus"""
        async def failing_handler(event: P2PEvent):
            raise ValueError("Test error")

        async def normal_handler(event: P2PEvent):
            pass

        event_bus.subscribe(EventTopic.CONNECTION, failing_handler)
        event_bus.subscribe(EventTopic.CONNECTION, normal_handler)

        event = P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=P2PEventType.PEER_CONNECTED,
        )
        await event_bus.publish(event)

        await asyncio.sleep(0.1)

        # Event bus should still be running
        assert event_bus._running is True
        # Error should be recorded
        assert event_bus._handler_errors > 0

    def test_get_metrics(self, event_bus):
        """Test getting event bus metrics"""
        metrics = event_bus.get_metrics()

        assert "uptime_seconds" in metrics
        assert "events_published" in metrics
        assert "events_processed" in metrics
        assert "events_dropped" in metrics
        assert "handler_errors" in metrics
        assert "queue_size" in metrics
        assert "running" in metrics

    def test_reset_metrics(self, event_bus):
        """Test resetting metrics"""
        # Publish some events to generate metrics
        event_bus._events_published = 10
        event_bus._events_processed = 8

        event_bus.reset_metrics()

        metrics = event_bus.get_metrics()
        assert metrics["events_published"] == 0
        assert metrics["events_processed"] == 0


class TestEventBuilder:
    """Test EventBuilder helper class"""

    def test_connection_event(self):
        """Test building connection event"""
        event = EventBuilder.connection_event(
            P2PEventType.PEER_CONNECTED,
            peer_id="peer-123",
            connection_type="p2p_udp",
        )

        assert event.topic == EventTopic.CONNECTION
        assert event.event_type == P2PEventType.PEER_CONNECTED
        assert event.data["peer_id"] == "peer-123"
        assert event.data["connection_type"] == "p2p_udp"
        assert event.peer_id == "peer-123"

    def test_stream_event(self):
        """Test building stream event"""
        event = EventBuilder.stream_event(
            P2PEventType.STREAM_OPENED,
            peer_id="peer-123",
            stream_id="stream-456",
            protocol="/protocol/1.0.0",
        )

        assert event.topic == EventTopic.STREAM
        assert event.event_type == P2PEventType.STREAM_OPENED
        assert event.data["stream_id"] == "stream-456"
        assert event.data["protocol"] == "/protocol/1.0.0"

    def test_protocol_event(self):
        """Test building protocol event"""
        event = EventBuilder.protocol_event(
            P2PEventType.PROTOCOL_NEGOTIATED,
            peer_id="peer-123",
            protocol="/protocol/1.0.0",
        )

        assert event.topic == EventTopic.PROTOCOL
        assert event.data["protocol"] == "/protocol/1.0.0"

    def test_nat_event(self):
        """Test building NAT event"""
        event = EventBuilder.nat_event(
            P2PEventType.NAT_DETECTED,
            nat_type="symmetric",
            public_ip="1.2.3.4",
        )

        assert event.topic == EventTopic.NAT
        assert event.event_type == P2PEventType.NAT_DETECTED
        assert event.data["nat_type"] == "symmetric"
        assert event.data["public_ip"] == "1.2.3.4"

    def test_relay_event(self):
        """Test building relay event"""
        event = EventBuilder.relay_event(
            P2PEventType.RELAY_CONNECTED,
            peer_id="peer-123",
            relay_peer="relay-456",
        )

        assert event.topic == EventTopic.RELAY
        assert event.data["relay_peer"] == "relay-456"

    def test_error_event(self):
        """Test building error event"""
        error = ValueError("Test error")
        event = EventBuilder.error_event(
            error=error,
            source="test_module",
            peer_id="peer-123",
        )

        assert event.topic == EventTopic.ERROR
        assert event.event_type == P2PEventType.ERROR_OCCURRED
        assert event.data["error_type"] == "ValueError"
        assert event.data["error_message"] == "Test error"
        assert event.source == "test_module"
        assert event.peer_id == "peer-123"

    def test_network_event(self):
        """Test building network event"""
        event = EventBuilder.network_event(
            P2PEventType.NETWORK_CHANGED,
            interface="eth0",
        )

        assert event.topic == EventTopic.NETWORK
        assert event.data["interface"] == "eth0"


class TestGlobalEventBus:
    """Test global event bus singleton"""

    @pytest.mark.asyncio
    async def test_get_global_event_bus(self):
        """Test getting global event bus"""
        bus = get_global_event_bus()
        assert bus is not None
        assert isinstance(bus, EventBus)

    @pytest.mark.asyncio
    async def test_global_event_bus_singleton(self):
        """Test that global event bus is a singleton"""
        bus1 = get_global_event_bus()
        bus2 = get_global_event_bus()
        assert bus1 is bus2

    @pytest.mark.asyncio
    async def test_start_stop_global_event_bus(self):
        """Test starting and stopping global event bus"""
        await start_global_event_bus()

        bus = get_global_event_bus()
        assert bus._running is True

        await stop_global_event_bus()

        # New instance after stop
        bus2 = get_global_event_bus()
        assert bus2 is not bus


class TestSubscribeDecorator:
    """Test subscribe_to decorator"""

    @pytest.mark.asyncio
    async def test_decorator_without_bus(self):
        """Test decorator without event bus"""
        received = []

        @subscribe_to(EventTopic.CONNECTION)
        async def handler(event: P2PEvent):
            received.append(event)

        # Handler should have metadata
        assert hasattr(handler, "_event_topic")
        assert handler._event_topic == EventTopic.CONNECTION


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
