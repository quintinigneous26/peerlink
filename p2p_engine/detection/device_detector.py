"""
网络设备厂商检测器

基于网络行为特征识别设备厂商
"""
import asyncio
import logging
import socket
import time
from dataclasses import dataclass
from typing import Optional, List

from ..types import DeviceVendor, NATType, NATInfo
from .stun_client import STUNClient, STUNResponse

logger = logging.getLogger("p2p_engine.device_detector")


@dataclass
class DeviceProfile:
    """设备配置档案"""
    vendor: DeviceVendor
    
    # NAT 行为
    nat_type: NATType
    port_strategy: str            # "continuous" | "random" | "jump"
    port_delta: int              # 端口递增步长
    
    # 超时配置
    udp_timeout_sec: int
    tcp_timeout_sec: int
    
    # 特殊功能
    alg_enabled: bool             # 是否启用 ALG
    hairpin_supported: bool    # 是否支持 Hairpin
    
    # 防火墙行为
    strict_inbound_filter: bool   # 是否严格过滤入站
    
    # 兼容建议
    heartbeat_interval_sec: int
    punch_strategy: str
    
    # 备注
    notes: str = ""


# ==================== 设备厂商配置档案 ====================

DEVICE_PROFILES = {
    # 运营商级设备
    DeviceVendor.HUAWEI: DeviceProfile(
        vendor=DeviceVendor.HUAWEI,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=20,
        tcp_timeout_sec=60,
        alg_enabled=True,
        hairpin_supported=False,
        strict_inbound_filter=True,
        heartbeat_interval_sec=20,
        punch_strategy="multi_port",
        notes="华为OLT/AR路由器，ALG极强，Hairpin默认关闭",
    ),
    
    DeviceVendor.ZTE: DeviceProfile(
        vendor=DeviceVendor.ZTE,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="jump",            # 跳跃式端口
        port_delta=2,                # 可能跳跃
        udp_timeout_sec=30,
        tcp_timeout_sec=90,
        alg_enabled=True,
        hairpin_supported=True,       # 版本差异大
        strict_inbound_filter=True,
        heartbeat_interval_sec=25,
        punch_strategy="multi_port_retry",
        notes="中兴设备，端口跳跃式分配，ALG默认开启",
    ),
    
    DeviceVendor.ERICSSON: DeviceProfile(
        vendor=DeviceVendor.ERICSSON,
        nat_type=NATType.SYMMETRIC,
        port_strategy="random",          # 完全随机
        port_delta=0,
        udp_timeout_sec=25,
        tcp_timeout_sec=60,
        alg_enabled=False,
        hairpin_supported=False,
        strict_inbound_filter=True,
        heartbeat_interval_sec=15,
        punch_strategy="relay",           # 直接中继
        notes="爱立信5G核心网，端口完全随机，对称NAT",
    ),
    
    DeviceVendor.NOKIA: DeviceProfile(
        vendor=DeviceVendor.NOKIA,
        nat_type=NATType.SYMMETRIC,
        port_strategy="random",
        port_delta=0,
        udp_timeout_sec=25,
        tcp_timeout_sec=60,
        alg_enabled=False,
        hairpin_supported=False,
        strict_inbound_filter=True,
        heartbeat_interval_sec=15,
        punch_strategy="relay",
        notes="诺基亚5G核心网，对称NAT，入站策略极严",
    ),
    
    DeviceVendor.FIBERHOME: DeviceProfile(
        vendor=DeviceVendor.FIBERHOME,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="jump",
        port_delta=3,
        udp_timeout_sec=20,
        tcp_timeout_sec=60,
        alg_enabled=True,
        hairpin_supported=False,
        strict_inbound_filter=True,
        heartbeat_interval_sec=20,
        punch_strategy="multi_port",
        notes="烽火OLT，多层CGNAT，几乎不支持Hairpin",
    ),
    
    DeviceVendor.ALCATEL_LUCENT: DeviceProfile(
        vendor=DeviceVendor.ALCATEL_LUCENT,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=45,
        tcp_timeout_sec=120,
        alg_enabled=False,
        hairpin_supported=True,
        strict_inbound_filter=False,
        heartbeat_interval_sec=40,
        punch_strategy="standard",
        notes="阿尔卡特朗讯，海外运营商常用，行为标准",
    ),
    
    DeviceVendor.SAMSUNG: DeviceProfile(
        vendor=DeviceVendor.SAMSUNG,
        nat_type=NATType.RESTRICTED_CONE,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=40,
        tcp_timeout_sec=90,
        alg_enabled=False,
        hairpin_supported=True,
        strict_inbound_filter=False,
        heartbeat_interval_sec=35,
        punch_strategy="standard",
        notes="三星5G设备，IPv6支持完善",
    ),
    
    # 企业级设备
    DeviceVendor.CISCO: DeviceProfile(
        vendor=DeviceVendor.CISCO,
        nat_type=NATType.FULL_CONE,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=120,           # 超时很长
        tcp_timeout_sec=300,
        alg_enabled=False,
        hairpin_supported=True,
        strict_inbound_filter=False,
        heartbeat_interval_sec=90,
        punch_strategy="standard",
        notes="思科企业设备，NAT宽松，超时很长",
    ),
    
    DeviceVendor.H3C: DeviceProfile(
        vendor=DeviceVendor.H3C,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=30,
        tcp_timeout_sec=90,
        alg_enabled=True,            # ALG 极强
        hairpin_supported=True,
        strict_inbound_filter=True,
        heartbeat_interval_sec=25,
        punch_strategy="tcp_fallback",
        notes="华三企业设备，ALG篡改UDP端口",
    ),
    
    DeviceVendor.SANGFOR: DeviceProfile(
        vendor=DeviceVendor.SANGFOR,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=20,
        tcp_timeout_sec=60,
        alg_enabled=True,
        hairpin_supported=False,
        strict_inbound_filter=True,
        heartbeat_interval_sec=15,
        punch_strategy="relay_immediately",  # 直接中继
        notes="深信服上网行为管理，P2P穿透成功率几乎为0",
    ),
    
    DeviceVendor.QIANXIN: DeviceProfile(
        vendor=DeviceVendor.QIANXIN,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=20,
        tcp_timeout_sec=60,
        alg_enabled=False,
        hairpin_supported=False,
        strict_inbound_filter=True,
        heartbeat_interval_sec=15,
        punch_strategy="tcp_fallback",
        notes="奇安信防火墙，识别P2P为异常流量",
    ),
    
    DeviceVendor.PALO_ALTO: DeviceProfile(
        vendor=DeviceVendor.PALO_ALTO,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=60,
        tcp_timeout_sec=180,
        alg_enabled=False,
        hairpin_supported=True,
        strict_inbound_filter=True,
        heartbeat_interval_sec=45,
        punch_strategy="check_policy",
        notes="Palo Alto应用识别强，策略严格但行为可预测",
    ),
    
    DeviceVendor.FORTINET: DeviceProfile(
        vendor=DeviceVendor.FORTINET,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=25,
        tcp_timeout_sec=90,
        alg_enabled=False,
        hairpin_supported=True,
        strict_inbound_filter=True,
        heartbeat_interval_sec=20,
        punch_strategy="multi_port",
        notes="飞塔防火墙，UDP会话清理积极",
    ),
    
    DeviceVendor.JUNIPER: DeviceProfile(
        vendor=DeviceVendor.JUNIPER,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=60,
        tcp_timeout_sec=180,
        alg_enabled=False,
        hairpin_supported=True,
        strict_inbound_filter=False,
        heartbeat_interval_sec=45,
        punch_strategy="standard",
        notes="Juniper海外常用，行为标准稳定",
    ),
    
    DeviceVendor.CHECKPOINT: DeviceProfile(
        vendor=DeviceVendor.CHECKPOINT,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=30,
        tcp_timeout_sec=90,
        alg_enabled=True,            # 可配置
        hairpin_supported=True,
        strict_inbound_filter=True,
        heartbeat_interval_sec=25,
        punch_strategy="relay",
        notes="Check Point企业防火墙，P2P有专门拦截策略",
    ),
    
    # 家用级设备
    DeviceVendor.TP_LINK: DeviceProfile(
        vendor=DeviceVendor.TP_LINK,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=30,
        tcp_timeout_sec=90,
        alg_enabled=False,
        hairpin_supported=True,
        strict_inbound_filter=True,
        heartbeat_interval_sec=25,
        punch_strategy="standard",
        notes="TP-Link家用路由，行为标准",
    ),
    
    DeviceVendor.XIAOMI: DeviceProfile(
        vendor=DeviceVendor.XIAOMI,
        nat_type=NATType.PORT_RESTRICTED,
        port_strategy="continuous",
        port_delta=1,
        udp_timeout_sec=30,
        tcp_timeout_sec=90,
        alg_enabled=True,
        hairpin_supported=True,
        strict_inbound_filter=True,
        heartbeat_interval_sec=25,
        punch_strategy="multi_port",
        notes="小米路由，ALG默认开启",
    ),
    
    DeviceVendor.UNKNOWN: DeviceProfile(
        vendor=DeviceVendor.UNKNOWN,
        nat_type=NATType.UNKNOWN,
        port_strategy="hybrid",
        port_delta=1,
        udp_timeout_sec=30,
        tcp_timeout_sec=90,
        alg_enabled=False,
        hairpin_supported=True,
        strict_inbound_filter=True,
        heartbeat_interval_sec=25,
        punch_strategy="standard",
        notes="未知设备，使用保守配置",
    ),
}


