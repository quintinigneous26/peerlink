"""
运营商配置档案

涵盖全球主流运营商的差异化参数
"""
from dataclasses import dataclass
from typing import Dict

from ..types import ISP, Region, NATType


@dataclass
class ISPProfile:
    """运营商配置档案"""
    isp: ISP
    region: Region
    name: str
    
    # NAT 特征
    symmetric_ratio: float              # 对称 NAT 占比 (0.0-1.0)
    cgnat_levels: int                   # CGNAT 层级 (0-3)
    
    # 打孔参数
    punch_timeout_ms: int               # 打孔超时
    punch_parallel_ports: int           # 并行端口数
    punch_port_strategy: str            # 端口策略
    
    # 心跳参数
    heartbeat_min_ms: int
    heartbeat_max_ms: int
    heartbeat_initial_ms: int
    
    # UDP 限流
    udp_rate_limit_mbps: int            # 0=不限
    prefer_tcp: bool
    
    # 穿透成功率预期
    punch_success_rate: float
    
    # 备注
    notes: str = ""


# ==================== 全球运营商配置 ====================

ISP_PROFILES: Dict[ISP, ISPProfile] = {
    # ==================== 中国大陆 ====================
    ISP.CHINA_TELECOM: ISPProfile(
        isp=ISP.CHINA_TELECOM,
        region=Region.MAINLAND,
        name="中国电信",
        symmetric_ratio=0.1,
        cgnat_levels=1,
        punch_timeout_ms=5000,
        punch_parallel_ports=4,
        punch_port_strategy="sequential",
        heartbeat_min_ms=20000,
        heartbeat_max_ms=40000,
        heartbeat_initial_ms=30000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.80,
        notes="CGNAT较少，公网IP申请容易，穿透成功率最高",
    ),
    
    ISP.CHINA_MOBILE: ISPProfile(
        isp=ISP.CHINA_MOBILE,
        region=Region.MAINLAND,
        name="中国移动",
        symmetric_ratio=0.7,
        cgnat_levels=3,
        punch_timeout_ms=3000,
        punch_parallel_ports=8,
        punch_port_strategy="hybrid",
        heartbeat_min_ms=15000,
        heartbeat_max_ms=25000,
        heartbeat_initial_ms=20000,
        udp_rate_limit_mbps=10,
        prefer_tcp=True,
        punch_success_rate=0.40,
        notes="大量对称NAT+多层CGNAT，UDP限流严格，必须依赖中继",
    ),
    
    ISP.CHINA_UNICOM: ISPProfile(
        isp=ISP.CHINA_UNICOM,
        region=Region.MAINLAND,
        name="中国联通",
        symmetric_ratio=0.2,
        cgnat_levels=2,
        punch_timeout_ms=5000,
        punch_parallel_ports=4,
        punch_port_strategy="sequential",
        heartbeat_min_ms=20000,
        heartbeat_max_ms=35000,
        heartbeat_initial_ms=25000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.70,
        notes="CGNAT中等，网络较干净，中等偏上",
    ),
    
    ISP.CHINA_RAILCOM: ISPProfile(
        isp=ISP.CHINA_RAILCOM,
        region=Region.MAINLAND,
        name="中国铁通",
        symmetric_ratio=0.6,
        cgnat_levels=3,
        punch_timeout_ms=3000,
        punch_parallel_ports=8,
        punch_port_strategy="hybrid",
        heartbeat_min_ms=15000,
        heartbeat_max_ms=25000,
        heartbeat_initial_ms=20000,
        udp_rate_limit_mbps=10,
        prefer_tcp=True,
        punch_success_rate=0.45,
        notes="归属移动骨干，策略同移动，优先走中继",
    ),
    
    # ==================== 香港地区 ====================
    ISP.HKBN: ISPProfile(
        isp=ISP.HKBN,
        region=Region.HONGKONG,
        name="香港宽带",
        symmetric_ratio=0.1,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.90,
        notes="公网IP充足，CGNAT少，UDP限制宽松",
    ),
    
    ISP.CMHK: ISPProfile(
        isp=ISP.CMHK,
        region=Region.HONGKONG,
        name="中国移动香港",
        symmetric_ratio=0.15,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.88,
        notes="香港移动，策略比大陆移动宽松",
    ),
    
    ISP.THREE_HK: ISPProfile(
        isp=ISP.THREE_HK,
        region=Region.HONGKONG,
        name="3香港",
        symmetric_ratio=0.1,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.90,
        notes="公网IP充足",
    ),
    
    ISP.SMARTONE: ISPProfile(
        isp=ISP.SMARTONE,
        region=Region.HONGKONG,
        name="数码通",
        symmetric_ratio=0.1,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.90,
        notes="网络质量好",
    ),
    
    # ==================== 新加坡 ====================
    ISP.SINGTEL: ISPProfile(
        isp=ISP.SINGTEL,
        region=Region.SINGAPORE,
        name="Singtel",
        symmetric_ratio=0.05,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.95,
        notes="网络质量高、丢包低、UDP几乎不限速",
    ),
    
    ISP.STARHUB: ISPProfile(
        isp=ISP.STARHUB,
        region=Region.SINGAPORE,
        name="StarHub",
        symmetric_ratio=0.05,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.95,
        notes="网络质量优秀",
    ),
    
    ISP.M1: ISPProfile(
        isp=ISP.M1,
        region=Region.SINGAPORE,
        name="M1",
        symmetric_ratio=0.05,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.95,
        notes="网络质量优秀",
    ),
    
    # ==================== 美国运营商 ====================
    ISP.ATT: ISPProfile(
        isp=ISP.ATT,
        region=Region.OVERSEAS,
        name="AT&T",
        symmetric_ratio=0.1,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="random",  # 美国运营商随机端口
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.80,
        notes="公网IP充足，UDP限制宽松，支持IPv6优先",
    ),
    
    ISP.VERIZON: ISPProfile(
        isp=ISP.VERIZON,
        region=Region.OVERSEAS,
        name="Verizon",
        symmetric_ratio=0.1,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="random",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.80,
        notes="5G场景少量对称NAT，IPv6支持完善",
    ),
    
    ISP.TMOBILE: ISPProfile(
        isp=ISP.TMOBILE,
        region=Region.OVERSEAS,
        name="T-Mobile",
        symmetric_ratio=0.15,
        cgnat_levels=1,
        punch_timeout_ms=8000,
        punch_parallel_ports=3,
        punch_port_strategy="random",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.75,
        notes="5G网络NAT策略略严格，IPv6优先",
    ),
    
    ISP.COMCAST: ISPProfile(
        isp=ISP.COMCAST,
        region=Region.OVERSEAS,
        name="Comcast",
        symmetric_ratio=0.08,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="random",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.85,
        notes="美国最大有线ISP，网络稳定",
    ),
    
    # ==================== 欧洲运营商 ====================
    ISP.VODAFONE: ISPProfile(
        isp=ISP.VODAFONE,
        region=Region.OVERSEAS,
        name="Vodafone",
        symmetric_ratio=0.1,
        cgnat_levels=2,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=40000,
        heartbeat_max_ms=70000,
        heartbeat_initial_ms=50000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.75,
        notes="UDP超时较长(40-60s)，CGNAT在人口密集区部署",
    ),
    
    ISP.ORANGE: ISPProfile(
        isp=ISP.ORANGE,
        region=Region.OVERSEAS,
        name="Orange",
        symmetric_ratio=0.12,
        cgnat_levels=2,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=40000,
        heartbeat_max_ms=70000,
        heartbeat_initial_ms=50000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.72,
        notes="部分地区IPv6强制部署，特定端口UDP有限制",
    ),
    
    ISP.DEUTSCHE_TELEKOM: ISPProfile(
        isp=ISP.DEUTSCHE_TELEKOM,
        region=Region.OVERSEAS,
        name="Deutsche Telekom",
        symmetric_ratio=0.08,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=40000,
        heartbeat_max_ms=70000,
        heartbeat_initial_ms=50000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.82,
        notes="德国最大运营商，网络质量高",
    ),
    
    ISP.BT: ISPProfile(
        isp=ISP.BT,
        region=Region.OVERSEAS,
        name="BT",
        symmetric_ratio=0.1,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=35000,
        heartbeat_max_ms=65000,
        heartbeat_initial_ms=50000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.78,
        notes="英国最大运营商，IPv6部署率高",
    ),
    
    # ==================== 东南亚运营商 ====================
    ISP.AIS: ISPProfile(
        isp=ISP.AIS,
        region=Region.OVERSEAS,
        name="AIS (泰国)",
        symmetric_ratio=0.15,
        cgnat_levels=2,
        punch_timeout_ms=8000,
        punch_parallel_ports=3,
        punch_port_strategy="hybrid",
        heartbeat_min_ms=25000,
        heartbeat_max_ms=45000,
        heartbeat_initial_ms=35000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.65,
        notes="UDP限流较宽松，跨境链路不稳定",
    ),
    
    ISP.TRUEMOVE: ISPProfile(
        isp=ISP.TRUEMOVE,
        region=Region.OVERSEAS,
        name="True Move (泰国)",
        symmetric_ratio=0.18,
        cgnat_levels=2,
        punch_timeout_ms=8000,
        punch_parallel_ports=3,
        punch_port_strategy="hybrid",
        heartbeat_min_ms=25000,
        heartbeat_max_ms=45000,
        heartbeat_initial_ms=35000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.60,
        notes="网络丢包率中等(5-15%)，跨境链路不稳定",
    ),
    
    ISP.MAXIS: ISPProfile(
        isp=ISP.MAXIS,
        region=Region.OVERSEAS,
        name="Maxis (马来西亚)",
        symmetric_ratio=0.12,
        cgnat_levels=2,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=50000,
        heartbeat_initial_ms=40000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.70,
        notes="支持IPv6混合部署",
    ),
    
    ISP.DIGI: ISPProfile(
        isp=ISP.DIGI,
        region=Region.OVERSEAS,
        name="Digi (马来西亚)",
        symmetric_ratio=0.1,
        cgnat_levels=2,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=50000,
        heartbeat_initial_ms=40000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.72,
        notes="CGNAT占比中等",
    ),
    
    # ==================== 日韩运营商 ====================
    ISP.NTT: ISPProfile(
        isp=ISP.NTT,
        region=Region.OVERSEAS,
        name="NTT (日本)",
        symmetric_ratio=0.08,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.85,
        notes="网络质量极高，IPv6部署完善",
    ),
    
    ISP.KDDI: ISPProfile(
        isp=ISP.KDDI,
        region=Region.OVERSEAS,
        name="KDDI (日本)",
        symmetric_ratio=0.1,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.82,
        notes="网络稳定",
    ),
    
    ISP.SK_TELECOM: ISPProfile(
        isp=ISP.SK_TELECOM,
        region=Region.OVERSEAS,
        name="SK Telecom (韩国)",
        symmetric_ratio=0.1,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.85,
        notes="5G网络全球领先，穿透表现优秀",
    ),
    
    ISP.KT: ISPProfile(
        isp=ISP.KT,
        region=Region.OVERSEAS,
        name="KT (韩国)",
        symmetric_ratio=0.1,
        cgnat_levels=1,
        punch_timeout_ms=10000,
        punch_parallel_ports=2,
        punch_port_strategy="sequential",
        heartbeat_min_ms=30000,
        heartbeat_max_ms=60000,
        heartbeat_initial_ms=45000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.83,
        notes="网络质量高",
    ),
    
    # ==================== 未知运营商 ====================
    ISP.UNKNOWN: ISPProfile(
        isp=ISP.UNKNOWN,
        region=Region.OVERSEAS,
        name="未知",
        symmetric_ratio=0.3,
        cgnat_levels=2,
        punch_timeout_ms=8000,
        punch_parallel_ports=4,
        punch_port_strategy="hybrid",
        heartbeat_min_ms=25000,
        heartbeat_max_ms=45000,
        heartbeat_initial_ms=30000,
        udp_rate_limit_mbps=0,
        prefer_tcp=False,
        punch_success_rate=0.55,
        notes="未知运营商，使用保守配置",
    ),
}


def get_isp_profile(isp: ISP) -> ISPProfile:
    """获取运营商配置档案"""
    return ISP_PROFILES.get(isp, ISP_PROFILES[ISP.UNKNOWN])


def is_cross_border(local_isp: ISP, peer_isp: ISP) -> bool:
    """判断是否跨境"""
    local_profile = ISP_PROFILES.get(local_isp, ISP_PROFILES[ISP.UNKNOWN])
    peer_profile = ISP_PROFILES.get(peer_isp, ISP_PROFILES[ISP.UNKNOWN])
    return local_profile.region != peer_profile.region


def is_cross_isp(local_isp: ISP, peer_isp: ISP) -> bool:
    """判断是否跨运营商"""
    return local_isp != peer_isp
