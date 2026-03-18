# P2P Engine 事件系统统一

## 概述

将 P2PEngine 的双事件系统统一为单一的 EventBus 架构，提升代码一致性和可维护性。

## 问题描述

之前 P2PEngine 使用简单的回调机制（`_on_state_change` 和 `_on_error`），而项目中已经有完善的 EventBus 系统。这导致：

1. 两套独立的事件机制并存
2. 代码不一致，难以维护
3. 无法利用 EventBus 的高级特性（过滤、异步处理、指标收集等）

## 解决方案

### 1. 集成 EventBus

P2PEngine 现在支持两种方式使用 EventBus：

```python
# 方式 1: 自动创建 EventBus（推荐）
engine = P2PEngine()
# engine.event_bus 自动创建并管理

# 方式 2: 使用共享 EventBus
shared_bus = EventBus()
await shared_bus.start()
engine = P2PEngine(event_bus=shared_bus)
```

### 2. 统一事件发布

所有状态变化和错误现在通过 EventBus 发布：

```python
# 状态变化事件
await engine._set_state(ConnectionState.CONNECTED)
# 自动发布 CONNECTION_STATE_CHANGED 事件

# 错误事件
await engine._emit_error(error, context="connection")
# 自动发布 ERROR_OCCURRED 事件
```

### 3. 向后兼容

保留了旧的回调 API，确保现有代码无需修改：

```python
# 旧 API 仍然有效
async def on_state_change(old_state, new_state):
    print(f"State: {old_state} -> {new_state}")

engine = P2PEngine(on_state_change=on_state_change)
```

## 使用示例

### 订阅状态变化事件

```python
from p2p_engine.event import EventTopic, P2PEventType

engine = P2PEngine()

async def on_connection_event(event):
    if event.event_type == P2PEventType.CONNECTION_STATE_CHANGED:
        print(f"State changed: {event.data['old_state']} -> {event.data['new_state']}")

# 订阅连接事件
engine.event_bus.subscribe(EventTopic.CONNECTION, on_connection_event)

await engine.event_bus.start()
await engine.initialize()
```

### 订阅错误事件

```python
async def on_error_event(event):
    print(f"Error: {event.data['error_message']}")
    print(f"Context: {event.data.get('context', 'N/A')}")

engine.event_bus.subscribe(EventTopic.ERROR, on_error_event)
```

### 使用事件过滤

```python
# 只订阅特定对端的事件
engine.event_bus.subscribe(
    EventTopic.CONNECTION,
    handler,
    filter_peer="peer-123"
)

# 只订阅特定类型的事件
engine.event_bus.subscribe(
    EventTopic.CONNECTION,
    handler,
    filter_types={P2PEventType.PEER_CONNECTED, P2PEventType.PEER_DISCONNECTED}
)
```

## 技术细节

### EventBus 生命周期管理

- 如果 P2PEngine 创建了 EventBus（`_owns_event_bus=True`），则负责启动和停止
- 如果使用共享 EventBus（`_owns_event_bus=False`），则不会停止它

```python
# 自动管理
engine = P2PEngine()
await engine.initialize()  # 启动 EventBus
await engine.disconnect()  # 停止 EventBus

# 共享 EventBus
bus = EventBus()
await bus.start()
engine = P2PEngine(event_bus=bus)
await engine.disconnect()  # 不会停止 bus
await bus.stop()  # 手动停止
```

### 事件数据结构

状态变化事件：
```python
{
    "topic": EventTopic.CONNECTION,
    "event_type": P2PEventType.CONNECTION_STATE_CHANGED,
    "data": {
        "old_state": "idle",
        "new_state": "detecting",
        "peer_id": "peer-123"
    },
    "timestamp": 1234567890.123,
    "source": "P2PEngine"
}
```

错误事件：
```python
{
    "topic": EventTopic.ERROR,
    "event_type": P2PEventType.ERROR_OCCURRED,
    "data": {
        "error_type": "RuntimeError",
        "error_message": "Connection failed",
        "context": "punch_attempt"
    },
    "timestamp": 1234567890.123,
    "source": "P2PEngine"
}
```

## 测试覆盖

新增测试文件：`tests/unit/test_engine_eventbus_integration.py`

测试覆盖：
- ✅ EventBus 自动创建
- ✅ 共享 EventBus 使用
- ✅ 状态变化事件发布
- ✅ 错误事件发布
- ✅ 向后兼容性（回调 API）
- ✅ EventBus 生命周期管理
- ✅ 共享 EventBus 不被停止

所有测试通过：7/7 ✅

## 迁移指南

### 从回调迁移到 EventBus

**旧代码：**
```python
async def on_state_change(old_state, new_state):
    print(f"State: {old_state} -> {new_state}")

async def on_error(error):
    print(f"Error: {error}")

engine = P2PEngine(
    on_state_change=on_state_change,
    on_error=on_error
)
```

**新代码（推荐）：**
```python
engine = P2PEngine()

async def on_connection_event(event):
    if event.event_type == P2PEventType.CONNECTION_STATE_CHANGED:
        print(f"State: {event.data['old_state']} -> {event.data['new_state']}")

async def on_error_event(event):
    print(f"Error: {event.data['error_message']}")

engine.event_bus.subscribe(EventTopic.CONNECTION, on_connection_event)
engine.event_bus.subscribe(EventTopic.ERROR, on_error_event)

await engine.event_bus.start()
```

### 优势

1. **更强大的过滤**：可以按主题、事件类型、对端 ID 过滤
2. **异步处理**：事件处理不会阻塞主流程
3. **指标收集**：EventBus 自动收集事件统计
4. **全局订阅**：可以订阅所有事件或特定主题
5. **解耦**：事件发布者和订阅者完全解耦

## 性能影响

- EventBus 使用异步队列，不会阻塞主流程
- 事件处理由独立的 worker 任务处理
- 向后兼容的回调仍然同步调用，保持原有行为

## 后续优化

1. 逐步废弃回调 API（在文档中标记为 deprecated）
2. 将更多内部事件迁移到 EventBus
3. 添加更多事件类型（NAT 检测、打孔进度等）
4. 实现事件持久化和重放功能

## 验收标准

- ✅ 只保留一套事件系统（EventBus）
- ✅ 所有事件通过 EventBus 发布
- ✅ 现有功能不受影响（向后兼容）
- ✅ 测试覆盖完整
- ✅ 文档完善

## 相关文件

- `p2p_engine/engine.py` - P2PEngine 主类
- `p2p_engine/event.py` - EventBus 实现
- `tests/unit/test_engine_eventbus_integration.py` - 集成测试
- `docs/P2P_ENGINE_EVENT_SYSTEM_UNIFICATION.md` - 本文档
