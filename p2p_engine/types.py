"""
P2P Engine 核心类型定义

基于运营商差异化增强版架构设计
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Awaitable
import time


# ==================== 区域 ====================

class Region(Enum):
    """
    地理区域枚举

    用于标识网络节点所在的地理区域，支持全球主要地区。

    属性:
        MAINLAND: 中国大陆
        HONGKONG: 香港特别行政区
        SINGAPORE: 新加坡
        OVERSEAS: 其他海外地区
    """
    MAINLAND = "mainland"       # 中国大陆
    HONGKONG = "hongkong"       # 香港
    SINGAPORE = "singapore"     # 新加坡
    OVERSEAS = "overseas"       # 其他海外


# ==================== 运营商 ====================

class ISP(Enum):
    """
    互联网服务提供商（ISP）枚举

    全球主要运营商和ISP的标识符，用于网络检测和优化策略选择。
    支持中国大陆、香港、新加坡、美国、欧洲、东南亚、日韩等地区的主要运营商。

    中国大陆运营商:
        CHINA_TELECOM: 中国电信
        CHINA_MOBILE: 中国移动
        CHINA_UNICOM: 中国联通
        CHINA_RAILCOM: 中国铁通

    香港运营商:
        HKBN: 香港宽频
        CMHK: 中国移动香港
        THREE_HK: 3香港
        SMARTONE: 数码通

    新加坡运营商:
        SINGTEL: 新加坡电信
        STARHUB: 星和集团
        M1: M1有限公司

    美国运营商:
        ATT: AT&T
        VERIZON: Verizon
        TMOBILE: T-Mobile
        COMCAST: Comcast

    欧洲运营商:
        VODAFONE: 沃达丰
        ORANGE: 橙色电信
        DEUTSCHE_TELEKOM: 德国电信
        BT: 英国电信

    东南亚运营商:
        AIS: 泰国AIS
        TRUEMOVE: 泰国TrueMove
        MAXIS: 马来西亚Maxis
        DIGI: 马来西亚Digi

    日韩运营商:
        NTT: 日本NTT
        KDDI: 日本KDDI
        SK_TELECOM: 韩国SK电信
        KT: 韩国KT

    UNKNOWN: 未知运营商
    """
    # 中国大陆
    CHINA_TELECOM = "china_telecom"
    CHINA_MOBILE = "china_mobile"
    CHINA_UNICOM = "china_unicom"
    CHINA_RAILCOM = "china_railcom"
    
    # 香港
    HKBN = "hkbn"
    CMHK = "cmhk"
    THREE_HK = "3hk"
    SMARTONE = "smartone"
    
    # 新加坡
    SINGTEL = "singtel"
    STARHUB = "starhub"
    M1 = "m1"
    
    # 美国
    ATT = "att"
    VERIZON = "verizon"
    TMOBILE = "tmobile"
    COMCAST = "comcast"
    
    # 欧洲
    VODAFONE = "vodafone"
    ORANGE = "orange"
    DEUTSCHE_TELEKOM = "deutsche_telekom"
    BT = "bt"
    
    # 东南亚
    AIS = "ais"                 # 泰国
    TRUEMOVE = "truemove"       # 泰国
    MAXIS = "maxis"             # 马来西亚
    DIGI = "digi"               # 马来西亚
    
    # 日韩
    NTT = "ntt"                 # 日本
    KDDI = "kddi"               # 日本
    SK_TELECOM = "sk_telecom"   # 韩国
    KT = "kt"                   # 韩国
    
    # 未知
    UNKNOWN = "unknown"


# ==================== 设备厂商 ====================

class DeviceVendor(Enum):
    """网络设备厂商"""
    # 运营商级
    HUAWEI = "huawei"
    ZTE = "zte"
    ERICSSON = "ericsson"
    NOKIA = "nokia"
    FIBERHOME = "fiberhome"
    ALCATEL_LUCENT = "alcatel_lucent"
    SAMSUNG = "samsung"
    
    # 企业级
    CISCO = "cisco"
    H3C = "h3c"
    SANGFOR = "sangfor"
    QIANXIN = "qianxin"
    QIMINGXING = "qimingxing"
    TIANRONGXIN = "tianrongxin"
    PALO_ALTO = "palo_alto"
    FORTINET = "fortinet"
    JUNIPER = "juniper"
    CHECKPOINT = "checkpoint"
    
    # 家用级
    TP_LINK = "tp_link"
    XIAOMI = "xiaomi"
    ASUS = "asus"
    NETGEAR = "netgear"
    
    # 未知
    UNKNOWN = "unknown"


# ==================== NAT 类型 ====================

class NATType(Enum):
    """
    NAT类型枚举 (RFC 3489)

    根据RFC 3489标准定义的NAT类型，用于判断NAT穿透的可行性。

    属性:
        FULL_CONE: 完全圆锥型NAT
            - 所有来自同一内部IP和端口的请求都映射到同一外部IP和端口
            - 任何外部主机都可以通过该外部地址向内部主机发送数据包
            - 穿透难度：最低

        RESTRICTED_CONE: 受限圆锥型NAT
            - 所有来自同一内部IP和端口的请求都映射到同一外部IP和端口
            - 外部主机只有在内部主机先向其发送过数据包后，才能向内部主机发送数据包
            - 穿透难度：中等

        PORT_RESTRICTED: 端口受限圆锥型NAT
            - 所有来自同一内部IP和端口的请求都映射到同一外部IP和端口
            - 外部主机只有在内部主机先向其特定端口发送过数据包后，才能向内部主机发送数据包
            - 穿透难度：中等偏高

        SYMMETRIC: 对称型NAT
            - 每个新的会话都会创建一个新的外部IP和端口映射
            - 穿透难度：最高，通常需要中继服务器

        UNKNOWN: 未知NAT类型
    """
    FULL_CONE = "full_cone"
    RESTRICTED_CONE = "restricted_cone"
    PORT_RESTRICTED = "port_restricted"
    SYMMETRIC = "symmetric"
    UNKNOWN = "unknown"


# ==================== NAT 信息 ====================

@dataclass
class NATInfo:
    """
    NAT信息数据类

    存储NAT检测结果和相关的网络信息，用于连接策略决策。

    属性:
        type (NATType): NAT类型
        public_ip (str): 公网IP地址
        public_port (int): 公网端口
        local_ip (str): 本地IP地址
        local_port (int): 本地端口
        is_cgnat (bool): 是否为CGNAT（运营商级NAT）
        cgnat_level (int): CGNAT层级（0表示非CGNAT）
        hairpin_supported (bool): 是否支持发夹效应（Hairpin）
        port_delta (int): 端口增量（用于对称NAT端口预测）
        mapping_timeout_sec (int): 映射超时时间（秒）
        device_vendor (DeviceVendor): NAT设备厂商

    方法:
        is_symmetric(): 判断是否为对称型NAT
        can_predict_port(): 判断是否可以预测端口
    """
    type: NATType = NATType.UNKNOWN
    
    # 地址信息
    public_ip: str = ""
    public_port: int = 0
    local_ip: str = ""
    local_port: int = 0
    
    # 增强信息
    is_cgnat: bool = False
    cgnat_level: int = 0
    hairpin_supported: bool = False
    port_delta: int = 1
    mapping_timeout_sec: int = 30
    
    # 新增：设备厂商
    device_vendor: DeviceVendor = DeviceVendor.UNKNOWN
    
    def is_symmetric(self) -> bool:
        return self.type == NATType.SYMMETRIC
    
    def can_predict_port(self) -> bool:
        return self.is_symmetric() and self.port_delta > 0


# ==================== 网络环境 ====================

@dataclass
class NetworkEnvironment:
    """
    网络环境信息数据类

    描述节点所处的网络环境特征，用于选择合适的连接策略。

    属性:
        nat_level (int): NAT层级数（1表示无NAT，>1表示多层NAT）
        is_behind_vpn (bool): 是否在VPN后
        is_behind_cdn (bool): 是否在CDN后
        is_enterprise_network (bool): 是否为企业网络
        is_mobile_network (bool): 是否为移动网络（4G/5G）
        firewall_type (str): 防火墙类型
            - "home": 家用防火墙
            - "enterprise": 企业防火墙
            - "isp": ISP级防火墙
            - "cross_border": 跨境防火墙
            - "unknown": 未知
        ipv6_available (bool): IPv6是否可用
        ipv6_preferred (bool): 是否优先使用IPv6
        packet_loss_rate (float): 丢包率（0.0-1.0）
        avg_latency_ms (float): 平均延迟（毫秒）

    方法:
        is_complex_environment(): 判断是否为复杂网络环境
    """
    # NAT 层级
    nat_level: int = 1                  # NAT 层数
    
    # 特殊环境
    is_behind_vpn: bool = False         # 是否在 VPN 后
    is_behind_cdn: bool = False         # 是否在 CDN 后
    is_enterprise_network: bool = False # 是否企业网络
    is_mobile_network: bool = False     # 是否移动网络(4G/5G)
    
    # 防火墙类型
    firewall_type: str = "unknown"      # home | enterprise | isp | cross_border
    
    # IPv6
    ipv6_available: bool = False
    ipv6_preferred: bool = False
    
    # 链路质量
    packet_loss_rate: float = 0.0       # 丢包率
    avg_latency_ms: float = 0.0         # 平均延迟
    
    def is_complex_environment(self) -> bool:
        """是否为复杂网络环境"""
        return (
            self.nat_level >= 3 or
            self.is_behind_vpn or
            self.is_enterprise_network or
            self.packet_loss_rate > 0.1
        )


# ==================== 连接状态 ====================

class ConnectionState(Enum):
    """
    连接状态枚举

    表示P2P连接的各个阶段状态，用于状态机驱动的连接流程。

    属性:
        IDLE: 空闲状态，未开始连接
        DETECTING: 检测阶段，正在进行NAT检测和网络环境分析
        SIGNALING: 信令阶段，通过信令服务器交换连接信息
        PUNCHING: 打洞阶段，正在进行NAT穿透
        CONNECTING: 连接中，正在建立P2P连接
        CONNECTED: 已连接，P2P连接成功建立
        RELAY: 中继模式，使用中继服务器转发数据
        RECONNECTING: 重新连接中，连接断开后正在重新建立
        DISCONNECTED: 已断开，连接已正常断开
        FAILED: 失败，连接建立失败
    """
    IDLE = "idle"
    DETECTING = "detecting"
    SIGNALING = "signaling"
    PUNCHING = "punching"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RELAY = "relay"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


class ConnectionType(Enum):
    """
    连接类型枚举

    表示实际建立的连接类型，用于区分直连和中继连接。

    属性:
        P2P_UDP: 直连UDP连接（最优）
        P2P_TCP: 直连TCP连接（备选）
        RELAY_UDP: 中继UDP连接（降级方案）
        RELAY_TCP: 中继TCP连接（降级方案）
        FAILED: 连接失败
    """
    P2P_UDP = "p2p_udp"
    P2P_TCP = "p2p_tcp"
    RELAY_UDP = "relay_udp"
    RELAY_TCP = "relay_tcp"
    FAILED = "failed"


# ==================== 事件系统 ====================

class EventType(Enum):
    """
    事件类型枚举

    P2P引擎中发生的各类事件，用于事件驱动的应用程序。

    属性:
        CONNECT: 连接请求事件
        DISCONNECT: 断开连接事件
        DETECTION_DONE: 网络检测完成事件
        SIGNALING_DONE: 信令交换完成事件
        PUNCH_SUCCESS: NAT穿透成功事件
        PUNCH_FAILED: NAT穿透失败事件
        RELAY_CONNECTED: 中继连接建立事件
        RELAY_FAILED: 中继连接失败事件
        HEARTBEAT_TIMEOUT: 心跳超时事件
        NETWORK_CHANGED: 网络变化事件
        ERROR: 错误事件
    """
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    DETECTION_DONE = "detection_done"
    SIGNALING_DONE = "signaling_done"
    PUNCH_SUCCESS = "punch_success"
    PUNCH_FAILED = "punch_failed"
    RELAY_CONNECTED = "relay_connected"
    RELAY_FAILED = "relay_failed"
    HEARTBEAT_TIMEOUT = "heartbeat_timeout"
    NETWORK_CHANGED = "network_changed"
    ERROR = "error"


@dataclass
class Event:
    """
    事件数据类

    表示P2P引擎中发生的事件，包含事件类型、数据和时间戳。

    属性:
        type (EventType): 事件类型
        data (dict): 事件数据，根据事件类型包含不同的字段
        timestamp (float): 事件发生的时间戳（Unix时间）
    """
    type: EventType
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ==================== 回调类型 ====================

StateCallback = Callable[[ConnectionState, ConnectionType, Optional[str]], Awaitable[None]]
DataCallback = Callable[[bytes, tuple], Awaitable[None]]
ErrorCallback = Callable[[Exception], Awaitable[None]]


# ==================== 连接结果 ====================

@dataclass
class ConnectionResult:
    """
    连接结果数据类

    包含连接尝试的完整结果信息，用于应用程序判断连接状态和选择后续操作。

    属性:
        success (bool): 连接是否成功
        connection_type (ConnectionType): 连接类型
        latency_ms (float): 连接延迟（毫秒）
        local_nat (Optional[NATInfo]): 本地NAT信息
        peer_nat (Optional[NATInfo]): 对端NAT信息
        local_isp (ISP): 本地ISP
        peer_isp (ISP): 对端ISP
        local_env (Optional[NetworkEnvironment]): 本地网络环境
        peer_env (Optional[NetworkEnvironment]): 对端网络环境
        is_fallback (bool): 是否为降级方案
        fallback_reason (str): 降级原因
        error (Optional[str]): 错误信息

    方法:
        to_dict(): 将结果转换为字典格式
    """
    success: bool
    connection_type: ConnectionType
    latency_ms: float = 0.0
    
    local_nat: Optional[NATInfo] = None
    peer_nat: Optional[NATInfo] = None
    local_isp: ISP = ISP.UNKNOWN
    peer_isp: ISP = ISP.UNKNOWN
    
    # 网络环境
    local_env: Optional[NetworkEnvironment] = None
    peer_env: Optional[NetworkEnvironment] = None
    
    is_fallback: bool = False
    fallback_reason: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "connection_type": self.connection_type.value,
            "latency_ms": self.latency_ms,
            "local_nat": self.local_nat.type.value if self.local_nat else None,
            "peer_nat": self.peer_nat.type.value if self.peer_nat else None,
            "local_isp": self.local_isp.value,
            "peer_isp": self.peer_isp.value,
            "is_fallback": self.is_fallback,
            "fallback_reason": self.fallback_reason,
            "error": self.error,
        }


# ==================== 对端信息 ====================

@dataclass
class PeerInfo:
    """
    对端信息数据类

    存储对端节点的相关信息，用于连接建立和优化。

    属性:
        peer_id (str): 对端节点ID
        public_ip (str): 对端公网IP
        public_port (int): 对端公网端口
        nat_info (Optional[NATInfo]): 对端NAT信息
        isp (ISP): 对端ISP
        network_env (Optional[NetworkEnvironment]): 对端网络环境
        candidates (list): 候选地址列表
    """
    peer_id: str
    public_ip: str = ""
    public_port: int = 0
    nat_info: Optional[NATInfo] = None
    isp: ISP = ISP.UNKNOWN
    network_env: Optional[NetworkEnvironment] = None
    candidates: list = field(default_factory=list)
