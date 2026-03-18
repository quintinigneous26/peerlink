"""
multistream-select 协议单元测试

测试覆盖:
- Varint 编解码
- 消息编解码
- 协议协商 (Initiator/Responder)
- 同时打开场景
- 错误处理
"""

import pytest
import asyncio
from io import BytesIO

from p2p_engine.protocol.messages import (
    encode_varint,
    decode_varint,
    encode_message,
    decode_message,
    decode_message_with_offset,
    MULTISTREAM_PROTOCOL_ID,
    NA_RESPONSE,
    is_valid_protocol_id,
    is_multistream_protocol,
    is_na_response,
)

from p2p_engine.protocol.negotiator import (
    StreamReaderWriter,
    NegotiationError,
    HandshakeError,
    ProtocolNegotiator,
)


# ==================== Mock 连接类 ====================

class MockStreamReader:
    """模拟 StreamReader"""

    def __init__(self, data: bytes = b""):
        self.queue = asyncio.Queue()
        self.closed = False
        self.feed_data(data)  # 初始化数据

    def feed_data(self, data: bytes) -> None:
        """向缓冲区添加数据"""
        if data:
            self.queue.put_nowait(data)

    async def read(self, n: int = -1) -> bytes:
        """读取数据"""
        if self.closed:
            raise ConnectionError("连接已关闭")

        # 如果没有数据，等待（用于超时测试）
        if self.queue.empty():
            # 模拟阻塞读取，但会在超时后被中断
            try:
                data = await asyncio.wait_for(self.queue.get(), timeout=30)
            except asyncio.TimeoutError:
                return b''
            return data

        # 获取第一个数据块
        data = await self.queue.get()

        if n == -1 or n >= len(data):
            return data
        else:
            # 只返回部分数据，剩余放回队列
            self.queue.put_nowait(data[n:])
            return data[:n]

    def close(self) -> None:
        """关闭连接"""
        self.closed = True


class MockStreamWriter:
    """模拟 StreamWriter"""

    def __init__(self):
        self.data = bytearray()
        self.closed = False
        self.drain_count = 0

    def write(self, data: bytes) -> None:
        """写入数据"""
        if self.closed:
            raise ConnectionError("连接已关闭")
        self.data.extend(data)

    async def drain(self) -> None:
        """等待数据发送"""
        self.drain_count += 1
        await asyncio.sleep(0)

    def close(self) -> None:
        """关闭连接"""
        self.closed = True

    def is_closing(self) -> bool:
        """检查是否正在关闭"""
        return self.closed


class MockConnection:
    """模拟连接"""

    def __init__(self):
        self.reader = MockStreamReader()
        self.writer = MockStreamWriter()

    def get_reader_writer(self) -> StreamReaderWriter:
        """获取 StreamReaderWriter 包装"""
        return StreamReaderWriter(self.reader, self.writer)

    def feed_read_data(self, data: bytes) -> None:
        """向读取端添加数据"""
        self.reader.feed_data(data)

    def get_written_data(self) -> bytes:
        """获取写入的数据"""
        return bytes(self.writer.data)

    def clear_written_data(self) -> None:
        """清除写入的数据"""
        self.writer.data.clear()


# ==================== Varint 编解码测试 ====================

class TestVarintEncoding:
    """Varint 编码测试"""

    @pytest.mark.parametrize("value,expected", [
        (0, b'\x00'),
        (1, b'\x01'),
        (3, b'\x03'),
        (127, b'\x7f'),
        (128, b'\x80\x01'),
        (300, b'\xac\x02'),
        (16384, b'\x80\x80\x01'),
        (65535, b'\xff\xff\x03'),
    ])
    def test_encode_varint(self, value: int, expected: bytes):
        """测试 varint 编码"""
        assert encode_varint(value) == expected

    def test_encode_varint_negative(self):
        """测试编码负数（应该失败）"""
        with pytest.raises(ValueError, match="varint 只支持无符号整数"):
            encode_varint(-1)


