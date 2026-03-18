# P2P SDK 发布指南

## 构建和发布流程

### 1. 准备发布

#### 1.1 更新版本号

```bash
# 使用版本管理脚本
./bump_version.sh 0.2.0
```

这将自动更新：
- `pyproject.toml`
- `src/p2p_sdk/__init__.py`
- `conda/meta.yaml`
- `CHANGELOG.md`

#### 1.2 更新 CHANGELOG

编辑 `CHANGELOG.md`，添加本次发布的详细变更：

```markdown
## [0.2.0] - 2026-03-20

### Added
- 新功能 1
- 新功能 2

### Changed
- 改进 1
- 改进 2

### Fixed
- 修复 1
- 修复 2
```

#### 1.3 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 检查覆盖率
pytest --cov=p2p_sdk tests/

# 运行类型检查
mypy src/

# 运行代码格式检查
black --check src/
ruff check src/
```

### 2. 构建包

#### 2.1 构建 Python Wheel

```bash
# 运行构建脚本
./build.sh
```

这将：
1. 清理旧的构建文件
2. 安装构建依赖
3. 构建 wheel 和 sdist
4. 验证包完整性

输出文件位于 `dist/` 目录：
- `p2p_sdk-0.2.0-py3-none-any.whl`
- `p2p_sdk-0.2.0.tar.gz`

#### 2.2 构建 Conda 包

```bash
# 运行 conda 构建脚本
cd conda
./build.sh
```

### 3. 本地测试

#### 3.1 测试 Wheel 包

```bash
# 创建虚拟环境
python3 -m venv test_env
source test_env/bin/activate

# 安装构建的包
pip install dist/p2p_sdk-0.2.0-py3-none-any.whl

# 测试导入
python -c "from p2p_sdk import P2PClient; print('OK')"

# 运行示例
python examples/basic_usage.py

# 清理
deactivate
rm -rf test_env
```

#### 3.2 测试 Conda 包

```bash
# 安装本地包
conda install --use-local p2p-sdk

# 测试
python -c "from p2p_sdk import P2PClient; print('OK')"

# 卸载
conda remove p2p-sdk
```

### 4. 发布到 Test PyPI

#### 4.1 配置凭证

复制模板并填写 Test PyPI token：

```bash
cp .pypirc.template ~/.pypirc
# 编辑 ~/.pypirc，填写 testpypi token
```

#### 4.2 上传到 Test PyPI

```bash
# 上传到 Test PyPI
./publish.sh test
```

#### 4.3 从 Test PyPI 安装测试

```bash
# 创建测试环境
python3 -m venv test_pypi_env
source test_pypi_env/bin/activate

# 从 Test PyPI 安装
pip install --index-url https://test.pypi.org/simple/ p2p-sdk

# 测试
python -c "from p2p_sdk import P2PClient; print('OK')"

# 清理
deactivate
rm -rf test_pypi_env
```

### 5. 发布到生产 PyPI

#### 5.1 最终检查

- [ ] 所有测试通过
- [ ] 文档已更新
- [ ] CHANGELOG 已更新
- [ ] 版本号正确
- [ ] Test PyPI 测试成功

#### 5.2 创建 Git 标签

```bash
# 提交版本变更
git add -A
git commit -m "chore: bump version to 0.2.0"

# 创建标签
git tag -a v0.2.0 -m "Release v0.2.0"

# 推送到远程
git push origin main
git push origin v0.2.0
```

#### 5.3 上传到 PyPI

```bash
# 上传到生产 PyPI
./publish.sh prod
```

#### 5.4 验证发布

```bash
# 等待几分钟让 PyPI 索引更新
sleep 60

# 安装并测试
pip install p2p-sdk==0.2.0
python -c "from p2p_sdk import P2PClient; print('OK')"
```

### 6. 发布到 Conda

#### 6.1 上传到 Anaconda Cloud

```bash
# 获取包路径
PACKAGE_PATH=$(conda-build conda/ --output)

# 上传
anaconda upload $PACKAGE_PATH
```

#### 6.2 验证

```bash
# 从 Anaconda Cloud 安装
conda install -c your-channel p2p-sdk

