#!/bin/bash
# Stop all P2P Platform services

set -e

echo "Stopping P2P Platform services..."

# Stop services
sudo systemctl stop p2p-signaling
sudo systemctl stop p2p-relay
sudo systemctl stop p2p-stun

echo "All services stopped successfully!"
