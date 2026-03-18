# P2P 跨平台 SDK 架构设计方案

**设计日期**: 2026-03-06
**设计团队**: P2P 跨平台 SDK 开发组
**参考**: go-libp2p, 尚云互联

---

## 一、设计目标

### 1.1 核心目标

| 目标 | 说明 |
|------|------|
| **跨平台** | Linux / macOS / Windows / iOS / Android |
| **多语言** | Python / Java / Swift / JavaScript / C |
| **二进制交付** | 编译后 SDK，保护源码 |
| **高性能** | C++ 核心，低延迟高吞吐 |
| **易集成** | 简洁 API，参考尚云互联风格 |

### 1.2 必须支持的平台

✅ **Linux** (x64, ARM64) - **必须支持**
✅ macOS (x64, ARM64)
✅ Windows (x64)
✅ iOS (ARM64)
✅ Android (ARM64, ARM32, x86)

---

## 二、系统架构

### 2.1 分层架构

```
┌────────────────────────────────────────────────────────────────┐
│                      Application Layer                         │
│         用户应用 (使用各语言 SDK)                              │
├────────────────────────────────────────────────────────────────┤
│                     Language Bindings                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ Python   │ │ Java/    │ │ Swift/   │ │ Java-    │          │
│  │ SDK      │ │ Android  │ │ iOS      │ │ Script   │          │
│  │ (.whl)   │ │ (.aar)   │ │ (.xcfw)  │ │ (.npm)   │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
├────────────────────────────────────────────────────────────────┤
│                        C API Layer                             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  p2p_client.h  │  p2p_channel.h  │  p2p_config.h        │  │
│  └─────────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────────┤
│                     C++ Core Engine                            │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    Engine Core                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │  │
│  │  │ Connection  │  │  Channel    │  │   Event     │     │  │
│  │  │ Manager     │  │  Manager    │  │   System    │     │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │  │
│  ├─────────────────────────────────────────────────────────┤  │
│  │                   Protocol Layer                        │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │  │
│  │  │Handshake│ │ Channel │ │ Keepalive│ │ Relay   │       │  │
│  │  │ Protocol│ │ Protocol│ │ Protocol │ │ Protocol│       │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │  │
│  ├─────────────────────────────────────────────────────────┤  │
│  │                  Transport Layer                        │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │  │
│  │  │   TCP   │ │   UDP   │ │  QUIC   │ │ WebRTC  │       │  │
│  │  │Transport│ │Transport│ │Transport│ │Transport│       │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │  │
│  ├─────────────────────────────────────────────────────────┤  │
│  │                    NAT Layer                            │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                   │  │
│  │  │  STUN   │ │  NAT    │ │  Hole   │                   │  │
│  │  │ Client  │ │ Detector│ │ Puncher │                   │  │
│  │  └─────────┘ └─────────┘ └─────────┘                   │  │
│  ├─────────────────────────────────────────────────────────┤  │
│  │                  Security Layer                         │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                   │  │
│  │  │  DTLS   │ │  SRTP   │ │  E2E    │                   │  │
│  │  │ Wrapper │ │ Session │ │ Encrypt │                   │  │
│  │  └─────────┘ └─────────┘ └─────────┘                   │  │
│  └─────────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────────┤
│                   Platform Abstraction                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │  Linux  │ │  macOS  │ │ Windows │ │   iOS   │ │ Android │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 | 依赖 |
|------|------|------|
| **Engine Core** | 状态机、连接管理、事件分发 | 所有模块 |
| **Protocol Layer** | 协议编解码、消息处理 | Transport |
| **Transport Layer** | 网络传输、连接建立 | Platform |
| **NAT Layer** | NAT 检测、打孔 | Transport |
| **Security Layer** | 加密、认证 | Transport |
| **Platform Abstraction** | 平台差异封装 | OS API |

---

## 三、目录结构

```
p2p-sdk/
├── CMakeLists.txt                    # CMake 构建配置
├── README.md
├── LICENSE
│
├── core/                             # C++ 核心层
│   ├── CMakeLists.txt
│   ├── include/
│   │   └── p2p/
│   │       ├── engine.hpp            # 引擎核心
│   │       ├── client.hpp            # 客户端
│   │       ├── channel.hpp           # 通道
│   │       ├── config.hpp            # 配置
│   │       └── types.hpp             # 类型定义
│   │
│   ├── src/
│   │   ├── engine/
│   │   │   ├── p2p_engine.cpp        # P2P 引擎
│   │   │   ├── connection_mgr.cpp    # 连接管理
│   │   │   ├── channel_mgr.cpp       # 通道管理
│   │   │   └── event_system.cpp      # 事件系统
│   │   │
│   │   ├── protocol/
│   │   │   ├── handshake.cpp         # 握手协议
│   │   │   ├── channel_proto.cpp     # 通道协议
│   │   │   ├── keepalive.cpp         # 心跳协议
│   │   │   └── relay_proto.cpp       # 中继协议
│   │   │
│   │   ├── transport/
│   │   │   ├── transport_base.cpp    # 传输基类
│   │   │   ├── tcp_transport.cpp     # TCP 传输
│   │   │   ├── udp_transport.cpp     # UDP 传输
│   │   │   ├── quic_transport.cpp    # QUIC 传输
│   │   │   └── webrtc_transport.cpp  # WebRTC 传输
│   │   │
│   │   ├── nat/
│   │   │   ├── stun_client.cpp       # STUN 客户端
│   │   │   ├── nat_detector.cpp      # NAT 检测
│   │   │   └── hole_puncher.cpp      # 打孔器
│   │   │
│   │   ├── security/
│   │   │   ├── dtls_wrapper.cpp      # DTLS 封装
│   │   │   ├── srtp_session.cpp      # SRTP 会话
│   │   │   └── crypto.cpp            # 加密工具
│   │   │
│   │   └── platform/
│   │       ├── platform_base.cpp     # 平台基类
│   │       ├── linux/
│   │       │   └── platform_linux.cpp
│   │       ├── macos/
│   │       │   └── platform_macos.cpp
│   │       ├── windows/
│   │       │   └── platform_windows.cpp
│   │       ├── ios/
│   │       │   └── platform_ios.mm
│   │       └── android/
│   │           └── platform_android.cpp
│   │
│   └── tests/
│       ├── test_engine.cpp
│       ├── test_transport.cpp
│       └── test_nat.cpp
│
├── api/                              # C API
│   ├── CMakeLists.txt
│   ├── include/
│   │   ├── p2p_client.h              # 客户端 API
│   │   ├── p2p_channel.h             # 通道 API
│   │   ├── p2p_config.h              # 配置 API
│   │   ├── p2p_events.h              # 事件定义
│   │   └── p2p_types.h               # 类型定义
│   └── src/
│       ├── p2p_client_c.cpp          # C API 实现
│       └── p2p_channel_c.cpp
│
├── bindings/                         # 语言绑定
│   ├── python/
│   │   ├── setup.py
│   │   ├── pyproject.toml
│   │   └── p2p_sdk/
│   │       ├── __init__.py
│   │       ├── client.py
│   │       ├── channel.py
│   │       └── _binding.pyx          # Cython 绑定
│   │
│   ├── java/
│   │   ├── build.gradle
│   │   └── src/main/java/com/p2p/sdk/
│   │       ├── P2PClient.java
│   │       ├── P2PChannel.java
│   │       ├── P2PConfig.java
│   │       └── P2PEventListener.java
│   │
│   ├── swift/
│   │   ├── Package.swift
│   │   └── Sources/P2PSDK/
│   │       ├── P2PClient.swift
│   │       ├── P2PChannel.swift
│   │       └── P2PConfig.swift
│   │
│   └── javascript/
│       ├── package.json
│       ├── tsconfig.json
│       └── src/
│           ├── index.ts
│           ├── client.ts
│           └── native_binding.cc
│
├── platforms/                        # 平台打包
│   ├── linux/
│   │   └── build.sh
│   ├── macos/
│   │   └── build.sh
│   ├── windows/
│   │   └── build.bat
│   ├── ios/
│   │   └── build_xcframework.sh
│   └── android/
│       ├── build.gradle
│       └── src/main/
│
├── examples/                         # 示例代码
│   ├── python/
│   │   └── basic_usage.py
│   ├── java/
│   │   └── BasicUsage.java
│   ├── swift/
│   │   └── BasicUsage.swift
│   └── javascript/
│       └── basic_usage.ts
│
└── docs/                             # 文档
    ├── api_reference.md
    ├── integration_guide.md
    └── platform_setup.md
