# P2P Platform 服务器架构说明

**生成时间**: 2026-03-15 23:35

---

## 📊 服务器组成

P2P Platform 服务器由 **4 个独立部件** 构成：

### 1️⃣ STUN 服务器
**目录**: `stun-server/`
**功能**: NAT 类型检测、公网 IP 发现
**端口**: 3478 (UDP)
**语言**: Python 3.11+

```
stun-server/
├── src/
│   ├── __init__.py
│   ├── server.py           # STUN 服务器主逻辑
│   ├── messages.py         # STUN 消息处理
│   └── nat_detection.py    # NAT 检测逻辑
├── tests/
├── Dockerfile
└── requirements.txt
```

### 2️⃣ 信令服务器 (Signaling Server)
**目录**: `signaling-server/`
**功能**: WebSocket 信令交换、对端发现
**端口**: 8080 (WebSocket)
**语言**: Python 3.11+ (FastAPI)

```
signaling-server/
├── src/
│   ├── __init__.py
│   ├── main.py             # 服务器入口
│   └── signaling_server/
│       ├── config.py       # 配置管理
│       ├── service.py      # FastAPI 服务
│       ├── connection.py   # 连接管理
│       └── messages.py     # 消息处理
├── Dockerfile
└── requirements.txt
```

### 3️⃣ 中继服务器 (Relay Server / TURN)
**目录**: `relay-server/`
**功能**: UDP/TCP 中继、带宽管理、端口分配
**端口**: 3479 (UDP/TCP)
**语言**: Python 3.11+

```
relay-server/
├── src/
│   ├── __init__.py
│   ├── main.py             # 服务器入口
│   ├── relay.py            # 中继核心逻辑
│   ├── allocation.py       # 端口分配管理
│   ├── bandwidth.py        # 带宽控制
│   └── messages.py         # TURN 消息处理
├── tests/
├── Dockerfile
└── requirements.txt
```

### 4️⃣ DID 服务 (DID Service)
**目录**: `did-service/`
**功能**: 去中心化身份管理
**端口**: 8081 (HTTP)
**语言**: Python 3.11+

```
did-service/
├── src/
│   ├── __init__.py
│   ├── main.py             # 服务器入口
│   └── did_service/
│       ├── identity.py     # 身份管理
│       ├── resolver.py     # DID 解析
│       └── storage.py      # 存储层
└── requirements.txt
```

---

## 💻 编程语言

### ❌ 没有 C++ 代码

**所有服务器组件都是 Python 实现**：
- 语言: Python 3.11+
- 框架: FastAPI, uvicorn, asyncio
- 无 C++ 代码
- 无需编译

### 为什么选择 Python？

1. **快速开发**: 服务器逻辑简单，Python 开发效率高
2. **易于部署**: 无需编译，跨平台兼容性好
3. **丰富生态**: 网络库、异步框架成熟
4. **易于维护**: 代码可读性强，便于运维

### C++ 在哪里？

**核心引擎 (p2p_engine) 是 Python 实现**，但可以通过 Cython 或 PyO3 编译为 C 扩展以提升性能（可选）。

---

## 📦 安装包格式

### ✅ 支持两种格式

#### 1. RPM 包 (Red Hat 系)

**适用系统**:
- CentOS 7+
- RHEL 7+
- Fedora 30+
- Rocky Linux 8+
- AlmaLinux 8+

**包文件**: `p2p-platform-1.0.0-1.noarch.rpm`

**构建命令**:
```bash
./packaging/scripts/build-rpm.sh
```

**安装命令**:
```bash
# YUM (CentOS 7/RHEL 7)
sudo yum install dist/rpm/p2p-platform-1.0.0-1.*.rpm

# DNF (Fedora/RHEL 8+)
sudo dnf install dist/rpm/p2p-platform-1.0.0-1.*.rpm
```

**SPEC 文件**: `packaging/rpm/p2p-platform.spec`

#### 2. DEB 包 (Debian 系)

**适用系统**:
- Ubuntu 20.04 LTS+
- Debian 11+

**包文件**: `p2p-platform_1.0.0_all.deb`

**构建命令**:
```bash
./packaging/scripts/build-deb.sh
```

**安装命令**:
```bash
sudo dpkg -i dist/deb/p2p-platform_1.0.0_all.deb
sudo apt-get install -f  # 自动安装依赖
```

**控制文件**: `packaging/deb/debian/control`

---

## 🏗️ 打包结构

### 目录结构

```
packaging/
├── rpm/
│   └── p2p-platform.spec      # RPM 规格文件
├── deb/
│   └── debian/                # DEB 控制文件
│       ├── control
│       ├── rules
│       ├── changelog
│       └── ...
├── systemd/                   # systemd 服务文件
│   ├── stun-server.service
│   ├── relay-server.service
│   ├── signaling-server.service
│   └── did-service.service
├── config/                    # 配置文件模板
│   ├── stun-server.conf
│   ├── relay-server.conf
│   ├── signaling-server.conf
│   └── did-service.conf
├── scripts/                   # 构建脚本
│   ├── build-rpm.sh          # 构建 RPM
│   ├── build-deb.sh          # 构建 DEB
│   └── install.sh            # 自动安装脚本
└── INSTALL.md                # 安装文档
```

