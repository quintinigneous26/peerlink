"""
模糊测试工具函数

提供通用的模糊测试辅助功能
"""
import asyncio
import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar, Generic

from hypothesis import settings, Verbosity
import pytest


T = TypeVar('T')


@dataclass
class FuzzReport:
    """模糊测试报告"""
    test_name: str
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    errors: list[dict[str, Any]]
    coverage: Optional[float]
    duration_sec: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Optional[Path] = None):
        """保存报告到文件"""
        if path is None:
            path = Path(f"reports/fuzz/{self.test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class FuzzTestCase(Generic[T]):
    """模糊测试用例包装器"""

    def __init__(
        self,
        name: str,
        test_func: Callable[[T], Any],
        strategy: Optional[Callable] = None,
    ):
        """
        初始化测试用例

        Args:
            name: 测试名称
            test_func: 测试函数
            strategy: hypothesis 策略
        """
        self.name = name
        self.test_func = test_func
        self.strategy = strategy
        self.passed = 0
        self.failed = 0
        self.errors: list[dict[str, Any]] = []
        self.start_time: Optional[float] = None

    def run(self, input_data: T) -> bool:
        """
        运行单个测试用例

        Args:
            input_data: 输入数据

        Returns:
            是否通过
        """
        try:
            result = self.test_func(input_data)
            self.passed += 1
            return True
        except AssertionError as e:
            self.failed += 1
            self.errors.append({
                "input": str(input_data),
                "error": str(e),
            })
            return False
        except Exception as e:
            self.failed += 1
            self.errors.append({
                "input": str(input_data),
                "error": f"Unexpected error: {e}",
            })
            return False

    def start(self):
        """开始测试计时"""
        self.start_time = time.time()

    def finish(self) -> float:
        """完成测试，返回耗时"""
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time


def timeout(seconds: float) -> Callable:
    """
    超时装饰器

    用于防止模糊测试中的无限循环

    Args:
        seconds: 超时时间（秒）

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")

        def sync_wrapper(*args, **kwargs):
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")

            if hasattr(signal, 'SIGALRM'):  # Unix only
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(seconds))
                try:
                    result = func(*args, **kwargs)
                finally:
                    signal.alarm(0)
                return result
            else:
                # Fallback for Windows
                return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def memory_limit(max_mb: int) -> Callable:
    """
    内存限制装饰器

    用于检测模糊测试中的内存泄漏

    Args:
        max_mb: 最大内存使用（MB）

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                import psutil
                import os

                process = psutil.Process(os.getpid())
                initial_memory = process.memory_info().rss / 1_000_000  # MB

                result = func(*args, **kwargs)

                peak_memory = process.memory_info().rss / 1_000_000  # MB
                memory_used = peak_memory - initial_memory

                if memory_used > max_mb:
                    raise MemoryError(f"Memory limit exceeded: {memory_used:.2f}MB > {max_mb}MB")

                return result

            except ImportError:
                # psutil 不可用，跳过检查
                return func(*args, **kwargs)

        return wrapper

    return decorator


class FuzzSettings:
    """
    模糊测试配置

    提供预设的 hypothesis 配置
    """

    @staticmethod
    def fast() -> settings:
        """快速测试配置 (开发时使用)"""
        return settings(
            max_examples=50,
            deadline=1000,
            phases=[hypothesis.Phase.generate],  # 只生成，不缩减
        )

    @staticmethod
    def standard() -> settings:
        """标准测试配置"""
        return settings(
            max_examples=200,
            deadline=2000,
        )

    @staticmethod
    def thorough() -> settings:
        """彻底测试配置 (CI/发布前使用)"""
        return settings(
            max_examples=1000,
            deadline=5000,
            verbosity=Verbosity.verbose,
        )

    @staticmethod
    def security() -> settings:
        """安全测试配置"""
        return settings(
            max_examples=500,
            deadline=10000,
            # 禁用缩减以获得更多样化的输入
            phases=[hypothesis.Phase.generate],
        )


# 导入 hypothesis
import hypothesis
