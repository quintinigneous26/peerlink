# P2P SDK API 参考文档

## 核心类

### P2PClient

主客户端类，用于 P2P 通信。

#### 构造函数

```python
P2PClient(
    did: str,
    signaling_server: str = "localhost",
    signaling_port: int = 8443,
    stun_server: str = "stun.l.google.com",
    stun_port: int = 19302,
    relay_server: str = "localhost",
    relay_port: int = 5000,
    local_port: int = 0,
    connection_timeout: float = 30.0,
    punch_timeout: float = 10.0,
    keepalive_interval: float = 5.0,
    max_retries: int = 3,
    auto_relay: bool = True,
    recv_buffer_size: int = 8192
)
```

**参数：**

- `did` (str): 设备唯一标识符
- `signaling_server` (str): 信令服务器地址
- `signaling_port` (int): 信令服务器端口
- `stun_server` (str): STUN 服务器地址
- `stun_port` (int): STUN 服务器端口
- `relay_server` (str): 中继服务器地址
- `relay_port` (int): 中继服务器端口
- `local_port` (int): 本地 UDP 端口（0 表示自动分配）
- `connection_timeout` (float): 连接超时时间（秒）
- `punch_timeout` (float): 打洞超时时间（秒）
- `keepalive_interval` (float): 保活间隔（秒）
- `max_retries` (int): 最大重试次数
- `auto_relay` (bool): 是否自动回退到中继
- `recv_buffer_size` (int): 接收缓冲区大小（字节）

#### 方法

##### async initialize()

初始化客户端（NAT 检测、连接信令服务器）。

```python
await client.initialize()
```

**返回：** None

**异常：**
- `NATDetectionError`: NAT 检测失败
- `ConnectionError`: 信令服务器连接失败

##### async detect_nat() -> NATType

检测 NAT 类型。

```python
nat_type = await client.detect_nat()
```

**返回：** `NATType` 枚举值

**异常：**
- `NATDetectionError`: NAT 检测失败

##### async connect(did: str) -> bool

连接到对等设备。

```python
success = await client.connect("peer-device-id")
```

**参数：**
- `did` (str): 对等设备 ID

**返回：** bool - 连接是否成功

**异常：**
- `ConnectionError`: 连接失败
- `TimeoutError`: 连接超时

##### async send_data(channel: int, data: bytes) -> None

在指定通道上发送数据。

```python
await client.send_data(channel_id, b"Hello, peer!")
```

**参数：**
- `channel` (int): 通道 ID
- `data` (bytes): 要发送的数据

**返回：** None

**异常：**
- `ConnectionError`: 连接已断开
- `ValueError`: 通道不存在

##### async recv_data(channel: int, timeout: float = None) -> bytes

从指定通道接收数据。

```python
data = await client.recv_data(channel_id, timeout=10.0)
```

**参数：**
- `channel` (int): 通道 ID
- `timeout` (float, optional): 超时时间（秒），None 表示无限等待

**返回：** bytes - 接收到的数据

**异常：**
- `TimeoutError`: 接收超时
- `ConnectionError`: 连接已断开
- `ValueError`: 通道不存在

##### create_channel(channel_type: ChannelType, reliable: bool = True, priority: int = 0) -> int

创建新的数据通道。

```python
channel_id = client.create_channel(ChannelType.DATA, reliable=True, priority=5)
```

**参数：**
- `channel_type` (ChannelType): 通道类型
- `reliable` (bool): 是否可靠传输
- `priority` (int): 通道优先级（0-10，数值越大优先级越高）

**返回：** int - 通道 ID

**异常：**
- `ValueError`: 参数无效

##### close_channel(channel_id: int) -> None

关闭数据通道。

```python
client.close_channel(channel_id)
```

**参数：**
- `channel_id` (int): 通道 ID

**返回：** None

##### async close() -> None

关闭连接并清理资源。

```python
await client.close()
```

**返回：** None

##### async measure_latency() -> float

测量到对等设备的延迟。

```python
latency_ms = await client.measure_latency()
```

**返回：** float - 延迟时间（毫秒）

**异常：**
- `ConnectionError`: 连接已断开
- `TimeoutError`: 测量超时

##### get_statistics() -> dict

获取连接统计信息。

```python
stats = client.get_statistics()
print(f"Bytes sent: {stats['bytes_sent']}")
print(f"Bytes received: {stats['bytes_received']}")
```

**返回：** dict - 统计信息字典

```python
{
    "bytes_sent": int,
    "bytes_received": int,
    "packets_sent": int,
    "packets_received": int,
    "send_rate": float,  # bytes/s
    "recv_rate": float,  # bytes/s
    "packet_loss": float,  # 0.0-1.0
    "connection_time": float,  # seconds
}
```

#### 属性

##### nat_type: NATType

当前检测到的 NAT 类型。

```python
print(f"NAT Type: {client.nat_type}")
```

##### local_address: tuple[str, int]

本地地址（IP, 端口）。

```python
ip, port = client.local_address
```

##### public_address: tuple[str, int]

公网地址（IP, 端口）。

```python
ip, port = client.public_address
```

##### is_connected: bool

是否已连接到对等设备。

```python
if client.is_connected:
    print("Connected")
```

##### is_signaling_connected: bool

是否已连接到信令服务器。

```python
if client.is_signaling_connected:
    print("Signaling connected")
```

##### peer_did: str | None

当前连接的对等设备 ID。

