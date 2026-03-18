"""
WebRTC DataChannel 传输实现

基于 aiortc 库实现 WebRTC DataChannel 支持，
实现浏览器与 Python 之间的 P2P 通信。

协议ID: /webrtc-direct

特性:
- WebRTC DataChannel 支持
- ICE 候选交换
- DTLS-SRTP 加密
- 与浏览器 WebRTC 互操作
"""

import asyncio
import json
import logging
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum

try:
    from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
    from aiortc import MediaStreamTrack, DataChannel
    from aiortc.sdp import SessionDescription
    from av import VideoFrame
    HAS_AIORTC = True
except ImportError:
    HAS_AIORTC = False
    RTCPeerConnection = None
    RTCSessionDescription = None
    RTCConfiguration = None
    RTCIceServer = None
    DataChannel = None

from .base import Transport, Connection, Listener, TransportError
from .base import ConnectionError as BaseConnectionError
from .base import ListenerError as BaseListenerError

# 兼容性别名
ConnectionError = BaseConnectionError
ListenerError = BaseListenerError

logger = logging.getLogger("p2p_engine.transport.webrtc")


# ==================== 协议常量 ====================

PROTOCOL_ID = "/webrtc-direct"
DEFAULT_STUN_SERVERS = [
    "stun:stun.l.google.com:19302",
    "stun:stun1.l.google.com:19302",
]

# DataChannel 配置
DEFAULT_DATA_CHANNEL_LABEL = "libp2p-webrtc"
MAX_DATA_CHANNEL_BUFFERED_AMOUNT = 16 * 1024 * 1024  # 16MB


# ==================== 信令消息类型 ====================

class SignalingMessageType(Enum):
    """信令消息类型"""
    OFFER = "offer"
    ANSWER = "answer"
    ICE_CANDIDATE = "ice_candidate"
    ERROR = "error"


@dataclass
class SignalingMessage:
    """信令消息"""
    type: SignalingMessageType
    data: Dict[str, Any]
    peer_id: str = ""

    def to_json(self) -> str:
        """转换为 JSON"""
        return json.dumps({
            "type": self.type.value,
            "data": self.data,
            "peer_id": self.peer_id,
        })

    @classmethod
    def from_json(cls, data: str) -> 'SignalingMessage':
        """从 JSON 解析"""
        obj = json.loads(data)
        return cls(
            type=SignalingMessageType(obj["type"]),
            data=obj["data"],
            peer_id=obj.get("peer_id", ""),
        )


# ==================== ICE 服务器配置 ====================

@dataclass
class ICEServer:
    """ICE 服务器配置"""
    urls: List[str]
    username: str = ""
    credential: str = ""

    def to_aiortc(self) -> RTCIceServer:
        """转换为 aiortc 格式"""
        if not HAS_AIORTC:
            raise RuntimeError("aiortc not installed")
        return RTCIceServer(
            urls=self.urls,
            username=self.username,
            credential=self.credential,
        )


# ==================== WebRTC 连接 ====================

