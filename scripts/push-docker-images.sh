#!/bin/bash
# scripts/push-docker-images.sh
# 推送 Docker 镜像到 Docker Hub

set -e

VERSION="1.0.0"
REGISTRY="docker.io/p2p-platform"

echo "🚀 Pushing Docker images to Docker Hub"
echo "=================================================="

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否已登录
if ! docker info | grep -q "Username"; then
    echo -e "${YELLOW}⚠️  Not logged in to Docker Hub${NC}"
    echo "Please login first:"
    echo "  docker login"
    exit 1
fi

# 推送函数
push_image() {
    local service=$1

    echo -e "${BLUE}Pushing ${service}...${NC}"

    # 推送版本标签
    docker push ${REGISTRY}/${service}:${VERSION}

    # 推送 latest 标签
    docker push ${REGISTRY}/${service}:latest

    echo -e "${GREEN}✅ ${service} pushed successfully${NC}"
    echo ""
}

# 推送所有镜像
push_image "stun-server"
push_image "relay-server"
push_image "signaling-server"
push_image "did-service"

echo "=================================================="
echo -e "${GREEN}✅ All images pushed successfully!${NC}"
echo ""
echo "Images available at:"
echo "  ${REGISTRY}/stun-server:${VERSION}"
echo "  ${REGISTRY}/relay-server:${VERSION}"
echo "  ${REGISTRY}/signaling-server:${VERSION}"
echo "  ${REGISTRY}/did-service:${VERSION}"