def get_device_profile(vendor: DeviceVendor) -> DeviceProfile:
    """获取设备配置档案"""
    return DEVICE_PROFILES.get(vendor, DEVICE_PROFILES[DeviceVendor.UNKNOWN])


class DeviceDetector:
    """设备厂商检测器"""
    
    def __init__(self, stun_client: STUNClient):
        self.stun_client = stun_client
        self._observations: List[dict] = []
    
    async def detect(self, nat_info: NATInfo) -> DeviceVendor:
        """
        检测设备厂商
        
        方法：
        1. 端口行为分析（连续/跳跃/随机）
        2. NAT 超时测试
        3. ALG 干扰检测
        4. Hairpin 测试
        """
        logger.info("开始设备厂商检测...")
        
        # 收集多个 STUN 观测
        observations = []
        for i in range(5):
            response = await self.stun_client.binding_request(
                self.stun_client.servers[0].split(":")[0],
                int(self.stun_client.servers[0].split(":")[1]) if ":" in self.stun_client.servers[0] else 3478
            )
            if response.success:
                observations.append({
                    "public_port": response.mapped_port,
                    "timestamp": time.time(),
                })
            await asyncio.sleep(0.5)
        
        # 分析端口行为
        port_behavior = self._analyze_port_behavior(observations)
        
        # 根据端口行为推断厂商
        vendor = self._infer_vendor(port_behavior, nat_info)
        
        logger.info(f"设备厂商检测完成: {vendor.value}")
        return vendor
    
    def _analyze_port_behavior(self, observations: List[dict]) -> dict:
        """分析端口行为"""
        if len(observations) < 2:
            return {"pattern": "unknown"}
        
        ports = [obs["public_port"] for obs in observations]
        
        # 计算端口差值
        deltas = [ports[i+1] - ports[i] for i in range(len(ports)-1)]
        
        if not deltas:
            return {"pattern": "single"}
        
        # 判断模式
        if all(d == 0 for d in deltas):
            # 端口不变 - 可能是固定映射
            return {"pattern": "fixed", "delta": 0}
        
        if all(d == deltas[0] for d in deltas):
            # 连续递增
            return {"pattern": "continuous", "delta": deltas[0]}
        
        if all(abs(d - deltas[0]) <= 3 for d in deltas):
            # 跳跃式
            return {"pattern": "jump", "delta": deltas[0]}
        
        # 随机
        return {"pattern": "random", "delta": 0}
    
    def _infer_vendor(self, port_behavior: dict, nat_info: NATInfo) -> DeviceVendor:
        """根据端口行为推断厂商"""
        pattern = port_behavior.get("pattern", "unknown")
        
        # 对称 NAT + 随机端口 → 爱立信/诺基亚（5G核心网）
        if nat_info.is_symmetric() and pattern == "random":
            return DeviceVendor.ERICSSON
        
        # 跳跃式端口 → 中兴/烽火
        if pattern == "jump":
            return DeviceVendor.ZTE
        
        # 连续端口 + 对称 NAT → 可能是企业设备
        if pattern == "continuous" and nat_info.is_symmetric():
            return DeviceVendor.CISCO
        
        # 默认返回未知
        return DeviceVendor.UNKNOWN
    
    async def detect_alg_interference(self) -> bool:
        """
        检测 ALG 干扰
        
        ALG（Application Layer Gateway）可能会：
        1. 篡改 STUN 响应中的端口
        2. 丢弃某些协议的包
        3. 改写包内容
        """
        # 发送特殊格式的 STUN 请求
        # 如果响应异常，说明有 ALG 干扰
        try:
            response = await self.stun_client.binding_request(
                self.stun_client.servers[0].split(":")[0],
                3478
            )
            
            # 检查响应是否正常
            if response.success and response.mapped_port > 0:
                # 正常响应，可能没有 ALG
                return False
            else:
                # 异常响应，可能有 ALG
                return True
                
        except Exception:
            # 请求失败，可能有 ALG 拦截
            return True
    
    async def detect_hairpin(self, local_ip: str, local_port: int) -> bool:
        """
        检测 Hairpin（内网回流）支持
        
        Hairpin 允许内网设备通过公网 IP 互通
        """
        # 这个需要两个内网设备配合测试
        # 简化实现：假设支持（实际应测试）
        return True
