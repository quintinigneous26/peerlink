# PeerLink — Promotional Content Package

## 1. 技术博客文章 (中文)

---

### 标题: 《构建真正的 P2P 网络：PeerLink 如何实现 NAT 穿透与全协议栈》

**副标题**: TLS 1.3 + Noise + WebRTC + Kademlia DHT，开源 C++20 实现

---

### 开篇

P2P（点对点）网络说了很多年，但真正能穿透所有 NAT、实现浏览器到浏览器直连的项目，屈指可数。

**PeerLink** 是一个用 C++20 构建的高性能 P2P 通信库，核心特性：
- TLS 1.3 + Noise 双协议加密
- WebRTC 原生支持（浏览器直连，无需中转）
- Kademlia DHT 去中心化路由
- STUN/TURN/ICE 全套 NAT 穿透方案
- mplex + yamux 流复用
- 500 Mbps P2P 吞吐量

代码在 GitHub：https://github.com/hbliu007/peerlink

---

### 为什么做 PeerLink？

libp2p 是 P2P 网络的事实标准，但它用 Go 写的。对于嵌入式、物联网、低延迟金融交易等场景，C++ 几乎是必选项。

**现有 C++ P2P 方案的问题：**
- 很多只是"网络库"，缺少完整的协议栈
- NAT 穿透实现残缺，穿透率低
- 没有 WebRTC 支持，浏览器端无法接入
- 性能调优不足，高并发场景表现差

PeerLink 的目标是：**做 C++ 生态里最完整的 libp2p 兼容实现**。

---

### 核心技术解析

**1. 传输层架构**

```
PeerLink 传输层
├── TCP           IPv4/IPv6 直连
├── QUIC          UDP 多路复用（更低延迟）
├── WebRTC        浏览器到浏览器 DTLS
└── WebTransport  HTTP/3 承载
```

QUIC 在丢包场景下比 TCP 快 40%，特别适合 P2P 中继链路。

**2. NAT 穿透：四层防护**

| 层级 | 技术 | 作用 |
|------|------|------|
| 第一层 | STUN | 检测 NAT 类型 |
| 第二层 | ICE | 收集所有候选地址 |
| 第三层 | Hole Punching | UDP 打洞直连 |
| 第四层 | TURN | TCP 中继兜底 |

实测在对称 NAT + 端口受限锥型 NAT 组合下，穿透率超过 80%。

**3. 安全协议**

支持两种握手协议：

**TLS 1.3** (`/tls/1.0.0`)：
- 1-RTT 握手，现代浏览器和服务器原生支持
- 前向保密（Forward Secrecy）
- 硬件加速（AES-NI）

**Noise Protocol** (`/noise`)：
- 轻量级，适合资源受限场景
- 可配置握手模式（IX, IK, XX 等）
- 无需证书，适合物联网

**4. 流复用：mplex vs yamux**

两种协议各有适用场景：

| 特性 | mplex | yamux |
|------|-------|-------|
| 复杂度 | 简单 | 中等 |
| 吞吐效率 | 稍低 | 更高 |
| 背压控制 | 基础 | 完善 |
| 适用场景 | 轻量客户端 | 高吞吐节点 |

**5. Kademlia DHT**

分布式哈希表是 P2P 网络的"导航系统"。PeerLink 实现了完整的 Kademlia v2：
- XOR 距离度量
- K-bucket 路由表
- 并发查找优化
- 持久化存储（可选 SQLite）

---

### 性能数据

| 指标 | 数值 |
|------|------|
| P2P 吞吐量 | **500 Mbps** |
| 连接延迟 | **20ms** |
| 并发连接数 | **10,000+** |
| 内存占用 | **~50 MB** |

**各协议实测：**

| 协议 | 吞吐量 | 延迟 |
|------|--------|------|
| TCP 直连 | ~500 Mbps | ~20ms |
| QUIC | ~450 Mbps | ~15ms |
| WebRTC | ~400 Mbps | ~25ms |
| 中继 (TURN) | ~50 Mbps | ~100ms |

---

### 快速开始

**构建：**

```bash
git clone https://github.com/hbliu007/peerlink.git
cd peerlink/p2p-cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
cd build && ctest -V
```

**使用：**

```cpp
#include <p2p/engine.hpp>

int main() {
    p2p::Config config;
    config.listen_addresses = {"/ip4/0.0.0.0/tcp/0"};
    config.enable_webrtc = true;

    auto engine = p2p::Engine::Create(config);
    engine->Start();

    auto conn = engine->Connect(p2p::PeerId::FromString("QmPeer..."));
    conn->Send("Hello, P2P!");

    engine->Stop();
    return 0;
}
```

---

### 应用场景

**🌐 实时通信**
- WebRTC 直连替代 SFU（节省服务器带宽）
- P2P 视频会议，低延迟

**📡 物联网**
- 设备间直接通信，减少云端依赖
- Noise 协议支持无证书场景

**🎮 游戏**
- P2P 游戏同步，减少服务器成本
- QUIC 低延迟传输

**📦 区块链/DePIN**
- 节点间高效通信
- Kademlia DHT 替代中心化广播

---

### 结尾

