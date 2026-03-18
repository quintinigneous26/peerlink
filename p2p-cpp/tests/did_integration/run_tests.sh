#!/bin/bash

set -e

echo "=== DID Service Integration Tests ==="
echo

# Check dependencies
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose not found"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

# Setup Python environment
echo "Setting up Python environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt

# Start services
echo "Starting DID service and Redis..."
docker-compose up -d

# Wait for services
echo "Waiting for services to be ready..."
sleep 10

# Run tests
echo
echo "Running DID integration tests..."
echo

pytest scenarios/ -v --tb=short --timeout=60

# Capture exit code
TEST_EXIT_CODE=$?

# Cleanup
echo
echo "Cleaning up..."
docker-compose down -v

# Deactivate venv
deactivate

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo
    echo "✅ All DID integration tests passed!"
else
    echo
    echo "❌ Some tests failed"
fi

exit $TEST_EXIT_CODE
