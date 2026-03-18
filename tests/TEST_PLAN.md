# P2P Platform 测试方案

## 测试工程师: tester-1
## 创建日期: 2026-03-06
## 对标目标: go-libp2p

---

## 1. 测试目标

### 1.1 总体目标

| 类别 | 目标值 | 当前值 | 状态 |
|------|--------|--------|------|
| 单元测试覆盖率 | >85% | ~80% | 🔄 进行中 |
| 集成测试覆盖 | 核心流程 100% | ~90% | 🔄 进行中 |
| 性能达标率 | >90% vs go-libp2p | 待测 | ⏳ 待验证 |
| 互操作性 | 与 go-libp2p 兼容 | 待测 | ⏳ 待验证 |

### 1.2 性能基准目标

基于 go-libp2p 性能指标：

| 指标 | go-libp2p | 目标 (90%) | 备注 |
|------|-----------|------------|------|
| 连接建立延迟 | ~20ms | <22ms | TCP 直连 |
| 流创建延迟 | ~1ms | <1.1ms | Yamux |
| 消息往返延迟 | ~0.5ms | <0.55ms | 本地 |
| 单流吞吐量 | ~500 Mbps | >450 Mbps | TCP |
| 并发连接数 | 10,000+ | 1,000+ | 最低要求 |

---

## 2. 测试框架设计

### 2.1 测试分层架构

```
tests/
├── unit/              # 单元测试 (85%+ 覆盖率)
│   ├── test_*.py
│   └── p2p_engine/*/test_*.py
├── integration/       # 集成测试 (核心流程)
│   ├── test_e2e_p2p.py
│   ├── test_dht_integration.py
│   └── test_transport_integration.py
├── benchmark/         # 性能基准测试
│   ├── test_latency.py      # 延迟测试
│   ├── test_throughput.py   # 吞吐量测试
│   └── test_concurrent.py   # 并发测试
├── interop/           # 互操作测试
│   ├── test_golibp2p.py     # 与 go-libp2p 互操作
│   └── test_jslibp2p.py     # 与 js-libp2p 互操作
├── fuzz/              # 模糊测试
│   ├── fuzz_noise.py
│   └── fuzz_yamux.py
└── stress/            # 压力测试
    └── locustfile.py
```

### 2.2 测试工具链

| 工具 | 用途 | 版本 |
|------|------|------|
| pytest | 测试框架 | 9.0.1 |
| pytest-asyncio | 异步测试 | 0.23+ |
| pytest-cov | 覆盖率 | 4.1+ |
| pytest-benchmark | 性能基准 | 4.0+ |
| hypothesis | 模糊测试 | 6.100+ |
| locust | 压力测试 | 24.0+ |

---

## 3. 单元测试计划

### 3.1 当前状态分析

```
当前覆盖率: ~80%
目标覆盖率: >85%
缺口: 需补充 ~5% 的测试用例
```

### 3.2 需要补充的测试

#### 3.2.1 核心模块测试

| 模块 | 当前覆盖 | 目标 | 缺口 |
|------|----------|------|------|
| p2p_engine/engine.py | 70% | 90% | 边界条件 |
| p2p_engine/event.py | 75% | 90% | 错误处理 |
| p2p_engine/muxer/ | 80% | 95% | 并发场景 |
| p2p_engine/protocol/ | 85% | 95% | 协议异常 |

#### 3.2.2 新增测试用例

```python
# 1. engine.py 边界条件测试
def test_engine_initialization_with_invalid_config()
def test_engine_shutdown_with_active_connections()
def test_engine_reconnection_handling()
def test_engine_concurrent_transport_operations()

# 2. event.py 错误处理测试
def test_event_bus_dispatch_with_exception()
def test_event_subscription_during_dispatch()
def test_event_handler_ordering()

# 3. muxer/ 并发场景测试
def test_yamux_concurrent_stream_creation()
def test_yamux_stream_close_during_write()
def test_mplex_frame_reordering()

# 4. protocol/ 协议异常测试
def test_noise_handshake_timeout()
def test_noise_invalid_message_format()
def test_identify_overflow_handling()
```

---

## 4. 集成测试计划

### 4.1 核心流程测试

#### 4.1.1 P2P 连接建立流程

