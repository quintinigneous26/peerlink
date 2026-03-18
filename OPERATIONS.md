# 运维手册

本文档提供 P2P Platform 日常运维操作指南。

---

## 📋 目录

- [服务管理](#服务管理)
- [日志管理](#日志管理)
- [监控告警](#监控告警)
- [性能分析](#性能分析)
- [故障排查](#故障排查)
- [备份恢复](#备份恢复)
- [安全维护](#安全维护)
- [容量规划](#容量规划)

---

## 服务管理

### Docker Compose 方式

#### 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 启动特定服务
docker-compose up -d stun-server
docker-compose up -d relay-server
docker-compose up -d signaling-server
docker-compose up -d did-service

# 查看服务状态
docker-compose ps

# 查看服务详情
docker-compose ps -a
```

#### 停止服务

```bash
# 停止所有服务
docker-compose stop

# 停止特定服务
docker-compose stop stun-server

# 停止并删除容器
docker-compose down

# 停止并删除容器、网络、卷
docker-compose down -v
```

#### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启特定服务
docker-compose restart stun-server

# 优雅重启 (等待连接关闭)
docker-compose stop stun-server
sleep 10
docker-compose start stun-server
```

#### 更新服务

```bash
# 拉取最新镜像
docker-compose pull

# 重新构建并启动
docker-compose up -d --build

# 滚动更新 (逐个服务)
docker-compose up -d --no-deps --build stun-server
docker-compose up -d --no-deps --build relay-server
docker-compose up -d --no-deps --build signaling-server
docker-compose up -d --no-deps --build did-service
```

### Systemd 方式

#### 启动服务

```bash
# 启动所有服务
sudo systemctl start p2p-stun
sudo systemctl start p2p-relay
sudo systemctl start p2p-signaling
sudo systemctl start p2p-did

# 设置开机自启
sudo systemctl enable p2p-stun
sudo systemctl enable p2p-relay
sudo systemctl enable p2p-signaling
sudo systemctl enable p2p-did
```

#### 停止服务

```bash
# 停止服务
sudo systemctl stop p2p-stun
sudo systemctl stop p2p-relay
sudo systemctl stop p2p-signaling
sudo systemctl stop p2p-did

# 禁用开机自启
sudo systemctl disable p2p-stun
```

#### 重启服务

```bash
# 重启服务
sudo systemctl restart p2p-stun

# 重新加载配置 (不中断服务)
sudo systemctl reload p2p-stun
```

#### 查看状态

```bash
# 查看服务状态
sudo systemctl status p2p-stun
sudo systemctl status p2p-relay
sudo systemctl status p2p-signaling
sudo systemctl status p2p-did

# 查看所有 P2P 服务
sudo systemctl list-units "p2p-*"

# 查看服务是否启用
sudo systemctl is-enabled p2p-stun
sudo systemctl is-active p2p-stun
```

---

## 日志管理

### 查看日志

#### Docker Compose

```bash
# 查看所有服务日志
docker-compose logs

# 查看特定服务日志
docker-compose logs stun-server
docker-compose logs relay-server
docker-compose logs signaling-server
docker-compose logs did-service

# 实时跟踪日志
docker-compose logs -f

# 查看最近 100 行
docker-compose logs --tail=100

# 查看特定时间范围
docker-compose logs --since="2026-03-15T10:00:00"
docker-compose logs --until="2026-03-15T12:00:00"
```

#### Systemd

```bash
# 查看服务日志
sudo journalctl -u p2p-stun
sudo journalctl -u p2p-relay
sudo journalctl -u p2p-signaling
sudo journalctl -u p2p-did

# 实时跟踪
sudo journalctl -u p2p-stun -f

# 查看最近 100 行
sudo journalctl -u p2p-stun -n 100

# 查看特定时间范围
sudo journalctl -u p2p-stun --since "2026-03-15 10:00:00"
sudo journalctl -u p2p-stun --since "1 hour ago"
sudo journalctl -u p2p-stun --since today
```

#### 文件日志

```bash
# 查看日志文件
tail -f /var/log/p2p/stun.log
tail -f /var/log/p2p/relay.log
tail -f /var/log/p2p/signaling.log
tail -f /var/log/p2p/did.log

# 搜索错误
grep ERROR /var/log/p2p/*.log
grep -i "connection failed" /var/log/p2p/*.log

# 统计错误数量
grep ERROR /var/log/p2p/stun.log | wc -l

# 查看最近的错误
grep ERROR /var/log/p2p/*.log | tail -20
```

### 日志分析

#### 常见日志模式

```bash
# 连接错误
grep "Connection refused" /var/log/p2p/*.log

# 超时错误
grep "timeout" /var/log/p2p/*.log

# 内存问题
grep "Out of memory" /var/log/p2p/*.log

# 认证失败
grep "Authentication failed" /var/log/p2p/*.log

# 高延迟警告
grep "High latency" /var/log/p2p/*.log
```

#### 日志统计

```bash
# 每小时错误数
awk '/ERROR/ {print $1" "$2}' /var/log/p2p/stun.log | cut -d: -f1 | uniq -c

# 最常见的错误
grep ERROR /var/log/p2p/*.log | awk '{print $NF}' | sort | uniq -c | sort -rn | head -10

# 连接统计
grep "New connection" /var/log/p2p/signaling.log | wc -l
grep "Connection closed" /var/log/p2p/signaling.log | wc -l
```

### 日志轮转

```bash
# 手动触发日志轮转
sudo logrotate -f /etc/logrotate.d/p2p-platform

# 测试配置
sudo logrotate -d /etc/logrotate.d/p2p-platform

# 查看轮转状态
sudo cat /var/lib/logrotate/status
```

---

## 监控告警

### 健康检查

#### 服务健康检查

```bash
# STUN 服务
nc -u -v -w 3 localhost 3478 < /dev/null

# Relay 服务
curl -f http://localhost:9001/health || echo "Relay unhealthy"

# 信令服务
curl -f http://localhost:8080/health || echo "Signaling unhealthy"

# DID 服务
curl -f http://localhost:9000/health || echo "DID unhealthy"

# Redis
docker-compose exec redis redis-cli ping || echo "Redis unhealthy"
```

#### 自动健康检查脚本

```bash
#!/bin/bash
# health-check.sh

SERVICES=("stun:3478" "signaling:8080" "did:9000")
FAILED=0

for service in "${SERVICES[@]}"; do
    name="${service%%:*}"
    port="${service##*:}"

    if ! curl -sf http://localhost:$port/health > /dev/null 2>&1; then
        echo "❌ $name service is unhealthy"
        FAILED=$((FAILED + 1))
    else
        echo "✅ $name service is healthy"
    fi
done

if [ $FAILED -gt 0 ]; then
    echo "⚠️  $FAILED service(s) failed health check"
    exit 1
fi

echo "✅ All services are healthy"
exit 0
```

### 性能指标

#### 系统资源

```bash
# CPU 使用率
docker stats --no-stream

# 内存使用
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}"

# 磁盘使用
df -h
du -sh /var/lib/docker/volumes/*

# 网络流量
docker stats --no-stream --format "table {{.Name}}\t{{.NetIO}}"
```

#### 应用指标

```bash
# 活跃连接数
curl http://localhost:9001/metrics | grep p2p_active_connections

# 错误率
curl http://localhost:9001/metrics | grep p2p_error_rate

# 延迟
curl http://localhost:9001/metrics | grep p2p_latency

# 吞吐量
curl http://localhost:9001/metrics | grep p2p_throughput
```

### 告警配置

#### Prometheus 告警规则

```yaml
# /etc/prometheus/rules/p2p-platform.yml
groups:
  - name: p2p_platform
    interval: 30s
    rules:
      # 服务不可用
      - alert: ServiceDown
        expr: up{job="p2p-platform"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.instance }} is down"

      # 高错误率
      - alert: HighErrorRate
        expr: rate(p2p_errors_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on {{ $labels.instance }}"

      # 高延迟
      - alert: HighLatency
        expr: p2p_latency_seconds > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency on {{ $labels.instance }}"

      # 连接数过高
      - alert: TooManyConnections
        expr: p2p_active_connections > 8000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Too many connections on {{ $labels.instance }}"

      # 磁盘空间不足
      - alert: DiskSpaceLow
        expr: node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Disk space low on {{ $labels.instance }}"
```

#### AlertManager 配置

```yaml
# /etc/alertmanager/alertmanager.yml
route:
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'team-email'

receivers:
  - name: 'team-email'
    email_configs:
      - to: 'ops@your-org.com'
        from: 'alertmanager@your-org.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'alertmanager@your-org.com'
        auth_password: 'your-password'
```

---

## 性能分析

### CPU 分析

```bash
# 查看 CPU 使用率
docker stats --no-stream

# 查看进程 CPU 使用
docker-compose exec stun-server top

# 生成 CPU 火焰图
docker-compose exec stun-server py-spy record -o profile.svg -- python main.py
```

### 内存分析

```bash
# 查看内存使用
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"

# 查看内存详情
docker-compose exec stun-server free -h

# 内存泄漏检测
docker-compose exec stun-server python -m memory_profiler main.py
```

### 网络分析

```bash
# 查看网络连接
docker-compose exec stun-server netstat -an | grep ESTABLISHED | wc -l

# 查看端口监听
docker-compose exec stun-server netstat -tlnp

# 抓包分析
sudo tcpdump -i any -w capture.pcap port 3478
wireshark capture.pcap
```

### 数据库分析

```bash
# Redis 性能
docker-compose exec redis redis-cli --latency
docker-compose exec redis redis-cli --stat

# Redis 慢查询
docker-compose exec redis redis-cli slowlog get 10

# Redis 内存分析
docker-compose exec redis redis-cli --bigkeys
```

---

## 故障排查

### 常见问题

#### 1. 服务无法启动

```bash
# 检查端口占用
sudo netstat -tlnp | grep 3478
sudo lsof -i :3478

# 检查配置文件
docker-compose config

# 查看详细错误
docker-compose up stun-server

# 检查依赖服务
docker-compose ps
```

#### 2. 连接失败

```bash
# 检查防火墙
sudo ufw status
sudo iptables -L -n

# 检查网络连通性
ping <server-ip>
telnet <server-ip> 3478

# 检查 DNS 解析
nslookup your-domain.com
dig your-domain.com

# 检查路由
traceroute <server-ip>
```

#### 3. 性能下降

```bash
# 检查系统负载
uptime
top
htop

# 检查磁盘 IO
iostat -x 1
iotop

# 检查网络流量
iftop
nethogs

# 检查连接数
ss -s
netstat -an | grep ESTABLISHED | wc -l
```

#### 4. 内存不足

```bash
# 查看内存使用
free -h
vmstat 1

# 查看进程内存
ps aux --sort=-%mem | head -10

# 清理缓存
sync
echo 3 > /proc/sys/vm/drop_caches

# 重启服务
docker-compose restart
```

#### 5. 磁盘空间不足

```bash
# 查看磁盘使用
df -h
du -sh /var/lib/docker/*

# 清理 Docker
docker system prune -a
docker volume prune

# 清理日志
sudo journalctl --vacuum-time=7d
find /var/log/p2p -name "*.log.*" -mtime +7 -delete
```

### 调试工具

```bash
# 进入容器
docker-compose exec stun-server bash

# 查看进程
docker-compose exec stun-server ps aux

# 查看环境变量
docker-compose exec stun-server env

# 查看网络配置
docker-compose exec stun-server ip addr
docker-compose exec stun-server ip route

# 测试网络连通性
docker-compose exec stun-server ping redis
docker-compose exec stun-server curl http://did-service:9000/health
```

---

## 备份恢复

### 自动备份

#### 备份脚本

```bash
#!/bin/bash
# /usr/local/bin/p2p-backup.sh

set -e

BACKUP_DIR="/backup/p2p-platform"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份配置文件
echo "Backing up configuration..."
tar -czf $BACKUP_DIR/config_$DATE.tar.gz \
    /etc/p2p-platform/ \
    docker-compose.yml \
    .env

# 备份 Redis 数据
echo "Backing up Redis data..."
docker-compose exec -T redis redis-cli BGSAVE
sleep 5
docker cp $(docker-compose ps -q redis):/data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# 备份日志
echo "Backing up logs..."
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz /var/log/p2p/

# 清理旧备份
echo "Cleaning old backups..."
find $BACKUP_DIR -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
find $BACKUP_DIR -name "*.rdb" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_DIR"
```

#### 定时任务

```bash
# 添加到 crontab
crontab -e

# 每天凌晨 2 点备份
0 2 * * * /usr/local/bin/p2p-backup.sh >> /var/log/p2p/backup.log 2>&1
```

### 恢复操作

#### 恢复配置

```bash
# 停止服务
docker-compose down

# 恢复配置文件
tar -xzf /backup/p2p-platform/config_20260315_020000.tar.gz -C /

# 启动服务
docker-compose up -d
```

#### 恢复 Redis

```bash
# 停止 Redis
docker-compose stop redis

# 恢复数据文件
docker cp /backup/p2p-platform/redis_20260315_020000.rdb \
    $(docker-compose ps -q redis):/data/dump.rdb

# 启动 Redis
docker-compose start redis

# 验证
docker-compose exec redis redis-cli DBSIZE
```

---

## 安全维护

### 定期安全检查

```bash
# 检查开放端口
sudo nmap -sT localhost

# 检查 SSL 证书
openssl s_client -connect localhost:8443 -showcerts

# 检查密码强度
docker-compose exec redis redis-cli CONFIG GET requirepass

# 检查文件权限
ls -la /etc/p2p-platform/
ls -la /var/log/p2p/
```

### 更新依赖

```bash
# 更新 Docker 镜像
docker-compose pull

# 更新系统包
sudo apt update && sudo apt upgrade -y

# 更新 Python 依赖
pip list --outdated
pip install --upgrade -r requirements.txt
```

### 安全审计

```bash
# 查看登录历史
last -n 20
lastlog

# 查看失败的登录尝试
sudo grep "Failed password" /var/log/auth.log

# 查看 sudo 使用记录
sudo grep sudo /var/log/auth.log

# 检查异常进程
ps aux | grep -v "^root"
```

---

## 容量规划

### 资源使用趋势

```bash
# CPU 使用趋势
sar -u 1 10

# 内存使用趋势
sar -r 1 10

# 磁盘 IO 趋势
sar -d 1 10

# 网络流量趋势
sar -n DEV 1 10
```

### 扩容建议

#### 垂直扩容 (增加资源)

```yaml
# docker-compose.yml
services:
  stun-server:
    deploy:
      resources:
        limits:
          cpus: '4'      # 从 2 增加到 4
          memory: 4G     # 从 2G 增加到 4G
```

#### 水平扩容 (增加实例)

```bash
# 启动多个实例
docker-compose up -d --scale stun-server=3

# 配置负载均衡
# 参考 DEPLOYMENT.md 中的负载均衡配置
```

### 容量评估

| 指标 | 当前值 | 阈值 | 建议 |
|------|--------|------|------|
| CPU 使用率 | 60% | 80% | 正常 |
| 内存使用率 | 70% | 85% | 关注 |
| 磁盘使用率 | 50% | 90% | 正常 |
| 并发连接数 | 3000 | 8000 | 正常 |
| 网络带宽 | 300 Mbps | 800 Mbps | 正常 |

---

## 运维检查清单

### 每日检查

- [ ] 检查所有服务状态
- [ ] 查看错误日志
- [ ] 检查磁盘空间
- [ ] 查看监控告警
- [ ] 验证备份完成

### 每周检查

- [ ] 分析性能趋势
- [ ] 检查安全日志
- [ ] 更新系统补丁
- [ ] 清理旧日志
- [ ] 测试备份恢复

### 每月检查

- [ ] 容量规划评估
- [ ] 安全审计
- [ ] 更新依赖包
- [ ] 性能优化
- [ ] 文档更新

---

## 紧急联系

### 升级路径

1. **L1 - 运维工程师**: 日常运维、监控告警
2. **L2 - 高级运维**: 复杂故障、性能优化
3. **L3 - 开发团队**: 代码问题、架构调整

### 联系方式

- 运维团队: ops@your-org.com
- 技术支持: support@your-org.com
- 紧急热线: +86-xxx-xxxx-xxxx
- Slack: #p2p-platform-ops

---

## 附录

### 常用命令速查

```bash
# 服务管理
docker-compose up -d              # 启动
docker-compose stop               # 停止
docker-compose restart            # 重启
docker-compose ps                 # 状态

# 日志查看
docker-compose logs -f            # 实时日志
docker-compose logs --tail=100    # 最近100行

# 健康检查
curl http://localhost:8080/health # 信令服务
curl http://localhost:9000/health # DID服务

# 资源监控
docker stats                      # 资源使用
docker-compose exec redis redis-cli INFO # Redis信息

# 备份恢复
/usr/local/bin/p2p-backup.sh     # 手动备份
```

### 故障代码

| 代码 | 说明 | 处理方法 |
|------|------|----------|
| E001 | STUN 服务无响应 | 检查端口、防火墙 |
| E002 | Relay 分配失败 | 检查端口池、资源限制 |
| E003 | 信令连接断开 | 检查 Redis、WebSocket |
| E004 | DID 认证失败 | 检查 JWT 配置、密钥 |
| E005 | Redis 连接失败 | 检查 Redis 服务、密码 |

---

**最后更新**: 2026-03-15
**版本**: 1.0.0
