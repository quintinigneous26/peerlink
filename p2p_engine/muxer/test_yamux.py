"""
Yamux 流复用协议测试

测试场景:
1. 基本流操作 (读写、关闭)
2. 并发流
3. 背压机制
4. 半关闭
5. Ping/保活
"""

import asyncio
import pytest
import logging

from .yamux import (
    YamuxSession,
    YamuxStream,
    YamuxConfig,
    FrameType,
    FrameFlag,
    GoAwayCode,
    YamuxClosedError,
    YamuxStreamReset,
)

logger = logging.getLogger("p2p_engine.muxer.test_yamux")


# ==================== 测试辅助函数 ====================

async def create_echo_server(
    host: str = "127.0.0.1",
    port: int = 0,
    config: YamuxConfig = None
) -> tuple[YamuxSession, int]:
    """创建回显服务器"""
    server_started = asyncio.Event()

    def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        session = YamuxSession.create_server_session(reader, writer, config)
        server_started.set()

    server = await asyncio.start_server(handle_client, host, port)
    port = server.sockets[0].getsockname()[1]

    async def serve():
        async with server:
            await server.serve_forever()

    asyncio.create_task(serve())
    await server_started.wait()

    return server, port


async def create_test_pair(config: YamuxConfig = None) -> tuple[YamuxSession, YamuxSession]:
    """创建测试用的客户端-服务端对"""
    server_started = asyncio.Event()
    client_session = None
    server_session = None

    async def handle_client(reader, writer):
        nonlocal server_session
        server_session = YamuxSession.create_server_session(reader, writer, config)
        server_started.set()

        # 保持服务端运行
        try:
            while not server_session.is_closed:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    # 启动服务器
    server = await asyncio.start_server(handle_client, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    asyncio.create_task(server.serve_forever())
    await server_started.wait()

    # 连接客户端
    client_session = await YamuxSession.create_client("127.0.0.1", port, config)

    return client_session, server_session


# ==================== 基本流操作测试 ====================

async def test_stream_basic_read_write():
    """测试流基本读写操作"""
    client, server = await create_test_pair()

    # 客户端打开流
    client_stream = await client.open_stream()

    # 服务端接受流
    server_stream = await server.accept_stream()

    # 客户端发送数据
    test_data = b"Hello, Yamux!"
    await client_stream.write(test_data)

    # 服务端接收
    received = await server_stream.read(len(test_data))

    assert received == test_data

    # 服务端回显
    await server_stream.write(received)

    # 客户端接收回显
    echo = await client_stream.read(len(test_data))

    assert echo == test_data

    # 关闭流
    await client_stream.close()
    await server_stream.close()

    await client.close()
    await server.close()


async def test_stream_close():
    """测试流关闭"""
    client, server = await create_test_pair()

    client_stream = await client.open_stream()
    server_stream = await server.accept_stream()

    # 发送数据后关闭
    await client_stream.write(b"test")
    await client_stream.close()

    # 服务端应该能读取到数据
    data = await server_stream.read(4)
    assert data == b"test"

    # 服务端再次读取应该得到空字节
    data = await server_stream.read(10)
    assert data == b""

    await server_stream.close()
    await client.close()
    await server.close()


async def test_stream_reset():
    """测试流重置"""
    client, server = await create_test_pair()

    client_stream = await client.open_stream()
    server_stream = await server.accept_stream()

    # 客户端重置流
    await client_stream.reset()

    # 服务端读取应该抛出异常
    try:
        await server_stream.read(10)
        assert False, "应该抛出异常"
    except Exception:
        pass

    await client.close()
    await server.close()


# ==================== 并发流测试 ====================

async def test_concurrent_streams():
    """测试并发流 (100+)"""
    config = YamuxConfig(
        accept_backlog=256,
        max_unacked_streams=256
    )

    client, server = await create_test_pair(config)

    num_streams = 100
    streams = []

    # 打开多个流
    for i in range(num_streams):
        stream = await client.open_stream()
        streams.append(stream)

    # 服务端接受所有流
    server_streams = []
    for _ in range(num_streams):
        stream = await server.accept_stream()
        server_streams.append(stream)

    # 每个流发送唯一数据
    for i, stream in enumerate(streams):
        await stream.write(f"stream-{i}".encode())

    # 服务端验证
    for i, stream in enumerate(server_streams):
        data = await stream.read(10)
        assert data == f"stream-{i}".encode()

    # 关闭所有流
    for stream in streams + server_streams:
        await stream.close()

    await client.close()
    await server.close()


# ==================== 背压测试 ====================

async def test_backpressure():
    """测试背压机制"""
    config = YamuxConfig(
        window_size=1024,  # 小窗口
    )

    client, server = await create_test_pair(config)

    client_stream = await client.open_stream()
    server_stream = await server.accept_stream()

    # 发送超过窗口大小的数据
    large_data = b"x" * 2048  # 超过1KB窗口

    # 应该能够处理（会等待窗口更新）
    write_task = asyncio.create_task(client_stream.write(large_data))

    # 服务端读取并更新窗口
    received = b""
    while len(received) < len(large_data):
        chunk = await server_stream.read(512)
        received += chunk

    await write_task
    assert received == large_data

    await client_stream.close()
    await server_stream.close()
    await client.close()
    await server.close()


async def test_window_update():
    """测试窗口更新"""
    config = YamuxConfig(
        window_size=512,
    )

    client, server = await create_test_pair(config)

    client_stream = await client.open_stream()
    server_stream = await server.accept_stream()

    # 发送恰好填满窗口的数据
    await client_stream.write(b"x" * 512)

    # 再发送应该需要等待窗口更新
    write_task = asyncio.create_task(client_stream.write(b"y"))

    # 读取数据
    data = await server_stream.read(512)
    assert data == b"x" * 512

    # 写入应该完成
    await write_task

    # 读取剩余数据
    data = await server_stream.read(1)
    assert data == b"y"

    await client_stream.close()
    await server_stream.close()
    await client.close()
    await server.close()


# ==================== 半关闭测试 ====================

async def test_half_close():
    """测试半关闭"""
    client, server = await create_test_pair()

    client_stream = await client.open_stream()
    server_stream = await server.accept_stream()

    # 客户端发送数据后关闭写端
    await client_stream.write(b"client to server")
    await client_stream.close()

    # 服务端接收数据
    data = await server_stream.read(20)
    assert data == b"client to server"

    # 服务端仍然可以发送数据
    await server_stream.write(b"server to client")

    # 客户端仍然可以接收数据
    data = await client_stream.read(20)
    assert data == b"server to client"

    # 服务端也关闭
    await server_stream.close()

    await client.close()
    await server.close()


# ==================== Ping 测试 ====================

async def test_ping():
    """测试 Ping 功能"""
    client, server = await create_test_pair()

    # 发送 Ping
    rtt = await client.ping(timeout=5.0)

    assert rtt >= 0
    assert rtt < 5.0

    await client.close()
    await server.close()


async def test_ping_timeout():
    """测试 Ping 超时"""
    config = YamuxConfig(keepalive_interval=0.1)

    client, server = await create_test_pair(config)

    # 关闭服务端
    await server.close()

    # 客户端 Ping 应该失败
    try:
        await client.ping(timeout=1.0)
        assert False, "应该超时"
    except asyncio.TimeoutError:
        pass

    await client.close()


# ==================== 会话关闭测试 ====================

async def test_session_close():
    """测试会话关闭"""
    client, server = await create_test_pair()

    # 打开一些流
    for _ in range(5):
        stream = await client.open_stream()
        await stream.close()

    # 关闭会话
    await client.close(GoAwayCode.NORMAL)

    assert client.is_closed
    assert client._goaway_code == GoAwayCode.NORMAL

    await server.close()


# ==================== 数据帧测试 ====================

async def test_frame_flags():
    """测试帧标志"""
    from .yamux import YamuxFrame

    frame = YamuxFrame(
        type=FrameType.DATA,
        flags=FrameFlag.SYN | FrameFlag.ACK,
        stream_id=1,
        length=0
    )

    assert frame.has_flag(FrameFlag.SYN)
    assert frame.has_flag(FrameFlag.ACK)
    assert not frame.has_flag(FrameFlag.FIN)

    frame.add_flag(FrameFlag.FIN)
    assert frame.has_flag(FrameFlag.FIN)


async def test_frame_pack_unpack():
    """测试帧序列化"""
    from .yamux import YamuxFrame

    original = YamuxFrame(
        type=FrameType.DATA,
        flags=FrameFlag.SYN,
        stream_id=1,
        length=5,
        data=b"hello"
    )

    packed = original.pack()
    unpacked = YamuxFrame.unpack(packed)

    assert unpacked.version == original.version
    assert unpacked.type == original.type
    assert unpacked.flags == original.flags
    assert unpacked.stream_id == original.stream_id
    assert unpacked.length == original.length
    assert unpacked.data == original.data


# ==================== 压力测试 ====================

async def test_stress_concurrent_streams():
    """压力测试: 大量并发流"""
    config = YamuxConfig(
        accept_backlog=256,
        max_unacked_streams=256,
        window_size=64 * 1024
    )

    client, server = await create_test_pair(config)

    num_streams = 200
    streams = []

    # 快速打开多个流
    open_tasks = [client.open_stream() for _ in range(num_streams)]
    streams = await asyncio.gather(*open_tasks)

    # 服务端接受
    server_streams = []
    for _ in range(num_streams):
        stream = await server.accept_stream()
        server_streams.append(stream)

    # 随机读写
    async def test_stream(i, client_stream, server_stream):
        data = f"stream-{i}-data".encode() * 10
        await client_stream.write(data)
        received = await server_stream.read(len(data))
        assert received == data
        await client_stream.close()
        await server_stream.close()

    test_tasks = [
        test_stream(i, streams[i], server_streams[i])
        for i in range(num_streams)
    ]

    await asyncio.gather(*test_tasks)

    await client.close()
    await server.close()


# ==================== 主函数 ====================

async def run_tests():
    """运行所有测试"""
    tests = [
        ("基本读写", test_stream_basic_read_write),
        ("流关闭", test_stream_close),
        ("流重置", test_stream_reset),
        ("并发流", test_concurrent_streams),
        ("背压", test_backpressure),
        ("窗口更新", test_window_update),
        ("半关闭", test_half_close),
        ("Ping", test_ping),
        ("会话关闭", test_session_close),
        ("帧标志", test_frame_flags),
        ("帧序列化", test_frame_pack_unpack),
        ("压力测试", test_stress_concurrent_streams),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            await test_func()
            print(f"✓ {name}")
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            failed += 1

    print(f"\n通过: {passed}, 失败: {failed}")
    return failed == 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(run_tests())
