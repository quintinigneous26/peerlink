# 开发规范

## 编码风格

遵循PEP 8规范，使用以下工具：

```bash
# 代码格式化
black src/ tests/

# 类型检查
mypy src/

# 导入排序
isort src/ tests/

# 代码检查
flake8 src/ tests/
```

## 测试规范

### 测试覆盖率要求

- 单元测试覆盖率 >= 80%
- 关键路径覆盖率 = 100%

### 测试命名

```python
def test_<function>_<scenario>_<expected_result>():
    """Test description."""
    # Given
    input_data = ...

    # When
    result = function_under_test(input_data)

    # Then
    assert result == expected
```

## Git提交规范

```
<type>: <description>

<optional body>

<optional footer>
```

### 类型 (type)

- `feat`: 新功能
- `fix`: 修复bug
- `refactor`: 重构
- `docs`: 文档
- `test`: 测试
- `chore`: 构建/工具

### 示例

```
feat(stun): implement NAT type detection

Add support for detecting Full Cone, Restricted Cone,
Port Restricted, and Symmetric NAT types.

Closes #4
```

## 代码审查清单

- [ ] 代码符合PEP 8规范
- [ ] 所有函数有文档字符串
- [ ] 测试覆盖率 >= 80%
- [ ] 无硬编码配置值
- [ ] 错误处理完整
- [ ] 无安全漏洞

## 部署流程

1. 更新版本号
2. 运行完整测试套件
3. 构建Docker镜像
4. 推送到镜像仓库
5. 更新docker-compose.yml
6. 部署到生产环境
