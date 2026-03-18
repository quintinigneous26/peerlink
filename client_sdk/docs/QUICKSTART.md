# P2P SDK 快速开始指南

## 安装

### 从 PyPI 安装

```bash
pip install p2p-sdk
```

### 从 Conda 安装

```bash
conda install -c conda-forge p2p-sdk
```

### 从源码安装

```bash
git clone https://github.com/p2p-platform/python-sdk.git
cd python-sdk
pip install -e .
```

## 基础使用

### 1. 创建客户端

```python
import asyncio
from p2p_sdk import P2PClient

async def main():
    # 创建客户端实例
    client = P2PClient(
        did="device-001",
        signaling_server="localhost",
        signaling_port=8443
    )

    # 初始化（NAT 检测、连接信令服务器）
    await client.initialize()

    print(f"NAT Type: {client.nat_type}")
    print(f"Local Address: {client.local_address}")

asyncio.run(main())
```

### 2. 连接到对等设备

```python
async def connect_to_peer():
    client = P2PClient(did="device-001")
    await client.initialize()

    # 连接到对等设备
    success = await client.connect("device-002")

    if success:
        print("Connected successfully!")
    else:
        print("Connection failed")

    await client.close()
```

### 3. 发送和接收数据

```python
from p2p_sdk import P2PClient, ChannelType

async def send_receive_data():
    client = P2PClient(did="device-001")
    await client.initialize()

    if await client.connect("device-002"):
        # 创建数据通道
        channel = client.create_channel(ChannelType.DATA)

        # 发送数据
        await client.send_data(channel, b"Hello, peer!")

        # 接收数据
        data = await client.recv_data(channel, timeout=10.0)
        print(f"Received: {data.decode()}")

    await client.close()
```

## 高级功能

### 多通道通信

```python
from p2p_sdk import P2PClient, ChannelType

async def multi_channel_example():
    client = P2PClient(did="device-001")
    await client.initialize()

    if await client.connect("device-002"):
        # 创建多个通道
        control_ch = client.create_channel(ChannelType.CONTROL)
        data_ch = client.create_channel(ChannelType.DATA)
        video_ch = client.create_channel(ChannelType.VIDEO, priority=10)

        # 在不同通道上发送数据
        await client.send_data(control_ch, b"control message")
        await client.send_data(data_ch, b"data payload")
        await client.send_data(video_ch, b"video frame")

    await client.close()
```

### 事件处理

```python
async def event_handling_example():
    client = P2PClient(did="device-001")

    # 注册事件处理器
    @client.on_connected
    async def on_connected():
        print("Connection established!")

    @client.on_disconnected
    async def on_disconnected():
        print("Connection lost")

    @client.on_data
    async def on_data(channel_id: int, data: bytes):
        print(f"Received {len(data)} bytes on channel {channel_id}")

    @client.on_error
    async def on_error(error: Exception):
        print(f"Error occurred: {error}")

    await client.initialize()
    await client.connect("device-002")

    # 保持连接
    await asyncio.sleep(60)
    await client.close()
```

### 自定义配置

```python
from p2p_sdk import P2PClient

async def custom_config_example():
    client = P2PClient(
        did="device-001",
        signaling_server="signal.example.com",
        signaling_port=8443,
        stun_server="stun.example.com",
        stun_port=3478,
        relay_server="relay.example.com",
        relay_port=5000,
        connection_timeout=30.0,
        punch_timeout=10.0,
        keepalive_interval=5.0,
        max_retries=3,
        auto_relay=True
    )

    await client.initialize()
    # ... 使用客户端
    await client.close()
```

## NAT 类型检测

```python
from p2p_sdk import detect_nat_type, NATType

async def detect_nat():
    nat_type = await detect_nat_type(
        stun_server="stun.l.google.com",
        stun_port=19302
    )

    if nat_type == NATType.SYMMETRIC:
        print("Symmetric NAT detected - relay required")
    elif nat_type in [NATType.FULL_CONE, NATType.RESTRICTED_CONE]:
        print("NAT type supports direct P2P")
    else:
        print(f"NAT Type: {nat_type}")
```

