# P2P 平台增强架构设计文档

## 1. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      应用层 (Application)                    │
├─────────────────────────────────────────────────────────────┤
│                      协议层 (Protocol)                       │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┐        │
│  │   TLS   │  mplex  │Kademlia │ PubSub  │  Ping   │        │
│  │  1.3    │         │   DHT   │GossipSub│         │        │
│  └─────────┴─────────┴─────────┴─────────┴─────────┘        │
├─────────────────────────────────────────────────────────────┤
│                      传输层 (Transport)                      │
│  ┌─────────┬─────────────┬──────────────────┐               │
│  │  QUIC   │   WebRTC    │  WebTransport    │               │
│  └─────────┴─────────────┴──────────────────┘               │
├─────────────────────────────────────────────────────────────┤
│                      验证层 (Verification)                   │
│  ┌─────────────┬─────────────┬─────────────┐                │
│  │ 互操作性测试 │ 性能基准测试 │  模糊测试   │                │
│  └─────────────┴─────────────┴─────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

## 2. 目录结构

```
p2p_engine/
├── protocol/
│   ├── tls.py              # TLS 1.3 安全通道
│   ├── mplex.py            # mplex 流复用
│   ├── kademlia.py         # Kademlia DHT
│   ├── pubsub.py           # GossipSub
│   └── ping.py             # Ping 协议
├── transport/
│   ├── __init__.py
│   ├── base.py             # 传输抽象基类
│   ├── quic.py             # QUIC 传输
│   ├── webrtc.py           # WebRTC DataChannel
│   └── webtransport.py     # WebTransport
└── dht/
    ├── __init__.py
    ├── routing.py          # 路由表 (k-bucket)
    ├── provider.go         # 提供者记录
    └── query.py            # 查询逻辑

tests/
├── interop/                # 互操作性测试
│   ├── test_go_libp2p.py
│   └── test_js_libp2p.py
├── benchmark/              # 性能测试
│   ├── test_latency.py
│   ├── test_throughput.py
│   └── test_concurrent.py
└── fuzz/                   # 模糊测试
    ├── fuzz_multistream.py
    └── fuzz_noise.py
```

## 3. 核心接口定义

### 3.1 安全传输接口

```python
from abc import ABC, abstractmethod
from typing import Tuple

class SecurityTransport(ABC):
    """安全传输抽象基类"""
    
    @abstractmethod
    async def handshake(
        self, 
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        is_initiator: bool
    ) -> "SecureConnection":
        """执行安全握手"""
        pass
    
    @abstractmethod
    def get_protocol_id(self) -> str:
        """返回协议ID"""
        pass


class TLS13Security(SecurityTransport):
    """TLS 1.3 安全传输实现"""
    PROTOCOL_ID = "/tls/1.0.0"
    
    async def handshake(self, reader, writer, is_initiator):
        # 使用 ssl 模块实现 TLS 1.3
        pass
```

### 3.2 流复用器接口

```python
class StreamMuxer(ABC):
    """流复用器抽象基类"""
    
    @abstractmethod
    async def open_stream(self) -> "MuxedStream":
        """打开新流"""
        pass
    
    @abstractmethod
    async def accept_stream(self) -> "MuxedStream":
        """接受入站流"""
        pass
    
    @abstractmethod
    async def close(self):
        """关闭会话"""
        pass


class MplexMuxer(StreamMuxer):
    """mplex 流复用实现"""
    PROTOCOL_ID = "/mplex/6.0.0"
```

### 3.3 DHT 接口

```python
class DHT(ABC):
    """分布式哈希表抽象基类"""
    
    @abstractmethod
    async def find_peer(self, peer_id: "PeerID") -> "PeerInfo":
        """查找节点"""
        pass
    
    @abstractmethod
    async def provide(self, cid: "CID", announce: bool = True):
        """声明提供某内容"""
        pass
    
    @abstractmethod
    async def find_providers(self, cid: "CID", count: int = 20) -> List["PeerInfo"]:
        """查找内容提供者"""
        pass
    
    @abstractmethod
    async def put_value(self, key: bytes, value: bytes):
        """存储键值"""
        pass
    
    @abstractmethod
    async def get_value(self, key: bytes) -> bytes:
        """获取键值"""
        pass


class KademliaDHT(DHT):
    """Kademlia DHT 实现"""
    PROTOCOL_ID = "/ipfs/kad/1.0.0"
```

### 3.4 PubSub 接口

