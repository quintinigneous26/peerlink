#!/bin/bash
# Configure P2P Platform services

set -e

echo "P2P Platform Configuration Wizard"
echo "=================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Error: This script must be run as root"
    exit 1
fi

# Get public IP
echo "Detecting public IP..."
PUBLIC_IP=$(curl -s ifconfig.me || echo "127.0.0.1")
echo "Detected public IP: $PUBLIC_IP"
echo ""

# Configure STUN server
echo "Configuring STUN server..."
read -p "STUN server port [3478]: " STUN_PORT
STUN_PORT=${STUN_PORT:-3478}

# Configure Relay server
echo "Configuring Relay server..."
read -p "Relay server port [3479]: " RELAY_PORT
RELAY_PORT=${RELAY_PORT:-3479}

# Configure Signaling server
echo "Configuring Signaling server..."
read -p "Signaling server port [8080]: " SIGNALING_PORT
SIGNALING_PORT=${SIGNALING_PORT:-8080}

# Enable services
echo ""
echo "Enabling services..."
systemctl enable p2p-stun
systemctl enable p2p-relay
systemctl enable p2p-signaling

echo ""
echo "Configuration complete!"
echo "Start services with: /usr/share/p2p-platform/scripts/start.sh"
