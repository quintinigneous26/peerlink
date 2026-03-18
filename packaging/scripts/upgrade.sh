#!/bin/bash
# Upgrade P2P Platform

set -e

echo "P2P Platform Upgrade Script"
echo "==========================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

# Stop services
echo "Stopping services..."
/usr/share/p2p-platform/scripts/stop.sh

# Backup configuration
echo "Backing up configuration..."
tar -czf /tmp/p2p-platform-config-backup-$(date +%Y%m%d-%H%M%S).tar.gz /etc/p2p-platform/

# Upgrade RPM
echo "Upgrading P2P Platform..."
if [ -f "p2p-platform-1.0.0-1.rpm" ]; then
    rpm -Uvh p2p-platform-1.0.0-1.rpm
else
    echo "Error: RPM file not found"
    exit 1
fi

# Start services
echo "Starting services..."
/usr/share/p2p-platform/scripts/start.sh

echo ""
echo "Upgrade complete!"