class WebRTCConnection(Connection):
    """
    WebRTC 连接

    封装 WebRTC PeerConnection 和 DataChannel，
    提供 libp2p 传输层接口。
    """

    def __init__(
        self,
        peer_connection: 'RTCPeerConnection',
        data_channel: Optional['DataChannel'] = None,
        is_initiator: bool = False,
    ):
        if not HAS_AIORTC:
            raise RuntimeError("aiortc is required for WebRTC support")

        self._pc = peer_connection
        self._data_channel = data_channel
        self._is_initiator = is_initiator

        # 状态
        self._closed = False
        self._read_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._write_lock = asyncio.Lock()

        # 地址信息
        self._remote_address: Optional[tuple] = None
        self._local_address: Optional[tuple] = None

        # ICE 候选收集
        self._ice_candidates: List[Dict[str, Any]] = []
        self._ice_gathering_complete = asyncio.Event()

        # 连接状态
        self._connection_state = "new"
        self._ice_connection_state = "new"

        # 设置回调
        self._setup_callbacks()

    @property
    def peer_connection(self) -> 'RTCPeerConnection':
        """获取底层 PeerConnection"""
        return self._pc

    @property
    def data_channel(self) -> Optional['DataChannel']:
        """获取 DataChannel"""
        return self._data_channel

    @property
    def is_initiator(self) -> bool:
        """是否为发起方"""
        return self._is_initiator

    async def read(self, n: int = -1) -> bytes:
        """
        读取数据

        Args:
            n: 读取字节数，-1 表示读取所有

        Returns:
            读取的数据
        """
        if self._closed:
            raise ConnectionError("连接已关闭")

        try:
            data = await asyncio.wait_for(
                self._read_queue.get(),
                timeout=30.0
            )
            if data is None:
                return b""
            if n > 0:
                return data[:n]
            return data
        except asyncio.TimeoutError:
            raise ConnectionError("读取超时")

    async def write(self, data: bytes) -> int:
        """
        写入数据

        Args:
            data: 要写入的数据

        Returns:
            写入的字节数
        """
        if self._closed:
            raise ConnectionError("连接已关闭")

        if not self._data_channel:
            raise ConnectionError("DataChannel 未建立")

        async with self._write_lock:
            try:
                self._data_channel.send(data)
                return len(data)
            except Exception as e:
                raise ConnectionError(f"写入失败: {e}")

    async def close(self) -> None:
        """关闭连接"""
        if self._closed:
            return

        self._closed = True

        # 关闭 DataChannel
        if self._data_channel:
            try:
                self._data_channel.close()
            except Exception:
                pass

        # 关闭 PeerConnection
        if self._pc:
            try:
                await self._pc.close()
            except Exception:
                pass

        # 清空读取队列
        while not self._read_queue.empty():
            try:
                self._read_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        logger.debug("WebRTC 连接已关闭")

    def is_closed(self) -> bool:
        """检查连接是否已关闭"""
        return self._closed

    @property
    def remote_address(self) -> Optional[tuple]:
        """获取远程地址"""
        return self._remote_address

    @property
    def local_address(self) -> Optional[tuple]:
        """获取本地地址"""
        return self._local_address

    def get_local_description(self) -> Optional['RTCSessionDescription']:
        """获取本地 SDP 描述"""
        return self._pc.localDescription

    def get_remote_description(self) -> Optional['RTCSessionDescription']:
        """获取远程 SDP 描述"""
        return self._pc.remoteDescription

    async def create_offer(self) -> 'RTCSessionDescription':
        """
        创建 Offer

        Returns:
            SDP Offer
        """
        if not self._is_initiator:
            raise ConnectionError("只有发起方可以创建 Offer")

        offer = await self._pc.createOffer()
        await self._pc.setLocalDescription(offer)

        # 等待 ICE 收集完成
        await self._wait_for_ice_gathering()

        return self._pc.localDescription

    async def create_answer(self) -> 'RTCSessionDescription':
        """
        创建 Answer

        Returns:
            SDP Answer
        """
        if self._is_initiator:
            raise ConnectionError("只有应答方可以创建 Answer")

        answer = await self._pc.createAnswer()
        await self._pc.setLocalDescription(answer)

        # 等待 ICE 收集完成
        await self._wait_for_ice_gathering()

        return self._pc.localDescription

    async def set_remote_description(self, sdp: 'RTCSessionDescription') -> None:
        """
        设置远程 SDP 描述

        Args:
            sdp: 远程 SDP 描述
        """
        await self._pc.setRemoteDescription(sdp)

    def add_ice_candidate(self, candidate_dict: Dict[str, Any]) -> None:
        """
        添加 ICE 候选

        Args:
            candidate_dict: ICE 候选字典
        """
        from aiortc import RTCIceCandidate
        candidate = RTCIceCandidate(
            sdpMid=candidate_dict.get("sdpMid"),
            sdpMLineIndex=candidate_dict.get("sdpMLineIndex"),
            candidate=candidate_dict.get("candidate"),
        )
        self._pc.addIceCandidate(candidate)

    def get_ice_candidates(self) -> List[Dict[str, Any]]:
        """获取已收集的 ICE 候选"""
        return self._ice_candidates.copy()

    def _setup_callbacks(self) -> None:
        """设置回调函数"""
        # ICE 候选回调
        @self._pc.on("icecandidate")
        def on_ice_candidate(candidate):
            if candidate:
                candidate_dict = {
                    "sdpMid": candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                    "candidate": candidate.candidate,
                }
                self._ice_candidates.append(candidate_dict)
                logger.debug(f"ICE 候选: {candidate.candidate[:50]}...")
            else:
                # ICE 收集完成
                self._ice_gathering_complete.set()
                logger.debug("ICE 候选收集完成")

        # ICE 连接状态回调
        @self._pc.on("iceconnectionstatechange")
        def on_ice_connection_state_change():
            self._ice_connection_state = self._pc.iceConnectionState
            logger.debug(f"ICE 连接状态: {self._ice_connection_state}")

            if self._ice_connection_state in ["failed", "disconnected"]:
                # 连接失败或断开
                if not self._closed:
                    asyncio.create_task(self.close())

        # 连接状态回调
        @self._pc.on("connectionstatechange")
        def on_connection_state_change():
            self._connection_state = self._pc.connectionState
            logger.debug(f"连接状态: {self._connection_state}")

        # DataChannel 回调（应答方）
        if not self._is_initiator:
            @self._pc.on("datachannel")
            def on_datachannel(channel):
                self._data_channel = channel
                self._setup_data_channel_callbacks(channel)

    def _setup_data_channel_callbacks(self, channel: 'DataChannel') -> None:
        """设置 DataChannel 回调"""
        @channel.on("open")
        def on_datachannel_open():
            logger.debug("DataChannel 已打开")

        @channel.on("message")
        def on_datachannel_message(message):
            if isinstance(message, str):
                message = message.encode("utf-8")
            if not self._closed:
                asyncio.create_task(self._read_queue.put(message))

        @channel.on("close")
        def on_datachannel_close():
            logger.debug("DataChannel 已关闭")
            if not self._closed:
                asyncio.create_task(self.close())

        @channel.on("error")
        def on_datachannel_error(error):
            logger.error(f"DataChannel 错误: {error}")
            if not self._closed:
                asyncio.create_task(self.close())

    async def _wait_for_ice_gathering(self, timeout: float = 10.0) -> None:
        """等待 ICE 收集完成"""
        try:
            await asyncio.wait_for(
                self._ice_gathering_complete.wait(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("ICE 收集超时")


# ==================== WebRTC 监听器 ====================

class WebRTCListener(Listener):
    """
    WebRTC 监听器

    监听传入的 WebRTC 连接请求。
    通过信令服务器接收 SDP Offer 并创建 Answer。
    """

    def __init__(
        self,
        transport: 'WebRTCTransport',
        local_address: str,
    ):
        self._transport = transport
        self._local_address = local_address
        self._closed = False

        # 接受队列
        self._accept_queue: asyncio.Queue[WebRTCConnection] = asyncio.Queue()

        # 待处理的连接
        self._pending_connections: Dict[str, WebRTCConnection] = {}

    @property
    def transport(self) -> 'WebRTCTransport':
        """获取关联的传输"""
        return self._transport

    async def accept(self) -> WebRTCConnection:
        """
        接受传入连接

        Returns:
            新接受的连接
        """
        if self._closed:
            raise ListenerError("监听器已关闭")

        return await self._accept_queue.get()

    async def close(self) -> None:
        """关闭监听器"""
        if self._closed:
            return

        self._closed = True

        # 关闭所有待处理的连接
        for conn in self._pending_connections.values():
            try:
                await conn.close()
            except Exception:
                pass

        self._pending_connections.clear()

        # 清空接受队列
        while not self._accept_queue.empty():
            try:
                conn = self._accept_queue.get_nowait()
                await conn.close()
            except Exception:
                pass

        logger.debug(f"WebRTC 监听器已关闭: {self._local_address}")

    def is_closed(self) -> bool:
        """检查监听器是否已关闭"""
        return self._closed

    @property
    def addresses(self) -> List[tuple]:
        """获取监听地址列表"""
        # WebRTC 使用 ICE 候选作为地址
        # 这里返回一个占位符地址
        return [("webrtc", self._local_address)]

    async def handle_offer(self, peer_id: str, offer_sdp: str) -> str:
        """
        处理传入的 Offer

        Args:
            peer_id: 对端 ID
            offer_sdp: Offer SDP

        Returns:
            Answer SDP
        """
        if self._closed:
            raise ListenerError("监听器已关闭")

        # 创建连接
        conn = await self._transport._create_connection(is_initiator=False)

        # 设置远程描述
        from aiortc import RTCSessionDescription
        offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
        await conn.set_remote_description(offer)

        # 创建 Answer
        answer = await conn.create_answer()

        # 添加到待处理连接
        self._pending_connections[peer_id] = conn

        return answer.sdp

    async def finalize_connection(self, peer_id: str) -> WebRTCConnection:
        """
        完成连接建立

        Args:
            peer_id: 对端 ID

        Returns:
            建立的连接
        """
        conn = self._pending_connections.pop(peer_id, None)
        if not conn:
            raise ListenerError(f"未找到待处理的连接: {peer_id}")

        await self._accept_queue.put(conn)
        return conn


# ==================== WebRTC 传输 ====================

class WebRTCTransport(Transport):
    """
    WebRTC 传输

    实现 libp2p WebRTC 传输协议，支持与浏览器互操作。

    协议ID: /webrtc-direct
    """

    def __init__(
        self,
        stun_servers: Optional[List[str]] = None,
        ice_servers: Optional[List[ICEServer]] = None,
    ):
        """
        初始化 WebRTC 传输

        Args:
            stun_servers: STUN 服务器列表
            ice_servers: ICE 服务器列表（包括 TURN）
        """
        if not HAS_AIORTC:
            raise RuntimeError(
                "aiortc is required for WebRTC support. "
                "Install it with: pip install aiortc"
            )

        self._stun_servers = stun_servers or DEFAULT_STUN_SERVERS
        self._ice_servers = ice_servers or []

        # RTC 配置
        self._rtc_config = self._create_rtc_config()

        # 状态
        self._closed = False
        self._connections: List[WebRTCConnection] = []
        self._listeners: List[WebRTCListener] = []

        # 信令回调
        self._on_signaling_message: Optional[Callable[[SignalingMessage], Awaitable[None]]] = None

    @property
    def rtc_config(self) -> 'RTCConfiguration':
        """获取 RTC 配置"""
        return self._rtc_config

    def protocols(self) -> List[str]:
        """返回支持的协议列表"""
        return [PROTOCOL_ID]

    async def dial(self, addr: str) -> WebRTCConnection:
        """
        建立到指定地址的连接

        WebRTC 连接需要通过信令交换 SDP，
        这里创建连接并返回 Offer。

        Args:
            addr: 目标地址（信令通道标识符）

        Returns:
            WebRTC 连接
        """
        if self._closed:
            raise TransportError("传输已关闭")

        # 创建连接
        conn = await self._create_connection(is_initiator=True)

        # 创建 Offer
        offer = await conn.create_offer()

        # 发送信令消息
        await self._send_signaling_message(SignalingMessage(
            type=SignalingMessageType.OFFER,
            data={
                "sdp": offer.sdp,
                "address": addr,
            },
        ))

        return conn

    async def listen(self, addr: str) -> WebRTCListener:
        """
        在指定地址开始监听

        Args:
            addr: 监听地址（信令通道标识符）

        Returns:
            WebRTC 监听器
        """
        if self._closed:
            raise TransportError("传输已关闭")

        listener = WebRTCListener(
            transport=self,
            local_address=addr,
        )
        self._listeners.append(listener)

        logger.info(f"WebRTC 监听器已启动: {addr}")
        return listener

    async def close(self) -> None:
        """关闭传输层"""
        if self._closed:
            return

        self._closed = True

        # 关闭所有连接
        for conn in self._connections:
            try:
                await conn.close()
            except Exception:
                pass
        self._connections.clear()

        # 关闭所有监听器
        for listener in self._listeners:
            try:
                await listener.close()
            except Exception:
                pass
        self._listeners.clear()

        logger.info("WebRTC 传输已关闭")

    def set_signaling_callback(
        self,
        callback: Callable[[SignalingMessage], Awaitable[None]]
    ) -> None:
        """
        设置信令消息回调

        Args:
            callback: 信令消息处理回调
        """
        self._on_signaling_message = callback

    async def handle_signaling_message(self, message: SignalingMessage) -> None:
        """
        处理信令消息

        Args:
            message: 信令消息
        """
        if message.type == SignalingMessageType.OFFER:
            await self._handle_offer(message)
        elif message.type == SignalingMessageType.ANSWER:
            await self._handle_answer(message)
        elif message.type == SignalingMessageType.ICE_CANDIDATE:
            await self._handle_ice_candidate(message)
        else:
            logger.warning(f"未知的信令消息类型: {message.type}")

    def _create_rtc_config(self) -> 'RTCConfiguration':
        """创建 RTC 配置"""
        ice_servers = []

        # 添加 STUN 服务器
        for stun_url in self._stun_servers:
            ice_servers.append({"urls": [stun_url]})

        # 添加自定义 ICE 服务器
        for server in self._ice_servers:
            ice_servers.append({
                "urls": server.urls,
                "username": server.username,
                "credential": server.credential,
            })

        return RTCConfiguration(iceServers=ice_servers)

    async def _create_connection(self, is_initiator: bool) -> WebRTCConnection:
        """创建 WebRTC 连接"""
        # 创建 PeerConnection
        pc = RTCPeerConnection(configuration=self._rtc_config)

        # 创建 DataChannel（发起方）
        data_channel = None
        if is_initiator:
            data_channel = pc.createDataChannel(
                DEFAULT_DATA_CHANNEL_LABEL,
                ordered=True,
            )
            # 设置 DataChannel 回调
            # 注意：回调需要在连接对象中设置

        # 创建连接对象
        conn = WebRTCConnection(
            peer_connection=pc,
            data_channel=data_channel,
            is_initiator=is_initiator,
        )

        # 设置 DataChannel 回调（发起方）
        if data_channel:
            conn._setup_data_channel_callbacks(data_channel)

        self._connections.append(conn)
        return conn

    async def _send_signaling_message(self, message: SignalingMessage) -> None:
        """发送信令消息"""
        if self._on_signaling_message:
            await self._on_signaling_message(message)
        else:
            logger.warning("未设置信令回调，消息未发送")

    async def _handle_offer(self, message: SignalingMessage) -> None:
        """处理 Offer 消息"""
        offer_sdp = message.data.get("sdp")
        if not offer_sdp:
            logger.error("Offer 消息缺少 SDP")
            return

        # 创建 Answer
        from aiortc import RTCSessionDescription

        # 创建连接
        conn = await self._create_connection(is_initiator=False)

        # 设置远程描述
        offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
        await conn.set_remote_description(offer)

        # 创建 Answer
        answer = await conn.create_answer()

        # 发送 Answer
        await self._send_signaling_message(SignalingMessage(
            type=SignalingMessageType.ANSWER,
            data={
                "sdp": answer.sdp,
                "peer_id": message.peer_id,
            },
        ))

    async def _handle_answer(self, message: SignalingMessage) -> None:
        """处理 Answer 消息"""
        answer_sdp = message.data.get("sdp")
        if not answer_sdp:
            logger.error("Answer 消息缺少 SDP")
            return

        from aiortc import RTCSessionDescription
        answer = RTCSessionDescription(sdp=answer_sdp, type="answer")

        # 找到对应的连接并设置远程描述
        # 这里简化处理，实际应该根据 peer_id 匹配
        for conn in self._connections:
            if conn.is_initiator and not conn.get_remote_description():
                await conn.set_remote_description(answer)
                break

    async def _handle_ice_candidate(self, message: SignalingMessage) -> None:
        """处理 ICE 候选消息"""
        candidate = message.data.get("candidate")
        if not candidate:
            return

        # 添加 ICE 候选到对应连接
        # 这里简化处理，实际应该根据 peer_id 匹配
        for conn in self._connections:
            conn.add_ice_candidate(candidate)
            break
