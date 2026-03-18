# PeerLink - High-Performance P2P C++ Library

<div align="center">

**High-performance P2P communication library written in C++**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![C++20](https://img.shields.io/badge/C++-20-blue.svg)](https://en.cppreference.com/w/cpp/20)
[![CMake](https://img.shields.io/badge/CMake-3.20+-green.svg)](https://cmake.org/)

[Features](#-key-features) • [Quick Start](#-quick-start) • [Documentation](#-documentation)

[中文](./README-zh.md) • English

</div>

---

## 📖 Introduction

PeerLink is a high-performance C++ library for P2P communication, implementing a complete libp2p protocol stack with WebRTC integration. Built for performance-critical applications.

### Core Advantages

- 🚀 **High Performance**: 500 Mbps throughput, 20ms latency
- 🔒 **Enterprise Security**: TLS 1.3, Ed25519 signatures
- 🌐 **libp2p Compatible**: Interoperable with go-libp2p
- 🔄 **Cross-Platform**: Linux, macOS, Windows

---

## ✨ Key Features

### Protocols
- TLS 1.3, Noise (Security)
- mplex, yamux (Stream Multiplexing)
- Kademlia DHT, GossipSub
- TCP, QUIC, WebRTC, WebTransport

### NAT Traversal
- STUN, TURN, ICE
- Hole punching

---

## 🚀 Quick Start

### Prerequisites

- CMake 3.20+
- C++20 compiler (GCC 11+, Clang 14+, MSVC 2022+)
- OpenSSL 3.0+

### Build

```bash
git clone https://github.com/hbliu007/peerlink
cd peerlink/p2p-cpp

cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
```

---

## 📂 Project Structure

```
peerlink/
├── p2p-cpp/              # C++ core library
│   ├── include/
│   ├── src/
│   └── tests/
└── signaling-server-cpp/ # Signaling server
```

---

## 📄 License

MIT License - see [LICENSE](./LICENSE)

---

<div align="center">

Built with ❤️ for decentralized networking

</div>
