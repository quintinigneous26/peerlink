# P2P Platform 文档索引

## 文档概览

本项目包含完整的 Doxygen 中文文档，涵盖所有核心模块和API。

## 文档位置

### 生成的文档
- **HTML文档**: `docs/doxygen/html/index.html` - 完整的交互式文档
- **LaTeX文档**: `docs/doxygen/latex/` - 可用于生成PDF
- **XML文档**: `docs/doxygen/xml/` - 用于工具集成

### 文档源文件
- **Doxyfile**: 项目根目录 - Doxygen配置文件
- **doxygen_mainpage.h**: `docs/` 目录 - 文档主页定义

### 文档指南
- **DOXYGEN_REPORT.md**: 详细的生成报告
- **QUICK_REFERENCE.md**: 快速参考指南
- **DOCUMENTATION_INDEX.md**: 本文件

## 快速开始

### 1. 访问文档

**方式一：直接打开HTML**
```bash
open docs/doxygen/html/index.html
```

**方式二：使用Web服务器**
```bash
cd docs/doxygen/html
python -m http.server 8000
# 访问 http://localhost:8000
```

### 2. 主要页面

| 页面 | 说明 |
|------|------|
| index.html | 项目主页和概述 |
| classes.html | 所有类和数据结构 |
| files.html | 所有源代码文件 |
| namespaces.html | 模块和命名空间 |
| annotated.html | 类详细信息 |
| functions.html | 所有函数和方法 |

## 文档内容

### 核心模块

#### 1. p2p_engine - P2P引擎核心
- **engine.py**: 主引擎类 (P2PEngine)
- **types.py**: 核心类型定义
  - ConnectionState: 连接状态
  - ConnectionType: 连接类型
  - NATType: NAT类型
  - NATInfo: NAT信息
  - NetworkEnvironment: 网络环境
  - ConnectionResult: 连接结果
  - PeerInfo: 对端信息
  - ISP: 运营商枚举
  - Region: 地理区域
- **event.py**: 事件系统
  - EventBus: 事件总线
  - EventTopic: 事件主题
  - P2PEventType: 事件类型

#### 2. 子模块
- **config/**: 配置管理
- **detection/**: 网络检测（ISP、NAT）
- **puncher/**: NAT穿透（UDP打孔）
- **keeper/**: 心跳保活
- **fallback/**: 降级策略
- **protocol/**: 协议实现
- **transport/**: 传输层
- **muxer/**: 多路复用
- **dht/**: 分布式哈希表
- **security/**: 安全模块

#### 3. client_sdk - 客户端SDK
- 简化的API接口
- 事件回调机制
- 连接管理
- 数据传输

#### 4. 服务器模块
- **stun-server**: STUN服务器
- **relay-server**: TURN中继服务器
- **signaling-server**: 信令服务器
- **did-service**: DID身份服务

## 使用指南

### 查找API

1. **按类名查找**
   - 访问 `classes.html`
   - 使用搜索功能

2. **按文件查找**
   - 访问 `files.html`
   - 浏览目录结构

3. **按功能查找**
   - 访问 `namespaces.html`
   - 查看模块组织

### 理解架构

1. **查看主页** (`index.html`)
   - 项目概述
   - 架构设计
   - 快速开始

2. **查看类图**
   - 继承关系
   - 依赖关系
   - 调用关系

3. **查看代码示例**
   - 基本使用
   - 高级用法
   - 错误处理

## 文档特性

### 1. 完整的API参考
- 所有类、函数、枚举的详细说明
- 参数和返回值文档
- 异常说明
- 使用示例

### 2. 架构图表
- 类继承关系图
- 函数调用关系图
- 模块依赖关系图
- 目录结构图

### 3. 中文本地化
- 所有文档均为中文
- 中文搜索支持
- 中文导航菜单

### 4. 交互式导航
- 导航树
- 搜索功能
- 索引页面
- 相关链接

## 文档维护

### 更新文档

当代码发生变化时，重新生成文档：

```bash
cd /Users/liuhongbo/work/p2p-platform
doxygen Doxyfile
```

### 文档规范

#### 类文档
```python
class MyClass:
    """
    简短描述

    详细描述...

    属性:
        attr1: 说明
        attr2: 说明

    方法:
        method1(): 说明
    """
```

#### 函数文档
```python
async def my_function(param1, param2):
    """
    简短描述

    详细描述...

    参数:
        param1: 说明
        param2: 说明

    返回:
        说明返回值

    异常:
        ValueError: 说明异常情况
    """
```

#### 枚举文档
```python
class MyEnum(Enum):
    """
    枚举说明

    属性:
        VALUE1: 说明
        VALUE2: 说明
    """
```

## 常见问题

### Q: 如何生成PDF文档？
A: 使用LaTeX输出：
```bash
cd docs/doxygen/latex
make
```

### Q: 如何修改文档语言？
A: 编辑Doxyfile，修改OUTPUT_LANGUAGE参数。

### Q: 如何添加自定义页面？
A: 创建.h文件并在Doxyfile中的INPUT中添加。

### Q: 如何改进文档搜索？
A: 启用SEARCHENGINE选项并配置搜索引擎。

## 相关资源

- **项目README**: README.md
- **快速参考**: docs/QUICK_REFERENCE.md
- **生成报告**: docs/DOXYGEN_REPORT.md
- **Doxygen官网**: https://www.doxygen.nl/
- **Python文档规范**: PEP 257

## 文件统计

| 项目 | 数量 |
|------|------|
| 总HTML文件 | 3525 |
| 源代码文件 | 100+ |
| 类/数据类 | 50+ |
| 枚举类型 | 15+ |
| 函数/方法 | 200+ |
| 代码行数 | 10000+ |

## 支持

如有问题或建议，请：
1. 查看文档中的故障排除部分
2. 检查代码注释和示例
3. 查看相关模块的API参考
4. 提交Issue或Pull Request
