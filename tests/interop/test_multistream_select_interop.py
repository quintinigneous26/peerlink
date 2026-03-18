"""
multistream-select 互操作性测试

验证与 go-libp2p 和 js-libp2p 的协议兼容性

测试覆盖:
- varint 编码格式一致性
- 协议协商流程
- 同时打开场景
- "na" 响应处理
- 错误恢复
"""

import pytest
import asyncio
from typing import Optional

from p2p_engine.protocol import (
    ProtocolNegotiator,
    StreamReaderWriter,
    encode_varint,
    decode_varint,
    encode_message,
    decode_message,
    MULTISTREAM_PROTOCOL_ID,
    NA_RESPONSE,
)


# ==================== Go-libp2p 互操作测试 ====================

class TestGoLibp2pInterop:
    """与 go-libp2p 的互操作性测试"""

    @pytest.mark.asyncio
    async def test_go_libp2p_varint_encoding(self):
        """
        验证 varint 编码与 go-libp2p 一致性

        go-libp2p 使用 github.com/multiformats/go-varint
        """
        # 测试用例来自 go-libp2p 规范
        test_cases = [
            (0, b'\x00'),
            (1, b'\x01'),
            (127, b'\x7f'),
            (128, b'\x80\x01'),
            (300, b'\xac\x02'),
            (16384, b'\x80\x80\x01'),
        ]

        for value, expected in test_cases:
            encoded = encode_varint(value)
            assert encoded == expected, f"varint({value}) 编码不一致"
            decoded, consumed = decode_varint(encoded)
            assert decoded == value, f"varint 解码不一致"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 go-libp2p 节点运行")
    async def test_go_libp2p_multistream_handshake(self):
        """
        验证与 go-libp2p 的 multistream-select 握手

        go-libp2p 实现参考:
        https://github.com/multiformats/go-multistream

        运行方式: pytest --run-interop-tests
        """
        # 需要从配置获取主机和端口
        # 这里使用默认值
        host = "127.0.0.1"
        port = 12345

        reader, writer = await asyncio.open_connection(host, port)
        conn = StreamReaderWriter(reader, writer)

        negotiator = ProtocolNegotiator(timeout=10.0)

        try:
            # go-libp2y 支持的协议列表
            protocols = [
                "/noise",
                "/tls/1.0.0",
                "/yamux/1.0.0",
                "/mplex/1.0.0",
            ]

            negotiated = await negotiator.negotiate(conn, protocols)

            # 验证协商结果
            assert negotiated in protocols, f"未知协议: {negotiated}"

        finally:
            writer.close()
            await writer.wait_closed()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 go-libp2p 节点运行")
    async def test_go_libp2p_na_response(self):
        """
        验证 "na" 响应处理与 go-libp2p 一致

        当 go-libp2p 不支持某个协议时，应返回 "na"

        运行方式: pytest --run-interop-tests
        """
        host = "127.0.0.1"
        port = 12345

        reader, writer = await asyncio.open_connection(host, port)
        conn = StreamReaderWriter(reader, writer)

        negotiator = ProtocolNegotiator(timeout=10.0)

        try:
            # 提议一个不存在的协议
            unsupported_protocol = "/unsupported/protocol/1.0.0"

            with pytest.raises(Exception):  # 应该收到 "na" 或协商失败
                await negotiator.negotiate(conn, [unsupported_protocol])

        finally:
            writer.close()
            await writer.wait_closed()


# ==================== JS-libp2p 互操作测试 ====================

class TestJSLibp2pInterop:
    """与 js-libp2p 的互操作性测试"""

    @pytest.mark.asyncio
    async def test_js_libp2p_varint_encoding(self):
        """
        验证 varint 编码与 js-libp2p 一致性

        js-libp2p 使用 uint8-array-to-varint
        """
        # js-libp2p 的 varint 实现应该与 go-libp2p 兼容
        # 测试用例相同
        test_cases = [
            (0, b'\x00'),
            (1, b'\x01'),
            (127, b'\x7f'),
            (128, b'\x80\x01'),
            (300, b'\xac\x02'),
        ]

        for value, expected in test_cases:
            encoded = encode_varint(value)
            assert encoded == expected

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 js-libp2p 节点运行")
    async def test_js_libp2p_simultaneous_open(self):
        """
        验证同时打开场景与 js-libp2p 兼容

        js-libp2p 在浏览器中经常遇到同时打开场景

        运行方式: pytest --run-interop-tests
        """
        host = "127.0.0.1"
        port = 12346

        reader, writer = await asyncio.open_connection(host, port)
        conn = StreamReaderWriter(reader, writer)

        negotiator = ProtocolNegotiator(timeout=10.0)

        try:
            # 使用 full_negotiate 处理同时打开
            protocols = ["/yamux/1.0.0", "/mplex/1.0.0"]
            negotiated = await negotiator.full_negotiate(conn, protocols)

            assert negotiated in protocols

        finally:
            writer.close()
            await writer.wait_closed()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要 WebSocket 客户端实现")
    async def test_js_libp2p_websocket_transport(self):
        """
        验证通过 WebSocket 传输的协议协商

        js-libp2p 常用 WebSocket 作为传输层
        """
        # 这里需要 WebSocket 客户端
        # 可以使用 websockets 库
        pass


