# 客户端 SDK 跨平台对比分析报告

**分析日期**: 2026-03-06  
**分析目标**: 评估 P2P-Platform SDK 跨平台支持能力，对标 go-libp2p，参考尚云互联接口设计

---

## 一、当前 SDK 现状

### 1.1 技术栈分析

| 维度 | 当前状态 | 问题 |
|------|----------|------|
| **语言** | Python 3.12+ | 仅支持 Python，无法跨平台 |
| **核心层** | 无 | 缺少 C/C++ 核心层 |
| **移动端** | 无 | 不支持 iOS/Android |
| **嵌入式** | 无 | 不支持 IoT 设备 |
| **绑定** | 无 | 无其他语言绑定 |

### 1.2 当前 SDK 架构

```
client_sdk/
├── src/p2p_sdk/
│   ├── client.py          # 主客户端类
│   ├── transport.py       # 传输层 (UDP/Relay)
│   ├── signaling.py       # 信令客户端
│   ├── nat_detection.py   # NAT 检测
│   ├── protocol.py        # 协议编解码
│   └── exceptions.py      # 异常定义
└── tests/
```

### 1.3 当前 SDK 功能

| 功能 | 状态 | 说明 |
|------|:----:|------|
| NAT 检测 | ✅ | STUN 协议 |
| UDP 打孔 | ✅ | 基础实现 |
| Relay 降级 | ✅ | 自动降级 |
| 多通道 | ✅ | Control/Data/Video/Audio |
| 事件回调 | ✅ | 异步回调 |
| 自动重连 | ⚠️ | 部分实现 |

---

## 二、跨平台支持对比

### 2.1 平台支持矩阵

| 平台 | P2P-Platform SDK | go-libp2p | 尚云互联 |
|------|:----------------:|:---------:|:--------:|
| **Linux x64** | ✅ | ✅ | ✅ |
| **macOS x64/ARM** | ✅ | ✅ | ✅ |
| **Windows x64** | ✅ | ✅ | ✅ |
| **iOS** | ❌ | ✅ | ✅ |
| **Android** | ❌ | ✅ | ✅ |
| **WebAssembly** | ❌ | ⚠️ | ✅ |
| **嵌入式 Linux** | ❌ | ✅ | ⚠️ |

**结论**: 当前 SDK 跨平台支持率仅 **43%** (3/7)

### 2.2 go-libp2p 跨平台架构

```
go-libp2p/
├── core/                   # 核心接口 (Go)
├── p2p/                    # P2P 实现 (Go)
├── transport/              # 传输层
│   ├── tcp/               # TCP 传输
│   ├── quic/              # QUIC 传输
│   ├── webrtc/            # WebRTC 传输
│   └── websocket/         # WebSocket 传输
├── c-go/                   # C 绑定 (libp2p-c)
├── js-libp2p/              # JavaScript 绑定
└── rust-libp2p/            # Rust 绑定
```

**go-libp2p 跨平台策略**:
1. Go 原生跨平台编译 (GOOS/GOARCH)
2. cgo 导出 C 接口 (libp2p-c)
3. FFI 绑定各语言 (JS, Rust, Swift, Kotlin)

### 2.3 尚云互联 SDK 架构 (参考)

```
尚云互联 SDK/
├── core/                   # C++ 核心层
│   ├── p2p_engine/        # P2P 引擎
│   ├── transport/         # 传输层
│   └── protocol/          # 协议层
├── bindings/               # 语言绑定
│   ├── python/            # Python SDK
│   ├── java/              # Java/Android SDK
│   ├── swift/             # Swift/iOS SDK
│   ├── js/                # JavaScript SDK
│   └── c/                 # C API
└── platforms/              # 平台适配
    ├── ios/               # iOS 平台
    ├── android/           # Android 平台
    └── embedded/          # 嵌入式平台
```

---

## 三、接口设计对比

### 3.1 当前 SDK 接口

```python
# 当前 Python SDK 接口
class P2PClient:
    async def initialize() -> None
    async def detect_nat() -> NATType
    async def connect(did: str) -> bool
    async def send_data(channel: int, data: bytes) -> None
    async def recv_data(channel: int, timeout: float) -> bytes
    def create_channel(channel_type: ChannelType) -> int
    def close_channel(channel_id: int) -> None
    async def close() -> None
    
    # 事件回调
    def on_connected(callback)
    def on_disconnected(callback)
    def on_data(callback)
    def on_error(callback)
```

