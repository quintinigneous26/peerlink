#!/bin/bash
# P2P Platform 性能基准测试执行脚本
# 测试工程师: tester-1

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 报告目录
REPORT_DIR="$PROJECT_ROOT/tests/reports/performance"
mkdir -p "$REPORT_DIR"

# 时间戳
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}P2P Platform 性能基准测试${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查依赖
echo -e "${YELLOW}[1/6] 检查测试依赖...${NC}"
python -c "import pytest; import psutil" 2>/dev/null || {
    echo -e "${RED}缺少测试依赖，正在安装...${NC}"
    pip install -q pytest pytest-asyncio pytest-cov pytest-benchmark psutil
}
echo -e "${GREEN}✓ 依赖检查完成${NC}"
echo ""

# 运行延迟测试
echo -e "${YELLOW}[2/6] 运行延迟测试...${NC}"
pytest tests/benchmark/test_latency.py -v \
    --tb=short \
    --html="$REPORT_DIR/latency_${TIMESTAMP}.html" \
    --self-contained-html \
    | tee "$REPORT_DIR/latency_${TIMESTAMP}.log"
echo -e "${GREEN}✓ 延迟测试完成${NC}"
echo ""

# 运行吞吐量测试
echo -e "${YELLOW}[3/6] 运行吞吐量测试...${NC}"
pytest tests/benchmark/test_throughput.py -v \
    --tb=short \
    --html="$REPORT_DIR/throughput_${TIMESTAMP}.html" \
    --self-contained-html \
    | tee "$REPORT_DIR/throughput_${TIMESTAMP}.log"
echo -e "${GREEN}✓ 吞吐量测试完成${NC}"
echo ""

# 运行并发测试
echo -e "${YELLOW}[4/6] 运行并发测试...${NC}"
pytest tests/benchmark/test_concurrent.py -v \
    --tb=short \
    --html="$REPORT_DIR/concurrent_${TIMESTAMP}.html" \
    --self-contained-html \
    | tee "$REPORT_DIR/concurrent_${TIMESTAMP}.log"
echo -e "${GREEN}✓ 并发测试完成${NC}"
echo ""

# 运行覆盖率测试
echo -e "${YELLOW}[5/6] 运行覆盖率测试...${NC}"
pytest tests/ -v \
    --cov=p2p_engine \
    --cov-report=html:"$REPORT_DIR/coverage_${TIMESTAMP}" \
    --cov-report=term-missing \
    --tb=short \
    | tee "$REPORT_DIR/coverage_${TIMESTAMP}.log"
echo -e "${GREEN}✓ 覆盖率测试完成${NC}"
echo ""

# 生成汇总报告
echo -e "${YELLOW}[6/6] 生成汇总报告...${NC}"
cat > "$REPORT_DIR/summary_${TIMESTAMP}.md" << EOF
# 性能基准测试汇总报告

## 测试信息
- 执行时间: $(date)
- 测试环境: $(uname -a)
- Python 版本: $(python --version)

## 测试结果

### 延迟测试
详见: latency_${TIMESTAMP}.html

### 吞吐量测试
详见: throughput_${TIMESTAMP}.html

### 并发测试
详见: concurrent_${TIMESTAMP}.html

### 代码覆盖率
详见: coverage_${TIMESTAMP}/index.html

## 快速统计

EOF

# 提取测试统计
echo "### 延迟测试" >> "$REPORT_DIR/summary_${TIMESTAMP}.md"
grep "passed\|failed\|skipped" "$REPORT_DIR/latency_${TIMESTAMP}.log" | tail -1 >> "$REPORT_DIR/summary_${TIMESTAMP}.md"
echo "" >> "$REPORT_DIR/summary_${TIMESTAMP}.md"

echo "### 吞吐量测试" >> "$REPORT_DIR/summary_${TIMESTAMP}.md"
grep "passed\|failed\|skipped" "$REPORT_DIR/throughput_${TIMESTAMP}.log" | tail -1 >> "$REPORT_DIR/summary_${TIMESTAMP}.md"
echo "" >> "$REPORT_DIR/summary_${TIMESTAMP}.md"

echo "### 并发测试" >> "$REPORT_DIR/summary_${TIMESTAMP}.md"
grep "passed\|failed\|skipped" "$REPORT_DIR/concurrent_${TIMESTAMP}.log" | tail -1 >> "$REPORT_DIR/summary_${TIMESTAMP}.md"
echo "" >> "$REPORT_DIR/summary_${TIMESTAMP}.md"

echo "### 代码覆盖率" >> "$REPORT_DIR/summary_${TIMESTAMP}.md"
grep "TOTAL" "$REPORT_DIR/coverage_${TIMESTAMP}.log" | tail -1 >> "$REPORT_DIR/summary_${TIMESTAMP}.md"

echo -e "${GREEN}✓ 汇总报告已生成: $REPORT_DIR/summary_${TIMESTAMP}.md${NC}"
echo ""

# 创建最新报告链接
ln -sf "summary_${TIMESTAMP}.md" "$REPORT_DIR/latest_summary.md"
ln -sf "latency_${TIMESTAMP}.html" "$REPORT_DIR/latest_latency.html"
ln -sf "throughput_${TIMESTAMP}.html" "$REPORT_DIR/latest_throughput.html"
ln -sf "concurrent_${TIMESTAMP}.html" "$REPORT_DIR/latest_concurrent.html"

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}性能基准测试完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "报告目录: ${GREEN}$REPORT_DIR${NC}"
echo -e "汇总报告: ${GREEN}$REPORT_DIR/summary_${TIMESTAMP}.md${NC}"
echo -e "HTML 报告: ${GREEN}$REPORT_DIR/latest_*.html${NC}"
echo ""
echo -e "查看报告:"
echo -e "  open $REPORT_DIR/latest_summary.md"
echo -e "  open $REPORT_DIR/latest_latency.html"
echo ""
