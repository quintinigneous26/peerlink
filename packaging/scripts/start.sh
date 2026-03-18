#!/bin/bash
# Start all P2P Platform services

set -e

echo "Starting P2P Platform services..."

# Start services
sudo systemctl start p2p-stun
sudo systemctl start p2p-relay
sudo systemctl start p2p-signaling

echo "Waiting for services to start..."
sleep 2

# Check status
sudo systemctl status p2p-stun --no-pager
sudo systemctl status p2p-relay --no-pager
sudo systemctl status p2p-signaling --no-pager

echo ""
echo "All services started successfully!"
echo "Check logs: journalctl -u p2p-stun -u p2p-relay -u p2p-signaling -f"
