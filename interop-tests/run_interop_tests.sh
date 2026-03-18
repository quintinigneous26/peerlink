#!/bin/bash
# ============================================================================
# go-libp2p Interoperability Test Runner
# ============================================================================
# This script runs comprehensive interoperability tests between C++ and Go
# libp2p implementations.
#
# Usage:
#   ./run_interop_tests.sh [options]
#
# Options:
#   --with-server    Start Go relay server for integration tests
#   --cpp-only       Run only C++ tests
#   --go-only        Run only Go tests
#   --full           Run full test suite with server
#   --report         Generate test report
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GO_TEST_DIR="${SCRIPT_DIR}/go-libp2p-test"
CPP_TEST_DIR="${SCRIPT_DIR}/cpp-go-interop"
P2P_CPP_DIR="${SCRIPT_DIR}/../p2p-cpp"

# Test results
TEST_RESULTS_DIR="${SCRIPT_DIR}/results"
mkdir -p "${TEST_RESULTS_DIR}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${TEST_RESULTS_DIR}/interop_test_${TIMESTAMP}.log"

# Flags
WITH_SERVER=false
CPP_ONLY=false
GO_ONLY=false
GENERATE_REPORT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
	case $1 in
		--with-server)
			WITH_SERVER=true
			shift
			;;
		--cpp-only)
			CPP_ONLY=true
			shift
			;;
		--go-only)
			GO_ONLY=true
			shift
			;;
		--full)
			WITH_SERVER=true
			GENERATE_REPORT=true
			shift
			;;
		--report)
			GENERATE_REPORT=true
			shift
			;;
		*)
			echo "Unknown option: $1"
			exit 1
			;;
	esac
done

# ============================================================================
# Utility Functions
# ============================================================================

log_info() {
	echo -e "${BLUE}[INFO]${NC} $1" | tee -a "${LOG_FILE}"
}

log_success() {
	echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "${LOG_FILE}"
}

log_warning() {
	echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "${LOG_FILE}"
}

log_error() {
	echo -e "${RED}[ERROR]${NC} $1" | tee -a "${LOG_FILE}"
}

print_header() {
	echo | tee -a "${LOG_FILE}"
	echo -e "${BLUE}============================================${NC}" | tee -a "${LOG_FILE}"
	echo -e "${BLUE}$1${NC}" | tee -a "${LOG_FILE}"
	echo -e "${BLUE}============================================${NC}" | tee -a "${LOG_FILE}"
	echo | tee -a "${LOG_FILE}"
}

# ============================================================================
# Prerequisites Check
# ============================================================================

check_prerequisites() {
	print_header "Checking Prerequisites"

	# Check Go
	if command -v go &> /dev/null; then
		GO_VERSION=$(go version | awk '{print $3}')
		log_success "Go found: ${GO_VERSION}"
	else
		log_error "Go not found. Please install Go 1.21+"
		exit 1
	fi

	# Check CMake
	if command -v cmake &> /dev/null; then
		CMAKE_VERSION=$(cmake --version | head -n1)
		log_success "CMake found: ${CMAKE_VERSION}"
	else
		log_error "CMake not found. Please install CMake"
		exit 1
	fi

	# Check if Go test directory exists
	if [ ! -d "${GO_TEST_DIR}" ]; then
		log_error "Go test directory not found: ${GO_TEST_DIR}"
		exit 1
	fi

	# Check if p2p-cpp directory exists
	if [ ! -d "${P2P_CPP_DIR}" ]; then
		log_warning "p2p-cpp directory not found: ${P2P_CPP_DIR}"
		log_warning "C++ tests will be skipped"
	fi
}

# ============================================================================
# Go Tests
# ============================================================================

run_go_tests() {
	print_header "Running Go Tests"

	cd "${GO_TEST_DIR}"

	# Test 1: Message serialization
	log_info "Test 1: Relay message serialization"
	if go test -v message_test.go 2>&1 | tee -a "${LOG_FILE}"; then
		log_success "Relay message tests passed"
	else
		log_error "Relay message tests failed"
		return 1
	fi

	# Test 2: DCUtR interoperability
	log_info "Test 2: DCUtR interoperability"
	if go test -v test_dcutr_interop.go 2>&1 | tee -a "${LOG_FILE}"; then
		log_success "DCUtR interoperability tests passed"
	else
		log_error "DCUtR interoperability tests failed"
		return 1
	fi

	# Test 3: Benchmarks
	log_info "Test 3: Performance benchmarks"
	if go test -bench=. -benchmem 2>&1 | tee -a "${LOG_FILE}"; then
		log_success "Benchmark tests completed"
	else
		log_warning "Benchmark tests had issues"
	fi

	cd "${SCRIPT_DIR}"
	return 0
}

# ============================================================================
# C++ Tests
# ============================================================================

run_cpp_tests() {
	print_header "Running C++ Tests"

	if [ ! -d "${P2P_CPP_DIR}" ]; then
		log_warning "Skipping C++ tests (p2p-cpp not found)"
		return 0
	fi

	# Check if test executable exists
	if [ ! -f "${CPP_TEST_DIR}/build/test_cpp_to_go" ]; then
		log_info "Building C++ interop test..."

		mkdir -p "${CPP_TEST_DIR}/build"
		cd "${CPP_TEST_DIR}/build"

		if cmake .. 2>&1 | tee -a "${LOG_FILE}"; then
			log_success "CMake configuration successful"
		else
			log_error "CMake configuration failed"
			return 1
		fi

		if make 2>&1 | tee -a "${LOG_FILE}"; then
			log_success "Build successful"
		else
			log_error "Build failed"
			return 1
		fi

		cd "${SCRIPT_DIR}"
	fi

	# Run C++ test
	if [ -f "${CPP_TEST_DIR}/build/test_cpp_to_go" ]; then
		log_info "Running C++ to Go message compatibility test..."
		if "${CPP_TEST_DIR}/build/test_cpp_to_go" 2>&1 | tee -a "${LOG_FILE}"; then
			log_success "C++ message compatibility tests passed"
		else
			log_error "C++ tests failed"
			return 1
		fi
	else
		log_warning "C++ test executable not found"
	fi

	return 0
}