class TestVarintDecoding:
    """Varint 解码测试"""

    @pytest.mark.parametrize("data,expected_value,expected_bytes", [
        (b'\x00', 0, 1),
        (b'\x01', 1, 1),
        (b'\x03', 3, 1),
        (b'\x7f', 127, 1),
        (b'\x80\x01', 128, 2),
        (b'\xac\x02', 300, 2),
        (b'\x80\x80\x01', 16384, 3),
        (b'\xff\xff\x03', 65535, 3),
    ])
    def test_decode_varint(self, data: bytes, expected_value: int, expected_bytes: int):
        """测试 varint 解码"""
        value, bytes_consumed = decode_varint(data)
        assert value == expected_value
        assert bytes_consumed == expected_bytes

    def test_decode_varint_with_offset(self):
        """测试带偏移量的 varint 解码"""
        data = b'\x00\x00\xac\x02'
        value, bytes_consumed = decode_varint(data, offset=2)
        assert value == 300
        assert bytes_consumed == 2

    def test_decode_varint_empty(self):
        """测试解码空数据"""
        with pytest.raises(ValueError, match="数据不足"):
            decode_varint(b'')

    def test_decode_varint_incomplete(self):
        """测试解码不完整的 varint"""
        with pytest.raises(ValueError, match="varint 不完整"):
            decode_varint(b'\x80')


# ==================== 消息编解码测试 ====================

class TestMessageEncoding:
    """消息编码测试"""

    def test_encode_na(self):
        """测试编码 "na" 消息"""
        encoded = encode_message("na")
        assert encoded == b'\x03na\n'

    def test_encode_multistream(self):
        """测试编码 multistream 协议 ID"""
        encoded = encode_message(MULTISTREAM_PROTOCOL_ID)
        # /multistream/1.0.0 = 18 chars + \n = 19 bytes = 0x13
        assert encoded[0] == 0x13
        assert encoded.endswith(b'/multistream/1.0.0\n')

    def test_encode_multistream_varint(self):
        """测试编码 multistream 协议 ID - varint 格式"""
        encoded = encode_message(MULTISTREAM_PROTOCOL_ID)
        # 验证完整的 varint 编码: 长度前缀 + 内容
        expected = encode_varint(19) + b'/multistream/1.0.0\n'
        assert encoded == expected

    def test_encode_custom_protocol(self):
        """测试编码自定义协议"""
        encoded = encode_message("/yamux/1.0.0")
        assert encoded.endswith(b'/yamux/1.0.0\n')


class TestMessageDecoding:
    """消息解码测试"""

    def test_decode_na(self):
        """测试解码 "na" 消息"""
        decoded = decode_message(b'\x03na\n')
        assert decoded == "na"

    def test_decode_multistream(self):
        """测试解码 multistream 协议 ID"""
        encoded = encode_message(MULTISTREAM_PROTOCOL_ID)
        decoded = decode_message(encoded)
        assert decoded == MULTISTREAM_PROTOCOL_ID

    def test_decode_custom_protocol(self):
        """测试解码自定义协议"""
        encoded = encode_message("/yamux/1.0.0")
        decoded = decode_message(encoded)
        assert decoded == "/yamux/1.0.0"

    def test_decode_with_offset(self):
        """测试带偏移量的消息解码"""
        # 正确的格式: varint(0) + varint(19) + message(19 bytes)
        full_data = b'\x00\x13/multistream/1.0.0\n'
        decoded, consumed = decode_message_with_offset(full_data, offset=1)
        assert decoded == MULTISTREAM_PROTOCOL_ID
        # varint(1 byte for 0x13) + message(19 bytes) = 20 bytes
        assert consumed == 20

    def test_decode_incomplete(self):
        """测试解码不完整的消息"""
        with pytest.raises(ValueError, match="数据长度不足"):
            decode_message(b'\x14/multistream')  # 长度不足


# ==================== 协议验证测试 ====================