```python
class PubSub(ABC):
    """发布订阅抽象基类"""
    
    @abstractmethod
    async def subscribe(self, topic: str) -> "Subscription":
        """订阅主题"""
        pass
    
    @abstractmethod
    async def unsubscribe(self, topic: str):
        """取消订阅"""
        pass
    
    @abstractmethod
    async def publish(self, topic: str, data: bytes):
        """发布消息"""
        pass
    
    @abstractmethod
    def list_peers(self, topic: str) -> List["PeerID"]:
        """列出主题的订阅节点"""
        pass


class GossipSub(PubSub):
    """GossipSub v1.1 实现"""
    PROTOCOL_ID = "/meshsub/1.1.0"
    FALLBACK_PROTOCOL = "/floodsub/1.0.0"
```

### 3.5 传输接口

```python
class Transport(ABC):
    """传输层抽象基类"""
    
    @abstractmethod
    async def dial(self, addr: "Multiaddr") -> "Connection":
        """建立连接"""
        pass
    
    @abstractmethod
    async def listen(self, addr: "Multiaddr") -> "Listener":
        """监听地址"""
        pass
    
    @abstractmethod
    def protocols(self) -> List[str]:
        """支持的协议"""
        pass


class QUICTransport(Transport):
    """QUIC 传输"""
    def protocols(self):
        return ["/quic-v1"]


class WebRTCTransport(Transport):
    """WebRTC DataChannel 传输"""
    def protocols(self):
        return ["/webrtc-direct"]


class WebTransportTransport(Transport):
    """WebTransport 传输"""
    def protocols(self):
        return ["/webtransport/1.0.0"]
```

## 4. 技术选型

| 模块 | 技术选型 | 说明 |
|------|----------|------|
| TLS 1.3 | `ssl` (stdlib) | Python 标准库 |
| mplex | 自实现 | 参考 libp2p spec |
| Kademlia DHT | 自实现 + `kademlia` 库 | k-bucket 路由表 |
| GossipSub | 自实现 | 网格 + gossip |
| Ping | 自实现 | 简单请求/响应 |
| QUIC | `aioquic` | 异步 QUIC 库 |
| WebRTC | `aiortc` | Python WebRTC 实现 |
| WebTransport | `aioquic` (HTTP/3) | 基于 QUIC |
| 互操作测试 | `pytest` + `docker` | 容器化测试 |
| 性能测试 | `pytest` + `locust` | 负载测试 |
| 模糊测试 | `hypothesis` | 属性测试 |

## 5. 依赖关系

```
应用层
   │
   ├──► 协议层
   │      ├── TLS/mplex ──► 现有 Noise/yamux
   │      ├── DHT ──► Kademlia 路由
   │      ├── PubSub ──► DHT (可选)
   │      └── Ping ──► 基础连接
   │
   └──► 传输层
          ├── QUIC ──► 内置加密+复用
          ├── WebRTC ──► ICE/DTLS
          └── WebTransport ──► HTTP/3
```

## 6. 开发计划

| 阶段 | 内容 | 周期 | 负责人 |
|------|------|------|--------|
| Phase 1 | 架构设计 | 完成 | architect |
| Phase 2 | TLS + mplex + Ping | 2周 | engineer-1, engineer-6 |
| Phase 2 | Kademlia DHT | 3周 | engineer-2 |
| Phase 2 | PubSub (GossipSub) | 3周 | engineer-3 |
| Phase 3 | QUIC 传输 | 2周 | engineer-4 |
| Phase 3 | WebRTC 传输 | 3周 | engineer-5 |
| Phase 3 | WebTransport | 2周 | engineer-6 |
| Phase 4 | 系统集成 | 1周 | engineer-7 |
| Phase 5 | 测试验证 | 2周 | tester-1, tester-2 |
| Phase 6 | 项目报告 | 1周 | pm-lead |

## 7. 风险分析

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| aioquic 兼容性 | 中 | 高 | 使用稳定版本，添加测试 |
| WebRTC 复杂度 | 高 | 中 | 参考现有实现，分阶段交付 |
| DHT 性能 | 中 | 中 | 使用高效数据结构，优化查询 |
| 互操作测试 | 中 | 高 | 使用官方测试向量，与 go-libp2p 对比 |

## 8. 验收标准

- [ ] 所有协议通过 libp2p 互操作测试
- [ ] 测试覆盖率 ≥ 80%
- [ ] 性能基准达到 libp2p 水平的 90%
- [ ] 文档完整，包含 API 文档和使用指南