### 3.2 尚云互联接口风格 (参考)

```c
// C API 风格
typedef struct p2p_client_t p2p_client;
typedef struct p2p_config_t p2p_config;
typedef struct p2p_channel_t p2p_channel;

// 初始化与销毁
int p2p_client_create(p2p_client** client, const p2p_config* config);
int p2p_client_destroy(p2p_client* client);

// 连接管理
int p2p_client_connect(p2p_client* client, const char* peer_id, int timeout_ms);
int p2p_client_disconnect(p2p_client* client);
int p2p_client_get_state(p2p_client* client);

// 通道管理
int p2p_channel_open(p2p_client* client, int channel_type, p2p_channel** channel);
int p2p_channel_close(p2p_channel* channel);
int p2p_channel_send(p2p_channel* channel, const void* data, size_t len);
int p2p_channel_recv(p2p_channel* channel, void* buf, size_t buf_len, int timeout_ms);

// 回调注册
typedef void (*p2p_event_cb)(int event_type, void* data, void* user_ctx);
int p2p_client_set_callback(p2p_client* client, int event_type, p2p_event_cb cb, void* ctx);
```

```java
// Java/Android API 风格
public class P2PClient {
    // 初始化
    public void initialize(P2PConfig config, Callback<Void> callback);
    public void destroy();
    
    // 连接管理
    public void connect(String peerId, int timeoutMs, Callback<P2PConnection> callback);
    public void disconnect();
    public ConnectionState getState();
    
    // 通道管理
    public void openChannel(int channelType, Callback<P2PChannel> callback);
    
    // 事件监听
    public void setEventListener(P2PEventListener listener);
}

public interface P2PEventListener {
    void onConnected(String peerId);
    void onDisconnected(String peerId);
    void onDataReceived(int channelId, byte[] data);
    void onError(P2PError error);
}
```

### 3.3 go-libp2p 接口风格

```go
// Go API 风格
type Host interface {
    ID() peer.ID
    Network() network.Network
    NewStream(ctx context.Context, p peer.ID, protos ...string) (network.Stream, error)
    Connect(ctx context.Context, pi peer.AddrInfo) error
    SetStreamHandler(pid protocol.ID, handler network.StreamHandler)
    Close() error
}

type Stream interface {
    Read(b []byte) (n int, err error)
    Write(b []byte) (n int, err error)
    Close() error
    Reset() error
}
```

---

## 四、跨平台方案对比

### 4.1 方案一：C++ 核心层 + 语言绑定 (推荐)

```
架构:
┌─────────────────────────────────────────┐
│           Application Layer             │
├─────────────────────────────────────────┤
│  Python SDK │ Java SDK │ Swift SDK │ JS │
├─────────────────────────────────────────┤
│              C API (FFI)                │
├─────────────────────────────────────────┤
│           C++ Core Engine               │
│  ┌─────────────────────────────────┐   │
│  │ Transport │ Protocol │ Security │   │
│  └─────────────────────────────────┘   │
├─────────────────────────────────────────┤
│           Platform Abstraction          │
│  Linux │ macOS │ Windows │ iOS │ Android│
└─────────────────────────────────────────┘
```

**优点**:
- 一次开发，多平台复用
- 性能最优
- 类似尚云互联架构

**缺点**:
- 开发成本较高
- 需要维护多语言绑定

### 4.2 方案二：Rust 核心层 + 语言绑定

```
架构:
┌─────────────────────────────────────────┐
│           Application Layer             │
├─────────────────────────────────────────┤
│  Python │ Java/Kotlin │ Swift │ Node.js │
├─────────────────────────────────────────┤
│              FFI Bindings               │
├─────────────────────────────────────────┤
│           Rust Core Engine              │
│  (参考 rust-libp2p 架构)               │
├─────────────────────────────────────────┤
│           Platform Abstraction          │
└─────────────────────────────────────────┘
```

**优点**:
- 内存安全
- 现代语言特性
- 可复用 rust-libp2p 组件

**缺点**:
- 学习曲线陡峭
- 团队可能不熟悉 Rust

### 4.3 方案三：Go 核心层 + gomobile (类似 go-libp2p)

```
架构:
┌─────────────────────────────────────────┐
│           Application Layer             │
├─────────────────────────────────────────┤
│  Python │ Android (AAR) │ iOS (Framework)│
├─────────────────────────────────────────┤
│           Go Core Engine                │
│  (可复用 go-libp2p)                    │
├─────────────────────────────────────────┤
│           gomobile / cgo                │
└─────────────────────────────────────────┘
```

