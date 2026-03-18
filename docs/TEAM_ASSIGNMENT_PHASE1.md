# P2P Platform Phase 1 团队分工计划

**基于架构设计**: ARCHITECTURE_DESIGN_PHASE1.md
**团队配置**: 方案 B (3 人团队)
**开发周期**: 2-3 周
**生成时间**: 2026-03-16

---

## 前置工作：架构设计已完成 ✅

两个架构师 agent 已完成深度技术分析：
- ✅ Circuit Relay v2 架构设计
- ✅ DCUtR 协议架构设计
- ✅ 技术头脑风暴和风险识别
- ✅ 模块划分和接口设计
- ✅ 状态机设计和数据流设计
- ✅ 安全性分析和性能目标

**关键文档**:
- `docs/ARCHITECTURE_DESIGN_PHASE1.md` - 综合架构设计
- `docs/TEAM_PLAN_PHASE1.md` - 原始开发计划
- `docs/TEAM_COLLABORATION.md` - 团队协作指南

---

## 团队成员和职责

### 1. P2P 协议专家 (Team Lead) 👨‍💻

**核心职责**: 协议实现和技术决策

**技能要求**:
- libp2p 规范深度理解
- C++17/20 熟练
- Protobuf 和网络协议设计
- Ed25519 密码学
- 有 go-libp2p 经验更佳

**工作量**: 全职 3 周

### 2. 资深 C++ 工程师 👨‍💻

**核心职责**: 核心引擎和集成

**技能要求**:
- C++17/20 熟练 (Boost.Asio, 协程)
- 网络编程 (TCP/UDP/QUIC)
- CMake 构建系统
- OpenSSL (TLS/DTLS)
- 多线程/并发编程

**工作量**: 全职 3 周

### 3. C++ 测试工程师 👨‍💻

**核心职责**: 测试和质量保证

**技能要求**:
- GoogleTest/CTest 框架
- TDD 方法论
- 集成测试、性能测试
- 代码覆盖率工具 (gcov/lcov)
- CI/CD 经验

**工作量**: 全职 3 周

---

## Week 1: 基础设施和 Protobuf (5 天)

### Day 1: 环境搭建和架构学习 (全员)

**目标**: 团队就绪，理解架构

**任务**:
- [ ] 开发环境配置 (C++20, CMake, 依赖库)
- [ ] 代码仓库权限和分支策略
- [ ] 阅读架构设计文档 (`ARCHITECTURE_DESIGN_PHASE1.md`)
- [ ] 阅读 libp2p 规范 (Circuit Relay v2, DCUtR)
- [ ] 团队技术讨论会 (2 小时)

**负责人**: 全员
**交付物**: 开发环境就绪，架构理解一致

---

### Day 2-3: Protobuf 消息格式定义 (协议专家)

**任务**:
- [ ] 定义 Circuit Relay v2 Protobuf 消息
  ```protobuf
  message CircuitRelay {
    enum Type { RESERVE = 0; CONNECT = 1; STATUS = 2; }
    Type type = 1;
    Reservation reservation = 2;
    Peer peer = 3;
    Status status = 4;
  }
  ```
- [ ] 定义 DCUtR Protobuf 消息
  ```protobuf
  message Connect {
    repeated bytes addrs = 1;
    int64 timestamp_ns = 2;
  }
  message Sync {
    repeated bytes addrs = 1;
    int64 echo_timestamp_ns = 2;
    int64 timestamp_ns = 3;
  }
  ```
- [ ] 生成 C++ 代码 (`protoc`)
- [ ] 编写消息序列化/反序列化测试

**负责人**: P2P 协议专家
**交付物**:
- `p2p-cpp/proto/relay_v2.proto`
- `p2p-cpp/proto/dcutr.proto`
- 生成的 C++ 代码
- 单元测试

**文件路径**:
```
p2p-cpp/proto/relay_v2.proto
p2p-cpp/proto/dcutr.proto
p2p-cpp/build/proto/relay_v2.pb.h
p2p-cpp/build/proto/relay_v2.pb.cc
p2p-cpp/build/proto/dcutr.pb.h
p2p-cpp/build/proto/dcutr.pb.cc
p2p-cpp/tests/unit/test_protobuf_messages.cpp
```

