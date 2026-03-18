# P2P SDK 最佳实践指南

## 1. 资源管理

### 1.1 始终清理资源

```python
# 推荐：使用 try-finally
async def good_example():
    client = P2PClient(did="device-001")
    try:
        await client.initialize()
        await client.connect("peer")
        # ... 使用客户端
    finally:
        await client.close()

# 不推荐：忘记清理
async def bad_example():
    client = P2PClient(did="device-001")
    await client.initialize()
    await client.connect("peer")
    # 忘记调用 close()
```

### 1.2 使用上下文管理器（如果支持）

```python
# 未来版本可能支持
async with P2PClient(did="device-001") as client:
    await client.initialize()
    await client.connect("peer")
    # 自动清理
```

## 2. 错误处理

### 2.1 捕获特定异常

```python
from p2p_sdk import (
    P2PClient,
    ConnectionError,
    NATDetectionError,
    TimeoutError
)

async def handle_errors():
    client = P2PClient(did="device-001")
    try:
        await client.initialize()
    except NATDetectionError:
        # NAT 检测失败，可能需要手动配置
        print("NAT detection failed, using relay")
        client.auto_relay = True
    except ConnectionError:
        # 连接失败，重试或通知用户
        print("Connection failed")
    except TimeoutError:
        # 超时，可能需要增加超时时间
        print("Operation timed out")
```

### 2.2 实现重试逻辑

```python
async def connect_with_retry(client, peer_did, max_retries=3):
    """指数退避重试"""
    for attempt in range(max_retries):
        try:
            if await client.connect(peer_did):
                return True
        except ConnectionError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"Retry {attempt + 1}/{max_retries} in {wait_time}s")
                await asyncio.sleep(wait_time)
            else:
                raise
    return False
```

## 3. 性能优化

### 3.1 通道优先级

为不同类型的数据设置合适的优先级：

```python
# 高优先级：控制消息
control_ch = client.create_channel(ChannelType.CONTROL, priority=10)

# 中优先级：实时音视频
video_ch = client.create_channel(ChannelType.VIDEO, priority=7)
audio_ch = client.create_channel(ChannelType.AUDIO, priority=8)

# 低优先级：文件传输
data_ch = client.create_channel(ChannelType.DATA, priority=3)
```

### 3.2 批量发送

```python
# 不推荐：多次小消息
async def send_many_small():
    for i in range(1000):
        await client.send_data(channel, f"msg{i}".encode())

# 推荐：批量发送
async def send_batch():
    messages = [f"msg{i}".encode() for i in range(1000)]
    batch = b"\n".join(messages)
    await client.send_data(channel, batch)
```

### 3.3 缓冲区调优

根据数据量调整缓冲区大小：

```python
# 小数据量（控制消息）
client = P2PClient(did="device-001", recv_buffer_size=4096)

# 中等数据量（一般数据）
client = P2PClient(did="device-001", recv_buffer_size=8192)

# 大数据量（视频流）
client = P2PClient(did="device-001", recv_buffer_size=131072)  # 128KB
```

### 3.4 并发处理

使用 asyncio 并发处理多个连接：

```python
async def handle_multiple_peers():
    clients = [
        P2PClient(did=f"device-{i}")
        for i in range(10)
    ]

    # 并发初始化
    await asyncio.gather(*[
        client.initialize() for client in clients
    ])

    # 并发连接
    await asyncio.gather(*[
        client.connect(f"peer-{i}") for i, client in enumerate(clients)
    ])
```

## 4. 网络适��

### 4.1 NAT 类型处理

根据 NAT 类型选择策略：

```python
async def adaptive_connection(client, peer_did):
    await client.initialize()

    if client.nat_type == NATType.SYMMETRIC:
        # 对称 NAT，直接使用中继
        print("Using relay for symmetric NAT")
        client.auto_relay = True
    elif client.nat_type in [NATType.FULL_CONE, NATType.RESTRICTED_CONE]:
        # 锥形 NAT，尝试直连
        print("Attempting direct P2P")
        client.auto_relay = False
    else:
        # 其他情况，启用自动回退
        print("Using auto relay fallback")
        client.auto_relay = True

    await client.connect(peer_did)
```

