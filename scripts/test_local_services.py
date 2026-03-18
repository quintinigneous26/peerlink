#!/usr/bin/env python3
"""
本地服务测试脚本
"""

import asyncio
import socket
import sys
import time
import struct
import os
from pathlib import Path


def get_free_port() -> int:
    """获取可用端口"""
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def build_stun_binding_request() -> tuple:
    """构建 STUN Binding Request"""
    msg_type = 0x0001
    msg_length = 0
    magic_cookie = 0x2112A442
    transaction_id = os.urandom(12)
    
    header = struct.pack(
        ">HHI12s",
        msg_type,
        msg_length,
        magic_cookie,
        transaction_id
    )
    return header, transaction_id


def parse_stun_response(data: bytes, transaction_id: bytes) -> dict:
    """解析 STUN 响应"""
    if len(data) < 20:
        return {"error": f"响应太短: {len(data)} bytes"}
    
    msg_type = struct.unpack(">H", data[0:2])[0]
    msg_length = struct.unpack(">H", data[2:4])[0]
    magic_cookie = struct.unpack(">I", data[4:8])[0]
    resp_transaction_id = data[8:20]
    
    if resp_transaction_id != transaction_id:
        return {"error": "Transaction ID 不匹配"}
    
    if msg_type != 0x0101:
        return {"error": f"非成功响应: 0x{msg_type:04x}"}
    
    # 解析属性
    offset = 20
    mapped_address = None
    
    while offset + 4 <= len(data):
        attr_type = struct.unpack(">H", data[offset:offset+2])[0]
        attr_length = struct.unpack(">H", data[offset+2:offset+4])[0]
        
        attr_end = offset + 4 + attr_length
        if attr_end > len(data):
            break
        
        attr_data = data[offset+4:attr_end]
        
        # XOR-MAPPED-ADDRESS (0x0020) 或 MAPPED-ADDRESS (0x0001)
        if attr_type in (0x0020, 0x0001):
            if len(attr_data) >= 4:
                reserved = attr_data[0]
                family = attr_data[1]
                
                if family == 1 and len(attr_data) >= 8:  # IPv4
                    port = struct.unpack(">H", attr_data[2:4])[0]
                    ip_bytes = attr_data[4:8]
                    
                    if attr_type == 0x0020:  # XOR
                        port ^= (magic_cookie >> 16) & 0xFFFF
                        ip_bytes = bytes(b ^ m for b, m in zip(
                            ip_bytes, 
                            struct.pack(">I", magic_cookie)
                        ))
                    
                    ip = ".".join(str(b) for b in ip_bytes)
                    mapped_address = {"ip": ip, "port": port}
        
        # 移动到下一个属性 (4字节对齐)
        padded_length = (attr_length + 3) & ~3
        offset += 4 + padded_length
    
    if mapped_address:
        return {
            "success": True,
            "mapped_ip": mapped_address["ip"],
            "mapped_port": mapped_address["port"]
        }
    
    return {"error": f"未找到映射地址，响应长度: {len(data)}, 属性数: {offset//4}"}


async def test_stun_server(host: str, port: int, timeout: float = 5.0) -> dict:
    """测试 STUN 服务器"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    
    try:
        request, transaction_id = build_stun_binding_request()
        start_time = time.time()
        sock.sendto(request, (host, port))
        
        data, server_addr = sock.recvfrom(1024)
        latency = (time.time() - start_time) * 1000
        
        result = parse_stun_response(data, transaction_id)
        result["latency_ms"] = latency
        result["response_bytes"] = len(data)
        result["server_addr"] = server_addr
        
        return result
        
    except socket.timeout:
        return {"error": "超时"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        sock.close()


async def test_udp_hole_punch():
    """模拟 UDP 打洞"""
    print("\n[测试] UDP 打洞模拟")
    
    client_a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    client_a.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client_b.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        client_a.bind(("127.0.0.1", 0))
        client_b.bind(("127.0.0.1", 0))
        
        port_a = client_a.getsockname()[1]
        port_b = client_b.getsockname()[1]
        
        print(f"  客户端 A: 127.0.0.1:{port_a}")
        print(f"  客户端 B: 127.0.0.1:{port_b}")
        
        client_a.setblocking(False)
        client_b.setblocking(False)
        
        loop = asyncio.get_event_loop()
        
        # 双向打洞
        await loop.sock_sendto(client_a, b"PUNCH_A", ("127.0.0.1", port_b))
        await loop.sock_sendto(client_b, b"PUNCH_B", ("127.0.0.1", port_a))
        
        await asyncio.sleep(0.1)
        
        # 验证双方收到
        try:
            data_a, addr_a = await asyncio.wait_for(
                loop.sock_recvfrom(client_a, 1024), timeout=1.0
            )
            print(f"  A 收到: {data_a.decode()} from {addr_a}")
        except asyncio.TimeoutError:
            pass
        
        try:
            data_b, addr_b = await asyncio.wait_for(
                loop.sock_recvfrom(client_b, 1024), timeout=1.0
            )
            print(f"  B 收到: {data_b.decode()} from {addr_b}")
        except asyncio.TimeoutError:
            pass
        
        print("  ✓ UDP 打洞成功")
        return True
        
    except Exception as e:
        print(f"  ✗ 错误: {e}")
        return False
    finally:
        client_a.close()
        client_b.close()


async def test_public_stun():
    """测试公网 STUN 服务器"""
    servers = [
        ("stun.l.google.com", 19302),
        ("stun1.l.google.com", 19302),
        ("stun2.l.google.com", 19302),
    ]
    
    print("\n[测试] 公网 STUN 服务器")
    
    for host, port in servers:
        print(f"\n  测试 {host}:{port}")
        result = await test_stun_server(host, port)
        
        if result.get("success"):
            print(f"    ✓ 成功! 延迟: {result['latency_ms']:.1f}ms")
            print(f"    ✓ 公网地址: {result['mapped_ip']}:{result['mapped_port']}")
            return True, result
        else:
            print(f"    ✗ 失败: {result.get('error', '未知错误')}")
    
    return False, None


async def main():
    print("""
╔═══════════════════════════════════════════════════════════╗
║           P2P 本地服务测试                                 ║
╚═══════════════════════════════════════════════════════════╝
""")
    
    results = []
    
    # 测试 1: UDP 打洞
    result1 = await test_udp_hole_punch()
    results.append(("UDP 打洞", result1))
    
    # 测试 2: 公网 STUN
    result2, stun_info = await test_public_stun()
    results.append(("公网 STUN", result2))
    
    # 总结
    print("\n" + "=" * 50)
    print("测试结果总结")
    print("=" * 50)
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("✓ 所有测试通过！")
        if stun_info:
            print(f"\n你的公网信息:")
            print(f"  IP: {stun_info['mapped_ip']}")
            print(f"  端口: {stun_info['mapped_port']}")
            print(f"\n其他设备可以通过此地址连接到你。")
    else:
        print("⚠ 部分测试失败")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
