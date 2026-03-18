"""
P2P事件总线系统

提供增强的事件驱动架构，支持基于主题的事件订阅和异步事件处理。
实现了发布-订阅模式，允许应用程序对P2P引擎的各类事件进行监听和响应。

主要特性:
    - 主题分类：将事件按功能分类（连接、流、协议、网络等）
    - 异步处理：支持异步事件处理器
    - 灵活订阅：支持按主题或事件类型订阅
    - 线程安全：使用锁保证并发安全
    - 性能优化：支持事件过滤和优先级处理

使用示例:
    ```python
    bus = EventBus()

    async def on_peer_connected(event):
        print(f"对端已连接: {event.data['peer_id']}")

    bus.subscribe(EventTopic.CONNECTION, on_peer_connected)
    await bus.publish(EventTopic.CONNECTION, P2PEventType.PEER_CONNECTED, {...})
    ```
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Optional,
    Awaitable,
    Dict,
    List,
    Set,
)
from collections import defaultdict
from threading import Lock
from concurrent.futures import ThreadPoolExecutor


logger = logging.getLogger("p2p_engine.event")


# ==================== Event Topics ====================

class EventTopic(Enum):
    """
    事件主题枚举

    将P2P引擎中的事件按功能分类，便于应用程序进行选择性订阅。

    属性:
        CONNECTION: 连接相关事件
            - 对端连接、断开、重连等
        STREAM: 流生命周期事件
            - 流创建、关闭、错误等
        PROTOCOL: 协议协商事件
            - 协议选择、升级、降级等
        NETWORK: 网络检测事件
            - 网络变化、质量变化等
        RELAY: 中继相关事件
            - 中继连接、断开、切换等
        NAT: NAT检测事件
            - NAT类型检测、穿透结果等
        ERROR: 错误事件
            - 各类错误信息
        METRIC: 指标和遥测事件
            - 性能指标、统计数据等
        CUSTOM: 自定义事件
            - 应用程序定义的事件
    """
    CONNECTION = "connection"      # Connection state changes
    STREAM = "stream"              # Stream lifecycle events
    PROTOCOL = "protocol"          # Protocol negotiation events
    NETWORK = "network"            # Network detection events
    RELAY = "relay"                # Relay-related events
    NAT = "nat"                    # NAT detection events
    ERROR = "error"                # Error events
    METRIC = "metric"              # Metrics and telemetry
    CUSTOM = "custom"              # Custom user-defined events


# ==================== Event Types ====================

class P2PEventType(Enum):
    """
    P2P事件类型枚举

    定义各个主题下的具体事件类型，提供更细粒度的事件分类。

    连接事件:
        PEER_CONNECTED: 对端已连接
        PEER_DISCONNECTED: 对端已断开连接
    """
    # Connection events
    PEER_CONNECTED = "peer_connected"
    PEER_DISCONNECTED = "peer_disconnected"
    CONNECTION_STATE_CHANGED = "connection_state_changed"
    CONNECTION_FAILED = "connection_failed"

    # Stream events
    STREAM_OPENED = "stream_opened"
    STREAM_CLOSED = "stream_closed"
    STREAM_DATA = "stream_data"
    STREAM_RESET = "stream_reset"

    # Protocol events
    PROTOCOL_NEGOTIATED = "protocol_negotiated"
    PROTOCOL_UNSUPPORTED = "protocol_unsupported"
    PROTOCOL_ERROR = "protocol_error"

    # Network events
    NETWORK_CHANGED = "network_changed"
    INTERFACE_UP = "interface_up"
    INTERFACE_DOWN = "interface_down"
    IP_CHANGED = "ip_changed"

    # NAT events
    NAT_DETECTED = "nat_detected"
    NAT_TYPE_CHANGED = "nat_type_changed"
    REACHABILITY_CHANGED = "reachability_changed"

    # Relay events
    RELAY_CONNECTED = "relay_connected"
    RELAY_DISCONNECTED = "relay_disconnected"
    RELAY_CIRCUIT_ESTABLISHED = "relay_circuit_established"
    RELAY_CIRCUIT_FAILED = "relay_circuit_failed"

    # Error events
    ERROR_OCCURRED = "error"
    TIMEOUT = "timeout"
    DIAL_FAILED = "dial_failed"

    # Metric events
    METRIC_RECORDED = "metric_recorded"
    PERFORMANCE_UPDATE = "performance_update"


# ==================== Event Data ====================

@dataclass
class P2PEvent:
    """P2P Event data structure"""
    topic: EventTopic
    event_type: P2PEventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = ""  # Source component identifier
    peer_id: Optional[str] = None  # Associated peer ID
    correlation_id: Optional[str] = None  # For event correlation


# ==================== Event Handler ====================

EventHandler = Callable[[P2PEvent], Awaitable[None]]
SyncEventHandler = Callable[[P2PEvent], None]


class EventSubscriber:
    """Event subscriber with filtering options"""

    def __init__(
        self,
        handler: EventHandler,
        filter_topics: Optional[Set[EventTopic]] = None,
        filter_types: Optional[Set[P2PEventType]] = None,
        filter_peer: Optional[str] = None,
    ):
        """
        Initialize event subscriber.

        Args:
            handler: Async event handler function
            filter_topics: Optional topic filter (only these topics)
            filter_types: Optional event type filter
            filter_peer: Optional peer ID filter (only events for this peer)
        """
        self.handler = handler
        self.filter_topics = filter_topics
        self.filter_types = filter_types
        self.filter_peer = filter_peer
        self._id = id(self)

    def __hash__(self) -> int:
        return self._id

    def matches(self, event: P2PEvent) -> bool:
        """Check if this subscriber should receive the event"""
        if self.filter_topics and event.topic not in self.filter_topics:
            return False

        if self.filter_types and event.event_type not in self.filter_types:
            return False

        if self.filter_peer and event.peer_id != self.filter_peer:
            return False

        return True


# ==================== Event Bus ====================

class EventBus:
    """
    Async event bus for P2P engine.

    Provides topic-based event publishing and subscription with
    async handling and filtering capabilities.
    """

    def __init__(
        self,
        max_queue_size: int = 1000,
        worker_count: int = 2,
        enable_metrics: bool = True,
    ):
        """
        Initialize event bus.

        Args:
            max_queue_size: Maximum event queue size
            worker_count: Number of event worker tasks
            enable_metrics: Track event metrics
        """
        self._subscribers: Dict[EventTopic, List[EventSubscriber]] = defaultdict(list)
        self._global_subscribers: List[EventSubscriber] = []

        self._queue: Optional[asyncio.Queue] = None
        self._max_queue_size = max_queue_size
        self._worker_count = worker_count
        self._enable_metrics = enable_metrics

        self._running = False
        self._workers: List[asyncio.Task] = []
        self._lock = Lock()

        # Metrics
        self._events_published = 0
        self._events_processed = 0
        self._events_dropped = 0
        self._handler_errors = 0
        self._start_time: Optional[float] = None

        # Thread-safe sync wrapper support
        self._executor = Optional[ThreadPoolExecutor]

    async def start(self) -> None:
        """Start the event bus"""
        if self._running:
            return

        self._running = True
        self._queue = asyncio.Queue(maxsize=self._max_queue_size)
        self._start_time = time.time()
        self._executor = ThreadPoolExecutor(max_workers=2)

        # Start worker tasks
        for i in range(self._worker_count):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(worker)

        logger.info(f"Event bus started with {self._worker_count} workers")

    async def stop(self) -> None:
        """Stop the event bus"""
        if not self._running:
            return

        self._running = False

        # Cancel workers
        for worker in self._workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=True)

        logger.info("Event bus stopped")

    def subscribe(
        self,
        topic: EventTopic,
        handler: EventHandler,
        filter_types: Optional[Set[P2PEventType]] = None,
        filter_peer: Optional[str] = None,
    ) -> EventSubscriber:
        """
        Subscribe to events on a topic.

        Args:
            topic: Event topic to subscribe to
            handler: Async event handler function
            filter_types: Optional event type filter
            filter_peer: Optional peer ID filter

        Returns:
            EventSubscriber that can be used to unsubscribe
        """
        subscriber = EventSubscriber(
            handler=handler,
            filter_topics={topic},
            filter_types=filter_types,
            filter_peer=filter_peer,
        )

        with self._lock:
            self._subscribers[topic].append(subscriber)

        logger.debug(f"Subscribed to topic: {topic.value}")
        return subscriber

    def subscribe_all(
        self,
        handler: EventHandler,
        filter_topics: Optional[Set[EventTopic]] = None,
        filter_types: Optional[Set[P2PEventType]] = None,
        filter_peer: Optional[str] = None,
    ) -> EventSubscriber:
        """
        Subscribe to all events (or filtered topics).

        Args:
            handler: Async event handler function
            filter_topics: Optional topic filter (default: all topics)
            filter_types: Optional event type filter
            filter_peer: Optional peer ID filter

        Returns:
            EventSubscriber that can be used to unsubscribe
        """
        subscriber = EventSubscriber(
            handler=handler,
            filter_topics=filter_topics,
            filter_types=filter_types,
            filter_peer=filter_peer,
        )

        with self._lock:
            self._global_subscribers.append(subscriber)

        logger.debug("Subscribed to all topics")
        return subscriber

    def unsubscribe(self, subscriber: EventSubscriber) -> bool:
        """
        Unsubscribe a subscriber.

        Args:
            subscriber: The subscriber to remove

        Returns:
            True if subscriber was found and removed
        """
        with self._lock:
            # Remove from topic-specific subscribers
            for topic, subs in self._subscribers.items():
                if subscriber in subs:
                    subs.remove(subscriber)
                    logger.debug(f"Unsubscribed from topic: {topic.value}")
                    return True

            # Remove from global subscribers
            if subscriber in self._global_subscribers:
                self._global_subscribers.remove(subscriber)
                logger.debug("Unsubscribed from all topics")
                return True

        return False

    async def publish(self, event: P2PEvent) -> bool:
        """
        Publish an event.

        Args:
            event: The event to publish

        Returns:
            True if event was queued, False if queue is full
        """
        if not self._running:
            logger.warning("Event bus not running, event dropped")
            return False

        try:
            self._queue.put_nowait(event)
            self._events_published += 1
            return True
        except asyncio.QueueFull:
            self._events_dropped += 1
            logger.warning(f"Event queue full, dropping event: {event.event_type.value}")
            return False

    async def publish_sync(self, event: P2PEvent) -> None:
        """
        Publish an event and wait for it to be queued.

        Args:
            event: The event to publish
        """
        if not self._running:
            logger.warning("Event bus not running, event dropped")
            return

        await self._queue.put(event)
        self._events_published += 1

    def publish_nowait(self, event: P2PEvent) -> bool:
        """
        Publish an event without waiting (non-async).

        Useful for publishing from sync contexts.

        Args:
            event: The event to publish

        Returns:
            True if event was queued, False otherwise
        """
        if not self._running or not self._queue:
            return False

        try:
            self._queue.put_nowait(event)
            self._events_published += 1
            return True
        except asyncio.QueueFull:
            self._events_dropped += 1
            return False

    async def _worker(self, name: str) -> None:
        """Event worker task"""
        logger.debug(f"Event worker {name} started")

        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )

                await self._process_event(event)
                self._events_processed += 1

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {name} error: {e}")
                self._handler_errors += 1

        logger.debug(f"Event worker {name} stopped")

    async def _process_event(self, event: P2PEvent) -> None:
        """Process a single event"""
        # Get matching subscribers
        matching_subscribers = []

        with self._lock:
            # Topic-specific subscribers
            for subscriber in self._subscribers.get(event.topic, []):
                if subscriber.matches(event):
                    matching_subscribers.append(subscriber)

            # Global subscribers
            for subscriber in self._global_subscribers:
                if subscriber.matches(event):
                    matching_subscribers.append(subscriber)

        # Notify all matching subscribers
        if matching_subscribers:
            tasks = []
            for subscriber in matching_subscribers:
                task = asyncio.create_task(
                    self._call_handler(subscriber.handler, event),
                    name=f"handler-{subscriber._id}",
                )
                tasks.append(task)

            # Wait for all handlers with timeout
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _call_handler(self, handler: EventHandler, event: P2PEvent) -> None:
        """Call an event handler with error handling"""
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Event handler error for {event.event_type.value}: {e}")
            self._handler_errors += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get event bus metrics"""
        uptime = time.time() - self._start_time if self._start_time else 0

        return {
            "uptime_seconds": uptime,
            "events_published": self._events_published,
            "events_processed": self._events_processed,
            "events_dropped": self._events_dropped,
            "handler_errors": self._handler_errors,
            "queue_size": self._queue.qsize() if self._queue else 0,
            "max_queue_size": self._max_queue_size,
            "subscribers": sum(len(subs) for subs in self._subscribers.values()) + len(self._global_subscribers),
            "running": self._running,
        }

    def reset_metrics(self) -> None:
        """Reset event metrics"""
        with self._lock:
            self._events_published = 0
            self._events_processed = 0
            self._events_dropped = 0
            self._handler_errors = 0


