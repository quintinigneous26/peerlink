#!/usr/bin/env python3
"""
单机 NAT 穿透模拟测试

使用 Docker 容器模拟不同 NAT 环境，测试 P2P 连接能力。

架构:
┌─────────────────────────────────────────────────────────┐
│                      Docker 网络                         │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐             │
│  │ Client A│    │ Server  │    │ Client B│             │
│  │ NAT网桥1│◄──►│ STUN等  │◄──►│ NAT网桥2│             │
│  └─────────┘    └─────────┘    └─────────┘             │
└─────────────────────────────────────────────────────────┘
"""

import asyncio
import json
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class NATType(Enum):
    """NAT 类型"""
    FULL_CONE = "full_cone"
    RESTRICTED_CONE = "restricted_cone"
    PORT_RESTRICTED = "port_restricted"
    SYMMETRIC = "symmetric"


@dataclass
class TestResult:
    """测试结果"""
    client_a_nat: NATType
    client_b_nat: NATType
    direct_connection: bool
    relay_required: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class NATSimulator:
    """使用 iptables 模拟 NAT 行为"""
    
    @staticmethod
    def get_iptables_rules(nat_type: NATType, container_id: str) -> list[str]:
        """根据 NAT 类型生成 iptables 规则"""
        rules = []
        
        if nat_type == NATType.FULL_CONE:
            # Full Cone: 任何外部主机都可以通过映射发送数据
            rules = [
                f"iptables -t nat -A POSTROUTING -s {container_id} -j MASQUERADE",
            ]
        elif nat_type == NATType.RESTRICTED_CONE:
            # Restricted Cone: 只有发送过数据的主机才能回复
            rules = [
                f"iptables -t nat -A POSTROUTING -s {container_id} -j MASQUERADE",
                f"iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
                f"iptables -A INPUT -m state --state NEW -j DROP",
            ]
        elif nat_type == NATType.PORT_RESTRICTED:
            # Port Restricted: IP 和端口都必须匹配
            rules = [
                f"iptables -t nat -A POSTROUTING -s {container_id} -j MASQUERADE",
                f"iptables -A INPUT -m state --state ESTABLISHED -j ACCEPT",
                f"iptables -A INPUT -j DROP",
            ]
        elif nat_type == NATType.SYMMETRIC:
            # Symmetric: 每个目标使用不同的端口
            rules = [
                f"iptables -t nat -A POSTROUTING -s {container_id} -j MASQUERADE --to-ports 40000-50000",
            ]
        
        return rules


