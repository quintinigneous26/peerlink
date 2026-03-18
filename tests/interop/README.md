# 互操作性测试

验证 p2p-platform 与 go-libp2p 和 js-libp2p 的协议兼容性。

## 测试覆盖

### 协议测试
- TLS 1.3 (`/tls/1.0.0`) - 安全传输握手
- mplex (`/mplex/6.7.0`) - 流复用协议
- Kademlia DHT (`/ipfs/kad/1.0.0`) - 分布式哈希表
- GossipSub (`/meshsub/1.1.0`) - 发布订阅
- Ping (`/ipfs/ping/1.0.0`) - 连接检测

### 传输测试
- QUIC (`/quic-v1`) - UDP 传输
- WebRTC (`/webrtc-direct`) - 浏览器 P2P
- WebTransport (`/webtransport/1.0.0`) - 现代浏览器传输

## 环境设置

### go-libp2p 测试节点

```bash
# 安装 Go
# 克隆测试节点
cd tests/interop/go-test-node
go mod download
go run main.go
```

### js-libp2p 测试节点

```bash
# 安装 Node.js
cd tests/interop/js-test-node
npm install
npm start
```

### Docker 测试环境

```bash
# 构建测试镜像
docker-compose build

# 启动测试节点
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## 运行测试

```bash
# 运行所有互操作测试
pytest tests/interop/ -v

# 运行特定协议测试
pytest tests/interop/test_tls_interop.py -v
pytest tests/interop/test_mplex_interop.py -v

# 运行需要外部节点的测试
pytest tests/interop/ --run-interop-tests -v

# 跳过需要外部节点的测试
pytest tests/interop/ -v
```

## 测试结果

测试通过率将输出到终端，详细报告保存在 `tests/interop/results/`。

## 故障排除

1. 确保测试节点正在运行
2. 检查防火墙设置
3. 验证端口未被占用
4. 查看测试节点日志
