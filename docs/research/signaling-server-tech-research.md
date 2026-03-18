# 信令服务器 C++ 技术调研报告

**调研人员**: engineer-signaling
**日期**: 2026-03-15
**目标**: 为信令服务器 C++ 迁移选择最佳技术栈

## 性能目标

- 并发连接数: 10,000+
- 消息延迟: < 10ms
- 内存占用: < 100MB (10K 连接)

## 1. WebSocket 库对比

### 1.1 uWebSockets

**优势**:
- 性能极致，号称最快的 WebSocket 实现
- 内存占用极低
- 支持 SSL/TLS
- 零拷贝设计

**劣势**:
- API 较底层，学习曲线陡峭
- 文档相对较少
- 社区规模较小
- 与标准 C++ 异步模型集成较困难

**性能数据** (官方 benchmark):
- 吞吐量: ~1.2M msg/s
- 延迟: ~0.5ms (p99)
- 内存: ~5KB per connection

**适用场景**: 对性能要求极致的场景

### 1.2 Boost.Beast

**优势**:
- Boost 官方库，成熟稳定
- 与 Boost.Asio 无缝集成
- 支持 C++20 coroutine
- 文档完善，社区活跃
- 易于维护和扩展

**劣势**:
- 性能略低于 uWebSockets
- 需要依赖整个 Boost 库
- 编译时间较长

**性能数据** (社区 benchmark):
- 吞吐量: ~800K msg/s
- 延迟: ~1-2ms (p99)
- 内存: ~8KB per connection

**适用场景**: 需要稳定性和可维护性的生产环境

### 1.3 推荐选择

**推荐: Boost.Beast**

**理由**:
1. 性能满足需求（800K msg/s >> 10K 连接需求）
2. 与 Boost.Asio 集成，支持现代 C++ 异步编程
3. 文档完善，降低开发和维护成本
4. 社区活跃，问题容易解决
5. 支持 C++20 coroutine，代码可读性好

## 2. JSON 库评估

### 2.1 nlohmann/json

**优势**:
- API 极其友好，类似 Python dict
- 单头文件，集成简单
- 支持 JSON Schema 验证
- 错误处理完善

**劣势**:
- 性能相对较低
- 编译时间较长（模板重）

**性能数据**:
- 序列化: ~50MB/s
- 反序列化: ~40MB/s
- 内存: 中等

**代码示例**:
```cpp
json msg = {
    {"type", "offer"},
    {"data", {
        {"session_id", "123"},
        {"offer", "sdp..."}
    }}
};
std::string str = msg.dump();
```

### 2.2 rapidjson

**优势**:
- 性能极致，SAX/DOM 双模式
- 内存占用低
- 支持原地解析（in-situ parsing）
- 零拷贝设计

**劣势**:
- API 较复杂
- 错误处理不够友好
- 代码可读性较差

**性能数据**:
- 序列化: ~200MB/s
- 反序列化: ~180MB/s
- 内存: 低

**代码示例**:
```cpp
rapidjson::Document doc;
doc.SetObject();
auto& allocator = doc.GetAllocator();
doc.AddMember("type", "offer", allocator);
rapidjson::Value data(rapidjson::kObjectType);
data.AddMember("session_id", "123", allocator);
doc.AddMember("data", data, allocator);
```

### 2.3 推荐选择

**推荐: nlohmann/json**

**理由**:
1. 信令服务器消息频率不高（相比数据传输）
2. API 友好，代码可读性好，易于维护
3. 性能足够（50MB/s 对于小消息完全够用）
4. 降低开发成本和出错概率
5. 如果后续性能瓶颈在 JSON，可局部优化为 rapidjson

## 3. 异步模型设计

### 3.1 Boost.Asio + C++20 Coroutine

**架构**:
```
io_context (事件循环)
    ↓
Acceptor (监听新连接)
    ↓
WebSocketSession (每个连接)
    ↓
MessageHandler (消息处理)
```

**优势**:
- 使用 co_await，代码类似 Python async/await
- 单线程事件循环，避免锁竞争
- 性能高，资源占用低

