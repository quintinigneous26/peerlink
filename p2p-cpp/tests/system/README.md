# P2P Platform System Tests

End-to-end system tests for the P2P platform.

## Test Scenarios

### 1. Complete P2P Connection (`test_p2p_connection.py`)
- DID device registration (2 devices)
- STUN NAT traversal
- Signaling exchange
- P2P connection establishment
- Data transfer

### 2. Relay Fallback (`test_relay_fallback.py`)
- NAT traversal failure simulation
- Automatic relay fallback
- Data transfer through TURN relay
- Concurrent relay allocations

### 3. Fault Recovery (`test_fault_recovery.py`)
- Device offline/reconnection
- Signaling server restart
- Redis connection recovery

### 4. Performance Tests (`test_performance.py`)
- 1000 device registrations
- 100 concurrent connections
- STUN throughput test
- Rate limiting verification

## Prerequisites

- Docker and Docker Compose
- Python 3.8+
- 8GB RAM minimum
- Ports 3478, 3479, 6379, 8080, 8081 available

## Running Tests

### Quick Start

```bash
cd tests/system
./run_tests.sh
```

### Manual Execution

```bash
# 1. Install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Start services
docker-compose up -d

# 3. Wait for services (15-20 seconds)
sleep 15

# 4. Run tests
pytest scenarios/ -v

# 5. Cleanup
docker-compose down -v
```

### Run Specific Scenarios

```bash
# P2P connection tests only
pytest scenarios/test_p2p_connection.py -v

# Performance tests only
pytest scenarios/test_performance.py -v

# With detailed output
pytest scenarios/ -v -s
```

## Test Results

Expected results:
- **P2P Connection**: 4/4 tests pass
- **Relay Fallback**: 3/3 tests pass
- **Fault Recovery**: 3/3 tests pass
- **Performance**: 4/4 tests pass

Total: **14 tests**, ~5-10 minutes runtime

## Architecture

```
tests/system/
├── docker-compose.yml      # Service orchestration
├── conftest.py             # Pytest fixtures
├── requirements.txt        # Python dependencies
├── run_tests.sh           # Test runner
├── scenarios/             # Test scenarios
│   ├── test_p2p_connection.py
│   ├── test_relay_fallback.py
│   ├── test_fault_recovery.py
│   └── test_performance.py
└── utils/                 # Test utilities
    └── test_clients.py    # Client implementations
```

## Troubleshooting

### Services not starting
```bash
docker-compose logs
docker-compose ps
```

### Port conflicts
```bash
# Check ports
lsof -i :3478
lsof -i :8080

# Change ports in docker-compose.yml
```

### Test timeouts
```bash
# Increase timeout
pytest scenarios/ --timeout=300
```

## CI/CD Integration

```yaml
# .github/workflows/system-tests.yml
- name: Run System Tests
  run: |
    cd tests/system
    ./run_tests.sh
```

## Performance Benchmarks

Expected performance (on 4-core, 8GB RAM):
- Device registration: >500/sec
- Concurrent connections: 100 in <10s
- STUN throughput: >1000 req/sec
- Relay allocation: >50/sec
