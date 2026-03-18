"""
互操作性测试模块

验证 p2p-platform 与 go-libp2p 和 js-libp2p 的协议兼容性。

测试覆盖:
- TLS 1.3 安全传输
- mplex 流复用
- Kademlia DHT
- GossipSub 发布订阅
- Ping 协议
- QUIC 传输
- WebRTC 传输
- WebTransport 传输

运行方式:
    # 运行所有互操作测试
    pytest tests/interop/ -v

    # 运行特定测试
    pytest tests/interop/test_tls_interop.py -v
    pytest tests/interop/test_mplex_interop.py -v

    # 运行需要外部节点的测试
    pytest tests/interop/ --run-interop-tests -v

注意:
    大部分互操作测试需要运行外部 libp2p 节点。
    参考 README.md 获取设置说明。
"""

__version__ = "1.0.0"
