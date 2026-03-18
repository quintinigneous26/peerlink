# Phase 2 Task #13 实施计划 - go-libp2p 互操作测试

**日期**: 2026-03-16
**任务**: Task #13 - go-libp2p Interoperability Testing
**负责人**: 测试工程师 + P2P 协议专家
**优先级**: P0
**状态**: 规划中

---

## 执行摘要

Task #13 的目标是验证我们的 C++ P2P 实现与 go-libp2p 的互操作性，确保消息格式兼容、协议流程正确，并能够在真实网络环境中进行双向通信。

**前置条件**:
- ✅ Task #11 (Protobuf 消息序列化) 已完成
- ✅ Task #12 (协议版本协商) 已完成
- ❌ Go 环境需要安装
- ❌ go-libp2p 需要安装

---

## Phase 1: 环境搭建 (Day 1, 上午)

### 1.1 安装 Go 环境

```bash
# macOS
brew install go

# 验证安装
go version  # 期望: go1.21+ 或更高版本

# 配置 Go 环境变量
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin
```

### 1.2 安装 go-libp2p

```bash
# 创建测试项目目录
mkdir -p ~/work/p2p-platform/interop-tests/go-libp2p-test
cd ~/work/p2p-platform/interop-tests/go-libp2p-test

# 初始化 Go 模块
go mod init github.com/p2p-platform/interop-test

# 安装 go-libp2p 核心库
go get github.com/libp2p/go-libp2p@latest
go get github.com/libp2p/go-libp2p/p2p/protocol/circuitv2/relay@latest
go get github.com/libp2p/go-libp2p/p2p/protocol/holepunch@latest

# 安装辅助库
go get github.com/multiformats/go-multiaddr@latest
go get github.com/libp2p/go-libp2p-core@latest
```

### 1.3 验证 go-libp2p 安装

创建简单的 Go 测试程序验证安装:

```go
// test_install.go
package main

import (
    "context"
    "fmt"
    "github.com/libp2p/go-libp2p"
)

func main() {
    ctx := context.Background()
    
    // 创建一个基本的 libp2p host
    host, err := libp2p.New(ctx)
    if err != nil {
        panic(err)
    }
    defer host.Close()
    
    fmt.Printf("libp2p host created successfully!\n")
    fmt.Printf("Peer ID: %s\n", host.ID())
    fmt.Printf("Addresses: %v\n", host.Addrs())
}
```

运行测试:
```bash
go run test_install.go
```

---

## Phase 2: 实现测试程序 (Day 1, 下午)

### 2.1 Go Relay Server (Circuit Relay v2)

创建 `relay_server.go`:

```go
package main

import (
    "context"
    "fmt"
    "log"
    
    "github.com/libp2p/go-libp2p"
    "github.com/libp2p/go-libp2p/p2p/protocol/circuitv2/relay"
)

func main() {
    ctx := context.Background()
    
    // 创建 relay host
    host, err := libp2p.New(ctx,
        libp2p.ListenAddrStrings("/ip4/0.0.0.0/tcp/9000"),
        libp2p.EnableRelay(),
    )
    if err != nil {
        log.Fatal(err)
    }
    defer host.Close()
    
    // 启动 relay 服务
    _, err = relay.New(host)
    if err != nil {
        log.Fatal(err)
    }
    
    fmt.Printf("Relay server started\n")
    fmt.Printf("Peer ID: %s\n", host.ID())
    fmt.Printf("Listening on: %v\n", host.Addrs())
    
    // 保持运行
    select {}
}
```

### 2.2 Go DCUtR Client

创建 `dcutr_client.go`:

