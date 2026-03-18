#!/usr/bin/env bash
set -euo pipefail

# P2P SDK Build Script
# Builds Python wheel and source distribution

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== P2P SDK Build Script ==="
echo "Building Python packages..."

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info src/*.egg-info

# Install build dependencies
echo "Installing build dependencies..."
python3 -m pip install --upgrade pip build twine

# Build wheel and sdist
echo "Building wheel and source distribution..."
python3 -m build

# Verify build
echo ""
echo "=== Build Complete ==="
echo "Generated packages:"
ls -lh dist/

# Check package
echo ""
echo "=== Package Check ==="
python3 -m twine check dist/*

echo ""
echo "Build successful!"
echo ""
echo "To install locally:"
echo "  pip install dist/p2p_sdk-*.whl"
echo ""
echo "To upload to PyPI:"
echo "  python3 -m twine upload dist/*"
echo ""
echo "To upload to Test PyPI:"
echo "  python3 -m twine upload --repository testpypi dist/*"
