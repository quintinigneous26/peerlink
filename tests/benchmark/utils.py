"""
性能测试工具函数

提供通用的性能测量和报告功能
"""
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class PerformanceReport:
    """性能测试报告"""
    test_name: str
    timestamp: str
    results: dict[str, Any]
    targets: dict[str, float]
    passed: bool
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Optional[Path] = None):
        """保存报告到文件"""
        if path is None:
            path = Path(f"reports/performance/{self.test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class PerformanceBenchmark:
    """性能基准测试框架"""

    def __init__(self, name: str, targets: dict[str, float]):
        """
        初始化基准测试

        Args:
            name: 测试名称
            targets: 性能目标基准值
        """
        self.name = name
        self.targets = targets
        self.measurements: list[float] = []

    async def measure(
        self,
        func: Callable,
        iterations: int = 100,
        warmup: int = 10,
    ) -> dict[str, float]:
        """
        测量函数执行性能

        Args:
            func: 要测量的异步函数
            iterations: 迭代次数
            warmup: 预热次数

        Returns:
            统计结果
        """
        # 预热
        for _ in range(warmup):
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()

        # 测量
        self.measurements = []
        for _ in range(iterations):
            start = time.perf_counter()
            if asyncio.iscoroutinefunction(func):
                await func()
            else:
                func()
            self.measurements.append((time.perf_counter() - start) * 1000)

        return self._calculate_stats()

    def _calculate_stats(self) -> dict[str, float]:
        """计算统计结果"""
        if not self.measurements:
            return {}

        sorted_measurements = sorted(self.measurements)
        n = len(sorted_measurements)

        return {
            "min_ms": round(sorted_measurements[0], 3),
            "max_ms": round(sorted_measurements[-1], 3),
            "mean_ms": round(statistics.mean(sorted_measurements), 3),
            "median_ms": round(sorted_measurements[n // 2], 3),
            "p95_ms": round(sorted_measurements[int(n * 0.95)], 3),
            "p99_ms": round(sorted_measurements[int(n * 0.99)], 3),
            "std_dev_ms": round(statistics.stdev(sorted_measurements) if n > 1 else 0, 3),
            "samples": n,
        }

    def verify(self, stats: dict[str, float]) -> bool:
        """
        验证结果是否达到目标

        Args:
            stats: 统计结果

        Returns:
            是否通过
        """
        passed = True
        for metric, target in self.targets.items():
            if metric in stats:
                actual = stats[metric]
                if actual > target:
                    passed = False
                    print(f"  ❌ {metric}: {actual:.3f} > {target:.3f}")
                else:
                    print(f"  ✅ {metric}: {actual:.3f} <= {target:.3f}")

        return passed

    def report(self, stats: dict[str, float], passed: bool) -> PerformanceReport:
        """生成测试报告"""
        return PerformanceReport(
            test_name=self.name,
            timestamp=datetime.now().isoformat(),
            results=stats,
            targets=self.targets,
            passed=passed,
            metadata={
                "iterations": len(self.measurements),
            },
        )


def compare_with_libp2p(
    our_stats: dict[str, float],
    libp2p_stats: dict[str, float],
    threshold: float = 0.9,
) -> dict[str, Any]:
    """
    与 go-libp2p 性能对比

    Args:
        our_stats: 我们的测试结果
        libp2p_stats: go-libp2p 参考值
        threshold: 通过阈值 (90%)

    Returns:
        对比结果
    """
    comparison = {}

    for metric, libp2p_value in libp2p_stats.items():
        if metric in our_stats:
            our_value = our_stats[metric]

            # 对于延迟，越小越好
            # 对于吞吐量，越大越好
            # 这里假设所有指标都是"越小越好" (如延迟)
            ratio = our_value / libp2p_value if libp2p_value > 0 else 0

            comparison[metric] = {
                "our_value": round(our_value, 3),
                "libp2p_value": round(libp2p_value, 3),
                "ratio": round(ratio, 3),
                "passed": ratio <= (1 / threshold),  # 我们的值应该在 110% 以内
            }

    return comparison


async def measure_steady_state(
    func: Callable,
    duration: float = 10.0,
    interval: float = 0.1,
) -> list[float]:
    """
    测量稳态性能

    Args:
        func: 要测量的函数
        duration: 测量持续时间
        interval: 采样间隔

    Returns:
        采样结果
    """
    measurements = []
    end_time = time.time() + duration

    while time.time() < end_time:
        start = time.perf_counter()
        if asyncio.iscoroutinefunction(func):
            await func()
        else:
            func()
        measurements.append((time.perf_counter() - start) * 1000)

        await asyncio.sleep(interval)

    return measurements
