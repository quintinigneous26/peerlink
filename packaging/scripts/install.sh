#!/bin/bash
# Install P2P Platform from RPM

set -e

echo "P2P Platform Installation Script"
echo "================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

# Detect OS
if [ -f /etc/redhat-release ]; then
    OS="rhel"
elif [ -f /etc/debian_version ]; then
    OS="debian"
else
    echo "Error: Unsupported OS"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
if [ "$OS" = "rhel" ]; then
    yum install -y boost openssl redis
elif [ "$OS" = "debian" ]; then
    apt-get update
    apt-get install -y libboost-all-dev libssl-dev redis-server
fi

# Install RPM
echo "Installing P2P Platform..."
if [ -f "p2p-platform-1.0.0-1.rpm" ]; then
    if [ "$OS" = "rhel" ]; then
        rpm -ivh p2p-platform-1.0.0-1.rpm
    elif [ "$OS" = "debian" ]; then
        alien -i p2p-platform-1.0.0-1.rpm
    fi
else
    echo "Error: RPM file not found"
    exit 1
fi

echo ""
echo "Installation complete!"
echo "Run /usr/share/p2p-platform/scripts/configure.sh to configure services"
