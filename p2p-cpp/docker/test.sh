#!/bin/bash
# Test all P2P Platform Docker images
# Usage: ./test.sh [version]

set -e

VERSION=${1:-1.0.0}
REGISTRY=${REGISTRY:-hbliu007}

echo "=========================================="
echo "Testing P2P Platform Docker Images"
echo "Version: $VERSION"
echo "=========================================="

# Test STUN server
echo ""
echo "Testing STUN server..."
docker run --rm -d --name stun-test ${REGISTRY}/peerlink-stun:${VERSION}
sleep 2
if docker exec stun-test nc -z localhost 3478; then
    echo "✅ STUN server is running"
else
    echo "❌ STUN server failed"
fi
docker stop stun-test 2>/dev/null || true

# Test Relay server
echo ""
echo "Testing Relay server..."
docker run --rm -d --name relay-test ${REGISTRY}/peerlink-relay:${VERSION}
sleep 2
if docker exec relay-test nc -z localhost 9001; then
    echo "✅ Relay server is running"
else
    echo "❌ Relay server failed"
fi
docker stop relay-test 2>/dev/null || true

# Test Signaling server (needs Redis)
echo ""
echo "Testing Signaling server..."
echo "Note: Signaling server requires Redis, skipping full test"
docker inspect ${REGISTRY}/peerlink-signaling:${VERSION} > /dev/null && echo "✅ Signaling image exists"

# Test DID service (needs Redis)
echo ""
echo "Testing DID service..."
echo "Note: DID service requires Redis, skipping full test"
docker inspect ${REGISTRY}/peerlink-did:${VERSION} > /dev/null && echo "✅ DID image exists"

echo ""
echo "=========================================="
echo "Test complete!"
echo "=========================================="
