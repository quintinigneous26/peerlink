"""
默认配置

分层配置结构：
  DEFAULT_CONFIG → REGION_CONFIG → ISP_CONFIG → SCENARIO_CONFIG
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json


@dataclass
class STUNConfig:
    """STUN 配置"""
    servers: List[str] = field(default_factory=lambda: [
        "stun.l.google.com:19302",
        "stun1.l.google.com:19302",
        "stun.stunprotocol.org:3478",
    ])
    timeout_ms: int = 3000
    retry_count: int = 3


@dataclass
class PunchConfig:
    """打孔配置"""
    # 并行端口数
    parallel_ports: int = 4
    
    # 端口策略: "sequential" | "random" | "hybrid"
    port_strategy: str = "sequential"
    
    # 端口预测范围
    port_predict_range: int = 8  # 预测 base+N 个端口
    
    # 超时配置
    timeout_ms: int = 5000
    retry_count: int = 3
    
    # 并发限制
    max_concurrent: int = 8


@dataclass
class HeartbeatConfig:
    """心跳配置"""
    interval_ms: int = 30000          # 心跳间隔
    min_interval_ms: int = 15000      # 最小间隔
    max_interval_ms: int = 60000      # 最大间隔
    
    timeout_ms: int = 5000            # 单次超时
    retry_count: int = 3              # 失败重试次数
    retry_interval_ms: int = 2000     # 重试间隔
    
    # 自适应
    adaptive: bool = True             # 是否启用自适应
    success_to_extend: int = 10       # 连续成功多少次延长间隔


@dataclass
class FallbackConfig:
    """降级配置"""
    # 降级触发阈值
    punch_fail_count: int = 3         # 打孔失败多少次降级
    udp_loss_rate: float = 0.3        # UDP 丢包率阈值
    udp_latency_ms: int = 500         # UDP 延迟阈值
    
    # 跨境配置
    cross_border_loss_rate: float = 0.2
    cross_border_timeout_ms: int = 10000
    
    # Relay 配置
    relay_timeout_ms: int = 5000
    relay_servers: List[str] = field(default_factory=list)


@dataclass
class Config:
    """完整配置"""
    stun: STUNConfig = field(default_factory=STUNConfig)
    punch: PunchConfig = field(default_factory=PunchConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    fallback: FallbackConfig = field(default_factory=FallbackConfig)
    
    # 日志级别
    log_level: str = "INFO"
    
    # 调试模式
    debug: bool = False
    
    def merge(self, other: dict) -> "Config":
        """深度合并配置（other 覆盖 self）

        Args:
            other: 要合并的配置字典，支持嵌套结构

        Returns:
            合并后的 Config 对象
        """
        def deep_merge(base: dict, update: dict) -> dict:
            """递归合并字典"""
            result = base.copy()
            for key, value in update.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        if "stun" in other:
            stun_dict = deep_merge(self.stun.__dict__.copy(), other["stun"])
            for k, v in stun_dict.items():
                setattr(self.stun, k, v)

        if "punch" in other:
            punch_dict = deep_merge(self.punch.__dict__.copy(), other["punch"])
            for k, v in punch_dict.items():
                setattr(self.punch, k, v)

        if "heartbeat" in other:
            heartbeat_dict = deep_merge(self.heartbeat.__dict__.copy(), other["heartbeat"])
            for k, v in heartbeat_dict.items():
                setattr(self.heartbeat, k, v)

        if "fallback" in other:
            fallback_dict = deep_merge(self.fallback.__dict__.copy(), other["fallback"])
            for k, v in fallback_dict.items():
                setattr(self.fallback, k, v)

        if "log_level" in other:
            self.log_level = other["log_level"]
        if "debug" in other:
            self.debug = other["debug"]

        return self
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "stun": self.stun.__dict__,
            "punch": self.punch.__dict__,
            "heartbeat": self.heartbeat.__dict__,
            "fallback": self.fallback.__dict__,
            "log_level": self.log_level,
            "debug": self.debug,
        }


# 默认配置（全局）
DEFAULT_CONFIG = Config()
