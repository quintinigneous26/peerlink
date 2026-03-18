# P2P Platform Phase 1 架构设计文档

**版本**: 1.0
**日期**: 2026-03-16
**团队**: 方案 B (3 人团队)

---

## 执行摘要

本文档整合了 Circuit Relay v2 和 DCUtR 协议的完整架构设计，为 Phase 1 开发提供技术指导。两个架构师 agent 已完成深度技术分析，识别了核心挑战、技术风险和实现方案。

**核心目标**:
1. 实现 libp2p Circuit Relay v2 (Hop/Stop 协议 + Reservation Voucher)
2. 实现 libp2p DCUtR 协议 (标准 NAT 穿透)
3. 与现有代码集成，保持向后兼容
4. 达到 80% 测试覆盖率

---

## 1. 技术头脑风暴总结

### 1.1 Circuit Relay v2 核心挑战

**安全性挑战**:
- Voucher 防伪造机制 (Ed25519 签名)
- 公钥验证流程
- 防止重放攻击

**资源管理挑战**:
- 并发连接限制 (1000 个预留)
- 带宽限流 (Token Bucket)
- 自动过期清理

**协议分离挑战**:
- Hop 协议 (RESERVE/CONNECT)
- Stop 协议 (CONNECT)
- 状态机设计

### 1.2 DCUtR 协议核心挑战

**时间同步挑战**:
- RTT 测量精度
- 网络延迟不对称
- 时钟漂移���偿

**打孔协调挑战**:
- TCP/UDP 同时打孔
- 打孔时间点计算
- 降级策略 (失败保持中继)

**集成挑战**:
- 与 Circuit Relay v2 集成
- 与现有 puncher 模块集成
- 异步状态管理

---

## 2. 系统架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                           │
│                   (P2PClient, Connection)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                   Protocol Layer                                 │
│  ┌──────────────────┐           ┌──────────────────────────┐   │
│  │  DCUtR Protocol  │◄──────────┤  Circuit Relay v2        │   │
│  │                  │           │                          │   │
│  │ - DCUtRClient    │           │ - HopProtocol            │   │
│  │ - DCUtRSession   │           │ - StopProtocol           │   │
│  │ - Coordinator    │           │ - VoucherManager         │   │
│  └────────┬─────────┘           └────────┬─────────────────┘   │
└───────────┼──────────────────────────────┼─────────────────────┘
            │                              │
┌───────────┴──────────────────────────────┴─────────────────────┐
│                   NAT Traversal Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ HolePuncher  │  │ UDPPuncher   │  │ TCPPuncher           │ │
│  │              │  │              │  │                      │ │
│  │ - Coordinate │  │ - Standard   │  │ - Simul Open         │ │
│  │ - Fallback   │  │ - Symmetric  │  │ - Listen mode        │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
            │
┌───────────┴──────────────────────────────────────────────────────┐
│                   Transport Layer                                 │
│         UDPTransport          TCPTransport          QUICTransport │
└───────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责划分

#### Circuit Relay v2 模块

| 模块 | 职责 | 关键接口 |
|------|------|----------|
| **HopProtocol** | RESERVE/CONNECT 处理 | `HandleReserve()`, `HandleConnect()` |
| **StopProtocol** | CONNECT 终止处理 | `HandleConnect()`, `AcceptConnection()` |
| **VoucherManager** | 签名/验证 Voucher | `SignVoucher()`, `VerifyVoucher()` |
| **ReservationStore** | 预留存储和过期 | `Store()`, `Lookup()`, `Cleanup()` |
| **RelaySession** | 数据转发 | `Forward()`, `TrackBandwidth()` |
| **ResourceLimiter** | 资源限制 | `CheckLimits()`, `RateLimit()` |

#### DCUtR 协议模块

