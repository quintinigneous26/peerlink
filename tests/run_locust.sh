#!/bin/bash
# Locust 负载测试运行脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "======================================"
echo "P2P Platform 负载测试 (Locust)"
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
echo "启动 Locust Web UI..."
echo ""
echo "访问 http://localhost:8089 开始测试"
echo "按 Ctrl+C 停止测试"
echo ""

cd "$PROJECT_ROOT"

# 运行 Locust
locust -f tests/stress/locustfile.py \
    --host=http://localhost:8080 \
    --port=8089 \
    --html=tests/reports/locust/$(date +%Y%m%d_%H%M%S).html
