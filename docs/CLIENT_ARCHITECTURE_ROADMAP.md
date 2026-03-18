# P2P Platform 客户端架构说明

**当前状态**: 2026-03-15

---

## ⚠️ 当前问题

### 现状
- ❌ **只有 Python 客户端** (`client_sdk/`)
- ❌ **核心引擎也是 Python** (`p2p_engine/`)
- ❌ **没有 C++ 客户端**
- ❌ **源码完全暴露**

### 问题
1. **性能问题**: Python 性能不如 C++
2. **源码暴露**: 客户端源码完全可见
3. **平台限制**: 难以集成到 C++/Java/Swift 应用
4. **商业风险**: 核心算法无保护

---

## 🎯 解决方案

### 方案 1: Python 客户端 + Cython 编译 ⭐⭐⭐

**适用场景**: Python 应用、快速原型

**实施**:
```bash
# 将 Python 客户端编译为 .so
cd client_sdk
python3 setup.py build_ext --inplace

# 生成
# p2p_sdk/client.cpython-311-x86_64-linux-gnu.so
```

**优点**:
- ✅ 快速实施
- ✅ 源码保护
- ✅ 性能提升 20-50%

**缺点**:
- ⚠️ 仍然是 Python 生态
- ⚠️ 跨语言调用困难

---

### 方案 2: C++ 核心库 + 多语言绑定 ⭐⭐⭐⭐⭐ 推荐

**架构**:
```
C++ 核心库 (libp2p-core.so)
    ↓
├── Python 绑定 (pybind11)
├── Java 绑定 (JNI)
├── Swift 绑定 (C interop)
├── JavaScript 绑定 (N-API)
└── Go 绑定 (cgo)
```

**实施步骤**:

#### 1. 创建 C++ 核心库

```cpp
// p2p_core/include/p2p_client.h
#ifndef P2P_CLIENT_H
#define P2P_CLIENT_H

#include <string>
#include <functional>

namespace p2p {

class Client {
public:
    Client(const std::string& device_id);
    ~Client();

    // 连接到对端
    bool connect(const std::string& peer_id);

    // 发送数据
    bool send(const uint8_t* data, size_t len);

    // 接收数据回调
    void on_receive(std::function<void(const uint8_t*, size_t)> callback);

    // 断开连接
    void disconnect();

private:
    class Impl;
    Impl* impl_;
};

} // namespace p2p

#endif // P2P_CLIENT_H
```

```cpp
// p2p_core/src/p2p_client.cpp
#include "p2p_client.h"
#include <memory>

namespace p2p {

class Client::Impl {
public:
    // 实现核心逻辑
    // NAT 穿透、STUN、TURN、信令等
};

Client::Client(const std::string& device_id)
    : impl_(new Impl()) {
}

Client::~Client() {
    delete impl_;
}

bool Client::connect(const std::string& peer_id) {
    // 实现连接逻辑
    return true;
}

// ... 其他实现

} // namespace p2p
```

#### 2. Python 绑定 (pybind11)

```cpp
// bindings/python/p2p_python.cpp
#include <pybind11/pybind11.h>
#include <pybind11/functional.h>
#include "p2p_client.h"

namespace py = pybind11;

PYBIND11_MODULE(p2p_core, m) {
    py::class_<p2p::Client>(m, "Client")
        .def(py::init<const std::string&>())
        .def("connect", &p2p::Client::connect)
        .def("send", [](p2p::Client& self, py::bytes data) {
            std::string str = data;
            return self.send((const uint8_t*)str.data(), str.size());
        })
        .def("on_receive", &p2p::Client::on_receive)
        .def("disconnect", &p2p::Client::disconnect);
}
```

**使用**:
```python
import p2p_core

client = p2p_core.Client("my-device")
client.connect("peer-device")
client.send(b"Hello")
```

#### 3. Java 绑定 (JNI)

