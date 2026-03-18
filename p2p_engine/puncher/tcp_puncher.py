"""
TCP 穿透模块

当 UDP 被拦截时，使用 TCP 作为备选穿透方式
"""
import asyncio
import logging
import socket
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from ..types import NATInfo, ConnectionType, ISP

logger = logging.getLogger("p2p_engine.tcp_puncher")


@dataclass
class TCPPunchResult:
    """TCP 打孔结果"""
    success: bool
    connection_type: ConnectionType = ConnectionType.P2P_TCP
    local_addr: Tuple[str, int] = ("", 0)
    peer_addr: Tuple[str, int] = ("", 0)
    latency_ms: float = 0.0
    error: str = ""
    conn_socket: Optional[socket.socket] = None


class TCPPuncher:
    """
    TCP 穿透器
    
    使用 TCP Simultaneous Open 技术
    适用于企业防火墙拦截 UDP 的场景
    """
    
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
        
        self._conn_socket: Optional[socket.socket] = None
        self._local_port: int = 0
    
    async def punch(
        self,
        peer_ip: str,
        peer_port: int,
        timeout_ms: int = 10000,
    ) -> TCPPunchResult:
        """
        执行 TCP 打孔
        
        原理：
        TCP Simultaneous Open（RFC 793）
        双方同时发起 TCP 连接，利用 SYN-SYN/ACK-ACK 三次握手
        
        适用场景：
        - 企业防火墙拦截 UDP
        - UDP 限流严重
        - 需要可靠传输
        """
        start_time = time.time()
        
        logger.info(f"开始 TCP 打孔: {peer_ip}:{peer_port}")
        
        # 创建 TCP socket
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        try:
            # 绑定本地端口
            self._socket.bind(("0.0.0.0", 0))
            self._local_port = self._socket.getsockname()[1]
            
            logger.debug(f"TCP 本地端口: {self._local_port}")
            
            # 设置非阻塞
            self._socket.setblocking(False)
            
            # 尝试连接（非阻塞，会立即返回）
            try:
                self._socket.connect((peer_ip, peer_port))
            except BlockingIOError:
                # 正常，连接进行中
                pass
            except ConnectionRefusedError:
                # 对方可能还没开始监听，继续尝试
                pass
            except OSError as e:
                if e.errno not in (115, 114):  # EINPROGRESS, EALREADY
                    logger.error(f"TCP 连接错误: {e}")
                    return TCPPunchResult(
                        success=False,
                        error=f"connect_error: {e}",
                    )
            
            # 等待连接完成
            loop = asyncio.get_event_loop()
            
            try:
                # 使用 asyncio 等待 socket 可写
                await asyncio.wait_for(
                    loop.sock_connect(self._socket, (peer_ip, peer_port)),
                    timeout=timeout_ms / 1000,
                )
                
                latency = (time.time() - start_time) * 1000
                local_addr = self._socket.getsockname()
                remote_addr = self._socket.getpeername()
                
                logger.info(f"TCP 打孔成功: {local_addr} -> {remote_addr}")
                
                return TCPPunchResult(
                    success=True,
                    connection_type=ConnectionType.P2P_TCP,
                    local_addr=local_addr,
                    peer_addr=remote_addr,
                    latency_ms=latency,
                    conn_socket=self._socket,
                )
                
            except asyncio.TimeoutError:
                logger.warning("TCP 打孔超时")
                return TCPPunchResult(
                    success=False,
                    error="timeout",
                )
                
        except Exception as e:
            logger.error(f"TCP 打孔失败: {e}")
            return TCPPunchResult(
                success=False,
                error=str(e),
            )
    
    async def punch_simultaneous(
        self,
        peer_ip: str,
        peer_port_start: int,
        peer_port_end: int,
        timeout_ms: int = 10000,
    ) -> TCPPunchResult:
        """
        TCP Simultaneous Open（双向同时打开）
        
        双方同时尝试连接对方的多个端口
        增加穿透成功率
        """
        start_time = time.time()
        
        logger.info(f"开始 TCP Simultaneous Open: {peer_ip}")
        
        # 创建多个 socket 尝试连接
        sockets = []
        tasks = []
        
        loop = asyncio.get_event_loop()
        
        for port in range(peer_port_start, peer_port_end + 1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setblocking(False)
            
            try:
                sock.connect((peer_ip, port))
            except (BlockingIOError, OSError):
                pass
            
            sockets.append((sock, port))
            
            # 等待任一 socket 连接成功
            async def wait_connect(s, p):
                try:
                    await asyncio.wait_for(
                        loop.sock_connect(s, (peer_ip, p)),
                        timeout=timeout_ms / 1000,
                    )
                    return (True, s, p)
                except asyncio.TimeoutError:
                    return (False, s, p)
                except Exception:
                    return (False, s, p)
            
            tasks.append(wait_connect(sock, port))
        
        # 并行等待所有连接
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 找到成功的连接
        for result in results:
            if isinstance(result, tuple) and result[0]:
                success, sock, port = result
                latency = (time.time() - start_time) * 1000
                
                # 关闭其他 socket
                for s, _ in sockets:
                    if s != sock:
                        try:
                            s.close()
                        except Exception:
                            pass
                
                logger.info(f"TCP Simultaneous Open 成功: 端口 {port}")
                
                return TCPPunchResult(
                    success=True,
                    connection_type=ConnectionType.P2P_TCP,
                    local_addr=sock.getsockname(),
                    peer_addr=(peer_ip, port),
                    latency_ms=latency,
                    socket=sock,
                )
        
        # 全部失败
        for sock, _ in sockets:
            try:
                sock.close()
            except Exception:
                pass
        
        return TCPPunchResult(
            success=False,
            error="all_ports_failed",
        )
    
    async def listen(
        self,
        local_port: int = 0,
        timeout_ms: int = 10000,
    ) -> TCPPunchResult:
        """
        TCP 监听模式
        
        等待对端连接进来
        用于 TCP 穿透的被动方
        """
        start_time = time.time()
        
        # 创建监听 socket
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.setblocking(False)
        
        try:
            server_sock.bind(("0.0.0.0", local_port))
            server_sock.listen(1)
            
            bound_port = server_sock.getsockname()[1]
            logger.info(f"TCP 监听端口: {bound_port}")
            
            loop = asyncio.get_event_loop()
            
            # 异步等待连接
            try:
                client_sock, client_addr = await asyncio.wait_for(
                    loop.sock_accept(server_sock),
                    timeout=timeout_ms / 1000,
                )
                
                latency = (time.time() - start_time) * 1000
                local_addr = client_sock.getsockname()
                
                logger.info(f"TCP 接受连接: {client_addr}")
                
                # 关闭监听 socket
                server_sock.close()
                
                return TCPPunchResult(
                    success=True,
                    connection_type=ConnectionType.P2P_TCP,
                    local_addr=local_addr,
                    peer_addr=client_addr,
                    latency_ms=latency,
                    conn_socket=client_sock,
                )
                
            except asyncio.TimeoutError:
                logger.warning("TCP 监听超时")
                server_sock.close()
                return TCPPunchResult(
                    success=False,
                    error="listen_timeout",
                )
                
        except Exception as e:
            logger.error(f"TCP 监听失败: {e}")
            server_sock.close()
            return TCPPunchResult(
                success=False,
                error=str(e),
            )
    
    def close(self) -> None:
        """关闭 socket"""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
