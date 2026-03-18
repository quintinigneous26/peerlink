"""
Unit tests for P2PEngine EventBus integration.

Tests that P2PEngine correctly publishes events through EventBus
and maintains backward compatibility with callback-based API.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock

from p2p_engine.engine import P2PEngine, P2PConfig
from p2p_engine.event import EventBus, EventTopic, P2PEventType
from p2p_engine.types import ConnectionState


@pytest.mark.asyncio
async def test_engine_creates_own_eventbus():
    """Test that engine creates its own EventBus if not provided"""
    engine = P2PEngine()

    assert engine.event_bus is not None
    assert isinstance(engine.event_bus, EventBus)
    assert engine._owns_event_bus is True


@pytest.mark.asyncio
async def test_engine_uses_provided_eventbus():
    """Test that engine uses provided EventBus"""
    event_bus = EventBus()
    engine = P2PEngine(event_bus=event_bus)

    assert engine.event_bus is event_bus
    assert engine._owns_event_bus is False


@pytest.mark.asyncio
async def test_state_change_publishes_event():
    """Test that state changes publish events to EventBus"""
    engine = P2PEngine()

    # Track events
    events_received = []

    async def event_handler(event):
        events_received.append(event)

    # Subscribe to connection events
    engine.event_bus.subscribe(EventTopic.CONNECTION, event_handler)

    # Start event bus
    await engine.event_bus.start()

    try:
        # Trigger state change
        await engine._set_state(ConnectionState.DETECTING)

        # Wait for event processing
        await asyncio.sleep(0.1)

        # Verify event was published
        assert len(events_received) == 1
        event = events_received[0]
        assert event.topic == EventTopic.CONNECTION
        assert event.event_type == P2PEventType.CONNECTION_STATE_CHANGED
        assert event.data["new_state"] == ConnectionState.DETECTING.value
    finally:
        await engine.event_bus.stop()


@pytest.mark.asyncio
async def test_backward_compatibility_with_callbacks():
    """Test that old callback API still works"""
    state_changes = []

    async def on_state_change(old_state, new_state):
        state_changes.append((old_state, new_state))

    engine = P2PEngine(on_state_change=on_state_change)
    await engine.event_bus.start()

    try:
        # Trigger state change
        await engine._set_state(ConnectionState.DETECTING)

        # Wait for callback
        await asyncio.sleep(0.1)

        # Verify callback was called
        assert len(state_changes) == 1
        old_state, new_state = state_changes[0]
        assert old_state == ConnectionState.IDLE
        assert new_state == ConnectionState.DETECTING
    finally:
        await engine.event_bus.stop()


@pytest.mark.asyncio
async def test_error_event_publishing():
    """Test that errors are published to EventBus"""
    engine = P2PEngine()

    # Track events
    events_received = []

    async def event_handler(event):
        events_received.append(event)

    # Subscribe to error events
    engine.event_bus.subscribe(EventTopic.ERROR, event_handler)

    # Start event bus
    await engine.event_bus.start()

    try:
        # Trigger error
        test_error = RuntimeError("Test error")
        await engine._emit_error(test_error, context="test")

        # Wait for event processing
        await asyncio.sleep(0.1)

        # Verify event was published
        assert len(events_received) == 1
        event = events_received[0]
        assert event.topic == EventTopic.ERROR
        assert event.event_type == P2PEventType.ERROR_OCCURRED
        assert event.data["error_type"] == "RuntimeError"
        assert event.data["error_message"] == "Test error"
        assert event.data["context"] == "test"
    finally:
        await engine.event_bus.stop()


@pytest.mark.asyncio
async def test_eventbus_lifecycle_management():
    """Test that engine manages EventBus lifecycle correctly"""
    engine = P2PEngine()

    # EventBus should not be running initially
    assert not engine.event_bus._running

    # Initialize should start EventBus
    await engine.initialize()
    assert engine.event_bus._running

    # Disconnect should stop EventBus
    await engine.disconnect()
    assert not engine.event_bus._running


@pytest.mark.asyncio
async def test_shared_eventbus_not_stopped():
    """Test that shared EventBus is not stopped by engine"""
    event_bus = EventBus()
    await event_bus.start()

    engine = P2PEngine(event_bus=event_bus)
    await engine.initialize()

    # Engine should not stop shared EventBus
    await engine.disconnect()
    assert event_bus._running

    # Clean up
    await event_bus.stop()