**代码示例**:
```cpp
asio::awaitable<void> handle_message(
    std::string device_id,
    json message
) {
    auto type = message["type"].get<std::string>();

    if (type == "offer") {
        auto session_id = message["data"]["session_id"];
        // 处理 offer
        co_await forward_to_peer(session_id, message);
    }

    co_return;
}
```

### 3.2 线程安全的连接管理

**设计**:
- 使用 `std::shared_mutex` 读写锁
- 读操作（查询设备）使用 shared_lock
- 写操作（添加/删除设备）使用 unique_lock
- 避免在锁内执行 I/O 操作

**代码示例**:
```cpp
class ConnectionManager {
private:
    std::unordered_map<std::string, DeviceInfo> devices_;
    mutable std::shared_mutex mutex_;

public:
    std::optional<DeviceInfo> get_device(const std::string& id) const {
        std::shared_lock lock(mutex_);
        auto it = devices_.find(id);
        return it != devices_.end()
            ? std::optional{it->second}
            : std::nullopt;
    }

    void add_device(std::string id, DeviceInfo info) {
        std::unique_lock lock(mutex_);
        devices_[std::move(id)] = std::move(info);
    }
};
```

## 4. 核心接口设计草案

### 4.1 ConnectionManager

```cpp
class ConnectionManager {
public:
    // 连接管理
    asio::awaitable<void> connect(
        std::string device_id,
        std::shared_ptr<WebSocketSession> session,
        std::string public_key,
        std::vector<std::string> capabilities
    );

    asio::awaitable<void> disconnect(std::string device_id);

    std::optional<DeviceInfo> get_device(const std::string& id) const;
    bool is_connected(const std::string& id) const;

    // 消息发送
    asio::awaitable<bool> send_message(
        const std::string& device_id,
        const json& message
    );

    asio::awaitable<int> broadcast(
        const json& message,
        const std::unordered_set<std::string>& exclude = {}
    );

    // 会话管理
    ConnectionSession create_session(
        std::string device_a,
        std::string device_b
    );

    std::optional<ConnectionSession> get_session(
        const std::string& session_id
    ) const;

    // 心跳管理
    asio::awaitable<void> update_heartbeat(std::string device_id);
    asio::awaitable<int> cleanup_stale(int timeout_seconds);
};
```

### 4.2 WebSocketSession

```cpp
class WebSocketSession
    : public std::enable_shared_from_this<WebSocketSession> {
public:
    WebSocketSession(
        tcp::socket socket,
        std::shared_ptr<ConnectionManager> manager
    );

    asio::awaitable<void> run();
    asio::awaitable<void> send(json message);
    asio::awaitable<void> close();

private:
    asio::awaitable<void> read_loop();
    asio::awaitable<void> handle_message(json message);

    websocket::stream<tcp::socket> ws_;
    std::shared_ptr<ConnectionManager> manager_;
    std::string device_id_;
};
```

### 4.3 MessageHandler

```cpp
class MessageHandler {
public:
    explicit MessageHandler(std::shared_ptr<ConnectionManager> manager);

    asio::awaitable<std::optional<json>> handle_message(
        const std::string& device_id,
        const json& message
    );

private:
    asio::awaitable<json> handle_register(
        const std::string& device_id,
        const json& message
    );

    asio::awaitable<json> handle_connect(
        const std::string& device_id,
        const json& message
    );

    asio::awaitable<json> handle_offer(
        const std::string& device_id,
        const json& message
    );

    asio::awaitable<json> handle_answer(
        const std::string& device_id,
        const json& message
    );

    asio::awaitable<json> handle_ice_candidate(
        const std::string& device_id,
        const json& message
    );

    std::shared_ptr<ConnectionManager> manager_;
};
```

## 5. 数据模型设计

### 5.1 核心结构体

