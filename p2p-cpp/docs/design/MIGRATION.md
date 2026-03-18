# Python 到 C++ 迁移指南

**版本**: 1.0.0
**日期**: 2026-03-15

---

## 1. 迁移概述

### 1.1 迁移目标

| 目标 | 说明 |
|------|------|
| **性能提升** | 3-5x 吞吐量提升，2-3x 延迟降低 |
| **跨平台** | 支持 Linux/macOS/Windows/iOS/Android |
| **向后兼容** | Python API 保持兼容 |
| **协议兼容** | 与 Python 版本互操作 |

### 1.2 迁移策略

采用**渐进式迁移**策略：

1. **Phase 1**: 核心引擎 + TCP 传输
2. **Phase 2**: STUN 服务器
3. **Phase 3**: Relay 服务器
4. **Phase 4**: 信令服务器
5. **Phase 5**: Python 绑定
6. **Phase 6**: 其他语言绑定

---

## 2. 模块映射

### 2.1 Python → C++ 模块映射

| Python 模块 | C++ 模块 | 说明 |
|-------------|----------|------|
| `p2p_engine/engine.py` | `src/core/engine.cpp` | 引擎核心 |
| `p2p_engine/event.py` | `src/core/event.cpp` | 事件系统 |
| `p2p_engine/transport/tcp.py` | `src/transport/tcp.cpp` | TCP 传输 |
| `p2p_engine/transport/udp.py` | `src/transport/udp.cpp` | UDP 传输 |
| `p2p_engine/security/tls.py` | `src/security/tls.cpp` | TLS 加密 |
| `p2p_engine/nat/stun.py` | `src/nat/stun.cpp` | STUN 客户端 |
| `p2p_engine/protocol/handshake.py` | `src/protocol/handshake.cpp` | 握手协议 |
| `stun-server/` | `src/servers/stun/` | STUN 服务器 |
| `relay-server/` | `src/servers/relay/` | Relay 服务器 |
| `signaling-server/` | `src/servers/signaling/` | 信令服务器 |
| `client_sdk/` | `src/bindings/python/` | Python SDK |

---

## 3. API 映射

### 3.1 Engine API

#### Python
```python
from p2p_engine import Engine, Config

config = Config(
    signaling_url="ws://localhost:8080",
    stun_server="localhost:3478"
)

engine = Engine(config)
await engine.start()

connection = await engine.connect("peer-123")
await connection.send(b"Hello")
data = await connection.receive()

await engine.stop()
```

#### C++
```cpp
#include <p2p/core/engine.hpp>

p2p::Config config;
config.signaling_url = "ws://localhost:8080";
config.stun_server = "localhost:3478";

auto engine = p2p::Engine::Create(config);
engine->Start();

std::shared_ptr<p2p::Connection> conn;
engine->Connect(p2p::PeerId("peer-123"), &conn);

std::vector<uint8_t> data = {1, 2, 3};
conn->Send(data);

conn->ReceiveAsync([](p2p::Status status, std::span<const uint8_t> data) {
    // Handle data
});

engine->Stop();
```

---

### 3.2 Event API

#### Python
```python
from p2p_engine import EventType

def on_connection_opened(event):
    print(f"Connection opened: {event.peer_id}")

engine.event_bus.subscribe(EventType.CONNECTION_OPENED, on_connection_opened)
```

#### C++
```cpp
#include <p2p/core/event.hpp>

engine->GetEventBus().Subscribe(
    p2p::EventType::CONNECTION_OPENED,
    [](const p2p::Event& event) {
        std::cout << "Connection opened: " << event.peer_id << std::endl;
    }
);
```

---

### 3.3 Transport API

#### Python
```python
from p2p_engine.transport import TcpTransport

transport = TcpTransport()
connection = await transport.dial("/ip4/127.0.0.1/tcp/8080")
```

#### C++
```cpp
#include <p2p/transport/tcp.hpp>

auto transport = std::make_unique<p2p::TcpTransport>();
std::shared_ptr<p2p::Connection> conn;
transport->Dial(p2p::Multiaddr("/ip4/127.0.0.1/tcp/8080"), &conn);
```

---

## 4. 数据类型映射

### 4.1 基本类型

