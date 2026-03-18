"""
pytest配置和共享fixtures
"""
import asyncio
import os
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """使用默认事件循环策略"""
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
def free_port() -> Generator[int, None, None]:
    """获取可用端口"""
    sock = socket.socket()
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    yield port


@pytest.fixture(scope="session")
def free_ports() -> Generator[dict[str, int], None, None]:
    """获取多个可用端口"""
    ports = {}
    sockets = []
    for name in ["stun", "signaling", "relay", "did"]:
        sock = socket.socket()
        sock.bind(("", 0))
        ports[name] = sock.getsockname()[1]
        sockets.append(sock)

    yield ports

    for sock in sockets:
        sock.close()


@pytest.fixture
def temp_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """临时目录"""
    yield tmp_path


@pytest.fixture
def mock_config() -> dict:
    """测试配置"""
    return {
        "stun_server": {
            "host": "127.0.0.1",
            "port": 3478,
        },
        "signaling_server": {
            "host": "127.0.0.1",
            "port": 8080,
        },
        "relay_server": {
            "host": "127.0.0.1",
            "port": 5000,
        },
        "did_service": {
            "host": "127.0.0.1",
            "port": 4000,
        },
        "ice_timeout": 30,
        "connection_timeout": 60,
    }


@pytest.fixture
def test_device_id() -> str:
    """测试设备ID"""
    return "test-device-001"


@pytest.fixture
def test_peer_id() -> str:
    """测试对等端ID"""
    return "test-peer-001"


# ===== NAT模拟配置 =====

NAT_BEHAVIORS = {
    "full_cone": {
        "name": "Full Cone NAT",
        "description": "外部IP:Port映射后，任何外部主机都可以通过该映射发送数据",
        "filtering": "none",
        "mapping": "endpoint-independent",
    },
    "restricted_cone": {
        "name": "Restricted Cone NAT",
        "description": "只有先前接收过数据的外部主机才能发送",
        "filtering": "endpoint-dependent",
        "mapping": "endpoint-independent",
    },
    "port_restricted": {
        "name": "Port Restricted Cone NAT",
        "description": "IP和Port都必须匹配",
        "filtering": "endpoint-and-port-dependent",
        "mapping": "endpoint-independent",
    },
    "symmetric": {
        "name": "Symmetric NAT",
        "description": "每个目标都有不同的映射",
        "filtering": "endpoint-dependent",
        "mapping": "endpoint-dependent",
    },
}


@pytest.fixture(params=list(NAT_BEHAVIORS.values()))
def nat_behavior(request) -> dict:
    """参数化的NAT行为"""
    return request.param


@pytest.fixture
def nat_combinations() -> list[tuple[str, str]]:
    """NAT穿透测试的组合"""
    combinations = []
    nat_types = list(NAT_BEHAVIORS.keys())
    for client_nat in nat_types:
        for peer_nat in nat_types:
            combinations.append((client_nat, peer_nat))
    return combinations


# ===== Mock服务器 =====

@pytest_asyncio.fixture
async def mock_stun_server(free_port: int) -> AsyncGenerator[dict, None]:
    """模拟STUN服务器"""
    server_info = {
        "host": "127.0.0.1",
        "port": free_port,
    }

    # 实际项目中会启动真实服务器
    yield server_info


@pytest_asyncio.fixture
async def mock_signaling_server(free_port: int) -> AsyncGenerator[dict, None]:
    """模拟信令服务器"""
    server_info = {
        "host": "127.0.0.1",
        "port": free_port,
        "ws_url": f"ws://127.0.0.1:{free_port}",
    }
    yield server_info


@pytest_asyncio.fixture
async def mock_did_service(free_port: int) -> AsyncGenerator[dict, None]:
    """模拟DID服务"""
    service_info = {
        "host": "127.0.0.1",
        "port": free_port,
        "base_url": f"http://127.0.0.1:{free_port}",
    }
    yield service_info


# ===== 测试数据 =====