## 错误处理

```python
from p2p_sdk import (
    P2PClient,
    P2PError,
    ConnectionError,
    NATDetectionError,
    RelayError,
    TimeoutError
)

async def error_handling_example():
    client = P2PClient(did="device-001")

    try:
        await client.initialize()
        await client.connect("device-002")
    except NATDetectionError as e:
        print(f"NAT detection failed: {e}")
    except ConnectionError as e:
        print(f"Connection failed: {e}")
    except TimeoutError as e:
        print(f"Operation timed out: {e}")
    except P2PError as e:
        print(f"P2P error: {e}")
    finally:
        await client.close()
```

## 最佳实践

### 1. 资源管理

始终使用 try-finally 或 async with 确保资源清理：

```python
async def resource_management():
    client = P2PClient(did="device-001")
    try:
        await client.initialize()
        # ... 使用客户端
    finally:
        await client.close()
```

### 2. 超时设置

为所有阻塞操作设置合理的超时：

```python
# 连接超时
client = P2PClient(did="device-001", connection_timeout=30.0)

# 接收超时
data = await client.recv_data(channel, timeout=10.0)
```

### 3. 错误重试

实现指数退避重试策略：

```python
async def connect_with_retry(client, peer_did, max_retries=3):
    for attempt in range(max_retries):
        try:
            if await client.connect(peer_did):
                return True
        except ConnectionError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    return False
```

### 4. 日志记录

启用日志以便调试：

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("p2p_sdk")
logger.setLevel(logging.DEBUG)
```

### 5. 网络状态监控

监控连接状态并实现自动重连：

```python
async def monitor_connection(client):
    @client.on_disconnected
    async def on_disconnected():
        print("Connection lost, attempting reconnect...")
        await asyncio.sleep(5)
        await client.connect(peer_did)
```

## 性能优化

### 1. 通道优先级

为不同类型的数据设置优先级：

```python
# 高优先级通道（控制消息）
control_ch = client.create_channel(ChannelType.CONTROL, priority=10)

# 中优先级通道（视频）
video_ch = client.create_channel(ChannelType.VIDEO, priority=5)

# 低优先级通道（数据）
data_ch = client.create_channel(ChannelType.DATA, priority=1)
```

### 2. 批量发送

批量发送小消息以减少开销：

```python
# 不推荐：多次小消息
for i in range(100):
    await client.send_data(channel, f"msg{i}".encode())

# 推荐：批量发送
batch = b"".join(f"msg{i}".encode() for i in range(100))
await client.send_data(channel, batch)
```

### 3. 缓冲区大小

根据数据量调整缓冲区：

```python
# 大数据传输时增加缓冲区
client = P2PClient(
    did="device-001",
    recv_buffer_size=65536  # 64KB
)
```

## 故障排查

### 连接失败

1. 检查 NAT 类型：
```python
print(f"NAT Type: {client.nat_type}")
```

2. 验证信令服务器连接：
```python
if not client.is_signaling_connected:
    print("Signaling server not connected")
```

3. 启用详细日志：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 性能问题

1. 检查网络延迟：
```python
latency = await client.measure_latency()
print(f"Latency: {latency}ms")
```

2. 监控数据速率：
```python
stats = client.get_statistics()
print(f"Send rate: {stats['send_rate']} bytes/s")
print(f"Recv rate: {stats['recv_rate']} bytes/s")
```

## 更多示例

完整示例代码请参见 `examples/` 目录：

- `basic_usage.py` - 基础 P2P 连接
- `multi_channel.py` - 多通道通信
- `file_transfer.py` - 文件传输
- `video_streaming.py` - 视频流传输

## 支持

- 文档：https://github.com/p2p-platform/python-sdk#readme
- 问题反馈：https://github.com/p2p-platform/python-sdk/issues
- 讨论：https://github.com/p2p-platform/python-sdk/discussions
