"""
UDP 打孔器

实现 UDP 穿透的核心逻辑
"""
import asyncio
import logging
import socket
import time
from dataclasses import dataclass
from typing import Optional, List, Tuple

from ..types import NATInfo, ConnectionType, ISP
from ..config.isp_profiles import ISPProfile, get_isp_profile
from .port_predictor import PortPredictor

logger = logging.getLogger("p2p_engine.puncher")


@dataclass
class PunchResult:
    """打孔结果"""
    success: bool
    connection_type: ConnectionType = ConnectionType.FAILED
    local_addr: Tuple[str, int] = ("", 0)
    peer_addr: Tuple[str, int] = ("", 0)
    latency_ms: float = 0.0
    error: str = ""


class UDPPuncher:
    """UDP 打孔器"""
    
    def __init__(
        self,
        local_nat: NATInfo,
        peer_nat: NATInfo,
        local_isp: ISP,
        peer_isp: ISP,
    ):
        self.local_nat = local_nat
        self.peer_nat = peer_nat
        self.local_isp = local_isp
        self.peer_isp = peer_isp
        
        self._socket: Optional[socket.socket] = None
        self._local_port: int = 0
    
    async def punch(self) -> PunchResult:
        """
        执行打孔
        
        决策树：
        1. 双对称 NAT → 直接失败，走中继
        2. 单对称 NAT → 端口预测 + 多端口并行
        3. 非对称 NAT → 标准双向打孔
        """
        start_time = time.time()
        
        # 获取运营商配置
        local_profile = get_isp_profile(self.local_isp)
        
        # 决策：双对称 NAT
        if self.local_nat.is_symmetric() and self.peer_nat.is_symmetric():
            logger.info("双对称 NAT，无法直接穿透")
            return PunchResult(
                success=False,
                error="symmetric_symmetric",
            )
        
        # 创建 UDP socket
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            # 绑定本地端口
            self._socket.bind(("0.0.0.0", 0))
            self._local_port = self._socket.getsockname()[1]
            self._socket.setblocking(False)
            
            logger.info(f"开始打孔，本地端口: {self._local_port}")
            
            # 根据情况选择策略
            if self.local_nat.is_symmetric() or self.peer_nat.is_symmetric():
                result = await self._punch_symmetric(local_profile)
            else:
                result = await self._punch_standard(local_profile)
            
            if result.success:
                result.latency_ms = (time.time() - start_time) * 1000
            
            return result
            
        finally:
            if self._socket and not result.success:
                self._socket.close()
    
    async def _punch_standard(self, profile: ISPProfile) -> PunchResult:
        """
        标准双向打孔（非对称 NAT）
        
        双方同时向对方发送数据包
        """
        peer_addr = (self.peer_nat.public_ip, self.peer_nat.public_port)
        timeout = profile.punch_timeout_ms / 1000
        
        loop = asyncio.get_event_loop()
        
        try:
            # 发送打洞包
            punch_packet = b"PUNCH_HELLO"
            await loop.sock_sendto(self._socket, punch_packet, peer_addr)
            logger.debug(f"发送打洞包到 {peer_addr}")
            
            # 等待响应
            async def receive():
                while True:
                    data, addr = await loop.sock_recvfrom(self._socket, 1024)
                    if data.startswith(b"PUNCH"):
                        logger.debug(f"收到打洞响应: {addr}")
                        return addr
            
            addr = await asyncio.wait_for(receive(), timeout=timeout)
            
            return PunchResult(
                success=True,
                connection_type=ConnectionType.P2P_UDP,
                local_addr=("0.0.0.0", self._local_port),
                peer_addr=addr,
            )
            
        except asyncio.TimeoutError:
            logger.warning("打孔超时")
            return PunchResult(success=False, error="timeout")
        except Exception as e:
            logger.error(f"打孔失败: {e}")
            return PunchResult(success=False, error=str(e))
    
    async def _punch_symmetric(self, profile: ISPProfile) -> PunchResult:
        """
        对称 NAT 打孔（端口预测 + 多端口并行）
        """
        # 端口预测
        predictor = PortPredictor(
            base_port=self.peer_nat.public_port,
            strategy=profile.punch_port_strategy,
            predict_count=profile.punch_parallel_ports,
        )
        prediction = predictor.predict()
        
        logger.debug(f"端口预测: {prediction.ports[:4]}... (策略: {prediction.strategy})")
        
        # 并行向多个预测端口发送
        peer_ip = self.peer_nat.public_ip
        timeout = profile.punch_timeout_ms / 1000
        
        loop = asyncio.get_event_loop()
        
        try:
            # 并行发送到多个端口
            punch_packet = b"PUNCH_HELLO"
            tasks = []
            for port in prediction.ports:
                task = loop.sock_sendto(self._socket, punch_packet, (peer_ip, port))
                tasks.append(task)
            
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.debug(f"已向 {len(prediction.ports)} 个预测端口发送打洞包")
            
            # 等待响应
            async def receive():
                while True:
                    data, addr = await loop.sock_recvfrom(self._socket, 1024)
                    if data.startswith(b"PUNCH"):
                        return addr
            
            addr = await asyncio.wait_for(receive(), timeout=timeout)
            
            return PunchResult(
                success=True,
                connection_type=ConnectionType.P2P_UDP,
                local_addr=("0.0.0.0", self._local_port),
                peer_addr=addr,
            )
            
        except asyncio.TimeoutError:
            return PunchResult(success=False, error="timeout")
        except Exception as e:
            return PunchResult(success=False, error=str(e))
    
    def get_socket(self) -> Optional[socket.socket]:
        """获取连接成功的 socket"""
        return self._socket
    
    def close(self) -> None:
        """关闭 socket"""
        if self._socket:
            self._socket.close()
            self._socket = None