### 4.2 网络状态监控

监控连接状态并自动重连：

```python
class ConnectionManager:
    def __init__(self, client: P2PClient, peer_did: str):
        self.client = client
        self.peer_did = peer_did
        self.reconnect_task = None

    async def start(self):
        @self.client.on_disconnected
        async def on_disconnected():
            print("Connection lost, scheduling reconnect...")
            self.reconnect_task = asyncio.create_task(
                self._reconnect()
            )

        await self.client.initialize()
        await self.client.connect(self.peer_did)

    async def _reconnect(self):
        """自动重连逻辑"""
        max_retries = 5
        for attempt in range(max_retries):
            await asyncio.sleep(2 ** attempt)
            try:
                if await self.client.connect(self.peer_did):
                    print("Reconnected successfully")
                    return
            except Exception as e:
                print(f"Reconnect attempt {attempt + 1} failed: {e}")

        print("Failed to reconnect after max retries")
```

### 4.3 超时配置

根据网络条件调整超时：

```python
# 良好网络
client = P2PClient(
    did="device-001",
    connection_timeout=10.0,
    punch_timeout=5.0
)

# 一般网络
client = P2PClient(
    did="device-001",
    connection_timeout=30.0,
    punch_timeout=10.0
)

# 差网络
client = P2PClient(
    did="device-001",
    connection_timeout=60.0,
    punch_timeout=20.0
)
```

## 5. 安全实践

### 5.1 设备 ID 管理

```python
import uuid

# 生成唯一设备 ID
device_id = str(uuid.uuid4())

# 持久化存储
with open("device_id.txt", "w") as f:
    f.write(device_id)

# 读取存储的 ID
with open("device_id.txt", "r") as f:
    device_id = f.read().strip()

client = P2PClient(did=device_id)
```

### 5.2 数据加密

在应用层加密敏感数据：

```python
from cryptography.fernet import Fernet

class SecureClient:
    def __init__(self, client: P2PClient, key: bytes):
        self.client = client
        self.cipher = Fernet(key)

    async def send_encrypted(self, channel: int, data: bytes):
        encrypted = self.cipher.encrypt(data)
        await self.client.send_data(channel, encrypted)

    async def recv_encrypted(self, channel: int) -> bytes:
        encrypted = await self.client.recv_data(channel)
        return self.cipher.decrypt(encrypted)
```

### 5.3 访问控制

实现设备白名单：

```python
class WhitelistClient:
    def __init__(self, client: P2PClient, allowed_peers: set[str]):
        self.client = client
        self.allowed_peers = allowed_peers

    async def connect(self, peer_did: str) -> bool:
        if peer_did not in self.allowed_peers:
            raise ValueError(f"Peer {peer_did} not in whitelist")
        return await self.client.connect(peer_did)
```

## 6. 日志和调试

### 6.1 启用日志

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 调试模式
logger = logging.getLogger("p2p_sdk")
logger.setLevel(logging.DEBUG)
```

### 6.2 性能监控

```python
async def monitor_performance(client: P2PClient):
    """定期监控性能指标"""
    while client.is_connected:
        stats = client.get_statistics()
        print(f"Send rate: {stats['send_rate']:.2f} bytes/s")
        print(f"Recv rate: {stats['recv_rate']:.2f} bytes/s")
        print(f"Packet loss: {stats['packet_loss']:.2%}")
        await asyncio.sleep(5)
```

### 6.3 错误追踪

```python
import traceback

@client.on_error
async def on_error(error: Exception):
    print(f"Error occurred: {error}")
    print("Traceback:")
    traceback.print_exc()
```

## 7. 测试

### 7.1 单元测试

```python
import pytest
from p2p_sdk import P2PClient

@pytest.mark.asyncio
async def test_client_initialization():
    client = P2PClient(did="test-device")
    try:
        await client.initialize()
        assert client.nat_type is not None
        assert client.local_address is not None
    finally:
        await client.close()