### 安装后的文件布局

```
/opt/p2p-platform/            # 程序目录
├── stun-server/
├── relay-server/
├── signaling-server/
└── did-service/

/etc/p2p-platform/            # 配置目录
├── stun-server.conf
├── relay-server.conf
├── signaling-server.conf
└── did-service.conf

/var/log/p2p-platform/        # 日志目录
/var/lib/p2p-platform/        # 数据目录

/usr/lib/systemd/system/      # systemd 服务
├── stun-server.service
├── relay-server.service
├── signaling-server.service
└── did-service.service
```

---

## 🚀 部署方式

### 方式 1: RPM/DEB 包安装（推荐）

**优点**:
- ✅ 自动安装依赖
- ✅ systemd 服务集成
- ✅ 自动创建用户和目录
- ✅ 配置文件管理
- ✅ 卸载干净

**步骤**:
```bash
# 1. 构建包
./packaging/scripts/build-rpm.sh  # 或 build-deb.sh

# 2. 安装
sudo yum install dist/rpm/p2p-platform-*.rpm

# 3. 启动服务
sudo systemctl start stun-server
sudo systemctl start relay-server
sudo systemctl start signaling-server
sudo systemctl start did-service

# 4. 设置开机自启
sudo systemctl enable stun-server relay-server signaling-server did-service
```

### 方式 2: Docker 容器部署

**优点**:
- ✅ 环境隔离
- ✅ 快速部署
- ✅ 易于扩展

**步骤**:
```bash
# 1. 构建镜像
docker build -t p2p-stun-server stun-server/
docker build -t p2p-relay-server relay-server/
docker build -t p2p-signaling-server signaling-server/
docker build -t p2p-did-service did-service/

# 2. 启动容器
docker-compose up -d
```

### 方式 3: 源码安装

**优点**:
- ✅ 灵活定制
- ✅ 开发调试方便

**步骤**:
```bash
# 1. 安装依赖
cd stun-server && pip3 install -r requirements.txt
cd relay-server && pip3 install -r requirements.txt
cd signaling-server && pip3 install -r requirements.txt
cd did-service && pip3 install -r requirements.txt

# 2. 启动服务
python3 stun-server/src/server.py
python3 relay-server/src/main.py
python3 signaling-server/src/main.py
python3 did-service/src/main.py
```

---

## 🔧 systemd 服务管理

### 服务控制

```bash
# 启动服务
sudo systemctl start stun-server
sudo systemctl start relay-server
sudo systemctl start signaling-server
sudo systemctl start did-service

# 停止服务
sudo systemctl stop stun-server

# 重启服务
sudo systemctl restart relay-server

# 查看状态
sudo systemctl status signaling-server

# 查看日志
sudo journalctl -u did-service -f
```

### 开机自启

```bash
# 启用开机自启
sudo systemctl enable stun-server relay-server signaling-server did-service

# 禁用开机自启
sudo systemctl disable stun-server
```

---

## 📊 架构对比

### P2P Platform vs go-libp2p

| 特性 | P2P Platform | go-libp2p |
|------|--------------|-----------|
| 服务器语言 | Python | Go |
| 客户端语言 | Python | Go/JS/Rust |
| 服务器数量 | 4 个独立服务 | 集成在客户端 |
| 部署方式 | RPM/DEB/Docker | 嵌入应用 |
| 架构 | 客户端-服务器 | 纯 P2P |

### 为什么需要服务器？

1. **STUN 服务器**: NAT 穿透必需
2. **信令服务器**: 对端发现和信令交换
3. **中继服务器**: 无法直连时的备用方案
4. **DID 服务**: 去中心化身份管理

---

## 🎯 总结

### 服务器组成
- **4 个独立部件**: STUN、信令、中继、DID
- **全部 Python 实现**: 无 C++ 代码
- **无需编译**: 直接运行

### 安装包格式
- **RPM 包**: CentOS/RHEL/Fedora
- **DEB 包**: Ubuntu/Debian
- **Docker 镜像**: 跨平台

### 部署方式
- **推荐**: RPM/DEB 包 + systemd
- **备选**: Docker 容器
- **开发**: 源码直接运行

### 构建命令
```bash
# RPM 包
./packaging/scripts/build-rpm.sh

# DEB 包
./packaging/scripts/build-deb.sh

# Docker 镜像
docker build -t p2p-stun-server stun-server/
```

---

**文档生成**: Claude Opus 4.6
**生成时间**: 2026-03-15 23:35
