"""
STUN 客户端

基于 RFC 5389 实现
"""
import asyncio
import logging
import socket
import struct
import os
from dataclasses import dataclass
from typing import Optional, Tuple, List

logger = logging.getLogger("p2p_engine.stun")


# STUN 常量
STUN_MAGIC_COOKIE = 0x2112A442
STUN_BINDING_REQUEST = 0x0001
STUN_BINDING_RESPONSE = 0x0101

# STUN 属性类型
STUN_ATTR_MAPPED_ADDRESS = 0x0001
STUN_ATTR_XOR_MAPPED_ADDRESS = 0x0020
STUN_ATTR_CHANGE_REQUEST = 0x0003
STUN_ATTR_CHANGED_ADDRESS = 0x0005


@dataclass
class STUNResponse:
    """STUN 响应"""
    success: bool
    mapped_ip: str = ""
    mapped_port: int = 0
    source_ip: str = ""
    source_port: int = 0
    changed_ip: str = ""
    changed_port: int = 0
    error: str = ""


class STUNClient:
    """STUN 客户端"""
    
    def __init__(
        self,
        servers: List[str],
        timeout_ms: int = 3000,
        retry_count: int = 3,
    ):
        self.servers = servers
        self.timeout_ms = timeout_ms
        self.retry_count = retry_count
    
    async def binding_request(
        self,
        server: str,
        port: int = 3478,
    ) -> STUNResponse:
        """
        发送 STUN Binding Request
        
        Args:
            server: STUN 服务器地址
            port: STUN 服务器端口
        
        Returns:
            STUNResponse
        """
        # 解析服务器地址
        try:
            server_ip = await self._resolve_host(server)
        except Exception as e:
            return STUNResponse(success=False, error=f"DNS 解析失败: {e}")
        
        # 创建 UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout_ms / 1000)
        
        try:
            # 构建 Binding Request
            transaction_id = os.urandom(12)
            request = self._build_binding_request(transaction_id)
            
            # 发送请求
            sock.sendto(request, (server_ip, port))
            
            # 接收响应
            data, addr = sock.recvfrom(1024)
            
            # 解析响应
            return self._parse_response(data, transaction_id)
            
        except socket.timeout:
            return STUNResponse(success=False, error="超时")
        except Exception as e:
            return STUNResponse(success=False, error=str(e))
        finally:
            sock.close()
    
    async def _resolve_host(self, host: str) -> str:
        """解析主机名"""
        loop = asyncio.get_event_loop()
        result = await loop.getaddrinfo(host, None)
        return result[0][4][0]
    
    def _build_binding_request(self, transaction_id: bytes) -> bytes:
        """构建 Binding Request"""
        # Type(2) + Length(2) + Magic Cookie(4) + Transaction ID(12)
        header = struct.pack(
            ">HHI12s",
            STUN_BINDING_REQUEST,
            0,  # 无属性
            STUN_MAGIC_COOKIE,
            transaction_id
        )
        return header
    
    def _parse_response(self, data: bytes, transaction_id: bytes) -> STUNResponse:
        """解析 STUN 响应"""
        if len(data) < 20:
            return STUNResponse(success=False, error="响应太短")
        
        # 解析头部
        msg_type = struct.unpack(">H", data[0:2])[0]
        msg_length = struct.unpack(">H", data[2:4])[0]
        magic_cookie = struct.unpack(">I", data[4:8])[0]
        resp_transaction_id = data[8:20]
        
        # 验证
        if magic_cookie != STUN_MAGIC_COOKIE:
            return STUNResponse(success=False, error="Magic Cookie 不匹配")
        
        if resp_transaction_id != transaction_id:
            return STUNResponse(success=False, error="Transaction ID 不匹配")
        
        if msg_type != STUN_BINDING_RESPONSE:
            return STUNResponse(success=False, error=f"非成功响应: 0x{msg_type:04x}")
        
        # 解析属性
        response = STUNResponse(success=True)
        offset = 20
        
        while offset + 4 <= len(data):
            attr_type = struct.unpack(">H", data[offset:offset+2])[0]
            attr_length = struct.unpack(">H", data[offset+2:offset+4])[0]
            
            if offset + 4 + attr_length > len(data):
                break
            
            attr_data = data[offset+4:offset+4+attr_length]
            
            if attr_type == STUN_ATTR_XOR_MAPPED_ADDRESS:
                mapped = self._parse_xor_mapped_address(attr_data)
                if mapped:
                    response.mapped_ip = mapped[0]
                    response.mapped_port = mapped[1]
            
            elif attr_type == STUN_ATTR_MAPPED_ADDRESS:
                mapped = self._parse_mapped_address(attr_data)
                if mapped:
                    response.mapped_ip = mapped[0]
                    response.mapped_port = mapped[1]
            
            # 移动到下一个属性（4字节对齐）
            padded_length = (attr_length + 3) & ~3
            offset += 4 + padded_length
        
        if not response.mapped_ip:
            response.success = False
            response.error = "未找到映射地址"
        
        return response
    
    def _parse_xor_mapped_address(self, data: bytes) -> Optional[Tuple[str, int]]:
        """解析 XOR-MAPPED-ADDRESS"""
        if len(data) < 8:
            return None
        
        family = data[1]
        if family != 1:  # 只支持 IPv4
            return None
        
        xport = struct.unpack(">H", data[2:4])[0]
        xip = data[4:8]
        
        # XOR 解码
        port = xport ^ ((STUN_MAGIC_COOKIE >> 16) & 0xFFFF)
        ip_bytes = bytes(b ^ m for b, m in zip(
            xip,
            struct.pack(">I", STUN_MAGIC_COOKIE)
        ))
        ip = ".".join(str(b) for b in ip_bytes)
        
        return ip, port
    
    def _parse_mapped_address(self, data: bytes) -> Optional[Tuple[str, int]]:
        """解析 MAPPED-ADDRESS"""
        if len(data) < 8:
            return None
        
        family = data[1]
        if family != 1:
            return None
        
        port = struct.unpack(">H", data[2:4])[0]
        ip = ".".join(str(b) for b in data[4:8])
        
        return ip, port
