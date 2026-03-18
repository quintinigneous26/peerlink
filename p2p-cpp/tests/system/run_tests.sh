#!/bin/bash

set -e

echo "=== P2P Platform System Tests ==="
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
echo "Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be healthy..."
sleep 15

# Run tests
echo
echo "Running system tests..."
echo

pytest scenarios/ -v --tb=short --timeout=120

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
    echo "✅ All system tests passed!"
else
    echo
    echo "❌ Some tests failed"
fi

exit $TEST_EXIT_CODE