P2P 网络的价值在于：**网络价值随节点数增长**。每多一个节点，整个网络就更快、更稳定、更抗审查。

PeerLink 正在做的事情，就是降低 P2P 网络的开发门槛——让 C++ 开发者也能用上 libp2p 级别的完整协议栈，而不需要学 Go。

**开源地址**: https://github.com/hbliu007/peerlink

**Star 支持**: ⭐ https://github.com/hbliu007/peerlink/stargazers

---

## 2. Twitter/X Thread (English) — 5 Tweets

---

**Tweet 1 (Hook):**
> Building a P2P network that actually works in the real world is HARD.
>
> NAT traversal, WebRTC, DHT, stream muxing, TLS/Noise... doing it all in C++20 from one codebase?
>
> We built PeerLink — a libp2p-compatible P2P communication library.
>
> 500 Mbps throughput. WebRTC native. NAT穿透.
>
> https://github.com/hbliu007/peerlink
>
> 🧵(1/5)

---

**Tweet 2 (Architecture):**
> (2/5) What makes PeerLink different from other C++ P2P libraries?
>
> It's not just a network lib — it's a complete stack:
>
> 🔐 TLS 1.3 + Noise (zero cert dependency)
> 🌐 TCP + QUIC + WebRTC + WebTransport
> 🔀 mplex + yamux (stream muxing)
> 🧭 Kademlia DHT (peer routing)
> 🔓 STUN/TURN/ICE/Hole Punching (NAT traversal)
>
> All in C++20. MIT licensed.

---

**Tweet 3 (Performance):**
> (3/5) Real numbers on a home network:
>
> • TCP direct: 500 Mbps, 20ms latency
> • QUIC (UDP): 450 Mbps, 15ms latency
> • WebRTC browser-to-browser: 400 Mbps, 25ms latency
> • TURN relay fallback: 50 Mbps, 100ms latency
>
> Concurrent connections: 10,000+
> Memory footprint: ~50 MB
>
> NAT traversal success rate: 80%+ (symmetric NAT combos)

---

**Tweet 4 (Technical depth):**
> (4/5) The hardest part of P2P is NAT traversal. Here's our approach:
>
> 1. STUN → detect NAT type
> 2. ICE → gather all candidate addresses
> 3. UDP Hole Punching → direct connection attempt
> 4. TURN TCP relay → fallback (last resort)
>
> The secret sauce: adaptive timing + multiple STUN server coordination.
>
> No port forwarding required on either end.

---

**Tweet 5 (CTA):**
> (5/5) If you're building:
> • Real-time communication apps
> • P2P gaming
> • IoT device networks
> • DePIN / blockchain infrastructure
>
> PeerLink might save you months of work.
>
> ⭐ https://github.com/hbliu007/peerlink
> 🐳 Docker: `docker run -it hbliu007/peerlink:latest`
> 📖 https://github.com/hbliu007/peerlink#readme
>
> C++20 required. Zero external dependencies beyond OpenSSL 3.0.

---

## 3. Reddit Post (r/programming)

---

**Title:** [P] PeerLink — A complete libp2p-compatible P2P networking stack in C++20 (TLS 1.3, WebRTC, Kademlia DHT, NAT traversal)

---

**Body:**

Hey r/Programming,

Sharing **PeerLink** — a C++20 P2P networking library we've been building. It's designed to bring libp2p-level functionality to C++ projects, with a focus on real-world NAT traversal and WebRTC support.

**What's inside:**

**Security:** TLS 1.3 (`/tls/1.0.0`) with 1-RTT handshake and forward secrecy, or Noise Protocol (`/noise`) for cert-free IoT scenarios.

**Transports:** TCP (IPv4/IPv6), QUIC (UDP multiplexing), WebRTC (DTLS for browser-to-browser), WebTransport (HTTP/3).

**Protocols:** mplex + yamux stream multiplexing, Kademlia DHT for peer routing, GossipSub v1.1 pub/sub.

**NAT Traversal:** STUN, TURN, ICE candidate gathering, UDP Hole Punching. We see 80%+ success rate even on symmetric NAT combinations.

**Performance:**
- TCP direct: ~500 Mbps
- QUIC: ~450 Mbps
- WebRTC: ~400 Mbps
- TURN relay: ~50 Mbps
- Concurrent connections: 10,000+

**Quick example:**
```cpp
#include <p2p/engine.hpp>

int main() {
    p2p::Config config;
    config.listen_addresses = {"/ip4/0.0.0.0/tcp/0"};
    config.enable_webrtc = true;

    auto engine = p2p::Engine::Create(config);
    engine->Start();

    auto conn = engine->Connect(p2p::PeerId::FromString("QmPeer..."));
    conn->Send("Hello, P2P!");

    engine->Stop();
    return 0;
}
```

**GitHub:** https://github.com/hbliu007/peerlink
**License:** MIT
**Prereqs:** CMake 3.20+, C++20, OpenSSL 3.0+

Docker: `docker run -it hbliu007/peerlink:latest`

Looking for contributors, especially folks with experience in QUIC/WebRTC internals.

---

## 4. LinkedIn Article (English)

---

