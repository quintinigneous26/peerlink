# P2P Platform 服务器安装指南

## 概述

P2P Platform 提供完整的 P2P 通信基础设施，包括：
- **STUN Server**: NAT 穿透和网络检测
- **Relay Server (TURN)**: 中继服务器，用于无法直连的场景
- **Signaling Server**: WebRTC 信令服务器
- **DID Service**: 去中心化身份服务

## 系统要求

### 支持的操作系统

**RPM 包 (CentOS/RHEL/Fedora)**:
- CentOS 7+
- RHEL 7+
- Fedora 30+
- Rocky Linux 8+
- AlmaLinux 8+

**DEB 包 (Ubuntu/Debian)**:
- Ubuntu 20.04 LTS+
- Debian 11+

### 支持的架构
- x86_64 (AMD64)
- aarch64 (ARM64)

### 依赖项
- Python 3.11+
- Redis 5.0+
- systemd

## 快速安装

### 方法 1: 使用自动安装脚本（推荐）

```bash
# 下载并解压安装包
tar -xzf p2p-platform-1.0.0.tar.gz
cd p2p-platform-1.0.0

# 运行安装脚本（自动检测系统类型）
sudo ./packaging/scripts/install.sh
```

### 方法 2: 手动安装

#### RPM 包安装 (CentOS/RHEL/Fedora)

```bash
# 1. 构建 RPM 包
cd p2p-platform
./packaging/scripts/build-rpm.sh

# 2. 安装依赖
sudo yum install python3 python3-pip redis

# 3. 安装 P2P Platform
sudo yum install dist/rpm/p2p-platform-1.0.0-1.*.rpm

# 或使用 DNF (Fedora/RHEL 8+)
sudo dnf install dist/rpm/p2p-platform-1.0.0-1.*.rpm
```

#### DEB 包安装 (Ubuntu/Debian)

```bash
# 1. 构建 DEB 包
cd p2p-platform
./packaging/scripts/build-deb.sh

# 2. 安装依赖
sudo apt-get update
sudo apt-get install python3 python3-pip redis-server

# 3. 安装 P2P Platform
sudo dpkg -i dist/deb/p2p-platform_1.0.0_all.deb
sudo apt-get install -f  # 自动安装缺失的依赖
```

## 配置

### 1. 配置文件位置

所有配置文件位于 `/etc/p2p-platform/`:
- `stun-server.conf` - STUN 服务器配置
- `relay-server.conf` - TURN 中继服务器配置
- `signaling-server.conf` - 信令服务器配置
- `did-service.conf` - DID 服务配置

### 2. 必须修改的配置项

**⚠️ 安全警告**: 安装后必须修改以下密钥！

编辑 `/etc/p2p-platform/relay-server.conf`:
```bash
TURN_SECRET=your_secure_random_secret_here
```

编辑 `/etc/p2p-platform/did-service.conf`:
```bash
JWT_SECRET=your_secure_jwt_secret_here
```

生成安全密钥:
```bash
# 生成随机密钥
openssl rand -base64 32
```

### 3. Redis 配置

确保 Redis 服务运行:
```bash
# 启动 Redis
sudo systemctl start redis

# 设置开机自启
sudo systemctl enable redis

# 检查状态
sudo systemctl status redis
```

### 4. 网络端口

确保以下端口开放:
- **3478/UDP**: STUN/TURN 服务
- **5349/TCP**: TURN over TLS
- **8080/TCP**: 信令服务器
- **8081/TCP**: DID 服务

防火墙配置示例:
```bash
# firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=3478/udp
sudo firewall-cmd --permanent --add-port=5349/tcp
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --permanent --add-port=8081/tcp
sudo firewall-cmd --reload

# ufw (Ubuntu/Debian)
sudo ufw allow 3478/udp
sudo ufw allow 5349/tcp
sudo ufw allow 8080/tcp
sudo ufw allow 8081/tcp
```

## 服务管理

### 启动服务

```bash
# 启动所有服务
sudo systemctl start stun-server
sudo systemctl start relay-server
sudo systemctl start signaling-server
sudo systemctl start did-service

# 设置开机自启
sudo systemctl enable stun-server
sudo systemctl enable relay-server
sudo systemctl enable signaling-server
sudo systemctl enable did-service
```

### 查看服务状态

