# PeerLink - 高性能 P2P C++ 库

<div align="center">

**高性能 P2P 通信库 (C++)**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![C++20](https://img.shields.io/badge/C++-20-blue.svg)](https://en.cppreference.com/w/cpp/20)
[![CMake](https://img.shields.io/badge/CMake-3.20+-green.svg)](https://cmake.org/)

[特性](#-主要特性) • [快速开始](#-快速开始) • [文档](#-文档)

English • [中文](./README.md)

</div>

---

## 📖 项目简介

PeerLink 是一个高性能的 C++ P2P 通信库，实现了完整的 libp2p 协议栈和 WebRTC 集成。

### 核心优势

- 🚀 **高性能**: 500 Mbps 吞吐量, 20ms 延迟
- 🔒 **企业级安全**: TLS 1.3, Ed25519 签名
- 🌐 **libp2p 兼容**: 与 go-libp2p 互操作
- 🔄 **跨平台**: Linux, macOS, Windows

---

## ✨ 主要特性

### 协议
- TLS 1.3, Noise (安全传输)
- mplex, yamux (流复用)
- Kademlia DHT, GossipSub
- TCP, QUIC, WebRTC, WebTransport

### NAT 穿透
- STUN, TURN, ICE
- 端口打洞

---

## 🚀 快速开始

### 前置要求

- CMake 3.20+
- C++20 编译器 (GCC 11+, Clang 14+, MSVC 2022+)
- OpenSSL 3.0+

### 构建

```bash
git clone https://github.com/hbliu007/peerlink
cd peerlink/p2p-cpp

cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
```

---

## 📂 项目结构

```
peerlink/
├── p2p-cpp/              # C++ 核心库
│   ├── include/
│   ├── src/
│   └── tests/
└── signaling-server-cpp/ # 信令服务器
```

---

## 📄 许可证

MIT License - 见 [LICENSE](./LICENSE)

---

<div align="center">

❤️ 为去中心化网络而生

</div>