```

---

## 四、核心 API 设计

### 4.1 C API (统一接口)

```c
// p2p_types.h - 类型定义
typedef enum {
    P2P_STATE_DISCONNECTED = 0,
    P2P_STATE_CONNECTING = 1,
    P2P_STATE_CONNECTED_P2P = 2,
    P2P_STATE_CONNECTED_RELAY = 3,
    P2P_STATE_FAILED = 4,
} p2p_state_t;

typedef enum {
    P2P_CHANNEL_CONTROL = 0,
    P2P_CHANNEL_DATA = 1,
    P2P_CHANNEL_VIDEO = 2,
    P2P_CHANNEL_AUDIO = 3,
    P2P_CHANNEL_CUSTOM = 4,
} p2p_channel_type_t;

typedef enum {
    P2P_NAT_UNKNOWN = 0,
    P2P_NAT_PUBLIC = 1,
    P2P_NAT_FULL_CONE = 2,
    P2P_NAT_RESTRICTED = 3,
    P2P_NAT_PORT_RESTRICTED = 4,
    P2P_NAT_SYMMETRIC = 5,
    P2P_NAT_BLOCKED = 6,
} p2p_nat_type_t;

// p2p_client.h - 客户端 API
P2P_API int p2p_client_create(const p2p_config_t* config, p2p_client_t** client);
P2P_API int p2p_client_destroy(p2p_client_t* client);
P2P_API int p2p_client_initialize(p2p_client_t* client);
P2P_API int p2p_client_connect(p2p_client_t* client, const char* peer_id, int timeout_ms);
P2P_API int p2p_client_disconnect(p2p_client_t* client);
P2P_API p2p_state_t p2p_client_get_state(p2p_client_t* client);
P2P_API p2p_nat_type_t p2p_client_get_nat_type(p2p_client_t* client);

