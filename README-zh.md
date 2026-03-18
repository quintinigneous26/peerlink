# PeerLink

<div align="center">

![PeerLink Logo](https://raw.githubusercontent.com/hbliu007/peerlink/main/.github/logo.svg)

### 高性能 P2P 通信库

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![C++20](https://img.shields.io/badge/C++-20-blue.svg)](https://en.cppreference.com/w/cpp/20)
[![CMake](https://img.shields.io/badge/CMake-3.20+-green.svg)](https://cmake.org/)
[![Platform](https://img.shields.io/badge/平台-Linux%20%7C%20macOS%20%7C%20Windows-white.svg)](https://github.com/hbliu007/peerlink)
[![Stars](https://img.shields.io/github/stars/hbliu007/peerlink?style=social)](https://github.com/hbliu007/peerlink)
[![Contributors](https://img.shields.io/github/contributors/hbliu007/peerlink)](https://github.com/hbliu007/peerlink/graphs/contributors)

---

**[快速开始](#快速开始)** • **[功能特性](#功能特性)** • **[架构](#架构)** • **[文档](#文档)** • **[贡献](#贡献)**

[English](./README.md) • [中文](./README-zh.md)

</div>

---

## 什么是 PeerLink?

PeerLink 是一个**高性能 C++ 库**，用于构建点对点应用程序。它实现了完整的 libp2p 兼容协议栈，支持 WebRTC，可实现浏览器到浏览器、设备到设备的直接通信。

## 为什么选择 PeerLink?

| 特性 | PeerLink | 其他方案 |
|------|----------|----------|
| 🚀 性能 | 500 Mbps, 20ms 延迟 | 参差不齐 |
| 🌐 WebRTC 原生 | ✅ 内置 | 通常需要额外工作 |
| 🔒 安全性 | TLS 1.3 + Noise | 基础 |
| 🔄 跨平台 | Linux/macOS/Windows/iOS/Android | 有限 |
| 📦 零拷贝 | ✅ 优化 | 罕见 |

---

## 快速开始

### 前置要求

- CMake 3.20+
- C++20 编译器 (GCC 11+, Clang 14+, MSVC 2022+)
- OpenSSL 3.0+

### 构建

```bash
git clone https://github.com/hbliu007/peerlink
cd peerlink/p2p-cpp

# 配置
cmake -B build -DCMAKE_BUILD_TYPE=Release

# 编译
cmake --build build -j$(nproc)

# 运行测试
cd build && ctest -V
```

### 使用示例

```cpp
#include <p2p/engine.hpp>

int main() {
    // 创建配置
    p2p::Config config;
    config.listen_addresses = {"/ip4/0.0.0.0/tcp/0"};
    config.enable_webrtc = true;

    // 创建并启动引擎
    auto engine = p2p::Engine::Create(config);
    engine->Start();

    // 连接到对等节点
    auto conn = engine->Connect(p2p::PeerId::FromString("QmPeer..."));

    // 发送数据
    conn->Send("Hello, P2P!");

    engine->Stop();
    return 0;
}
```

---

## 功能特性

### 🔐 安全协议
- TLS 1.3 (`/tls/1.0.0`)
- Noise 协议 (`/noise`)

### 🔀 流复用
- mplex (`/mplex/6.7.0`)
- yamux (`/yamux/1.0.0`)

### 🌐 传输层
| 协议 | 描述 |
|------|------|
| TCP | IPv4/IPv6 |
| QUIC | UDP 多路复用 |
| WebRTC | 浏览器到浏览器 |
| WebTransport | HTTP/3 |

### 🧭 路由
| 协议 | 描述 |
|------|------|
| Kademlia DHT | 分布式哈希表 |
| Bootstrap Nodes | 初始节点发现 |

### 📢 发布订阅
| 协议 | 描述 |
|------|------|
| GossipSub v1.1 | 可扩展发布订阅 |

### 🔓 NAT 穿透
| 方法 | 描述 |
|------|------|
| STUN | NAT 类型检测 |
| TURN | 中继回退 |
| ICE | 候选地址收集 |
| Hole Punching | 打洞直连 |

---

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                      应用层                               │
├─────────────────────────────────────────────────────────┤
│  Python 绑定  │  Go 绑定  │  Swift/ObjC                │
├─────────────────────────────────────────────────────────┤
│                      C API 层                             │
├─────────────────────────────────────────────────────────┤
│                     核心引擎                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  │
│  │   身份      │ │   传输      │ │    流复用       │  │
│  └─────────────┘ └─────────────┘ └─────────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  │
│  │   安全      │ │  节点存储   │ │   DHT/PubSub   │  │
│  └─────────────┘ └─────────────┘ └─────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                   平台抽象层                              │
│      Linux      │     macOS     │    Windows          │
└─────────────────────────────────────────────────────────┘
```

---

## 性能指标

| 指标 | 数值 |
|------|------|
| P2P 吞吐量 | 500 Mbps |
| 连接延迟 | 20ms |
| 并发连接数 | 10,000+ |
| 内存占用 | 50 MB |

---

## 文档

- [架构设计](./p2p-cpp/docs/ARCHITECTURE.md)
- [API 参考](./p2p-cpp/docs/API.md)
- [示例代码](./p2p-cpp/examples/)

---

## 贡献

欢迎贡献！请阅读我们的 [贡献指南](./CONTRIBUTING.md) 了解更多。

```bash
# Fork 并克隆
git clone https://github.com/hbliu007/peerlink

# 创建特性分支
git checkout -b feature/awesome-feature

# 修改并测试
cmake -B build -DBUILD_TESTS=ON
cmake --build build

# 提交并推送
git commit -m "feat: add awesome feature"
git push origin feature/awesome-feature
```

---

## 许可证

PeerLink 使用 [MIT 许可证](./LICENSE)。

---

## 相关项目

- [libp2p/go-libp2p](https://github.com/libp2p/go-libp2p) - Go 实现
- [libp2p/js-libp2p](https://github.com/libp2p/js-libp2p) - JavaScript 实现

---

<div align="center">

**❤️ 为去中心化网络而生**

[![GitHub Stars](https://img.shields.io/github/stars/hbliu007/peerlink?style=social)](https://github.com/hbliu007/peerlink)

</div>