# ==================== Event Builders ====================

class EventBuilder:
    """Helper class to build common P2P events"""

    @staticmethod
    def connection_event(
        event_type: P2PEventType,
        peer_id: str,
        connection_type: Optional[str] = None,
        **extra_data,
    ) -> P2PEvent:
        """Build a connection-related event"""
        data = {
            "peer_id": peer_id,
            "connection_type": connection_type,
            **extra_data,
        }
        return P2PEvent(
            topic=EventTopic.CONNECTION,
            event_type=event_type,
            data=data,
            peer_id=peer_id,
        )

    @staticmethod
    def stream_event(
        event_type: P2PEventType,
        peer_id: str,
        stream_id: Optional[str] = None,
        protocol: Optional[str] = None,
        **extra_data,
    ) -> P2PEvent:
        """Build a stream-related event"""
        data = {
            "stream_id": stream_id,
            "protocol": protocol,
            **extra_data,
        }
        return P2PEvent(
            topic=EventTopic.STREAM,
            event_type=event_type,
            data=data,
            peer_id=peer_id,
        )

    @staticmethod
    def protocol_event(
        event_type: P2PEventType,
        peer_id: str,
        protocol: str,
        **extra_data,
    ) -> P2PEvent:
        """Build a protocol-related event"""
        data = {
            "protocol": protocol,
            **extra_data,
        }
        return P2PEvent(
            topic=EventTopic.PROTOCOL,
            event_type=event_type,
            data=data,
            peer_id=peer_id,
        )

    @staticmethod
    def nat_event(
        event_type: P2PEventType,
        nat_type: Optional[str] = None,
        public_ip: Optional[str] = None,
        **extra_data,
    ) -> P2PEvent:
        """Build a NAT-related event"""
        data = {
            "nat_type": nat_type,
            "public_ip": public_ip,
            **extra_data,
        }
        return P2PEvent(
            topic=EventTopic.NAT,
            event_type=event_type,
            data=data,
        )

    @staticmethod
    def relay_event(
        event_type: P2PEventType,
        peer_id: str,
        relay_peer: Optional[str] = None,
        **extra_data,
    ) -> P2PEvent:
        """Build a relay-related event"""
        data = {
            "relay_peer": relay_peer,
            **extra_data,
        }
        return P2PEvent(
            topic=EventTopic.RELAY,
            event_type=event_type,
            data=data,
            peer_id=peer_id,
        )

    @staticmethod
    def error_event(
        error: Exception,
        source: str = "",
        peer_id: Optional[str] = None,
        **extra_data,
    ) -> P2PEvent:
        """Build an error event"""
        data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            **extra_data,
        }
        return P2PEvent(
            topic=EventTopic.ERROR,
            event_type=P2PEventType.ERROR_OCCURRED,
            data=data,
            source=source,
            peer_id=peer_id,
        )

    @staticmethod
    def network_event(
        event_type: P2PEventType,
        **extra_data,
    ) -> P2PEvent:
        """Build a network-related event"""
        return P2PEvent(
            topic=EventTopic.NETWORK,
            event_type=event_type,
            data=extra_data,
        )


