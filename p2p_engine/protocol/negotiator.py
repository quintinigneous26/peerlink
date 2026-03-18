"""
multistream-select 协议协商器

实现 libp2p 兼容的协议协商流程:
1. 双方交换 multistream 协议 ID
2. 发起方提议协议
3. 接收方响应支持 (echo) 或不支持 (na)

参考: https://github.com/libp2p/specs/blob/master/connections/README.md
"""

import asyncio
import logging
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass

from .messages import (
    encode_message,
    decode_message,
    MULTISTREAM_PROTOCOL_ID,
    NA_RESPONSE,
    is_valid_protocol_id,
    is_multistream_protocol,
    is_na_response,
)


logger = logging.getLogger(__name__)


# ==================== 异常定义 ====================

class NegotiationError(Exception):
    """协议协商失败异常"""

    def __init__(self, message: str, tried_protocols: Optional[list[str]] = None):
        super().__init__(message)
        self.tried_protocols = tried_protocols or []


class ProtocolNotSupportedError(NegotiationError):
    """协议不支持异常"""

    def __init__(self, protocol: str):
        super().__init__(f"Protocol not supported: {protocol}")
        self.protocol = protocol


class HandshakeError(NegotiationError):
    """握手失败异常"""

    def __init__(self, message: str, expected: str, actual: str):
        super().__init__(message)
        self.expected = expected
        self.actual = actual


# ==================== 连接接口 ====================

