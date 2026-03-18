"""
Yamux 流复用协议简单测试

测试基本功能
"""

import asyncio
import logging
import sys

sys.path.insert(0, '.')

from p2p_engine.muxer.yamux import (
    YamuxSession,
    YamuxStream,
    YamuxConfig,
    FrameType,
    FrameFlag,
    GoAwayCode,
)

logger = logging.getLogger("p2p_engine.muxer.test_yamux")


async def test_frame_serialization():
    """测试帧序列化"""
    from p2p_engine.muxer.yamux import YamuxFrame

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

    print("✓ 帧序列化测试通过")


async def test_frame_flags():
    """测试帧标志"""
    from p2p_engine.muxer.yamux import YamuxFrame

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

    print("✓ 帧标志测试通过")


async def test_stream_create():
    """测试流创建"""
    config = YamuxConfig()

    # 创建一个模拟会话
    class MockSession:
        async def _send_frame(self, frame):
            pass

    session = MockSession()

    stream = YamuxStream(
        stream_id=1,
        session=session,
        is_initiator=True,
        config=config
    )

    assert stream.id == 1
    assert not stream.is_closed

    print("✓ 流创建测试通过")


async def main():
    """运行所有测试"""
    logging.basicConfig(level=logging.INFO)

    tests = [
        ("帧序列化", test_frame_serialization),
        ("帧标志", test_frame_flags),
        ("流创建", test_stream_create),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {name}: {e}")
            logger.exception(f"{name} 失败")
            failed += 1

    print(f"\n通过: {passed}, 失败: {failed}")
    return failed == 0


if __name__ == "__main__":
    asyncio.run(main())