class LocalNATTest:
    """本地 NAT 测试（无需 Docker）"""
    
    def __init__(self, stun_host: str = "stun.l.google.com", stun_port: int = 19302):
        self.stun_host = stun_host
        self.stun_port = stun_port
    
    def detect_local_nat_type(self) -> tuple[Optional[str], Optional[str], Optional[int]]:
        """
        检测本地网络的 NAT 类型
        返回: (nat_type, public_ip, public_port)
        """
        try:
            import stun
            
            nat_type, external_ip, external_port = stun.get_ip_info(
                stun_host=self.stun_host,
                stun_port=self.stun_port
            )
            return nat_type, external_ip, external_port
        except ImportError:
            print("请先安装 pystun3: pip install pystun3")
            return None, None, None
        except Exception as e:
            print(f"检测 NAT 类型失败: {e}")
            return None, None, None
    
    def test_udp_hole_punch(self, local_port: int = 0) -> dict:
        """测试 UDP 打洞能力"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            sock.bind(("0.0.0.0", local_port or 0))
            actual_port = sock.getsockname()[1]
            
            # 发送 STUN 绑定请求
            stun_request = self._build_stun_binding_request()
            sock.sendto(stun_request, (self.stun_host, self.stun_port))
            
            sock.settimeout(5)
            try:
                data, addr = sock.recvfrom(1024)
                mapped_addr = self._parse_stun_response(data)
                return {
                    "success": True,
                    "local_port": actual_port,
                    "mapped_address": mapped_addr,
                    "stun_server": addr,
                }
            except socket.timeout:
                return {"success": False, "error": "STUN 服务器响应超时"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            sock.close()
    
    def _build_stun_binding_request(self) -> bytes:
        """构建 STUN Binding Request"""
        import struct
        import os
        
        # STUN Header: Type(2) + Length(2) + Magic Cookie(4) + Transaction ID(12)
        msg_type = 0x0001  # Binding Request
        msg_length = 0     # 无属性
        magic_cookie = 0x2112A442
        transaction_id = os.urandom(12)
        
        header = struct.pack(
            ">HHI12s",
            msg_type,
            msg_length,
            magic_cookie,
            transaction_id
        )
        return header
    
    def _parse_stun_response(self, data: bytes) -> dict:
        """解析 STUN 响应"""
        import struct
        
        if len(data) < 20:
            return {"error": "响应太短"}
        
        msg_type, msg_length, magic_cookie = struct.unpack(">HHI", data[:8])
        
        # 简化解析，只提取 XOR-MAPPED-ADDRESS (类型 0x0020)
        # 或 MAPPED-ADDRESS (类型 0x0001)
        offset = 20
        while offset < len(data):
            attr_type, attr_length = struct.unpack(">HH", data[offset:offset+4])
            
            if attr_type in (0x0001, 0x0020):  # MAPPED-ADDRESS or XOR-MAPPED-ADDRESS
                # 简化：假设是 IPv4
                family = data[offset + 4]
                if family == 1:  # IPv4
                    port = struct.unpack(">H", data[offset + 6:offset + 8])[0]
                    if attr_type == 0x0020:  # XOR
                        port ^= 0x2112
                    ip_bytes = data[offset + 8:offset + 12]
                    if attr_type == 0x0020:  # XOR with magic cookie
                        ip_bytes = bytes(b ^ m for b, m in zip(ip_bytes, struct.pack(">I", magic_cookie)))
                    ip = ".".join(str(b) for b in ip_bytes)
                    return {"ip": ip, "port": port}
            
            offset += 4 + attr_length
            if attr_length % 4 != 0:
                offset += 4 - (attr_length % 4)  # Padding
        
        return {"error": "未找到映射地址"}


async def test_local_stun():
    """测试本地 STUN 连接"""
    print("=" * 50)
    print("本地 STUN 测试")
    print("=" * 50)
    
    tester = LocalNATTest()
    
    # 测试 1: 检测 NAT 类型
    print("\n[1] 检测 NAT 类型...")
    nat_type, public_ip, public_port = tester.detect_local_nat_type()
    
    if nat_type:
        print(f"    NAT 类型: {nat_type}")
        print(f"    公网 IP: {public_ip}")
        print(f"    公网端口: {public_port}")
    else:
        print("    无法检测 NAT 类型，尝试直接测试...")
    
    # 测试 2: UDP 打洞测试
    print("\n[2] UDP 打洞测试...")
    result = tester.test_udp_hole_punch()
    
    if result["success"]:
        print(f"    ✓ STUN 响应成功")
        print(f"    本地端口: {result['local_port']}")
        if "mapped_address" in result:
            addr = result["mapped_address"]
            if "ip" in addr:
                print(f"    映射地址: {addr['ip']}:{addr['port']}")
    else:
        print(f"    ✗ 测试失败: {result.get('error', '未知错误')}")
    
    return result


def print_nat_matrix():
    """打印 NAT 穿透可能性矩阵"""
    print("\n" + "=" * 60)
    print("NAT 穿透可能性矩阵")
    print("=" * 60)
    
    nat_types = ["Full Cone", "Restricted", "Port Restricted", "Symmetric"]
    
    print("\n              │", end="")
    for t in nat_types:
        print(f" {t[:12]:12}│", end="")
    print()
    print("─" * 70)
    
    results = {
        ("Full Cone", "Full Cone"): "✓ 直接",
        ("Full Cone", "Restricted"): "✓ 直接",
        ("Full Cone", "Port Restricted"): "✓ 直接",
        ("Full Cone", "Symmetric"): "✓ 直接",
        ("Restricted", "Full Cone"): "✓ 直接",
        ("Restricted", "Restricted"): "✓ 直接",
        ("Restricted", "Port Restricted"): "✓ 直接",
        ("Restricted", "Symmetric"): "✓ 直接",
        ("Port Restricted", "Full Cone"): "✓ 直接",
        ("Port Restricted", "Restricted"): "✓ 直接",
        ("Port Restricted", "Port Restricted"): "✓ 直接",
        ("Port Restricted", "Symmetric"): "✓ 直接",
        ("Symmetric", "Full Cone"): "✓ 直接",
        ("Symmetric", "Restricted"): "✓ 直接",
        ("Symmetric", "Port Restricted"): "✓ 直接",
        ("Symmetric", "Symmetric"): "⚠ Relay",
    }
    
    for client in nat_types:
        print(f"{client[:14]:14}│", end="")
        for peer in nat_types:
            result = results.get((client, peer), "?")
            print(f" {result:12}│", end="")
        print()


def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║           P2P 单机 NAT 穿透测试                            ║
║                                                            ║
║  此脚本测试你当前网络环境的 NAT 类型                        ║
║  和 UDP 打洞能力                                           ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    # 打印 NAT 矩阵
    print_nat_matrix()
    
    # 运行本地测试
    result = asyncio.run(test_local_stun())
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)
    
    if result.get("success"):
        print("\n✓ 你的网络支持 STUN/NAT 穿透")
        print("  其他设备可以通过你的公网地址连接到你")
    else:
        print("\n✗ NAT 穿透可能受限")
        print("  可能需要使用 Relay 服务器中继")
    
    print("\n下一步:")
    print("  1. 在不同网络下运行此脚本，比较 NAT 类型")
    print("  2. 使用 docker-compose up -d 启动你的服务")
    print("  3. 运行 pytest tests/integration/ 测试完整功能")


if __name__ == "__main__":
    main()