---

### Day 2-4: 修复 4 个失败的 C++ 测试 (测试工程师)

**任务**:
- [ ] 修复 `test_dht_providers` (DHT provider 功能)
  - 问题: DHT provider 注册/查询失败
  - 文件: `tests/integration/test_dht_integration.cpp`
- [ ] 修复 `test_noise_multiple_messages` (Noise 签名验证)
  - 问题: Signature verification failed
  - 文件: `tests/integration/test_noise_multistream.cpp`
- [ ] 修复 `test_concurrent_connections` (并发连接握手)
  - 问题: Handshake failed in concurrent scenario
  - 文件: `tests/integration/test_noise_simple.cpp`
- [ ] 修复 `test_dht_provider_discovery_performance` (性能测试)
  - 问题: 性能指标未达标
  - 文件: `tests/integration/test_dht_integration.cpp`

**负责人**: C++ 测试工程师
**交付物**: 所有测试通过，测试报告

**调试步骤**:
1. 运行失败测试，查看错误日志
2. 使用 GDB 调试
3. 修复代码或测试
4. 验证修复
5. 提交 PR

---

### Day 3-5: Signed Envelope 实现 (协议专家)

**任务**:
- [ ] 实现 Ed25519 签名器
  ```cpp
  class Ed25519Signer {
  public:
      std::vector<uint8_t> Sign(
          const Ed25519PrivateKey& key,
          const std::vector<uint8_t>& data
      );

      bool Verify(
          const Ed25519PublicKey& key,
          const std::vector<uint8_t>& data,
          const std::vector<uint8_t>& signature
      );
  };
  ```
- [ ] 实现 Signed Envelope (RFC 0002)
  ```cpp
  struct SignedEnvelope {
      std::string public_key;
      std::string payload_type;
      std::vector<uint8_t> payload;
      std::vector<uint8_t> signature;
  };
  ```
- [ ] 集成 OpenSSL EVP_PKEY_ED25519
- [ ] 编写单元测试 (签名/验证)

**负责人**: P2P 协议专家
**交付物**:
- `p2p-cpp/include/p2p/crypto/ed25519_signer.hpp`
- `p2p-cpp/src/crypto/ed25519_signer.cpp`
- `p2p-cpp/include/p2p/crypto/signed_envelope.hpp`
- `p2p-cpp/src/crypto/signed_envelope.cpp`
- `p2p-cpp/tests/unit/test_ed25519_signer.cpp`

---

### Day 4-5: CMake 构建配置 (C++ 工程师)

**任务**:
- [ ] 配置 Protobuf 编译
  ```cmake
  find_package(Protobuf REQUIRED)
  protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS
      proto/relay_v2.proto
      proto/dcutr.proto
  )
  ```
- [ ] 添加 OpenSSL 依赖
  ```cmake
  find_package(OpenSSL REQUIRED)
  target_link_libraries(p2p-core OpenSSL::Crypto)
  ```
- [ ] 配置代码覆盖率
  ```cmake
  if(ENABLE_COVERAGE)
      set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} --coverage")
  endif()
  ```
- [ ] 更新 CI/CD 配置

**负责人**: 资深 C++ 工程师
**交付物**:
- 更新的 `CMakeLists.txt`
- CI/CD 配置文件
- 编译通过

---

## Week 2: DCUtR 协议实现 (5 天)

### Day 6-8: DCUtR 协议核心实现 (协议专家)

**任务**:
- [ ] 实现 DCUtRClient
  ```cpp
  class DCUtRClient {
  public:
      void InitiateUpgrade(const PeerInfo& peer, UpgradeCallback cb);
      void RespondToUpgrade(std::shared_ptr<DCUtRSession> session, UpgradeCallback cb);
  };
  ```
- [ ] 实现 DCUtRSession 状态机
  ```cpp
  enum class DCUtRState {
      IDLE, CONNECTING, SYNCING, PUNCHING, CONNECTED, FAILED
  };

  class DCUtRSession {
  public:
      void Start();
      void OnConnectReceived(const DCUtRConnectMessage& msg);
      void OnSyncReceived(const DCUtRSyncMessage& msg);
      void OnPunchComplete(bool success, std::shared_ptr<Connection> conn);
  };
  ```
