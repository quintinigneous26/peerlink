# P2P Platform Phase 1 开发计划

**团队配置**: 方案 B (3 人团队)
**开发周期**: 2-3 个月
**生成时间**: 2026-03-16

---

## 团队成员和职责

### 1. P2P 协议专家 (C++) - Team Lead
**姓名**: [待定]
**职责**:
- 实现 DCUtR 协议 (C++)
- 完善 Circuit Relay v2 Hop/Stop 协议
- 实现 Reservation Voucher (Signed Envelope)
- Protobuf 消息格式统一
- 与 libp2p 互操作性验证
- 技术架构决策

**技能要求**:
- libp2p 规范深度理解 (DCUtR, Circuit Relay v2)
- C++17/20 熟练
- 网络协议设计 (Protobuf, 异步 IO)
- NAT 穿透算法 (UDP/TCP 打孔)
- 有 go-libp2p 或 rust-libp2p 经验

### 2. 资深 C++ 工程师
**姓名**: [待定]
**职责**:
- p2p-cpp 核心引擎实现
- STUN/TURN/Relay 服务器优化
- 性能优化、内存安全
- 并发和多线程处理
- 协助协议专家

**技能要求**:
- C++17/20 熟练 (Asio, 协程)
- 网络编程 (TCP/UDP/QUIC, 异步 IO)
- CMake 构建系统
- OpenSSL (TLS/DTLS)
- 多线程/并发编程

### 3. C++ 测试工程师
**姓名**: [待定]
**职责**:
- GoogleTest 测试框架
- 单元测试、集成测试
- 修复 4 个失败的 C++ 测试
- 提升 C++ 代码覆盖率 (目标 80%)
- 互操作性测试 (与 go-libp2p)
- 性能测试和基准测试

**技能要求**:
- GoogleTest/CTest 框架
- TDD 方法论
- 集成测试、性能测试
- 代码覆盖率工具 (gcov/lcov)
- CI/CD 经验

---

## Phase 1: 核心互操作性 (Week 1-3)

### 目标
与 libp2p 网络基本互操作，修复关键问题

### Week 1: 基础设施和测试修复

#### 任务 1.1: 环境搭建 (全员，1 天)
- [ ] 开发环境配置 (C++20, CMake, 依赖库)
- [ ] 代码仓库权限和分支策略
- [ ] CI/CD 流程熟悉
- [ ] 文档阅读 (libp2p 规范、项目架构)

**负责人**: 全员
**交付物**: 开发环境就绪，能够编译和运行测试

#### 任务 1.2: 修复 4 个失败测试 (测试工程师，2-3 天)
- [ ] 修复 `test_dht_providers` (DHT provider 功能)
- [ ] 修复 `test_noise_multiple_messages` (Noise 签名验证)
- [ ] 修复 `test_concurrent_connections` (并发连接握手)
- [ ] 修复 `test_dht_provider_discovery_performance` (性能测试)

**负责人**: C++ 测试工程师
**交付物**: 所有测试通过，测试报告

#### 任务 1.3: Protobuf 消息格式定义 (协议专家，2-3 天)
- [ ] 定义 DCUtR 协议 Protobuf 消息
  ```protobuf
  message Connect {
    bytes peer_id = 1;
  }
  message Sync {
    repeated bytes addrs = 1;
  }
  ```
- [ ] 定义 Circuit Relay v2 Protobuf 消息
  ```protobuf
  message HopMessage {
    enum Type {
      RESERVE = 0;
      CONNECT = 1;
      STATUS = 2;
    }
    Type type = 1;
    Reservation reservation = 2;
    Status status = 3;
  }
  ```
- [ ] 生成 C++ 代码 (protoc)

**负责人**: P2P 协议专家
**交付物**: Protobuf 定义文件，生成的 C++ 代码

### Week 2: DCUtR 协议实现

#### 任务 2.1: DCUtR 协议核心实现 (协议专家，3-4 天)
- [ ] 实现 `/libp2p/dcutr` 协议 ID
- [ ] 实现 CONNECT 消息处理
  - 发起方发送 CONNECT 消息
  - 接收方回复 CONNECT 消息
- [ ] 实现 SYNC 消息处理
  - 交换地址列表
  - RTT 测量
- [ ] 实现打孔协调逻辑
  - 同步时间戳
  - 并发 TCP/UDP 打孔

**负责人**: P2P 协议专家
**交付物**: DCUtR 协议实现，单元测试

**文件路径**:
- `p2p-cpp/include/p2p/protocol/dcutr.hpp`
- `p2p-cpp/src/protocol/dcutr.cpp`
- `p2p-cpp/tests/protocol/test_dcutr.cpp`

