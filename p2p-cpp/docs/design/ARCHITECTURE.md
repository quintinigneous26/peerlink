# P2P Platform C++ 架构设计

**版本**: 1.0.0
**日期**: 2026-03-15
**架构师**: P2P Platform Team

---

## 1. 设计目标

### 1.1 核心目标

| 目标 | 说明 |
|------|------|
| **高性能** | C++20 实现，零拷贝优化，低延迟高吞吐 |
| **跨平台** | Linux/macOS/Windows/iOS/Android 全平台支持 |
| **多语言绑定** | Python/Java/Swift/JavaScript C API 绑定 |
| **libp2p 兼容** | 完整实现 libp2p 协议栈，与 go-libp2p 互操作 |
| **易于集成** | 简洁的 C API，类似尚云互联 SDK 风格 |
| **安全可靠** | TLS 1.3/Noise 加密，完整的错误处理 |

### 1.2 性能指标

| 指标 | 目标 | Python 基线 |
|------|------|-------------|
| 本地连接延迟 | < 20ms | ~50ms |
| 远程连接延迟 | < 100ms | ~200ms |
| P2P 直连吞吐量 | > 500 Mbps | ~150 Mbps |
| 中继吞吐量 | > 50 Mbps | ~15 Mbps |
| 并发连接数 | 10,000+ | 500+ |
| 内存占用 | < 50MB | ~200MB |

---

## 2. 系统架构

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
│  │  │  TLS    │ │  Noise  │ │  DTLS   │                   │  │
│  │  │ 1.3     │ │ Protocol│ │ Wrapper │                   │  │
│  │  └─────────┘ └─────────┘ └─────────┘                   │  │
│  └─────────────────────────────────────────────────────────┘  │
├───────────────────────────────────��────────────────────────────┤
│                   Platform Abstraction                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │  Linux  │ │  macOS  │ │ Windows │ │   iOS   │ │ Android │ │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 | 关键类 |
|------|------|--------|
| **Core** | 引擎核心、连接管理、事件系统 | `Engine`, `ConnectionManager`, `EventBus` |
| **Protocol** | 协议编解码、消息处理 | `HandshakeProtocol`, `ChannelProtocol` |
| **Transport** | 网络传输、连接建立 | `TcpTransport`, `UdpTransport`, `QuicTransport` |
| **NAT** | NAT 检测、打孔 | `StunClient`, `NatDetector`, `HolePuncher` |
| **Security** | 加密、认证 | `TlsWrapper`, `NoiseProtocol`, `DtlsSession` |
| **Utils** | 工具类、日志、配置 | `Logger`, `Config`, `ThreadPool` |
| **Platform** | 平台抽象层 | `PlatformSocket`, `PlatformThread` |

---

## 3. 核心模块设计

### 3.1 Engine Core

**职责**: 引擎生命周期管理、连接协调、事件分发

**关键接口**:
```cpp
class Engine {
public:
    static std::unique_ptr<Engine> Create(const Config& config);

    Status Start();
    Status Stop();

    std::shared_ptr<Connection> Connect(const PeerId& peer_id);
    Status Listen(const Multiaddr& addr);

    void RegisterProtocol(const std::string& protocol_id,
                         std::unique_ptr<ProtocolHandler> handler);

    EventBus& GetEventBus();
};
```

### 3.2 Connection Manager

**职责**: 连接池管理、连接复用、连接状态跟踪

**关键接口**:
```cpp
class ConnectionManager {
public:
    std::shared_ptr<Connection> GetConnection(const PeerId& peer_id);
    Status AddConnection(std::shared_ptr<Connection> conn);
    Status RemoveConnection(const ConnectionId& conn_id);

    std::vector<std::shared_ptr<Connection>> GetAllConnections();
    size_t GetConnectionCount() const;
};
```

### 3.3 Transport Layer

**职责**: 多传输协议支持、连接建立、数据传输

**关键接口**:
```cpp
class Transport {
public:
    virtual ~Transport() = default;

    virtual Status Dial(const Multiaddr& addr,
                       std::shared_ptr<Connection>* conn) = 0;
    virtual Status Listen(const Multiaddr& addr,
                         std::shared_ptr<Listener>* listener) = 0;

    virtual std::vector<std::string> Protocols() const = 0;
};

class TcpTransport : public Transport { /* ... */ };
class UdpTransport : public Transport { /* ... */ };
class QuicTransport : public Transport { /* ... */ };
```

