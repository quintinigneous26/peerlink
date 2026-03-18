"""
心跳保活模块

实现自适应心跳，分运营商配置
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable

from ..types import ConnectionState, ISP
from ..config.isp_profiles import ISPProfile, get_isp_profile

logger = logging.getLogger("p2p_engine.heartbeat")


@dataclass
class HeartbeatStats:
    """心跳统计"""
    total_sent: int = 0
    total_received: int = 0
    consecutive_success: int = 0
    consecutive_failure: int = 0
    last_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    last_success_time: float = 0.0


class HeartbeatKeeper:
    """心跳保活器"""
    
    def __init__(
        self,
        send_func: Callable[[bytes], Awaitable[bool]],
        on_timeout: Callable[[], Awaitable[None]],
        isp: ISP = ISP.UNKNOWN,
    ):
        """
        初始化
        
        Args:
            send_func: 发送心跳包的函数
            on_timeout: 心跳超时回调
            isp: 当前运营商
        """
        self._send_func = send_func
        self._on_timeout = on_timeout
        self._isp = isp
        
        self._profile: Optional[ISPProfile] = None
        self._interval_ms: int = 30000
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._stats = HeartbeatStats()
        
        # 心跳内容
        self._heartbeat_data = b"\x00\x00"  # 简单的空包
    
    @property
    def stats(self) -> HeartbeatStats:
        """获取统计信息"""
        return self._stats
    
    @property
    def current_interval_ms(self) -> int:
        """当前心跳间隔"""
        return self._interval_ms
    
    def set_isp(self, isp: ISP) -> None:
        """设置运营商（更新心跳参数）"""
        self._isp = isp
        self._profile = get_isp_profile(isp)
        self._interval_ms = self._profile.heartbeat_initial_ms
        logger.info(f"心跳参数已更新: ISP={isp.value}, 间隔={self._interval_ms}ms")
    
    async def start(self) -> None:
        """启动心跳"""
        if self._running:
            logger.warning("心跳已在运行")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"心跳已启动: 间隔={self._interval_ms}ms")
    
    async def stop(self) -> None:
        """停止心跳"""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info("心跳已停止")
    
    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while self._running:
            try:
                # 发送心跳
                success = await self._send_heartbeat()
                
                if success:
                    self._on_heartbeat_success()
                else:
                    await self._on_heartbeat_failure()
                
                # 等待下一次心跳
                await asyncio.sleep(self._interval_ms / 1000)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳循环异常: {e}")
                await asyncio.sleep(1)
    
    async def _send_heartbeat(self) -> bool:
        """发送心跳包"""
        try:
            start_time = time.time()
            
            success = await self._send_func(self._heartbeat_data)
            
            latency = (time.time() - start_time) * 1000
            self._stats.last_latency_ms = latency
            
            return success
            
        except Exception as e:
            logger.debug(f"发送心跳失败: {e}")
            return False
    
    def _on_heartbeat_success(self) -> None:
        """心跳成功处理"""
        self._stats.total_received += 1
        self._stats.consecutive_success += 1
        self._stats.consecutive_failure = 0
        self._stats.last_success_time = time.time()
        
        # 更新平均延迟
        if self._stats.total_received == 1:
            self._stats.avg_latency_ms = self._stats.last_latency_ms
        else:
            # 指数移动平均
            alpha = 0.2
            self._stats.avg_latency_ms = (
                alpha * self._stats.last_latency_ms +
                (1 - alpha) * self._stats.avg_latency_ms
            )
        
        # 自适应延长心跳间隔
        if self._profile and self._profile.heartbeat_max_ms > self._interval_ms:
            if self._stats.consecutive_success >= self._profile.success_to_extend:
                new_interval = min(
                    self._interval_ms + 5000,
                    self._profile.heartbeat_max_ms
                )
                if new_interval != self._interval_ms:
                    self._interval_ms = new_interval
                    logger.debug(f"心跳间隔延长至 {self._interval_ms}ms")
    
    async def _on_heartbeat_failure(self) -> None:
        """心跳失败处理"""
        self._stats.consecutive_failure += 1
        self._stats.consecutive_success = 0
        
        logger.warning(f"心跳失败 ({self._stats.consecutive_failure}次)")
        
        # 自适应缩短心跳间隔
        if self._profile:
            self._interval_ms = max(
                self._interval_ms - 5000,
                self._profile.heartbeat_min_ms
            )
        
        # 连续失败超过阈值，触发超时回调
        if self._stats.consecutive_failure >= 3:
            logger.error("心跳连续失败 3 次，触发超时")
            if self._on_timeout:
                await self._on_timeout()
    
    def reset_stats(self) -> None:
        """重置统计"""
        self._stats = HeartbeatStats()