```cpp
// bindings/java/p2p_jni.cpp
#include <jni.h>
#include "p2p_client.h"

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_p2p_Client_nativeCreate(JNIEnv* env, jobject obj, jstring deviceId) {
    const char* id = env->GetStringUTFChars(deviceId, nullptr);
    p2p::Client* client = new p2p::Client(id);
    env->ReleaseStringUTFChars(deviceId, id);
    return reinterpret_cast<jlong>(client);
}

JNIEXPORT jboolean JNICALL
Java_com_p2p_Client_nativeConnect(JNIEnv* env, jobject obj, jlong handle, jstring peerId) {
    p2p::Client* client = reinterpret_cast<p2p::Client*>(handle);
    const char* peer = env->GetStringUTFChars(peerId, nullptr);
    bool result = client->connect(peer);
    env->ReleaseStringUTFChars(peerId, peer);
    return result;
}

} // extern "C"
```

**使用**:
```java
// Java 客户端
public class Client {
    private long nativeHandle;

    public Client(String deviceId) {
        nativeHandle = nativeCreate(deviceId);
    }

    public boolean connect(String peerId) {
        return nativeConnect(nativeHandle, peerId);
    }

    private native long nativeCreate(String deviceId);
    private native boolean nativeConnect(long handle, String peerId);
}
```

#### 4. Swift 绑定

```swift
// bindings/swift/P2PClient.swift
import Foundation

public class P2PClient {
    private var handle: OpaquePointer?

    public init(deviceId: String) {
        handle = p2p_client_create(deviceId)
    }

    deinit {
        p2p_client_destroy(handle)
    }

    public func connect(peerId: String) -> Bool {
        return p2p_client_connect(handle, peerId)
    }
}
```

---

### 方案 3: 混合架构 ⭐⭐⭐⭐

**架构**:
```
Python 服务器 (STUN/Relay/Signaling)
    ↓
C++ 客户端库 (核心引擎)
    ↓
多语言绑定 (Python/Java/Swift/JS)
```

**优点**:
- ✅ 服务器保持 Python（易维护）
- ✅ 客户端使用 C++（高性能、源码保护）
- ✅ 多语言支持
- ✅ 商业级保护

**实施优先级**:
1. **Phase 1**: C++ 核心库（NAT 穿透、STUN、TURN）
2. **Phase 2**: Python 绑定（兼容现有代码）
3. **Phase 3**: Java/Swift 绑定（移动端）
4. **Phase 4**: JavaScript 绑定（Web 端）

---

## 📦 项目结构（重构后）

```
p2p-platform/
├── p2p_core/                    # C++ 核心库 ⭐ 新增
│   ├── include/
│   │   ├── p2p_client.h
│   │   ├── nat_traversal.h
│   │   ├── stun_client.h
│   │   └── turn_client.h
│   ├── src/
│   │   ├── p2p_client.cpp
│   │   ├── nat_traversal.cpp
│   │   ├── stun_client.cpp
│   │   └── turn_client.cpp
│   ├── CMakeLists.txt
│   └── README.md
│
├── bindings/                    # 多语言绑定 ⭐ 新增
│   ├── python/
│   │   ├── p2p_python.cpp      # pybind11
│   │   └── setup.py
│   ├── java/
│   │   ├── p2p_jni.cpp         # JNI
│   │   └── build.gradle
│   ├── swift/
│   │   ├── P2PClient.swift
│   │   └── Package.swift
│   └── javascript/
│       ├── p2p_napi.cpp        # N-API
│       └── package.json
│
├── client_sdk/                  # Python SDK（使用 C++ 核心）
│   └── src/p2p_sdk/
│       └── __init__.py         # 导入 p2p_core
│
├── p2p_engine/                  # Python 引擎（服务器端）
│   └── ...
│
├── stun-server/                 # Python 服务器
├── relay-server/
├── signaling-server/
└── did-service/
```

---

## 🛠️ 构建系统

### CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.15)
project(p2p-core VERSION 1.0.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 核心库
add_library(p2p-core SHARED
    src/p2p_client.cpp
    src/nat_traversal.cpp
    src/stun_client.cpp
    src/turn_client.cpp
)

target_include_directories(p2p-core PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

# 依赖
find_package(OpenSSL REQUIRED)
find_package(Boost REQUIRED COMPONENTS system)

target_link_libraries(p2p-core
    OpenSSL::SSL
    OpenSSL::Crypto
    Boost::system
)

# 安装
install(TARGETS p2p-core
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
)
```

### 构建命令

```bash
# 构建 C++ 核心库
mkdir build && cd build
cmake ..
make -j$(nproc)
sudo make install

# 构建 Python 绑定
cd bindings/python
pip3 install pybind11
python3 setup.py build_ext --inplace
pip3 install .

# 构建 Java 绑定
cd bindings/java
./gradlew build

# 构建 Swift 绑定
cd bindings/swift
swift build
```

---

## 🚀 迁移路径

### Phase 1: 准备阶段（1-2 周）

1. **设计 C++ API**
   - 定义核心接口
   - 确定数据结构
   - 设计回调机制

2. **搭建构建系统**
   - CMake 配置
   - CI/CD 集成
   - 跨平台测试

### Phase 2: 核心实现（4-6 周）

1. **实现 C++ 核心库**
   - NAT 穿透逻辑
   - STUN 客户端
   - TURN 客户端
   - 信令客户端

2. **单元测试**
   - Google Test
   - 覆盖率 > 80%

### Phase 3: Python 绑定（1-2 周）

1. **pybind11 绑定**
2. **兼容现有 API**
3. **集成测试**

### Phase 4: 其他语言绑定（2-4 周）

1. **Java 绑定** (Android)
2. **Swift 绑定** (iOS)
3. **JavaScript 绑定** (Web)

### Phase 5: 发布（1 周）

1. **打包发布**
   - PyPI (Python)
   - Maven (Java)
   - CocoaPods (Swift)
   - npm (JavaScript)

2. **文档更新**
3. **示例代码**

---

## 📊 对比分析

### 当前 vs 重构后

| 特性 | 当前 (Python) | 重构后 (C++) |
|------|---------------|--------------|
| **性能** | 基准 | 3-5x 提升 |
| **源码保护** | ❌ 完全暴露 | ✅ 二进制保护 |
| **多语言支持** | ❌ 仅 Python | ✅ Python/Java/Swift/JS |
| **移动端支持** | ⚠️ 困难 | ✅ 原生支持 |
| **商业可用** | ⚠️ 风险高 | ✅ 商业级 |
| **维护成本** | 低 | 中 |

---

## 💰 成本估算

### 开发成本

| 阶段 | 工作量 | 时间 |
|------|--------|------|
| C++ 核心库 | 4-6 人周 | 4-6 周 |
| Python 绑定 | 1-2 人周 | 1-2 周 |
| Java 绑定 | 1-2 人周 | 1-2 周 |
| Swift 绑定 | 1-2 人周 | 1-2 周 |
| 测试 & 文档 | 2-3 人周 | 2-3 周 |
| **总计** | **9-15 人周** | **10-15 周** |

### 收益

1. **性能提升**: 3-5x
2. **源码保护**: 商业级
3. **市场扩展**: 支持所有主流平台
4. **商业价值**: 可销售的 SDK

---

## 🎯 推荐方案

### 短期（1-2 月）

**方案 1: Python + Cython**
- 快速实施
- 基础保护
- 性能提升 20-50%

```bash
./packaging/scripts/compile-source.sh
# 选择: 2) Cython 编译
```

### 长期（3-6 月）

**方案 2: C++ 核心 + 多语言绑定**
- 商业级保护
- 多平台支持
- 性能提升 3-5x

**实施步骤**:
1. 立即启动 C++ 核心库开发
2. 优先实现 Python 绑定（兼容现有代码）
3. 逐步添加其他语言绑定
4. 最终替换所有 Python 客户端

---

## 📝 总结

### 当前问题
- ❌ 客户端是 Python 源码
- ❌ 核心引擎是 Python 源码
- ❌ 没有 C++ 客户端
- ❌ 源码完全暴露

### 解决方案
1. **短期**: Cython 编译 Python 代码
2. **长期**: 开发 C++ 核心库 + 多语言绑定

### 行动建议

**立即执行**:
```bash
# 1. 编译现有 Python 代码
./packaging/scripts/compile-source.sh

# 2. 启动 C++ 核心库项目
mkdir p2p_core
cd p2p_core
# 开始 C++ 开发
```

**长期规划**:
- Q2 2026: 完成 C++ 核心库
- Q3 2026: 完成多语言绑定
- Q4 2026: 全面替换 Python 客户端

---

**文档**: `docs/CLIENT_ARCHITECTURE_ROADMAP.md`
**状态**: 需要立即行动
