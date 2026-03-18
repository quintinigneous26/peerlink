#!/bin/bash
# Build DEB package for P2P Platform
# Supports: Ubuntu 20.04+, Debian 11+

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION="${VERSION:-1.0.0}"
ARCH="${ARCH:-all}"

echo "Building P2P Platform DEB package..."
echo "Version: $VERSION"
echo "Architecture: $ARCH"

# Check for required tools
if ! command -v dpkg-deb &> /dev/null; then
    echo "Error: dpkg-deb not found. Install with:"
    echo "  sudo apt-get install dpkg-dev debhelper"
    exit 1
fi

# Create build directory
BUILD_DIR="$PROJECT_ROOT/build/deb/p2p-platform_${VERSION}"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Create directory structure
mkdir -p "$BUILD_DIR/opt/p2p-platform"
mkdir -p "$BUILD_DIR/etc/p2p-platform"
mkdir -p "$BUILD_DIR/lib/systemd/system"
mkdir -p "$BUILD_DIR/DEBIAN"

# Copy server components
echo "Copying server components..."
cp -r "$PROJECT_ROOT/stun-server" "$BUILD_DIR/opt/p2p-platform/"
cp -r "$PROJECT_ROOT/relay-server" "$BUILD_DIR/opt/p2p-platform/"
cp -r "$PROJECT_ROOT/signaling-server" "$BUILD_DIR/opt/p2p-platform/"
cp -r "$PROJECT_ROOT/did-service" "$BUILD_DIR/opt/p2p-platform/"

# Copy configuration files
cp "$PROJECT_ROOT/packaging/config"/*.conf "$BUILD_DIR/etc/p2p-platform/"

# Copy systemd service files
cp "$PROJECT_ROOT/packaging/systemd"/*.service "$BUILD_DIR/lib/systemd/system/"

# Copy Debian control files
cp "$PROJECT_ROOT/packaging/deb/debian/control" "$BUILD_DIR/DEBIAN/"
cp "$PROJECT_ROOT/packaging/deb/debian/postinst" "$BUILD_DIR/DEBIAN/"
cp "$PROJECT_ROOT/packaging/deb/debian/prerm" "$BUILD_DIR/DEBIAN/"
cp "$PROJECT_ROOT/packaging/deb/debian/postrm" "$BUILD_DIR/DEBIAN/"

# Update version in control file
sed -i "s/^Version:.*/Version: $VERSION/" "$BUILD_DIR/DEBIAN/control"

# Set permissions
chmod 755 "$BUILD_DIR/DEBIAN/postinst"
chmod 755 "$BUILD_DIR/DEBIAN/prerm"
chmod 755 "$BUILD_DIR/DEBIAN/postrm"

# Build package
echo "Building DEB package..."
dpkg-deb --build "$BUILD_DIR"

# Move to output directory
OUTPUT_DIR="$PROJECT_ROOT/dist/deb"
mkdir -p "$OUTPUT_DIR"
mv "$BUILD_DIR.deb" "$OUTPUT_DIR/p2p-platform_${VERSION}_${ARCH}.deb"

echo ""
echo "✓ DEB package built successfully!"
echo "Output: $OUTPUT_DIR/p2p-platform_${VERSION}_${ARCH}.deb"
ls -lh "$OUTPUT_DIR"

echo ""
echo "To install:"
echo "  sudo dpkg -i $OUTPUT_DIR/p2p-platform_${VERSION}_${ARCH}.deb"
echo "  sudo apt-get install -f  # Install dependencies if needed"