```python
if client.peer_did:
    print(f"Connected to: {client.peer_did}")
```

#### 事件处理器

##### @client.on_connected

连接建立时触发。

```python
@client.on_connected
async def on_connected():
    print("Connection established!")
```

##### @client.on_disconnected

连接断开时触发。

```python
@client.on_disconnected
async def on_disconnected():
    print("Connection lost")
```

##### @client.on_data

接收到数据时触发。

```python
@client.on_data
async def on_data(channel_id: int, data: bytes):
    print(f"Received {len(data)} bytes on channel {channel_id}")
```

**参数：**
- `channel_id` (int): 通道 ID
- `data` (bytes): 接收到的数据

##### @client.on_error

发生错误时触发。

```python
@client.on_error
async def on_error(error: Exception):
    print(f"Error: {error}")
```

**参数：**
- `error` (Exception): 错误对象

##### @client.on_channel_opened

通道打开时触发。

```python
@client.on_channel_opened
async def on_channel_opened(channel_id: int, channel_type: ChannelType):
    print(f"Channel {channel_id} opened: {channel_type}")
```

**参数：**
- `channel_id` (int): 通道 ID
- `channel_type` (ChannelType): 通道类型

##### @client.on_channel_closed

通道关闭时触发。

```python
@client.on_channel_closed
async def on_channel_closed(channel_id: int):
    print(f"Channel {channel_id} closed")
```

**参数：**
- `channel_id` (int): 通道 ID

## 枚举类型

### ChannelType

数据通道类型。

```python
class ChannelType(Enum):
    CONTROL = 0    # 控制/信令通道
    DATA = 1       # 通用数据通道
    VIDEO = 2      # 视频流
    AUDIO = 3      # 音频流
    CUSTOM = 4     # 自定义应用通道
```

### NATType

NAT 类型。

```python
class NATType(Enum):
    PUBLIC_IP = 0              # 无 NAT，公网 IP
    FULL_CONE = 1              # 完全锥形 NAT
    RESTRICTED_CONE = 2        # 限制锥形 NAT
    PORT_RESTRICTED_CONE = 3   # 端口限制锥形 NAT
    SYMMETRIC = 4              # 对称 NAT（需要中继）
    UNKNOWN = 5                # 无法检测
    BLOCKED = 6                # UDP 被阻止
```

## 异常类

### P2PError

所有 P2P SDK 异常的基类。

```python
class P2PError(Exception):
    pass
```

### ConnectionError

连接相关错误。

```python
class ConnectionError(P2PError):
    pass
```

### NATDetectionError

NAT 检测失败。

```python
class NATDetectionError(P2PError):
    pass
```

### RelayError

中继服务器错误。

```python
class RelayError(P2PError):
    pass
```

### TimeoutError

操作超时。

```python
class TimeoutError(P2PError):
    pass
```

## 工具函数

### async detect_nat_type(stun_server: str, stun_port: int) -> NATType

独立的 NAT 类型检测函数。

```python
from p2p_sdk import detect_nat_type

nat_type = await detect_nat_type(
    stun_server="stun.l.google.com",
    stun_port=19302
)
```

**参数：**
- `stun_server` (str): STUN 服务器地址
- `stun_port` (int): STUN 服务器端口

**返回：** NATType

**异常：**
- `NATDetectionError`: 检测失败

## 协议格式

### 消息格式

所有消息使用以下二进制格式：

```
[total_length(4)][json_length(4)][json_header][payload]
```

- `total_length` (4 bytes): 整个消息的长度（大端序）
- `json_length` (4 bytes): JSON 头部的长度（大端序）
- `json_header` (variable): JSON 格式的消息头
- `payload` (variable): 消息负载（可选）

### 消息类型

#### handshake

连接握手消息。

```json
{
    "type": "handshake",
    "version": "1.0",
    "did": "device-001",
    "timestamp": 1234567890
}
```

#### keepalive

保活消息。

```json
{
    "type": "keepalive",
    "timestamp": 1234567890
}
```

#### channel_data

通道数据传输。

```json
{
    "type": "channel_data",
    "channel_id": 1,
    "data_length": 1024,
    "timestamp": 1234567890
}
```

#### channel_open

打开新通道。

```json
{
    "type": "channel_open",
    "channel_id": 1,
    "channel_type": "data",
    "reliable": true,
    "priority": 5
}
```

#### channel_close

关闭通道。

```json
{
    "type": "channel_close",
    "channel_id": 1
}
```

#### disconnect

优雅断开连接。

```json
{
    "type": "disconnect",
    "reason": "user_requested"
}
```

#### error

错误通知。

```json
{
    "type": "error",
    "code": "connection_failed",
    "message": "Connection timeout"
}
```

## 配置示例

### 最小配置

```python
client = P2PClient(did="device-001")
```

### 生产环境配置

```python
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
    auto_relay=True,
    recv_buffer_size=65536
)
```

### 高性能配置

```python
client = P2PClient(
    did="device-001",
    recv_buffer_size=131072,  # 128KB
    keepalive_interval=3.0,   # 更频繁的保活
    max_retries=5,            # 更多重试
    auto_relay=True
)
```

### 低延迟配置

```python
client = P2PClient(
    did="device-001",
    connection_timeout=10.0,  # 更短的超时
    punch_timeout=5.0,
    keepalive_interval=2.0,   # 更频繁的保活
    recv_buffer_size=8192     # 更小的缓冲区
)
```
