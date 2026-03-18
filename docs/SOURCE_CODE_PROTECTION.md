# Python 源码保护方案

**问题**: 当前 P2P Platform 服务器是 Python 源码，部署后源码完全暴露

**风险**:
- ❌ 商业机密泄露
- ❌ 算法逻辑暴露
- ❌ 安全漏洞易被发现
- ❌ 知识产权无保护

---

## 🛡️ 源码保护方案

### 方案对比

| 方案 | 保护级别 | 性能 | 兼容性 | 难度 |
|------|----------|------|--------|------|
| **1. 字节码编译** | ⭐⭐ | 100% | ✅ 完美 | 简单 |
| **2. Cython 编译** | ⭐⭐⭐⭐ | 120% | ⚠️ 需编译 | 中等 |
| **3. PyInstaller** | ⭐⭐⭐ | 95% | ✅ 单文件 | 简单 |
| **4. Nuitka 编译** | ⭐⭐⭐⭐⭐ | 150% | ⚠️ 需编译 | 中等 |
| **5. 混淆 + 加密** | ⭐⭐⭐ | 90% | ✅ 完美 | 复杂 |

---

## 方案 1: 字节码编译 (.pyc)

### 原理
将 `.py` 源码编译为 `.pyc` 字节码，删除源码文件

### 优点
- ✅ 简单快速，无需额外依赖
- ✅ 100% 兼容性
- ✅ 性能无损
- ✅ 基础保护，防止直接查看

### 缺点
- ⚠️ 可以被反编译（uncompyle6）
- ⚠️ 保护级别较低

### 实施步骤

```bash
# 1. 编译源码
python3 -m compileall -b stun-server/src
python3 -m compileall -b relay-server/src
python3 -m compileall -b signaling-server/src
python3 -m compileall -b did-service/src

# 2. 删除源码，只保留 .pyc
find . -name "*.py" ! -name "__init__.py" -delete

# 3. 打包
./packaging/scripts/build-rpm.sh
```

### 使用脚本

```bash
./packaging/scripts/compile-source.sh
# 选择: 1) 字节码编译
```

---

## 方案 2: Cython 编译 (.so) ⭐ 推荐

### 原理
将 Python 代码编译为 C 扩展 (.so 或 .pyd)，完全二进制化

### 优点
- ✅ 强保护，几乎无法反编译
- ✅ 性能提升 20-50%
- ✅ 与 C/C++ 库无缝集成
- ✅ 商业级保护

### 缺点
- ⚠️ 需要 C 编译器
- ⚠️ 跨平台需要分别编译
- ⚠️ 调试稍复杂

### 实施步骤

#### 1. 安装 Cython

```bash
pip3 install Cython
```

#### 2. 创建 setup.py

```python
# stun-server/setup.py
from setuptools import setup
from Cython.Build import cythonize
import glob

setup(
    name="stun-server",
    ext_modules=cythonize(
        glob.glob("src/**/*.py", recursive=True),
        compiler_directives={
            'language_level': '3',
            'embedsignature': True,
        }
    )
)
```

#### 3. 编译

```bash
cd stun-server
python3 setup.py build_ext --inplace

# 生成 .so 文件
# src/server.cpython-311-x86_64-linux-gnu.so
```

#### 4. 删除源码

```bash
find src -name "*.py" ! -name "__init__.py" -delete
```

#### 5. 打包

```bash
./packaging/scripts/build-rpm.sh
```

### 使用脚本

```bash
./packaging/scripts/compile-source.sh
# 选择: 2) Cython 编译
```

---

## 方案 3: PyInstaller 打包

### 原理
将 Python 程序和解释器打包为单个可执行文件

### 优点
- ✅ 单文件部署
- ✅ 无需 Python 环境
- ✅ 中等保护级别

### 缺点
- ⚠️ 文件体积大（50-100MB）
- ⚠️ 启动稍慢
- ⚠️ 可以被解包

### 实施步骤

```bash
# 1. 安装 PyInstaller
pip3 install pyinstaller

# 2. 打包
cd stun-server
pyinstaller --onefile src/server.py

# 3. 生成可执行文件
# dist/server
```

### 使用脚本

```bash
./packaging/scripts/compile-source.sh
# 选择: 3) PyInstaller 打包
```

---

## 方案 4: Nuitka 编译 ⭐⭐ 最强保护

### 原理
将 Python 代码完全编译为机器码（类似 C++ 编译）

### 优点
- ✅ 最强保护，完全二进制
- ✅ 性能提升 50-200%
- ✅ 无法反编译
- ✅ 商业级保护

### 缺点
- ⚠️ 编译时间长
- ⚠️ 文件体积大
- ⚠️ 跨平台需分别编译

### 实施步骤

```bash
# 1. 安装 Nuitka
pip3 install nuitka

# 2. 编译
cd stun-server
nuitka3 --standalone --onefile src/server.py

# 3. 生成可执行文件
# server.bin
```

### 使用脚本