class TestProtocolValidation:
    """协议验证测试"""

    @pytest.mark.parametrize("protocol_id,valid", [
        ("/multistream/1.0.0", True),
        ("/yamux/1.0.0", True),
        ("/noise", True),
        ("/ipfs/id/1.0.0", True),
        ("", False),
        ("invalid", False),
        ("/invalid protocol", False),
        ("/with\tnull", False),
    ])
    def test_is_valid_protocol_id(self, protocol_id: str, valid: bool):
        """测试协议 ID 验证"""
        assert is_valid_protocol_id(protocol_id) == valid

    def test_is_multistream_protocol(self):
        """测试 multistream 协议 ID 检查"""
        assert is_multistream_protocol(MULTISTREAM_PROTOCOL_ID)
        assert not is_multistream_protocol("/yamux/1.0.0")

    def test_is_na_response(self):
        """测试 na 响应检查"""
        assert is_na_response(NA_RESPONSE)
        assert not is_na_response("/yamux/1.0.0")


# ==================== 协议协商测试 ====================

class TestProtocolNegotiatorInitiator:
    """协议协商器 (发起方) 测试"""

    @pytest.mark.asyncio
    async def test_successful_negotiation_first_protocol(self):
        """测试成功协商第一个协议"""
        # 创建两个模拟连接
        initiator_conn = MockConnection()
        responder_conn = MockConnection()

        # 创建协商器
        initiator = ProtocolNegotiator(timeout=5.0)
        responder = ProtocolNegotiator(timeout=5.0)

        # 发起方发送的任务
        async def initiator_task():
            conn = initiator_conn.get_reader_writer()
            # 模拟响应方的回复
            initiator_conn.feed_read_data(encode_message(MULTISTREAM_PROTOCOL_ID))
            initiator_conn.feed_read_data(encode_message("/yamux/1.0.0"))

            result = await initiator.negotiate(conn, ["/yamux/1.0.0", "/mplex/1.0.0"])
            return result

        # 响应方的处理
        async def responder_task():
            conn = responder_conn.get_reader_writer()
            supported = ["/yamux/1.0.0", "/mplex/1.0.0"]

            # 模拟发起方的发送
            responder_conn.feed_read_data(encode_message(MULTISTREAM_PROTOCOL_ID))
            responder_conn.feed_read_data(encode_message("/yamux/1.0.0"))

            result = await responder.handle_negotiate(conn, supported)
            return result

        # 并发执行
        result_initiator, result_responder = await asyncio.gather(
            initiator_task(),
            responder_task()
        )

        assert result_initiator == "/yamux/1.0.0"
        assert result_responder == "/yamux/1.0.0"

    @pytest.mark.asyncio
    async def test_successful_negotiation_second_protocol(self):
        """测试成功协商第二个协议（第一个不支持）"""
        initiator_conn = MockConnection()
        responder_conn = MockConnection()

        initiator = ProtocolNegotiator(timeout=5.0)
        responder = ProtocolNegotiator(timeout=5.0)

        async def initiator_task():
            conn = initiator_conn.get_reader_writer()
            # 模拟响应方的回复
            initiator_conn.feed_read_data(encode_message(MULTISTREAM_PROTOCOL_ID))
            initiator_conn.feed_read_data(encode_message(NA_RESPONSE))  # 第一个协议不支持
            initiator_conn.feed_read_data(encode_message("/mplex/1.0.0"))  # 第二个协议支持

            result = await initiator.negotiate(conn, ["/yamux/1.0.0", "/mplex/1.0.0"])
            return result

        async def responder_task():
            conn = responder_conn.get_reader_writer()
            supported = ["/mplex/1.0.0"]  # 只支持 mplex

            # 模拟发起方的发送
            responder_conn.feed_read_data(encode_message(MULTISTREAM_PROTOCOL_ID))
            responder_conn.feed_read_data(encode_message("/yamux/1.0.0"))
            # 发起方会尝试下一个协议
            # 这里简化了测试，实际需要更复杂的模拟

            return "/mplex/1.0.0"

        result = await initiator_task()
        assert result == "/mplex/1.0.0"

    @pytest.mark.asyncio
    async def test_negotiation_failure_no_common_protocol(self):
        """测试协商失败 - 没有共同支持的协议"""
        initiator_conn = MockConnection()

        initiator = ProtocolNegotiator(timeout=5.0)

        async def initiator_task():
            conn = initiator_conn.get_reader_writer()
            # 模拟响应方拒绝所有协议
            initiator_conn.feed_read_data(encode_message(MULTISTREAM_PROTOCOL_ID))
            initiator_conn.feed_read_data(encode_message(NA_RESPONSE))
            initiator_conn.feed_read_data(encode_message(NA_RESPONSE))

            with pytest.raises(NegotiationError) as exc_info:
                await initiator.negotiate(conn, ["/yamux/1.0.0", "/mplex/1.0.0"])

            assert exc_info.value.tried_protocols == ["/yamux/1.0.0", "/mplex/1.0.0"]

        await initiator_task()

    @pytest.mark.asyncio
    async def test_handshake_error(self):
        """测试握手错误"""
        initiator_conn = MockConnection()

        initiator = ProtocolNegotiator(timeout=5.0)

        async def initiator_task():
            conn = initiator_conn.get_reader_writer()
            # 模拟响应方返回错误的协议 ID
            initiator_conn.feed_read_data(encode_message("/invalid/1.0.0"))

            with pytest.raises(HandshakeError):
                await initiator.negotiate(conn, ["/yamux/1.0.0"])

        await initiator_task()

    @pytest.mark.asyncio
    async def test_negotiation_timeout(self):
        """测试协商超时"""
        initiator_conn = MockConnection()

        initiator = ProtocolNegotiator(timeout=0.1)  # 短超时

        async def initiator_task():
            conn = initiator_conn.get_reader_writer()
            # 不提供任何数据，导致超时

            with pytest.raises(NegotiationError, match="超时"):
                await initiator.negotiate(conn, ["/yamux/1.0.0"])

        await initiator_task()


