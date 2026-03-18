# 模块接口定义

## 1. Core 模块

### 1.1 Engine (引擎核心)

**职责**: 引擎生命周期管理、连接协调、事件分发

**头文件**: `include/p2p/core/engine.hpp`

**关键接口**:
```cpp
class Engine {
public:
    static std::unique_ptr<Engine> Create(const Config& config);

    Status Start();
    Status Stop();

    Status Connect(const PeerId& peer_id, std::shared_ptr<Connection>* conn);
    Status Listen(const Multiaddr& addr, std::shared_ptr<Listener>* listener);

    Status RegisterProtocol(const std::string& protocol_id,
                           std::unique_ptr<ProtocolHandler> handler);

    EventBus& GetEventBus();
    std::vector<std::shared_ptr<Connection>> GetConnections();
    std::shared_ptr<Connection> GetConnection(const PeerId& peer_id);
};
```

**依赖**:
- Transport 层 (TCP/UDP/QUIC)
- Security 层 (TLS/Noise)
- NAT 层 (STUN/Hole Punching)

---

### 1.2 Connection (连接管理)

**职责**: 连接抽象、数据传输、状态管理

**头文件**: `include/p2p/core/connection.hpp`

**关键接口**:
```cpp
class Connection {
public:
    ConnectionId GetId() const;
    const PeerId& GetPeerId() const;
    ConnectionState GetState() const;

    Status Send(std::span<const uint8_t> data);
    void ReceiveAsync(ReceiveCallback callback);
    Status Close();

    Multiaddr GetLocalAddr() const;
    Multiaddr GetRemoteAddr() const;
};
```

**状态机**:
```
CONNECTING → CONNECTED → DISCONNECTING → DISCONNECTED
     ↓                        ↓
   ERROR ←──────────────────ERROR
```

---

### 1.3 EventBus (事件系统)

**职责**: 事件发布订阅、异步通知

**头文件**: `include/p2p/core/event.hpp`

**关键接口**:
```cpp
class EventBus {
public:
    void Subscribe(EventType type, EventCallback callback);
    void Publish(const Event& event);
    void UnsubscribeAll();
};
```

**事件类型**:
- `CONNECTION_OPENED`: 连接建立
- `CONNECTION_CLOSED`: 连接关闭
- `CONNECTION_ERROR`: 连接错误
- `DATA_RECEIVED`: 数据接收
- `PEER_DISCOVERED`: 节点发现
- `NAT_TYPE_DETECTED`: NAT 类型检测完成

---

## 2. Transport 模块

### 2.1 Transport (传输抽象)

**职责**: 传输层抽象、多协议支持

**头文件**: `include/p2p/transport/transport.hpp`

**关键接口**:
```cpp
class Transport {
public:
    virtual Status Dial(const Multiaddr& addr,
                       std::shared_ptr<Connection>* conn) = 0;
    virtual Status Listen(const Multiaddr& addr,
                         std::shared_ptr<Listener>* listener) = 0;
    virtual std::vector<std::string> Protocols() const = 0;
};
```

**实现类**:
- `TcpTransport`: TCP 传输
- `UdpTransport`: UDP 传输
- `QuicTransport`: QUIC 传输
- `WebRtcTransport`: WebRTC 传输

---

### 2.2 TcpTransport

**头文件**: `include/p2p/transport/tcp.hpp`

**特性**:
- 可靠传输
- 流式数据
- 支持 IPv4/IPv6

**配置**:
```cpp
struct TcpConfig {
    bool enable_keepalive = true;
    uint32_t keepalive_interval_sec = 30;
    uint32_t connect_timeout_sec = 10;
};
```

---

### 2.3 UdpTransport

**头文件**: `include/p2p/transport/udp.hpp`

**特性**:
- 无连接
- 低延迟
- 支持 NAT 穿透

---

### 2.4 QuicTransport

**头文件**: `include/p2p/transport/quic.hpp`

**特性**:
- 基于 UDP
- 内置加密 (TLS 1.3)
- 多路复用
- 0-RTT 连接

---

## 3. Security 模块

### 3.1 SecureTransport (安全传输)

**职责**: 加密、认证、安全通道建立

**头文件**: `include/p2p/security/secure_transport.hpp`

