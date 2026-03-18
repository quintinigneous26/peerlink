#!/usr/bin/env bash
set -euo pipefail

# PyPI Upload Script
# Uploads built packages to PyPI or Test PyPI

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if dist/ exists
if [ ! -d "dist" ] || [ -z "$(ls -A dist)" ]; then
    echo "Error: No packages found in dist/"
    echo "Run ./build.sh first"
    exit 1
fi

# Parse arguments
REPOSITORY="pypi"
if [ $# -gt 0 ]; then
    case "$1" in
        test|testpypi)
            REPOSITORY="testpypi"
            ;;
        prod|pypi)
            REPOSITORY="pypi"
            ;;
        *)
            echo "Usage: $0 [test|prod]"
            echo "  test - Upload to Test PyPI"
            echo "  prod - Upload to PyPI (default)"
            exit 1
            ;;
    esac
fi

echo "=== PyPI Upload Script ==="
echo "Repository: $REPOSITORY"
echo ""

# Check packages
echo "Packages to upload:"
ls -lh dist/
echo ""

# Verify packages
echo "Verifying packages..."
python3 -m twine check dist/*
echo ""

# Confirm upload
if [ "$REPOSITORY" = "pypi" ]; then
    echo "WARNING: You are about to upload to PRODUCTION PyPI!"
    echo "This action cannot be undone."
    read -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Upload cancelled"
        exit 0
    fi
fi

# Upload
echo "Uploading to $REPOSITORY..."
if [ "$REPOSITORY" = "testpypi" ]; then
    python3 -m twine upload --repository testpypi dist/*
else
    python3 -m twine upload dist/*
fi

echo ""
echo "Upload complete!"
if [ "$REPOSITORY" = "testpypi" ]; then
    echo ""
    echo "To install from Test PyPI:"
    echo "  pip install --index-url https://test.pypi.org/simple/ p2p-sdk"
fi