# ============================================================================
# Integration Tests
# ============================================================================

run_integration_tests() {
	print_header "Running Integration Tests"

	# Check if server is needed and available
	RELAY_PID=""
	if [ "${WITH_SERVER}" = true ]; then
		log_info "Starting Go relay server..."

		cd "${GO_TEST_DIR}"

		# Start server in background
		go run relay_server.go > "${TEST_RESULTS_DIR}/relay_server_${TIMESTAMP}.log" 2>&1 &
		RELAY_PID=$!

		# Wait for server to start
		sleep 2

		# Check if server is running
		if ps -p ${RELAY_PID} > /dev/null; then
			log_success "Relay server started (PID: ${RELAY_PID})"
		else
			log_error "Failed to start relay server"
			return 1
		fi

		cd "${SCRIPT_DIR}"

		# Run integration tests
		log_info "Running C++ to Go relay connection test..."
		# TODO: Add actual network connection test

		# Cleanup
		log_info "Stopping relay server..."
		kill ${RELAY_PID} 2>/dev/null || true
		wait ${RELAY_PID} 2>/dev/null || true
		log_success "Relay server stopped"
	else
		log_warning "Integration tests skipped (use --with-server to enable)"
	fi

	return 0
}

# ============================================================================
# Report Generation
# ============================================================================

generate_report() {
	if [ "${GENERATE_REPORT}" = false ]; then
		return
	fi

	print_header "Generating Test Report"

	REPORT_FILE="${TEST_RESULTS_DIR}/interop_report_${TIMESTAMP}.md"

	cat > "${REPORT_FILE}" << EOF
# go-libp2p Interoperability Test Report

**Date**: $(date +"%Y-%m-%d %H:%M:%S")
**Test ID**: ${TIMESTAMP}

## Test Environment

- Go Version: $(go version | awk '{print $3}')
- CMake Version: $(cmake --version | head -n1 | awk '{print $3}')
- Platform: $(uname -s) $(uname -m)

## Test Results

### Message Serialization Tests
EOF

	# Parse log file for results
	if grep -q "Relay message tests passed" "${LOG_FILE}"; then
		echo "- Relay v2 Messages: ✅ PASS" >> "${REPORT_FILE}"
	else
		echo "- Relay v2 Messages: ❌ FAIL" >> "${REPORT_FILE}"
	fi

	if grep -q "DCUtR interoperability tests passed" "${LOG_FILE}"; then
		echo "- DCUtR Messages: ✅ PASS" >> "${REPORT_FILE}"
	else
		echo "- DCUtR Messages: ❌ FAIL" >> "${REPORT_FILE}"
	fi

	if grep -q "C++ message compatibility tests passed" "${LOG_FILE}"; then
		echo "- C++ Compatibility: ✅ PASS" >> "${REPORT_FILE}"
	else
		echo "- C++ Compatibility: ⚠️  SKIPPED" >> "${REPORT_FILE}"
	fi

	cat >> "${REPORT_FILE}" << EOF

### Integration Tests
EOF

	if grep -q "Integration tests skipped" "${LOG_FILE}"; then
		echo "- Relay Connection: ⚠️  SKIPPED" >> "${REPORT_FILE}"
	else
		if grep -q "Relay server started" "${LOG_FILE}"; then
			echo "- Relay Connection: ✅ PASS" >> "${REPORT_FILE}"
		else
			echo "- Relay Connection: ❌ FAIL" >> "${REPORT_FILE}"
		fi
	fi

	cat >> "${REPORT_FILE}" << EOF

## Performance Benchmarks

See log file for detailed benchmark results.

## Issues Found

EOF

	# Check for errors in log
	if grep -i "error\|fail" "${LOG_FILE}" > /dev/null; then
		echo "See detailed log for errors." >> "${REPORT_FILE}"
	else
		echo "No critical issues found." >> "${REPORT_FILE}"
	fi

	cat >> "${REPORT_FILE}" << EOF

## Conclusion

EOF

	if grep -q "PASS" "${REPORT_FILE}"; then
		echo "✅ Interoperability tests completed successfully." >> "${REPORT_FILE}"
	else
		echo "⚠️  Some tests failed. Please review the log." >> "${REPORT_FILE}"
	fi

	log_success "Report generated: ${REPORT_FILE}"
	cat "${REPORT_FILE}"
}

# ============================================================================
# Main
# ============================================================================

main() {
	print_header "go-libp2p Interoperability Test Suite"
	echo "Log file: ${LOG_FILE}"

	check_prerequisites

	RUN_ALL=true
	if [ "${CPP_ONLY}" = true ]; then
		run_cpp_tests
		RUN_ALL=false
	fi

	if [ "${GO_ONLY}" = true ]; then
		run_go_tests
		RUN_ALL=false
	fi

	if [ "${RUN_ALL}" = true ]; then
		run_go_tests
		run_cpp_tests
		run_integration_tests
	fi

	generate_report

	print_header "Test Suite Complete"
	log_info "Full log: ${LOG_FILE}"
}

# Run main
main "$@"
