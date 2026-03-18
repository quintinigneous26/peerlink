#!/usr/bin/env bash
set -euo pipefail

# Conda Package Build Script
# Builds conda package for p2p-sdk

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=== Conda Package Build Script ==="

# Check if conda-build is installed
if ! command -v conda-build &> /dev/null; then
    echo "Error: conda-build not found"
    echo "Install with: conda install conda-build"
    exit 1
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info src/*.egg-info

# Build conda package
echo "Building conda package..."
conda-build conda/

echo ""
echo "=== Build Complete ==="
echo ""
echo "To install locally:"
echo "  conda install --use-local p2p-sdk"
echo ""
echo "To upload to Anaconda Cloud:"
echo "  anaconda upload <path-to-package>"
echo ""
echo "Find package path with:"
echo "  conda-build conda/ --output"
