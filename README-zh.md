# P2P Platform

<div align="center">

**基于 WebRTC 和 libp2p 技术的去中心化 P2P 通信平台**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Test Coverage](https://img.shields.io/badge/coverage-80%25+-green.svg)](./docs/TESTING.md)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](./docker-compose.yml)

[特性](#-主要特性) • [快速开始](#-快速开始) • [安装](#-安装方式) • [文档](#-文档) • [贡献](#-贡献指南)

</div>

---

## 📖 项目简介

P2P Platform 是一套完整的去中心化 P2P 通信解决方案，实现了 libp2p 协议栈和 WebRTC 技术的深度集成。平台提供了从 NAT 穿透、设备发现、安全传输到流复用的全栈能力，支持构建高性能、可扩展的 P2P 应用。

### 核心优势

- 🚀 **高性能**: P2P 直连吞吐量 ~150 Mbps，本地连接延迟 ~50ms
- 🔒 **安全可靠**: TLS 1.3 加密，Ed25519 签名，完整的证书链验证
- 🌐 **libp2p 兼容**: 完整实现 libp2p 协议栈，与 go-libp2p 互操作
- 📦 **开箱即用**: Docker Compose 一键部署，支持 RPM/DEB/pip 安装
- 🧪 **测试完善**: 575 个测试用例，95.1% 通过率，≥80% 代码覆盖率
- 🛠️ **易于集成**: 简洁的客户端 SDK，支持 Python/Go/Rust/JavaScript

---

## ✨ 主要特性

### 核心服务

| 服务 | 功能 | 端口 |
|------|------|------|
| **STUN 服务器** | NAT 穿透、公网 IP 获取、NAT 类型检测 | 3478 (UDP), 3479 (TCP) |
| **Relay 服务器** | TURN 中继、UDP/TCP 转发、带宽管理 | 50000-50010 |
| **信令服务器** | 设备注册、SDP 交换、连接协调 | 8080 (WS), 8443 (WSS) |
| **DID 服务** | 设备身份认证、访问令牌管理 | 9000 (HTTP) |
| **客户端 SDK** | 简化 P2P 连接开发 | - |

### libp2p 协议栈

#### 安全传输
- ✅ TLS 1.3 (`/tls/1.0.0`)
- ✅ Noise (`/noise`)

#### 流复用
- ✅ mplex (`/mplex/6.7.0`)
- ✅ yamux (`/yamux/1.0.0`)

#### 核心协议
- ✅ multistream-select (`/multistream/1.0.0`)
- ✅ Identify (`/ipfs/id/1.0.0`)
- ✅ AutoNAT (`/libp2p/autonat/1.0.0`)
- ✅ Circuit Relay v2 (`/libp2p/circuit/relay/0.2.0/hop`)
- ✅ DCUtR (`/libp2p/dcutr/1.0.0`)
- ✅ Ping (`/ipfs/ping/1.0.0`)

#### 高级功能
- ✅ Kademlia DHT (`/ipfs/kad/1.0.0`) - 分布式哈希表
- ✅ GossipSub v1.1 (`/meshsub/1.1.0`) - 发布订阅

#### 传输层
- ✅ TCP
- ✅ QUIC (`/quic-v1`)
- ✅ WebRTC (`/webrtc-direct`)
- ✅ WebTransport (`/webtransport/1.0.0`)

### 网络优化

- 🌍 28 个全球运营商配置
- 📱 22 个设备厂商检测
- 💓 智能心跳和降级策略
- 🔍 NAT 类型检测 (Full Cone, Restricted, Port Restricted, Symmetric)

---

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (如果不使用 Docker)

### 使用 Docker Compose (推荐)

```bash
# 克隆项目
git clone https://github.com/hbliu007/peerlink.git
cd p2p-platform

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

服务启动后，可以通过以下地址访问：

- STUN 服务器: `udp://localhost:3478`
- Relay 服务器: `udp://localhost:50000-50010`
- 信令服务器: `ws://localhost:8080`
- DID 服务: `http://localhost:9000`

### 使用客户端 SDK

```python
from client_sdk import P2PClient

# 创建客户端
client = P2PClient(
    signaling_url="ws://localhost:8080",
    stun_server="localhost:3478"
)

# 注册设备
await client.register(device_id="device-001")

# 连接到另一个设备
connection = await client.connect(target_device="device-002")

# 发送数据
await connection.send(b"Hello, P2P!")

# 接收数据
data = await connection.receive()
print(f"Received: {data}")

# 关闭连接
await connection.close()
```

---

## 📦 安装方式

### 方式 1: Docker (推荐)

```bash
docker-compose up -d
```

### 方式 2: RPM 包 (CentOS/RHEL/Fedora)

```bash
# 下载 RPM 包
wget https://github.com/hbliu007/peerlink/releases/download/v1.0.0/p2p-platform-1.0.0.rpm

# 安装
sudo rpm -ivh p2p-platform-1.0.0.rpm

# 启动服务
sudo systemctl start p2p-stun
sudo systemctl start p2p-relay
sudo systemctl start p2p-signaling
sudo systemctl start p2p-did

# 设置开机自启
sudo systemctl enable p2p-stun p2p-relay p2p-signaling p2p-did
```

### 方式 3: DEB 包 (Ubuntu/Debian)

```bash
# 下载 DEB 包
wget https://github.com/hbliu007/peerlink/releases/download/v1.0.0/p2p-platform_1.0.0_amd64.deb

# 安装
sudo dpkg -i p2p-platform_1.0.0_amd64.deb
sudo apt-get install -f  # 安装依赖

# 启动服务
sudo systemctl start p2p-stun
sudo systemctl start p2p-relay
sudo systemctl start p2p-signaling
sudo systemctl start p2p-did
```

### 方式 4: pip 安装 (仅客户端 SDK)

```bash
pip install p2p-platform-sdk
```

### 方式 5: 源码安装

```bash
# 克隆项目
git clone https://github.com/hbliu007/peerlink.git
cd p2p-platform

# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest tests/ -v

# 启动服务 (需要分别启动各个服务)
python stun-server/main.py &
python relay-server/main.py &
python signaling-server/main.py &
python did-service/main.py &
```

---

## 📚 文档

### 核心文档

- [架构设计](./docs/architecture.md) - 系统架构和组件说明
- [API 规范](./docs/api-spec.md) - REST API 和 WebSocket 接口
- [用户手册](./docs/USER_GUIDE.md) - 安装、配置和使用指南
- [开发者指南](./docs/DEVELOPER_GUIDE.md) - 贡献流程和开发规范
- [测试指南](./docs/TESTING.md) - 测试框架和测试用例
- [部署指南](./DEPLOYMENT.md) - 生产环境部署步骤
- [运维手册](./OPERATIONS.md) - 服务管理和故障排查

### 技术文档

- [libp2p 对比分析](./docs/libp2p-comparison-analysis.md)
- [客户端 SDK 设计](./docs/CLIENT-SDK-DESIGN-PROPOSAL.md)
- [性能优化报告](./docs/P2P-PLATFORM-OPTIMIZATION-FINAL-REPORT.md)
- [项目完成报告](./docs/PROJECT-COMPLETION-REPORT.md)

### 发布说明

- [CHANGELOG](./CHANGELOG.md) - 版本变更历史
- [RELEASE NOTES](./RELEASE_NOTES.md) - v1.0.0 发布说明

---

## 🧪 测试

```bash
# 运行所有测试
pytest tests/ -v --cov=p2p_engine --cov-report=html

# 运行单元测试
pytest tests/unit/ -v

# 运行集成测试
pytest tests/integration/ -v

# 运行互操作性测试
pytest tests/interop/ -v

# 运行性能测试
pytest tests/benchmark/ -v -m benchmark

# 查看覆盖率报告
open htmlcov/index.html
```

---

## 🛠️ 配置

### 环境变量

```bash
# STUN 服务器
STUN_PORT=3478
STUN_TCP_PORT=3479

# Relay 服务器
RELAY_MIN_PORT=50000
RELAY_MAX_PORT=50010
RELAY_MAX_ALLOCATIONS=1000
RELAY_ALLOCATION_LIFETIME=600

# 信令服务器
SIGNALING_WS_PORT=8080
SIGNALING_WSS_PORT=8443
REDIS_URL=redis://localhost:6379

# DID 服务
DID_SERVICE_PORT=9000
JWT_SECRET=your-secret-key-change-in-production
JWT_EXPIRATION=3600
```

### 配置文件

详细配置请参考 [docker-compose.yml](./docker-compose.yml) 和各服务目录下的配置文件。

---

## 📊 性能指标

| 指标 | 目标 | 实际 |
|------|------|------|
| 本地连接延迟 | < 100ms | ~50ms ✅ |
| 远程连接延迟 | < 500ms | ~200ms ✅ |
| 中继连接延迟 | < 1000ms | ~500ms ✅ |
| P2P 直连吞吐量 | > 100 Mbps | ~150 Mbps ✅ |
| 中继吞吐量 | > 10 Mbps | ~15 Mbps ✅ |
| 并发连接数 | 100+ | 500+ ✅ |

---

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 提交规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `test`: 测试相关
- `refactor`: 代码重构
- `perf`: 性能优化
- `chore`: 构建/工具链更新

### 代码规范

- Python 代码遵循 PEP 8
- 使用 `black` 格式化代码
- 使用 `mypy` 进行类型检查
- 测试覆盖率 ≥ 80%

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

感谢以下项目和社区：

- [libp2p](https://libp2p.io/) - 模块化网络栈
- [WebRTC](https://webrtc.org/) - 实时通信技术
- [aioquic](https://github.com/aiortc/aioquic) - Python QUIC 实现
- [aiortc](https://github.com/aiortc/aiortc) - Python WebRTC 实现

---

## 📞 联系我们

- 问题反馈: [GitHub Issues](https://github.com/hbliu007/peerlink/issues)
- 功能建议: [GitHub Discussions](https://github.com/hbliu007/peerlink/discussions)
- 邮件: support@peerlink.dev

---

<div align="center">

**[⬆ 回到顶部](#p2p-platform)**

Made with ❤️ by P2P Platform Team

</div>