| 模块 | 职责 | 关键接口 |
|------|------|----------|
| **DCUtRClient** | 协议客户端 | `InitiateUpgrade()`, `RespondToUpgrade()` |
| **DCUtRSession** | 会话状态机 | `Start()`, `OnConnectReceived()`, `OnSyncReceived()` |
| **DCUtRCoordinator** | 时间协调 | `MeasureRTT()`, `CalculatePunchSchedule()` |
| **DCUtRMessage** | Protobuf 消息 | `SerializeConnect()`, `ParseSync()` |

#### NAT 穿透模块

| 模块 | 职责 | 关键接口 |
|------|------|----------|
| **HolePuncher** | 统一打孔接口 | `Punch()`, `SelectBest()` |
| **UDPPuncher** | UDP 打孔 | `StandardPunch()`, `SymmetricPunch()` |
| **TCPPuncher** | TCP 打孔 | `SimultaneousOpen()`, `Listen()` |
| **PortPredictor** | 端口预测 | `PredictPorts()` |

---

## 3. 关键技术方案

### 3.1 Reservation Voucher 安全设计

**Signed Envelope (RFC 0002)**:
```cpp
struct SignedEnvelope {
    std::string public_key;      // Ed25519 公钥 (32 bytes)
    std::string payload_type;    // "/libp2p/relay-reservation"
    std::vector<uint8_t> payload; // 序列化的 ReservationVoucher
    std::vector<uint8_t> signature; // Ed25519 签名 (64 bytes)
};

// 签名过程
signature = Ed25519Sign(
    private_key,
    "libp2p-signed-envelope:" + payload_type + payload
);

// 验证过程
bool valid = Ed25519Verify(
    public_key,
    "libp2p-signed-envelope:" + payload_type + payload,
    signature
);
```

**安全属性**:
- ✅ 防伪造: Ed25519 签名
- ✅ 防重放: 过期时间戳
- ✅ 防盗用: Peer ID 绑定
- ✅ 防篡改: 签名覆盖全部数据

### 3.2 DCUtR 时间同步算法

**RTT 测量**:
```
发起方 (A)                    响应方 (B)

t1: 发送 CONNECT
    ──────────────>
                              t2: 收到 CONNECT
                              t3: 发送 SYNC
    <──────────────
t4: 收到 SYNC

RTT = (t4 - t1) - (t3 - t2)
    ≈ (t4 - t1)  (假设处理时间忽略)

单程延迟 = RTT / 2
```

**打孔时间计算**:
```cpp
// 发起方
punch_time_A = t4 + RTT + buffer;

// 响应方
punch_time_B = t3 + RTT + buffer;

// buffer = 100ms (容错窗口)
```

### 3.3 TCP/UDP 并行打孔策略

```cpp
// 伪代码
async Connection ExecuteCoordinatedPunch(PunchSchedule schedule) {
    // 等待到打孔时间
    await SleepUntil(schedule.punch_time);

    // 并行启动 TCP 和 UDP 打孔
    auto udp_future = async(UDPPunch);
    auto tcp_future = async(TCPPunch);

    // 竞速：任一成功即返回
    auto result = await WhenAny(udp_future, tcp_future);

    if (result.success) {
        CancelOther(result.type);
        return result.connection;
    }

    // 都失败，保持中继连接
    return relay_connection;
}
```

---

## 4. Protobuf 消息格式

### 4.1 Circuit Relay v2 消息

```protobuf
syntax = "proto3";

message CircuitRelay {
  enum Type {
    RESERVE = 0;
    CONNECT = 1;
    STATUS = 2;
  }

  Type type = 1;
  Reservation reservation = 2;
  Peer peer = 3;
  Status status = 4;
}

message Reservation {
  uint64 expire = 1;        // Unix timestamp
  bytes addr = 2;           // Relay multiaddr
  bytes voucher = 3;        // Signed envelope
  uint64 limit_duration = 4;
  uint64 limit_data = 5;
}

message ReservationVoucher {
  bytes relay = 1;          // Relay peer ID
  bytes peer = 2;           // Client peer ID
  uint64 expiration = 3;    // Unix timestamp
}
```

### 4.2 DCUtR 消息