**优点**:
- 可直接复用 go-libp2p
- gomobile 成熟稳定
- 开发效率高

**缺点**:
- iOS 包体积较大
- 跨语言调用有开销

### 4.4 方案对比总结

| 方案 | 开发成本 | 性能 | 可维护性 | 推荐度 |
|------|:--------:|:----:|:--------:|:------:|
| C++ 核心 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Rust 核心 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Go 核心 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 五、目标 SDK 架构设计 (推荐方案)

### 5.1 整体架构

```
p2p-sdk/
├── core/                           # C++ 核心层
│   ├── engine/
│   │   ├── p2p_engine.cpp         # P2P 引擎核心
│   │   ├── connection_manager.cpp  # 连接管理
│   │   └── channel_manager.cpp     # 通道管理
│   ├── transport/
│   │   ├── tcp_transport.cpp       # TCP 传输
│   │   ├── udp_transport.cpp       # UDP 传输
│   │   ├── quic_transport.cpp      # QUIC 传输
│   │   └── webrtc_transport.cpp    # WebRTC 传输
│   ├── protocol/
│   │   ├── handshake.cpp           # 握手协议
│   │   ├── channel_proto.cpp       # 通道协议
│   │   └── relay_proto.cpp         # 中继协议
│   ├── nat/
│   │   ├── stun_client.cpp         # STUN 客户端
│   │   ├── nat_detector.cpp        # NAT 检测
│   │   └── hole_puncher.cpp        # 打孔器
│   ├── security/
│   │   ├── dtls_wrapper.cpp        # DTLS 封装
│   │   └── srtp_session.cpp        # SRTP 会话
│   └── platform/
│       ├── linux/                   # Linux 平台
│       ├── macos/                   # macOS 平台
│       ├── windows/                 # Windows 平台
│       ├── ios/                     # iOS 平台
│       └── android/                 # Android 平台
├── api/                             # C API
│   ├── p2p_client.h                # 客户端 API
│   ├── p2p_channel.h               # 通道 API
│   ├── p2p_config.h                # 配置 API
│   └── p2p_types.h                 # 类型定义
├── bindings/                        # 语言绑定
│   ├── python/                      # Python 绑定
│   │   └── p2p_sdk/
│   │       ├── __init__.py
│   │       └── client.py
│   ├── java/                        # Java/Android 绑定
│   │   └── src/main/java/com/p2p/
│   │       ├── P2PClient.java
│   │       └── P2PChannel.java
│   ├── swift/                       # Swift/iOS 绑定
│   │   └── Sources/P2PSDK/
│   │       ├── P2PClient.swift
│   │       └── P2PChannel.swift
│   └── js/                          # JavaScript 绑定
│       └── src/
│           ├── index.ts
│           └── client.ts
└── tests/                           # 测试
    ├── core_tests/
    ├── binding_tests/
    └── integration_tests/
```

### 5.2 核心 API 设计 (参考尚云互联)

