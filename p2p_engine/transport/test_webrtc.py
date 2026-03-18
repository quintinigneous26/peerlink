"""
WebRTC 传输单元测试

测试 WebRTC 传输层的核心功能。
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

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


class TestWebRTCTransport:
    """测试 WebRTC 传输"""

    @pytest.fixture
    def mock_aiortc(self):
        """Mock aiortc 模块"""
        with patch('p2p_engine.transport.webrtc.HAS_AIORTC', True):
            with patch('p2p_engine.transport.webrtc.RTCPeerConnection') as mock_pc:
                with patch('p2p_engine.transport.webrtc.RTCConfiguration') as mock_config:
                    with patch('p2p_engine.transport.webrtc.RTCIceServer') as mock_ice:
                        with patch('p2p_engine.transport.webrtc.RTCSessionDescription') as mock_sdp:
                            with patch('p2p_engine.transport.webrtc.DataChannel') as mock_dc:
                                yield {
                                    'RTCPeerConnection': mock_pc,
                                    'RTCConfiguration': mock_config,
                                    'RTCIceServer': mock_ice,
                                    'RTCSessionDescription': mock_sdp,
                                    'DataChannel': mock_dc,
                                }

    @pytest.fixture
    def transport(self, mock_aiortc):
        """创建 WebRTC 传输实例"""
        from p2p_engine.transport.webrtc import WebRTCTransport
        return WebRTCTransport()

    def test_protocols(self, transport):
        """测试返回协议列表"""
        protocols = transport.protocols()
        assert protocols == ["/webrtc-direct"]

    def test_init_with_custom_stun_servers(self, mock_aiortc):
        """测试使用自定义 STUN 服务器初始化"""
        from p2p_engine.transport.webrtc import WebRTCTransport

        stun_servers = ["stun:custom.server:3478"]
        transport = WebRTCTransport(stun_servers=stun_servers)

        assert transport._stun_servers == stun_servers

    def test_init_with_ice_servers(self, mock_aiortc):
        """测试使用自定义 ICE 服务器初始化"""
        from p2p_engine.transport.webrtc import WebRTCTransport, ICEServer

        ice_server = ICEServer(
            urls=["turn:turn.server:3478"],
            username="user",
            credential="pass",
        )
        transport = WebRTCTransport(ice_servers=[ice_server])

        assert len(transport._ice_servers) == 1

    @pytest.mark.asyncio
    async def test_close(self, transport):
        """测试关闭传输"""
        # 模拟连接
        mock_conn = AsyncMock()
        transport._connections.append(mock_conn)

        # 模拟监听器
        mock_listener = AsyncMock()
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

    def test_set_signaling_callback(self, transport):
        """测试设置信令回调"""
        async def callback(msg):
            pass

        transport.set_signaling_callback(callback)
        assert transport._on_signaling_message == callback

    @pytest.mark.asyncio
    async def test_listen(self, transport):
        """测试监听"""
        listener = await transport.listen("test-address")

        assert listener in transport._listeners
        assert not listener.is_closed()
        assert listener.local_address == "test-address"

    @pytest.mark.asyncio
    async def test_listen_when_closed(self, transport):
        """测试关闭后监听"""
        transport._closed = True

        with pytest.raises(TransportError):
            await transport.listen("test-address")


class TestWebRTCConnection:
    """测试 WebRTC 连接"""

    @pytest.fixture
    def mock_peer_connection(self):
        """创建模拟的 PeerConnection"""
        pc = Mock()
        pc.localDescription = None
        pc.remoteDescription = None
        pc.iceConnectionState = "new"
        pc.connectionState = "new"
        pc.close = AsyncMock()
        pc.setLocalDescription = AsyncMock()
        pc.setRemoteDescription = AsyncMock()
        pc.createOffer = AsyncMock()
        pc.createAnswer = AsyncMock()
        pc.addIceCandidate = Mock()
        return pc

    @pytest.fixture
    def mock_data_channel(self):
        """创建模拟的 DataChannel"""
        dc = Mock()
        dc.send = Mock()
        dc.close = Mock()
        return dc

    @pytest.fixture
    def connection(self, mock_peer_connection, mock_data_channel):
        """创建 WebRTC 连接"""
        from p2p_engine.transport.webrtc import WebRTCConnection
        return WebRTCConnection(
            peer_connection=mock_peer_connection,
            data_channel=mock_data_channel,
            is_initiator=True,
        )

    def test_properties(self, connection):
        """测试连接属性"""
        assert connection.is_initiator
        assert connection.peer_connection is not None
        assert connection.data_channel is not None

    def test_is_closed_initially(self, connection):
        """测试初始状态"""
        assert not connection.is_closed()

    @pytest.mark.asyncio
    async def test_write(self, connection, mock_data_channel):
        """测试写入数据"""
        data = b"test data"
        written = await connection.write(data)

        assert written == len(data)
        mock_data_channel.send.assert_called_once_with(data)

    @pytest.mark.asyncio
    async def test_write_when_closed(self, connection):
        """测试关闭后写入"""
        connection._closed = True
        connection._data_channel = Mock()

        with pytest.raises(Exception):  # ConnectionError
            await connection.write(b"data")

    @pytest.mark.asyncio
    async def test_write_without_data_channel(self, connection):
        """测试没有 DataChannel 时写入"""
        connection._data_channel = None

        with pytest.raises(Exception):  # ConnectionError
            await connection.write(b"data")

    @pytest.mark.asyncio
    async def test_close(self, connection, mock_data_channel, mock_peer_connection):
        """测试关闭连接"""
        await connection.close()

        assert connection.is_closed()
        mock_data_channel.close.assert_called_once()
        mock_peer_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_already_closed(self, connection):
        """测试关闭已关闭的连接"""
        connection._closed = True
        await connection.close()  # 不应抛出异常

    @pytest.mark.asyncio
    async def test_create_offer_by_initiator(self, connection):
        """测试发起方创建 Offer"""
        from p2p_engine.transport.webrtc import WebRTCConnection

        # Mock createOffer 和 setLocalDescription
        pc = connection.peer_connection
        mock_offer = Mock()
        mock_offer.sdp = "test-sdp"
        pc.createOffer = AsyncMock(return_value=mock_offer)
        pc.setLocalDescription = AsyncMock()

        # 设置 ICE 收集完成事件
        connection._ice_gathering_complete.set()

        offer = await connection.create_offer()

        assert offer is not None
        pc.createOffer.assert_called_once()
        pc.setLocalDescription.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_offer_by_non_initiator(self, mock_peer_connection):
        """测试非发起方不能创建 Offer"""
        from p2p_engine.transport.webrtc import WebRTCConnection

        connection = WebRTCConnection(
            peer_connection=mock_peer_connection,
            is_initiator=False,
        )

        with pytest.raises(Exception):  # ConnectionError
            await connection.create_offer()

    @pytest.mark.asyncio
    async def test_create_answer_by_responder(self, mock_peer_connection):
        """测试应答方创建 Answer"""
        from p2p_engine.transport.webrtc import WebRTCConnection

        connection = WebRTCConnection(
            peer_connection=mock_peer_connection,
            is_initiator=False,
        )

        # Mock createAnswer 和 setLocalDescription
        mock_answer = Mock()
        mock_answer.sdp = "test-answer-sdp"
        mock_peer_connection.createAnswer = AsyncMock(return_value=mock_answer)
        mock_peer_connection.setLocalDescription = AsyncMock()

        # 设置 ICE 收集完成事件
        connection._ice_gathering_complete.set()

        answer = await connection.create_answer()

        assert answer is not None
        mock_peer_connection.createAnswer.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_remote_description(self, connection):
        """测试设置远程描述"""
        from p2p_engine.transport.webrtc import RTCSessionDescription

        mock_sdp = Mock()
        connection.peer_connection.setRemoteDescription = AsyncMock()

        await connection.set_remote_description(mock_sdp)

        connection.peer_connection.setRemoteDescription.assert_called_once_with(mock_sdp)

    def test_add_ice_candidate(self, connection):
        """测试添加 ICE 候选"""
        candidate_dict = {
            "sdpMid": "0",
            "sdpMLineIndex": 0,
            "candidate": "test-candidate",
        }

        connection.add_ice_candidate(candidate_dict)

        pc = connection.peer_connection
        pc.addIceCandidate.assert_called_once()

    def test_get_ice_candidates(self, connection):
        """测试获取 ICE 候选"""
        connection._ice_candidates = [{"candidate": "test"}]

        candidates = connection.get_ice_candidates()

        assert candidates == [{"candidate": "test"}]


class TestWebRTCListener:
    """测试 WebRTC 监听器"""

    @pytest.fixture
    def transport(self):
        """创建模拟传输"""
        transport = Mock()
        transport._create_connection = AsyncMock()
        return transport

    @pytest.fixture
    def listener(self, transport):
        """创建监听器"""
        from p2p_engine.transport.webrtc import WebRTCListener
        return WebRTCListener(transport, "test-address")

    def test_properties(self, listener):
        """测试监听器属性"""
        assert listener.local_address == "test-address"
        assert listener.transport is not None
        assert not listener.is_closed()

    def test_addresses(self, listener):
        """测试监听地址"""
        addresses = listener.addresses
        assert len(addresses) == 1
        assert addresses[0] == ("webrtc", "test-address")

    @pytest.mark.asyncio
    async def test_accept(self, listener):
        """测试接受连接"""
        from p2p_engine.transport.webrtc import WebRTCConnection

        mock_conn = Mock(spec=WebRTCConnection)
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


class TestSignalingMessage:
    """测试信令消息"""

    def test_to_json(self):
        """测试 JSON 序列化"""
        from p2p_engine.transport.webrtc import SignalingMessage, SignalingMessageType

        msg = SignalingMessage(
            type=SignalingMessageType.OFFER,
            data={"sdp": "test"},
            peer_id="peer-1",
        )

        json_str = msg.to_json()
        assert '"type": "offer"' in json_str
        assert '"peer_id": "peer-1"' in json_str

    def test_from_json(self):
        """测试 JSON 反序列化"""
        from p2p_engine.transport.webrtc import SignalingMessage, SignalingMessageType

        json_str = '{"type": "offer", "data": {"sdp": "test"}, "peer_id": "peer-1"}'
        msg = SignalingMessage.from_json(json_str)

        assert msg.type == SignalingMessageType.OFFER
        assert msg.data == {"sdp": "test"}
        assert msg.peer_id == "peer-1"


class TestICEServer:
    """测试 ICE 服务器配置"""

    def test_to_aiortc(self):
        """测试转换为 aiortc 格式"""
        from p2p_engine.transport.webrtc import ICEServer

        with patch('p2p_engine.transport.webrtc.HAS_AIORTC', True):
            with patch('p2p_engine.transport.webrtc.RTCIceServer') as mock_ice_class:
                server = ICEServer(
                    urls=["stun:stun.server:19302"],
                    username="user",
                    credential="pass",
                )

                mock_ice_instance = Mock()
                mock_ice_class.return_value = mock_ice_instance

                result = server.to_aiortc()

                assert result is mock_ice_instance
                mock_ice_class.assert_called_once_with(
                    urls=["stun:stun.server:19302"],
                    username="user",
                    credential="pass",
                )

    def test_to_aiortc_without_aiortc(self):
        """测试没有 aiortc 时转换"""
        from p2p_engine.transport.webrtc import ICEServer

        with patch('p2p_engine.transport.webrtc.HAS_AIORTC', False):
            server = ICEServer(urls=["stun:stun.server:19302"])

            with pytest.raises(RuntimeError, match="aiortc not installed"):
                server.to_aiortc()


class TestWebRTCNoAiortc:
    """测试没有 aiortc 的情况"""

    def test_webrtc_connection_without_aiortc(self):
        """测试没有 aiortc 时创建连接"""
        from p2p_engine.transport.webrtc import WebRTCConnection

        with patch('p2p_engine.transport.webrtc.HAS_AIORTC', False):
            with pytest.raises(RuntimeError, match="aiortc is required"):
                WebRTCConnection(Mock())

    def test_webrtc_transport_without_aiortc(self):
        """测试没有 aiortc 时创建传输"""
        from p2p_engine.transport.webrtc import WebRTCTransport

        with patch('p2p_engine.transport.webrtc.HAS_AIORTC', False):
            with pytest.raises(RuntimeError, match="aiortc is required"):
                WebRTCTransport()


# 集成测试标记（需要 aiortc 才能运行）
pytestmark = pytest.mark.skipif(
    True,  # 默认跳过，需要 aiortc 才能运行
    reason="需要 aiortc 库，使用 pytest -m webrtc 运行"
)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