class StreamReaderWriter:
    """
    流读写接口抽象

    包装任何支持异步读写操作的对象，提供统一的接口。
    兼容 asyncio.StreamReader/Writer 和其他类似接口。
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer

    async def read(self, n: int = -1) -> bytes:
        """读取数据"""
        if n == -1:
            return await self.reader.read()
        return await self.reader.read(n)

    async def write(self, data: bytes) -> None:
        """写入数据"""
        self.writer.write(data)
        await self.writer.drain()

    def close(self) -> None:
        """关闭连接"""
        self.writer.close()

    async def closed(self) -> bool:
        """检查连接是否已关闭"""
        if hasattr(self.writer, 'is_closing'):
            return self.writer.is_closing()
        return False

    @classmethod
    def from_stream(cls, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """从 asyncio StreamReader/Writer 创建"""
        return cls(reader, writer)


# ==================== 协议协商器 ====================

@dataclass
class NegotiationResult:
    """协商结果"""
    protocol: str           # 协商成功的协议
    tried_protocols: list[str]  # 尝试过的协议列表
    is_initiator: bool      # 是否为发起方
    rounds: int = 1         # 协商轮数


class ProtocolNegotiator:
    """
    multistream-select 协议协商器

    支持两种角色:
    - Initiator: 发起协商，提议协议
    - Responder: 响应协商，接受或拒绝协议

    同时打开场景:
    - 双方同时发送 multistream 协议 ID
    - 后续通过 tie-breaker 决定主导权
    """

    def __init__(
        self,
        timeout: float = 30.0,
        simultaneous_open_delay: float = 0.1,
    ):
        """
        初始化协商器

        Args:
            timeout: 协商超时时间（秒）
            simultaneous_open_delay: 同时打开场景下的延迟（秒）
        """
        self.timeout = timeout
        self.simultaneous_open_delay = simultaneous_open_delay

    async def negotiate(
        self,
        conn: StreamReaderWriter,
        protocols: list[str],
    ) -> str:
        """
        作为发起方进行协议协商

        Args:
            conn: 连接对象
            protocols: 希望协商的协议列表（按优先级排序）

        Returns:
            协商成功的协议 ID

        Raises:
            NegotiationError: 协商失败
            ValueError: 参数无效
        """
        if not protocols:
            raise ValueError("协议列表不能为空")

        # 验证所有协议 ID
        for proto in protocols:
            if not is_valid_protocol_id(proto):
                raise ValueError(f"无效的协议 ID: {proto}")

        tried_protocols = []

        try:
            # 步骤1: 发送 multistream 协议 ID
            logger.debug(f"[Initiator] 发送 multistream 协议 ID")
            await self._send_with_timeout(conn, encode_message(MULTISTREAM_PROTOCOL_ID))

            # 步骤2: 接收对方的 multistream 协议 ID
            logger.debug("[Initiator] 等待对方 multistream 协议 ID")
            response = await self._recv_with_timeout(conn)
            handshake_msg = decode_message(response)

            if not is_multistream_protocol(handshake_msg):
                raise HandshakeError(
                    f"期望收到 multistream 协议 ID",
                    expected=MULTISTREAM_PROTOCOL_ID,
                    actual=handshake_msg
                )

            logger.debug(f"[Initiator] 握手成功: {handshake_msg}")

            # 步骤3: 尝试每个协议
            for proto in protocols:
                tried_protocols.append(proto)
                logger.debug(f"[Initiator] 提议协议: {proto}")

                await self._send_with_timeout(conn, encode_message(proto))

                response = await self._recv_with_timeout(conn)
                response_msg = decode_message(response)

                if is_multistream_protocol(response_msg):
                    # 对方也发送了 multistream 协议 ID，说明是同时打开场景
                    # 需要重新发送协议提议
                    logger.debug("[Initiator] 检测到同时打开，重新提议协议")
                    await self._send_with_timeout(conn, encode_message(proto))

                    response = await self._recv_with_timeout(conn)
                    response_msg = decode_message(response)

                if response_msg == proto:
                    # 对方接受该协议
                    logger.info(f"[Initiator] 协议协商成功: {proto}")
                    return proto
                elif is_na_response(response_msg):
                    # 对方拒绝该协议，尝试下一个
                    logger.debug(f"[Initiator] 协议 {proto} 不被支持，尝试下一个")
                    continue
                else:
                    # 未知响应
                    logger.warning(f"[Initiator] 未知响应: {response_msg}")
                    raise NegotiationError(f"未知的协商响应: {response_msg}")

            # 所有协议都被拒绝
            raise NegotiationError(
                "没有找到共同支持的协议",
                tried_protocols=tried_protocols
            )

        except asyncio.TimeoutError:
            raise NegotiationError(
                f"协议协商超时 ({self.timeout}s)",
                tried_protocols=tried_protocols
            )

    async def handle_negotiate(
        self,
        conn: StreamReaderWriter,
        supported: list[str],
        protocol_handler: Optional[Callable[[str, StreamReaderWriter], Awaitable[None]]] = None,
    ) -> str:
        """
        作为响应方处理协议协商

        Args:
            conn: 连接对象
            supported: 支持的协议列表
            protocol_handler: 协议处理函数 (协议协商成功后调用)

        Returns:
            协商成功的协议 ID

        Raises:
            NegotiationError: 协商失败
        """
        if not supported:
            raise ValueError("支持的协议列表不能为空")

        # 创建支持协议的集合用于快速查找
        supported_set = set(supported)

        try:
            # 步骤1: 接收对方的 multistream 协议 ID（可选同时发送）
            logger.debug("[Responder] 等待对方 multistream 协议 ID")

            # 同时发送 multistream 协议 ID
            send_task = asyncio.create_task(
                self._send_with_timeout(conn, encode_message(MULTISTREAM_PROTOCOL_ID))
            )
            recv_task = asyncio.create_task(self._recv_with_timeout(conn))

            # 等待接收和发送都完成
            await send_task
            response = await recv_task
            handshake_msg = decode_message(response)

            if not is_multistream_protocol(handshake_msg):
                raise HandshakeError(
                    f"期望收到 multistream 协议 ID",
                    expected=MULTISTREAM_PROTOCOL_ID,
                    actual=handshake_msg
                )

            logger.debug(f"[Responder] 握手成功: {handshake_msg}")

            # 步骤2: 持续接收协议提议并响应
            while True:
                # 接收协议提议
                response = await self._recv_with_timeout(conn)
                proposed_proto = decode_message(response)

                logger.debug(f"[Responder] 收到协议提议: {proposed_proto}")

                # 检查是否是 multistream 协议 ID (同时打开场景)
                if is_multistream_protocol(proposed_proto):
                    logger.debug("[Responder] 检测到同时打开，等待实际协议提议")
                    continue

                # 检查协议是否支持
                if proposed_proto in supported_set:
                    # 支持该协议，echo 响应
                    logger.info(f"[Responder] 接受协议: {proposed_proto}")
                    await self._send_with_timeout(conn, encode_message(proposed_proto))

                    # 调用协议处理器（如果提供）
                    if protocol_handler:
                        await protocol_handler(proposed_proto, conn)

                    return proposed_proto
                else:
                    # 不支持该协议，响应 "na"
                    logger.debug(f"[Responder] 协议 {proposed_proto} 不支持")
                    await self._send_with_timeout(conn, encode_message(NA_RESPONSE))

        except asyncio.TimeoutError:
            raise NegotiationError(f"协议协商超时 ({self.timeout}s)")

    async def full_negotiate(
        self,
        conn: StreamReaderWriter,
        protocols: list[str],
    ) -> str:
        """
        完整协商流程，同时处理发起和响应

        用于同时打开场景，双方同时发送协议提议。

        Args:
            conn: 连接对象
            protocols: 我方支持的协议列表

        Returns:
            协商成功的协议 ID

        Raises:
            NegotiationError: 协商失败
        """
        # 同时发送 multistream 协议 ID
        send_task = asyncio.create_task(
            self._send_with_timeout(conn, encode_message(MULTISTREAM_PROTOCOL_ID))
        )
        recv_task = asyncio.create_task(self._recv_with_timeout(conn))

        await send_task
        response = await recv_task
        handshake_msg = decode_message(response)

        if not is_multistream_protocol(handshake_msg):
            raise HandshakeError(
                f"期望收到 multistream 协议 ID",
                expected=MULTISTREAM_PROTOCOL_ID,
                actual=handshake_msg
            )

        # 同时发送第一个协议提议
        first_proto = protocols[0]
        send_task = asyncio.create_task(
            self._send_with_timeout(conn, encode_message(first_proto))
        )
        recv_task = asyncio.create_task(self._recv_with_timeout(conn))

        await send_task
        response = await recv_task
        response_msg = decode_message(response)

        if is_multistream_protocol(response_msg):
            # 同时打开，重新发送协议提议
            await self._send_with_timeout(conn, encode_message(first_proto))
            response = await self._recv_with_timeout(conn)
            response_msg = decode_message(response)

        if response_msg == first_proto:
            return first_proto
        elif is_na_response(response_msg):
            # 尝试下一个协议
            for proto in protocols[1:]:
                await self._send_with_timeout(conn, encode_message(proto))
                response = await self._recv_with_timeout(conn)
                response_msg = decode_message(response)
                if response_msg == proto:
                    return proto

        raise NegotiationError("没有找到共同支持的协议")

    async def _send_with_timeout(self, conn: StreamReaderWriter, data: bytes) -> None:
        """带超时的发送"""
        try:
            await asyncio.wait_for(conn.write(data), timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.error(f"发送数据超时 ({self.timeout}s)")
            raise

    async def _recv_with_timeout(self, conn: StreamReaderWriter) -> bytes:
        """带超时的接收"""
        try:
            data = await asyncio.wait_for(conn.read(), timeout=self.timeout)
            if not data:
                raise ConnectionError("连接已关闭")
            return data
        except asyncio.TimeoutError:
            logger.error(f"接收数据超时 ({self.timeout}s)")
            raise
