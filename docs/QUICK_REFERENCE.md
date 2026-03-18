# P2P Platform 文档快速参考

## 文档位置

- **HTML文档**: `/Users/liuhongbo/work/p2p-platform/docs/doxygen/html/index.html`
- **配置文件**: `/Users/liuhongbo/work/p2p-platform/Doxyfile`
- **生成报告**: `/Users/liuhongbo/work/p2p-platform/docs/DOXYGEN_REPORT.md`

## 快速访问

### 本地浏览
```bash
# 直接打开HTML文件
open /Users/liuhongbo/work/p2p-platform/docs/doxygen/html/index.html

# 或使用Web服务器
cd /Users/liuhongbo/work/p2p-platform/docs/doxygen/html
python -m http.server 8000
# 访问 http://localhost:8000
```

## 核心API速查

### 连接状态
```python
from p2p_engine.types import ConnectionState

# 可用状态
ConnectionState.IDLE              # 空闲
ConnectionState.DETECTING         # 检测中
ConnectionState.SIGNALING         # 信令中
ConnectionState.PUNCHING          # 打洞中
ConnectionState.CONNECTING        # 连接中
ConnectionState.CONNECTED         # 已连接
ConnectionState.RELAY             # 中继模式
ConnectionState.RECONNECTING      # 重连中
ConnectionState.DISCONNECTED      # 已断开
ConnectionState.FAILED            # 失败
```

### NAT类型
```python
from p2p_engine.types import NATType

NATType.FULL_CONE          # 完全圆锥型
NATType.RESTRICTED_CONE    # 受限圆锥型
NATType.PORT_RESTRICTED    # 端口受限型
NATType.SYMMETRIC          # 对称型
NATType.UNKNOWN            # 未知
```

### 连接类型
```python
from p2p_engine.types import ConnectionType

ConnectionType.P2P_UDP      # 直连UDP（最优）
ConnectionType.P2P_TCP      # 直连TCP
ConnectionType.RELAY_UDP    # 中继UDP
ConnectionType.RELAY_TCP    # 中继TCP
ConnectionType.FAILED       # 失败
```

### 事件主题
```python
from p2p_engine.event import EventTopic

EventTopic.CONNECTION      # 连接事件
EventTopic.STREAM          # 流事件
EventTopic.PROTOCOL        # 协议事件
EventTopic.NETWORK         # 网络事件
EventTopic.RELAY           # 中继事件
EventTopic.NAT             # NAT事件
EventTopic.ERROR           # 错误事件
EventTopic.METRIC          # 指标事件
EventTopic.CUSTOM          # 自定义事件
```

## 常用代码片段

### 初始化引擎
```python
from p2p_engine import P2PEngine, P2PConfig

config = P2PConfig(
    stun_servers=["stun.l.google.com:19302"],
    stun_timeout_ms=3000,
    debug=True,
    log_level="INFO"
)

engine = P2PEngine(config)
await engine.initialize()
```

### 连接到对端
```python
from p2p_engine.types import PeerInfo

peer_info = PeerInfo(
    peer_id="peer-123",
    public_ip="203.0.113.1",
    public_port=5000
)

result = await engine.connect_to_peer("peer-123", peer_info)

if result.success:
    print(f"连接成功: {result.connection_type}")
    print(f"延迟: {result.latency_ms}ms")
else:
    print(f"连接失败: {result.error}")
```

### 订阅事件
```python
from p2p_engine.event import EventBus, EventTopic

bus = EventBus()

async def on_peer_connected(event):
    print(f"对端已连接: {event.data['peer_id']}")

async def on_error(event):
    print(f"错误: {event.data['error']}")

bus.subscribe(EventTopic.CONNECTION, on_peer_connected)
bus.subscribe(EventTopic.ERROR, on_error)
```

## 文档结构

```
docs/doxygen/html/
├── index.html              # 主页
├── classes.html            # 类列表
├── files.html              # 文件列表
├── namespaces.html         # 命名空间
├── annotated.html          # 类详情
├── functions.html          # 函数列表
├── globals.html            # 全局符号
├── search/                 # 搜索功能
└── [module]/               # 各模块文档
    ├── index.html
    ├── class_*.html
    └── ...
```

## 主要模块

| 模块 | 说明 | 关键类 |
|------|------|--------|
| p2p_engine | 核心引擎 | P2PEngine, P2PConfig |
| types | 类型定义 | ConnectionState, NATType, NATInfo |
| event | 事件系统 | EventBus, EventTopic |
| detection | 网络检测 | ISPDetector, NATDetector |
| puncher | NAT穿透 | UDPPuncher, PunchResult |
| keeper | 心跳保活 | HeartbeatKeeper |
| fallback | 降级策略 | FallbackDecider |
| protocol | 协议实现 | 各协议类 |
| transport | 传输层 | 传输实现 |
| muxer | 多路复用 | 多路复用实现 |
| dht | DHT | DHT实现 |
| security | 安全 | 安全模块 |

## 常见问题

### Q: 如何更新文档？
A: 修改代码后运行：
```bash
cd /Users/liuhongbo/work/p2p-platform
doxygen Doxyfile
```

### Q: 如何添加新的文档？
A: 在代码中添加docstring，格式如下：
```python
class MyClass:
    """
    简短描述

    详细描述...

    属性:
        attr1: 说明
    """
```

### Q: 文档支持哪些语言？
A: 当前配置为中文，可在Doxyfile中修改OUTPUT_LANGUAGE。

### Q: 如何生成PDF文档？
A: 使用LaTeX输出：
```bash
cd /Users/liuhongbo/work/p2p-platform/docs/doxygen/latex
make
```

## 相关资源

- **项目README**: `/Users/liuhongbo/work/p2p-platform/README.md`
- **Doxygen官网**: https://www.doxygen.nl/
- **Python文档规范**: PEP 257

## 支持

如有问题，请：
1. 查看文档中的故障排除部分
2. 检查代码注释和示例
3. 查看相关模块的API参考