```python
async def test_complete_p2p_handshake():
    """
    测试完整的 P2P 握手流程:
    1. 传输层连接
    2. Multistream Select 协议协商
    3. Noise 加密握手
    4. Identify 协议交换
    5. Yamux 流复用初始化
    """
    # Setup: 创建两个节点
    node_a = await create_test_node()
    node_b = await create_test_node()

    # Execute: 完整握手
    conn = await node_a.dial_peer(node_b.peer_id)

    # Verify: 验证各层协议
    assert conn.secure.is_authenticated
    assert conn.muxer.is_active
    assert conn.remote_peer_id == node_a.peer_id
```

#### 4.1.2 DHT 集成流程

```python
async def test_dht_provider_discovery():
    """
    测试 DHT 提供者发现流程:
    1. 节点 A 提供服务
    2. 节点 B 查询服务
    3. DHT 路由传播
    4. 连接建立
    """
```

### 4.2 边界条件测试

| 测试场景 | 描述 | 预期结果 |
|----------|------|----------|
| 网络中断恢复 | 连接期间网络中断后恢复 | 自动重连 |
| 同时连接尝试 | 同时向同一对等方发起多个连接 | 只保留一个连接 |
| 最大连接数 | 达到最大连接数限制 | 拒绝新连接或驱逐旧连接 |
| 大消息传输 | 传输超大消息 (>16MB) | 分片传输成功 |

---

## 5. 性能基准测试

### 5.1 延迟测试

#### 5.1.1 连接建立延迟

```python
@pytest.mark.benchmark
async def test_connection_latency_local():
    """本地 TCP 连接延迟"""
    target_p95 = 1.1  # ms (90% of go-libp2p)

    latencies = []
    for _ in range(1000):
        start = time.perf_counter()
        conn = await establish_connection()
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)
        await conn.close()

    p95 = np.percentile(latencies, 95)
    assert p95 < target_p95, f"P95 延迟 {p95}ms 超过目标"
```

#### 5.1.2 流操作延迟

```python
@pytest.mark.benchmark
async def test_stream_creation_latency():
    """流创建延迟"""
    target_p50 = 1.1  # ms

    for _ in range(1000):
        start = time.perf_counter()
        stream = await conn.open_stream()
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)

    p50 = np.median(latencies)
    assert p50 < target_p50
```

#### 5.1.3 消息往返延迟

```python
@pytest.mark.benchmark
async def test_message_rtt_latency():
    """消息往返延迟"""
    target_p95 = 0.55  # ms

    for _ in range(1000):
        start = time.perf_counter()
        await stream.write(b"ping")
        response = await stream.read(4)
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)

    p95 = np.percentile(latencies, 95)
    assert p95 < target_p95
```

### 5.2 吞吐量测试

#### 5.2.1 单流吞吐量

```python
@pytest.mark.benchmark
async def test_single_stream_throughput():
    """单流吞吐量测试"""
    target_throughput = 450  # Mbps (90% of go-libp2p)

    duration_sec = 10
    data_size = 1024 * 1024  # 1MB chunks

    start_time = time.time()
    total_bytes = 0

    while time.time() - start_time < duration_sec:
        await stream.write(bytes(data_size))
        total_bytes += data_size

    throughput_mbps = (total_bytes * 8) / (duration_sec * 1_000_000)
    assert throughput_mbps > target_throughput
```

#### 5.2.2 多流并发吞吐量

```python
@pytest.mark.benchmark
async def test_multi_stream_throughput():
    """多流并发吞吐量测试"""
    num_streams = 100
    target_aggregate = 400  # Mbps

    streams = [await conn.open_stream() for _ in range(num_streams)]

    async def pump_data(stream):
        while True:
            await stream.write(bytes(1024 * 1024))

    await asyncio.gather(*[pump_data(s) for s in streams])
```

### 5.3 并发测试

#### 5.3.1 并发连接数

```python
@pytest.mark.benchmark
async def test_max_concurrent_connections():
    """最大并发连接测试"""
    target_connections = 1000

    connections = []
    for i in range(target_connections):
        conn = await establish_connection()
        connections.append(conn)

    # 验证所有连接都活跃
    for conn in connections:
        assert conn.is_active

    # 验证内存使用
    memory_mb = get_memory_usage()
    per_connection_mb = memory_mb / target_connections
    assert per_connection_mb < 0.5  # 每连接 < 0.5MB
```

#### 5.3.2 并发流数