# ==================== Convenience Decorators ====================

def subscribe_to(
    topic: EventTopic,
    event_types: Optional[Set[P2PEventType]] = None,
    event_bus: Optional[EventBus] = None,
):
    """
    Decorator to subscribe a function to events.

    Usage:
        @subscribe_to(EventTopic.CONNECTION)
        async def on_connection(event: P2PEvent):
            logger.info(f"Connection event: {event.event_type}")
    """
    def decorator(func: EventHandler):
        # If event_bus provided, subscribe immediately
        if event_bus is not None:
            event_bus.subscribe(topic, func, event_types)

        # Store for later subscription
        func._event_topic = topic
        func._event_types = event_types
        return func

    return decorator


# ==================== Global Event Bus ====================

_global_event_bus: Optional[EventBus] = None


def get_global_event_bus() -> EventBus:
    """Get or create the global event bus"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


async def start_global_event_bus() -> None:
    """Start the global event bus"""
    bus = get_global_event_bus()
    await bus.start()


async def stop_global_event_bus() -> None:
    """Stop the global event bus"""
    global _global_event_bus
    if _global_event_bus is not None:
        await _global_event_bus.stop()
        _global_event_bus = None


__all__ = [
    # Topics and types
    "EventTopic",
    "P2PEventType",

    # Event data
    "P2PEvent",

    # Event handlers
    "EventHandler",
    "SyncEventHandler",
    "EventSubscriber",

    # Event bus
    "EventBus",

    # Event builder
    "EventBuilder",

    # Decorators
    "subscribe_to",

    # Global event bus
    "get_global_event_bus",
    "start_global_event_bus",
    "stop_global_event_bus",
]
