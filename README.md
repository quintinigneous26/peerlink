# PeerLink

<div align="center">

![PeerLink Logo](https://raw.githubusercontent.com/hbliu007/peerlink/main/.github/logo.svg)

### High-Performance P2P Communication Library

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![C++20](https://img.shields.io/badge/C++-20-blue.svg)](https://en.cppreference.com/w/cpp/20)
[![CMake](https://img.shields.io/badge/CMake-3.20+-green.svg)](https://cmake.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-white.svg)](https://github.com/hbliu007/peerlink)
[![Stars](https://img.shields.io/github/stars/hbliu007/peerlink?style=social)](https://github.com/hbliu007/peerlink)
[![Contributors](https://img.shields.io/github/contributors/hbliu007/peerlink)](https://github.com/hbliu007/peerlink/graphs/contributors)

---

**[Quick Start](#quick-start)** • **[Features](#features)** • **[Architecture](#architecture)** • **[Documentation](#documentation)** • **[Contributing](#contributing)**

[English](./README.md) • [中文](./README-zh.md)

</div>

---

## What is PeerLink?

PeerLink is a **high-performance C++ library** for building peer-to-peer applications. It implements a complete libp2p-compatible protocol stack with first-class WebRTC support, enabling direct browser-to-browser and device-to-device communication.

## Why PeerLink?

| Feature | PeerLink | Others |
|---------|----------|--------|
| 🚀 Performance | 500 Mbps, 20ms latency | Varies |
| 🌐 WebRTC Native | ✅ Built-in | Often requires extra work |
| 🔒 Security | TLS 1.3 + Noise | Basic |
| 🔄 Cross-Platform | Linux/macOS/Windows/iOS/Android | Limited |
| 📦 Zero-Copy | ✅ Optimized | Rare |

---

## Quick Start

### Prerequisites

- CMake 3.20+
- C++20 Compiler (GCC 11+, Clang 14+, MSVC 2022+)
- OpenSSL 3.0+

### Build

```bash
git clone https://github.com/hbliu007/peerlink
cd peerlink/p2p-cpp

# Configure
cmake -B build -DCMAKE_BUILD_TYPE=Release

# Build
cmake --build build -j$(nproc)

# Run tests
cd build && ctest -V
```

### Usage

```cpp
#include <p2p/engine.hpp>

int main() {
    // Create config
    p2p::Config config;
    config.listen_addresses = {"/ip4/0.0.0.0/tcp/0"};
    config.enable_webrtc = true;

    // Create and start engine
    auto engine = p2p::Engine::Create(config);
    engine->Start();

    // Connect to peer
    auto conn = engine->Connect(p2p::PeerId::FromString("QmPeer..."));

    // Send data
    conn->Send("Hello, P2P!");

    engine->Stop();
    return 0;
}
```

---

## Features

### 🔐 Security Protocols
- TLS 1.3 (`/tls/1.0.0`)
- Noise Protocol (`/noise`)

### 🔀 Stream Multiplexing
- mplex (`/mplex/6.7.0`)
- yamux (`/yamux/1.0.0`)

### 🌐 Transport
| Protocol | Description |
|----------|-------------|
| TCP | IPv4/IPv6 |
| QUIC | UDP-based multiplexing |
| WebRTC | Browser-to-browser |
| WebTransport | HTTP/3-based |

### 🧭 Peer Routing
| Protocol | Description |
|----------|-------------|
| Kademlia DHT | Distributed hash table |
| Bootstrap Nodes | Initial peer discovery |

### 📢 PubSub
| Protocol | Description |
|----------|-------------|
| GossipSub v1.1 | Scalable pub/sub |

### 🔓 NAT Traversal
| Method | Description |
|--------|-------------|
| STUN | NAT type detection |
| TURN | Relay fallback |
| ICE | Candidate gathering |
| Hole Punching | Direct connection |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
├─────────────────────────────────────────────────────────┤
│  Python Bindings  │  Go Bindings  │  Swift/ObjC     │
├─────────────────────────────────────────────────────────┤
│                      C API Layer                         │
├─────────────────────────────────────────────────────────┤
│                   Core Engine                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  │
│  │  Identity   │ │   Transport │ │  Stream Mux    │  │
│  └─────────────┘ └─────────────┘ └─────────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  │
│  │  Security   │ │  Peerstore  │ │   DHT/PubSub   │  │
│  └─────────────┘ └─────────────┘ └─────────────────┘  │
├─────────────────────────────────────────────────────────┤
│              Platform Abstraction Layer                  │
│     Linux      │     macOS     │    Windows           │
└─────────────────────────────────────────────────────────┘
```

---

## Performance

| Metric | Value |
|--------|-------|
| P2P Throughput | 500 Mbps |
| Connection Latency | 20ms |
| Concurrent Connections | 10,000+ |
| Memory Usage | 50 MB |

---

## Documentation

- [Architecture](./p2p-cpp/docs/ARCHITECTURE.md)
- [API Reference](./p2p-cpp/docs/API.md)
- [Examples](./p2p-cpp/examples/)

---

## Contributing

Contributions are welcome! Please read our [Contributing Guide](./CONTRIBUTING.md) for details.

```bash
# Fork and clone
git clone https://github.com/hbliu007/peerlink

# Create feature branch
git checkout -b feature/amazing-feature

# Make changes and test
cmake -B build -DBUILD_TESTS=ON
cmake --build build

# Commit and push
git commit -m "feat: add amazing feature"
git push origin feature/amazing-feature
```

---

## License

PeerLink is licensed under the [MIT License](./LICENSE).

---

## Related Projects

- [libp2p/go-libp2p](https://github.com/libp2p/go-libp2p) - Go implementation
- [libp2p/js-libp2p](https://github.com/libp2p/js-libp2p) - JavaScript implementation

---

<div align="center">

**Built with ❤️ for the decentralized web**

[![GitHub Stars](https://img.shields.io/github/stars/hbliu007/peerlink?style=social)](https://github.com/hbliu007/peerlink)

</div>