```c
// p2p_client.h - 核心 C API

#ifndef P2P_CLIENT_H
#define P2P_CLIENT_H

#include "p2p_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// ==================== 客户端管理 ====================

/// 创建 P2P 客户端
/// @param config 配置参数
/// @param client 输出客户端句柄
/// @return 0 成功，其他失败
P2P_API int p2p_client_create(const p2p_config_t* config, p2p_client_t** client);

/// 销毁 P2P 客户端
/// @param client 客户端句柄
/// @return 0 成功，其他失败
P2P_API int p2p_client_destroy(p2p_client_t* client);

/// 初始化客户端 (NAT 检测、信令连接)
/// @param client 客户端句柄
/// @return 0 成功，其他失败
P2P_API int p2p_client_initialize(p2p_client_t* client);

// ==================== 连接管理 ====================

/// 连接对端设备
/// @param client 客户端句柄
/// @param peer_id 对端设备 ID
/// @param timeout_ms 超时时间 (毫秒)
/// @return 0 成功，其他失败
P2P_API int p2p_client_connect(p2p_client_t* client, const char* peer_id, int timeout_ms);

/// 断开连接
/// @param client 客户端句柄
/// @return 0 成功，其他失败
P2P_API int p2p_client_disconnect(p2p_client_t* client);

/// 获取连接状态
/// @param client 客户端句柄
/// @return 连接状态
P2P_API p2p_state_t p2p_client_get_state(p2p_client_t* client);

/// 获取连接类型 (P2P/Relay)
/// @param client 客户端句柄
/// @return 连接类型
P2P_API p2p_conn_type_t p2p_client_get_conn_type(p2p_client_t* client);

// ==================== 通道管理 ====================

/// 打开数据通道
/// @param client 客户端句柄
/// @param type 通道类型
/// @param config 通道配置
/// @param channel 输出通道句柄
/// @return 0 成功，其他失败
P2P_API int p2p_channel_open(p2p_client_t* client, 
                              p2p_channel_type_t type,
                              const p2p_channel_config_t* config,
                              p2p_channel_t** channel);

/// 关闭数据通道
/// @param channel 通道句柄
/// @return 0 成功，其他失败
P2P_API int p2p_channel_close(p2p_channel_t* channel);

/// 发送数据
/// @param channel 通道句柄
/// @param data 数据指针
/// @param len 数据长度
/// @return 实际发送字节数，负数表示失败
P2P_API int p2p_channel_send(p2p_channel_t* channel, const void* data, size_t len);

/// 接收数据
/// @param channel 通道句柄
/// @param buf 接收缓冲区
/// @param buf_len 缓冲区大小
/// @param timeout_ms 超时时间
/// @return 实际接收字节数，负数表示失败
P2P_API int p2p_channel_recv(p2p_channel_t* channel, void* buf, size_t buf_len, int timeout_ms);

// ==================== 事件回调 ====================

/// 事件回调类型
typedef void (*p2p_event_callback_t)(p2p_event_type_t type, 
                                       const p2p_event_data_t* data,
                                       void* user_ctx);

/// 设置事件回调
/// @param client 客户端句柄
/// @param type 事件类型
/// @param callback 回调函数
/// @param user_ctx 用户上下文
/// @return 0 成功，其他失败
P2P_API int p2p_client_set_callback(p2p_client_t* client,
                                     p2p_event_type_t type,
                                     p2p_event_callback_t callback,
                                     void* user_ctx);

// ==================== NAT 检测 ====================

/// 获取 NAT 类型
/// @param client 客户端句柄
/// @return NAT 类型
P2P_API p2p_nat_type_t p2p_client_get_nat_type(p2p_client_t* client);

/// 获取公网地址
/// @param client 客户端句柄
/// @param addr 输出地址
/// @param port 输出端口
/// @return 0 成功，其他失败
P2P_API int p2p_client_get_public_addr(p2p_client_t* client, 
                                        char* addr, int addr_len,
                                        int* port);

#ifdef __cplusplus
}
#endif

#endif // P2P_CLIENT_H
```

### 5.3 Python 绑定示例