# ==================== 协议兼容性测试 ====================

class TestProtocolCompatibility:
    """协议兼容性验证测试"""

    def test_multistream_protocol_id_format(self):
        """
        验证 multistream 协议 ID 格式

        协议规范: https://github.com/multiformats/multistream-select
        """
        assert MULTISTREAM_PROTOCOL_ID == "/multistream/1.0.0"

    def test_na_response_format(self):
        """验证 "na" 响应格式"""
        assert NA_RESPONSE == "na"

    def test_message_encoding_compliance(self):
        """
        验证消息编码符合规范

        格式: varint(长度) + UTF-8字符串 + \n
        """
        # 测试 "na" 消息
        encoded_na = encode_message(NA_RESPONSE)
        assert encoded_na == b'\x03na\n'

        # 验证可以解码
        decoded = decode_message(encoded_na)
        assert decoded == NA_RESPONSE

    def test_varint_compliance(self):
        """
        验证 varint 编码符合 multiformats 规范

        规范: https://github.com/multiformats/unsigned-varint
        """
        # 边界测试
        assert encode_varint(0) == b'\x00'
        assert encode_varint(127) == b'\x7f'  # 单字节最大值
        assert encode_varint(128) == b'\x80\x01'  # 需要两字节

        # 测试解码
        assert decode_varint(b'\x7f')[0] == 127
        assert decode_varint(b'\x80\x01')[0] == 128


# ==================== 错误恢复测试 ====================

class TestErrorRecovery:
    """错误恢复和边界条件测试"""

    @pytest.mark.asyncio
    async def test_invalid_varint_recovery(self):
        """测试无效 varint 的恢复"""
        with pytest.raises(ValueError):
            decode_varint(b'\x80\x80\x80')  # 不完整的 varint

    @pytest.mark.asyncio
    async def test_invalid_message_recovery(self):
        """测试无效消息的恢复"""
        # 长度不匹配
        with pytest.raises(ValueError):
            decode_message(b'\x05abc')  # 声明 5 字节，实际只有 4

    @pytest.mark.asyncio
    async def test_timeout_recovery(self):
        """测试超时恢复"""
        negotiator = ProtocolNegotiator(timeout=0.01)  # 10ms 超时

        # 使用一个不会响应的 mock 连接
        class NoResponseReader:
            async def read(self, n=-1):
                await asyncio.sleep(1)  # 永远阻塞
                return b''

        class NoResponseWriter:
            def write(self, data):
                pass

            async def drain(self):
                pass

            def close(self):
                pass

            def is_closing(self):
                return False

        conn = StreamReaderWriter(NoResponseReader(), NoResponseWriter())

        with pytest.raises(Exception):  # 应该超时
            await negotiator.negotiate(conn, ["/yamux/1.0.0"])


# ==================== 性能基准 =================---

class TestPerformanceBenchmarks:
    """性能基准测试"""

    @pytest.mark.asyncio
    async def test_varint_encoding_performance(self):
        """varint 编码性能基准"""
        import time

        iterations = 10000
        start = time.perf_counter()

        for _ in range(iterations):
            encode_varint(300)

        elapsed = time.perf_counter() - start
        ops_per_second = iterations / elapsed

        # 应该能轻松达到 > 100万次/秒
        assert ops_per_second > 100_000, f"varint 编码性能: {ops_per_second:.0f} ops/s"

    @pytest.mark.asyncio
    async def test_varint_decoding_performance(self):
        """varint 解码性能基准"""
        import time

        data = encode_varint(300)
        iterations = 10000
        start = time.perf_counter()

        for _ in range(iterations):
            decode_varint(data)

        elapsed = time.perf_counter() - start
        ops_per_second = iterations / elapsed

        assert ops_per_second > 100_000, f"varint 解码性能: {ops_per_second:.0f} ops/s"