// 通道 API
P2P_API int p2p_channel_open(p2p_client_t* client, p2p_channel_type_t type, p2p_channel_t** channel);
P2P_API int p2p_channel_close(p2p_channel_t* channel);
P2P_API int p2p_channel_send(p2p_channel_t* channel, const void* data, size_t len);
P2P_API int p2p_channel_recv(p2p_channel_t* channel, void* buf, size_t buf_len, int timeout_ms);

// 事件回调
typedef void (*p2p_event_callback_t)(int event_type, void* data, void* user_ctx);
P2P_API int p2p_client_set_callback(p2p_client_t* client, int event_type, 
                                     p2p_event_callback_t callback, void* user_ctx);
```

### 4.2 Python API (高仿尚云互联)

```python
from p2p_sdk import P2PClient, P2PConfig, ChannelType

# 创建配置
config = P2PConfig(
    device_id="my-device-001",
    signaling_server="signal.example.com:8443",
    stun_server="stun.l.google.com:19302",
    auto_relay=True,
)

# 创建客户端
client = P2PClient(config)

# 设置回调
@client.on_connected
def on_connected(peer_id: str):
    print(f"Connected to {peer_id}")

@client.on_disconnected
def on_disconnected(peer_id: str):
    print(f"Disconnected from {peer_id}")

