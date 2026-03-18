#!/bin/bash
# 互操作性测试运行脚本

set -e

echo "========================================="
echo "p2p-platform 互操作性测试"
echo "========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查依赖
echo "检查测试依赖..."

# 检查 pytest
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}错误: pytest 未安装${NC}"
    echo "请运行: pip install pytest pytest-asyncio"
    exit 1
fi

echo -e "${GREEN}✓ pytest 已安装${NC}"

# 检查可选依赖
if python -c "import aioquic" 2>/dev/null; then
    echo -e "${GREEN}✓ aioquic 已安装 (QUIC 测试可用)${NC}"
else
    echo -e "${YELLOW}⚠ aioquic 未安装 (QUIC 测试将被跳过)${NC}"
fi

if python -c "import aiortc" 2>/dev/null; then
    echo -e "${GREEN}✓ aiortc 已安装 (WebRTC 测试可用)${NC}"
else
    echo -e "${YELLOW}⚠ aiortc 未安装 (WebRTC 测试将被跳过)${NC}"
fi

echo ""
echo "========================================="
echo "运行互操作性测试"
echo "========================================="
echo ""

# 创建结果目录
mkdir -p tests/interop/results

# 运行测试
echo "运行协议合规性测试..."
pytest tests/interop/ -v \
    --tb=short \
    --cov=p2p_engine \
    --cov-report=term-missing \
    --cov-report=html:tests/interop/results/coverage \
    -m "not (run_interop_tests or skip)" \
    | tee tests/interop/results/protocol_tests.log

echo ""
echo "========================================="
echo "测试结果摘要"
echo "========================================="
echo ""

# 检查是否需要运行外部互操作测试
if [[ "$*" == *"--run-interop-tests"* ]]; then
    echo -e "${YELLOW}运行需要外部节点的互操作测试...${NC}"
    pytest tests/interop/ -v \
        --tb=short \
        -m "run_interop_tests" \
        -k "go_libp2p or js_libp2p or browser" \
        | tee tests/interop/results/external_tests.log
else
    echo -e "${YELLOW}跳过需要外部节点的测试${NC}"
    echo "使用 --run-interop-tests 参数运行完整互操作测试"
fi

echo ""
echo "========================================="
echo "生成测试报告"
echo "========================================="
echo ""

# 生成汇总报告
python -c "
import re
import sys

# 读取测试日志
try:
    with open('tests/interop/results/protocol_tests.log', 'r') as f:
        log = f.read()

    # 提取测试结果
    passed = len(re.findall(r'PASSED', log))
    failed = len(re.findall(r'FAILED', log))
    skipped = len(re.findall(r'SKIPPED', log))
    total = passed + failed + skipped

    print(f'总测试数: {total}')
    print(f'通过: {passed}')
    print(f'失败: {failed}')
    print(f'跳过: {skipped}')

    if failed == 0:
        print('\\n✓ 所有协议合规性测试通过！')
        sys.exit(0)
    else:
        print(f'\\n✗ {failed} 个测试失败')
        sys.exit(1)
except Exception as e:
    print(f'无法生成报告: {e}')
    sys.exit(1)
"

echo ""
echo "详细报告: tests/interop/results/"
echo "覆盖率报告: tests/interop/results/coverage/index.html"
echo ""
