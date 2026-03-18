#!/bin/bash
# Python 源码编译和混淆脚本
# 将 Python 源码编译为字节码或使用 Cython 编译为 C 扩展

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/compiled"

echo "=========================================="
echo "P2P Platform 源码保护编译"
echo "=========================================="
echo ""

# 检查 Python 版本
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python 版本: $PYTHON_VERSION"

# 选择编译方式
echo ""
echo "选择编译方式:"
echo "1) 字节码编译 (.pyc) - 快速，基础保护"
echo "2) Cython 编译 (.so) - 最强保护，需要编译器"
echo "3) PyInstaller 打包 - 单文件可执行"
echo "4) Nuitka 编译 - 完整编译为机器码"
echo ""
read -p "请选择 (1-4): " COMPILE_METHOD

case $COMPILE_METHOD in
    1)
        echo ""
        echo "=== 方式 1: 字节码编译 ==="
        ;;
    2)
        echo ""
        echo "=== 方式 2: Cython 编译 ==="
        ;;
    3)
        echo ""
        echo "=== 方式 3: PyInstaller 打包 ==="
        ;;
    4)
        echo ""
        echo "=== 方式 4: Nuitka 编译 ==="
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac

# 创建构建目录
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# 方式 1: 字节码编译
compile_to_bytecode() {
    echo "编译 Python 源码为字节码..."

    # 编译所有服务器组件
    for component in stun-server relay-server signaling-server did-service; do
        echo "  编译 $component..."
        python3 -m compileall -b "$PROJECT_ROOT/$component/src" -d "/opt/p2p-platform/$component/src"

        # 复制编译后的 .pyc 文件
        mkdir -p "$BUILD_DIR/$component/src"
        find "$PROJECT_ROOT/$component/src" -name "*.pyc" -exec cp {} "$BUILD_DIR/$component/src/" \;

        # 删除源码，只保留字节码
        find "$BUILD_DIR/$component/src" -name "*.py" -delete

        # 复制其他必要文件
        cp "$PROJECT_ROOT/$component/requirements.txt" "$BUILD_DIR/$component/" 2>/dev/null || true
        cp "$PROJECT_ROOT/$component/Dockerfile" "$BUILD_DIR/$component/" 2>/dev/null || true
    done

    echo "✅ 字节码编译完成"
    echo "输出目录: $BUILD_DIR"
}

# 方式 2: Cython 编译
compile_with_cython() {
    echo "使用 Cython 编译为 C 扩展..."

    # 检查 Cython 是否安装
    if ! python3 -c "import Cython" 2>/dev/null; then
        echo "安装 Cython..."
        pip3 install Cython
    fi

    # 为每个组件创建 setup.py
    for component in stun-server relay-server signaling-server did-service; do
        echo "  编译 $component..."

        cd "$PROJECT_ROOT/$component"

        # 创建临时 setup.py
        cat > setup_temp.py << 'EOF'
from setuptools import setup
from Cython.Build import cythonize
import glob

# 查找所有 .py 文件
py_files = []
for root, dirs, files in os.walk('src'):
    for file in files:
        if file.endswith('.py') and file != '__init__.py':
            py_files.append(os.path.join(root, file))

setup(
    ext_modules=cythonize(
        py_files,
        compiler_directives={
            'language_level': '3',
            'embedsignature': True,
        }
    )
)
EOF

        # 编译
        python3 setup_temp.py build_ext --inplace

        # 复制编译结果
        mkdir -p "$BUILD_DIR/$component/src"
        find src -name "*.so" -exec cp {} "$BUILD_DIR/$component/src/" \;
        find src -name "__init__.py" -exec cp {} "$BUILD_DIR/$component/src/" \;

        # 清理
        rm -f setup_temp.py
        rm -rf build

        # 复制其他文件
        cp requirements.txt "$BUILD_DIR/$component/" 2>/dev/null || true
        cp Dockerfile "$BUILD_DIR/$component/" 2>/dev/null || true
    done

    echo "✅ Cython 编译完成"
    echo "输出目录: $BUILD_DIR"
}

# 方式 3: PyInstaller 打包
compile_with_pyinstaller() {
    echo "使用 PyInstaller 打包为可执行文件..."

    # 检查 PyInstaller 是否安装
    if ! command -v pyinstaller &> /dev/null; then
        echo "安装 PyInstaller..."
        pip3 install pyinstaller
    fi

    for component in stun-server relay-server signaling-server did-service; do
        echo "  打包 $component..."

        cd "$PROJECT_ROOT/$component"

        # 查找主入口文件
        MAIN_FILE=$(find src -name "main.py" -o -name "server.py" | head -1)

        if [ -n "$MAIN_FILE" ]; then
            pyinstaller --onefile \
                --name "$component" \
                --distpath "$BUILD_DIR/$component/bin" \
                --workpath "$BUILD_DIR/$component/build" \
                --specpath "$BUILD_DIR/$component" \
                "$MAIN_FILE"
        fi
    done

    echo "✅ PyInstaller 打包完成"
    echo "输出目录: $BUILD_DIR"
}

# 方式 4: Nuitka 编译
compile_with_nuitka() {
    echo "使用 Nuitka 编译为机器码..."

    # 检查 Nuitka 是否安装
    if ! command -v nuitka3 &> /dev/null; then
        echo "安装 Nuitka..."
        pip3 install nuitka
    fi

    for component in stun-server relay-server signaling-server did-service; do
        echo "  编译 $component..."

        cd "$PROJECT_ROOT/$component"

        # 查找主入口文件
        MAIN_FILE=$(find src -name "main.py" -o -name "server.py" | head -1)

        if [ -n "$MAIN_FILE" ]; then
            nuitka3 --standalone \
                --output-dir="$BUILD_DIR/$component" \
                --remove-output \
                "$MAIN_FILE"
        fi
    done

    echo "✅ Nuitka 编译完成"
    echo "输出目录: $BUILD_DIR"
}

# 执行选择的编译方式
case $COMPILE_METHOD in
    1)
        compile_to_bytecode
        ;;
    2)
        compile_with_cython
        ;;
    3)
        compile_with_pyinstaller
        ;;
    4)
        compile_with_nuitka
        ;;
esac

echo ""
echo "=========================================="
echo "编译完成！"
echo "=========================================="
echo ""
echo "编译后的文件位于: $BUILD_DIR"
echo ""
echo "下一步:"
echo "1. 测试编译后的程序"
echo "2. 使用编译后的文件构建 RPM/DEB 包"
echo "3. 部署到生产环境"
echo ""
