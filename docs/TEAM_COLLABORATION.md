# P2P Platform 团队协作指南

**团队**: 方案 B (3 人团队)
**生成时间**: 2026-03-16

---

## 团队成员

### 1. P2P 协议专家 (Team Lead)
- **角色**: 技术负责人
- **主要职责**: DCUtR 协议、Circuit Relay v2、Reservation Voucher
- **联系方式**: [待定]

### 2. 资深 C++ 工程师
- **角色**: 核心开发
- **主要职责**: p2p-cpp 引擎、NAT 穿透集成、性能优化
- **联系方式**: [待定]

### 3. C++ 测试工程师
- **角色**: 质量保证
- **主要职责**: 测试框架、覆盖率提升、互操作性测试
- **联系方式**: [待定]

---

## 沟通渠道

### 即时通讯
- **Slack**: #p2p-platform-dev
- **紧急联系**: [待定]

### 会议
- **每日站会**: 每天上午 10:00 (15 分钟)
- **每周回顾**: 每周五下午 4:00 (1 小时)
- **技术讨论**: 按需安排

### 代码协作
- **代码仓库**: https://github.com/[org]/p2p-platform
- **Pull Request**: 所有代码必须通过 PR
- **Code Review**: 至少 1 人审查通过

---

## 开发流程

### 1. 任务领取
1. 从任务看板选择任务
2. 在 Slack 通知团队
3. 创建 feature 分支
4. 更新任务状态为 "进行中"

### 2. 开发
1. 遵循代码规范 (见下文)
2. 编写单元测试 (TDD)
3. 本地测试通过
4. 提交代码 (遵循提交规范)

### 3. 代码审查
1. 创建 Pull Request
2. 填写 PR 模板
3. 请求审查 (至少 1 人)
4. 根据反馈修改
5. 审查通过后合并

### 4. 测试和部署
1. CI/CD 自动运行测试
2. 测试通过后合并到 develop
3. 每周五合并到 main (发布)

---

## 代码规范

### C++ 编码规范
- 遵循 C++ Core Guidelines
- 使用 C++17/20 特性
- 命名规范:
  - 类名: `PascalCase` (例: `DCUtRProtocol`)
  - 函数名: `snake_case` (例: `send_connect_message`)
  - 变量名: `snake_case` (例: `peer_id`)
  - 常量: `UPPER_CASE` (例: `MAX_RETRIES`)

### 代码格式化
- 使用 `clang-format` (配置文件: `.clang-format`)
- 缩进: 4 空格
- 行宽: 100 字符

### 注释规范
```cpp
/**
 * @brief 发送 CONNECT 消息到对端
 *
 * @param peer_id 对端节点 ID
 * @param addrs 本地地址列表
 * @return true 发送成功
 * @return false 发送失败
 */
bool send_connect_message(const bytes& peer_id, const std::vector<multiaddr>& addrs);
```

---

## 测试规范

### 单元测试
- 使用 GoogleTest 框架
- 测试文件命名: `test_<module>.cpp`
- 测试用例命名: `TEST(<TestSuite>, <TestCase>)`

示例:
```cpp
TEST(DCUtRProtocol, SendConnectMessage) {
    DCUtRProtocol protocol;
    bytes peer_id = {0x01, 0x02, 0x03};
    std::vector<multiaddr> addrs = {"/ip4/127.0.0.1/tcp/8080"};

    EXPECT_TRUE(protocol.send_connect_message(peer_id, addrs));
}
```

### 集成测试
- 测试端到端流程
- 使用真实网络环境
- 测试互操作性 (与 go-libp2p)

### 代码覆盖率
- 目标: ≥80%
- 工具: gcov + lcov
- 每周生成覆盖率报告

---

## 提交规范

### Commit Message 格式
```
<type>: <description>

<optional body>

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

### Types
- `feat`: 新功能
- `fix`: Bug 修复
- `refactor`: 代码重构
- `docs`: 文档更新
- `test`: 测试相关
- `chore`: 构建/工具相关
- `perf`: 性能优化

### 示例
```
feat: implement DCUtR protocol CONNECT message

- Add CONNECT message protobuf definition
- Implement send_connect_message() function
- Add unit tests for CONNECT message

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## Pull Request 模板