# 测试
python -c "from p2p_sdk import P2PClient; print('OK')"
```

### 7. 发布 GitHub Release

#### 7.1 创建 Release

1. 访问 GitHub 仓库
2. 点击 "Releases" → "Create a new release"
3. 选择标签 `v0.2.0`
4. 填写 Release 标题：`v0.2.0`
5. 复制 CHANGELOG 内容到描述
6. 上传构建产物：
   - `dist/p2p_sdk-0.2.0-py3-none-any.whl`
   - `dist/p2p_sdk-0.2.0.tar.gz`
7. 点击 "Publish release"

#### 7.2 更新文档

如果使用 GitHub Pages 或 Read the Docs：

```bash
# 构建文档
cd docs
make html

# 部署到 GitHub Pages
# （根据你的文档托管方式）
```

## 发布检查清单

### 发布前

- [ ] 所有测试通过（单元测试、集成测试）
- [ ] 代码覆盖率 ≥ 80%
- [ ] 类型检查通过（mypy）
- [ ] 代码格式检查通过（black, ruff）
- [ ] 文档已更新
- [ ] CHANGELOG 已更新
- [ ] 版本号已更新（所有文件一致）
- [ ] 示例代码可运行
- [ ] 无已知的严重 bug

### 构建

- [ ] Wheel 包构建成功
- [ ] Source distribution 构建成功
- [ ] Conda 包构建成功（如果适用）
- [ ] 包完整性检查通过（twine check）

### 测试

- [ ] 本地安装测试通过
- [ ] Test PyPI 安装测试通过
- [ ] 示例代码在新环境中可运行
- [ ] 依赖项正确安装

### 发布

- [ ] Git 标签已创建
- [ ] 代码已推送到 GitHub
- [ ] PyPI 发布成功
- [ ] Conda 发布成功（如果适用）
- [ ] GitHub Release 已创建
- [ ] 文档已更新

### 发布后

- [ ] PyPI 页面显示正常
- [ ] 从 PyPI 安装测试通过
- [ ] GitHub Release 页面正常
- [ ] 文档链接正常
- [ ] 通知用户（邮件列表、社交媒体等）

## 回滚流程

如果发布后发现严重问题：

### 1. PyPI 回滚

PyPI 不支持删除已发布的版本，但可以：

```bash
# 发布修复版本
./bump_version.sh 0.2.1
# 修复问题
./build.sh
./publish.sh prod
```

### 2. 标记为 Yanked

```bash
# 使用 twine 标记版本为 yanked
python3 -m twine upload --skip-existing --repository pypi dist/*
# 然后在 PyPI 网页上标记为 yanked
```

### 3. Git 回滚

```bash
# 删除远程标签
git push --delete origin v0.2.0

# 删除本地标签
git tag -d v0.2.0

# 回滚提交（如果需要）
git revert <commit-hash>
git push origin main
```

## 自动化发布

### GitHub Actions 工作流

创建 `.github/workflows/release.yml`：

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build-and-publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine

      - name: Build package
        run: python -m build

      - name: Check package
        run: twine check dist/*

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
        run: twine upload dist/*

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          files: dist/*
          body_path: CHANGELOG.md
```

## 版本策略

遵循语义化版本（Semantic Versioning）：

- **主版本号（Major）**：不兼容的 API 变更
- **次版本号（Minor）**：向后兼容的功能新增
- **修订号（Patch）**：向后兼容的问题修复

示例：
- `0.1.0` → `0.2.0`：新增功能
- `0.2.0` → `0.2.1`：bug 修复
- `0.2.1` → `1.0.0`：稳定版本，API 冻结

## 支持的 Python 版本

当前支持：
- Python 3.11
- Python 3.12

计划支持：
- Python 3.13（下一个版本）

停止支持：
- 当 Python 版本达到 EOL（End of Life）时

## 许可证

确保所有文件包含正确的许可证头：

```python
# Copyright (c) 2026 P2P Platform Team
# Licensed under the MIT License
```

## 联系方式

发布相关问题：
- Email: dev@p2p-platform.example.com
- GitHub Issues: https://github.com/p2p-platform/python-sdk/issues
