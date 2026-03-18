#!/bin/bash
# Build RPM package for P2P Platform
# Supports: CentOS 7+, RHEL 7+, Fedora 30+

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION="${VERSION:-1.0.0}"
RELEASE="${RELEASE:-1}"
ARCH="${ARCH:-noarch}"

echo "Building P2P Platform RPM package..."
echo "Version: $VERSION-$RELEASE"
echo "Architecture: $ARCH"

# Check for required tools
if ! command -v rpmbuild &> /dev/null; then
    echo "Error: rpmbuild not found. Install with:"
    echo "  sudo yum install rpm-build rpmdevtools"
    exit 1
fi

# Create RPM build directory structure
BUILD_DIR="$PROJECT_ROOT/build/rpm"
mkdir -p "$BUILD_DIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# Create source tarball
TARBALL_NAME="p2p-platform-${VERSION}.tar.gz"
TARBALL_PATH="$BUILD_DIR/SOURCES/$TARBALL_NAME"

echo "Creating source tarball..."
cd "$PROJECT_ROOT"
tar --exclude='build' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='venv' \
    --exclude='.venv' \
    -czf "$TARBALL_PATH" \
    --transform "s,^,p2p-platform-${VERSION}/," \
    stun-server/ \
    relay-server/ \
    signaling-server/ \
    did-service/ \
    packaging/

echo "Source tarball created: $TARBALL_PATH"

# Copy spec file
cp "$PROJECT_ROOT/packaging/rpm/p2p-platform.spec" "$BUILD_DIR/SPECS/"

# Update version in spec file
sed -i "s/^Version:.*/Version:        $VERSION/" "$BUILD_DIR/SPECS/p2p-platform.spec"
sed -i "s/^Release:.*/Release:        $RELEASE%{?dist}/" "$BUILD_DIR/SPECS/p2p-platform.spec"

# Build RPM
echo "Building RPM package..."
rpmbuild --define "_topdir $BUILD_DIR" \
         --define "_arch $ARCH" \
         -ba "$BUILD_DIR/SPECS/p2p-platform.spec"

# Copy built packages to output directory
OUTPUT_DIR="$PROJECT_ROOT/dist/rpm"
mkdir -p "$OUTPUT_DIR"

if [ -d "$BUILD_DIR/RPMS/$ARCH" ]; then
    cp "$BUILD_DIR/RPMS/$ARCH"/*.rpm "$OUTPUT_DIR/"
fi
if [ -d "$BUILD_DIR/SRPMS" ]; then
    cp "$BUILD_DIR/SRPMS"/*.rpm "$OUTPUT_DIR/"
fi

echo ""
echo "✓ RPM packages built successfully!"
echo "Output directory: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"

echo ""
echo "To install:"
echo "  sudo yum install $OUTPUT_DIR/p2p-platform-${VERSION}-${RELEASE}.*.rpm"
echo ""
echo "Or for DNF-based systems:"
echo "  sudo dnf install $OUTPUT_DIR/p2p-platform-${VERSION}-${RELEASE}.*.rpm"
