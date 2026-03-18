#!/bin/bash
# 模糊测试运行脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORTS_DIR="$PROJECT_ROOT/tests/reports/fuzz"

# 创建报告目录
mkdir -p "$REPORTS_DIR"

echo "======================================"
echo "P2P Platform 模糊测试"
echo "======================================"
echo ""

# 激活虚拟环境（如果存在）
if [ -d "$PROJECT_ROOT/.venv" ]; then
    echo "激活虚拟环境..."
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# 安装测试依赖
echo "安装测试依赖..."
pip install -q -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "运行模糊测试..."
echo ""

cd "$PROJECT_ROOT"

# Multistream Select 模糊测试
echo "1. Multistream Select 协议模糊测试..."
pytest tests/fuzz/fuzz_multistream.py \
    -v \
    --hypothesis-seed=0 \
    --html="$REPORTS_DIR/multistream.html" \
    --self-contained-html \
    || echo "Multistream 测试完成（可能有失败）"

echo ""

# Noise 协议模糊测试
echo "2. Noise 协议模糊测试..."
pytest tests/fuzz/fuzz_noise.py \
    -v \
    --hypothesis-seed=0 \
    --html="$REPORTS_DIR/noise.html" \
    --self-contained-html \
    || echo "Noise 测试完成（可能有失败）"

echo ""

# Yamux 协议模糊测试
echo "3. Yamux 协议模糊测试..."
pytest tests/fuzz/fuzz_yamux.py \
    -v \
    --hypothesis-seed=0 \
    --html="$REPORTS_DIR/yamux.html" \
    --self-contained-html \
    || echo "Yamux 测试完成（可能有失败）"

echo ""
echo "======================================"
echo "模糊测试完成"
echo "======================================"
echo ""
echo "报告位置: $REPORTS_DIR"
echo "  - multistream.html"
echo "  - noise.html"
echo "  - yamux.html"
echo ""