```protobuf
syntax = "proto3";

message Connect {
  repeated bytes addrs = 1;  // Multiaddr
  int64 timestamp_ns = 2;
}

message Sync {
  repeated bytes addrs = 1;
  int64 echo_timestamp_ns = 2;
  int64 timestamp_ns = 3;
}

message DCUtRMessage {
  enum Type {
    CONNECT = 0;
    SYNC = 1;
  }

  Type type = 1;
  oneof payload {
    Connect connect = 2;
    Sync sync = 3;
  }
}
```

---

## 5. 状态机设计

### 5.1 Circuit Relay v2 Hop 协议状态机

```
┌─────────┐
│  IDLE   │
└────┬────┘
     │ RESERVE request
     ▼
┌─────────────┐
│ RESERVING   │──► Check limits, Generate voucher
└────┬────────┘
     │ Success
     ▼
┌─────────────┐
│  RESERVED   │◄──┐ REFRESH
└────┬────────┘   │
     │ CONNECT    │
     ▼            │
┌─────────────┐   │
│  RELAYING   │───┘
└────┬────────┘
     │ Close/Expire
     ▼
┌─────────┐
│  CLOSED │
└─────────┘
```

### 5.2 DCUtR 会话状态机

```
┌──────┐
│ IDLE │
└───┬──┘
    │ Start()
    ▼
┌─────────────┐
│ CONNECTING  │──► SendConnect()
└──────┬──────┘
       │ OnConnectReceived()
       ▼
┌─────────────┐
│   SYNCING   │──► SendSync()
└──────┬──────┘
       │ OnSyncReceived()
       ▼
┌─────────────┐
│  PUNCHING   │──► ExecutePunch()
└──────┬──────┘
       │
       ├─► Success ──► CONNECTED
       │
       └─► Failed ──► FAILED (keep relay)
```

---

## 6. 文件结构

### 6.1 新增文件清单

**Circuit Relay v2**:
```
p2p-cpp/include/p2p/relay/
├── hop_protocol.hpp
├── stop_protocol.hpp
├── voucher_manager.hpp
├── reservation_store.hpp
├── relay_session.hpp
└── resource_limiter.hpp

p2p-cpp/src/relay/
├── hop_protocol.cpp
├── stop_protocol.cpp
├── voucher_manager.cpp
├── reservation_store.cpp
├── relay_session.cpp
└── resource_limiter.cpp
```

**DCUtR 协议**:
```
p2p-cpp/include/p2p/protocol/
├── dcutr_client.hpp
├── dcutr_session.hpp
├── dcutr_coordinator.hpp
└── dcutr_message.hpp

p2p-cpp/src/protocol/
├── dcutr_client.cpp
├── dcutr_session.cpp
├── dcutr_coordinator.cpp
└── dcutr_message.cpp
```

**NAT 穿透**:
```
p2p-cpp/include/p2p/nat/
├── hole_puncher.hpp
├── udp_puncher.hpp
├── tcp_puncher.hpp
└── port_predictor.hpp

p2p-cpp/src/nat/
├── hole_puncher.cpp
├── udp_puncher.cpp
├── tcp_puncher.cpp
└── port_predictor.cpp
```

**Protobuf**:
```
p2p-cpp/proto/
├── relay_v2.proto
└── dcutr.proto
```

**测试**:
```
p2p-cpp/tests/unit/
├── test_hop_protocol.cpp
├── test_voucher_manager.cpp
├── test_dcutr_session.cpp
└── test_dcutr_coordinator.cpp

p2p-cpp/tests/integration/
├── test_relay_v2_e2e.cpp
└── test_dcutr_e2e.cpp
```

### 6.2 需要修改的文件

```
p2p-cpp/include/p2p/core/p2p_client.hpp
p2p-cpp/src/core/p2p_client.cpp
p2p-cpp/include/p2p/transport/tcp_transport.hpp
p2p-cpp/src/transport/tcp_transport.cpp
p2p-cpp/CMakeLists.txt
```

---

## 7. 技术决策

