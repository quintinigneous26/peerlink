# 部署指南

本文档提供 P2P Platform 在生产环境中的完整部署指南。

---

## 📋 目录

- [系统要求](#系统要求)
- [部署架构](#部署架构)
- [部署步骤](#部署步骤)
- [配置说明](#配置说明)
- [性能调优](#性能调优)
- [监控和日志](#监控和日志)
- [安全加固](#安全加固)
- [高可用部署](#高可用部署)

---

## 系统要求

### 硬件要求

#### 最小配置 (测试环境)
- CPU: 2 核
- 内存: 4 GB
- 磁盘: 20 GB
- 网络: 10 Mbps

#### 推荐配置 (生产环境)
- CPU: 8 核
- 内存: 16 GB
- 磁盘: 100 GB SSD
- 网络: 1 Gbps

#### 高负载配置 (大规模部署)
- CPU: 16+ 核
- 内存: 32+ GB
- 磁盘: 500 GB SSD
- 网络: 10 Gbps

### 软件要求

- **操作系统**:
  - Ubuntu 20.04/22.04 LTS
  - CentOS 7/8
  - RHEL 8+
  - Debian 11+
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Python**: 3.11+ (源码部署)
- **Redis**: 7.0+ (可选，用于集群部署)

### 网络要求

#### 端口开放

| 服务 | 端口 | 协议 | 说明 |
|------|------|------|------|
| STUN | 3478 | UDP | NAT 穿透 |
| STUN | 3479 | TCP | NAT 穿透 (备用) |
| Relay | 50000-50010 | UDP/TCP | 中继端口池 |
| Signaling | 8080 | TCP | WebSocket (HTTP) |
| Signaling | 8443 | TCP | WebSocket (HTTPS) |
| DID | 9000 | TCP | HTTP API |
| Redis | 6379 | TCP | 缓存 (内部) |

#### 防火墙配置

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 3478/udp
sudo ufw allow 3479/tcp
sudo ufw allow 50000:50010/udp
sudo ufw allow 50000:50010/tcp
sudo ufw allow 8080/tcp
sudo ufw allow 8443/tcp
sudo ufw allow 9000/tcp

# CentOS/RHEL (firewalld)
sudo firewall-cmd --permanent --add-port=3478/udp
sudo firewall-cmd --permanent --add-port=3479/tcp
sudo firewall-cmd --permanent --add-port=50000-50010/udp
sudo firewall-cmd --permanent --add-port=50000-50010/tcp
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --permanent --add-port=8443/tcp
sudo firewall-cmd --permanent --add-port=9000/tcp
sudo firewall-cmd --reload
```

---

## 部署架构

### 单机部署

```
┌─────────────────────────────────────────┐
│           Single Server                  │
│                                          │
│  ┌──────────┐  ┌──────────┐            │
│  │   STUN   │  │  Relay   │            │
│  └──────────┘  └──────────┘            │
│                                          │
│  ┌──────────┐  ┌──────────┐            │
│  │Signaling │  │   DID    │            │
│  └──────────┘  └──────────┘            │
│                                          │
│  ┌──────────────────────┐               │
│  │       Redis          │               │
│  └──────────────────────┘               │
└─────────────────────────────────────────┘
```

### 分布式部署

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Server 1  │     │   Server 2  │     │   Server 3  │
│             │     │             │     │             │
│  ┌────────┐ │     │  ┌────────┐ │     │  ┌────────┐ │
│  │  STUN  │ │     │  │  STUN  │ │     │  │  STUN  │ │
│  └────────┘ │     │  └────────┘ │     │  └────────┘ │
│             │     │             │     │             │
│  ┌────────┐ │     │  ┌────────┐ │     │  ┌────────┐ │
│  │ Relay  │ │     │  │ Relay  │ │     │  │ Relay  │ │
│  └────────┘ │     │  └────────┘ │     │  └────────┘ │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
              ┌────────────▼────────────┐
              │      Load Balancer      │
              └────────────┬────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
│ Signaling 1 │     │ Signaling 2 │     │ Signaling 3 │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
              ┌────────────▼────────────┐
              │    Redis Cluster        │
              └─────────────────────────┘
```

---

## 部署步骤

### 方式 1: Docker Compose 部署 (推荐)

#### 1. 准备环境

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证安装
docker --version
docker-compose --version
```

#### 2. 下载项目

```bash
git clone https://github.com/your-org/p2p-platform.git
cd p2p-platform
```

#### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置
vim .env
```

`.env` 文件示例：

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
REDIS_URL=redis://redis:6379

# DID 服务
DID_SERVICE_PORT=9000
JWT_SECRET=CHANGE_THIS_TO_A_RANDOM_SECRET_KEY
JWT_EXPIRATION=3600

# Redis
REDIS_PASSWORD=CHANGE_THIS_TO_A_STRONG_PASSWORD
```

#### 4. 启动服务

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

#### 5. 验证部署

```bash
# 检查 STUN 服务
nc -u -v localhost 3478

# 检查信令服务
curl http://localhost:8080/health

# 检查 DID 服务
curl http://localhost:9000/health

# 检查 Redis
docker-compose exec redis redis-cli ping
```

### 方式 2: RPM/DEB 包部署

#### RPM 包 (CentOS/RHEL/Fedora)

```bash
# 下载包
wget https://github.com/your-org/p2p-platform/releases/download/v1.0.0/p2p-platform-1.0.0.rpm

# 安装
sudo rpm -ivh p2p-platform-1.0.0.rpm

# 配置
sudo vim /etc/p2p-platform/config.yml

# 启动服务
sudo systemctl start p2p-stun
sudo systemctl start p2p-relay
sudo systemctl start p2p-signaling
sudo systemctl start p2p-did

# 设置开机自启
sudo systemctl enable p2p-stun p2p-relay p2p-signaling p2p-did

# 查看状态
sudo systemctl status p2p-stun
sudo systemctl status p2p-relay
sudo systemctl status p2p-signaling
sudo systemctl status p2p-did
```

#### DEB 包 (Ubuntu/Debian)

```bash
# 下载包
wget https://github.com/your-org/p2p-platform/releases/download/v1.0.0/p2p-platform_1.0.0_amd64.deb

# 安装
sudo dpkg -i p2p-platform_1.0.0_amd64.deb
sudo apt-get install -f

# 配置和启动 (同 RPM)
```

### 方式 3: 源码部署

```bash
# 克隆项目
git clone https://github.com/your-org/p2p-platform.git
cd p2p-platform

# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置
cp config.example.yml config.yml
vim config.yml

# 启动服务 (使用 systemd 或 supervisor)
# 参考 scripts/ 目录下的服务脚本
```

---

## 配置说明

### STUN 服务器配置

```yaml
# stun-server/config.yml
server:
  host: 0.0.0.0
  port: 3478
  tcp_port: 3479

logging:
  level: INFO
  file: /var/log/p2p/stun.log

performance:
  max_connections: 10000
  buffer_size: 65536
```

### Relay 服务器配置

```yaml
# relay-server/config.yml
server:
  host: 0.0.0.0
  min_port: 50000
  max_port: 50010

allocation:
  max_allocations: 1000
  lifetime: 600
  max_bandwidth: 10485760  # 10 MB/s

logging:
  level: INFO
  file: /var/log/p2p/relay.log
```

### 信令服务器配置

```yaml
# signaling-server/config.yml
server:
  ws_port: 8080
  wss_port: 8443
  ssl_cert: /etc/ssl/certs/server.crt
  ssl_key: /etc/ssl/private/server.key

redis:
  url: redis://localhost:6379
  password: your-redis-password
  db: 0

did_service:
  url: http://localhost:9000

logging:
  level: INFO
  file: /var/log/p2p/signaling.log
```

### DID 服务配置

```yaml
# did-service/config.yml
server:
  host: 0.0.0.0
  port: 9000

jwt:
  secret: your-jwt-secret-key
  expiration: 3600
  algorithm: HS256

redis:
  url: redis://localhost:6379
  password: your-redis-password

logging:
  level: INFO
  file: /var/log/p2p/did.log
```

---

## 性能调优

### 系统级优化

```bash
# 增加文件描述符限制
sudo vim /etc/security/limits.conf
```

添加：
```
* soft nofile 65536
* hard nofile 65536
```

```bash
# 优化网络参数
sudo vim /etc/sysctl.conf
```

添加：
```
# 增加 TCP 缓冲区
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864

# 增加连接队列
net.core.somaxconn = 4096
net.ipv4.tcp_max_syn_backlog = 8192

# 启用 TCP Fast Open
net.ipv4.tcp_fastopen = 3

# UDP 缓冲区
net.core.rmem_default = 262144
net.core.wmem_default = 262144
```

应用配置：
```bash
sudo sysctl -p
```

### Docker 优化

```yaml
# docker-compose.yml
services:
  stun-server:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
```

### 应用级优化

#### STUN 服务器

```python
# stun-server/config.py
MAX_CONNECTIONS = 10000
BUFFER_SIZE = 65536
WORKER_THREADS = 4
```

#### Relay 服务器

```python
# relay-server/config.py
MAX_ALLOCATIONS = 1000
ALLOCATION_LIFETIME = 600
MAX_BANDWIDTH_PER_ALLOCATION = 10 * 1024 * 1024  # 10 MB/s
CLEANUP_INTERVAL = 60
```

#### 信令服务器

```python
# signaling-server/config.py
MAX_CONNECTIONS = 5000
HEARTBEAT_INTERVAL = 30
CONNECTION_TIMEOUT = 300
REDIS_POOL_SIZE = 50
```

---

## 监控和日志

### 日志配置

#### 日志目录结构

```
/var/log/p2p/
├── stun.log
├── relay.log
├── signaling.log
├── did.log
└── access.log
```

#### 日志轮转

```bash
# /etc/logrotate.d/p2p-platform
/var/log/p2p/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 p2p p2p
    sharedscripts
    postrotate
        systemctl reload p2p-* > /dev/null 2>&1 || true
    endscript
}
```

### 监控指标

#### Prometheus 配置

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'p2p-platform'
    static_configs:
      - targets:
          - 'localhost:9001'  # STUN metrics
          - 'localhost:9002'  # Relay metrics
          - 'localhost:9003'  # Signaling metrics
          - 'localhost:9004'  # DID metrics
```

#### 关键指标

| 指标 | 说明 | 告警阈值 |
|------|------|----------|
| `p2p_active_connections` | 活跃连接数 | > 8000 |
| `p2p_connection_errors` | 连接错误数 | > 100/min |
| `p2p_relay_bandwidth` | 中继带宽使用 | > 80% |
| `p2p_stun_latency` | STUN 响应延迟 | > 100ms |
| `p2p_signaling_queue` | 信令队列长度 | > 1000 |

### Grafana 仪表板

导入预配置的仪表板：

```bash
# 下载仪表板配置
wget https://github.com/your-org/p2p-platform/releases/download/v1.0.0/grafana-dashboard.json

# 导入到 Grafana
# Dashboard -> Import -> Upload JSON file
```

---

## 安全加固

### SSL/TLS 配置

```bash
# 生成自签名证书 (测试用)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/server.key \
  -out /etc/ssl/certs/server.crt

# 生产环境使用 Let's Encrypt
sudo apt-get install certbot
sudo certbot certonly --standalone -d your-domain.com
```

### JWT 密钥生成

```bash
# 生成强随机密钥
openssl rand -base64 64
```

### Redis 安全

```bash
# redis.conf
requirepass your-strong-password
bind 127.0.0.1
protected-mode yes
```

### 防火墙规则

```bash
# 只允许特定 IP 访问管理端口
sudo ufw allow from 192.168.1.0/24 to any port 6379
sudo ufw allow from 192.168.1.0/24 to any port 9001
```

---

## 高可用部署

### 负载均衡

#### Nginx 配置

```nginx
# /etc/nginx/conf.d/p2p-platform.conf
upstream signaling_backend {
    least_conn;
    server 192.168.1.10:8080;
    server 192.168.1.11:8080;
    server 192.168.1.12:8080;
}

server {
    listen 80;
    server_name signaling.your-domain.com;

    location / {
        proxy_pass http://signaling_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Redis 集群

```bash
# 启动 Redis 集群
docker-compose -f docker-compose.redis-cluster.yml up -d

# 创建集群
docker exec -it redis-1 redis-cli --cluster create \
  192.168.1.10:6379 \
  192.168.1.11:6379 \
  192.168.1.12:6379 \
  --cluster-replicas 1
```

### 健康检查

```yaml
# docker-compose.yml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

---

## 故障排查

### 常见问题

#### 1. STUN 服务无响应

```bash
# 检查端口监听
sudo netstat -ulnp | grep 3478

# 检查防火墙
sudo ufw status

# 查看日志
docker-compose logs stun-server
```

#### 2. Relay 连接失败

```bash
# 检查端口范围
sudo netstat -ulnp | grep 50000

# 检查资源限制
ulimit -n

# 查看分配情况
curl http://localhost:9001/metrics | grep relay_allocations
```

#### 3. 信令服务器连接断开

```bash
# 检查 Redis 连接
docker-compose exec redis redis-cli ping

# 检查 WebSocket 连接
wscat -c ws://localhost:8080

# 查看连接数
docker-compose exec signaling-server ps aux
```

---

## 备份和恢复

### 备份脚本

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/p2p-platform"
DATE=$(date +%Y%m%d_%H%M%S)

# 备份配置
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /etc/p2p-platform/

# 备份 Redis 数据
docker-compose exec redis redis-cli BGSAVE
cp /var/lib/docker/volumes/p2p-platform_redis-data/_data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# 备份日志
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz /var/log/p2p/

# 清理旧备份 (保留 30 天)
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.rdb" -mtime +30 -delete
```

### 恢复

```bash
# 恢复配置
tar -xzf config_20260315_120000.tar.gz -C /

# 恢复 Redis
docker-compose stop redis
cp redis_20260315_120000.rdb /var/lib/docker/volumes/p2p-platform_redis-data/_data/dump.rdb
docker-compose start redis
```

---

## 升级指南

### 滚动升级

```bash
# 1. 备份当前版本
./backup.sh

# 2. 拉取新版本
git pull origin main

# 3. 逐个升级服务
docker-compose up -d --no-deps --build stun-server
sleep 30
docker-compose up -d --no-deps --build relay-server
sleep 30
docker-compose up -d --no-deps --build signaling-server
sleep 30
docker-compose up -d --no-deps --build did-service

# 4. 验证
docker-compose ps
docker-compose logs -f
```

---

## 联系支持

如有部署问题，请联系：

- 技术支持: support@your-org.com
- GitHub Issues: https://github.com/your-org/p2p-platform/issues
- 文档: https://docs.your-org.com