- [ ] 实现 DCUtRCoordinator (RTT 测量和时间同步)
  ```cpp
  class DCUtRCoordinator {
  public:
      void MeasureRTT(std::function<void(RTTMeasurement)> callback);
      PunchSchedule CalculatePunchSchedule(const RTTMeasurement& rtt, DCUtRRole role);
  };
  ```
- [ ] 实现 CONNECT/SYNC 消息处理

**负责人**: P2P 协议专家
**交付物**:
- `p2p-cpp/include/p2p/protocol/dcutr_client.hpp`
- `p2p-cpp/src/protocol/dcutr_client.cpp`
- `p2p-cpp/include/p2p/protocol/dcutr_session.hpp`
- `p2p-cpp/src/protocol/dcutr_session.cpp`
- `p2p-cpp/include/p2p/protocol/dcutr_coordinator.hpp`
- `p2p-cpp/src/protocol/dcutr_coordinator.cpp`
- 单元测试

---

### Day 7-9: 集成 DCUtR 到 NAT 穿透模块 (C++ 工程师)

**任务**:
- [ ] 实现 HolePuncher 统一接口
  ```cpp
  class HolePuncher {
  public:
      std::shared_ptr<Connection> Punch(
          const PeerInfo& peer,
          const PunchSchedule& schedule
      );
  };
  ```
- [ ] 移植 UDPPuncher (从 Python)
  ```cpp
  class UDPPuncher {
  public:
      std::shared_ptr<Connection> StandardPunch(const PeerInfo& peer);
      std::shared_ptr<Connection> SymmetricPunch(const PeerInfo& peer);
  };
  ```
- [ ] 移植 TCPPuncher (从 Python)
  ```cpp
  class TCPPuncher {
  public:
      std::shared_ptr<Connection> SimultaneousOpen(const PeerInfo& peer);
      std::shared_ptr<Connection> Listen(uint16_t port);
  };
  ```
- [ ] 实现 TCP/UDP 并行打孔
- [ ] 实现降级策略 (打孔失败保持中继)

**负责人**: 资深 C++ 工程师
**交付物**:
- `p2p-cpp/include/p2p/nat/hole_puncher.hpp`
- `p2p-cpp/src/nat/hole_puncher.cpp`
- `p2p-cpp/include/p2p/nat/udp_puncher.hpp`
- `p2p-cpp/src/nat/udp_puncher.cpp`
- `p2p-cpp/include/p2p/nat/tcp_puncher.hpp`
- `p2p-cpp/src/nat/tcp_puncher.cpp`
- 集成测试

---

### Day 8-10: DCUtR 测试 (测试工程师)

**任务**:
- [ ] DCUtRSession 单元测试
  - 状态机转换测试
  - 超时处理测试
  - 错误处理测试
- [ ] DCUtRCoordinator 单元测试
  - RTT 测量测试
  - 时间同步测试
  - 打孔调度测试
- [ ] DCUtR 端到端集成测试
  - 发起方 → 响应方流程
  - TCP/UDP 并行打孔
  - 降级策略测试
- [ ] 互操作性测试 (与 go-libp2p)
  - 搭建 go-libp2p 测试节点
  - 验证 CONNECT/SYNC 消息格式
  - 验证打孔成功率

**负责人**: C++ 测试工程师
**交付物**:
- `p2p-cpp/tests/unit/test_dcutr_session.cpp`
- `p2p-cpp/tests/unit/test_dcutr_coordinator.cpp`
- `p2p-cpp/tests/integration/test_dcutr_e2e.cpp`
- `p2p-cpp/tests/integration/test_dcutr_interop.cpp`
- 测试报告

---

## Week 3: Circuit Relay v2 实现 (5 天)

### Day 11-12: Hop 协议实现 (协议专家)

**任务**:
- [ ] 实现 HopProtocol
  ```cpp
  class HopProtocol {
  public:
      void HandleReserve(const ReserveRequest& req, ReserveCallback cb);
      void HandleConnect(const ConnectRequest& req, ConnectCallback cb);
  };
  ```
