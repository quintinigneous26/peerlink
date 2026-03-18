"""
端口预测器

用于对称 NAT 的端口预测
"""
import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger("p2p_engine.port_predictor")


@dataclass
class PredictionResult:
    """预测结果"""
    ports: List[int]
    strategy: str  # "sequential" | "random" | "hybrid"


class PortPredictor:
    """端口预测器"""
    
    def __init__(
        self,
        base_port: int,
        strategy: str = "hybrid",
        predict_count: int = 8,
    ):
        self.base_port = base_port
        self.strategy = strategy
        self.predict_count = predict_count
        
        # 历史端口（用于学习规律）
        self._history: List[int] = []
    
    def predict(self) -> PredictionResult:
        """
        预测可能的端口列表
        
        策略：
        1. sequential: 递增端口 base+1, base+2, ...
        2. random: 随机端口
        3. hybrid: 混合策略（推荐）
        """
        if self.strategy == "sequential":
            return self._predict_sequential()
        elif self.strategy == "random":
            return self._predict_random()
        else:
            return self._predict_hybrid()
    
    def _predict_sequential(self) -> PredictionResult:
        """递增预测"""
        ports = [self.base_port + i for i in range(1, self.predict_count + 1)]
        return PredictionResult(ports=ports, strategy="sequential")
    
    def _predict_random(self) -> PredictionResult:
        """随机预测"""
        import random
        # 在 base_port 附近随机选择
        ports = []
        for _ in range(self.predict_count):
            offset = random.randint(1, 100)
            port = self.base_port + offset
            if 1024 <= port <= 65535:
                ports.append(port)
        return PredictionResult(ports=ports, strategy="random")
    
    def _predict_hybrid(self) -> PredictionResult:
        """混合预测（推荐）"""
        import random
        
        ports = []
        
        # 60% 递增
        seq_count = int(self.predict_count * 0.6)
        for i in range(1, seq_count + 1):
            ports.append(self.base_port + i)
        
        # 40% 随机
        rand_count = self.predict_count - seq_count
        for _ in range(rand_count):
            offset = random.randint(1, 50)
            port = self.base_port + offset
            if port not in ports and 1024 <= port <= 65535:
                ports.append(port)
        
        return PredictionResult(ports=ports, strategy="hybrid")
    
    def add_observation(self, port: int) -> None:
        """添加观察到的端口（用于学习）"""
        self._history.append(port)
        
        # 保持历史记录在合理范围
        if len(self._history) > 20:
            self._history.pop(0)
    
    def learn_pattern(self) -> Optional[int]:
        """
        从历史记录学习端口递增规律
        
        Returns:
            端口递增步长，如果无法确定则返回 None
        """
        if len(self._history) < 3:
            return None
        
        # 计算连续端口差值
        deltas = []
        for i in range(1, len(self._history)):
            delta = self._history[i] - self._history[i-1]
            deltas.append(delta)
        
        # 如果差值一致，返回该步长
        if deltas and all(d == deltas[0] for d in deltas):
            logger.debug(f"学习到端口规律: 递增步长 {deltas[0]}")
            return deltas[0]
        
        return None