### 3.4 Security Layer

**职责**: 安全传输、加密、认证

**关键接口**:
```cpp
class SecureTransport {
public:
    virtual ~SecureTransport() = default;

    virtual Status SecureInbound(std::shared_ptr<Connection> conn,
                                std::shared_ptr<SecureConnection>* secure_conn) = 0;
    virtual Status SecureOutbound(std::shared_ptr<Connection> conn,
                                 const PeerId& peer_id,
                                 std::shared_ptr<SecureConnection>* secure_conn) = 0;
};

class TlsSecureTransport : public SecureTransport { /* ... */ };
class NoiseSecureTransport : public SecureTransport { /* ... */ };
```

---

## 4. 目录结构

```
p2p-cpp/
├── CMakeLists.txt              # 根 CMake 配置
├── README.md                   # 项目说明
├── LICENSE                     # MIT 许可证
│
├── include/p2p/                # 公共头文件
│   ├── core/
│   │   ├── engine.hpp
│   │   ├── connection.hpp
│   │   ├── event.hpp
│   │   └── types.hpp
│   ├── protocol/
│   │   ├── handshake.hpp
│   │   ├── channel.hpp
│   │   └── keepalive.hpp
│   ├── transport/
│   │   ├── transport.hpp
│   │   ├── tcp.hpp
│   │   ├── udp.hpp
│   │   └── quic.hpp
│   ├── nat/
│   │   ├── stun.hpp
│   │   ├── detector.hpp
│   │   └── puncher.hpp
│   ├── security/
│   │   ├── tls.hpp
│   │   ├── noise.hpp
│   │   └── dtls.hpp
│   └── utils/
│       ├── logger.hpp
│       ├── config.hpp
│       └── thread_pool.hpp
│
├── src/                        # 源代码实现
│   ├── core/
│   │   ├── CMakeLists.txt
│   │   ├── engine.cpp
│   │   ├── connection.cpp
│   │   └── event.cpp
│   ├── protocol/
│   │   ├── CMakeLists.txt
│   │   ├── handshake.cpp
│   │   └── channel.cpp
│   ├── transport/
│   │   ├── CMakeLists.txt
│   │   ├── tcp.cpp
│   │   ├── udp.cpp
│   │   └── quic.cpp
│   ├── nat/
│   │   ├── CMakeLists.txt
│   │   ├── stun.cpp
│   │   └── detector.cpp
│   ├── security/
│   │   ├── CMakeLists.txt
│   │   ├── tls.cpp
│   │   └── noise.cpp
│   ├── utils/
│   │   ├── CMakeLists.txt
│   │   ├── logger.cpp
│   │   └── config.cpp
│   ├── platform/               # 平台抽象层
│   │   ├── CMakeLists.txt
│   │   ├── linux/
│   │   ├── macos/
│   │   ├── windows/
│   │   ├── ios/
│   │   └── android/
│   ├── bindings/               # 语言绑定
│   │   ├── c/
│   │   │   ├── CMakeLists.txt
│   │   │   ├── p2p_client.h
│   │   │   └── p2p_client.cpp
│   │   ├── python/
│   │   │   ├── CMakeLists.txt
│   │   │   ├── setup.py
│   │   │   └── p2p_python.cpp
│   │   ├── java/
│   │   ├── swift/
│   │   └── javascript/
│   └── servers/                # 服务器组件
│       ├── stun/
│       │   ├── CMakeLists.txt
│       │   └── main.cpp
│       ├── relay/
│       │   ├── CMakeLists.txt
│       │   └── main.cpp
│       └── signaling/
│           ├── CMakeLists.txt
│           └── main.cpp
│
├── tests/                      # 测试
│   ├── CMakeLists.txt
│   ├── unit/
│   │   ├── test_engine.cpp
│   │   ├── test_connection.cpp
│   │   └── test_transport.cpp
│   ├── integration/
│   │   ├── test_e2e.cpp
│   │   └── test_nat.cpp
│   └── benchmark/
│       ├── bench_throughput.cpp
│       └── bench_latency.cpp
│
├── examples/                   # 示例代码
│   ├── CMakeLists.txt
│   ├── basic/
│   │   ├── simple_client.cpp
│   │   └── simple_server.cpp
│   └── advanced/
│       ├── multi_transport.cpp
│       └── custom_protocol.cpp
│
├── docs/                       # 文档
│   ├── api/
│   │   ├── core.md
│   │   ├── transport.md
│   │   └── security.md
│   ├── design/
│   │   ├── ARCHITECTURE.md     # 本文档
│   │   ├── PROTOCOL.md
│   │   └── MIGRATION.md
│   └── guides/
│       ├── getting_started.md
│       ├── building.md
│       └── integration.md
│
├── third_party/                # 第三方依赖
│   ├── CMakeLists.txt
│   ├── asio/                   # 异步 IO
│   ├── openssl/                # TLS/DTLS
│   ├── protobuf/               # 协议序列化
│   ├── spdlog/                 # 日志
│   └── googletest/             # 测试框架
│
├── cmake/                      # CMake 模块
│   ├── FindAsio.cmake
│   ├── FindOpenSSL.cmake
│   └── CompilerWarnings.cmake
│
├── scripts/                    # 构建脚本
│   ├── build.sh
│   ├── test.sh
│   ├── format.sh
│   └── package.sh
│
└── build/                      # 构建输出 (gitignore)
```