@client.on_data
def on_data(channel_id: int, data: bytes):
    print(f"Received {len(data)} bytes on channel {channel_id}")

@client.on_error
def on_error(error: Exception):
    print(f"Error: {error}")

# 初始化并连接
await client.initialize()
await client.connect("peer-device-001")

# 创建通道并发送数据
channel = client.open_channel(ChannelType.DATA)
await channel.send(b"Hello, P2P!")

# 接收数据
data = await channel.recv(timeout_ms=5000)

# 关闭
await client.close()
```

### 4.3 Java/Android API

```java
// 创建配置
P2PConfig config = new P2PConfig.Builder()
    .setDeviceId("my-device-001")
    .setSignalingServer("signal.example.com", 8443)
    .setStunServer("stun.l.google.com", 19302)
    .setAutoRelay(true)
    .build();

// 创建客户端
P2PClient client = new P2PClient(config);

// 设置监听器
client.setEventListener(new P2PEventListener() {
    @Override
    public void onConnected(String peerId) {
        Log.d("P2P", "Connected to " + peerId);
    }
    
    @Override
    public void onDisconnected(String peerId) {
        Log.d("P2P", "Disconnected from " + peerId);
    }
    
    @Override
    public void onDataReceived(int channelId, byte[] data) {
        Log.d("P2P", "Received " + data.length + " bytes");
    }
    
    @Override
    public void onError(P2PError error) {
        Log.e("P2P", "Error: " + error.getMessage());
    }
});

// 初始化并连接
client.initialize();
client.connect("peer-device-001", 30000, new Callback<P2PConnection>() {
    @Override
    public void onSuccess(P2PConnection connection) {
        // 连接成功
        P2PChannel channel = connection.openChannel(ChannelType.DATA);
        channel.send("Hello, P2P!".getBytes());
    }
    
    @Override
    public void onError(P2PError error) {
        // 连接失败
    }
});
```

### 4.4 Swift/iOS API

```swift
// 创建配置
let config = P2PConfig(
    deviceId: "my-device-001",
    signalingServer: "signal.example.com:8443",
    stunServer: "stun.l.google.com:19302",
    autoRelay: true
)

// 创建客户端
let client = P2PClient(config: config)

// 设置代理
client.delegate = self

// 初始化并连接
client.initialize()
client.connect(to: "peer-device-001", timeout: 30000) { result in
    switch result {
    case .success(let connection):
        let channel = connection.openChannel(.data)
        channel.send(data: "Hello, P2P!".data(using: .utf8)!)
    case .failure(let error):
        print("Error: \(error)")
    }
}

// 代理方法
extension ViewController: P2PClientDelegate {
    func client(_ client: P2PClient, didConnectToPeer peerId: String) {
        print("Connected to \(peerId)")
    }
    
    func client(_ client: P2PClient, didDisconnectFromPeer peerId: String) {
        print("Disconnected from \(peerId)")
    }
    
    func client(_ client: P2PClient, didReceiveData data: Data, onChannel channelId: Int) {
        print("Received \(data.count) bytes")
    }
    
