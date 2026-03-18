# P2P Platform Packaging

RPM packaging and deployment scripts for P2P Platform.

## Contents

- `rpm/p2p-platform.spec` - RPM spec file
- `systemd/` - Systemd service files
- `scripts/` - Deployment scripts

## Building RPM

```bash
# Prepare source tarball
cd /path/to/p2p-platform
tar -czf p2p-platform-1.0.0.tar.gz --transform 's,^,p2p-platform-1.0.0/,' *

# Build RPM
rpmbuild -ba packaging/rpm/p2p-platform.spec
```

## Installation

### RHEL/CentOS/Fedora

```bash
# Install dependencies
sudo yum install -y boost openssl redis

# Install RPM
sudo rpm -ivh p2p-platform-1.0.0-1.rpm

# Configure services
sudo /usr/share/p2p-platform/scripts/configure.sh

# Start services
sudo /usr/share/p2p-platform/scripts/start.sh
```

### Ubuntu/Debian

```bash
# Install alien for RPM support
sudo apt-get install -y alien

# Install dependencies
sudo apt-get install -y libboost-all-dev libssl-dev redis-server

# Convert and install RPM
sudo alien -i p2p-platform-1.0.0-1.rpm

# Configure services
sudo /usr/share/p2p-platform/scripts/configure.sh

# Start services
sudo /usr/share/p2p-platform/scripts/start.sh
```

## Services

- `p2p-stun` - STUN server (port 3478)
- `p2p-relay` - TURN relay server (port 3479)
- `p2p-signaling` - WebSocket signaling server (port 8080)

## Management Scripts

- `install.sh` - Install from RPM
- `configure.sh` - Configuration wizard
- `start.sh` - Start all services
- `stop.sh` - Stop all services
- `status.sh` - Check service status
- `upgrade.sh` - Upgrade to new version

## Service Management

```bash
# Start individual service
sudo systemctl start p2p-stun

# Stop individual service
sudo systemctl stop p2p-stun

# Check status
sudo systemctl status p2p-stun

# View logs
sudo journalctl -u p2p-stun -f

# Enable auto-start
sudo systemctl enable p2p-stun
```

## Directories

- `/etc/p2p-platform/` - Configuration files
- `/var/log/p2p-platform/` - Log files
- `/var/lib/p2p-platform/` - Data directory
- `/usr/share/p2p-platform/scripts/` - Management scripts

## Upgrade

```bash
# Stop services
sudo /usr/share/p2p-platform/scripts/stop.sh

# Upgrade RPM
sudo rpm -Uvh p2p-platform-1.0.0-2.rpm

# Start services
sudo /usr/share/p2p-platform/scripts/start.sh
```

## Uninstall

```bash
# Stop services
sudo /usr/share/p2p-platform/scripts/stop.sh

# Remove RPM
sudo rpm -e p2p-platform
```

## Troubleshooting

### Services won't start

```bash
# Check logs
sudo journalctl -u p2p-stun -n 50

# Check permissions
ls -la /var/log/p2p-platform/
ls -la /var/lib/p2p-platform/

# Verify user exists
id p2p
```

### Port conflicts

```bash
# Check if ports are in use
sudo netstat -tulpn | grep -E '(3478|3479|8080)'

# Change ports in service files
sudo vi /etc/systemd/system/p2p-stun.service
sudo systemctl daemon-reload
sudo systemctl restart p2p-stun
```

## Support

For issues and questions, please open an issue on GitHub.