- [ ] 实现 RESERVE 消息处理
  - 检查资源限制
  - 生成 Reservation Voucher
  - 返回 Reservation
- [ ] 实现 CONNECT 消息处理 (作为中继)
  - 验证 Voucher
  - 建立双向中继
  - 转发数据

**负责人**: P2P 协议专家
**交付物**:
- `p2p-cpp/include/p2p/relay/hop_protocol.hpp`
- `p2p-cpp/src/relay/hop_protocol.cpp`
- 单元测试

---

### Day 11-12: Stop 协议实现 (C++ 工程师)

**任务**:
- [ ] 实现 StopProtocol
  ```cpp
  class StopProtocol {
  public:
      void HandleConnect(const ConnectRequest& req, ConnectCallback cb);
  };
  ```
- [ ] 实现 CONNECT 消息处理 (作为终止端)
  - 验证中继节点身份
  - 接受/拒绝连接
  - 建立流式连接
- [ ] 触发 DCUtR 升级

**负责人**: 资深 C++ 工程师
**交付物**:
- `p2p-cpp/include/p2p/relay/stop_protocol.hpp`
- `p2p-cpp/src/relay/stop_protocol.cpp`
- 单元测试

---

### Day 13-14: Reservation Voucher 实现 (协议专家)

**任务**:
- [ ] 实现 VoucherManager
  ```cpp
  class VoucherManager {
  public:
      SignedEnvelope SignVoucher(const ReservationVoucher& voucher);
      bool VerifyVoucher(const SignedEnvelope& envelope, const PeerID& relay);
  };
  ```
- [ ] 实现 ReservationStore
  ```cpp
  class ReservationStore {
  public:
      void Store(const Reservation& reservation);
      std::optional<Reservation> Lookup(const PeerID& peer);
      void Cleanup();  // 清理过期预留
  };
  ```
- [ ] 实现 ResourceLimiter
  ```cpp
  class ResourceLimiter {
  public:
      bool CheckLimits(const ReserveRequest& req);
      void RateLimit(const PeerID& peer);
  };
  ```

**负责人**: P2P 协议专家
**交付物**:
- `p2p-cpp/include/p2p/relay/voucher_manager.hpp`
- `p2p-cpp/src/relay/voucher_manager.cpp`
- `p2p-cpp/include/p2p/relay/reservation_store.hpp`
- `p2p-cpp/src/relay/reservation_store.cpp`
- `p2p-cpp/include/p2p/relay/resource_limiter.hpp`
- `p2p-cpp/src/relay/resource_limiter.cpp`
- 单元测试

---

### Day 13-14: RelaySession 实现 (C++ 工程师)

**任务**:
- [ ] 实现 RelaySession
  ```cpp
  class RelaySession {
  public:
      void Forward(const std::vector<uint8_t>& data, Direction dir);
      void TrackBandwidth(size_t bytes);
      bool IsExpired() const;
  };
  ```
- [ ] 实现双向数据转发
- [ ] 实现带宽统计和限流
- [ ] 实现会话过期管理

**负责人**: 资深 C++ 工程师
**交付物**:
- `p2p-cpp/include/p2p/relay/relay_session.hpp`
- `p2p-cpp/src/relay/relay_session.cpp`
- 单元测试

---

### Day 14-15: Circuit Relay v2 测试 (测试工程师)

**任务**:
- [ ] Hop 协议单元测试
  - RESERVE 请求处理
  - CONNECT 请求处理
  - Voucher 验证
- [ ] Stop 协议单元测试
  - CONNECT 请求处理
  - 连接接受/拒绝
- [ ] Voucher 安全测试
  - 签名验证测试
  - 过期检查测试
  - 伪造 Voucher 测试
- [ ] Circuit Relay v2 端到端测试
  - RESERVE → CONNECT 流程
  - 数据转发测试
  - 资源限制测试
- [ ] 互操作性测试 (与 go-libp2p)

**负责人**: C++ 测试工程师
**交付物**:
- `p2p-cpp/tests/unit/test_hop_protocol.cpp`
- `p2p-cpp/tests/unit/test_stop_protocol.cpp`
- `p2p-cpp/tests/unit/test_voucher_manager.cpp`
- `p2p-cpp/tests/integration/test_relay_v2_e2e.cpp`
- `p2p-cpp/tests/integration/test_relay_v2_interop.cpp`
- 测试报告