**关键接口**:
```cpp
class SecureTransport {
public:
    virtual Status SecureInbound(std::shared_ptr<Connection> conn,
                                std::shared_ptr<SecureConnection>* secure_conn) = 0;
    virtual Status SecureOutbound(std::shared_ptr<Connection> conn,
                                 const PeerId& peer_id,
                                 std::shared_ptr<SecureConnection>* secure_conn) = 0;
};
```

**实现类**:
- `TlsSecureTransport`: TLS 1.3
- `NoiseSecureTransport`: Noise Protocol
- `DtlsSecureTransport`: DTLS (for UDP)

---

### 3.2 TLS 1.3

**头文件**: `include/p2p/security/tls.hpp`

**特性**:
- OpenSSL 3.0+
- Ed25519 证书
- 完整证书链验证
- 0-RTT 支持

**配置**:
```cpp
struct TlsConfig {
    std::string cert_path;
    std::string key_path;
    std::string ca_path;
    bool verify_peer = true;
};
```

---

### 3.3 Noise Protocol

**头文件**: `include/p2p/security/noise.hpp`

**特性**:
- libp2p 兼容
- XX handshake pattern
- Curve25519 密钥交换
- ChaCha20-Poly1305 加密

---

## 4. NAT 模块

### 4.1 StunClient (STUN 客户端)

**职责**: 获取公网地址、NAT 类型检测

**头文件**: `include/p2p/nat/stun.hpp`

**关键接口**:
```cpp
class StunClient {
public:
    Status GetPublicAddr(const std::string& stun_server,
                        Multiaddr* public_addr);
    Status DetectNatType(const std::string& stun_server,
                        NatType* nat_type);
};
```

**NAT 类型**:
```cpp
enum class NatType {
    UNKNOWN,
    OPEN_INTERNET,
    FULL_CONE,
    RESTRICTED_CONE,
    PORT_RESTRICTED_CONE,
    SYMMETRIC
};
```

---

### 4.2 HolePuncher (打孔器)

**职责**: NAT 穿透、UDP 打孔

**头文件**: `include/p2p/nat/puncher.hpp`

**关键接口**:
```cpp
class HolePuncher {
public:
    Status Punch(const Multiaddr& local_addr,
                const Multiaddr& remote_addr,
                std::shared_ptr<Connection>* conn);
};
```

**策略**:
- 同时打孔 (Simultaneous Open)
- 端口预测
- 多路径尝试

---

## 5. Protocol 模块

### 5.1 Handshake Protocol

**职责**: 连接握手、协议协商

**头文件**: `include/p2p/protocol/handshake.hpp`

**流程**:
```
Client                    Server
  │                         │
  ├──── HELLO ─────────────>│
  │                         │
  │<──── HELLO_ACK ─────────┤
  │                         │
  ├──── AUTH ──────────────>│
  │                         │
  │<──── AUTH_ACK ──────────┤
  │                         │
  │      CONNECTED          │
```

---

### 5.2 Channel Protocol

**职责**: 多路复用、流管理

**头文件**: `include/p2p/protocol/channel.hpp`

**关键接口**:
```cpp
class ChannelManager {
public:
    Status OpenChannel(const std::string& protocol_id,
                      std::shared_ptr<Channel>* channel);
    Status AcceptChannel(std::shared_ptr<Channel>* channel);
    Status CloseChannel(uint32_t channel_id);
};
```

---

### 5.3 Keepalive Protocol

**职责**: 连接保活、心跳检测

**头文件**: `include/p2p/protocol/keepalive.hpp`

**配置**:
```cpp
struct KeepaliveConfig {
    uint32_t interval_sec = 30;
    uint32_t timeout_sec = 90;
    uint32_t max_retries = 3;
};
```

---

## 6. Utils 模块

### 6.1 Logger (日志系统)

**职责**: 结构化日志、性能日志

**头文件**: `include/p2p/utils/logger.hpp`

**关键接口**:
```cpp
class Logger {
public:
    static Logger& GetInstance();

    void SetLevel(LogLevel level);
    void SetOutput(const std::string& file_path);

    void Trace(const std::string& message);
    void Debug(const std::string& message);
    void Info(const std::string& message);
    void Warn(const std::string& message);
    void Error(const std::string& message);
};
```

**日志级别**:
```cpp
enum class LogLevel {
    TRACE,
    DEBUG,
    INFO,
    WARN,
    ERROR,
    OFF
};
```

---

### 6.2 Config (配置管理)

**职责**: 配置加载、验证