| Python | C++ | 说明 |
|--------|-----|------|
| `str` | `std::string` | 字符串 |
| `bytes` | `std::vector<uint8_t>` | 字节数组 |
| `int` | `int64_t` | 整数 |
| `float` | `double` | 浮点数 |
| `bool` | `bool` | 布尔值 |
| `None` | `std::nullopt` | 空值 |
| `List[T]` | `std::vector<T>` | 列表 |
| `Dict[K, V]` | `std::unordered_map<K, V>` | 字典 |

### 4.2 自定义类型

| Python | C++ | 说明 |
|--------|-----|------|
| `PeerId` | `p2p::PeerId` | 节点 ID |
| `Multiaddr` | `p2p::Multiaddr` | 多地址 |
| `ConnectionId` | `p2p::ConnectionId` | 连接 ID |
| `Status` | `p2p::Status` | 状态码 |
| `Event` | `p2p::Event` | 事件 |

---

## 5. 异步模型映射

### 5.1 Python asyncio → C++ Asio

#### Python
```python
async def connect_and_send():
    connection = await engine.connect("peer-123")
    await connection.send(b"Hello")
    data = await connection.receive()
    return data
```

#### C++
```cpp
void connect_and_send() {
    std::shared_ptr<p2p::Connection> conn;
    engine->Connect(p2p::PeerId("peer-123"), &conn);

    std::vector<uint8_t> data = {1, 2, 3};
    conn->Send(data);

    conn->ReceiveAsync([](p2p::Status status, std::span<const uint8_t> data) {
        // Handle data
    });
}
```

---

## 6. 错误处理映射

### 6.1 Python 异常 → C++ Status

#### Python
```python
try:
    connection = await engine.connect("peer-123")
except ConnectionError as e:
    print(f"Connection failed: {e}")
```

#### C++
```cpp
std::shared_ptr<p2p::Connection> conn;
auto status = engine->Connect(p2p::PeerId("peer-123"), &conn);

if (!status.ok()) {
    std::cerr << "Connection failed: " << status.message() << std::endl;
}
```

---

## 7. 配置映射

### 7.1 Python Config → C++ Config

#### Python
```python
config = Config(
    signaling_url="ws://localhost:8080",
    stun_server="localhost:3478",
    relay_servers=["localhost:50000"],
    max_connections=1000,
    enable_relay=True
)
```

#### C++
```cpp
p2p::Config config;
config.signaling_url = "ws://localhost:8080";
config.stun_server = "localhost:3478";
config.relay_servers = {"localhost:50000"};
config.max_connections = 1000;
config.enable_relay = true;
```

---

## 8. 测试迁移

### 8.1 pytest → GoogleTest

#### Python
```python
import pytest
from p2p_engine import Engine

@pytest.mark.asyncio
async def test_engine_start():
    engine = Engine(Config())
    await engine.start()
    assert engine.is_running()
    await engine.stop()
```

#### C++
```cpp
#include <gtest/gtest.h>
#include <p2p/core/engine.hpp>

TEST(EngineTest, Start) {
    p2p::Config config;
    auto engine = p2p::Engine::Create(config);

    auto status = engine->Start();
    EXPECT_TRUE(status.ok());

    engine->Stop();
}
```

---

## 9. 性能优化

### 9.1 零拷贝

#### Python (拷贝)
```python
data = b"Hello, World!"
await connection.send(data)  # 拷贝数据
```

#### C++ (零拷贝)
```cpp
std::vector<uint8_t> data = {1, 2, 3, 4};
conn->Send(std::span(data));  // 零拷贝，使用 span
```

### 9.2 内存池

#### Python (GC)
```python
# Python 使用垃圾回收
data = bytearray(1024)
```

#### C++ (对象池)
```cpp
// C++ 使用对象池
auto buffer = buffer_pool.Allocate(1024);
// ... use buffer ...
buffer_pool.Deallocate(buffer);
```

---

## 10. 迁移检查清单

### 10.1 功能完整性

- [ ] 核心引擎功能
- [ ] 传输层 (TCP/UDP/QUIC)
- [ ] 安全层 (TLS/Noise)
- [ ] NAT 穿透 (STUN/Hole Punching)
- [ ] 协议层 (Handshake/Channel/Keepalive)
- [ ] 事件系统
- [ ] 日志系统
- [ ] 配置管理

### 10.2 性能指标

- [ ] 延迟 < Python 版本 50%
- [ ] 吞吐量 > Python 版本 3x
- [ ] 内存占用 < Python 版本 25%
- [ ] 并发连接数 > Python 版本 10x