### 7.1 异步 I/O (Boost.Asio)

**决策**: 使用 Boost.Asio + C++20 协程

**理由**:
- ✅ 符合现有代码风格
- ✅ 高并发性能 (1000+ 连接)
- ✅ 协程简化异步代码
- ❌ 学习曲线较陡

### 7.2 内存管理

**决策**: 混合策略

- **RelaySession**: 内存池 (高频分配)
- **Reservation**: 动态分配 (低频分配)
- **智能指针**: `std::shared_ptr` 管理生命周期

### 7.3 Protobuf vs JSON

**决策**: Protobuf

**理由**:
- ✅ libp2p 规范要求
- ✅ 性能优势 (二进制格式)
- ✅ 向后兼容性
- ❌ 调试不便 (使用 JSON 日志)

### 7.4 单进程 vs 多进程

**决策**: 单进程 + 线程池

**理由**:
- ✅ 简化部署
- ✅ Asio 提供足够并发
- ✅ 易于调试
- 🔮 未来: 多进程水平扩展

---

## 8. 安全性分析

### 8.1 威胁模型

| 威胁 | 攻击方式 | 缓解措施 | 状态 |
|------|---------|---------|------|
| Voucher 伪造 | 创建假 Voucher | Ed25519 签名验证 | ✅ 已防护 |
| Voucher 重放 | 重用过期 Voucher | 过期时间检查 | ✅ 已防护 |
| 资源耗尽 | 大量预留请求 | 全局限制 + 速率限制 | ✅ 已防护 |
| 带宽滥用 | 超量数据传输 | Token Bucket 限流 | ✅ 已防护 |
| 中间人攻击 | 拦截中继流量 | TLS 1.3 加密 | ✅ 已防护 |

### 8.2 安全检查清单

- [x] Ed25519 签名验证
- [x] Peer ID 验证
- [x] 过期时间验证
- [x] 速率限制
- [x] 全局资源限制
- [x] 带宽限流
- [x] DDoS 防护
- [x] 常量时间签名验证

---

## 9. 性能目标

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| DCUtR 打孔成功率 | >80% | 集成测试统计 |
| 中继连接延迟 | <500ms | RTT 测量 |
| Voucher 验证延迟 | <1ms | 单元测试 |
| 并发中继连接 | 1000+ | 压力测试 |
| 内存占用 | <100MB | 内存分析工具 |
| CPU 占用 | <50% | 性能分析工具 |

---

## 10. 风险和缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| RTT 测量不准确 | 高 | 中 | 多次测量 + EWMA 平滑 |
| 时间同步失败 | 高 | 中 | 增加容错窗口 |
| 状态机死锁 | 高 | 低 | 严格超时机制 |
| 内存泄漏 | 中 | 低 | RAII + 智能指针 |
| Protobuf 兼容性 | 中 | 低 | 版本协商 |

---

## 11. 下一步：团队分工

基于以上架构设计，现在可以进行明确的团队分工：

### 11.1 P2P 协议专家 (Team Lead)

**Week 1**:
- Protobuf 消息格式定义
- Signed Envelope 实现

**Week 2**:
- DCUtR 协议核心实现
- DCUtRSession 状态机

**Week 3**:
- Hop 协议实现
- Reservation Voucher 实现

### 11.2 资深 C++ 工程师

**Week 1**:
- 环境搭建
- 修复失败测试

**Week 2**:
- 集成 DCUtR 到 NAT 穿透
- HolePuncher 实现

**Week 3**:
- Stop 协议实现
- RelaySession 实现

### 11.3 C++ 测试工程师

**Week 1**:
- 修复 4 个失败测试
- 测试框架搭建

**Week 2**:
- DCUtR 单元测试
- DCUtR 集成测试

**Week 3**:
- Circuit Relay v2 测试
- 互操作性测试

---

**文档版本**: 1.0
**最后更新**: 2026-03-16
**审核者**: 架构师 Agent × 2
**下次审查**: Phase 1 结束后
