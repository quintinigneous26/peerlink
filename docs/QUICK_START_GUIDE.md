# P2P Platform 快速启动指南

**目标读者**: 新加入的团队成员
**预计时间**: 1 天

---

## 第一步: 环境准备 (2 小时)

### 1.1 安装编译工具

**macOS**:
```bash
# 安装 Xcode Command Line Tools
xcode-select --install

# 安装 Homebrew (如果没有)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装依赖
brew install cmake gcc@11 openssl@3 protobuf spdlog
```

**Linux (Ubuntu/Debian)**:
```bash
sudo apt update
sudo apt install -y build-essential cmake gcc-11 g++-11 \
    libssl-dev libprotobuf-dev protobuf-compiler libspdlog-dev
```

### 1.2 克隆代码仓库

```bash
cd ~/work
git clone https://github.com/[org]/p2p-platform.git
cd p2p-platform
```

### 1.3 安装 Asio

```bash
# 下载 Asio 1.28+
cd /tmp
wget https://github.com/chriskohlhoff/asio/archive/refs/tags/asio-1-28-0.tar.gz
tar -xzf asio-1-28-0.tar.gz
sudo cp -r asio-asio-1-28-0/asio/include/asio* /usr/local/include/
```

### 1.4 安装 GoogleTest

```bash
cd /tmp
git clone https://github.com/google/googletest.git
cd googletest
mkdir build && cd build
cmake ..
make -j$(nproc)
sudo make install
```

---

## 第二步: 编译项目 (30 分钟)

### 2.1 配置 CMake

```bash
cd ~/work/p2p-platform/p2p-cpp
mkdir build && cd build

# 配置
cmake .. \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_CXX_COMPILER=g++-11 \
    -DBUILD_TESTS=ON \
    -DENABLE_COVERAGE=ON
```

### 2.2 编译

```bash
# 编译 (使用所有 CPU 核心)
make -j$(nproc)

# 预计时间: 5-10 分钟
```

### 2.3 验证编译

```bash
# 检查生成的库
ls -lh lib/

# 应该看到:
# libp2p-core.a
# libp2p-protocol.a
# libp2p-transport.a
# libp2p-nat.a
# libp2p-security.a
```

---

## 第三步: 运行测试 (30 分钟)

### 3.1 运行所有测试

```bash
cd ~/work/p2p-platform/p2p-cpp/build

# 运行所有测试
ctest --output-on-failure

# 或者使用 make
make test
```

### 3.2 运行特定测试

```bash
# 运行 STUN 测试
./tests/stun/stun_test

# 运行 Relay 测试
./tests/servers/relay/relay_test

# 运行 DCUtR 测试 (如果已实现)
./tests/protocol/dcutr_test
```

### 3.3 生成覆盖率报告

```bash
# 生成覆盖率数据
make coverage

# 查看 HTML 报告
open coverage/index.html  # macOS
xdg-open coverage/index.html  # Linux
```

---

## 第四步: 熟悉代码结构 (2 小时)

### 4.1 目录结构

```
p2p-cpp/
├── include/p2p/          # 公共头文件
│   ├── core/             # 核心引擎
│   ├── protocol/         # 协议实现
│   ├── transport/        # 传输层
│   ├── nat/              # NAT 穿透
│   ├── security/         # 安全模块
│   └── servers/          # 服务器
├── src/                  # 实现文件
│   ├── core/
│   ├── protocol/
│   ├── transport/
│   ├── nat/
│   ├── security/
│   └── servers/
├── tests/                # 测试文件
│   ├── stun/
│   ├── servers/
│   └── protocol/
├── examples/             # 示例代码
└── docs/                 # 文档
```

### 4.2 关键文件

**核心引擎**:
- `include/p2p/core/engine.hpp` - 主引擎
- `include/p2p/core/connection.hpp` - 连接管理
- `include/p2p/core/event.hpp` - 事件系统

**协议实现**:
- `include/p2p/protocol/handshake.hpp` - 握手协议
- `include/p2p/protocol/channel.hpp` - 通道协议
- `include/p2p/protocol/dcutr.hpp` - DCUtR 协议 (待实现)

**NAT 穿透**:
- `include/p2p/nat/stun_client.hpp` - STUN 客户端
- `include/p2p/nat/puncher.hpp` - 打孔器
- `include/p2p/nat/detector.hpp` - NAT 检测

**服务器**:
- `include/p2p/servers/stun/stun_server.hpp` - STUN 服务器
- `include/p2p/servers/relay/relay_server.hpp` - Relay 服务器
- `include/p2p/servers/relay/hop_protocol.hpp` - Hop 协议 (待实现)

### 4.3 阅读文档

```bash
cd ~/work/p2p-platform/docs

# 必读文档
cat ARCHITECTURE.md          # 架构设计
cat LIBP2P_SPEC_COMPLIANCE_ANALYSIS.md  # libp2p 规范符合度
cat TEAM_PLAN_PHASE1.md      # Phase 1 开发计划
cat TEAM_COLLABORATION.md    # 团队协作指南
```

