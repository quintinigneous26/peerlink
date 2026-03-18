# P2P SDK 构建和发布文档

本目录包含 P2P Platform Client SDK 的完整构建和发布配置。

## 📦 包含内容

### 构建配置

- **pyproject.toml** - Python 包配置（PEP 621）
- **MANIFEST.in** - 源码分发包含文件清单
- **LICENSE** - MIT 许可证
- **CHANGELOG.md** - 版本变更日志

### 构建脚本

- **build.sh** - Python wheel 和 sdist 构建脚本
- **publish.sh** - PyPI 发布脚本
- **bump_version.sh** - 版本号管理脚本

### Conda 配置

- **conda/meta.yaml** - Conda 包元数据
- **conda/build.sh** - Conda 包构建脚本

### PyPI 配置

- **.pypirc.template** - PyPI 凭证配置模板

### 文档

- **docs/QUICKSTART.md** - 快速开始指南
- **docs/API_REFERENCE.md** - API 参考文档
- **docs/BEST_PRACTICES.md** - 最佳实践指南
- **docs/RELEASE_GUIDE.md** - 发布流程指南

## 🚀 快速开始

### 构建 Python 包

```bash
# 构建 wheel 和 source distribution
./build.sh

# 输出位于 dist/ 目录
ls -lh dist/
```

### 本地安装测试

```bash
# 安装构建的包
pip install dist/p2p_sdk-*.whl

# 测试导入
python -c "from p2p_sdk import P2PClient; print('OK')"
```

### 发布到 PyPI

```bash
# 1. 配置 PyPI token
cp .pypirc.template ~/.pypirc
# 编辑 ~/.pypirc，填写你的 token

# 2. 发布到 Test PyPI（测试）
./publish.sh test

# 3. 发布到生产 PyPI
./publish.sh prod
```

### 构建 Conda 包

```bash
# 构建 conda 包
cd conda
./build.sh

# 本地安装测试
conda install --use-local p2p-sdk
```

## 📋 发布流程

完整的发布流程请参见 [docs/RELEASE_GUIDE.md](docs/RELEASE_GUIDE.md)。

简要步骤：

1. **更新版本号**
   ```bash
   ./bump_version.sh 0.2.0
   ```

2. **更新 CHANGELOG**
   编辑 `CHANGELOG.md`，添加本次发布的变更

3. **运行测试**
   ```bash
   pytest tests/ -v
   pytest --cov=p2p_sdk tests/
   ```

4. **构建包**
   ```bash
   ./build.sh
   ```

5. **测试发布（Test PyPI）**
   ```bash
   ./publish.sh test
   ```

6. **创建 Git 标签**
   ```bash
   git add -A
   git commit -m "chore: bump version to 0.2.0"
   git tag -a v0.2.0 -m "Release v0.2.0"
   git push origin main --tags
   ```

7. **发布到生产**
   ```bash
   ./publish.sh prod
   ```

8. **创建 GitHub Release**
   在 GitHub 上创建 Release，上传构建产物

## 📚 文档

### 用户文档

- [快速开始](docs/QUICKSTART.md) - 安装和基础使用
- [API 参考](docs/API_REFERENCE.md) - 完整 API 文档
- [最佳实践](docs/BEST_PRACTICES.md) - 开发最佳实践

### 开发者文档

- [发布指南](docs/RELEASE_GUIDE.md) - 完整发布流程
- [README.md](README.md) - SDK 功能和使用说明

## 🔧 开发环境设置

### 安装开发依赖

```bash
# 安装包（可编辑模式）
pip install -e .

# 安装开发依赖
pip install -e ".[dev]"
```

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 带覆盖率
pytest --cov=p2p_sdk tests/

# 生成 HTML 覆盖率报告
pytest --cov=p2p_sdk --cov-report=html tests/
```

### 代码质量检查

```bash
# 格式化代码
black src/

# 检查代码风格
ruff check src/

# 类型检查
mypy src/
```

## 📦 包结构

```
client_sdk/
├── src/
│   └── p2p_sdk/          # SDK 源代码
│       ├── __init__.py
│       ├── client.py
│       ├── nat_detection.py
│       ├── protocol.py
│       ├── signaling.py
│       ├── transport.py
│       └── exceptions.py
├── tests/                # 测试代码
│   ├── test_client.py
│   ├── test_nat.py
│   └── ...
├── examples/             # 示例代码
│   ├── basic_usage.py
│   └── multi_channel.py
├── docs/                 # 文档
│   ├── QUICKSTART.md
│   ├── API_REFERENCE.md
│   ├── BEST_PRACTICES.md
│   └── RELEASE_GUIDE.md
├── conda/                # Conda 配置
│   ├── meta.yaml
│   └── build.sh
├── pyproject.toml        # 包配置
├── MANIFEST.in           # 分发清单
├── LICENSE               # 许可证
├── CHANGELOG.md          # 变更日志
├── README.md             # SDK 说明
├── build.sh              # 构建脚本
├── publish.sh            # 发布脚本
├── bump_version.sh       # 版本管理脚本
└── .pypirc.template      # PyPI 配置模板
```

## 🔐 安全

### PyPI Token 管理

1. 在 PyPI 创建 API token
2. 复制 `.pypirc.template` 到 `~/.pypirc`
3. 填写 token（不要提交到 Git）

```bash
cp .pypirc.template ~/.pypirc
chmod 600 ~/.pypirc
```

### 敏感文件

以下文件不应提交到版本控制：

- `~/.pypirc` - PyPI 凭证
- `dist/` - 构建产物
- `build/` - 构建临时文件
- `*.egg-info/` - 包元数据

## 📊 版本管理

遵循语义化版本（Semantic Versioning）：

- **主版本号（Major）**：不兼容的 API 变更
- **次版本号（Minor）**：向后兼容的功能新增
- **修订号（Patch）**：向后兼容的问题修复

当前版本：**0.1.0**

## 🐛 问题反馈

- GitHub Issues: https://github.com/p2p-platform/python-sdk/issues
- Email: dev@p2p-platform.example.com

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献

欢迎贡献！请遵循以下步骤：

1. Fork 仓库
2. 创建特性分支
3. 提交变更
4. 推送到分支
5. 创建 Pull Request

## 📞 联系方式

- 项目主页: https://github.com/p2p-platform/python-sdk
- 文档: https://github.com/p2p-platform/python-sdk#readme
- 问题追踪: https://github.com/p2p-platform/python-sdk/issues

---

**注意：** 首次发布前，请确保：

1. 所有测试通过
2. 文档完整
3. 示例可运行
4. 版本号正确
5. CHANGELOG 已更新
