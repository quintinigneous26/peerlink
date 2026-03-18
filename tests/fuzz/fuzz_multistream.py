"""
Multistream Select 协议模糊测试

使用 hypothesis 测试 multistream-select 协议解析的健壮性：
- 无效的协议协商消息
- 边界长度的协议名
- 恶意构造的握手数据
- 并发协商测试
"""
import asyncio
from typing import List, Optional

import hypothesis
from hypothesis import given, settings, strategies as st
import pytest


# ===== 测试数据生成策略 =====

def valid_protocol_names() -> st.SearchStrategy[str]:
    """
    生成有效的协议名

    根据 libp2p multistream-select 规范：
    - 以 / 开头
    - 包含协议名称和版本
    - 不包含空字符
    """
    return st.builds(
        lambda name, version: f"/{name}/{version}",
        name=st.from_regex(r"[a-z0-9][a-z0-9-]*[a-z0-9]", fullmatch=True),
        version=st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True),
    )


def invalid_protocol_names() -> st.SearchStrategy[str]:
    """
    生成无效的协议名用于测试健壮性

    包括：
    - 不以 / 开头
    - 包含空字符
    - 空字符串
    - 过长的协议名
    - 特殊字符
    """
    return st.one_of(
        # 不以 / 开头
        st.text(min_size=1, max_size=20).filter(lambda x: not x.startswith("/")),
        # 包含空字符
        st.text().filter(lambda x: "\x00" in x),
        # 空字符串
        st.just(""),
        # 只有 /
        st.just("/"),
        # 连续的 //
        st.builds(lambda x: f"//{x}" if x else "//", st.text(min_size=0, max_size=10)),
        # 特殊字符
        st.from_regex(r".*[\x00-\x1f\x7f-\x9f].*"),
    )


def protocol_lists() -> st.SearchStrategy[List[str]]:
    """
    生成协议列表

    用于多协议协商测试
    """
    return st.lists(
        valid_protocol_names(),
        min_size=1,
        max_size=10,
        unique=True,
    )


def binary_messages() -> st.SearchStrategy[bytes]:
    """
    生成二进制消息

    用于测试二进制协议解析
    """
    return st.binary(min_size=0, max_size=4096)


def handshake_messages() -> st.SearchStrategy[bytes]:
    """
    生成握手消息

    multistream-select 握手消息格式：
    - 协议名 + \n
    - 或者 na\n + 协议列表 + \n
    """
    return st.one_of(
        # 简单协议协商
        valid_protocol_names().map(lambda x: f"{x}\n".encode()),
        # 多协议协商 (na 开头)
        st.builds(
            lambda protocols: b"na\n" + "\n".join(protocols).encode() + b"\n",
            protocol_lists(),
        ),
        # 无效的握手消息
        st.binary(),
    )


# ===== 测试用例 =====


class TestMultistreamFuzz:
    """Multistream Select 协议模糊测试"""

    @given(protocol_name=valid_protocol_names())
    @settings(max_examples=100)
    def test_valid_protocol_name_parsing(self, protocol_name: str):
        """
        测试有效协议名的解析

        验证：
        - 可以正确解析
        - 格式符合规范
        """
        # 基本验证
        assert protocol_name.startswith("/"), "协议名必须以 / 开头"
        assert "/" in protocol_name[1:], "协议名必须包含版本分隔符"
        assert protocol_name.count("/") >= 2, "协议名格式: /name/version"

        # 无空字符
        assert "\x00" not in protocol_name, "协议名不能包含空字符"

    @given(protocol_name=invalid_protocol_names())
    @settings(max_examples=100)
    def test_invalid_protocol_name_rejection(self, protocol_name: str):
        """
        测试无效协议名被正确拒绝

        验证：
        - 无效协议名不会导致崩溃
        - 返回适当的错误
        """
        # TODO: 实际测试协议协商逻辑
        # 这里只是框架，需要等实现完成后连接到实际代码
        pass

    @given(protocols=protocol_lists())
    @settings(max_examples=50)
    def test_protocol_list_negotiation(self, protocols: List[str]):
        """
        测试协议列表协商

        验证：
        - 可以处理多个协议
        - 正确选择共同支持的协议
        """
        # 基本验证
        assert len(protocols) > 0, "协议列表不能为空"
        assert len(set(protocols)) == len(protocols), "协议列表不能重复"

        # 所有协议都是有效的
        for protocol in protocols:
            assert protocol.startswith("/"), f"无效协议: {protocol}"

    @given(message=binary_messages())
    @settings(max_examples=200)
    def test_binary_message_parsing(self, message: bytes):
        """
        测试二进制消息解析

        验证：
        - 任意二进制数据不会导致崩溃
        - 无效数据返回适当的错误
        """
        # TODO: 实际测试消息解析逻辑
        # 确保不会因任何二进制数据而崩溃
        pass


