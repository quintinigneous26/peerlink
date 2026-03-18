"""
multistream-select 消息编码/解码模块

协议规范:
- 消息格式: varint长度前缀 + UTF-8字符串 + \n
- varint: 无符号变长整数编码 (multiformats unsigned varint)

参考: https://github.com/multiformats/unsigned-varint
"""

from typing import Union


# ==================== Varint 编解码 ====================

def encode_varint(value: int) -> bytes:
    """
    将无符号整数编码为 varint 格式

    Args:
        value: 要编码的无符号整数

    Returns:
        varint 编码的字节序列

    Raises:
        ValueError: 如果值为负数

    Examples:
        >>> encode_varint(0)
        b'\\x00'
        >>> encode_varint(3)
        b'\\x03'
        >>> encode_varint(300)
        b'\\xac\\x02'
    """
    if value < 0:
        raise ValueError("varint 只支持无符号整数")

    if value == 0:
        return b'\x00'

    result = bytearray()
    while value > 0:
        # 取低 7 位
        byte = value & 0x7f
        value >>= 7
        # 如果还有更多数据，设置最高位为 1
        if value > 0:
            byte |= 0x80
        result.append(byte)

    return bytes(result)


def decode_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    """
    从 varint 格式解码无符号整数

    Args:
        data: 包含 varint 编码的字节序列
        offset: 开始解码的位置偏移量

    Returns:
        (解码后的值, 消耗的字节数)

    Raises:
        ValueError: 如果 varint 格式无效或数据不足

    Examples:
        >>> decode_varint(b'\\x00')
        (0, 1)
        >>> decode_varint(b'\\xac\\x02')
        (300, 2)
    """
    if offset >= len(data):
        raise ValueError("数据不足，无法解码 varint")

    result = 0
    shift = 0
    bytes_consumed = 0

    for i in range(offset, len(data)):
        byte = data[i]
        bytes_consumed += 1

        # 取低 7 位，累加到结果
        result |= (byte & 0x7f) << shift

        # 如果最高位为 0，表示这是最后一个字节
        if (byte & 0x80) == 0:
            return result, bytes_consumed

        shift += 7

        # 防止 varint 过长导致的问题 (最多 9 字节对应 64 位)
        if bytes_consumed > 9:
            raise ValueError("varint 过长")

    raise ValueError("varint 不完整")


# ==================== 消息常量 ====================

MULTISTREAM_PROTOCOL_ID = "/multistream/1.0.0"
NA_RESPONSE = "na"


# ==================== 消息编解码 ====================

def encode_message(data: str) -> bytes:
    """
    编码 multistream-select 消息

    格式: varint(长度) + UTF-8字符串 + \n

    Args:
        data: 要编码的字符串

    Returns:
        编码后的字节序列

    Examples:
        >>> encode_message("na")
        b'\\x03na\\n'
        >>> encode_message("/multistream/1.0.0")
        b'\\x13/multistream/1.0.0\\n'
    """
    # 将字符串编码为 UTF-8，并添加换行符
    message_bytes = (data + '\n').encode('utf-8')

    # 添加 varint 长度前缀
    length_prefix = encode_varint(len(message_bytes))

    return length_prefix + message_bytes


def decode_message(data: bytes) -> str:
    """
    解码 multistream-select 消息

    Args:
        data: 要解码的字节序列

    Returns:
        解码后的字符串 (不含换行符)

    Raises:
        ValueError: 如果消息格式无效

    Examples:
        >>> decode_message(b'\\x03na\\n')
        'na'
        >>> decode_message(b'\\x13/multistream/1.0.0\\n')
        '/multistream/1.0.0'
    """
    # 解码 varint 长度前缀
    length, varint_size = decode_varint(data)

    # 验证数据长度
    if len(data) < varint_size + length:
        raise ValueError(f"数据长度不足: 期望 {varint_size + length}, 实际 {len(data)}")

    # 提取消息内容
    message_bytes = data[varint_size:varint_size + length]

    # 解码为字符串并去除换行符
    message = message_bytes.decode('utf-8').strip()

    return message


def decode_message_with_offset(data: bytes, offset: int = 0) -> tuple[str, int]:
    """
    从指定偏移量解码 multistream-select 消息

    Args:
        data: 要解码的字节序列
        offset: 开始解码的位置偏移量

    Returns:
        (解码后的字符串, 消耗的总字节数)

    Raises:
        ValueError: 如果消息格式无效
    """
    # 解码 varint 长度前缀
    length, varint_size = decode_varint(data, offset)

    # 验证数据长度
    if len(data) < offset + varint_size + length:
        raise ValueError(f"数据长度不足: 期望 {offset + varint_size + length}, 实际 {len(data)}")

    # 提取消息内容
    message_bytes = data[offset + varint_size:offset + varint_size + length]

    # 解码为字符串并去除换行符
    message = message_bytes.decode('utf-8').strip()

    return message, varint_size + length


# ==================== 协议验证 ====================

def is_valid_protocol_id(protocol_id: str) -> bool:
    """
    验证协议 ID 是否有效

    有效的协议 ID 应该:
    1. 以 '/' 开头
    2. 不包含空格或控制字符
    3. 不为空

    Args:
        protocol_id: 要验证的协议 ID

    Returns:
        是否有效
    """
    if not protocol_id:
        return False

    if not protocol_id.startswith('/'):
        return False

    # 检查是否包含无效字符
    for char in protocol_id:
        if ord(char) < 0x20:  # 控制字符
            return False
        if char in (' ', '\t', '\n', '\r'):
            return False

    return True


def is_multistream_protocol(message: str) -> bool:
    """
    检查消息是否是 multistream-select 协议 ID

    Args:
        message: 要检查的消息字符串

    Returns:
        是否是 multistream-select 协议 ID
    """
    return message == MULTISTREAM_PROTOCOL_ID


def is_na_response(message: str) -> bool:
    """
    检查消息是否是 "na" (不可用) 响应

    Args:
        message: 要检查的消息字符串

    Returns:
        是否是 "na" 响应
    """
    return message == NA_RESPONSE