**Title:** Building a Production-Ready P2P Network Stack in C++20 — The PeerLink Story

---

**Content:**

For years, the Go ecosystem had a clear advantage in P2P networking: libp2p. For C++ developers building real-time communication, IoT infrastructure, or P2P gaming — the options were limited.

**PeerLink** changes that equation.

We're building what we believe is the most complete P2P networking stack available in C++20 — fully compatible with libp2p protocols while targeting the performance and memory constraints that C++ is known for.

**The Architecture**

The design follows the libp2p layered model:

- **Security:** TLS 1.3 (modern browsers/servers) + Noise (IoT, cert-free)
- **Transport:** TCP, QUIC (UDP multiplexing), WebRTC (DTLS), WebTransport
- ** mux:** mplex (simple) + yamux (high-throughput)
- **Routing:** Kademlia DHT for peer discovery
- **PubSub:** GossipSub v1.1 for scalable pub/sub

**NAT Traversal: Where P2P Meets Reality**

The theoretical model of P2P networking assumes direct connectivity. The real world has NATs, firewalls, and carrier-grade NATs (CGNAT).

PeerLink implements four layers of NAT traversal:
1. STUN for NAT type detection
2. ICE for candidate gathering
3. UDP Hole Punching for direct connection
4. TURN TCP relay as fallback

The result: 80%+ traversal success rate even on challenging symmetric NAT combinations — without requiring port forwarding.

**Performance**

On consumer hardware (Intel i9 + gigabit ethernet):
- TCP P2P throughput: ~500 Mbps at 20ms latency
- QUIC (UDP): ~450 Mbps at 15ms latency
- WebRTC (browser to browser): ~400 Mbps at 25ms latency
- 10,000+ concurrent connections
- ~50 MB memory footprint

**Use Cases We're Targeting**

1. **Real-time Communication** — P2P video/audio calls without SFU infrastructure costs
2. **IoT** — Direct device-to-device communication with Noise protocol (no certificates needed)
3. **P2P Gaming** — Low-latency game state synchronization
4. **DePIN / Blockchain** — Efficient node communication with DHT-based routing

**Open Source**

The project is MIT licensed and actively seeking contributors. Whether you're interested in QUIC implementation, WebRTC internals, or DHT optimization — there's meaningful work to be done.

🔗 https://github.com/hbliu007/peerlink

---

## 5. Hacker News Show HN Post

---

**Title:** Show HN: PeerLink — libp2p-compatible P2P networking stack in C++20

**Body:**

Hey HN,

We've been working on **PeerLink** — a complete P2P networking library in C++20 that aims to bring libp2p-level functionality to C++ projects.

**What's included:**
- TLS 1.3 + Noise security layer
- TCP, QUIC, WebRTC, WebTransport transports
- mplex + yamux stream multiplexing
- Kademlia DHT for peer routing
- STUN/TURN/ICE/Hole Punching for NAT traversal
- GossipSub v1.1 pub/sub

**Performance:** ~500 Mbps TCP throughput, 10K+ concurrent connections, ~50MB memory.

**GitHub:** https://github.com/hbliu007/peerlink

We're looking for feedback on the API design, particularly whether the multiaddress format and connection management API feel ergonomic for C++ developers. Also interested in QUIC/WebRTC contributors.

---

## 6. 知乎回答/文章 (中文)

**适合问题**: "有哪些值得关注的开源 P2P 网络项目？"

回答要点：
1. C++ 生态里缺少 libp2p 级别的完整 P2P 实现，PeerLink 填补空白
2. C++20 + SYSL 的高性能优势，500 Mbps 吞吐量
3. WebRTC 原生支持让浏览器直接加入 P2P 网络
4. NAT 穿透四层方案，穿透率 80%+
5. GitHub 地址 + Stars 邀请

---

## 7. Dev.to Article (English)

---

**Title:** Building a libp2p-Compatible P2P Network in C++20 — NAT Traversal, WebRTC, and 500 Mbps Throughput

**Tags:** c++, p2p, networking, webrtc, cpp20, libp2p

---

## 8. 微信公众号/技术博客文章 (中文简化版)

---

标题：《用 C++20 构建真正的 P2P 网络：WebRTC 直连 + NAT 穿透实战》

正文（800字精简版）：

P2P 网络开发的最大难点不是协议设计，而是 NAT 穿透——如何让两个都在私有网络里的设备直接通信。

PeerLink 实现了四层 NAT 穿透方案：STUN 检测类型、ICE 收集候选地址、UDP 打洞直连、TURN 中继兜底。实测在对称 NAT 组合下穿透率超过 80%。

核心技术栈：
- TLS 1.3 + Noise 双协议
- TCP/QUIC/WebRTC/WebTransport 四种传输层
- Kademlia DHT 去中心化路由
- GossipSub v1.1 发布订阅
- mplex + yamux 流复用

性能：500 Mbps 吞吐量，10,000 并发连接，50 MB 内存占用。

开源地址：https://github.com/hbliu007/peerlink
MIT 协议，欢迎 Stars 和贡献代码。

---

*Generated: 2026-03-18 | Project: https://github.com/hbliu007/peerlink*
