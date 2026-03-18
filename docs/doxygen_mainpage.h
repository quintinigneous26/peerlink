/**
 * @mainpage P2P Platform 文档
 *
 * @section intro 项目介绍
 *
 * P2P Platform 是一个基于WebRTC技术的去中心化P2P通信平台，提供完整的P2P连接解决方案。
 * 平台包含STUN服务器、TURN中继服务器、信令服务器、DID身份服务和客户端SDK等核心组件。
 *
 * @section features 主要特性
 *
 * - **智能NAT穿透**: 支持多种NAT类型的穿透，包括对称型NAT的端口预测
 * - **运营商差异化**: 针对不同运营商的网络特性进行优化
 * - **自动降级**: 连接失败时自动降级到中继服务
 * - **心跳保活**: 保持连接活跃，防止NAT映射超时
 * - **事件驱动**: 基于事件总线的异步架构
 * - **完整的SDK**: 提供易用的客户端SDK
 *
 * @section architecture 架构设计
 *
 * @subsection core_modules 核心模块
 *
 * - **p2p_engine**: 核心P2P引擎
 *   - engine.py: 主引擎类
 *   - types.py: 核心类型定义
 *   - event.py: 事件系统
 *   - config/: 配置管理
 *   - detection/: 网络检测
 *   - puncher/: NAT穿透
 *   - keeper/: 心跳保活
 *   - fallback/: 降级策略
 *   - protocol/: 协议实现
 *   - transport/: 传输层
 *   - muxer/: 多路复用
 *   - dht/: 分布式哈希表
 *   - security/: 安全模块
 *
 * - **client_sdk**: 客户端SDK
 *   - 简化的API接口
 *   - 事件回调机制
 *   - 连接管理
 *   - 数据传输
 *
 * - **stun-server**: STUN服务器
 *   - NAT类型检测
 *   - 公网地址获取
 *   - RFC 5389标准实现
 *
 * - **relay-server**: TURN中继服务器
 *   - 数据中继转发
 *   - 带宽管理
 *   - 连接管理
 *
 * - **signaling-server**: 信令服务器
 *   - 设备注册
 *   - 连接协调
 *   - 信息交换
 *
 * - **did-service**: DID身份服务
 *   - 设备身份认证
 *   - 密钥管理
 *   - 权限控制
 *
 * @section quick_start 快速开始
 *
 * @subsection installation 安装
 *
 * ```bash
 * # 克隆项目
 * git clone <repo-url>
 * cd p2p-platform
 *
 * # 安装依赖
 * pip install -r requirements.txt
 * ```
 *
 * @subsection basic_usage 基本使用
 *
 * ```python
 * from p2p_engine import P2PEngine, P2PConfig
 *
 * # 创建引擎
 * config = P2PConfig(
 *     stun_servers=["stun.l.google.com:19302"],
 *     debug=True
 * )
 * engine = P2PEngine(config)
 *
 * # 初始化
 * await engine.initialize()
 *
 * # 连接到对端
 * result = await engine.connect_to_peer(peer_id, peer_info)
 * if result.success:
 *     print(f"连接成功: {result.connection_type}")
 * ```
 *
 * @section api_reference API参考
 *
 * @subsection types 核心类型
 *
 * - @ref p2p_engine.types.ConnectionState "连接状态"
 * - @ref p2p_engine.types.ConnectionType "连接类型"
 * - @ref p2p_engine.types.NATType "NAT类型"
 * - @ref p2p_engine.types.NATInfo "NAT信息"
 * - @ref p2p_engine.types.NetworkEnvironment "网络环境"
 * - @ref p2p_engine.types.ConnectionResult "连接结果"
 * - @ref p2p_engine.types.PeerInfo "对端信息"
 * - @ref p2p_engine.types.ISP "ISP运营商"
 * - @ref p2p_engine.types.Region "地理区域"
 *
 * @subsection engine 引擎类
 *
 * - @ref p2p_engine.engine.P2PEngine "P2P引擎主类"
 * - @ref p2p_engine.engine.P2PConfig "引擎配置"
 * - @ref p2p_engine.engine.P2PState "引擎状态"
 *
 * @subsection events 事件系统
 *
 * - @ref p2p_engine.event.EventBus "事件总线"
 * - @ref p2p_engine.event.EventTopic "事件主题"
 * - @ref p2p_engine.event.P2PEventType "事件类型"
 *
 * @section examples 使用示例
 *
 * @subsection example_basic 基本连接示例
 *
 * ```python
 * import asyncio
 * from p2p_engine import P2PEngine, P2PConfig, PeerInfo
 *
 * async def main():
 *     # 创建引擎
 *     engine = P2PEngine()
 *     await engine.initialize()
 *
 *     # 创建对端信息
 *     peer_info = PeerInfo(
 *         peer_id="peer-123",
 *         public_ip="203.0.113.1",
 *         public_port=5000
 *     )
 *
 *     # 连接
 *     result = await engine.connect_to_peer("peer-123", peer_info)
 *
 *     if result.success:
 *         print(f"连接成功!")
 *         print(f"连接类型: {result.connection_type}")
 *         print(f"延迟: {result.latency_ms}ms")
 *     else:
 *         print(f"连接失败: {result.error}")
 *
 * asyncio.run(main())
 * ```
 *
 * @subsection example_events 事件处理示例
 *
 * ```python
 * from p2p_engine.event import EventBus, EventTopic, P2PEventType
 *
 * async def on_peer_connected(event):
 *     print(f"对端已连接: {event.data['peer_id']}")
 *
 * async def on_error(event):
 *     print(f"错误: {event.data['error']}")
 *
 * bus = EventBus()
 * bus.subscribe(EventTopic.CONNECTION, on_peer_connected)
 * bus.subscribe(EventTopic.ERROR, on_error)
 * ```
 *
 * @section deployment 部署指南
 *
 * @subsection docker_deployment Docker部署
 *
 * ```bash
 * # 使用docker-compose启动所有服务
 * docker-compose up -d
 *
 * # 查看日志
 * docker-compose logs -f
 *
 * # 停止服务
 * docker-compose down
 * ```
 *
 * @subsection configuration 配置说明
 *
 * 详见 `docs/` 目录下的配置文档。
 *
 * @section troubleshooting 故障排除
 *
 * @subsection nat_issues NAT穿透问题
 *
 * 如果NAT穿透失败，请检查：
 * - STUN服务器是否可达
 * - 防火墙是否阻止了UDP/TCP连接
 * - 对端是否在线
 * - 网络延迟是否过高
 *
 * @subsection connection_issues 连接问题
 *
 * 如果连接建立失败，请检查：
 * - 信令服务器是否正常运行
 * - 对端信息是否正确
 * - 网络环境是否支持P2P连接
 *
 * @section performance 性能优化
 *
 * - 使用UDP而不是TCP以降低延迟
 * - 启用多路复用以提高吞吐量
 * - 配置合适的心跳间隔
 * - 使用DHT加速对端发现
 *
 * @section security 安全性
 *
 * - 所有连接都支持DTLS加密
 * - 支持SRTP保护媒体流
 * - DID服务提供身份认证
 * - 支持权限控制和访问列表
 *
 * @section contributing 贡献指南
 *
 * 欢迎提交Issue和Pull Request！
 *
 * @section license 许可证
 *
 * MIT License
 *
 * @section contact 联系方式
 *
 * 如有问题，请通过以下方式联系：
 * - GitHub Issues
 * - 项目文档
 * - 开发者邮箱
 */