#### 任务 2.2: 集成 DCUtR 到 NAT 穿透模块 (C++ 工程师，2-3 天)
- [ ] 修改 `p2p-cpp/src/nat/puncher.cpp`
- [ ] 在打孔前建立中继连接
- [ ] 通过 DCUtR 协调打孔
- [ ] 实现降级策略 (打孔失败保持中继)

**负责人**: 资深 C++ 工程师
**交付物**: NAT 穿透集成 DCUtR，集成测试

#### 任务 2.3: DCUtR 测试 (测试工程师，2 天)
- [ ] 单元测试 (消息解析、状态机)
- [ ] 集成测试 (端到端打孔)
- [ ] 互操作性测试 (与 go-libp2p)

**负责人**: C++ 测试工程师
**交付物**: 测试用例，测试报告

### Week 3: Circuit Relay v2 实现

#### 任务 3.1: Hop 协议实现 (协议专家，2-3 天)
- [ ] 实现 `/libp2p/circuit/relay/0.2.0/hop` 协议
- [ ] 实现 RESERVE 消息处理
  - 分配中继槽位
  - 生成 Reservation Voucher
- [ ] 实现 CONNECT 消息处理
  - 验证预留权限
  - 建立中继连接

**负责人**: P2P 协议专家
**交付物**: Hop 协议实现

**文件路径**:
- `p2p-cpp/include/p2p/servers/relay/hop_protocol.hpp`
- `p2p-cpp/src/servers/relay/hop_protocol.cpp`

#### 任务 3.2: Stop 协议实现 (C++ 工程师，2 天)
- [ ] 实现 `/libp2p/circuit/relay/0.2.0/stop` 协议
- [ ] 实现 CONNECT 消息处理
- [ ] 流式连接升级

**负责人**: 资深 C++ 工程师
**交付物**: Stop 协议实现

**文件路径**:
- `p2p-cpp/include/p2p/servers/relay/stop_protocol.hpp`
- `p2p-cpp/src/servers/relay/stop_protocol.cpp`

#### 任务 3.3: Reservation Voucher 实现 (协议专家，2-3 天)
- [ ] 实现 Signed Envelope (RFC 0002)
  - 域: `libp2p-relay-rsvp`
  - Multicodec: `0x0302`
- [ ] 实现 Voucher 结构
  ```protobuf
  message Voucher {
    bytes relay = 1;
    bytes peer = 2;
    uint64 expiration = 3;
  }
  ```
- [ ] 实现加密签名和验证
  - Ed25519 签名
  - 公钥验证

**负责人**: P2P 协议专家
**交付物**: Reservation Voucher 实现

**文件路径**:
- `p2p-cpp/include/p2p/servers/relay/voucher.hpp`
- `p2p-cpp/src/servers/relay/voucher.cpp`

#### 任务 3.4: Circuit Relay v2 测试 (测试工程师，2 天)
- [ ] 单元测试 (Hop/Stop 协议)
- [ ] 集成测试 (预留、连接、转发)
- [ ] 安全测试 (Voucher 验证)
- [ ] 互操作性测试 (与 go-libp2p)

**负责人**: C++ 测试工程师
**交付物**: 测试用例，测试报告

---

## Phase 1 验收标准

### 功能验收
- [ ] 所有 C++ 测试通过 (包括之前失败的 4 个)
- [ ] DCUtR 协议实现完整
  - [ ] 能与 go-libp2p 节点协商打孔
  - [ ] TCP/UDP 同时打孔成功
  - [ ] 打孔失败降级到中继连接
- [ ] Circuit Relay v2 实现完整
  - [ ] Hop 协议 (RESERVE/CONNECT)
  - [ ] Stop 协议 (CONNECT)
  - [ ] Reservation Voucher 验证通过
- [ ] 与 go-libp2p 互操作性验证通过

### 性能验收
- [ ] DCUtR 打孔成功率 >80%
- [ ] 中继连接建立延迟 <500ms
- [ ] 内存泄漏检测通过 (Valgrind)

### 代码质量验收
- [ ] 代码覆盖率 >60% (Phase 1 目标)
- [ ] 无编译警告
- [ ] 通过静态分析 (clang-tidy)
- [ ] 代码审查通过

---

## Phase 2: 功能完整性 (Week 4-6)

### 目标
完善核心功能，提升安全性和测试覆盖率

### Week 4: DHT 改进

#### 任务 4.1: DHT Client/Server Mode (C++ 工程师，2-3 天)
- [ ] 实现节点模式区分
- [ ] Server Mode: 广告 Kademlia 协议 ID
- [ ] Client Mode: 不广告协议 ID
- [ ] 根据 AutoNAT 结果自动切换模式

**负责人**: 资深 C++ 工程师
**交付物**: DHT 模式区分实现

#### 任务 4.2: DHT Entry Validation (协议专家，3-4 天)
- [ ] 实现记录签名验证
- [ ] 实现时间戳检查
- [ ] 实现 Entry Correction 机制
- [ ] 拒绝过期记录

