"""
降级决策器

基于运营商差异化的降级决策逻辑
"""
import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum

from ..types import NATInfo, NATType, ISP
from ..config.isp_profiles import get_isp_profile, is_cross_border, is_cross_isp

logger = logging.getLogger("p2p_engine.fallback")


class FallbackReason(Enum):
    """降级原因"""
    SYMMETRIC_SYMMETRIC = "symmetric_symmetric"       # 双对称 NAT
    SYMMETRIC_TIMEOUT = "symmetric_timeout"           # 对称 NAT 超时
    MOBILE_CGNAT = "mobile_cgnat"                     # 移动 CGNAT
    CROSS_ISP_FAILED = "cross_isp_failed"             # 跨运营商失败
    CROSS_BORDER_TIMEOUT = "cross_border_timeout"     # 跨境超时
    PUNCH_TIMEOUT = "punch_timeout"                   # 打孔超时
    UDP_RATE_LIMITED = "udp_rate_limited"             # UDP 限流
    PUNCH_FAIL_COUNT = "punch_fail_count"             # 打孔失败次数
    MANUAL = "manual"                                 # 手动降级


@dataclass
class FallbackDecision:
    """降级决策结果"""
    should_fallback: bool
    reason: Optional[FallbackReason] = None
    delay_ms: int = 0            # 延迟多久降级
    target: str = "relay"        # 降级目标
    description: str = ""


class FallbackDecider:
    """降级决策器"""
    
    def __init__(self):
        self._punch_fail_count = 0
        self._last_punch_time: Optional[float] = None
    
    def record_punch_attempt(self, success: bool) -> None:
        """记录打孔尝试"""
        self._last_punch_time = time.time()
        if success:
            self._punch_fail_count = 0
        else:
            self._punch_fail_count += 1
    
    def decide(
        self,
        local_nat: NATInfo,
        peer_nat: NATInfo,
        local_isp: ISP,
        peer_isp: ISP,
        punch_duration_ms: int = 0,
    ) -> FallbackDecision:
        """
        决定是否需要降级
        
        决策优先级：
        1. 双对称 NAT → 立即降级（0ms）
        2. 移动 CGNAT + 对称 → 快速降级（<1s）
        3. 跨运营商失败多次 → 降级
        4. 跨境超时多次 → 降级
        5. 单次打孔超时 → 重试，3次后降级
        """
        
        # 规则 1: 双对称 NAT
        if local_nat.is_symmetric() and peer_nat.is_symmetric():
            logger.info("降级决策: 双对称 NAT")
            return FallbackDecision(
                should_fallback=True,
                reason=FallbackReason.SYMMETRIC_SYMMETRIC,
                delay_ms=0,
                description="双方都是对称 NAT，无法直接穿透",
            )
        
        # 规则 2: 移动 CGNAT + 对称 NAT
        local_profile = get_isp_profile(local_isp)
        peer_profile = get_isp_profile(peer_isp)
        
        if local_nat.is_cgnat and local_nat.is_symmetric():
            if local_isp == ISP.CHINA_MOBILE or local_isp == ISP.CHINA_RAILCOM:
                logger.info("降级决策: 移动 CGNAT + 对称 NAT")
                return FallbackDecision(
                    should_fallback=True,
                    reason=FallbackReason.MOBILE_CGNAT,
                    delay_ms=1000,  # 1秒后降级
                    description="移动 CGNAT + 对称 NAT，快速降级",
                )
        
        if peer_nat.is_cgnat and peer_nat.is_symmetric():
            if peer_isp == ISP.CHINA_MOBILE or peer_isp == ISP.CHINA_RAILCOM:
                logger.info("降级决策: 对端移动 CGNAT + 对称 NAT")
                return FallbackDecision(
                    should_fallback=True,
                    reason=FallbackReason.MOBILE_CGNAT,
                    delay_ms=1000,
                    description="对端移动 CGNAT + 对称 NAT",
                )
        
        # 规则 3: 跨运营商失败
        if is_cross_isp(local_isp, peer_isp):
            if self._punch_fail_count >= 3:
                logger.info(f"降级决策: 跨运营商失败 {self._punch_fail_count} 次")
                return FallbackDecision(
                    should_fallback=True,
                    reason=FallbackReason.CROSS_ISP_FAILED,
                    delay_ms=0,
                    description=f"跨运营商打孔失败 {self._punch_fail_count} 次",
                )
        
        # 规则 4: 跨境超时
        if is_cross_border(local_isp, peer_isp):
            if punch_duration_ms > 10000:  # 超过 10 秒
                logger.info(f"降级决策: 跨境超时 {punch_duration_ms}ms")
                return FallbackDecision(
                    should_fallback=True,
                    reason=FallbackReason.CROSS_BORDER_TIMEOUT,
                    delay_ms=0,
                    description=f"跨境打孔超时 {punch_duration_ms}ms",
                )
        
        # 规则 5: 打孔超时（累计）
        if self._punch_fail_count >= 3:
            logger.info(f"降级决策: 打孔失败 {self._punch_fail_count} 次")
            return FallbackDecision(
                should_fallback=True,
                reason=FallbackReason.PUNCH_FAIL_COUNT,
                delay_ms=0,
                description=f"打孔累计失败 {self._punch_fail_count} 次",
            )
        
        # 规则 6: 对称 NAT 超时（缩短等待）
        if local_nat.is_symmetric() or peer_nat.is_symmetric():
            if punch_duration_ms > 2000:  # 对称 NAT 只等 2 秒
                logger.info(f"降级决策: 对称 NAT 超时 {punch_duration_ms}ms")
                return FallbackDecision(
                    should_fallback=True,
                    reason=FallbackReason.SYMMETRIC_TIMEOUT,
                    delay_ms=0,
                    description=f"对称 NAT 打孔超时 {punch_duration_ms}ms",
                )
        
        # 不需要降级
        return FallbackDecision(
            should_fallback=False,
            description="继续尝试打孔",
        )
    
    def reset(self) -> None:
        """重置状态"""
        self._punch_fail_count = 0
        self._last_punch_time = None