```bash
# 查看单个服务状态
sudo systemctl status stun-server

# 查看所有 P2P 服务状态
sudo systemctl status stun-server relay-server signaling-server did-service
```

### 查看日志

```bash
# 实时查看日志
sudo journalctl -u stun-server -f
sudo journalctl -u relay-server -f
sudo journalctl -u signaling-server -f
sudo journalctl -u did-service -f

# 查看日志文件
tail -f /var/log/p2p-platform/stun-server.log
tail -f /var/log/p2p-platform/relay-server.log
tail -f /var/log/p2p-platform/signaling-server.log
tail -f /var/log/p2p-platform/did-service.log
```

### 停止服务

```bash
# 停止单个服务
sudo systemctl stop stun-server

# 停止所有服务
sudo systemctl stop stun-server relay-server signaling-server did-service
```

### 重启服务

```bash
# 重启单个服务
sudo systemctl restart stun-server

# 重启所有服务
sudo systemctl restart stun-server relay-server signaling-server did-service
```

## 验证安装

### 1. 检查服务状态

```bash
# 所有服务应该显示 "active (running)"
sudo systemctl status stun-server relay-server signaling-server did-service
```

### 2. 测试 STUN 服务器

```bash
# 使用 stunclient 测试 (需要安装 stun-client)
stunclient localhost 3478
```

### 3. 测试信令服务器

```bash
# 测试 HTTP 端点
curl http://localhost:8080/health

# 预期输出: {"status": "ok"}
```

### 4. 测试 DID 服务

```bash
# 测试健康检查端点
curl http://localhost:8081/health

# 预期输出: {"status": "ok"}
```

## 目录结构

```
/opt/p2p-platform/          # 应用程序目录
├── stun-server/            # STUN 服务器
├── relay-server/           # TURN 中继服务器
├── signaling-server/       # 信令服务器
└── did-service/            # DID 服务

/etc/p2p-platform/          # 配置文件目录
├── stun-server.conf
├── relay-server.conf
├── signaling-server.conf
└── did-service.conf

/var/log/p2p-platform/      # 日志目录
├── stun-server.log
├── relay-server.log
├── signaling-server.log
└── did-service.log

/var/lib/p2p-platform/      # 数据目录

/lib/systemd/system/        # systemd 服务文件
├── stun-server.service
├── relay-server.service
├── signaling-server.service
└── did-service.service
```

## 卸载

### RPM 包卸载

```bash
# 停止服务
sudo systemctl stop stun-server relay-server signaling-server did-service

# 卸载包
sudo yum remove p2p-platform
# 或
sudo dnf remove p2p-platform

# 清理数据（可选）
sudo rm -rf /var/log/p2p-platform
sudo rm -rf /var/lib/p2p-platform
sudo rm -rf /etc/p2p-platform
```

### DEB 包卸载

```bash
# 停止服务
sudo systemctl stop stun-server relay-server signaling-server did-service

# 卸载包
sudo apt-get remove p2p-platform

# 完全清理（包括配置文件）
sudo apt-get purge p2p-platform
```

## 故障排查

### 服务无法启动

1. 检查日志:
```bash
sudo journalctl -u <service-name> -n 50
```

2. 检查端口占用:
```bash
sudo netstat -tulpn | grep <port>
```

3. 检查 Redis 连接:
```bash
redis-cli ping
# 应该返回: PONG
```

### Python 依赖问题

手动安装依赖:
```bash
cd /opt/p2p-platform/<service-name>
sudo pip3 install -r requirements.txt
```

### 权限问题

重置权限:
```bash
sudo chown -R p2p:p2p /opt/p2p-platform
sudo chown -R p2p:p2p /var/log/p2p-platform
sudo chown -R p2p:p2p /var/lib/p2p-platform
```

## 性能调优

### 系统限制

编辑 `/etc/security/limits.conf`:
```
p2p soft nofile 65536
p2p hard nofile 65536
p2p soft nproc 4096
p2p hard nproc 4096
```

### Redis 优化

编辑 `/etc/redis/redis.conf`:
```
maxmemory 2gb
maxmemory-policy allkeys-lru
tcp-backlog 511
```

## 支持

- 文档: https://github.com/yourusername/p2p-platform/docs
- 问题反馈: https://github.com/yourusername/p2p-platform/issues
- 邮件: support@p2p-platform.com

## 许可证

MIT License - 详见 LICENSE 文件