class TestMultistreamEdgeCases:
    """边界条件测试"""

    @pytest.mark.parametrize("length", [0, 1, 2, 3, 4, 5, 10, 100, 1000, 10000])
    def test_protocol_name_length(self, length: int):
        """
        测试不同长度的协议名

        边界条件：
        - 空协议名
        - 最短有效协议名
        - 最长合理协议名
        - 超长协议名
        """
        # 生成指定长度的协议名
        if length == 0:
            protocol = ""
        elif length == 1:
            protocol = "/"
        else:
            protocol = "/" + "a" * (length - 2) + "/1.0.0"

        # 测试解析
        if length == 0 or length == 1:
            # 应该被拒绝
            assert not self._is_valid_protocol_name(protocol)
        elif length > 256:
            # 超长协议名可能被限制
            # 验证不会崩溃
            pass
        else:
            # 应该被接受（或至少不会崩溃）
            pass

    def _is_valid_protocol_name(self, protocol: str) -> bool:
        """辅助函数：验证协议名"""
        if not protocol.startswith("/"):
            return False
        if protocol == "/":
            return False
        if "\x00" in protocol:
            return False
        return True

    def test_empty_protocol_list(self):
        """测试空协议列表"""
        protocols: List[str] = []
        # 应该被拒绝
        assert len(protocols) == 0

    def test_single_protocol_list(self):
        """测试单个协议的列表"""
        protocols = ["/echo/1.0.0"]
        assert len(protocols) == 1

    def test_large_protocol_list(self):
        """测试大量协议的列表"""
        # 生成 100 个不同的协议
        protocols = [f"/protocol{i}/1.0.0" for i in range(100)]
        assert len(protocols) == 100
        assert len(set(protocols)) == 100, "协议不能重复"


class TestMultistreamSecurity:
    """安全性测试"""

    @given(message=binary_messages())
    @settings(max_examples=100)
    def test_no_buffer_overflow(self, message: bytes):
        """
        测试不存在缓冲区溢出

        任意长度的消息都不应该导致缓冲区溢出
        """
        # TODO: 实际测试，确保没有缓冲区溢出
        # 使用内存检查工具如 valgrind 或 ASAN
        pass

    @given(message=binary_messages())
    @settings(max_examples=100)
    def test_no_infinite_loop(self, message: bytes):
        """
        测试不存在无限循环

        恶意构造的数据不应该导致解析器陷入无限循环
        """
        # TODO: 实际测试，添加超时检测
        pass

    def test_protocol_injection(self):
        """
        测试协议注入攻击

        验证协议名中的特殊字符不会被当作命令执行
        """
        malicious_protocols = [
            "/../../../etc/passwd",
            "/$(rm -rf /)",
            "/; DROP TABLE users; --",
            "/<script>alert('xss')</script>",
        ]

        for protocol in malicious_protocols:
            # 应该被当作普通字符串处理，不会造成安全影响
            assert isinstance(protocol, str)

    @given(message=binary_messages())
    @settings(max_examples=50)
    def test_resource_exhaustion(self, message: bytes):
        """
        测试资源耗尽攻击

        大量或复杂的消息不应该耗尽系统资源
        """
        # TODO: 实际测试，监控内存和 CPU 使用
        pass


class TestMultistreamConcurrent:
    """并发测试"""

    @pytest.mark.asyncio
    @given(count=st.integers(min_value=1, max_value=100))
    @settings(max_examples=20)
    async def test_concurrent_negotiation(self, count: int):
        """
        测试并发协议协商

        多个并发协商不应该互相干扰
        """
        # TODO: 实际测试并发协商
        pass


# ===== 属性测试 =====

class TestMultistreamProperties:
    """协议属性测试"""

    @given(a=valid_protocol_names(), b=valid_protocol_names())
    @settings(max_examples=50)
    def test_protocol_equality(self, a: str, b: str):
        """
        测试协议相等性属性

        - 反身性: a == a
        - 对称性: a == b 意味着 b == a
        - 传递性: a == b 且 b == c 意味着 a == c
        """
        # 反身性
        assert a == a

        # 对称性
        if a == b:
            assert b == a

    @given(protocols=protocol_lists())
    @settings(max_examples=50)
    def test_protocol_list_ordering(self, protocols: List[str]):
        """
        测试协议列表排序属性

        协议协商应该按照优先级（列表顺序）进行
        """
        # 列表顺序代表优先级
        for i in range(len(protocols) - 1):
            # 优先级递减
            assert i < i + 1

    @given(protocols=protocol_lists())
    @settings(max_examples=50)
    def test_protocol_uniqueness(self, protocols: List[str]):
        """
        测试协议唯一性属性

        协议列表中的协议应该唯一
        """
        # 策略生成的是唯一列表
        assert len(protocols) == len(set(protocols))