**负责人**: P2P 协议专家
**交付物**: DHT 安全性增强

### Week 5: AutoNAT v2 和 mplex 迁移

#### 任务 5.1: AutoNAT v2 实现 (C++ 工程师，3-4 天)
- [ ] 实现 `/libp2p/autonat/2/dial-request` 协议
- [ ] 实现 Nonce 验证机制
- [ ] 实现放大攻击防护 (30-100KB 数据传输)
- [ ] 单地址检测

**负责人**: 资深 C++ 工程师
**交付物**: AutoNAT v2 实现

#### 任务 5.2: mplex → Yamux 迁移 (协议专家，2-3 天)
- [ ] 全局替换 mplex 为 Yamux
- [ ] 测试兼容性
- [ ] 性能对比

**负责人**: P2P 协议专家
**交付物**: 完全使用 Yamux

### Week 6: 测试覆盖率提升

#### 任务 6.1: 核心模块测试补充 (测试工程师，5 天)
- [ ] 补充 0% 覆盖率模块测试
  - `p2p-cpp/src/nat/puncher.cpp`
  - `p2p-cpp/src/servers/relay/relay_server.cpp`
  - `p2p-cpp/src/protocol/dcutr.cpp`
- [ ] 提升覆盖率到 80%

**负责人**: C++ 测试工程师
**交付物**: 测试覆盖率报告

---

## Phase 2 验收标准

### 功能验收
- [ ] DHT Client/Server Mode 正常工作
- [ ] DHT Entry Validation 防止恶意记录
- [ ] AutoNAT v2 单地址检测正常
- [ ] 完全使用 Yamux，mplex 已移除

### 性能验收
- [ ] DHT 路由表质量提升 (受限节点不污染路由表)
- [ ] Yamux 性能提升 10-20% (相比 mplex)

### 代码质量验收
- [ ] 代码覆盖率 ≥80%
- [ ] 所有测试通过
- [ ] 代码审查通过

---

## 开发流程和规范

### 分支策略
- `main` - 主分支，稳定版本
- `develop` - 开发分支
- `feature/dcutr` - DCUtR 协议开发
- `feature/relay-v2` - Circuit Relay v2 开发
- `feature/dht-security` - DHT 安全性改进
- `feature/autonat-v2` - AutoNAT v2 开发

### 代码审查
- 所有代码必须经过 Code Review
- 至少 1 人审查通过才能合并
- 使用 GitHub Pull Request

### 测试要求
- 所有新功能必须有单元测试
- 集成测试覆盖关键流程
- 代码覆盖率 ≥80%

### 提交规范
```
<type>: <description>

<optional body>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

Types: feat, fix, refactor, docs, test, chore, perf

### 每日站会
- 时间: 每天上午 10:00
- 内容:
  - 昨天完成了什么
  - 今天计划做什么
  - 遇到什么阻碍

### 每周回顾
- 时间: 每周五下午 4:00
- 内容:
  - 本周完成情况
  - 下周计划
  - 风险和问题

---

## 风险和缓解措施

### 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| DCUtR 实现复杂度高 | 高 | 中 | 参考 go-libp2p 实现，分阶段测试 |
| Protobuf 迁移破坏兼容性 | 高 | 中 | 保留旧协议兼容层，逐步迁移 |
| Signed Envelope 实现错误 | 高 | 低 | 使用官方测试向量验证 |
| 测试覆盖率提升缓慢 | 中 | 中 | 优先核心模块，并行开发 |

### 项目风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 工作量估算不足 | 中 | 中 | 预留 20% 缓冲时间 |
| 团队成员不熟悉 libp2p | 高 | 中 | 前期培训，文档学习 |
| 与现有客户端不兼容 | 高 | 中 | 协议版本协商，保留旧版本支持 |

---

## 资源需求

### 开发环境
- C++20 编译器 (GCC 11+, Clang 14+)
- CMake 3.20+
- 依赖库: Asio, OpenSSL, Protobuf, spdlog, GoogleTest
- 代码覆盖率工具: gcov, lcov
- 静态分析工具: clang-tidy, cppcheck

### 测试环境
- go-libp2p 节点 (互操作性测试)
- 网络模拟工具 (延迟、丢包)
- 性能测试工具 (压力测试)

### 文档
- libp2p 规范: https://github.com/libp2p/specs
- go-libp2p 参考实现: https://github.com/libp2p/go-libp2p
- 项目文档: `docs/`

---

## 联系方式

- **项目负责人**: [待定]
- **技术负责人**: P2P 协议专家
- **Slack 频道**: #p2p-platform-dev
- **每日站会**: Zoom / 线下
- **代码仓库**: https://github.com/[org]/p2p-platform

---

**文档版本**: 1.0
**最后更新**: 2026-03-16
**下次审查**: 每周五