```markdown
## 描述
简要描述这个 PR 的目的和改动

## 类型
- [ ] 新功能 (feat)
- [ ] Bug 修复 (fix)
- [ ] 代码重构 (refactor)
- [ ] 文档更新 (docs)
- [ ] 测试相关 (test)

## 改动清单
- [ ] 实现了 XXX 功能
- [ ] 修复了 XXX Bug
- [ ] 添加了 XXX 测试

## 测试
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 代码覆盖率 ≥80%

## 检查清单
- [ ] 代码遵循规范
- [ ] 添加了必要的注释
- [ ] 更新了相关文档
- [ ] 通过了 CI/CD 检查

## 相关 Issue
Closes #XXX
```

---

## 分支策略

### 主要分支
- `main` - 生产环境，稳定版本
- `develop` - 开发环境，集成分支

### 功能分支
- `feature/dcutr` - DCUtR 协议开发
- `feature/relay-v2` - Circuit Relay v2 开发
- `feature/dht-security` - DHT 安全性改进
- `feature/autonat-v2` - AutoNAT v2 开发

### 分支命名规范
- 功能分支: `feature/<feature-name>`
- Bug 修复: `fix/<bug-name>`
- 热修复: `hotfix/<issue-name>`

### 合并流程
1. feature 分支 → develop (通过 PR)
2. develop → main (每周五，通过 PR)

---

## 每日站会

### 时间
每天上午 10:00 (15 分钟)

### 内容
每人回答 3 个问题:
1. 昨天完成了什么？
2. 今天计划做什么？
3. 遇到什么阻碍？

### 格式
- 简洁明了，每人 3-5 分钟
- 技术细节留到会后讨论
- 记录阻碍和行动项

---

## 每周回顾

### 时间
每周五下午 4:00 (1 小时)

### 内容
1. **本周完成情况** (20 分钟)
   - 完成的任务
   - 代码统计 (提交数、PR 数)
   - 测试覆盖率变化

2. **下周计划** (15 分钟)
   - 下周任务分配
   - 优先级排序

3. **问题和风险** (15 分钟)
   - 遇到的技术问题
   - 项目风险
   - 需要的支持

4. **改进建议** (10 分钟)
   - 流程改进
   - 工具改进
   - 团队协作改进

---

## 技术讨论

### 何时召开
- 遇到重大技术决策
- 架构设计需要讨论
- 技术方案有争议

### 流程
1. 发起人准备技术方案文档
2. 提前 1 天发送给团队
3. 会议讨论 (1-2 小时)
4. 达成共识，记录决策

### 决策记录
- 文档路径: `docs/decisions/`
- 格式: ADR (Architecture Decision Record)

---

## 工具和资源

### 开发工具
- **IDE**: CLion, VS Code, Visual Studio
- **编译器**: GCC 11+, Clang 14+
- **构建工具**: CMake 3.20+
- **版本控制**: Git

### 测试工具
- **单元测试**: GoogleTest
- **覆盖率**: gcov, lcov
- **静态分析**: clang-tidy, cppcheck
- **内存检测**: Valgrind, AddressSanitizer

### 文档
- **libp2p 规范**: https://github.com/libp2p/specs
- **go-libp2p**: https://github.com/libp2p/go-libp2p
- **项目文档**: `docs/`

### 学习资源
- **C++ Core Guidelines**: https://isocpp.github.io/CppCoreGuidelines/
- **Asio 文档**: https://think-async.com/Asio/
- **Protobuf 文档**: https://protobuf.dev/

---

## 问题升级

### Level 1: 团队内部
- 技术问题先在团队内讨论
- Slack 提问，30 分钟内响应

### Level 2: Team Lead
- 团队无法解决的问题
- 需要外部资源的问题

### Level 3: 项目负责人
- 影响项目进度的问题
- 需要管理层决策的问题

---

## 代码审查指南

### 审查者职责
- 检查代码质量和规范
- 检查测试覆盖率
- 检查性能和安全性
- 提供建设性反馈

### 审查清单
- [ ] 代码遵循规范
- [ ] 逻辑正确，无明显 Bug
- [ ] 测试覆盖充分
- [ ] 注释清晰
- [ ] 无性能问题
- [ ] 无安全漏洞

### 反馈规范
- 使用建设性语言
- 提供具体建议
- 区分 "必须修改" 和 "建议改进"

---

## 紧急情况处理

### 生产环境 Bug
1. 立即通知 Team Lead
2. 创建 hotfix 分支
3. 修复并测试
4. 快速审查和合并
5. 部署到生产环境
6. 事后分析 (Post-mortem)

### 阻塞性问题
1. 在 Slack 标记 @team
2. 召开紧急会议
3. 快速决策
4. 记录决策和行动项

---

**文档版本**: 1.0
**最后更新**: 2026-03-16
**维护者**: Team Lead
