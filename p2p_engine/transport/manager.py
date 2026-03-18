"""
Transport Manager - 传输管理器

管理多个传输协议，提供统一的拨号和监听接口。
支持多传输自动选择和故障转移。
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any, Callable, Awaitable

from .base import Transport, Connection, Listener, TransportError
from .upgrader import TransportUpgrader, UpgradedConnection

logger = logging.getLogger("p2p_engine.transport.manager")


class DialError(TransportError):
    """拨号错误"""
    pass


class ListenError(TransportError):
    """监听错误"""
    pass


class TransportManager:
    """
    传输管理器

    管理多个传输协议，提供统一的接口。
    """

    def __init__(
        self,
        local_peer_id: str,
        upgrader: Optional[TransportUpgrader] = None
    ):
        """
        初始化传输管理器

        Args:
            local_peer_id: 本地对等节点ID
            upgrader: 可选的传输升级器
        """
        self._local_peer_id = local_peer_id
        self._upgrader = upgrader
        self._transports: Dict[str, Transport] = {}
        self._listeners: Dict[str, Listener] = {}
        self._dial_timeout: float = 30.0
        self._prefer_order: List[str] = []
        self._closed = False

    @property
    def local_peer_id(self) -> str:
        """本地对等节点ID"""
        return self._local_peer_id

    @property
    def upgrader(self) -> Optional[TransportUpgrader]:
        """获取传输升级器"""
        return self._upgrader

    def setUpgrader(self, upgrader: TransportUpgrader) -> None:
        """设置传输升级器"""
        self._upgrader = upgrader

    def add_transport(self, transport: Transport, priority: int = 0) -> None:
        """
        添加传输协议

        Args:
            transport: 传输实例
            priority: 优先级（数字越小优先级越高）
        """
        for protocol in transport.protocols():
            key = f"{priority}:{protocol}"
            self._transports[key] = transport

        # 更新优先级顺序
        self._prefer_order = sorted(self._transports.keys())

        logger.debug(
            f"Added transport {transport.protocols()} "
            f"with priority {priority}"
        )

    def remove_transport(self, protocol: str) -> None:
        """移除传输协议"""
        keys_to_remove = [k for k in self._transports if k.endswith(f":{protocol}")]
        for key in keys_to_remove:
            del self._transports[key]

        self._prefer_order = sorted(self._transports.keys())
        logger.debug(f"Removed transport {protocol}")

    def get_transport(self, protocol: str) -> Optional[Transport]:
        """获取指定协议的传输"""
        for key in self._prefer_order:
            if key.endswith(f":{protocol}"):
                return self._transports[key]
        return None

    def list_transports(self) -> List[str]:
        """列出所有已注册的传输协议"""
        protocols = set()
        for key in self._transports:
            _, protocol = key.split(":", 1)
            protocols.add(protocol)
        return sorted(protocols)

    async def listen(
        self,
        addr: str,
        protocol: Optional[str] = None
    ) -> Listener:
        """
        开始监听

        Args:
            addr: 监听地址
            protocol: 指定使用的传输协议，None表示自动选择

        Returns:
            监听器

        Raises:
            ListenError: 监听失败
        """
        if self._closed:
            raise ListenError("Transport manager is closed")

        transport = self._select_transport(protocol)
        if not transport:
            raise ListenError(f"No transport available for protocol: {protocol}")

        try:
            listener = await transport.listen(addr)
            self._listeners[addr] = listener
            logger.info(f"Listening on {addr} via {transport.protocols()}")
            return listener
        except Exception as e:
            raise ListenError(f"Listen failed: {e}") from e

    async def dial(
        self,
        addr: str,
        peer_id: str,
        protocol: Optional[str] = None
    ) -> UpgradedConnection:
        """
        建立连接

        Args:
            addr: 目标地址
            peer_id: 目标对等节点ID
            protocol: 指定使用的传输协议，None表示按优先级自动选择

        Returns:
            升级后的连接

        Raises:
            DialError: 连接失败
        """
        if self._closed:
            raise DialError("Transport manager is closed")

        if not self._upgrader:
            raise DialError("No upgrader configured")

        # 尝试按优先级拨号
        last_error = None
        tried_protocols = []

        for key in self._prefer_order:
            if protocol and not key.endswith(f":{protocol}"):
                continue

            transport = self._transports[key]
            _, proto = key.split(":", 1)
            tried_protocols.append(proto)

            try:
                logger.debug(f"Dialing {addr} via {proto}")
                conn = await asyncio.wait_for(
                    transport.dial(addr),
                    timeout=self._dial_timeout
                )

                # 升级连接
                upgraded = await self._upgrader.upgrade_outbound(conn, peer_id)
                logger.info(f"Connected to {peer_id} via {proto}")
                return upgraded

            except asyncio.TimeoutError:
                logger.debug(f"Dial timeout via {proto}")
                last_error = DialError(f"Dial timeout via {proto}")
            except Exception as e:
                logger.debug(f"Dial failed via {proto}: {e}")
                last_error = DialError(f"Dial failed: {e}")

        raise DialError(
            f"All dial attempts failed. Tried: {tried_protocols}. "
            f"Last error: {last_error}"
        )

    async def accept(self) -> tuple[str, UpgradedConnection]:
        """
        接受传入连接

        Returns:
            (peer_id, upgraded_connection) 元组

        Raises:
            TransportError: 接受失败
        """
        if not self._listeners:
            raise TransportError("No active listeners")

        if not self._upgrader:
            raise TransportError("No upgrader configured")

        # 等待任意监听器有连接
        tasks = []
        for addr, listener in self._listeners.items():
            task = asyncio.create_task(self._accept_from_listener(listener, addr))
            tasks.append(task)

        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED
        )

        # 取消其他任务
        for task in pending:
            task.cancel()

        for task in done:
            return await task

        raise TransportError("Accept failed")

    async def _accept_from_listener(
        self,
        listener: Listener,
        addr: str
    ) -> tuple[str, UpgradedConnection]:
        """从指定监听器接受连接"""
        try:
            conn = await listener.accept()

            # 升级连接
            upgraded = await self._upgrader.upgrade_inbound(conn)

            logger.info(
                f"Accepted connection from {upgraded.peer_id} "
                f"via {upgraded.security_protocol}"
            )
            return (upgraded.peer_id, upgraded)

        except Exception as e:
            logger.error(f"Accept error on {addr}: {e}")
            raise

    def set_dial_timeout(self, timeout: float) -> None:
        """设置拨号超时时间"""
        self._dial_timeout = timeout

    async def close(self) -> None:
        """关闭传输管理器"""
        if self._closed:
            return

        self._closed = True

        # 关闭所有监听器
        close_tasks = []
        for addr, listener in self._listeners.items():
            close_tasks.append(listener.close())

        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

        self._listeners.clear()

        # 关闭所有传输
        close_tasks = []
        for transport in set(self._transports.values()):
            close_tasks.append(transport.close())

        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)

        self._transports.clear()

        logger.info("Transport manager closed")

    def _select_transport(self, protocol: Optional[str]) -> Optional[Transport]:
        """选择传输"""
        if protocol:
            return self.get_transport(protocol)

        # 返回优先级最高的传输
        if self._prefer_order:
            return self._transports[self._prefer_order[0]]

        return None


class TransportBuilder:
    """
    传输构建器

    用于构建配置好的传输管理器。
    """

    def __init__(self, local_peer_id: str):
        self._local_peer_id = local_peer_id
        self._transports: List[tuple[Transport, int]] = []
        self._security_transports: List[Any] = []
        self._muxers: List[Any] = []

    def add_transport(self, transport: Transport, priority: int = 0) -> "TransportBuilder":
        """添加传输"""
        self._transports.append((transport, priority))
        return self

    def add_security(self, security_transport: Any) -> "TransportBuilder":
        """添加安全传输"""
        self._security_transports.append(security_transport)
        return self

    def add_muxer(self, muxer: Any) -> "TransportBuilder":
        """添加流复用器"""
        self._muxers.append(muxer)
        return self

    def build(self) -> TransportManager:
        """构建传输管理器"""
        # 创建升级器
        upgrader = TransportUpgrader(
            security_transports=self._security_transports,
            muxers=self._muxers
        )

        # 创建管理器
        manager = TransportManager(self._local_peer_id, upgrader)

        # 添加传输
        for transport, priority in self._transports:
            manager.add_transport(transport, priority)

        return manager


def create_transport_manager(
    local_peer_id: str,
    transports: Optional[List[Transport]] = None,
    security_transports: Optional[List[Any]] = None,
    muxers: Optional[List[Any]] = None
) -> TransportManager:
    """
    创建传输管理器的便捷函数

    Args:
        local_peer_id: 本地对等节点ID
        transports: 传输列表
        security_transports: 安全传输列表
        muxers: 流复用器列表

    Returns:
        配置好的传输管理器
    """
    builder = TransportBuilder(local_peer_id)

    if transports:
        for transport in transports:
            builder.add_transport(transport)

    if security_transports:
        for security in security_transports:
            builder.add_security(security)

    if muxers:
        for muxer in muxers:
            builder.add_muxer(muxer)

    return builder.build()
