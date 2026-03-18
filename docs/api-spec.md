# API接口规范

## 通用响应格式

所有API响应遵循统一格式：

```json
{
  "success": boolean,
  "data": any | null,
  "error": {
    "code": string,
    "message": string
  } | null,
  "timestamp": int64
}
```

## 错误码定义

| 错误码 | 说明 |
|--------|------|
| `INVALID_REQUEST` | 请求参数无效 |
| `UNAUTHORIZED` | 未授权访问 |
| `NOT_FOUND` | 资源不存在 |
| `INTERNAL_ERROR` | 服务器内部错误 |
| `RATE_LIMITED` | 请求频率超限 |
| `DEVICE_NOT_FOUND` | 设备未注册 |
| `CONNECTION_FAILED` | 连接建立失败 |

## STUN协议 (RFC 5389)

### 绑定请求

```
Message Type: 0x0001 (Binding Request)
Message Length: 0 (no attributes)
Magic Cookie: 0x2112A442
Transaction ID: 96-bit random
```

### 绑定响应

```
Message Type: 0x0101 (Binding Success Response)
Attributes:
  - XOR-MAPPED-ADDRESS: 客户端公网IP和端口
```

## 信令服务器API

### WebSocket连接

```
URL: ws://localhost:8080/v1/signaling
URL: wss://localhost:8443/v1/signaling
```

### 消息格式

#### 注册设备

```json
{
  "type": "register",
  "data": {
    "device_id": "string",
    "public_key": "string",
    "capabilities": ["p2p", "relay"]
  }
}
```

#### 连接请求

```json
{
  "type": "connect",
  "data": {
    "target_device_id": "string",
    "offer": "string (SDP)"
  }
}
```

#### 连接响应

```json
{
  "type": "answer",
  "data": {
    "source_device_id": "string",
    "answer": "string (SDP)"
  }
}
```

#### ICE候选

```json
{
  "type": "ice_candidate",
  "data": {
    "candidate": "string",
    "sdpMid": "string",
    "sdpMLineIndex": number
  }
}
```

### REST API

#### 获取设备信息

```
GET /api/v1/devices/{device_id}
```

响应：
```json
{
  "success": true,
  "data": {
    "device_id": "string",
    "public_key": "string",
    "status": "online|offline",
    "last_seen": int64,
    "capabilities": ["p2p", "relay"]
  }
}
```

#### 心跳

```
POST /api/v1/devices/{device_id}/heartbeat
```

## DID服务API

### 生成设备身份

```
POST /api/v1/did/generate
```

请求：
```json
{
  "device_type": "ios|android|web|desktop"
}
```

响应：
```json
{
  "success": true,
  "data": {
    "device_id": "did:p2p:xxx",
    "public_key": "string",
    "private_key": "string (仅返回一次)"
  }
}
```

### 验证设备身份

```
POST /api/v1/did/verify
```

请求：
```json
{
  "device_id": "string",
  "signature": "string",
  "challenge": "string"
}
```

### 获取访问令牌

```
POST /api/v1/did/token
```

请求：
```json
{
  "device_id": "string",
  "signature": "string"
}
```

响应：
```json
{
  "success": true,
  "data": {
    "token": "string (JWT)",
    "expires_in": 3600
  }
}
```

## Relay服务器API

### 分配中继端口

```
POST /api/v1/relay/allocate
```

请求：
```json
{
  "device_id": "string",
  "token": "string (JWT)"
}
```

响应：
```json
{
  "success": true,
  "data": {
    "relay_addr": "string",
    "relay_port": number,
    "expires_at": int64
  }
}
```

### 释放中继端口

```
DELETE /api/v1/relay/{allocation_id}
```

## 客户端SDK接口

### 初始化

```python
from p2p_client import P2PClient

client = P2PClient(
    device_id="did:p2p:xxx",
    private_key="xxx",
    stun_server="stun.example.com:3478",
    signaling_url="wss://signaling.example.com/v1/signaling"
)
```

### 连接设备

```python
async def connect_handler(peer_device_id):
    async for connection in client.connect(peer_device_id):
        async for message in connection.messages():
            print(f"Received: {message}")
```

### 接受连接

```python
async def handle_incoming():
    async for connection in client.accept():
        print(f"Connected by: {connection.remote_device_id}")
```