```go
package main

import (
    "context"
    "fmt"
    "log"
    "time"
    
    "github.com/libp2p/go-libp2p"
    "github.com/libp2p/go-libp2p/p2p/protocol/holepunch"
    "github.com/multiformats/go-multiaddr"
)

func main() {
    ctx := context.Background()
    
    // 创建 client host
    host, err := libp2p.New(ctx,
        libp2p.ListenAddrStrings("/ip4/0.0.0.0/tcp/0"),
        libp2p.EnableHolePunching(),
    )
    if err != nil {
        log.Fatal(err)
    }
    defer host.Close()
    
    fmt.Printf("DCUtR client started\n")
    fmt.Printf("Peer ID: %s\n", host.ID())
    
    // 连接到 relay
    relayAddr, _ := multiaddr.NewMultiaddr("/ip4/127.0.0.1/tcp/9000")
    relayInfo, err := peer.AddrInfoFromP2pAddr(relayAddr)
    if err != nil {
        log.Fatal(err)
    }
    
    if err := host.Connect(ctx, *relayInfo); err != nil {
        log.Fatal(err)
    }
    
    fmt.Println("Connected to relay")
    
    // 等待 hole punching
    time.Sleep(30 * time.Second)
}
```

### 2.3 消息格式测试程序

创建 `message_test.go`:

```go
package main

import (
    "fmt"
    "testing"
    
    pb "github.com/libp2p/go-libp2p/p2p/protocol/circuitv2/pb"
    "google.golang.org/protobuf/proto"
)

func TestRelayMessageSerialization(t *testing.T) {
    // 创建 RESERVE 消息
    msg := &pb.CircuitRelay{
        Type: pb.CircuitRelay_RESERVE.Enum(),
    }
    
    // 序列化
    data, err := proto.Marshal(msg)
    if err != nil {
        t.Fatal(err)
    }
    
    fmt.Printf("Serialized RESERVE message: %d bytes\n", len(data))
    fmt.Printf("Hex: %x\n", data)
    
    // 反序列化
    msg2 := &pb.CircuitRelay{}
    if err := proto.Unmarshal(data, msg2); err != nil {
        t.Fatal(err)
    }
    
    if msg2.GetType() != pb.CircuitRelay_RESERVE {
        t.Fatal("Type mismatch")
    }
    
    fmt.Println("Message round-trip successful")
}
```

---

## Phase 3: 互操作测试 (Day 2, 上午)

### 3.1 测试场景 1: C++ Client → Go Relay Server

**目标**: C++ 客户端连接到 Go relay 服务器，发送 RESERVE 消息

**步骤**:
1. 启动 Go relay server
2. 运行 C++ 客户端连接到 Go server
3. 发送 RESERVE 消息
4. 验证响应

**C++ 测试代码** (伪���码):
```cpp
// test_cpp_to_go_relay.cpp
#include "p2p/protocol/relay_message.hpp"
#include "p2p/net/socket.hpp"

int main() {
    // 连接到 Go relay server
    TCPSocket socket;
    socket.Connect("127.0.0.1", 9000);
    
    // 创建 RESERVE 消息
    auto msg = RelayMessageWrapper::CreateReserve();
    auto data = msg.Serialize();
    
    // 发送消息
    socket.Send(data);
    
    // 接收响应
    auto response = socket.Receive();
    auto response_msg = RelayMessageWrapper::Deserialize(response);
    
    // 验证响应
    assert(response_msg.has_value());
    assert(response_msg->GetType() == RelayMessageType::STATUS);
    
    std::cout << "C++ → Go relay test PASSED\n";
    return 0;
}
```

### 3.2 测试场景 2: Go Client → C++ Relay Server

**目标**: Go 客户端连接到 C++ relay 服务器

**步骤**:
1. 启动 C++ relay server
2. 运行 Go 客户端连接到 C++ server
3. 发送 RESERVE 消息
4. 验证响应

### 3.3 测试场景 3: DCUtR 协议互操作

**目标**: 测试 DCUtR CONNECT/SYNC 消息的互操作性

**步骤**:
1. C++ 发送 CONNECT 消息 → Go 接收并解析
2. Go 发送 SYNC 消息 → C++ 接收并解析
3. 验证时间戳和地址信息

### 3.4 测试场景 4: 端到端 NAT 穿透

**目标**: 完整的 NAT 穿透流程测试

**步骤**:
1. 启动 Go relay server
2. 启动 C++ peer A (behind NAT)
3. 启动 Go peer B (behind NAT)
4. Peer A 和 Peer B 通过 relay 建立连接
5. 执行 DCUtR hole punching
6. 验证直连建立成功

---

## Phase 4: 性能和兼容性测试 (Day 2, 下午)