```python
@pytest.mark.benchmark
async def test_max_concurrent_streams():
    """最大并发流测试"""
    target_streams = 1000

    streams = []
    for i in range(target_streams):
        stream = await conn.open_stream()
        streams.append(stream)

    # 验证所有流都可写
    for stream in streams:
        await stream.write(b"ping")
```

---

## 6. 互操作测试

### 6.1 与 go-libp2p 互操作

```python
@pytest.mark.interop
async def test_golibp2p_handshake():
    """
    测试与 go-libp2p 节点的握手:
    1. 启动 go-libp2p 节点
    2. Python 节点连接
    3. 验证协议兼容性
    """
    # Setup: 启动 go-libp2p 节点
    go_node = await start_golibp2p_node()

    # Execute: Python 节点连接
    py_conn = await py_node.dial_peer(go_node.peer_id)

    # Verify: 验证连接成功
    assert py_conn.is_active
    assert py_conn.remote_agent_version.startswith("go-libp2p")
```

### 6.2 协议兼容性矩阵

| 协议 | go-libp2p | js-libp2p | rust-libp2p |
|------|-----------|-----------|-------------|
| Multistream Select | ✅ | ✅ | ✅ |
| Noise XX | ✅ | ✅ | ✅ |
| Yamux | ✅ | ✅ | ✅ |
| mplex | ✅ | ✅ | ✅ |
| Identify | ✅ | ✅ | ✅ |
| Ping | ✅ | ✅ | ✅ |
| Kademlia DHT | ✅ | ✅ | ✅ |

---

## 7. 测试执行计划

### 7.1 测试执行顺序

```bash
# 1. 单元测试 (快速反馈)
pytest tests/unit/ -v --cov=p2p_engine --cov-report=term-missing

# 2. 集成测试 (功能验证)
pytest tests/integration/ -v -m "not slow"

# 3. 性能基准测试 (性能验证)
pytest tests/benchmark/ -v -m benchmark

# 4. 互操作测试 (兼容性验证)
pytest tests/interop/ -v -m interop

# 5. 模糊测试 (安全性验证)
pytest tests/fuzz/ -v

# 6. 压力测试 (稳定性验证)
locust -f tests/stress/locustfile.py --headless -u 1000 -t 60s
```

### 7.2 CI/CD 集成

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.11, 3.12]

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -r tests/requirements.txt

      - name: Run unit tests
        run: pytest tests/unit/ --cov=p2p_engine

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Run performance tests
        run: pytest tests/benchmark/ -v -m benchmark

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 8. 质量报告

### 8.1 测试覆盖率报告

```bash
# 生成覆盖率报告
pytest --cov=p2p_engine --cov-report=html --cov-report=term

# 报告输出
tests/reports/coverage/index.html
tests/reports/coverage/term.txt
```

### 8.2 性能基准报告

```bash
# 生成性能报告
pytest tests/benchmark/ -v --benchmark-json=benchmark.json

# 报告输出
tests/reports/performance/benchmark.json
tests/reports/performance/summary.md
```

### 8.3 回归测试报告

```bash
# 对比历史数据
pytest-benchmark compare --benchmark1=baseline.json --benchmark2=current.json

# 报告输出
tests/reports/regression/comparison.md
```

---

## 9. 测试验收标准

### 9.1 功能验收

- [ ] 单元测试覆盖率 >85%
- [ ] 集成测试通过率 >95%
- [ ] 核心流程 100% 覆盖

### 9.2 性能验收

- [ ] 连接延迟 <22ms (P95)
- [ ] 流延迟 <1.1ms (P50)
- [ ] 吞吐量 >450 Mbps
- [ ] 并发连接 >1000

### 9.3 质量验收

- [ ] 无 P0/P1 级别 bug
- [ ] 代码质量评分 >8.0
- [ ] 文档完整性 >90%

---

## 10. 下一步行动

### 10.1 立即执行 (P0)

1. 补充单元测试达到 85% 覆盖率
2. 完善核心流程集成测试
3. 建立性能基准测试

### 10.2 短期执行 (P1)

1. 实现互操作测试框架
2. 完善压力测试场景
3. 集成 CI/CD 自动化

### 10.3 长期执行 (P2)

1. 建立性能回归监控
2. 完善模糊测试覆盖
3. 建立性能优化反馈循环

---

*文档版本: 1.0*
*创建者: tester-1*
*最后更新: 2026-03-06*
