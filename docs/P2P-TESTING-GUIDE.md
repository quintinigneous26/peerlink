# P2P 系统测试指南

## 📋 测试概览

本指南详细介绍如何测试 P2P 平台的各个组件。

## 🚀 快速开始

### 1. 环境准备

```bash
# 进入项目目录
cd /Users/liuhongbo/work/p2p-platform

# 安装测试依赖
pip install -e ".[dev]"

# 或者手动安装
pip install pytest pytest-asyncio pytest-cov pytest-timeout pytest-mock
```

### 2. 运行所有测试

```bash
# 方式1: 使用脚本
./scripts/run_tests.sh all

# 方式2: 直接使用 pytest
pytest tests/ -v
```

## 📁 测试结构

```
tests/
├── conftest.py                    # 共享 fixtures 和配置
├── unit/                          # 单元测试 (快速)
│   ├── test_stun.py              # STUN 协议测试
│   ├── test_signaling.py         # 信令服务器测试
│   └── test_did.py               # DID 服务测试
├── integration/                   # 集成测试 (中等速度)
│   ├── test_e2e_p2p.py           # 端到端 P2P 连接
│   ├── test_nat_penetration.py   # NAT 穿透测试
│   └── test_shangyun_compatibility.py  # 兼容性测试
└── stress/                        # 压力测试 (慢)
    ├── test_concurrent_connections.py  # 并发测试
    └── locustfile.py              # Locust 性能测试
```

## 🧪 测试类型详解

### 1. 单元测试 (Unit Tests)

测试独立组件的功能，不依赖外部服务。

```bash
# 运行所有单元测试
./scripts/run_tests.sh unit

# 或
pytest tests/unit/ -v

# 运行特定测试文件
pytest tests/unit/test_stun.py -v

# 运行特定测试用例
pytest tests/unit/test_stun.py::TestStunMessage::test_binding_request -v
```

**测试内容**:
| 文件 | 测试内容 |
|------|----------|
| `test_stun.py` | STUN 消息解析、创建、属性处理 |
| `test_signaling.py` | 信令消息格式、注册/注销、转发 |
| `test_did.py` | DID 生成/验证、密钥管理、认证 |

### 2. 集成测试 (Integration Tests)

测试多个组件的协作，需要启动依赖服务。

```bash
# 运行所有集成测试
./scripts/run_tests.sh integration

# 或
pytest tests/integration/ -v -m integration
```

**前置条件**:
```bash
# 启动依赖服务 (Docker)
docker-compose up -d redis

# 或本地安装 Redis
redis-server &
```

**测试内容**:
| 文件 | 测试内容 |
|------|----------|
| `test_e2e_p2p.py` | 完整的 P2P 连接流程 |
| `test_nat_penetration.py` | 各种 NAT 类型组合 |
| `test_shangyun_compatibility.py` | 与现有系统兼容性 |

### 3. NAT 穿透测试

专门测试 NAT 穿透能力。

```bash
# 运行 NAT 测试
./scripts/run_tests.sh nat

# 或
pytest tests/integration/test_nat_penetration.py -v -m nat
```

**测试场景**:
- Full Cone NAT → Full Cone NAT
- Symmetric NAT → Full Cone NAT
- 各种 NAT 组合的穿透成功率

### 4. 压力测试 (Stress Tests)

测试系统在高负载下的表现。

```bash
# 运行压力测试
./scripts/run_tests.sh stress

# 或
pytest tests/stress/ -v -m stress
```

**测试指标**:
- 并发连接数
- 消息吞吐量
- 内存使用
- 响应延迟

### 5. Locust 性能测试

使用 Locust 进行 HTTP API 性能测试。

```bash
# Web UI 模式 (推荐)
./scripts/run_tests.sh locust
# 浏览器打开 http://localhost:8089

# 无头模式 (CI/CD)
./scripts/run_tests.sh locust --headless -u 100 -r 10 -t 60s
```

**参数说明**:
- `-u 100`: 模拟 100 个用户
- `-r 10`: 每秒增加 10 个用户
- `-t 60s`: 持续 60 秒

## 🔧 测试配置

### pytest.ini 配置

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
```

### 常用命令行选项

```bash
# 显示详细输出
pytest -v tests/

# 显示 print 输出
pytest -s tests/

# 失败时停止
pytest -x tests/

# 只运行失败的测试
pytest --lf tests/

