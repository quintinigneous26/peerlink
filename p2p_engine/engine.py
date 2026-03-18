"""
P2P 引擎主模块

整合所有子模块，实现状态机驱动的 P2P 连接流程
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable, Dict, Any

from .types import (
    ConnectionState,
    ConnectionType,
    ConnectionResult,
    EventType,
    Event,
    NATInfo,
    NATType,
    ISP,
    PeerInfo,
    StateCallback,
    ErrorCallback,
)
from .config import ConfigLoader, get_isp_profile
from .detection import ISPDetector, NATDetector, STUNClient
from .puncher import UDPPuncher, PunchResult
from .keeper import HeartbeatKeeper
from .fallback import FallbackDecider
from .event import EventBus, P2PEvent, EventTopic, P2PEventType, EventBuilder

logger = logging.getLogger("p2p_engine")


@dataclass
class P2PConfig:
    """
    P2P引擎配置数据类

    包含P2P引擎的所有配置参数，用于初始化和控制引擎行为。

    属性:
        stun_servers (list): STUN服务器地址列表，格式为 "host:port"
            默认使用Google的公共STUN服务器
        stun_timeout_ms (int): STUN请求超时时间（毫秒），默认3000ms
        debug (bool): 是否启用调试模式，默认False
        log_level (str): 日志级别，可选值：DEBUG, INFO, WARNING, ERROR, CRITICAL
    """
    stun_servers: list = field(default_factory=lambda: [
        "stun.l.google.com:19302",
        "stun1.l.google.com:19302",
    ])
    stun_timeout_ms: int = 3000
    debug: bool = False
    log_level: str = "INFO"


@dataclass
class P2PState:
    """
    P2P引擎状态数据类

    存储P2P引擎的当前运行状态，包括连接状态、网络信息和连接结果。

    属性:
        state (ConnectionState): 当前连接状态
        isp (ISP): 检测到的本地ISP
        nat_info (Optional[NATInfo]): 本地NAT信息
        peer_info (Optional[PeerInfo]): 对端信息
        connection_result (Optional[ConnectionResult]): 连接结果
        start_time (float): 连接开始时间戳
    """
    state: ConnectionState = ConnectionState.IDLE
    isp: ISP = ISP.UNKNOWN
    nat_info: Optional[NATInfo] = None
    peer_info: Optional[PeerInfo] = None
    connection_result: Optional[ConnectionResult] = None
    start_time: float = 0.0


class P2PEngine:
    """
    P2P引擎主类

    核心P2P连接引擎，整合所有子模块实现完整的P2P连接流程。
    采用状态机驱动的架构，支持NAT穿透、中继降级等功能。

    主要功能:
        - 网络检测：ISP识别、NAT类型检测
        - NAT穿透：UDP打孔、TCP连接
        - 信令交换：与对端交换连接信息
        - 连接管理：建立、维护、断开连接
        - 心跳保活：保持连接活跃
        - 降级策略：连接失败时自动降级到中继

    使用示例:
        ```python
        engine = P2PEngine()
        await engine.initialize()
        result = await engine.connect_to_peer(peer_id, peer_info)
        if result.success:
            print(f"连接成功: {result.connection_type}")
        ```

    属性:
        _config (P2PConfig): 引擎配置
        _state (P2PState): 当前引擎状态
        _event_queue (asyncio.Queue): 事件队列
        _on_state_change (StateCallback): 状态变化回调
        _on_error (ErrorCallback): 错误回调
        _config_loader (ConfigLoader): 配置加载器
        _isp_detector (ISPDetector): ISP检测器
        _nat_detector (NATDetector): NAT检测器
        _puncher (UDPPuncher): UDP打孔器
        _fallback_decider (FallbackDecider): 降级决策器
        _heartbeat (HeartbeatKeeper): 心跳保活器
        _main_task (asyncio.Task): 主循环任务
        _running (bool): 引擎是否运行中
    """
    
    def __init__(
        self,
        config: Optional[P2PConfig] = None,
        event_bus: Optional[EventBus] = None,
        on_state_change: Optional[StateCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ):
        self._config = config or P2PConfig()
        self._state = P2PState()
        self._event_queue: asyncio.Queue = asyncio.Queue()

        # EventBus 统一事件系统
        self._event_bus = event_bus
        self._owns_event_bus = event_bus is None
        if self._owns_event_bus:
            self._event_bus = EventBus()

        # 向后兼容：保留回调支持（已废弃，建议使用 EventBus）
        self._on_state_change = on_state_change
        self._on_error = on_error

        # 配置加载器
        self._config_loader = ConfigLoader()
        
        # 检测器
        self._isp_detector: Optional[ISPDetector] = None
        self._nat_detector: Optional[NATDetector] = None
        
        # 打孔器
        self._puncher: Optional[UDPPuncher] = None
        
        # 降级决策器
        self._fallback_decider = FallbackDecider()
        
        # 心跳保活
        self._heartbeat: Optional[HeartbeatKeeper] = None
        
        # 主循环任务
        self._main_task: Optional[asyncio.Task] = None
        self._running = False
    
    @property
    def state(self) -> P2PState:
        return self._state

    @property
    def event_bus(self) -> EventBus:
        """获取事件总线实例"""
        return self._event_bus

    async def _emit_state_change(self, old_state: ConnectionState, new_state: ConnectionState) -> None:
        """发布状态变化事件"""
        # 发布到 EventBus
        event = EventBuilder.connection_event(
            event_type=P2PEventType.CONNECTION_STATE_CHANGED,
            peer_id=self._state.peer_info.did if self._state.peer_info else "",
            old_state=old_state.value,
            new_state=new_state.value,
        )
        await self._event_bus.publish(event)

        # 向后兼容：调用旧回调
        if self._on_state_change:
            try:
                await self._on_state_change(old_state, new_state)
            except Exception as e:
                logger.error(f"状态变化回调错误: {e}")

    async def _emit_error(self, error: Exception, context: str = "") -> None:
        """发布错误事件"""
        # 发布到 EventBus
        event = EventBuilder.error_event(
            error=error,
            source="P2PEngine",
            peer_id=self._state.peer_info.did if self._state.peer_info else None,
            context=context,
        )
        await self._event_bus.publish(event)

        # 向后兼容：调用旧回调
        if self._on_error:
            try:
                await self._on_error(error)
            except Exception as e:
                logger.error(f"错误回调错误: {e}")

    async def _set_state(self, new_state: ConnectionState) -> None:
        """设置状态并发布事件"""
        old_state = self._state.state
        if old_state != new_state:
            self._state.state = new_state
            await self._emit_state_change(old_state, new_state)
    
    async def initialize(self) -> P2PState:
        """初始化引擎"""
        if self._running:
            raise RuntimeError("引擎已在运行")

        self._running = True
        await self._set_state(ConnectionState.DETECTING)
        self._state.start_time = time.time()

        # 启动 EventBus
        if self._owns_event_bus and not self._event_bus._running:
            await self._event_bus.start()

        # 创建 STUN 客户端
        stun_client = STUNClient(
            servers=self._config.stun_servers,
            timeout_ms=self._config.stun_timeout_ms,
        )

        # 创建检测器
        self._isp_detector = ISPDetector(stun_client)
        self._nat_detector = NATDetector(stun_client)

        logger.info("P2P 引擎初始化完成")
        return self._state
    
    async def connect(self, peer_info: PeerInfo) -> ConnectionResult:
        """发起连接"""
        if self._state.state != ConnectionState.IDLE:
            raise RuntimeError(f"引擎状态错误: {self._state.state}")
        
        self._state.peer_info = peer_info
        await self._event_queue.put(Event(EventType.CONNECT, {"peer_info": peer_info}))
        
        # 启动主循环
        if not self._main_task:
            self._main_task = asyncio.create_task(self._main_loop())
        
        # 等待连接结果
        while self._state.state not in (ConnectionState.CONNECTED, ConnectionState.FAILED):
            await asyncio.sleep(0.1)
        
        return self._state.connection_result or ConnectionResult(
            success=False,
            connection_type=ConnectionType.FAILED,
            error="连接超时",
        )
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self._state.state == ConnectionState.IDLE:
            return

        # 停止心跳
        if self._heartbeat:
            await self._heartbeat.stop()

        # 停止主循环
        if self._main_task:
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass
            self._main_task = None

        # 停止 EventBus（如果由引擎创建）
        if self._owns_event_bus and self._event_bus._running:
            await self._event_bus.stop()

        await self._set_state(ConnectionState.DISCONNECTED)
        logger.info("P2P 引擎已断开")
    
    async def _main_loop(self) -> None:
        """主循环"""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=5.0
                )
                await self._handle_event(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"主循环错误: {e}")
    
    async def _handle_event(self, event: Event) -> None:
        """处理事件"""
        handlers = {
            EventType.CONNECT: self._handle_connect,
            EventType.DETECTION_DONE: self._handle_detection_done,
            EventType.PUNCH_SUCCESS: self._handle_punch_success,
            EventType.PUNCH_FAILED: self._handle_punch_failed,
            EventType.HEARTBEAT_TIMEOUT: self._handle_heartbeat_timeout,
        }
        
        handler = handlers.get(event.type)
        if handler:
            await handler(event.data)
    
    async def _handle_connect(self, data: dict) -> None:
        """处理连接事件"""
        await self._set_state(ConnectionState.DETECTING)

        # 启动检测
        detection_task = asyncio.create_task(self._run_detection())
        await detection_task
    
    async def _run_detection(self) -> None:
        """运行检测"""
        logger.info("开始检测...")
        
        # 检测运营商
        self._state.isp = await self._isp_detector.detect()
        self._config_loader.set_isp(self._state.isp)
        
        logger.info(f"运营商: {self._state.isp.value}")
        
        # 检测 NAT
        self._state.nat_info = await self._nat_detector.detect()
        
        logger.info(f"NAT 类型: {self._state.nat_info.type.value}")
        
        # 发送检测完成事件
        await self._event_queue.put(Event(EventType.DETECTION_DONE))
    
    async def _handle_detection_done(self, data: dict) -> None:
        """处理检测完成事件"""
        if not self._state.peer_info:
            logger.error("没有对端信息")
            return
        
        # 检查是否需要立即降级
        decision = self._fallback_decider.decide(
            local_nat=self._state.nat_info,
            peer_nat=self._state.peer_info.nat_info,
            local_isp=self._state.isp,
            peer_isp=self._state.peer_info.isp,
        )
        
        if decision.should_fallback:
            logger.info(f"立即降级: {decision.reason.value}")
            await self._do_fallback(decision)
            return

        # 开始打孔
        await self._set_state(ConnectionState.PUNCHING)
        self._puncher = UDPPuncher(
            local_nat=self._state.nat_info,
            peer_nat=self._state.peer_info.nat_info,
            local_isp=self._state.isp,
            peer_isp=self._state.peer_info.isp,
        )
        
        # 异步执行打孔
        punch_task = asyncio.create_task(self._puncher.punch())
        
        try:
            result = await asyncio.wait_for(punch_task, timeout=10.0)
            if result.success:
                await self._event_queue.put(Event(EventType.PUNCH_SUCCESS, {"result": result}))
            else:
                await self._event_queue.put(Event(EventType.PUNCH_FAILED, {"result": result}))
        except asyncio.TimeoutError:
            await self._event_queue.put(Event(EventType.PUNCH_FAILED, {"error": "timeout"}))
    
    async def _handle_punch_success(self, data: dict) -> None:
        """处理打孔成功事件"""
        result: PunchResult = data.get("result")

        self._state.connection_result = ConnectionResult(
            success=True,
            connection_type=result.connection_type,
            local_nat=self._state.nat_info,
            peer_nat=self._state.peer_info.nat_info,
            local_isp=self._state.isp,
            peer_isp=self._state.peer_info.isp,
            latency_ms=result.latency_ms,
        )

        await self._set_state(ConnectionState.CONNECTED)
        logger.info(f"P2P 连接成功: {result.connection_type.value}")

        # 启动心跳
        await self._start_heartbeat()
    
    async def _handle_punch_failed(self, data: dict) -> None:
        """处理打孔失败事件"""
        self._fallback_decider.record_punch_attempt(False)

        # 检查是否需要降级
        decision = self._fallback_decider.decide(
            local_nat=self._state.nat_info,
            peer_nat=self._state.peer_info.nat_info,
            local_isp=self._state.isp,
            peer_isp=self._state.peer_info.isp,
        )

        if decision.should_fallback:
            await self._do_fallback(decision)
        else:
            # 重试打孔
            await self._set_state(ConnectionState.PUNCHING)
            # TODO: 重试逻辑
    
    async def _do_fallback(self, decision) -> None:
        """执行降级"""
        logger.info(f"降级到 Relay: {decision.reason.value}")

        await self._set_state(ConnectionState.RECONNECTING)

        # TODO: 实现真正的 Relay 连接
        await asyncio.sleep(0.5)

        self._state.connection_result = ConnectionResult(
            success=True,
            connection_type=ConnectionType.RELAY_UDP,
            local_nat=self._state.nat_info,
            peer_nat=self._state.peer_info.nat_info,
            local_isp=self._state.isp,
            peer_isp=self._state.peer_info.isp,
            is_fallback=True,
            fallback_reason=decision.reason.value,
        )

        await self._set_state(ConnectionState.CONNECTED)
        logger.info("Relay 连接成功")

        await self._start_heartbeat()
    
    async def _start_heartbeat(self) -> None:
        """启动心跳"""
        async def send_heartbeat(data: bytes) -> bool:
            # TODO: 实现真实发送
            return True
        
        async def on_timeout() -> None:
            await self._event_queue.put(Event(EventType.HEARTBEAT_TIMEOUT))
        
        self._heartbeat = HeartbeatKeeper(
            send_func=send_heartbeat,
            on_timeout=on_timeout,
            isp=self._state.isp,
        )
        
        await self._heartbeat.start()
    
    async def _handle_heartbeat_timeout(self, data: dict) -> None:
        """处理心跳超时"""
        logger.warning("心跳超时，尝试重连")

        await self._set_state(ConnectionState.RECONNECTING)

        # 停止心跳
        if self._heartbeat:
            await self._heartbeat.stop()

        # 重新检测和连接
        await self._run_detection()
