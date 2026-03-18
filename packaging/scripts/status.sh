#!/bin/bash
# Check status of all P2P Platform services

echo "P2P Platform Services Status"
echo "============================"
echo ""

# Check each service
for service in p2p-stun p2p-relay p2p-signaling; do
    echo "Service: $service"
    if systemctl is-active --quiet $service; then
        echo "  Status: RUNNING"
        echo "  Uptime: $(systemctl show -p ActiveEnterTimestamp $service --value)"
    else
        echo "  Status: STOPPED"
    fi
    echo ""
done

# Show resource usage
echo "Resource Usage:"
echo "==============="
ps aux | grep -E "(stun-server|relay_server|signaling-server)" | grep -v grep || echo "No processes found"