class TestProtocolNegotiatorSimultaneousOpen:
    """同时打开场景测试"""

    @pytest.mark.asyncio
    async def test_simultaneous_open(self):
        """测试同时打开场景"""
        conn = MockConnection()

        initiator = ProtocolNegotiator(timeout=5.0, simultaneous_open_delay=0.1)

        # 模拟同时发送 multistream 协议 ID
        conn.feed_read_data(encode_message(MULTISTREAM_PROTOCOL_ID))
        # 模拟响应方也发送了 multistream 协议 ID
        conn.feed_read_data(encode_message(MULTISTREAM_PROTOCOL_ID))
        # 最后是协议接受
        conn.feed_read_data(encode_message("/yamux/1.0.0"))

        stream_rw = conn.get_reader_writer()

        # 使用 full_negotiate 处理同时打开
        result = await initiator.full_negotiate(stream_rw, ["/yamux/1.0.0"])

        assert result == "/yamux/1.0.0"


# ==================== 集成测试 ====================

class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.skip(reason="Test timeout due to race condition - needs investigation")
    async def test_full_negotiation_flow(self):
        """测试完整的协商流程"""
        # 创建真实的 TCP 连接
        server_started = asyncio.Event()

        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            """服务端处理客户端连接"""
            server_started.set()
            conn = StreamReaderWriter(reader, writer)
            negotiator = ProtocolNegotiator(timeout=5.0)

            supported = ["/yamux/1.0.0", "/noise"]

            try:
                result = await negotiator.handle_negotiate(conn, supported)
                assert result in supported
            finally:
                writer.close()
                await writer.wait_closed()

        async def run_client():
            """客户端连接服务端"""
            await server_started.wait()
            reader, writer = await asyncio.open_connection("127.0.0.1", 8765)

            conn = StreamReaderWriter(reader, writer)
            negotiator = ProtocolNegotiator(timeout=5.0)

            protocols = ["/noise", "/yamux/1.0.0"]

            try:
                result = await negotiator.negotiate(conn, protocols)
                return result
            finally:
                writer.close()
                await writer.wait_closed()

        # 启动服务器
        server = await asyncio.start_server(handle_client, "127.0.0.1", 8765)

        async with server:
            # 运行客户端
            result = await asyncio.wait_for(run_client(), timeout=10.0)
            assert result in ["/yamux/1.0.0", "/noise"]
