# 测试文档

## 测试概述

本项目包含完整的测试套件，涵盖单元测试、集成测试、NAT穿透测试和压力测试。

## 测试结构

```
tests/
├── conftest.py              # pytest配置和共享fixtures
├── unit/                    # 单元测试
│   ├── test_stun.py         # STUN服务器测试
│   ├── test_signaling.py    # 信令服务器测试
│   └── test_did.py          # DID服务测试
├── integration/             # 集成测试
│   ├── test_e2e_p2p.py      # 端到端P2P连接测试
│   └── test_nat_penetration.py  # NAT穿透测试
└── stress/                  # 压力测试
    ├── test_concurrent_connections.py  # 并发连接测试
    └── locustfile.py        # Locust压力测试脚本
```

## 运行测试

### 运行所有测试

```bash
./scripts/run_tests.sh all
```

### 运行单元测试

```bash
./scripts/run_tests.sh unit
```

### 运行集成测试

```bash
./scripts/run_tests.sh integration
```

### 运行NAT穿透测试

```bash
./scripts/run_tests.sh nat
```

### 运行压力测试

```bash
./scripts/run_tests.sh stress
```

### 运行Locust压力测试

```bash
# 交互模式 (Web UI)
./scripts/run_tests.sh locust

# 无头模式 (命令行)
./scripts/run_tests.sh locust --headless -u 100 -r 10 -t 60s
```

### 快速测试 (开发时使用)

```bash
./scripts/run_tests.sh quick
```

## 测试标记

使用pytest标记来分类测试:

- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.stress` - 压力测试
- `@pytest.mark.nat` - NAT穿透测试
- `@pytest.mark.slow` - 慢速测试

### 运行特定标记的测试

```bash
# 只运行单元测试
pytest -m unit

# 运行除压力测试外的所有测试
pytest -m "not stress"

# 运行集成测试或NAT测试
pytest -m "integration or nat"
```

## 代码覆盖率

### 生成覆盖率报告

```bash
./scripts/run_tests.sh coverage
```

报告生成在:
- HTML: `htmlcov/index.html`
- XML: `coverage.xml`
- 终端: 直接输出

### 查看覆盖率

```bash
# 在浏览器中查看HTML报告
open htmlcov/index.html
```

## CI/CD

GitHub Actions工作流在以下情况自动运行:
- Push到main或develop分支
- 创建Pull Request
- 手动触发 (workflow_dispatch)

### CI工作流

1. **代码质量检查** (lint)
   - Black格式检查
   - isort导入排序检查
   - Flake8 linting
   - Mypy类型检查

2. **单元测试** (test-unit)
   - 运行所有单元测试
   - 生成覆盖率报告

3. **集成测试** (test-integration)
   - 运行集成测试
   - 包含端到端测试

4. **NAT穿透测试** (test-nat)
   - 各种NAT组合测试
   - 打洞技术验证

5. **压力测试** (test-stress)
   - 并发连接测试
   - 性能基准测试

6. **安全扫描** (security-scan)
   - Bandit安全检查
   - Safety依赖检查

7. **构建测试** (build)
   - 包构建验证

## 测试用例

### 单元测试

#### STUN服务器测试 (`test_stun.py`)
- 消息解析
- 消息创建
- NAT类型检测
- 属性处理

#### 信令服务器测试 (`test_signaling.py`)
- 消息格式
- 客户端注册/注销
- 消息转发
- WebSocket连接
- 房间管理

#### DID服务测试 (`test_did.py`)
- DID生成和验证
- 密钥管理
- 设备注册
- 认证流程

### 集成测试

#### 端到端测试 (`test_e2e_p2p.py`)
- 完整P2P握手
- 直接连接
- Relay降级
- 数据传输
- 多方连接

#### NAT穿透测试 (`test_nat_penetration.py`)
- 各种NAT组合
- ICE协商
- 打洞技术
- Relay降级

### 压力测试

#### 并发连接 (`test_concurrent_connections.py`)
- 小/中/大规模并发
- 持续连接
- 连接更替
- 内存使用

#### Locust测试 (`locustfile.py`)
- 模拟真实用户行为
- 可配置用户数和请求速率
- 实时性能监控

## 测试最佳实践

1. **隔离性**: 每个测试应该独立运行
2. **确定性**: 避免随机性，使用固定种子
3. **快速**: 单元测试应该快速执行
4. **清晰**: 使用描述性的测试名称
5. **覆盖率**: 目标80%以上的代码覆盖率

## 添加新测试

### 创建新测试文件

```bash
# 单元测试
touch tests/unit/test_new_feature.py

# 集成测试
touch tests/integration/test_new_integration.py
```

### 测试模板

```python
"""
新功能测试
"""
import pytest
from unittest.mock import AsyncMock


class TestNewFeature:
    """新功能测试类"""

    @pytest.mark.asyncio
    async def test_basic_functionality(self):
        """测试基本功能"""
        # Arrange
        mock_service = AsyncMock()
        mock_service.return_value = {"status": "ok"}

        # Act
        result = await mock_service()

        # Assert
        assert result["status"] == "ok"

    @pytest.mark.integration
    async def test_integration_scenario(self):
        """测试集成场景"""
        # 测试代码
        pass
```

## 调试测试

### 使用pdb调试

```bash
# 在失败时进入调试器
pytest --pdb

# 在开始时进入调试器
pytest --trace
```

### 只运行失败的测试

```bash
# 第一次运行
pytest

# 之后只运行失败的
pytest --lf

# 先运行失败的，然后运行其他
pytest --ff
```

### 详细输出

```bash
# 显示print输出
pytest -s

# 显示详细跟踪信息
pytest -vv

# 显示本地变量
pytest -l
```

## 持续集成

测试在GitHub Actions上自动运行。状态显示在:
- Pull Request检查
- Actions标签页

### 本地验证CI

在推送前，可以本地运行相同的检查:

```bash
# 运行格式检查
black --check .
isort --check-only .

# 运行linting
flake8 .

# 运行所有测试
./scripts/run_tests.sh all
```
