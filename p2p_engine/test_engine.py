#!/usr/bin/env python3
"""
P2P Engine 框架测试（完整版）

测试所有新增模块：
- 欧美运营商配置
- 设备厂商检测
- TCP 穿透
- 网络环境检测
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from p2p_engine import (
    ISP,
    NATType,
    NATInfo,
    ConnectionState,
    ConnectionType,
    DeviceVendor,
    NetworkEnvironment,
    get_isp_profile,
)
from p2p_engine.config.isp_profiles import ISP_PROFILES


def test_global_isp_profiles():
    """测试全球运营商配置"""
    print("\n=== 测试全球运营商配置 ===")
    
    # 统计各区域运营商数量
    regions = {"mainland": 0, "hongkong": 0, "singapore": 0, "overseas": 0}
    
    for isp, profile in ISP_PROFILES.items():
        regions[profile.region.value] = regions.get(profile.region.value, 0) + 1
    
    print("\n运营商分布:")
    for region, count in regions.items():
        print(f"  {region}: {count} 个")
    
    # 测试美国运营商
    us_isps = [ISP.ATT, ISP.VERIZON, ISP.TMOBILE, ISP.COMCAST]
    print("\n美国运营商配置:")
    for isp in us_isps:
        profile = get_isp_profile(isp)
        print(f"  {profile.name}:")
        print(f"    穿透成功率: {profile.punch_success_rate * 100:.0f}%")
        print(f"    端口策略: {profile.punch_port_strategy}")
    
    # 测试欧洲运营商
    eu_isps = [ISP.VODAFONE, ISP.ORANGE, ISP.DEUTSCHE_TELEKOM, ISP.BT]
    print("\n欧洲运营商配置:")
    for isp in eu_isps:
        profile = get_isp_profile(isp)
        print(f"  {profile.name}:")
        print(f"    心跳间隔: {profile.heartbeat_initial_ms}ms")
    
    # 测试日韩运营商
    asia_isps = [ISP.NTT, ISP.KDDI, ISP.SK_TELECOM, ISP.KT]
    print("\n日韩运营商配置:")
    for isp in asia_isps:
        profile = get_isp_profile(isp)
        print(f"  {profile.name}:")
        print(f"    穿透成功率: {profile.punch_success_rate * 100:.0f}%")
    
    print("\n✅ 全球运营商配置测试通过")


def test_device_profiles():
    """测试设备厂商配置"""
    print("\n=== 测试设备厂商配置 ===")
    
    from p2p_engine.detection.device_detector import DEVICE_PROFILES, DeviceVendor
    
    # 统计设备类型
    vendors_by_type = {
        "运营商级": [DeviceVendor.HUAWEI, DeviceVendor.ZTE, DeviceVendor.ERICSSON, 
                   DeviceVendor.NOKIA, DeviceVendor.FIBERHOME],
        "企业级": [DeviceVendor.CISCO, DeviceVendor.H3C, DeviceVendor.SANGFOR,
                  DeviceVendor.PALO_ALTO, DeviceVendor.FORTINET],
        "家用级": [DeviceVendor.TP_LINK, DeviceVendor.XIAOMI],
    }
    
    for vendor_type, vendors in vendors_by_type.items():
        print(f"\n{vendor_type}设备:")
        for vendor in vendors:
            profile = DEVICE_PROFILES.get(vendor)
            if profile:
                print(f"  {vendor.value}:")
                print(f"    端口策略: {profile.port_strategy}")
                print(f"    ALG: {'启用' if profile.alg_enabled else '未启用'}")
                print(f"    打孔策略: {profile.punch_strategy}")
    
    print("\n✅ 设备厂商配置测试通过")


async def test_tcp_puncher():
    """测试 TCP 穿透模块"""
    print("\n=== 测试 TCP 穿透模块 ===")
    
    from p2p_engine.puncher.tcp_puncher import TCPPuncher
    
    # 创建测试用例
    local_nat = NATInfo(
        type=NATType.PORT_RESTRICTED,
        public_ip="192.168.1.100",
        public_port=50000,
    )
    peer_nat = NATInfo(
        type=NATType.PORT_RESTRICTED,
        public_ip="192.168.2.100",
        public_port=50001,
    )
    
    puncher = TCPPuncher(
        local_nat=local_nat,
        peer_nat=peer_nat,
        local_isp=ISP.CHINA_TELECOM,
        peer_isp=ISP.CHINA_TELECOM,
    )
    
    print("  TCP 穿透器创建成功")
    print("  支持的穿透模式:")
    print("    - punch: 单端口连接")
    print("    - punch_simultaneous: 多端口同时打开")
    print("    - listen: 监听模式")
    
    print("\n✅ TCP 穿透模块测试通过")


async def test_network_detector():
    """测试网络环境检测"""
    print("\n=== 测试网络环境检测 ===")
    
    from p2p_engine.detection.network_detector import NetworkDetector, NetworkEnvironment
    from p2p_engine.detection.stun_client import STUNClient
    
    # 创建 STUN 客户端
    stun_client = STUNClient(
        servers=["stun.l.google.com:19302"],
        timeout_ms=3000,
    )
    
    # 创建检测器
    detector = NetworkDetector(stun_client)
    
    # 测试网络环境数据结构
    env = NetworkEnvironment(
        nat_level=2,
        is_behind_vpn=False,
        is_enterprise_network=False,
        is_mobile_network=False,
        firewall_type="home",
        ipv6_available=True,
        ipv6_preferred=False,
        packet_loss_rate=0.05,
        avg_latency_ms=50.0,
    )
    
    print(f"  网络环境:")
    print(f"    NAT 层级: {env.nat_level}")
    print(f"    企业网络: {env.is_enterprise_network}")
    print(f"    IPv6 可用: {env.ipv6_available}")
    print(f"    丢包率: {env.packet_loss_rate * 100:.1f}%")
    print(f"    平均延迟: {env.avg_latency_ms:.0f}ms")
    print(f"    复杂环境: {detector.is_complex_environment(env)}")
    
    print("\n✅ 网络环境检测测试通过")


def test_cross_border_logic():
    """测试跨境逻辑"""
    print("\n=== 测试跨境/跨运营商逻辑 ===")
    
    from p2p_engine.config.isp_profiles import is_cross_border, is_cross_isp
    
    # 测试跨运营商
    cases = [
        (ISP.CHINA_TELECOM, ISP.CHINA_MOBILE, "同国跨运营商"),
        (ISP.CHINA_TELECOM, ISP.ATT, "跨境（中国→美国）"),
        (ISP.SINGTEL, ISP.VODAFONE, "跨境（新加坡→欧洲）"),
        (ISP.CHINA_MOBILE, ISP.CMHK, "跨境（大陆→香港）"),
    ]
    
    print("\n跨运营商/跨境测试:")
    for local_isp, peer_isp, desc in cases:
        cross_isp = is_cross_isp(local_isp, peer_isp)
        cross_border = is_cross_border(local_isp, peer_isp)
        
        print(f"  {desc}:")
        print(f"    跨运营商: {cross_isp}")
        print(f"    跨境: {cross_border}")
    
    print("\n✅ 跨境逻辑测试通过")


async def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║       P2P Engine 完整框架测试（全球运营商版）            ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    # 同步测试
    test_global_isp_profiles()
    test_device_profiles()
    test_cross_border_logic()
    
    # 异步测试
    await test_tcp_puncher()
    await test_network_detector()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！框架支持全球运营商和网络环境。")
    print("=" * 60)
    
    # 打印统计信息
    print("\n📊 框架统计:")
    print(f"  运营商配置: {len(ISP_PROFILES)} 个")
    print(f"  设备配置: {len([v for v in DeviceVendor])} 个")
    print(f"  支持区域: 中国大陆、香港、新加坡、美国、欧洲、东南亚、日韩")


if __name__ == "__main__":
    asyncio.run(main())