    func client(_ client: P2PClient, didEncounterError error: P2PError) {
        print("Error: \(error)")
    }
}
```

---

## 五、构建与打包

### 5.1 构建系统

```cmake
# CMakeLists.txt
cmake_minimum_required(VERSION 3.16)
project(p2p_sdk VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 核心库
add_library(p2p_core SHARED
    core/src/engine/p2p_engine.cpp
    core/src/engine/connection_mgr.cpp
    core/src/engine/channel_mgr.cpp
    core/src/protocol/handshake.cpp
    core/src/transport/tcp_transport.cpp
    core/src/transport/udp_transport.cpp
    core/src/nat/stun_client.cpp
    core/src/nat/nat_detector.cpp
    core/src/security/dtls_wrapper.cpp
)

# C API
add_library(p2p_c SHARED
    api/src/p2p_client_c.cpp
    api/src/p2p_channel_c.cpp
)
target_link_libraries(p2p_c p2p_core)

# 平台特定代码
if(LINUX)
    target_sources(p2p_core PRIVATE core/src/platform/linux/platform_linux.cpp)
elseif(APPLE)
    target_sources(p2p_core PRIVATE core/src/platform/macos/platform_macos.cpp)
elseif(WIN32)
    target_sources(p2p_core PRIVATE core/src/platform/windows/platform_windows.cpp)
endif()
```

### 5.2 打包输出

| 平台 | 输出文件 | 说明 |
|------|----------|------|
| Linux x64 | `libp2p_core.so` + `libp2p_c.so` | 动态库 |
| Linux ARM64 | `libp2p_core.so` + `libp2p_c.so` | 动态库 |
| macOS x64 | `libp2p_core.dylib` | 动态库 |
| macOS ARM | `libp2p_core.dylib` | 动态库 |
| Windows | `p2p_core.dll` + `p2p_c.dll` | DLL |
| iOS | `P2PSDK.xcframework` | Framework |
| Android | `p2p-sdk.aar` | AAR 包 |

---

## 六、依赖库

### 6.1 核心依赖

| 库 | 版本 | 用途 |
|------|------|------|
| **OpenSSL** | 3.0+ | DTLS, 加密 |
| **libsrtp** | 2.4+ | SRTP 媒体加密 |
| **opus** | 1.3+ | 音频编解码 (可选) |
| **libuv** | 1.44+ | 跨平台异步 I/O |

### 6.2 平台依赖

| 平台 | 依赖 |
|------|------|
| Linux | glibc 2.17+, systemd |
| macOS | macOS 10.15+ |
| Windows | Windows 10+ |
| iOS | iOS 13.0+ |
| Android | Android 5.0+ (API 21) |

---

## 七、开发计划

### 7.1 阶段划分

| 阶段 | 内容 | 工期 | 交付物 |
|------|------|------|--------|
| **Phase 1** | C++ 核心层 | 4 周 | libp2p_core.so |
| **Phase 2** | C API | 1 周 | libp2p_c.so + 头文件 |
| **Phase 3** | Python 绑定 | 1 周 | p2p_sdk.whl |
| **Phase 4** | Java/Android 绑定 | 2 周 | p2p-sdk.aar |
| **Phase 5** | Swift/iOS 绑定 | 2 周 | P2PSDK.xcframework |
| **Phase 6** | JavaScript 绑定 | 1 周 | @p2p/sdk npm 包 |
| **Phase 7** | 测试与文档 | 2 周 | 测试报告 + API 文档 |

**总工期**: 约 13 周

### 7.2 里程碑

| 里程碑 | 日期 | 交付物 |
|--------|------|--------|
| M1 | Week 4 | C++ 核心 (Linux/macOS/Windows) |
| M2 | Week 5 | C API 发布 |
| M3 | Week 6 | Python SDK v1.0 |
| M4 | Week 8 | Android SDK v1.0 |
| M5 | Week 10 | iOS SDK v1.0 |
| M6 | Week 11 | JavaScript SDK v1.0 |
| M7 | Week 13 | 1.0 正式版发布 |

---

## 八、风险与对策

| 风险 | 概率 | 对策 |
|------|------|------|
| 跨平台兼容性问题 | 中 | 统一平台抽象层 |
| iOS/Android 审核问题 | 低 | 纯数据通道，无特殊权限 |
| 性能不达标 | 低 | C++ 原生实现，性能有保障 |
| API 设计变更 | 中 | 版本化 API，保持向后兼容 |

---

**设计完成时间**: 2026-03-06
**下一步**: 团队评审，确认方案，开始分工开发