```python
# p2p_sdk/client.py - Python 绑定

from typing import Optional, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass
import asyncio

from ._binding import ffi, lib

class ConnectionState(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED_P2P = 2
    CONNECTED_RELAY = 3
    FAILED = 4

class ChannelType(Enum):
    CONTROL = 0
    DATA = 1
    VIDEO = 2
    AUDIO = 3
    CUSTOM = 4

@dataclass
class P2PConfig:
    signaling_server: str = "localhost"
    signaling_port: int = 8443
    stun_server: str = "stun.l.google.com"
    stun_port: int = 19302
    relay_server: str = "localhost"
    relay_port: int = 5000
    auto_relay: bool = True

class P2PChannel:
    """数据通道"""
    
    def __init__(self, handle):
        self._handle = handle
    
    async def send(self, data: bytes) -> int:
        """发送数据"""
        return await asyncio.get_event_loop().run_in_executor(
            None, lib.p2p_channel_send, self._handle, data, len(data)
        )
    
    async def recv(self, timeout_ms: int = 5000) -> bytes:
        """接收数据"""
        buf = ffi.new("char[65536]")
        ret = await asyncio.get_event_loop().run_in_executor(
            None, lib.p2p_channel_recv, self._handle, buf, 65536, timeout_ms
        )
        if ret < 0:
            raise Exception(f"Recv failed: {ret}")
        return ffi.buffer(buf, ret)[:]
    
    def close(self) -> None:
        """关闭通道"""
        lib.p2p_channel_close(self._handle)

class P2PClient:
    """P2P 客户端"""
    
    def __init__(self, device_id: str, config: Optional[P2PConfig] = None):
        self._device_id = device_id
        self._config = config or P2PConfig()
        self._handle = None
        self._callbacks = {}
    
    async def initialize(self) -> None:
        """初始化客户端"""
        # 创建 C 配置结构
        c_config = ffi.new("p2p_config_t*")
        c_config.signaling_server = self._config.signaling_server.encode()
        c_config.signaling_port = self._config.signaling_port
        # ... 其他配置
        
        # 创建客户端
        handle_ptr = ffi.new("p2p_client_t**")
        ret = lib.p2p_client_create(c_config, handle_ptr)
        if ret != 0:
            raise Exception(f"Create failed: {ret}")
        self._handle = handle_ptr[0]
        
        # 初始化
        ret = lib.p2p_client_initialize(self._handle)
        if ret != 0:
            raise Exception(f"Initialize failed: {ret}")
    
    async def connect(self, peer_id: str, timeout_ms: int = 30000) -> bool:
        """连接对端"""
        ret = await asyncio.get_event_loop().run_in_executor(
            None, lib.p2p_client_connect, 
            self._handle, peer_id.encode(), timeout_ms
        )
        return ret == 0
    
    async def disconnect(self) -> None:
        """断开连接"""
        lib.p2p_client_disconnect(self._handle)
    
    def open_channel(self, channel_type: ChannelType) -> P2PChannel:
        """打开通道"""
        channel_ptr = ffi.new("p2p_channel_t**")
        ret = lib.p2p_channel_open(
            self._handle, channel_type.value, ffi.NULL, channel_ptr
        )
        if ret != 0:
            raise Exception(f"Open channel failed: {ret}")
        return P2PChannel(channel_ptr[0])
    
    @property
    def state(self) -> ConnectionState:
        """获取连接状态"""
        state = lib.p2p_client_get_state(self._handle)
        return ConnectionState(state)
    
    def on_connected(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """设置连接回调"""
        self._callbacks['connected'] = callback
        # 注册 C 回调...
    
    def on_disconnected(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """设置断开回调"""
        self._callbacks['disconnected'] = callback
    
    def on_data(self, callback: Callable[[int, bytes], Awaitable[None]]) -> None:
        """设置数据回调"""
        self._callbacks['data'] = callback
    
    def on_error(self, callback: Callable[[Exception], Awaitable[None]]) -> None:
        """设置错误回调"""
        self._callbacks['error'] = callback
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._handle:
            lib.p2p_client_destroy(self._handle)
            self._handle = None
```

---

## 六、实施计划

### 6.1 阶段划分

| 阶段 | 内容 | 工期 | 人员 |
|------|------|------|------|
| Phase 1 | C++ 核心层开发 | 4 周 | 2 C++ 工程师 |
| Phase 2 | C API 设计与实现 | 2 周 | 1 C++ 工程师 |
| Phase 3 | Python 绑定 | 1 周 | 1 Python 工程师 |
| Phase 4 | Java/Android 绑定 | 2 周 | 1 Android 工程师 |
| Phase 5 | Swift/iOS 绑定 | 2 周 | 1 iOS 工程师 |
| Phase 6 | JavaScript 绑定 | 1 周 | 1 前端工程师 |
| Phase 7 | 测试与文档 | 2 周 | 1 测试工程师 |

**总工期**: 约 14 周

### 6.2 里程碑

| 里程碑 | 交付物 |
|--------|--------|
| M1 | C++ 核心层完成 (Linux/macOS/Windows) |
| M2 | C API 发布 |
| M3 | Python SDK 发布 |
| M4 | Android SDK 发布 |
| M5 | iOS SDK 发布 |
| M6 | JavaScript SDK 发布 |
| M7 | 1.0 正式版发布 |

---

## 七、结论与建议

### 7.1 当前问题

1. **不支持跨平台**: 仅 Python，无法在移动端使用
2. **无 C 核心层**: 无法提供多语言绑定
3. **接口不统一**: 与主流 SDK 接口风格差异大

### 7.2 建议方案

**推荐采用 C++ 核心层 + 语言绑定方案**:
- 参考 go-libp2p 和尚云互联架构
- 实现跨平台支持 (Linux/macOS/Windows/iOS/Android)
- 提供多语言绑定 (Python/Java/Swift/JS)
- 保持与现有 Python SDK 接口兼容

### 7.3 预期收益

| 维度 | 改进 |
|------|------|
| 平台覆盖 | 43% → **100%** (7/7) |
| 语言支持 | 1 → **5** (Python/Java/Swift/JS/C) |
| 性能 | 提升 **30%+** (C++ vs Python) |
| 内存占用 | 降低 **50%+** |

