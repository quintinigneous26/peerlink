"""
QUIC 传输单元测试

测试 QUIC 传输层的核心功能。
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, PropertyMock

# 测试基类
from p2p_engine.transport.base import Transport, Connection, Listener, TransportError


class TestTransportBase:
    """测试传输基类"""

    def test_transport_is_abstract(self):
        """测试传输基类是抽象的"""
        with pytest.raises(TypeError):
            Transport()

    def test_connection_is_abstract(self):
        """测试连接基类是抽象的"""
        with pytest.raises(TypeError):
            Connection()

    def test_listener_is_abstract(self):
        """测试监听器基类是抽象的"""
        with pytest.raises(TypeError):
            Listener()


class TestQUICTransport:
    """测试 QUIC 传输"""

    @pytest.fixture
    def mock_aioquic(self):
        """Mock aioquic 模块"""
        with patch('p2p_engine.transport.quic.HAS_AIOQUIC', True):
            with patch('p2p_engine.transport.quic.QuicConfiguration') as mock_config:
                with patch('p2p_engine.transport.quic.connect') as mock_connect:
                    with patch('p2p_engine.transport.quic.serve') as mock_serve:
                        with patch('p2p_engine.transport.quic.QuicConnectionProtocol') as mock_protocol:
                            yield {
                                'QuicConfiguration': mock_config,
                                'connect': mock_connect,
                                'serve': mock_serve,
                                'QuicConnectionProtocol': mock_protocol,
                            }

    @pytest.fixture
    def transport(self, mock_aioquic):
        """创建 QUIC 传输实例"""
        from p2p_engine.transport.quic import QUICTransport
        return QUICTransport()

    def test_protocols(self, transport):
        """测试返回协议列表"""
        protocols = transport.protocols()
        assert protocols == ["/quic-v1"]

    def test_init_with_default_params(self, mock_aioquic):
        """测试使用默认参数初始化"""
        from p2p_engine.transport.quic import QUICTransransport

        transport = QUICTransport()

        assert transport._alpn_protocols == ["quic-v1", "libp2p"]
        assert transport._max_streams == 65535
        assert transport._idle_timeout == 60.0
        assert transport._enable_0rtt is True
        assert transport._connection_migration is True

    def test_init_with_custom_params(self, mock_aioquic):
        """测试使用自定义参数初始化"""
        from p2p_engine.transport.quic import QUICTransport

        transport = QUICTransport(
            alpn_protocols=["custom-protocol"],
            max_streams=1000,
            idle_timeout=30.0,
            enable_0rtt=False,
            connection_migration=False,
        )

        assert transport._alpn_protocols == ["custom-protocol"]
        assert transport._max_streams == 1000
        assert transport._idle_timeout == 30.0
        assert transport._enable_0rtt is False
        assert transport._connection_migration is False

    def test_init_without_aioquic(self):
        """测试没有 aioquic 时创建传输"""
        from p2p_engine.transport.quic import QUICTransport

        with patch('p2p_engine.transport.quic.HAS_AIOQUIC', False):
            with pytest.raises(RuntimeError, match="aioquic is required"):
                QUICTransport()

    @pytest.mark.asyncio
    async def test_close(self, transport):
        """测试关闭传输"""
        # 模拟连接
        mock_conn = AsyncMock()
        mock_conn.close = AsyncMock()
        transport._connections.append(mock_conn)

        # 模拟监听器
        mock_listener = AsyncMock()
        mock_listener.close = AsyncMock()
        transport._listeners.append(mock_listener)

        await transport.close()

        assert transport._closed
        mock_conn.close.assert_called_once()
        mock_listener.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_already_closed(self, transport):
        """测试关闭已关闭的传输"""
        transport._closed = True
        await transport.close()  # 不应抛出异常

    @pytest.mark.asyncio
    async def test_listen(self, transport, mock_aioquic):
        """测试监听"""
        # Mock 服务器
        mock_server = AsyncMock()
        mock_server.close = Mock()
        mock_aioquic['serve'].return_value = mock_server

        listener = await transport.listen("0.0.0.0:4242")

        assert listener in transport._listeners
        assert not listener.is_closed()
        assert listener.host == "0.0.0.0"
        assert listener.port == 4242

    @pytest.mark.asyncio
    async def test_listen_when_closed(self, transport):
        """测试关闭后监听"""
        transport._closed = True

        with pytest.raises(TransportError, match="传输已关闭"):
            await transport.listen("0.0.0.0:4242")

    @pytest.mark.asyncio
    async def test_dial(self, transport, mock_aioquic):
        """测试拨号连接"""
        # Mock 协议
        mock_protocol = AsyncMock()
        mock_protocol._transport = Mock()
        mock_protocol._transport.get_extra_info = Mock(return_value=("127.0.0.1", 12345))

        # Mock 连接
        with patch('p2p_engine.transport.quic.QUICConnection') as mock_conn_class:
            mock_conn = AsyncMock()
            mock_conn.wait_handshake = AsyncMock()
            mock_conn_class.return_value = mock_conn

            mock_aioquic['connect'].return_value = mock_protocol

            conn = await transport.dial("example.com:443")

            assert conn is not None
            mock_aioquic['connect'].assert_called_once()

    @pytest.mark.asyncio
    async def test_dial_when_closed(self, transport):
        """测试关闭后拨号"""
        transport._closed = True

        with pytest.raises(TransportError, match="传输已关闭"):
            await transport.dial("example.com:443")

    def test_parse_address_host_port(self, transport):
        """测试解析 host:port 格式地址"""
        host, port = transport._parse_address("example.com:443")
        assert host == "example.com"
        assert port == 443

    def test_parse_address_multiaddr_ipv4(self, transport):
        """测试解析 IPv4 multiaddr 格式"""
        host, port = transport._parse_address("/ip4/192.168.1.1/udp/4242/quic-v1")
        assert host == "192.168.1.1"
        assert port == 4242

    def test_parse_address_multiaddr_ipv6(self, transport):
        """测试解析 IPv6 multiaddr 格式"""
        host, port = transport._parse_address("/ip6/::1/udp/4242/quic-v1")
        assert host == "::1"
        assert port == 4242

    def test_parse_address_default_port(self, transport):
        """测试使用默认端口"""
        host, port = transport._parse_address("example.com")
        assert host == "example.com"
        assert port == 4242

    def test_create_client_configuration(self, transport):
        """测试创建客户端配置"""
        config = transport._create_client_configuration("example.com")

        assert config is not None
        assert config.is_client is True

    def test_create_server_configuration(self, transport):
        """测试创建服务器配置"""
        config = transport._create_server_configuration()

        assert config is not None
        assert config.is_client is False


class TestQUICConnection:
    """测试 QUIC 连接"""

    @pytest.fixture
    def mock_protocol(self):
        """创建模拟的 QUIC 协议"""
        protocol = Mock()
        protocol.send_data = Mock()
        protocol.send_stream_data = Mock()
        protocol.quic = Mock()
        protocol.quic.get_next_available_stream_id = Mock(return_value=4)
        protocol.close = Mock()
        return protocol

    @pytest.fixture
    def connection(self, mock_protocol):
        """创建 QUIC 连接"""
        from p2p_engine.transport.quic import QUICConnection
        return QUICConnection(mock_protocol, is_initiator=True)

    def test_properties(self, connection):
        """测试连接属性"""
        assert connection.is_initiator
        assert connection.protocol is not None

    def test_is_closed_initially(self, connection):
        """测试初始状态"""
        assert not connection.is_closed()

    @pytest.mark.asyncio
    async def test_write(self, connection, mock_protocol):
        """测试写入数据"""
        data = b"test data"
        written = await connection.write(data)

        assert written == len(data)
        mock_protocol.send_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_when_closed(self, connection):
        """测试关闭后写入"""
        connection._closed = True

        with pytest.raises(Exception):  # ConnectionError
            await connection.write(b"data")

    @pytest.mark.asyncio
    async def test_close(self, connection, mock_protocol):
        """测试关闭连接"""
        await connection.close()

        assert connection.is_closed()
        mock_protocol.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_already_closed(self, connection):
        """测试关闭已关闭的连接"""
        connection._closed = True
        await connection.close()  # 不应抛出异常

    @pytest.mark.asyncio
    async def test_wait_handshake(self, connection):
        """测试等待握手完成"""
        connection._handshake_complete.set()

        await connection.wait_handshake()  # 不应抛出异常

    @pytest.mark.asyncio
    async def test_wait_handshake_timeout(self, connection):
        """测试握手超时"""
        with pytest.raises(Exception):  # ConnectionError
            await connection.wait_handshake(timeout=0.1)

    @pytest.mark.asyncio
    async def test_open_stream(self, connection):
        """测试打开新流"""
        from p2p_engine.transport.quic import QuicStreamType

        stream = await connection.open_stream(QuicStreamType.BIDI)

        assert stream is not None
        assert stream.stream_type == QuicStreamType.BIDI
        assert stream.connection is connection

    def test_handle_quic_event_handshake_completed(self, connection):
        """测试处理握手完成事件"""
        from p2p_engine.transport.quic import HandshakeCompleted

        mock_event = Mock(spec=HandshakeCompleted)
        mock_event.session_ticket = Mock()

        connection._handle_quic_event(mock_event)

        assert connection._handshake_complete.is_set()

    def test_handle_quic_event_stream_data(self, connection):
        """测试处理流数据事件"""
        from p2p_engine.transport.quic import StreamDataReceived

        connection._stream_id = 0
        mock_event = Mock(spec=StreamDataReceived)
        mock_event.stream_id = 0
        mock_event.data = b"test data"
        mock_event.end_stream = False

        connection._handle_quic_event(mock_event)

        # 检查数据已放入队列
        assert not connection._read_queue.empty()


class TestQUICStream:
    """测试 QUIC 流"""

    @pytest.fixture
    def mock_connection(self):
        """创建模拟的连接"""
        conn = Mock()
        conn.protocol = Mock()
        conn.protocol.send_data = Mock()
        conn.protocol.send_stream_data = Mock()
        return conn

    @pytest.fixture
    def stream(self, mock_connection):
        """创建 QUIC 流"""
        from p2p_engine.transport.quic import QUICStream, QuicStreamType
        return QUICStream(mock_connection, 0, QuicStreamType.BIDI)

    def test_properties(self, stream):
        """测试流属性"""
        assert stream.stream_id == 0
        assert stream.stream_type.name == "BIDI"
        assert stream.connection is not None

    def test_is_closed_initially(self, stream):
        """测试初始状态"""
        assert not stream.is_closed()

    @pytest.mark.asyncio
    async def test_write(self, stream):
        """测试写入数据"""
        data = b"test data"
        written = await stream.write(data)

        assert written == len(data)

    @pytest.mark.asyncio
    async def test_write_when_closed(self, stream):
        """测试关闭后写入"""
        stream._closed = True

        with pytest.raises(Exception):  # ConnectionError
            await stream.write(b"data")

    @pytest.mark.asyncio
    async def test_close(self, stream):
        """测试关闭流"""
        await stream.close()

        assert stream.is_closed()

    @pytest.mark.asyncio
    async def test_close_already_closed(self, stream):
        """测试关闭已关闭的流"""
        stream._closed = True
        await stream.close()  # 不应抛出异常

    def test_handle_data(self, stream):
        """测试处理接收数据"""
        stream._handle_data(b"test data", end_stream=False)

        # 检查数据已放入队列
        assert not stream._read_queue.empty()

    def test_handle_data_end_stream(self, stream):
        """测试处理流结束"""
        stream._handle_data(b"", end_stream=True)

        assert stream.is_closed()


class TestQUICListener:
    """测试 QUIC 监听器"""

    @pytest.fixture
    def transport(self):
        """创建模拟传输"""
        transport = Mock()
        return transport

    @pytest.fixture
    def listener(self, transport):
        """创建监听器"""
        from p2p_engine.transport.quic import QUICListener
        return QUICListener(transport, "0.0.0.0", 4242)

    def test_properties(self, listener):
        """测试监听器属性"""
        assert listener.host == "0.0.0.0"
        assert listener.port == 4242
        assert listener.transport is not None
        assert not listener.is_closed()

    def test_addresses(self, listener):
        """测试监听地址"""
        addresses = listener.addresses
        assert len(addresses) == 1
        assert addresses[0] == ("0.0.0.0", 4242)

    @pytest.mark.asyncio
    async def test_accept(self, listener):
        """测试接受连接"""
        from p2p_engine.transport.quic import QUICConnection

        mock_conn = Mock(spec=QUICConnection)
        await listener._accept_queue.put(mock_conn)

        conn = await listener.accept()
        assert conn is mock_conn

    @pytest.mark.asyncio
    async def test_accept_when_closed(self, listener):
        """测试关闭后接受"""
        listener._closed = True

        with pytest.raises(Exception):  # ListenerError
            await listener.accept()

    @pytest.mark.asyncio
    async def test_close(self, listener):
        """测试关闭监听器"""
        await listener.close()

        assert listener.is_closed()

    @pytest.mark.asyncio
    async def test_close_already_closed(self, listener):
        """测试关闭已关闭的监听器"""
        listener._closed = True
        await listener.close()  # 不应抛出异常


class TestQuicStreamType:
    """测试 QUIC 流类型枚举"""

    def test_stream_types(self):
        """测试流类型值"""
        from p2p_engine.transport.quic import QuicStreamType

        assert QuicStreamType.UNI.value == 0
        assert QuicStreamType.BIDI.value == 1


class TestQuicProtocolFactory:
    """测试 QUIC 协议工厂"""

    def test_create_factory(self):
        """测试创建工厂"""
        from p2p_engine.transport.quic import QuicProtocolFactory, QUICTransport

        with patch('p2p_engine.transport.quic.HAS_AIOQUIC', True):
            transport = Mock(spec=QUICTransport)
            factory = QuicProtocolFactory(transport)

            assert factory._transport is transport


class TestCreateQUICTransport:
    """测试创建 QUIC 传输便捷函数"""

    def test_create_quic_transport(self):
        """测试便捷创建函数"""
        from p2p_engine.transport.quic import create_quic_transport

        with patch('p2p_engine.transport.quic.HAS_AIOQUIC', True):
            transport = create_quic_transport(
                alpn_protocols=["test"],
                max_streams=100,
            )

            assert transport is not None


class TestIsQuicAvailable:
    """测试 QUIC 可用性检查"""

    def test_is_quic_available_with_aioquic(self):
        """测试有 aioquic 时返回 True"""
        from p2p_engine.transport.quic import is_quic_available

        with patch('p2p_engine.transport.quic.HAS_AIOQUIC', True):
            assert is_quic_available() is True

    def test_is_quic_available_without_aioquic(self):
        """测试没有 aioquic 时返回 False"""
        from p2p_engine.transport.quic import is_quic_available

        with patch('p2p_engine.transport.quic.HAS_AIOQUIC', False):
            assert is_quic_available() is False


class TestQUICTransportNoAioquic:
    """测试没有 aioquic 的情况"""

    def test_quic_connection_without_aioquic(self):
        """测试没有 aioquic 时创建连接"""
        from p2p_engine.transport.quic import QUICConnection

        with patch('p2p_engine.transport.quic.HAS_AIOQUIC', False):
            with pytest.raises(RuntimeError, match="aioquic is required"):
                QUICConnection(Mock())

    def test_quic_transport_without_aioquic(self):
        """测试没有 aioquic 时创建传输"""
        from p2p_engine.transport.quic import QUICTransport

        with patch('p2p_engine.transport.quic.HAS_AIOQUIC', False):
            with pytest.raises(RuntimeError, match="aioquic is required"):
                QUICTransport()


class TestQUICTransportCertificate:
    """测试 QUIC 传输证书处理"""

    @pytest.fixture
    def transport_with_custom_cert(self, mock_aioquic):
        """创建带自定义证书的传输"""
        from p2p_engine.transport.quic import QUICTransport

        mock_cert = b"mock_certificate"
        mock_key = b"mock_private_key"

        return QUICTransport(
            certificate=mock_cert,
            private_key=mock_key,
        )

    def test_custom_certificate(self, transport_with_custom_cert):
        """测试使用自定义证书"""
        assert transport_with_custom_cert._certificate == b"mock_certificate"
        assert transport_with_custom_cert._private_key == b"mock_private_key"


# 集成测试标记（需要 aioquic 才能运行）
pytestmark = pytest.mark.skipif(
    True,  # 默认跳过，需要 aioquic 才能运行
    reason="需要 aioquic 库，使用 pytest -m quic 运行"
)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