```cpp
enum class MessageType {
    REGISTER,
    REGISTERED,
    UNREGISTER,
    CONNECT,
    CONNECT_REQUEST,
    CONNECT_RESPONSE,
    DISCONNECT,
    OFFER,
    ANSWER,
    ICE_CANDIDATE,
    HEARTBEAT,
    HEARTBEAT_ACK,
    ERROR,
    PING,
    PONG,
    QUERY_DEVICE,
    DEVICE_INFO,
    RELAY_REQUEST,
    RELAY_RESPONSE
};

enum class ConnectionStatus {
    CONNECTING,
    CONNECTED,
    DISCONNECTED,
    FAILED
};

enum class NATType {
    PUBLIC,
    FULL_CONE,
    RESTRICTED_CONE,
    PORT_RESTRICTED,
    SYMMETRIC,
    UNKNOWN
};

struct DeviceInfo {
    std::string device_id;
    std::shared_ptr<WebSocketSession> session;
    std::string public_key;
    std::vector<std::string> capabilities;
    NATType nat_type = NATType::UNKNOWN;
    std::optional<std::string> public_ip;
    std::optional<int> public_port;
    std::chrono::system_clock::time_point connected_at;
    std::chrono::system_clock::time_point last_heartbeat;
    ConnectionStatus status = ConnectionStatus::CONNECTED;
    json metadata;
};

struct ConnectionSession {
    std::string session_id;
    std::string device_a;
    std::string device_b;
    ConnectionStatus status = ConnectionStatus::CONNECTING;
    std::chrono::system_clock::time_point created_at;
    std::optional<std::string> offer;
    std::optional<std::string> answer;
    std::vector<json> ice_candidates_a;
    std::vector<json> ice_candidates_b;
    bool use_relay = false;
};
```

## 6. 性能优化策略

### 6.1 内存池

- 使用 `boost::pool` 或自定义内存池
- 预分配常用对象（DeviceInfo, ConnectionSession）
- 减少频繁的 new/delete

### 6.2 零拷贝

- 使用 `std::string_view` 避免字符串拷贝
- JSON 解析使用原地解析（如果切换到 rapidjson）
- WebSocket 消息使用 `asio::buffer` 直接发送

### 6.3 连接池优化

- 使用 `std::unordered_map` 快速查找
- 读写锁分离，提高并发读性能
- 定期清理过期连接，避免内存泄漏

## 7. 实现计划

### Phase 1: 基础框架（2-3 天）
- [ ] 搭建 CMake 项目结构
- [ ] 集成 Boost.Beast 和 nlohmann/json
- [ ] 实现 WebSocketSession 基础类
- [ ] 实现 ConnectionManager 基础功能

### Phase 2: 核心功能（3-4 天）
- [ ] 实现消息路由和处理
- [ ] 实现设备注册/注销
- [ ] 实现连接请求/响应
- [ ] 实现 WebRTC 信令（Offer/Answer/ICE）

### Phase 3: 高级功能（2-3 天）
- [ ] 实现心跳检测和超时清理
- [ ] 实现设备发现
- [ ] 实现 Relay 请求处理
- [ ] 错误处理和日志

### Phase 4: 测试和优化（2-3 天）
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能测试和优化
- [ ] 压力测试（10K 连接）

## 8. 风险和挑战

### 8.1 技术风险

1. **C++20 Coroutine 兼容性**
   - 需要 GCC 10+ 或 Clang 14+
   - 部分平台可能不支持
   - 缓解: 提供回退方案（callback 模式）

2. **内存管理复杂度**
   - shared_ptr 循环引用风险
   - 缓解: 使用 weak_ptr，严格的生命周期管理

3. **并发 Bug**
   - 死锁、竞态条件
   - 缓解: 使用 ThreadSanitizer，充分测试

### 8.2 性能风险

1. **JSON 序列化瓶颈**
   - 缓解: 如果成为瓶颈，局部切换到 rapidjson

2. **锁竞争**
   - 缓解: 使用读写锁，减少锁粒度

## 9. 总结

**推荐技术栈**:
- WebSocket: Boost.Beast
- JSON: nlohmann/json
- 异步模型: Boost.Asio + C++20 Coroutine
- 并发控制: std::shared_mutex

**预期性能**:
- 并发连接: 10,000+ ✓
- 消息延迟: < 10ms ✓
- 内存占用: ~80MB (10K 连接) ✓

**开发周期**: 9-13 天

**下一步**: 等待架构师完成整体架构设计，然后开始实现。
