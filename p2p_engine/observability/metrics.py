"""
指标收集器

按运营商维度统计连接成功率等指标
"""
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List
from threading import Lock

from ..types import ISP, ConnectionType, NATType

logger = logging.getLogger("p2p_engine.metrics")


@dataclass
class ConnectionMetrics:
    """连接指标"""
    total_attempts: int = 0
    p2p_success: int = 0
    relay_success: int = 0
    failed: int = 0
    total_latency_ms: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_attempts == 0:
            return 0.0
        return (self.p2p_success + self.relay_success) / self.total_attempts
    
    @property
    def p2p_rate(self) -> float:
        """P2P 成功率"""
        if self.total_attempts == 0:
            return 0.0
        return self.p2p_success / self.total_attempts
    
    @property
    def avg_latency_ms(self) -> float:
        """平均延迟"""
        success_count = self.p2p_success + self.relay_success
        if success_count == 0:
            return 0.0
        return self.total_latency_ms / success_count


@dataclass
class NATMetrics:
    """NAT 指标"""
    nat_type_counts: Dict[NATType, int] = field(default_factory=lambda: defaultdict(int))
    cgnat_count: int = 0
    symmetric_count: int = 0


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self._lock = Lock()
        
        # 按运营商统计
        self._isp_metrics: Dict[ISP, ConnectionMetrics] = defaultdict(ConnectionMetrics)
        
        # NAT 统计
        self._nat_metrics = NATMetrics()
        
        # 总体统计
        self._total_metrics = ConnectionMetrics()
        
        # 开始时间
        self._start_time = time.time()
    
    def record_connection(
        self,
        local_isp: ISP,
        peer_isp: ISP,
        connection_type: ConnectionType,
        latency_ms: float,
    ) -> None:
        """记录连接结果"""
        with self._lock:
            # 更新本地运营商统计
            local_metrics = self._isp_metrics[local_isp]
            local_metrics.total_attempts += 1
            local_metrics.total_latency_ms += latency_ms
            
            if connection_type == ConnectionType.P2P_UDP or connection_type == ConnectionType.P2P_TCP:
                local_metrics.p2p_success += 1
            elif connection_type == ConnectionType.RELAY_UDP or connection_type == ConnectionType.RELAY_TCP:
                local_metrics.relay_success += 1
            else:
                local_metrics.failed += 1
            
            # 更新总体统计
            self._total_metrics.total_attempts += 1
            self._total_metrics.total_latency_ms += latency_ms
            if connection_type == ConnectionType.P2P_UDP or connection_type == ConnectionType.P2P_TCP:
                self._total_metrics.p2p_success += 1
            elif connection_type == ConnectionType.RELAY_UDP or connection_type == ConnectionType.RELAY_TCP:
                self._total_metrics.relay_success += 1
            else:
                self._total_metrics.failed += 1
    
    def record_nat_detection(
        self,
        nat_type: NATType,
        is_cgnat: bool,
    ) -> None:
        """记录 NAT 检测结果"""
        with self._lock:
            self._nat_metrics.nat_type_counts[nat_type] += 1
            
            if is_cgnat:
                self._nat_metrics.cgnat_count += 1
            
            if nat_type == NATType.SYMMETRIC:
                self._nat_metrics.symmetric_count += 1
    
    def get_isp_metrics(self, isp: ISP) -> ConnectionMetrics:
        """获取运营商指标"""
        return self._isp_metrics.get(isp, ConnectionMetrics())
    
    def get_all_isp_metrics(self) -> Dict[ISP, ConnectionMetrics]:
        """获取所有运营商指标"""
        return dict(self._isp_metrics)
    
    def get_total_metrics(self) -> ConnectionMetrics:
        """获取总体指标"""
        return self._total_metrics
    
    def get_nat_metrics(self) -> NATMetrics:
        """获取 NAT 指标"""
        return self._nat_metrics
    
    def get_summary(self) -> dict:
        """获取摘要报告"""
        uptime = time.time() - self._start_time
        
        return {
            "uptime_seconds": int(uptime),
            "total": {
                "attempts": self._total_metrics.total_attempts,
                "p2p_success": self._total_metrics.p2p_success,
                "relay_success": self._total_metrics.relay_success,
                "failed": self._total_metrics.failed,
                "success_rate": f"{self._total_metrics.success_rate:.1%}",
                "p2p_rate": f"{self._total_metrics.p2p_rate:.1%}",
                "avg_latency_ms": f"{self._total_metrics.avg_latency_ms:.1f}",
            },
            "by_isp": {
                isp.value: {
                    "attempts": m.total_attempts,
                    "success_rate": f"{m.success_rate:.1%}",
                    "p2p_rate": f"{m.p2p_rate:.1%}",
                }
                for isp, m in self._isp_metrics.items()
                if m.total_attempts > 0
            },
            "nat": {
                "cgnat_count": self._nat_metrics.cgnat_count,
                "symmetric_count": self._nat_metrics.symmetric_count,
                "by_type": {
                    t.value: c
                    for t, c in self._nat_metrics.nat_type_counts.items()
                },
            },
        }
    
    def reset(self) -> None:
        """重置指标"""
        with self._lock:
            self._isp_metrics.clear()
            self._nat_metrics = NATMetrics()
            self._total_metrics = ConnectionMetrics()
            self._start_time = time.time()