### 10.3 兼容性

- [ ] 协议兼容 (与 Python 版本互操作)
- [ ] API 兼容 (Python 绑定)
- [ ] 配置兼容 (配置文件格式)

### 10.4 质量保证

- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 集成测试通过
- [ ] 性能测试通过
- [ ] 内存泄漏检测通过 (Valgrind/ASAN)
- [ ] 线程安全检测通过 (TSAN)

---

## 11. 迁移时间表

| 阶段 | 内容 | 时间 | 负责人 |
|------|------|------|--------|
| **Week 1-2** | 核心引擎 + TCP 传输 | 2 weeks | Core Team |
| **Week 3-4** | STUN 服务器 | 2 weeks | STUN Team |
| **Week 5-6** | Relay 服务器 | 2 weeks | Relay Team |
| **Week 7-8** | 信令服务器 | 2 weeks | Signaling Team |
| **Week 9-10** | Python 绑定 | 2 weeks | SDK Team |
| **Week 11-12** | 测试和优化 | 2 weeks | QA Team |

---

## 12. 风险和缓解

### 12.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 性能不达标 | 高 | 早期性能测试，持续优化 |
| 协议不兼容 | 高 | 互操作性测试 |
| 内存泄漏 | 中 | ASAN/Valgrind 检测 |
| 线程安全问题 | 中 | TSAN 检测，代码审查 |

### 12.2 项目风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 时间延期 | 中 | 分阶段交付，优先级管理 |
| 人员不足 | 中 | 提前招聘，知识转移 |
| 需求变更 | 低 | 敏捷开发，快速迭代 |

---

## 13. 参考资料

### 13.1 C++ 资源

- [C++20 Reference](https://en.cppreference.com/w/cpp/20)
- [Asio Documentation](https://think-async.com/Asio/asio-1.28.0/doc/)
- [OpenSSL Documentation](https://www.openssl.org/docs/)
- [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html)

### 13.2 libp2p 资源

- [libp2p Specification](https://github.com/libp2p/specs)
- [go-libp2p](https://github.com/libp2p/go-libp2p)
- [rust-libp2p](https://github.com/libp2p/rust-libp2p)

### 13.3 Python 项目

- [Python 项目文档](../../docs/)
- [Python API 文档](../../docs/api-spec.md)
- [Python 架构文档](../../docs/architecture.md)

---

## 14. 附录

### 14.1 代码风格对比

#### Python (PEP 8)
```python
class ConnectionManager:
    def __init__(self, max_connections: int):
        self._connections: Dict[str, Connection] = {}
        self._max_connections = max_connections

    async def add_connection(self, peer_id: str, conn: Connection) -> None:
        if len(self._connections) >= self._max_connections:
            raise ValueError("Max connections reached")
        self._connections[peer_id] = conn
```

#### C++ (Google Style)
```cpp
class ConnectionManager {
 public:
  explicit ConnectionManager(size_t max_connections)
      : max_connections_(max_connections) {}

  Status AddConnection(const PeerId& peer_id,
                      std::shared_ptr<Connection> conn) {
    if (connections_.size() >= max_connections_) {
      return Status::Error(StatusCode::ERROR_ALREADY_EXISTS,
                          "Max connections reached");
    }
    connections_[peer_id] = std::move(conn);
    return Status::OK();
  }

 private:
  std::unordered_map<PeerId, std::shared_ptr<Connection>> connections_;
  size_t max_connections_;
};
```

### 14.2 构建系统对比

#### Python (setup.py)
```python
from setuptools import setup, find_packages

setup(
    name="p2p-platform",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.8.0",
        "cryptography>=41.0.0",
    ],
)
```

#### C++ (CMakeLists.txt)
```cmake
cmake_minimum_required(VERSION 3.20)
project(P2P_Platform VERSION 1.0.0)

set(CMAKE_CXX_STANDARD 20)

find_package(OpenSSL REQUIRED)
find_package(Asio REQUIRED)

add_library(p2p_platform
    src/core/engine.cpp
    src/core/connection.cpp
)

target_link_libraries(p2p_platform
    OpenSSL::SSL
    Asio::Asio
)
```

---

**迁移完成后，C++ 版本将提供更高的性能、更好的跨平台支持和更灵活的语言绑定！**