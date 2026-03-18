#!/bin/bash
# Push all P2P Platform Docker images to registry
# Usage: ./push.sh [version]

set -e

VERSION=${1:-1.0.0}
REGISTRY=${REGISTRY:-hbliu007}

echo "=========================================="
echo "Pushing P2P Platform Docker Images"
echo "Version: $VERSION"
echo "Registry: $REGISTRY"
echo "=========================================="

# Check if logged in
if ! docker info | grep -q "Username"; then
    echo "Error: Not logged in to Docker registry"
    echo "Please run: docker login"
    exit 1
fi

# Push STUN server
echo ""
echo "Pushing STUN server..."
docker push ${REGISTRY}/peerlink-stun:${VERSION}
docker push ${REGISTRY}/peerlink-stun:latest

# Push Relay server
echo ""
echo "Pushing Relay server..."
docker push ${REGISTRY}/peerlink-relay:${VERSION}
docker push ${REGISTRY}/peerlink-relay:latest

# Push Signaling server
echo ""
echo "Pushing Signaling server..."
docker push ${REGISTRY}/peerlink-signaling:${VERSION}
docker push ${REGISTRY}/peerlink-signaling:latest

# Push DID service
echo ""
echo "Pushing DID service..."
docker push ${REGISTRY}/peerlink-did:${VERSION}
docker push ${REGISTRY}/peerlink-did:latest

echo ""
echo "=========================================="
echo "Push complete!"
echo "=========================================="
