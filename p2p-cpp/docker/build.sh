#!/bin/bash
# Build all P2P Platform Docker images
# Usage: ./build.sh [version]

set -e

VERSION=${1:-1.0.0}
REGISTRY=${REGISTRY:-hbliu007}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Building P2P Platform Docker Images"
echo "Version: $VERSION"
echo "Registry: $REGISTRY"
echo "=========================================="

cd "$PROJECT_DIR"

# Build STUN server
echo ""
echo "Building STUN server..."
docker build -f docker/Dockerfile.stun -t ${REGISTRY}/peerlink-stun:${VERSION} -t ${REGISTRY}/peerlink-stun:latest .

# Build Relay server
echo ""
echo "Building Relay server..."
docker build -f docker/Dockerfile.relay -t ${REGISTRY}/peerlink-relay:${VERSION} -t ${REGISTRY}/peerlink-relay:latest .

# Build Signaling server
echo ""
echo "Building Signaling server..."
docker build -f docker/Dockerfile.signaling -t ${REGISTRY}/peerlink-signaling:${VERSION} -t ${REGISTRY}/peerlink-signaling:latest .

# Build DID service
echo ""
echo "Building DID service..."
docker build -f docker/Dockerfile.did -t ${REGISTRY}/peerlink-did:${VERSION} -t ${REGISTRY}/peerlink-did:latest .

echo ""
echo "=========================================="
echo "Build complete!"
echo "=========================================="
docker images | grep peerlink