@pytest.fixture
def sample_stun_request() -> bytes:
    """示例STUN绑定请求"""
    # STUN Binding Request (RFC 5389格式)
    # Type(2) + Length(2) + Magic Cookie(4) + Transaction ID(12)
    # Magic Cookie = 0x2112A442
    return bytes.fromhex("000100002112A4424245464748494A4B4C4E4F50")


@pytest.fixture
def sample_stun_response() -> bytes:
    """示例STUN绑定响应"""
    # STUN Binding Success Response
    return bytes.fromhex("010100042122234242454647")


@pytest.fixture
def sample_ice_candidates() -> list[dict]:
    """示例ICE候选"""
    return [
        {
            "candidate": "candidate:1 1 UDP 2130706431 192.168.1.100 54321 typ host",
            "sdpMid": "0",
            "sdpMLineIndex": 0,
            "type": "host",
        },
        {
            "candidate": "candidate:2 1 UDP 1694498815 203.0.113.1 54322 typ srflx raddr 192.168.1.100 rport 54321",
            "sdpMid": "0",
            "sdpMLineIndex": 0,
            "type": "srflx",
        },
        {
            "candidate": "candidate:3 1 UDP 16777215 198.51.100.1 54323 typ relay raddr 203.0.113.1 rport 54322",
            "sdpMid": "0",
            "sdpMLineIndex": 0,
            "type": "relay",
        },
    ]


@pytest.fixture
def sample_did_document() -> dict:
    """示例DID文档"""
    return {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": "did:example:123456",
        "verificationMethod": [{
            "id": "did:example:123456#key-1",
            "type": "JsonWebKey2020",
            "controller": "did:example:123456",
            "publicKeyJwk": {
                "kty": "EC",
                "crv": "secp256k1",
                "x": "test_x_value",
                "y": "test_y_value",
            }
        }],
        "authentication": ["did:example:123456#key-1"],
        "service": [{
            "id": "did:example:123456#p2p",
            "type": "P2PService",
            "serviceEndpoint": "p2p://example.com/device123"
        }]
    }


# ===== 网络测试工具 =====

@pytest.fixture
def is_port_available() -> callable:
    """检查端口是否可用"""
    def _check(port: int, host: str = "127.0.0.1") -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False
        finally:
            sock.close()
    return _check


@pytest.fixture
def wait_for_port() -> callable:
    """等待端口可用"""
    async def _wait(port: int, host: str = "127.0.0.1", timeout: float = 10.0) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.settimeout(0.1)
                sock.connect((host, port))
                sock.close()
                return True
            except (ConnectionRefusedError, socket.timeout, OSError):
                await asyncio.sleep(0.1)
        return False
    return _wait


# ===== 性能测试工具 =====

@pytest.fixture
def measure_bandwidth() -> callable:
    """测量带宽"""
    async def _measure(data_size: int, duration: float) -> float:
        """
        测量吞吐量
        :param data_size: 传输数据大小(字节)
        :param duration: 持续时间(秒)
        :return: 吞吐量(Mbps)
        """
        return (data_size * 8) / (duration * 1_000_000)
    return _measure


@pytest.fixture
def measure_latency() -> callable:
    """测量延迟"""
    async def _measure(host: str, port: int, samples: int = 10) -> dict:
        """
        测量网络延迟
        :return: {"min": x, "max": y, "avg": z, "jitter": w}
        """
        latencies = []
        for _ in range(samples):
            start = time.time()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                sock.connect((host, port))
                sock.close()
                latencies.append((time.time() - start) * 1000)  # ms
            except Exception:
                pass

        if not latencies:
            return {"min": 0, "max": 0, "avg": 0, "jitter": 0}

        latencies.sort()
        return {
            "min": latencies[0],
            "max": latencies[-1],
            "avg": sum(latencies) / len(latencies),
            "jitter": sum(abs(latencies[i] - latencies[i-1])
                         for i in range(1, len(latencies))) / max(len(latencies) - 1, 1),
        }
    return _measure


# ===== 日志捕获 =====

@pytest.fixture
def log_capture(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """捕获日志"""
    caplog.set_level(logging.DEBUG)
    return caplog


import logging
