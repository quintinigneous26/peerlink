"""
传输层抽象基类

定义传输层的统一接口，所有传输实现都必须遵循此接口。
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any
import asyncio


class TransportError(Exception):
    """传输层错误基类"""
    pass


class ConnectionError(TransportError):
    """连接错误"""
    pass


class ListenerError(TransportError):
    """监听器错误"""
    pass


class Connection(ABC):
    """
    连接抽象基类

    表示一个已建立的连接，提供数据传输功能。
    """

    @abstractmethod
    async def read(self, n: int = -1) -> bytes:
        """
        读取数据

        Args:
            n: 读取字节数，-1 表示读取所有可用数据

        Returns:
            读取的数据
        """
        pass

    @abstractmethod
    async def write(self, data: bytes) -> int:
        """
        写入数据

        Args:
            data: 要写入的数据

        Returns:
            写入的字节数
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""
        pass

    @abstractmethod
    def is_closed(self) -> bool:
        """检查连接是否已关闭"""
        pass

    @property
    @abstractmethod
    def remote_address(self) -> Optional[tuple]:
        """获取远程地址"""
        pass

    @property
    @abstractmethod
    def local_address(self) -> Optional[tuple]:
        """获取本地地址"""
        pass


class Listener(ABC):
    """
    监听器抽象基类

    表示一个正在监听的传输端点。
    """

    @abstractmethod
    async def accept(self) -> Connection:
        """
        接受传入连接

        Returns:
            新接受的连接
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭监听器"""
        pass

    @abstractmethod
    def is_closed(self) -> bool:
        """检查监听器是否已关闭"""
        pass

    @property
    @abstractmethod
    def addresses(self) -> List[tuple]:
        """获取监听地址列表"""
        pass


class Transport(ABC):
    """
    传输层抽象基类

    定义传输层的统一接口，所有传输实现都必须遵循。
    """

    @abstractmethod
    async def dial(self, addr: str) -> Connection:
        """
        建立到指定地址的连接

        Args:
            addr: 目标地址（格式取决于传输类型）

        Returns:
            建立的连接

        Raises:
            ConnectionError: 连接失败
        """
        pass

    @abstractmethod
    async def listen(self, addr: str) -> Listener:
        """
        在指定地址开始监听

        Args:
            addr: 监听地址（格式取决于传输类型）

        Returns:
            监听器实例

        Raises:
            ListenerError: 监听失败
        """
        pass

    @abstractmethod
    def protocols(self) -> List[str]:
        """
        返回支持的协议列表

        Returns:
            协议ID列表
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭传输层，释放所有资源"""
        pass