**头文件**: `include/p2p/utils/config.hpp`

**支持格式**:
- JSON
- YAML
- TOML

---

### 6.3 ThreadPool (线程池)

**职责**: 任务调度、并发控制

**头文件**: `include/p2p/utils/thread_pool.hpp`

**关键接口**:
```cpp
class ThreadPool {
public:
    explicit ThreadPool(size_t num_threads);

    template<typename F>
    auto Submit(F&& task) -> std::future<decltype(task())>;

    void Shutdown();
};
```

---

## 7. Platform 模块

### 7.1 Platform Abstraction

**职责**: 平台差异抽象

**头文件**: `include/p2p/platform/platform.hpp`

**抽象接口**:
- Socket 操作
- 线程管理
- 文件 IO
- 时间获取

**平台实现**:
- `src/platform/linux/`
- `src/platform/macos/`
- `src/platform/windows/`
- `src/platform/ios/`
- `src/platform/android/`

---

## 8. 模块依赖关系

```
┌─────────────────────────────────────────────────────────┐
│                      Application                        │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                      Engine Core                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │Connection│  │ EventBus │  │ Protocol │              │
│  │ Manager  │  │          │  │ Handler  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
         │                │                │
         ├────────────────┼────────────────┤
         │                │                │
┌────────▼────────┐ ┌────▼────────┐ ┌────▼────────┐
│   Transport     │ │  Security   │ │    NAT      │
│  ┌──────────┐   │ │ ┌──────────┐│ │┌──────────┐ │
│  │   TCP    │   │ │ │   TLS    ││ ││   STUN   │ │
│  │   UDP    │   │ │ │  Noise   ││ ││  Puncher │ │
│  │   QUIC   │   │ │ │   DTLS   ││ ││          │ │
│  └──────────┘   │ │ └──────────┘│ │└──────────┘ │
└─────────────────┘ └─────────────┘ └─────────────┘
         │                │                │
         └────────────────┼────────────────┘
                          │
                ┌─────────▼─────────┐
                │     Platform      │
                │   Abstraction     │
                └───────────────────┘
```

---

## 9. 接口稳定性保证

### 9.1 C++ API

- 使用 `pimpl` 模式隐藏实现细节
- 虚函数接口保持稳定
- 新功能通过新接口添加

### 9.2 C API

- 严格遵循语义化版本
- 不破坏 ABI 兼容性
- 废弃接口保留至少 2 个大版本

### 9.3 语言绑定

- Python: 遵循 PEP 8
- Java: 遵循 Java 命名规范
- Swift: 遵循 Swift API 设计指南

---

## 10. 性能考虑

### 10.1 零拷贝

- 使用 `std::span` 传递数据
- 避免不必要的内存分配
- 引用计数智能指针

### 10.2 异步 IO

- 基于 Asio 的异步模型
- 回调和 Future 两种风格
- 避免阻塞操作

### 10.3 内存管理

- 对象池
- 内存池
- 小对象优化

---

## 11. 错误处理

### 11.1 错误码

- 使用 `Status` 类封装错误
- 错误码和错误消息
- 支持错误链

### 11.2 异常

- C++ 内部可以使用异常
- C API 不抛出异常
- 语言绑定转换为对应语言的异常

---

## 12. 线程安全

### 12.1 线程模型

- 单线程事件循环 (Asio)
- 线程池处理 CPU 密集任务
- 无锁数据结构

### 12.2 同步原语

- `std::mutex`
- `std::shared_mutex`
- `std::atomic`

---

## 13. 测试接口

### 13.1 Mock 接口

- 所有接口都可 Mock
- 依赖注入
- 测试辅助类

### 13.2 测试工具

- GoogleTest
- GoogleMock
- Benchmark

---

## 14. 文档生成

### 14.1 Doxygen

- 所有公共接口都有文档注释
- 示例代码
- 参数说明

### 14.2 示例代码

- `examples/basic/`: 基础示例
- `examples/advanced/`: 高级示例
- 每个模块都有示例

---

## 15. 版本兼容性

### 15.1 语义化版本

- MAJOR.MINOR.PATCH
- MAJOR: 不兼容的 API 变更
- MINOR: 向后兼容的功能新增
- PATCH: 向后兼容的 bug 修复

### 15.2 废弃策略

- 废弃接口标记 `[[deprecated]]`
- 提供迁移指南
- 至少保留 2 个大版本