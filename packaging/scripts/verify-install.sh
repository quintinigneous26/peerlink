#!/bin/bash
# Verify P2P Platform installation
# Usage: ./verify-install.sh

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SERVICES=("p2p-stun" "p2p-relay" "p2p-signaling")
BINARIES=("stun-server" "relay-server" "signaling-server")
FAILED=0

echo -e "${BLUE}P2P Platform Installation Verification${NC}"
echo "========================================"
echo ""

# Function to check a condition
check() {
    local name=$1
    local command=$2

    echo -n "Checking $name... "

    if eval "$command" &>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${RED}FAILED${NC}"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# Check binaries
echo -e "${BLUE}1. Checking binaries:${NC}"
for binary in "${BINARIES[@]}"; do
    check "$binary" "command -v $binary"
done
echo ""

# Check systemd services
echo -e "${BLUE}2. Checking systemd services:${NC}"
for service in "${SERVICES[@]}"; do
    check "$service.service" "systemctl list-unit-files | grep -q $service"
done
echo ""

# Check directories
echo -e "${BLUE}3. Checking directories:${NC}"
check "/var/log/p2p-platform" "[ -d /var/log/p2p-platform ]"
check "/var/lib/p2p-platform" "[ -d /var/lib/p2p-platform ]"
check "/usr/share/p2p-platform" "[ -d /usr/share/p2p-platform ]"
echo ""

# Check permissions
echo -e "${BLUE}4. Checking permissions:${NC}"
check "p2p user" "id p2p"
check "p2p group" "getent group p2p"
check "log directory permissions" "[ -w /var/lib/p2p-platform ] || sudo -u p2p [ -w /var/lib/p2p-platform ]"
echo ""

# Check dependencies
echo -e "${BLUE}5. Checking dependencies:${NC}"
check "Boost libraries" "ldconfig -p | grep -q libboost"
check "OpenSSL" "command -v openssl"
check "systemd" "command -v systemctl"
echo ""

# Try to start services
echo -e "${BLUE}6. Testing service startup:${NC}"
for service in "${SERVICES[@]}"; do
    echo -n "Testing $service... "

    # Check if already running
    if systemctl is-active --quiet "$service"; then
        echo -e "${YELLOW}already running${NC}"
        continue
    fi

    # Try to start
    if sudo systemctl start "$service" 2>/dev/null; then
        sleep 2

        # Check if still running
        if systemctl is-active --quiet "$service"; then
            echo -e "${GREEN}OK${NC}"

            # Stop it
            sudo systemctl stop "$service" 2>/dev/null
        else
            echo -e "${RED}FAILED (crashed)${NC}"
            FAILED=$((FAILED + 1))

            # Show logs
            echo "  Last log lines:"
            journalctl -u "$service" -n 5 --no-pager 2>/dev/null | sed 's/^/    /'
        fi
    else
        echo -e "${RED}FAILED (won't start)${NC}"
        FAILED=$((FAILED + 1))
    fi
done
echo ""

# Summary
echo "========================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Installation verified successfully."
    echo "To start services: sudo /usr/share/p2p-platform/scripts/start.sh"
    exit 0
else
    echo -e "${RED}✗ $FAILED check(s) failed${NC}"
    echo ""
    echo "Installation verification failed."
    echo "Please check the errors above and fix them."
    exit 1
fi
