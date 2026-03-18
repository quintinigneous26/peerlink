#!/bin/bash
# 测试运行脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# 打印带颜色的消息
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    print_info "检查依赖..."

    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 未安装"
        exit 1
    fi

    if ! python3 -c "import pytest" &> /dev/null; then
        print_info "安装测试依赖..."
        pip install -e ".[dev]"
    fi
}

# 运行单元测试
run_unit_tests() {
    print_info "运行单元测试..."
    pytest tests/unit/ \
        -v \
        --cov=. \
        --cov-report=term-missing:skip-covered \
        --cov-report=html:htmlcov \
        --cov-report=xml \
        --timeout=300 \
        --tb=short \
        "$@"
}

# 运行集成测试
run_integration_tests() {
    print_info "运行集成测试..."
    pytest tests/integration/ \
        -v \
        -m "not stress and not nat" \
        --cov=. \
        --cov-append \
        --cov-report=term-missing:skip-covered \
        --timeout=600 \
        --tb=short \
        "$@"
}

# 运行NAT穿透测试
run_nat_tests() {
    print_info "运行NAT穿透测试..."
    pytest tests/integration/test_nat_penetration.py \
        -v \
        -m nat \
        --timeout=300 \
        --tb=short \
        "$@"
}

# 运行压力测试
run_stress_tests() {
    print_info "运行压力测试..."
    pytest tests/stress/ \
        -v \
        -m stress \
        --timeout=900 \
        --tb=short \
        "$@"
}

# 运行Locust压力测试
run_locust() {
    print_info "启动Locust压力测试..."
    locust -f tests/stress/locustfile.py "$@"
}

# 运行所有测试
run_all_tests() {
    print_info "运行所有测试..."

    # 单元测试
    run_unit_tests

    # 集成测试
    run_integration_tests

    # NAT测试
    run_nat_tests

    print_info "所有测试完成!"
}

# 运行快速测试 (开发时使用)
run_quick_tests() {
    print_info "运行快速测试..."
    pytest tests/unit/ \
        -v \
        --timeout=60 \
        -k "not slow" \
        "$@"
}

# 生成覆盖率报告
generate_coverage() {
    print_info "生成覆盖率报告..."
    pytest tests/ \
        --cov=. \
        --cov-report=html:htmlcov \
        --cov-report=term \
        --cov-report=xml

    print_info "覆盖率报告已生成: htmlcov/index.html"
}

# 清理测试产物
clean() {
    print_info "清理测试产物..."
    rm -rf .pytest_cache
    rm -rf htmlcov
    rm -rf .coverage
    rm -rf coverage.xml
    rm -rf __pycache__
    rm -rf **/__pycache__
    rm -rf **/.pytest_cache
    print_info "清理完成"
}

# 显示帮助信息
show_help() {
    cat << EOF
P2P平台测试脚本

用法: ./scripts/run_tests.sh [命令] [选项]

命令:
    all             运行所有测试
    unit            运行单元测试
    integration     运行集成测试
    nat             运行NAT穿透测试
    stress          运行压力测试
    locust          启动Locust压力测试
    quick           运行快速测试 (开发用)
    coverage        生成覆盖率报告
    clean           清理测试产物
    help            显示此帮助信息

示例:
    ./scripts/run_tests.sh all
    ./scripts/run_tests.sh unit
    ./scripts/run_tests.sh unit -k test_stun
    ./scripts/run_tests.sh locust --headless -u 100 -r 10 -t 60s
EOF
}

# 主函数
main() {
    check_dependencies

    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi

    case "$1" in
        all)
            run_all_tests
            ;;
        unit)
            shift
            run_unit_tests "$@"
            ;;
        integration)
            shift
            run_integration_tests "$@"
            ;;
        nat)
            shift
            run_nat_tests "$@"
            ;;
        stress)
            shift
            run_stress_tests "$@"
            ;;
        locust)
            shift
            run_locust "$@"
            ;;
        quick)
            shift
            run_quick_tests "$@"
            ;;
        coverage)
            generate_coverage
            ;;
        clean)
            clean
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "未知命令: $1"
            show_help
            exit 1
            ;;
    esac
}

main "$@"
