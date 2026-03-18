"""
NAT 类型探测器

基于 RFC 3489 实现
"""
import asyncio
import logging
import socket
from typing import List

from ..types import NATType, NATInfo
from .stun_client import STUNClient, STUNResponse

logger = logging.getLogger("p2p_engine.nat_detector")


class NATDetector:
    """NAT 类型探测器"""
    
    def __init__(self, stun_client: STUNClient):
        self.stun_client = stun_client
    
    async def detect(self) -> NATInfo:
        """
        检测 NAT 类型
        
        检测流程（RFC 3489 简化版）：
        1. 向 Server A 发送请求 → 获取映射地址 M1
        2. 向 Server B 发送请求 → 获取映射地址 M2
        3. 比较 M1 和 M2：
           - 相同 → 非对称 NAT
           - 不同 → 对称 NAT
        """
        logger.info("开始 NAT 类型检测...")
        
        servers = self.stun_client.servers
        if len(servers) < 1:
            logger.error("没有可用的 STUN 服务器")
            return NATInfo(type=NATType.UNKNOWN)
        
        # Test 1: 基础连接测试
        server_a = servers[0].split(":")
        host_a = server_a[0]
        port_a = int(server_a[1]) if len(server_a) > 1 else 3478
        
        response1 = await self.stun_client.binding_request(host_a, port_a)
        
        if not response1.success:
            logger.error(f"STUN Test 1 失败: {response1.error}")
            return NATInfo(type=NATType.UNKNOWN)
        
        logger.debug(f"Test 1: {response1.mapped_ip}:{response1.mapped_port}")
        
        # 获取本地地址
        local_ip, local_port = self._get_local_address()
        
        # 检测 NAT 类型
        if self._is_public_ip(response1.mapped_ip):
            # 公网 IP，可能是 Full Cone
            nat_type = NATType.FULL_CONE
        else:
            nat_type = await self._detect_nat_type(response1, servers)
        
        # 构建 NAT 信息
        nat_info = NATInfo(
            type=nat_type,
            public_ip=response1.mapped_ip,
            public_port=response1.mapped_port,
            local_ip=local_ip,
            local_port=local_port,
        )
        
        # 检测 CGNAT
        nat_info.is_cgnat = self._detect_cgnat(response1)
        
        logger.info(f"NAT 检测完成: {nat_info.type.value}, CGNAT: {nat_info.is_cgnat}")
        
        return nat_info
    
    async def _detect_nat_type(
        self,
        first_response: STUNResponse,
        servers: List[str],
    ) -> NATType:
        """检测 NAT 类型"""
        if len(servers) < 2:
            return NATType.PORT_RESTRICTED
        
        # 向第二个服务器发送请求
        server_b = servers[1].split(":")
        host_b = server_b[0]
        port_b = int(server_b[1]) if len(server_b) > 1 else 3478
        
        response2 = await self.stun_client.binding_request(host_b, port_b)
        
        if not response2.success:
            return NATType.UNKNOWN
        
        # 比较映射地址
        addr1 = (first_response.mapped_ip, first_response.mapped_port)
        addr2 = (response2.mapped_ip, response2.mapped_port)
        
        if addr1 != addr2:
            # 映射地址不同 → 对称 NAT
            return NATType.SYMMETRIC
        
        # 映射地址相同 → 端口限制锥（最常见）
        return NATType.PORT_RESTRICTED
    
    def _get_local_address(self) -> tuple:
        """获取本地地址"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()
        finally:
            sock.close()
    
    def _is_public_ip(self, ip: str) -> bool:
        """检查是否为公网 IP"""
        private_prefixes = ["10.", "172.16.", "172.17.", "172.18.", "172.19.",
                          "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                          "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
                          "172.30.", "172.31.", "192.168.", "127.", "169.254."]
        for prefix in private_prefixes:
            if ip.startswith(prefix):
                return False
        return True
    
    def _detect_cgnat(self, response: STUNResponse) -> bool:
        """检测 CGNAT"""
        # CGNAT 使用 100.64.0.0/10
        if response.mapped_ip.startswith("100."):
            return True
        return False