---

## 5. 依赖管理

### 5.1 核心依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| **Asio** | 1.28+ | 异步 IO、网络编程 |
| **OpenSSL** | 3.0+ | TLS/DTLS 加密 |
| **Protobuf** | 3.21+ | 协议序列化 |
| **spdlog** | 1.12+ | 高性能日志 |
| **GoogleTest** | 1.14+ | 单元测试 |
| **Benchmark** | 1.8+ | 性能测试 |

### 5.2 可选依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| **pybind11** | 2.11+ | Python 绑定 |
| **JNI** | - | Java 绑定 |
| **WebRTC** | M120+ | WebRTC 传输 |
| **QUIC** | - | QUIC 传输 |

---

## 6. 构建系统

### 6.1 CMake 配置

```bash
# 基本构建
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)

# 启用所有选项
cmake -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTS=ON \
  -DBUILD_EXAMPLES=ON \
  -DBUILD_SERVERS=ON \
  -DBUILD_BINDINGS_PYTHON=ON

# 开发模式 (启用 sanitizers)
cmake -B build \
  -DCMAKE_BUILD_TYPE=Debug \
  -DENABLE_ASAN=ON \
  -DENABLE_COVERAGE=ON
```

### 6.2 交叉编译

```bash
# Android
cmake -B build-android \
  -DCMAKE_TOOLCHAIN_FILE=$ANDROID_NDK/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a \
  -DANDROID_PLATFORM=android-24

# iOS
cmake -B build-ios \
  -DCMAKE_TOOLCHAIN_FILE=cmake/ios.toolchain.cmake \
  -DPLATFORM=OS64
```

---

## 7. 接口设计

### 7.1 C API (p2p_client.h)

```c
// 客户端创建和销毁
typedef struct p2p_client p2p_client_t;
typedef struct p2p_config p2p_config_t;

p2p_client_t* p2p_client_create(const p2p_config_t* config);
void p2p_client_destroy(p2p_client_t* client);

// 连接管理
typedef struct p2p_connection p2p_connection_t;

int p2p_client_connect(p2p_client_t* client,
                       const char* peer_id,
                       p2p_connection_t** conn);
void p2p_connection_close(p2p_connection_t* conn);

// 数据传输
int p2p_connection_send(p2p_connection_t* conn,
                        const uint8_t* data,
                        size_t len);
int p2p_connection_recv(p2p_connection_t* conn,
                        uint8_t* buffer,
                        size_t buffer_size,
                        size_t* received);

// 事件回调
typedef void (*p2p_event_callback_t)(const char* event_type,
                                     const void* event_data,
                                     void* user_data);

void p2p_client_set_event_callback(p2p_client_t* client,
                                   p2p_event_callback_t callback,
                                   void* user_data);
```

### 7.2 Python API

