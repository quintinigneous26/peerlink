# PeerLink - High-Performance P2P Communication Platform

<div align="center">

**Decentralized P2P Communication Platform with WebRTC and libp2p**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![C++20](https://img.shields.io/badge/C++-20-blue.svg)](https://en.cppreference.com/w/cpp/20)
[![Test Coverage](https://img.shields.io/badge/coverage-80%25+-green.svg)](./docs/TESTING.md)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](./docker-compose.yml)

[Features](#-key-features) • [Quick Start](#-quick-start) • [Installation](#-installation) • [Documentation](#-documentation) • [Contributing](#-contributing)

[中文](./README-zh.md) • English

</div>

---

## 📖 Introduction

PeerLink is a high-performance decentralized P2P communication platform that implements a complete libp2p protocol stack with deep WebRTC integration. It provides end-to-end capabilities including NAT traversal, peer discovery, secure transport, and stream multiplexing for building high-performance, scalable P2P applications.

### Core Advantages

- 🚀 **High Performance**: P2P direct throughput ~500 Mbps (C++), local connection latency ~20ms
- 🔒 **Enterprise Security**: TLS 1.3 encryption, Ed25519 signatures, complete certificate chain validation
- 🌐 **libp2p Compatible**: Full protocol stack implementation, interoperable with go-libp2p
- 📦 **Ready to Deploy**: Docker Compose one-click deployment, supports RPM/DEB/pip installation
- 🧪 **Well Tested**: 575 test cases, 95.1% pass rate, ≥80% code coverage
- 🛠️ **Easy Integration**: Clean client SDK, supports Python/Go/Rust/JavaScript

---

## ✨ Key Features

### Core Services

| Service | Function | Port |
|---------|----------|------|
| **STUN Server** | NAT traversal, public IP detection, NAT type detection | 3478 (UDP), 3479 (TCP) |
| **Relay Server** | TURN relay, UDP/TCP forwarding, bandwidth management | 50000-50010 |
| **Signaling Server** | Device registration, SDP exchange, connection coordination | 8080 (WS), 8443 (WSS) |
| **DID Service** | Device identity authentication, access token management | 9000 (HTTP) |
| **Client SDK** | Simplified P2P connection development | - |

### libp2p Protocol Stack

#### Security
- ✅ TLS 1.3 (`/tls/1.0.0`)
- ✅ Noise (`/noise`)

#### Stream Multiplexing
- ✅ mplex (`/mplex/6.7.0`)
- ✅ yamux (`/yamux/1.0.0`)

#### Core Protocols
- ✅ multistream-select (`/multistream/1.0.0`)
- ✅ Identify (`/ipfs/id/1.0.0`)
- ✅ AutoNAT (`/libp2p/autonat/1.0.0`)
- ✅ Circuit Relay v2 (`/libp2p/circuit/relay/0.2.0/hop`)
- ✅ DCUtR (`/libp2p/dcutr/1.0.0`)
- ✅ Ping (`/ipfs/ping/1.0.0`)

#### Advanced Features
- ✅ Kademlia DHT (`/ipfs/kad/1.0.0`) - Distributed Hash Table
- ✅ GossipSub v1.1 (`/meshsub/1.1.0`) - Pub/Sub

#### Transport
- ✅ TCP
- ✅ QUIC (`/quic-v1`)
- ✅ WebRTC (`/webrtc-direct`)
- ✅ WebTransport (`/webtransport/1.0.0`)

---

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (if not using Docker)

### Using Docker Compose (Recommended)

```bash
# Clone the project
git clone https://github.com/hbliu007/peerlink.git
cd peerlink

# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

After starting, services are available at:

- STUN Server: `udp://localhost:3478`
- Relay Server: `udp://localhost:50000-50010`
- Signaling Server: `ws://localhost:8080`
- DID Service: `http://localhost:9000`

### Using Client SDK

```python
from client_sdk import P2PClient

# Create client
client = P2PClient(
    signaling_url="ws://localhost:8080",
    stun_server="localhost:3478"
)

# Register device
await client.register(device_id="device-001")

# Connect to another device
connection = await client.connect(target_device="device-002")

# Send data
await connection.send(b"Hello, P2P!")

# Receive data
data = await connection.receive()
print(f"Received: {data}")

# Close connection
await connection.close()
```

---

## 📦 Installation

### Option 1: Docker (Recommended)

```bash
docker-compose up -d
```

### Option 2: RPM Package (CentOS/RHEL/Fedora)

```bash
# Download RPM package
wget https://github.com/hbliu007/peerlink/releases/download/v1.0.0/peerlink-1.0.0.rpm

# Install
sudo rpm -ivh peerlink-1.0.0.rpm
```

### Option 3: DEB Package (Ubuntu/Debian)

```bash
# Download DEB package
wget https://github.com/hbliu007/peerlink/releases/download/v1.0.0/peerlink_1.0.0_amd64.deb

# Install
sudo dpkg -i peerlink_1.0.0_amd64.deb
```

### Option 4: pip (Client SDK Only)

```bash
pip install peerlink-sdk
```

---

## 📚 Documentation

- [Architecture](./docs/architecture.md)
- [API Specification](./docs/api-spec.md)
- [Development Guide](./docs/development-guide.md)
- [Testing Guide](./docs/TESTING.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Operations Guide](./OPERATIONS.md)

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=p2p_engine
```

---

## 📊 Performance Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Local connection latency | < 100ms | ~20ms ✅ |
| Remote connection latency | < 500ms | ~100ms ✅ |
| P2P direct throughput | > 100 Mbps | ~500 Mbps ✅ |
| Concurrent connections | 100+ | 10,000+ ✅ |

---

## 🤝 Contributing

1. Fork this project
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes
4. Push to branch
5. Open Pull Request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file

---

<div align="center">

Made with ❤️ by PeerLink Team

</div>
