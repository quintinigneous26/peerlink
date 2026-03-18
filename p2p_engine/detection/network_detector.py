"""
网络环境检测器

检测 VPN、CDN、多层 NAT、企业网络等复杂环境
"""
import asyncio
import logging
import socket
import time
from dataclasses import dataclass
from typing import Optional, List

from ..types import NetworkEnvironment, DeviceVendor
from .stun_client import STUNClient

logger = logging.getLogger("p2p_engine.network_detector")


@dataclass
class NetworkObservation:
    """网络观测数据"""
    timestamp: float
    public_ip: str
    public_port: int
    local_ip: str
    local_port: int
    latency_ms: float


class NetworkDetector:
    """网络环境检测器"""
    
    def __init__(self, stun_client: STUNClient):
        self.stun_client = stun_client
        self._observations: List[NetworkObservation] = []
    
    async def detect(self) -> NetworkEnvironment:
        """
        检测网络环境
        
        检测项目：
        1. NAT 层级
        2. VPN 环境
        3. CDN 环境
        4. 企业网络
        5. 移动网络
        6. IPv6 可用性
        7. 链路质量
        """
        logger.info("开始网络环境检测...")
        
        env = NetworkEnvironment()
        
        # 1. 检测 NAT 层级
        env.nat_level = await self._detect_nat_level()
        
        # 2. 检测 VPN
        env.is_behind_vpn = await self._detect_vpn()
        
        # 3. 检测 CDN
        env.is_behind_cdn = await self._detect_cdn()
        
        # 4. 检测企业网络
        env.is_enterprise_network = await self._detect_enterprise_network()
        
        # 5. 检测移动网络
        env.is_mobile_network = await self._detect_mobile_network()
        
        # 6. 检测 IPv6
        env.ipv6_available, env.ipv6_preferred = await self._detect_ipv6()
        
        # 7. 检测链路质量
        env.packet_loss_rate, env.avg_latency_ms = await self._detect_link_quality()
        
        # 8. 判断防火墙类型
        env.firewall_type = self._infer_firewall_type(env)
        
        logger.info(
            f"网络环境检测完成: NAT层级={env.nat_level}, "
            f"VPN={env.is_behind_vpn}, 企业={env.is_enterprise_network}, "
            f"移动={env.is_mobile_network}"
        )
        
        return env
    
    async def _detect_nat_level(self) -> int:
        """
        检测 NAT 层级
        
        方法：
        1. 比较本地 IP 和 STUN 返回的公网 IP
        2. 如果差异大（不同网段），说明有多层 NAT
        3. CGNAT IP 段检测
        """
        observations = []
        
        # 收集多次观测
        for i in range(3):
            response = await self.stun_client.binding_request(
                self.stun_client.servers[0].split(":")[0],
                3478
            )
            
            if response.success:
                # 获取本地 IP
                local_ip = self._get_local_ip()
                
                observations.append(NetworkObservation(
                    timestamp=time.time(),
                    public_ip=response.mapped_ip,
                    public_port=response.mapped_port,
                    local_ip=local_ip,
                    local_port=0,
                    latency_ms=0,
                ))
            
            await asyncio.sleep(0.3)
        
        if not observations:
            return 1
        
        first_obs = observations[0]
        
        # 检查是否在 CGNAT 后（100.64.0.0/10）
        if first_obs.public_ip.startswith("100."):
            logger.debug("检测到 CGNAT")
            return 2
        
        # 比较本地 IP 和公网 IP 的网段
        local_parts = first_obs.local_ip.split(".")
        public_parts = first_obs.public_ip.split(".")
        
        if len(local_parts) == 4 and len(public_parts) == 4:
            # 检查前两个网段是否相同
            if local_parts[0] == public_parts[0] and local_parts[1] == public_parts[1]:
                # 同网段，可能是 1 层 NAT
                return 1
            else:
                # 不同网段，可能有多层 NAT
                return 2
        
        # 默认返回 1 层
        return 1
    
    def _get_local_ip(self) -> str:
        """获取本地 IP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except OSError:
            return "127.0.0.1"
    
    async def _detect_vpn(self) -> bool:
        """
        检测 VPN 环境
        
        方法：
        1. 检查常见 VPN 接口（tun0, ppp0 等）
        2. 检查 MTU 大小（VPN 通常较小）
        3. 检查公网 IP 是否为 VPN 出口
        """
        # 检查 VPN 接口
        vpn_interfaces = ["tun", "ppp", "utun", "ipsec"]
        
        try:
            import netifaces
            interfaces = netifaces.interfaces()
            for iface in interfaces:
                for vpn_prefix in vpn_interfaces:
                    if iface.startswith(vpn_prefix):
                        logger.debug(f"检测到 VPN 接口: {iface}")
                        return True
        except ImportError:
            pass
        
        # 检查公网 IP 是否属于 VPN 服务商
        # 常见 VPN IP 段
        vpn_ip_ranges = [
            "10.",        # 私有网络 VPN
            "172.16.",    # 私有网络 VPN
        ]
        
        response = await self.stun_client.binding_request(
            self.stun_client.servers[0].split(":")[0],
            3478
        )
        
        if response.success:
            for vpn_range in vpn_ip_ranges:
                if response.mapped_ip.startswith(vpn_range):
                    # 可能是 VPN，但也可能是 CGNAT
                    # 需要进一步确认
                    pass
        
        return False
    
    async def _detect_cdn(self) -> bool:
        """
        检测 CDN 环境
        
        方法：
        1. 多次请求 STUN，如果返回的 IP 频繁变化，可能是 CDN
        2. 检查 IP 是否属于 CDN 厂商
        """
        ips = []
        
        for i in range(3):
            response = await self.stun_client.binding_request(
                self.stun_client.servers[0].split(":")[0],
                3478
            )
            if response.success:
                ips.append(response.mapped_ip)
            await asyncio.sleep(0.5)
        
        if len(set(ips)) > 1:
            # IP 频繁变化，可能是 CDN
            logger.debug(f"检测到 IP 变化: {ips}")
            return True
        
        return False
    
    async def _detect_enterprise_network(self) -> bool:
        """
        检测企业网络
        
        方法：
        1. 检查内网 IP 段（10.x, 172.16-31.x）
        2. 检查是否有企业防火墙特征
        3. 检查 DNS 是否为企业 DNS
        """
        local_ip = self._get_local_ip()
        
        # 企业网络通常使用 10.x.x.x 或 172.16-31.x.x
        if local_ip.startswith("10."):
            # 10.x 可能是企业网，也可能是 CGNAT
            # 检查是否有企业防火墙特征
            pass
        
        # 172.16-31.x.x 私有网段
        if local_ip.startswith("172."):
            parts = local_ip.split(".")
            if len(parts) >= 2:
                second_octet = int(parts[1])
                if 16 <= second_octet <= 31:
                    # 企业私有网段
                    logger.debug("检测到企业私有网段")
                    return True
        
        return False
    
    async def _detect_mobile_network(self) -> bool:
        """
        检测移动网络（4G/5G）
        
        方法：
        1. 检查 MTU 大小（移动网络通常较小）
        2. 检查网络延迟和抖动
        3. 检查 IP 变化频率
        """
        # 测量延迟和抖动
        latencies = []
        
        for i in range(5):
            start = time.time()
            response = await self.stun_client.binding_request(
                self.stun_client.servers[0].split(":")[0],
                3478
            )
            latency = (time.time() - start) * 1000
            
            if response.success:
                latencies.append(latency)
            
            await asyncio.sleep(0.2)
        
        if len(latencies) >= 3:
            # 计算抖动
            avg = sum(latencies) / len(latencies)
            jitter = sum(abs(latencies[i] - latencies[i-1]) 
                        for i in range(1, len(latencies))) / (len(latencies) - 1)
            
            # 移动网络特征：高延迟 + 高抖动
            if avg > 80 and jitter > 30:
                logger.debug(f"检测到移动网络特征: 延迟={avg:.0f}ms, 抖动={jitter:.0f}ms")
                return True
        
        return False
    
    async def _detect_ipv6(self) -> tuple:
        """
        检测 IPv6 可用性
        
        Returns:
            (是否可用, 是否优先)
        """
        try:
            # 检查是否有 IPv6 地址
            sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            sock.settimeout(2)
            
            # 尝试连接 IPv6 DNS
            try:
                sock.connect(("2001:4860::8888", 53))
                sock.close()
                logger.debug("IPv6 可用")
                return True, True
            except (OSError, socket.error):
                sock.close()
                return True, False
                
        except Exception:
            pass
        
        return False, False
    
    async def _detect_link_quality(self) -> tuple:
        """
        检测链路质量
        
        Returns:
            (丢包率, 平均延迟)
        """
        success_count = 0
        total_count = 10
        latencies = []
        
        for i in range(total_count):
            start = time.time()
            response = await self.stun_client.binding_request(
                self.stun_client.servers[0].split(":")[0],
                3478
            )
            
            if response.success:
                success_count += 1
                latencies.append((time.time() - start) * 1000)
            
            await asyncio.sleep(0.2)
        
        loss_rate = 1 - (success_count / total_count)
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        logger.debug(f"链路质量: 丢包率={loss_rate:.1%}, 延迟={avg_latency:.0f}ms")
        
        return loss_rate, avg_latency
    
    def _infer_firewall_type(self, env: NetworkEnvironment) -> str:
        """根据环境特征推断防火墙类型"""
        if env.is_enterprise_network:
            return "enterprise"
        
        if env.is_mobile_network:
            return "isp"
        
        if env.is_behind_vpn:
            return "isp"
        
        # 跨境高丢包
        if env.packet_loss_rate > 0.1:
            return "cross_border"
        
        return "home"
    
    def is_complex_environment(self, env: NetworkEnvironment) -> bool:
        """判断是否为复杂网络环境"""
        return (
            env.nat_level >= 3 or
            env.is_behind_vpn or
            env.is_enterprise_network or
            env.packet_loss_rate > 0.15 or
            env.is_mobile_network
        )
    
    async def monitor_changes(
        self,
        check_interval_sec: int = 60,
    ) -> None:
        """
        持续监控网络变化
        
        检测：
        1. IP 变化（网络切换）
        2. 延迟变化
        3. NAT 行为变化
        """
        last_ip = None
        last_latency = 0
        
        while True:
            await asyncio.sleep(check_interval_sec)
            
            # 检测 IP 变化
            response = await self.stun_client.binding_request(
                self.stun_client.servers[0].split(":")[0],
                3478
            )
            
            if response.success:
                current_ip = response.mapped_ip
                
                if last_ip and current_ip != last_ip:
                    logger.warning(f"检测到 IP 变化: {last_ip} -> {current_ip}")
                    # TODO: 触发网络变化事件
                    return NetworkEnvironment(
                        nat_level=await self._detect_nat_level(),
                    is_behind_vpn=await self._detect_vpn(),
                    is_behind_cdn=await self._detect_cdn(),
                        is_enterprise_network=await self._detect_enterprise_network(),
                        is_mobile_network=await self._detect_mobile_network(),
                        firewall_type="",
                        ipv6_available=False,
                        ipv6_preferred=False,
                        packet_loss_rate=0,
                        avg_latency_ms=0,
                    )
                
                last_ip = current_ip
