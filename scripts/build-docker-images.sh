#!/bin/bash
# scripts/build-docker-images.sh
# 构建所有 Docker 镜像

set -e

VERSION="1.0.0"
REGISTRY="docker.io/p2p-platform"

echo "🐳 Building Docker images for P2P Platform v${VERSION}"
echo "=================================================="

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 构建函数
build_image() {
    local service=$1
    local context=$2

    echo -e "${BLUE}Building ${service}...${NC}"

    docker build \
        -t ${REGISTRY}/${service}:${VERSION} \
        -t ${REGISTRY}/${service}:latest \
        -f ${context}/Dockerfile \
        ${context}

    echo -e "${GREEN}✅ ${service} built successfully${NC}"
    echo ""
}

# 构建所有镜像
build_image "stun-server" "./stun-server"
build_image "relay-server" "./relay-server"
build_image "signaling-server" "./signaling-server"
build_image "did-service" "./did-service"

echo "=================================================="
echo -e "${GREEN}✅ All images built successfully!${NC}"
echo ""
echo "Images:"
docker images | grep ${REGISTRY}

echo ""
echo "To push images to Docker Hub, run:"
echo "  ./scripts/push-docker-images.sh"
