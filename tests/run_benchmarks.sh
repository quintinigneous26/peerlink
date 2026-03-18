#!/bin/bash
# 性能测试运行脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORTS_DIR="$PROJECT_ROOT/tests/reports/performance"

# 创建报告目录
mkdir -p "$REPORTS_DIR"

echo "======================================"
echo "P2P Platform 性能基准测试"
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
echo "运行性能测试..."
echo ""

# 运行性能测试
cd "$PROJECT_ROOT"

# 延迟测试
echo "1. 延迟测试..."
pytest tests/benchmark/test_latency.py \
    -v \
    -m "benchmark" \
    --html="$REPORTS_DIR/latency.html" \
    --self-contained-html \
    --json-report \
    --json-report-file="$REPORTS_DIR/latency.json" \
    || echo "延迟测试完成（可能有失败）"

echo ""

# 吞吐量测试
echo "2. 吞吐量测试..."
pytest tests/benchmark/test_throughput.py \
    -v \
    -m "benchmark" \
    --html="$REPORTS_DIR/throughput.html" \
    --self-contained-html \
    --json-report \
    --json-report-file="$REPORTS_DIR/throughput.json" \
    || echo "吞吐量测试完成（可能有失败）"

echo ""

# 并发测试
echo "3. 并发连接测试..."
pytest tests/benchmark/test_concurrent.py \
    -v \
    -m "benchmark" \
    --html="$REPORTS_DIR/concurrent.html" \
    --self-contained-html \
    --json-report \
    --json-report-file="$REPORTS_DIR/concurrent.json" \
    || echo "并发测试完成（可能有失败）"

echo ""
echo "======================================"
echo "性能测试完成"
echo "======================================"
echo ""
echo "报告位置: $REPORTS_DIR"
echo "  - latency.html"
echo "  - throughput.html"
echo "  - concurrent.html"
echo ""