```python
from p2p_sdk import P2PClient, Config

# 创建客户端
config = Config(
    signaling_url="ws://localhost:8080",
    stun_server="localhost:3478"
)
client = P2PClient(config)

# 连接到对等节点
connection = await client.connect("peer-id-123")

# 发送数据
await connection.send(b"Hello, P2P!")

# 接收数据
data = await connection.receive()

# 关闭连接
await connection.close()
```

---

## 8. 迁移策略

### 8.1 迁移阶段

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| **Phase 1** | 核心引擎、传输层 | P0 |
| **Phase 2** | STUN/Relay 服务器 | P0 |
| **Phase 3** | 信令服务器 | P0 |
| **Phase 4** | Python 绑定 | P1 |
| **Phase 5** | 其他语言绑定 | P2 |

### 8.2 兼容性保证

- C API 保持稳定，遵循语义化版本
- Python API 与现有 SDK 兼容
- 协议层与 Python 版本互操作
- 配置文件格式兼容

---

## 9. 质量保证

### 9.1 测试覆盖率

- 单元测试覆盖率 ≥ 80%
- 集成测试覆盖核心流程
- 性能测试建立基线

### 9.2 代码规范

- C++20 标准
- Google C++ Style Guide
- clang-format 自动格式化
- clang-tidy 静态分析

### 9.3 CI/CD

- GitHub Actions 自动构建
- 多平台测试 (Linux/macOS/Windows)
- 自动发布二进制包

---

## 10. 性能优化

### 10.1 零拷贝

- 使用 `std::span` 避免数据拷贝
- 内存池管理
- 引用计数智能指针

### 10.2 并发优化

- 无锁数据结构
- 线程池
- 异步 IO (Asio)

### 10.3 内存优化

- 对象池
- 小对象优化
- 内存对齐

---

## 11. 安全性

### 11.1 加密

- TLS 1.3 (OpenSSL)
- Noise Protocol
- DTLS for UDP

### 11.2 认证

- Ed25519 签名
- 证书链验证
- DID 身份认证

### 11.3 防护

- 输入验证
- 缓冲区溢出防护
- 资源限制

---

## 12. 监控和日志

### 12.1 日志系统

- spdlog 高性能日志
- 分级日志 (TRACE/DEBUG/INFO/WARN/ERROR)
- 日志轮转

### 12.2 指标收集

- 连接数
- 吞吐量
- 延迟分布
- 错误率

---

## 13. 文档

### 13.1 API 文档

- Doxygen 生成
- 示例代码
- 最佳实践

### 13.2 设计文档

- 架构设计 (本文档)
- 协议规范
- 迁移指南

---

## 14. 发布计划

### 14.1 里程碑

| 版本 | 内容 | 时间 |
|------|------|------|
| **v0.1.0** | 核心引擎 + TCP 传输 | Week 2 |
| **v0.2.0** | STUN 服务器 | Week 4 |
| **v0.3.0** | Relay 服务器 | Week 6 |
| **v0.4.0** | 信令服务器 | Week 8 |
| **v0.5.0** | Python 绑定 | Week 10 |
| **v1.0.0** | 生产就绪 | Week 12 |

### 14.2 交付物

- 源代码
- 二进制库 (.so/.dylib/.dll)
- 头文件
- 文档
- 示例代码

---

## 15. 附录

### 15.1 参考资料

- [libp2p Specification](https://github.com/libp2p/specs)
- [go-libp2p Implementation](https://github.com/libp2p/go-libp2p)
- [WebRTC Specification](https://www.w3.org/TR/webrtc/)
- [STUN RFC 5389](https://tools.ietf.org/html/rfc5389)
- [TURN RFC 5766](https://tools.ietf.org/html/rfc5766)

### 15.2 术语表

| 术语 | 说明 |
|------|------|
| **P2P** | Peer-to-Peer，点对点通信 |
| **NAT** | Network Address Translation，网络地址转换 |
| **STUN** | Session Traversal Utilities for NAT |
| **TURN** | Traversal Using Relays around NAT |
| **ICE** | Interactive Connectivity Establishment |
| **SDP** | Session Description Protocol |
| **DID** | Decentralized Identifier |
| **libp2p** | 模块化网络栈 |
