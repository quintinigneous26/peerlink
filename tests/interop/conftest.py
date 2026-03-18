"""
互操作性测试配置

提供测试共享的 fixtures 和配置。
"""

import asyncio
import os
import pytest
import socket
from typing import Optional, List, Tuple
from pathlib import Path


# ==================== 测试配置 ====================

def pytest_addoption(parser):
    """添加 pytest 命令行选项"""
    parser.addoption(
        "--run-interop-tests",
        action="store_true",
        default=False,
        help="运行需要外部 libp2p 节点的互操作测试"
    )
    parser.addoption(
        "--go-libp2p-host",
        action="store",
        default="127.0.0.1",
        help="go-libp2p 测试节点主机"
    )
    parser.addoption(
        "--go-libp2p-port",
        action="store",
        default=12345,
        type=int,
        help="go-libp2p 测试节点端口"
    )
    parser.addoption(
        "--js-libp2p-host",
        action="store",
        default="127.0.0.1",
        help="js-libp2p 测试节点主机"
    )
    parser.addoption(
        "--js-libp2p-port",
        action="store",
        default=12346,
        type=int,
        help="js-libp2p 测试节点端口"
    )


def pytest_configure(config):
    """配置 pytest"""
    config.addinivalue_line(
        "markers", "interop: 标记需要外部节点的互操作测试"
    )
    config.addinivalue_line(
        "markers", "go_libp2p: 标记 go-libp2p 互操作测试"
    )
    config.addinivalue_line(
        "markers", "js_libp2p: 标记 js-libp2p 互操作测试"
    )
    config.addinivalue_line(
        "markers", "browser: 标记浏览器互操作测试"
    )


# ==================== Fixtures ====================

@pytest.fixture(scope="session")
def interop_test_config():
    """互操作测试配置"""
    return {
        "go_libp2p": {
            "host": os.getenv("GO_LIBP2P_HOST", "127.0.0.1"),
            "port": int(os.getenv("GO_LIBP2P_PORT", "12345")),
        },
        "js_libp2p": {
            "host": os.getenv("JS_LIBP2P_HOST", "127.0.0.1"),
            "port": int(os.getenv("JS_LIBP2P_PORT", "12346")),
        },
        "timeout": float(os.getenv("INTEROP_TIMEOUT", "10.0")),
    }


@pytest.fixture
async def free_port():
    """获取一个可用端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture
def test_data_dir():
    """获取测试数据目录"""
    return Path(__file__).parent / "data"


@pytest.fixture
def test_results_dir():
    """获取测试结果目录"""
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    return results_dir


# ==================== 辅助类 ====================

class MockConnection:
    """模拟连接"""

    def __init__(self):
        self._read_buffer = asyncio.Queue()
        self._write_buffer = []
        self._closed = False

    async def read(self, n: int = -1) -> bytes:
        if self._closed:
            raise ConnectionError("Connection closed")
        return await self._read_buffer.get()

    async def write(self, data: bytes) -> int:
        if self._closed:
            raise ConnectionError("Connection closed")
        self._write_buffer.append(data)
        return len(data)

    async def close(self) -> None:
        self._closed = True

    def is_closed(self) -> bool:
        return self._closed

    def feed_data(self, data: bytes):
        """向读缓冲区添加数据"""
        self._read_buffer.put_nowait(data)

    def get_written(self) -> List[bytes]:
        """获取已写入的数据"""
        return self._write_buffer


class StreamReaderWriter:
    """流读写器包装"""

    def __init__(self, reader, writer):
        self._reader = reader
        self._writer = writer

    async def read(self, n: int = -1) -> bytes:
        return await self._reader.read(n)

    async def write(self, data: bytes) -> int:
        self._writer.write(data)
        await self._writer.drain()
        return len(data)

    async def close(self) -> None:
        self._writer.close()
        await self._writer.wait_closed()

    def is_closing(self) -> bool:
        return self._writer.is_closing()
