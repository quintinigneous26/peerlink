# P2P Platform C++

**高性能跨平台 P2P 通信引擎**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![C++20](https://img.shields.io/badge/C%2B%2B-20-blue.svg)](https://en.cppreference.com/w/cpp/20)
[![CMake](https://img.shields.io/badge/CMake-3.20+-green.svg)](https://cmake.org/)

---

## 项目简介

P2P Platform C++ 是 Python 版本的高性能重写，提供：

- 🚀 **3-5x 性能提升**: C++20 实现，零拷贝优化
- 🌐 **全平台支持**: Linux/macOS/Windows/iOS/Android
- 🔗 **多语言绑定**: Python/Java/Swift/JavaScript
- 🔒 **libp2p 兼容**: 完整协议栈实现
- 📦 **易于集成**: 简洁的 C API

---

## 快速开始

### 前置要求

- CMake 3.20+
- C++20 编译器 (GCC 11+, Clang 14+, MSVC 2022+)
- OpenSSL 3.0+
- Asio 1.28+

### 构建

```bash
# 克隆项目
git clone https://github.com/your-org/p2p-platform.git
cd p2p-platform/p2p-cpp

# 构建
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)

# 运行测试
cd build && ctest -V

# 安装
sudo cmake --install build
```

### 使用示例

#### C++ API

```cpp
#include <p2p/core/engine.hpp>

int main() {
    // 创建配置
    p2p::Config config;
    config.signaling_url = "ws://localhost:8080";
    config.stun_server = "localhost:3478";

    // 创建引擎
    auto engine = p2p::Engine::Create(config);
    engine->Start();

    // 连接到对等节点
    std::shared_ptr<p2p::Connection> conn;
    auto status = engine->Connect(p2p::PeerId("peer-123"), &conn);

    if (status.ok()) {
        // 发送数据
        std::vector<uint8_t> data = {1, 2, 3, 4};
        conn->Send(data);

        // 接收数据
        conn->ReceiveAsync([](p2p::Status status, std::span<const uint8_t> data) {
            if (status.ok()) {
                // 处理数据
            }
        });
    }

    engine->Stop();
    return 0;
}
```

#### C API

```c
#include "p2p_client.h"

int main() {
    // 创建配置
    p2p_config_t* config = p2p_config_create();
    p2p_config_set_signaling_url(config, "ws://localhost:8080");
    p2p_config_set_stun_server(config, "localhost:3478");

    // 创建客户端
    p2p_client_t* client = p2p_client_create(config);
    p2p_client_start(client);

    // 连接
    p2p_connection_t* conn;
    p2p_status_t status = p2p_client_connect(client, "peer-123", &conn);

    if (status == P2P_OK) {
        // 发送数据
        uint8_t data[] = {1, 2, 3, 4};
        p2p_connection_send(conn, data, sizeof(data));

        // 接收数据
        uint8_t buffer[1024];
        size_t received;
        p2p_connection_recv(conn, buffer, sizeof(buffer), &received);

        p2p_connection_close(conn);
    }

    p2p_client_stop(client);
    p2p_client_destroy(client);
    p2p_config_destroy(config);
    return 0;
}
```

---

## 架构设计

### 分层架构

```
Application Layer
    ↓
Language Bindings (Python/Java/Swift/JS)
    ↓
C API Layer
    ↓
C++ Core Engine
    ├── Core (Engine, Connection, Event)
    ├── Protocol (Handshake, Channel, Keepalive)
    ├── Transport (TCP, UDP, QUIC, WebRTC)
    ├── NAT (STUN, Detector, Puncher)
    ├── Security (TLS, Noise, DTLS)
    └── Utils (Logger, Config, ThreadPool)
    ↓
Platform Abstraction (Linux/macOS/Windows/iOS/Android)
```

详细设计请参考 [ARCHITECTURE.md](docs/design/ARCHITECTURE.md)

---

## 目录结构

```
p2p-cpp/
├── include/p2p/        # 公共头文件
├── src/                # 源代码实现
│   ├── core/
│   ├── protocol/
│   ├── transport/
│   ├── nat/
│   ├── security/
│   ├── utils/
│   ├── platform/
│   ├── bindings/
│   └── servers/
├── tests/              # 测试
├── examples/           # 示例代码
├── docs/               # 文档
├── third_party/        # 第三方依赖
├── cmake/              # CMake 模块
└── scripts/            # 构建脚本
```

---

## 构建选项

```bash
# 构建共享库 (默认)
cmake -B build -DBUILD_SHARED_LIBS=ON

# 构建静态库
cmake -B build -DBUILD_SHARED_LIBS=OFF

# 启用测试
cmake -B build -DBUILD_TESTS=ON

# 启用示例
cmake -B build -DBUILD_EXAMPLES=ON

# 启用服务器组件
cmake -B build -DBUILD_SERVERS=ON

# 启用 Python 绑定
cmake -B build -DBUILD_BINDINGS_PYTHON=ON

# 启用 AddressSanitizer
cmake -B build -DENABLE_ASAN=ON

# 启用代码覆盖率
cmake -B build -DENABLE_COVERAGE=ON
```

---

## 性能指标

| 指标 | C++ 版本 | Python 版本 | 提升 |
|------|----------|-------------|------|
| 本地连接延迟 | ~20ms | ~50ms | 2.5x |
| 远程连接延迟 | ~100ms | ~200ms | 2x |
| P2P 直连吞吐量 | ~500 Mbps | ~150 Mbps | 3.3x |
| 中继吞吐量 | ~50 Mbps | ~15 Mbps | 3.3x |
| 并发连接数 | 10,000+ | 500+ | 20x |
| 内存占用 | ~50MB | ~200MB | 4x |

---

## 测试

```bash
# 运行所有测试
cd build && ctest -V

# 运行单元测试
./build/tests/unit/test_engine

# 运行集成测试
./build/tests/integration/test_e2e

# 运行性能测试
./build/tests/benchmark/bench_throughput
```

---

## 文档

- [架构设计](docs/design/ARCHITECTURE.md)
- [模块接口](docs/design/MODULE_INTERFACES.md)
- [迁移指南](docs/design/MIGRATION.md)
- [API 文档](docs/api/)
- [开发指南](docs/guides/)

---

## 依赖

### 核心依赖

- [Asio](https://think-async.com/Asio/) - 异步 IO
- [OpenSSL](https://www.openssl.org/) - TLS/DTLS
- [Protobuf](https://protobuf.dev/) - 协议序列化
- [spdlog](https://github.com/gabime/spdlog) - 日志
- [GoogleTest](https://github.com/google/googletest) - 测试

### 可选依赖

- [pybind11](https://github.com/pybind/pybind11) - Python 绑定
- [WebRTC](https://webrtc.org/) - WebRTC 传输
- [QUIC](https://github.com/microsoft/msquic) - QUIC 传输

---

## 贡献

欢迎贡献！请参考 [CONTRIBUTING.md](../CONTRIBUTING.md)

---

## 许可证

MIT License - 详见 [LICENSE](../LICENSE)

---

## 联系我们

- Issues: [GitHub Issues](https://github.com/your-org/p2p-platform/issues)
- Discussions: [GitHub Discussions](https://github.com/your-org/p2p-platform/discussions)

---

**Made with ❤️ by P2P Platform Team**