---

## 第五步: 开发第一个功能 (4 小时)

### 5.1 创建 feature 分支

```bash
cd ~/work/p2p-platform
git checkout develop
git pull origin develop

# 创建 feature 分支
git checkout -b feature/my-first-feature
```

### 5.2 编写测试 (TDD)

创建测试文件 `tests/protocol/test_my_feature.cpp`:

```cpp
#include <gtest/gtest.h>
#include "p2p/protocol/my_feature.hpp"

TEST(MyFeature, BasicTest) {
    MyFeature feature;
    EXPECT_TRUE(feature.is_valid());
}

TEST(MyFeature, ProcessData) {
    MyFeature feature;
    std::vector<uint8_t> data = {0x01, 0x02, 0x03};
    auto result = feature.process(data);
    EXPECT_EQ(result.size(), 3);
}
```

### 5.3 实现功能

创建头文件 `include/p2p/protocol/my_feature.hpp`:

```cpp
#pragma once

#include <vector>
#include <cstdint>

namespace p2p::protocol {

class MyFeature {
public:
    MyFeature() = default;
    ~MyFeature() = default;

    bool is_valid() const;
    std::vector<uint8_t> process(const std::vector<uint8_t>& data);

private:
    bool valid_ = true;
};

}  // namespace p2p::protocol
```

创建实现文件 `src/protocol/my_feature.cpp`:

```cpp
#include "p2p/protocol/my_feature.hpp"

namespace p2p::protocol {

bool MyFeature::is_valid() const {
    return valid_;
}

std::vector<uint8_t> MyFeature::process(const std::vector<uint8_t>& data) {
    // 实现处理逻辑
    return data;
}

}  // namespace p2p::protocol
```

### 5.4 编译和测试

```bash
cd ~/work/p2p-platform/p2p-cpp/build

# 重新配置 (如果添加了新文件)
cmake ..

# 编译
make -j$(nproc)

# 运行测试
./tests/protocol/test_my_feature

# 或者运行所有测试
ctest --output-on-failure
```

### 5.5 提交代码

```bash
# 添加文件
git add include/p2p/protocol/my_feature.hpp
git add src/protocol/my_feature.cpp
git add tests/protocol/test_my_feature.cpp

# 提交
git commit -m "feat: implement my first feature

- Add MyFeature class
- Add unit tests
- Test coverage: 100%

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

# 推送到远程
git push origin feature/my-first-feature
```

### 5.6 创建 Pull Request

1. 访问 GitHub 仓库
2. 点击 "New Pull Request"
3. 选择 `feature/my-first-feature` → `develop`
4. 填写 PR 模板
5. 请求审查

---

## 第六步: 熟悉 libp2p 规范 (2 小时)

### 6.1 必读规范

**DCUtR 协议**:
- https://github.com/libp2p/specs/blob/master/relay/DCUtR.md
- 理解 CONNECT/SYNC 消息流程
- 理解 RTT 测量和同步机制

**Circuit Relay v2**:
- https://github.com/libp2p/specs/blob/master/relay/circuit-v2.md
- 理解 Hop/Stop 协议
- 理解 Reservation Voucher 机制

**Yamux**:
- https://github.com/libp2p/specs/blob/master/yamux/README.md
- 理解帧格式和流控机制

### 6.2 参考实现

**go-libp2p**:
```bash
# 克隆 go-libp2p
cd /tmp
git clone https://github.com/libp2p/go-libp2p.git
cd go-libp2p

# 查看 DCUtR 实现
cat p2p/protocol/holepunch/holepunch.go

# 查看 Circuit Relay v2 实现
cat p2p/protocol/circuitv2/relay/relay.go
```

---

## 常见问题

### Q1: 编译失败，找不到 Asio
**A**: 确保 Asio 头文件在 `/usr/local/include/` 或 CMake 能找到的路径

### Q2: 测试失败，端口被占用
**A**: 修改测试配置，使用不同的端口范围

### Q3: 代码覆盖率报告为空
**A**: 确保使用 `-DENABLE_COVERAGE=ON` 编译，并运行 `make coverage`

### Q4: 如何调试测试
**A**: 使用 GDB 或 LLDB:
```bash
gdb ./tests/protocol/test_my_feature
(gdb) run
(gdb) bt  # 查看堆栈
```

### Q5: 如何查看日志
**A**: 设置日志级别:
```cpp
#include <spdlog/spdlog.h>
spdlog::set_level(spdlog::level::debug);
```

---

## 下一步

1. 阅读 Phase 1 开发计划 (`docs/TEAM_PLAN_PHASE1.md`)
2. 领取第一个任务
3. 参加每日站会
4. 开始开发！

---

## 联系方式

- **Team Lead**: [待定]
- **Slack**: #p2p-platform-dev
- **紧急联系**: [待定]

---

**文档版本**: 1.0
**最后更新**: 2026-03-16