---

---

## 八、SDK 交付要求

### 8.1 交付形式要求

**关键要求**: 客户端 SDK 必须以**编译后的二进制形式**交付，**不能暴露源码**。

| 平台 | 交付格式 | 说明 |
|------|----------|------|
| **Linux** | `.so` + 头文件 | 动态库 + API 头文件 |
| **macOS** | `.dylib` + 头文件 | 动态库 + API 头文件 |
| **Windows** | `.dll` + `.lib` + 头文件 | DLL + 导入库 + 头文件 |
| **iOS** | `.framework` / `.xcframework` | iOS Framework 包 |
| **Android** | `.aar` | Android Archive 包 |
| **Python** | `.whl` (wheel) | Python wheel 包 (含编译后二进制) |
| **JavaScript** | `.node` + `.d.ts` | Native addon + TypeScript 类型 |

### 8.2 SDK 包结构

```
# Python SDK 包结构 (p2p_sdk-1.0.0-py3-none-any.whl)
p2p_sdk/
├── __init__.py           # Python 入口
├── client.py             # Python 封装层
├── _binding.cpython-312-x86_64-linux-gnu.so  # 编译后的核心库
└── py.typed              # 类型标记

# Android SDK 包结构 (p2p-sdk-1.0.0.aar)
p2p-sdk.aar/
├── AndroidManifest.xml
├── classes.jar           # Java/Kotlin 封装层
├── jni/
│   ├── arm64-v8a/
│   │   └── libp2p_core.so    # ARM64 核心库
│   ├── armeabi-v7a/
│   │   └── libp2p_core.so    # ARM32 核心库
│   └── x86_64/
│       └── libp2p_core.so    # x86 核心库
└── res/

# iOS SDK 包结构 (P2PSDK.xcframework)
P2PSDK.xcframework/
├── Info.plist
├── ios-arm64/
│   └── P2PSdk.framework/
│       ├── P2PSdk              # ARM64 二进制
│       └── Headers/
│           ├── P2PClient.h
│           └── P2PChannel.h
├── ios-arm64-simulator/
│   └── P2PSdk.framework/       # 模拟器版本
└── macos-arm64-x86_64/
    └── P2PSdk.framework/       # macOS 版本

# JavaScript SDK 包结构 (@p2p/sdk-1.0.0.tgz)
@p2p/sdk/
├── package.json
├── index.js              # JS 封装层
├── index.d.ts            # TypeScript 类型
├── native/
│   ├── linux-x64/
│   │   └── p2p_core.node    # Linux x64 原生模块
│   ├── darwin-x64/
│   │   └── p2p_core.node    # macOS x64 原生模块
│   ├── darwin-arm64/
│   │   └── p2p_core.node    # macOS ARM 原生模块
│   └── win32-x64/
│       └── p2p_core.node    # Windows x64 原生模块
└── lib/
    └── p2p.d.ts             # 类型定义
```

### 8.3 代码保护策略

| 层级 | 保护措施 |
|------|----------|
| **核心层 (C++)** | 编译为二进制，符号剥离 |
| **Python 绑定** | Cython 编译为 .so |
| **Java 绑定** | ProGuard 混淆 |
| **JS 绑定** | 二进制 addon，不暴露源码 |
| **API** | 只暴露必要接口，隐藏内部实现 |

### 8.4 SDK 发布清单

每次发布需要包含：

1. **二进制包** (各平台)
   - [ ] Linux x64: `libp2p_core.so`
   - [ ] macOS x64: `libp2p_core.dylib`
   - [ ] macOS ARM: `libp2p_core.dylib`
   - [ ] Windows x64: `p2p_core.dll`
   - [ ] Android: `p2p-sdk.aar`
   - [ ] iOS: `P2PSDK.xcframework`

2. **语言绑定包**
   - [ ] Python: `p2p_sdk-1.0.0-py3-none-any.whl`
   - [ ] Java: `p2p-sdk-java-1.0.0.jar`
   - [ ] Swift: `P2PSDK.xcframework`
   - [ ] JavaScript: `@p2p/sdk-1.0.0.tgz`

3. **文档**
   - [ ] API 参考文档
   - [ ] 集成指南
   - [ ] 示例代码
   - [ ] 更新日志

4. **许可**
   - [ ] 许可证文件
   - [ ] 授权验证机制

---

**报告完成时间**: 2026-03-06
**下一步**: 团队讨论，确定方案，开始设计