---

## Phase 1 验收标准

### 功能验收

**DCUtR 协议**:
- [ ] CONNECT/SYNC 消息交换正常
- [ ] RTT 测量精度 <10ms
- [ ] TCP/UDP 并行打孔成功
- [ ] 打孔失败降级到中继
- [ ] 与 go-libp2p 互操作性通过

**Circuit Relay v2**:
- [ ] RESERVE 请求处理正常
- [ ] CONNECT 请求处理正常
- [ ] Voucher 签名验证通过
- [ ] 资源限制生效
- [ ] 数据转发正常
- [ ] 与 go-libp2p 互操作性通过

**集成**:
- [ ] DCUtR 通过中继协调打孔
- [ ] 打孔成功后关闭中继
- [ ] 所有 C++ 测试通过

### 性能验收

- [ ] DCUtR 打孔成功率 >80%
- [ ] 中继连接建立延迟 <500ms
- [ ] Voucher 验证延迟 <1ms
- [ ] 并发中继连接 >100
- [ ] 内存泄漏检测通过 (Valgrind)

### 代码质量验收

- [ ] 代码覆盖率 >60% (Phase 1 目标)
- [ ] 无编译警告
- [ ] 通过静态分析 (clang-tidy)
- [ ] 代码审查通过
- [ ] 文档完整

---

## 每日站会

**时间**: 每天上午 10:00 (15 分钟)

**内容**:
1. 昨天完成了什么？
2. 今天计划做什么？
3. 遇到什么阻碍？

**记录**: 在 Slack #p2p-platform-dev 频道

---

## 每周回顾

**时间**: 每周五下午 4:00 (1 小时)

**内容**:
1. 本周完成情况 (对照任务清单)
2. 下周计划
3. 问题和风险
4. 改进建议

**记录**: 更新 `docs/WEEKLY_REPORT_WEEKX.md`

---

## 技术讨论会

**触发条件**:
- 遇到重大技术决策
- 架构设计需要讨论
- 技术方案有争议

**流程**:
1. 发起人准备技术方案文档
2. 提前 1 天发送给团队
3. 会议讨论 (1-2 小时)
4. 达成共识，记录决策

**决策记录**: `docs/decisions/ADR-XXX.md`

---

## 风险管理

### 技术风险

| 风险 | 缓解措施 | 负责人 |
|------|---------|--------|
| RTT 测量不准确 | 多次测量 + EWMA 平滑 | 协议专家 |
| 时间同步失败 | 增加容错窗口 | 协议专家 |
| 状态机死锁 | 严格超时机制 | 协议专家 |
| 内存泄漏 | RAII + 智能指针 | C++ 工程师 |
| 测试覆盖率不足 | 并行编写测试 | 测试工程师 |

### 项目风险

| 风险 | 缓解措施 | 负责人 |
|------|---------|--------|
| 工作量估算不足 | 预留 20% 缓冲时间 | Team Lead |
| 团队成员不熟悉 libp2p | 前期培训，文档学习 | Team Lead |
| 与现有客户端不兼容 | 协议版本协商 | 协议专家 |

---

## 交付物清单

### 代码

- [ ] Circuit Relay v2 实现 (Hop/Stop 协议)
- [ ] DCUtR 协议实现
- [ ] Reservation Voucher 实现
- [ ] NAT 穿透模块 (HolePuncher, UDPPuncher, TCPPuncher)
- [ ] Protobuf 消息定义
- [ ] 单元测试 (>60% 覆盖率)
- [ ] 集成测试
- [ ] 互操作性测试

### 文档

- [ ] 架构设计文档 (已完成)
- [ ] API 文档 (Doxygen)
- [ ] 测试报告
- [ ] 每周进度报告
- [ ] 技术决策记录 (ADR)

### 其他

- [ ] CI/CD 配置
- [ ] 代码覆盖率报告
- [ ] 性能测试报告

---

**文档版本**: 2.0 (基于架构设计更新)
**最后更新**: 2026-03-16
**下次审查**: 每周五