### 4.1 消息格式兼容性测试

**测试矩阵**:

| 消息类型 | C++ → Go | Go → C++ | 状态 |
|---------|----------|----------|------|
| RESERVE | [ ] | [ ] | |
| CONNECT (Relay) | [ ] | [ ] | |
| STATUS | [ ] | [ ] | |
| CONNECT (DCUtR) | [ ] | [ ] | |
| SYNC | [ ] | [ ] | |

### 4.2 协议流程测试

**测试用例**:
1. **Relay 预留流程**
   - C++ client → Go relay: RESERVE
   - Go relay → C++ client: STATUS (OK + Reservation)
   
2. **Relay 连接流程**
   - C++ client A → Go relay: CONNECT (to peer B)
   - Go relay → C++ client B: CONNECT notification
   - Bidirectional data forwarding

3. **DCUtR 流程**
   - C++ initiator → Go responder: CONNECT (via relay)
   - Go responder → C++ initiator: SYNC (via relay)
   - Direct connection establishment

### 4.3 性能基准测试

**测试指标**:
- 消息序列化/反序列化时间
- 连接建立延迟
- 数据转发吞吐量
- NAT 穿透成功率

---

## Phase 5: 问题诊断和修复 (按需)

### 5.1 常见问题

**问题 1: 消息格式不兼容**
- 症状: 反序列化失败
- 诊断: 使用 Wireshark 抓包对比
- 修复: 调整 Protobuf 定义或序列化逻辑

**问题 2: 协议版本不匹配**
- 症状: 版本协商失败
- 诊断: 检查 ProtocolNegotiator 配置
- 修复: 更新支持的版本列表

**问题 3: 网络连接问题**
- 症状: 连接超时或拒绝
- 诊断: 检查防火墙、端口配置
- 修复: 调整网络配置

### 5.2 调试工具

**Wireshark 抓包**:
```bash
# 捕获 localhost 流量
sudo tcpdump -i lo0 -w interop_test.pcap port 9000

# 使用 Wireshark 分析
wireshark interop_test.pcap
```

**Protobuf 消息解析**:
```bash
# 使用 protoc 解析二进制消息
protoc --decode=p2p.relay.v2.CircuitRelay relay_v2.proto < message.bin
```

---

## 验收标准

### 功能验收
- [ ] C++ 和 Go 实现可以互相通信
- [ ] 所有协议流程正常工作
- [ ] 消息格式完全兼容
- [ ] 互操作测试通过率 > 95%

### 性能验收
- [ ] 消息序列化性能相当 (误差 < 20%)
- [ ] 连接建立延迟相当 (误差 < 50ms)
- [ ] 数据转发性能相当 (误差 < 30%)

### 质量验收
- [ ] 测试代码覆盖所有消息类型
- [ ] 测试覆盖所有协议流程
- [ ] 有详细的测试报告
- [ ] 问题和修复都有文档记录

---

## 交付物

### 代码交付
1. Go 测试程序 (relay_server.go, dcutr_client.go, message_test.go)
2. C++ 互操作测试 (test_cpp_to_go_relay.cpp, test_go_to_cpp_relay.cpp)
3. 测试脚本 (run_interop_tests.sh)

### 文档交付
1. 环境搭建指南
2. 测试执行指南
3. 互操作测试报告
4. 问题和修复记录

### 数据交付
1. 测试日志
2. 抓包文件
3. 性能测试数据

---

## 风险和缓解

### 风险 1: go-libp2p 版本兼容性
**影响**: 高
**概率**: 中
**缓解**: 使用稳定版本 (v0.35+)，参考官方文档

### 风险 2: Protobuf 版本差异
**影响**: 高
**概率**: 中
**缓解**: 使用相同的 Protobuf 版本，验证生成的代码

### 风险 3: 网络环境限制
**影响**: 中
**概率**: 低
**缓解**: 使用 localhost 测试，必要时使用 Docker 网络

---

## 下一步

完成 Task #13 后，继续:
- Task #14: 内存池优化
- Task #15: 零拷贝优化
- Task #16: 并发性能提升

---

**计划生成**: 2026-03-16
**版本**: 1.0
**状态**: 待执行