```bash
./packaging/scripts/compile-source.sh
# 选择: 4) Nuitka 编译
```

---

## 方案 5: 混淆 + 加密

### 原理
使用 PyArmor 等工具对源码进行混淆和加密

### 优点
- ✅ 保持 Python 格式
- ✅ 强加密保护
- ✅ 运行时解密

### 缺点
- ⚠️ 需要商业许可
- ⚠️ 性能损失 10-20%

### 实施步骤

```bash
# 1. 安装 PyArmor
pip3 install pyarmor

# 2. 加密
pyarmor obfuscate --recursive stun-server/src/server.py

# 3. 生成加密后的文件
# dist/server.py (加密)
```

---

## 🎯 推荐方案

### 生产环境推荐

**方案 2: Cython 编译** ⭐⭐⭐⭐⭐

**理由**:
1. 强保护 - 编译为 .so 二进制文件
2. 性能提升 - 20-50% 性能提升
3. 商业可用 - 完全合法，无许可费用
4. 易于集成 - 与现有构建流程兼容

### 快速部署推荐

**方案 1: 字节码编译** ⭐⭐⭐

**理由**:
1. 简单快速 - 一条命令完成
2. 零依赖 - 无需额外工具
3. 基础保护 - 防止直接查看源码
4. 完美兼容 - 100% Python 兼容

---

## 📦 修改后的 RPM 构建流程

### 更新 RPM SPEC 文件

```spec
# packaging/rpm/p2p-platform.spec

%build
# 编译 Python 源码为字节码或 Cython
cd %{_builddir}/%{name}-%{version}

# 方式 1: 字节码
python3 -m compileall -b stun-server/src
python3 -m compileall -b relay-server/src
python3 -m compileall -b signaling-server/src
python3 -m compileall -b did-service/src

# 删除源码
find . -name "*.py" ! -name "__init__.py" -delete

# 方式 2: Cython (需要 BuildRequires: gcc, python3-devel)
# cd stun-server && python3 setup.py build_ext --inplace
# cd relay-server && python3 setup.py build_ext --inplace
# ...

%install
# 安装编译后的文件
cp -r stun-server %{buildroot}/opt/p2p-platform/
cp -r relay-server %{buildroot}/opt/p2p-platform/
cp -r signaling-server %{buildroot}/opt/p2p-platform/
cp -r did-service %{buildroot}/opt/p2p-platform/
```

---

## 🔒 安全建议

### 1. 多层保护

```
源码保护 (Cython)
    ↓
+ 代码混淆 (可选)
    ↓
+ 运行时加密 (可选)
    ↓
+ 网络加密 (TLS)
    ↓
+ 访问控制 (防火墙)
```

### 2. 关键模块重点保护

**高价值模块** (必须 Cython 编译):
- 核心算法
- 加密逻辑
- 商业逻辑
- 授权验证

**一般模块** (字节码即可):
- 配置文件
- 工具函数
- 日志处理

### 3. 许可证保护

添加许可证验证机制：

```python
# license_check.py (Cython 编译)
def verify_license(license_key: str) -> bool:
    # 复杂的许可证验证逻辑
    # 编译为 .so 后无法查看
    ...
```

---

## 📊 性能对比

| 方案 | 启动时间 | 运行性能 | 内存占用 |
|------|----------|----------|----------|
| 源码 | 1.0x | 1.0x | 1.0x |
| 字节码 | 0.95x | 1.0x | 1.0x |
| Cython | 0.9x | 1.2-1.5x | 0.95x |
| PyInstaller | 1.5x | 0.95x | 1.2x |
| Nuitka | 0.8x | 1.5-2.0x | 0.9x |

---

## 🚀 快速开始

### 立即保护源码

```bash
# 1. 运行编译脚本
cd /Users/liuhongbo/work/p2p-platform
./packaging/scripts/compile-source.sh

# 2. 选择编译方式
# 推荐: 2) Cython 编译

# 3. 构建 RPM 包
./packaging/scripts/build-rpm.sh

# 4. 验证
rpm -qlp dist/rpm/p2p-platform-*.rpm | grep -E "\.py$|\.so$"
# 应该只看到 .so 文件，没有 .py 源码
```

---

## 📝 总结

### 当前状态
- ❌ Python 源码直接部署
- ❌ 源码完全暴露
- ❌ 无任何保护

### 改进后
- ✅ Cython 编译为 .so 二进制
- ✅ 源码完全隐藏
- ✅ 商业级保护
- ✅ 性能提升 20-50%

### 行动建议

**立即执行**:
1. 运行 `./packaging/scripts/compile-source.sh`
2. 选择 Cython 编译
3. 重新构建 RPM/DEB 包
4. 测试编译后的程序
5. 部署到生产环境

**长期优化**:
1. 关键模块使用 Cython
2. 一般模块使用字节码
3. 添加许可证验证
4. 定期更新保护机制

---

**文档**: `docs/SOURCE_CODE_PROTECTION.md`
**脚本**: `packaging/scripts/compile-source.sh`
