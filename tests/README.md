# 测试框架文档

## 概述

p2p-platform 测试框架包含三个主要测试类型：

1. **性能基准测试** (`tests/benchmark/`) - 测试协议性能指标
2. **模糊测试** (`tests/fuzz/`) - 使用 hypothesis 进行属性测试
3. **压力测试** (`tests/stress/`) - 使用 locust 进行负载测试

## 目录结构

```
tests/
├── benchmark/              # 性能基准测试
│   ├── __init__.py
│   ├── test_latency.py     # 延迟测试
│   ├── test_throughput.py  # 吞吐量测试
│   ├── test_concurrent.py  # 并发连接测试
│   └── utils.py            # 性能测试工具
├── fuzz/                   # 模糊测试
│   ├── __init__.py
│   ├── fuzz_multistream.py # Multiselect 协议
│   ├── fuzz_noise.py       # Noise 协议
│   ├── fuzz_yamux.py       # Yamux 协议
│   └── utils.py            # 模糊测试工具
├── stress/                 # 压力测试
│   └── locustfile.py       # Locust 负载测试
├── interop/                # 互操作性测试
├── integration/            # 集成测试
├── unit/                   # 单元测试
├── conftest.py             # pytest 配置
├── requirements.txt        # 测试依赖
├── run_benchmarks.sh       # 性能测试脚本
├── run_fuzz_tests.sh       # 模糊测试脚本
└── run_locust.sh           # 负载测试脚本
```

## 安装依赖

```bash
pip install -r tests/requirements.txt
```

## 性能基准测试

### 测试内容

- **延迟测试**: TCP/QUIC/WebRTC 连接延迟
- **吞吐量测试**: 数据传输速率
- **并发测试**: 并发连接能力和资源使用

### 运行方式

```bash
# 运行所有性能测试
./tests/run_benchmarks.sh

# 或单独运行
pytest tests/benchmark/test_latency.py -v
pytest tests/benchmark/test_throughput.py -v
pytest tests/benchmark/test_concurrent.py -v
```

### 性能目标

| 测试项 | 目标值 | 说明 |
|--------|--------|------|
| 本地 TCP 延迟 p50 | < 1ms | localhost 连接 |
| 本地 TCP 延迟 p95 | < 2ms | 95 分位 |
| 本地 TCP 吞吐量 | > 500 Mbps | 本地回环 |
| 并发连接数 | > 1000 | 内存 < 1GB |

## 模糊测试

### 测试内容

- **协议解析**: 测试各种边界输入
- **安全性**: 检测缓冲区溢出、注入攻击
- **并发**: 多线程/协程安全性

### 运行方式

```bash
# 运行所有模糊测试
./tests/run_fuzz_tests.sh

# 或单独运行
pytest tests/fuzz/fuzz_multistream.py -v
pytest tests/fuzz/fuzz_noise.py -v
pytest tests/fuzz/fuzz_yamux.py -v
```

### Hypothesis 配置

```python
from tests.fuzz.utils import FuzzSettings

# 快速测试（开发时）
@settings(FuzzSettings.fast())

# 标准测试
@settings(FuzzSettings.standard())

# 彻底测试（CI/发布前）
@settings(FuzzSettings.thorough())

# 安全测试
@settings(FuzzSettings.security())
```

## 压力测试

### 运行方式

```bash
# 启动 Locust Web UI
./tests/run_locust.sh

# 然后访问 http://localhost:8089
```

### 无头模式

```bash
locust -f tests/stress/locustfile.py \
    --host=http://localhost:8080 \
    --headless \
    -u 100 \
    -r 10 \
    -t 60s
```

## 互操作性测试

互操作性测试用于验证与其他 libp2p 实现的兼容性：

- go-libp2p (Go 实现)
- js-libp2p (JavaScript 实现)
- rust-libp2p (Rust 实现)

## 测试报告

测试报告保存在 `tests/reports/` 目录：

```
tests/reports/
├── performance/           # 性能测试报告
│   ├── latency.html
│   ├── throughput.html
│   └── concurrent.html
├── fuzz/                  # 模糊测试报告
│   ├── multistream.html
│   ├── noise.html
│   └── yamux.html
└── locust/                # 负载测试报告
    └── *.html
```

## CI 集成

```yaml
# .github/workflows/test.yml
- name: Run performance tests
  run: ./tests/run_benchmarks.sh

- name: Run fuzz tests
  run: ./tests/run_fuzz_tests.sh
```

## 贡献指南

### 添加新的性能测试

1. 在 `tests/benchmark/` 创建新文件
2. 继承测试基类或使用工具函数
3. 添加性能目标和验证逻辑
4. 运行并验证结果

### 添加新的模糊测试

1. 在 `tests/fuzz/` 创建新文件
2. 定义输入策略 (`st.*`)
3. 使用 `@given` 装饰器编写测试
4. 添加边界条件和安全测试

## 故障排除

### 性能测试失败

- 检查系统负载：`top` 或 `htop`
- 关闭其他占用资源的程序
- 检查防火墙设置

### 模糊测试超时

- 使用 `FuzzSettings.fast()` 减少测试用例
- 增加 deadline 值
- 使用 `@timeout` 装饰器

### Locust 连接失败

- 确保目标服务器正在运行
- 检查防火墙设置
- 验证 host 参数正确