# 先运行失败的
pytest --ff tests/

# 超时设置 (秒)
pytest --timeout=60 tests/

# 并行运行 (需要 pytest-xdist)
pytest -n 4 tests/
```

## 📊 覆盖率报告

```bash
# 生成覆盖率报告
./scripts/run_tests.sh coverage

# 或
pytest tests/ --cov=client_sdk/src --cov=did-service/src --cov-report=html

# 查看 HTML 报告
open htmlcov/index.html
```

## 🐛 调试测试

### 使用 pdb 调试

```bash
# 失败时进入调试器
pytest --pdb tests/

# 在开始时进入调试器
pytest --trace tests/

# 在代码中设置断点
# import pdb; pdb.set_trace()
```

### 查看详细错误信息

```bash
# 显示完整堆栈
pytest -vv tests/

# 显示本地变量
pytest -l tests/
```

## 🧪 测试各组件

### 测试 DID 服务

```bash
# 启动 Redis (依赖)
docker-compose up -d redis

# 运行 DID 服务测试
pytest tests/unit/test_did.py -v

# 测试 API 端点 (需要启动服务)
curl -X POST http://localhost:9000/api/v1/did/generate \
  -H "Content-Type: application/json" \
  -d '{"device_type": "android", "capabilities": ["p2p"]}'
```

### 测试 STUN 服务

```bash
# 运行 STUN 测试
pytest tests/unit/test_stun.py -v

# 测试真实 STUN 服务器
python -c "
from client_sdk.src.p2p_client import P2PClient
client = P2PClient()
client.initialize()
nat_type = client.detect_nat()
print(f'NAT Type: {nat_type}')
"
```

### 测试信令服务

```bash
# 启动信令服务器
cd signaling-server && python -m signaling_server

# 运行测试
pytest tests/unit/test_signaling.py -v
```

### 测试客户端 SDK

```bash
# 运行 SDK 测试
pytest client_sdk/tests/ -v

# 测试 NAT 检测
pytest client_sdk/tests/test_nat_detection.py -v
```

## 🔄 CI/CD 集成

### GitHub Actions

测试在以下情况自动运行:
- Push 到 main 分支
- Pull Request 创建/更新

### 本地验证 CI

```bash
# 格式检查
black --check .
isort --check-only .

# Linting
flake8 .

# 类型检查
mypy src/

# 运行所有测试
./scripts/run_tests.sh all
```

## 📝 编写新测试

### 单元测试模板

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch

class TestMyFeature:
    """功能测试类"""

    def test_sync_function(self):
        """测试同步函数"""
        # Arrange
        input_data = "test"

        # Act
        result = my_function(input_data)

        # Assert
        assert result == expected

    @pytest.mark.asyncio
    async def test_async_function(self):
        """测试异步函数"""
        # Arrange
        mock_service = AsyncMock()
        mock_service.return_value = {"status": "ok"}

        # Act
        result = await mock_service()

        # Assert
        assert result["status"] == "ok"
```

### 集成测试模板

```python
import pytest
import asyncio

@pytest.mark.integration
@pytest.mark.asyncio
class TestIntegration:
    """集成测试类"""

    async def test_full_flow(self):
        """测试完整流程"""
        # 启动服务
        # 执行操作
        # 验证结果
        # 清理资源
        pass
```

## ⚠️ 常见问题

### 1. 测试超时

```bash
# 增加超时时间
pytest --timeout=300 tests/
```

### 2. Redis 连接失败

```bash
# 检查 Redis 是否运行
redis-cli ping

# 启动 Redis
docker-compose up -d redis
```

### 3. 端口被占用

```bash
# 查看端口占用
lsof -i :9000

# 杀死进程
kill -9 <PID>
```

### 4. 异步测试失败

```python
# 确保使用 pytest-asyncio
@pytest.mark.asyncio
async def test_async():
    result = await async_function()
    assert result is not None
```

## 📈 性能基准

| 指标 | 目标值 |
|------|--------|
| 单元测试运行时间 | < 30秒 |
| 集成测试运行时间 | < 5分钟 |
| 测试覆盖率 | >= 80% |
| 并发连接数 | >= 1000 |
| 消息延迟 | < 100ms |

## 🔗 相关文档

- [开发规范](./development-guide.md)
- [API 规范](./api-spec.md)
- [架构文档](./architecture.md)