```

### 7.2 集成测试

```python
@pytest.mark.asyncio
async def test_peer_connection():
    client1 = P2PClient(did="device-1")
    client2 = P2PClient(did="device-2")

    try:
        await asyncio.gather(
            client1.initialize(),
            client2.initialize()
        )

        # 模拟连接
        success = await client1.connect("device-2")
        assert success

        # 测试数据传输
        channel = client1.create_channel(ChannelType.DATA)
        await client1.send_data(channel, b"test")

    finally:
        await asyncio.gather(
            client1.close(),
            client2.close()
        )
```

### 7.3 压力测试

```python
async def stress_test():
    """压力测试：大量并发连接"""
    num_clients = 100
    clients = [
        P2PClient(did=f"device-{i}")
        for i in range(num_clients)
    ]

    try:
        # 并发初始化
        await asyncio.gather(*[
            client.initialize() for client in clients
        ])

        # 测试连接
        start_time = time.time()
        results = await asyncio.gather(*[
            client.connect(f"peer-{i}")
            for i, client in enumerate(clients)
        ], return_exceptions=True)

        elapsed = time.time() - start_time
        success_count = sum(1 for r in results if r is True)

        print(f"Connected {success_count}/{num_clients} in {elapsed:.2f}s")

    finally:
        await asyncio.gather(*[
            client.close() for client in clients
        ])
```

## 8. 部署

### 8.1 生产环境配置

```python
import os

# 从环境变量读取配置
client = P2PClient(
    did=os.getenv("DEVICE_ID"),
    signaling_server=os.getenv("SIGNALING_SERVER", "localhost"),
    signaling_port=int(os.getenv("SIGNALING_PORT", "8443")),
    stun_server=os.getenv("STUN_SERVER", "stun.l.google.com"),
    stun_port=int(os.getenv("STUN_PORT", "19302")),
    relay_server=os.getenv("RELAY_SERVER", "localhost"),
    relay_port=int(os.getenv("RELAY_PORT", "5000")),
)
```

### 8.2 容器化

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### 8.3 健康检查

```python
async def health_check(client: P2PClient) -> bool:
    """健康检查"""
    try:
        if not client.is_signaling_connected:
            return False

        # 测试延迟
        latency = await client.measure_latency()
        if latency > 1000:  # 1秒
            return False

        return True
    except Exception:
        return False
```

## 9. 常见问题

### 9.1 连接失败

**问题：** 无法建立 P2P 连接

**解决方案：**
1. 检查 NAT 类型
2. 启用自动中继回退
3. 增加超时时间
4. 检查防火墙设置

```python
# 诊断脚本
async def diagnose_connection(client: P2PClient):
    await client.initialize()
    print(f"NAT Type: {client.nat_type}")
    print(f"Local Address: {client.local_address}")
    print(f"Public Address: {client.public_address}")
    print(f"Signaling Connected: {client.is_signaling_connected}")
```

### 9.2 性能问题

**问题：** 数据传输速度慢

**解决方案：**
1. 增加缓冲区大小
2. 使用批量发送
3. 调整通道优先级
4. 检查网络延迟

```python
# 性能诊断
async def diagnose_performance(client: P2PClient):
    stats = client.get_statistics()
    latency = await client.measure_latency()

    print(f"Latency: {latency}ms")
    print(f"Send rate: {stats['send_rate']} bytes/s")
    print(f"Packet loss: {stats['packet_loss']:.2%}")
```

### 9.3 内存泄漏

**问题：** 长时间运行后内存增长

**解决方案：**
1. 确保调用 `close()`
2. 关闭不用的通道
3. 定期清理缓冲区

```python
# 资源清理
async def cleanup_resources(client: P2PClient):
    # 关闭所有通道
    for channel_id in client.get_channels():
        client.close_channel(channel_id)

    # 关闭客户端
    await client.close()
```

## 10. 总结

遵循这些最佳实践可以帮助你：

1. **提高可靠性** - 正确的错误处理和重试逻辑
2. **优化性能** - 合理的缓冲区和批量处理
3. **增强安全性** - 数据加密和访问控制
4. **简化调试** - 完善的日志和监控
5. **便于维护** - 清晰的代码结构和测试

记住：

- 始终清理资源
- 捕获特定异常
- 根据网络条件调整配置
- 监控性能指标
- 编写测试用例
