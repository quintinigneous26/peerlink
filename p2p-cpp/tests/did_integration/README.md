# DID Service Integration Tests

Integration tests for the DID (Decentralized Identifier) service.

## Test Scenarios

### 1. Device Registration (`test_device_registration.py`)
- Complete registration flow (DID generation, registration, verification, token)
- Basic device registration
- Duplicate registration handling
- Device retrieval
- Non-existent device handling

**Tests**: 5

### 2. Device Lifecycle (`test_device_lifecycle.py`)
- Complete lifecycle: Register → Online → Heartbeat → Offline → Delete
- Heartbeat updates
- Device deletion
- Offline detection

**Tests**: 4

### 3. Multi-Device Scenarios (`test_multi_device.py`)
- Multiple device types registration
- Query by platform
- Online devices list
- List all devices
- Platform filtering

**Tests**: 5

### 4. Error Handling (`test_error_handling.py`)
- Invalid DID format
- Missing required fields
- Non-existent device operations
- Invalid signature verification
- Rate limiting
- Malformed JSON

**Tests**: 6

### 5. Concurrent Operations (`test_concurrent.py`)
- Concurrent registrations (50 devices)
- Concurrent heartbeats (20 devices)
- Mixed concurrent operations (60 ops)
- Rate limiting under load (100 requests)
- Concurrent device queries

**Tests**: 5

## Total: 25 Integration Tests

## Prerequisites

- Docker and Docker Compose
- Python 3.8+
- Redis (via Docker)
- Ports 6380, 8082 available

## Running Tests

### Quick Start

```bash
cd tests/did_integration
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

# 3. Wait for services
sleep 10

# 4. Run tests
pytest scenarios/ -v

# 5. Cleanup
docker-compose down -v
```

### Run Specific Scenarios

```bash
# Registration tests only
pytest scenarios/test_device_registration.py -v

# Concurrent tests only
pytest scenarios/test_concurrent.py -v

# With detailed output
pytest scenarios/ -v -s
```

## Test Architecture

```
tests/did_integration/
├── docker-compose.yml          # Service orchestration
├── conftest.py                 # Pytest fixtures
├── requirements.txt            # Python dependencies
├── run_tests.sh               # Test runner
├── scenarios/                 # Test scenarios
│   ├── test_device_registration.py
│   ├── test_device_lifecycle.py
│   ├── test_multi_device.py
│   ├── test_error_handling.py
│   └── test_concurrent.py
└── utils/
    └── did_client.py          # DID service client
```

## DID Service Client

The `DIDServiceClient` provides methods for:

- `register_device(device_data)` - Register a new device
- `get_device(device_id)` - Get device information
- `update_heartbeat(device_id)` - Update device heartbeat
- `delete_device(device_id)` - Delete a device
- `list_devices(platform, online_only)` - List devices with filters
- `verify_did(did, signature)` - Verify DID signature
- `get_token(device_id)` - Get authentication token
- `health_check()` - Check service health

## Expected Results

All 25 tests should pass with:
- Registration success rate: >95%
- Concurrent operations success rate: >80%
- Error handling: All edge cases covered
- Performance: <30s for all tests

## Troubleshooting

### Services not starting

```bash
docker-compose logs did-service
docker-compose logs redis
```

### Port conflicts

```bash
# Check ports
lsof -i :6380
lsof -i :8082

# Change ports in docker-compose.yml
```

### Redis connection issues

```bash
# Test Redis connection
redis-cli -p 6380 ping

# Check Redis logs
docker-compose logs redis
```

### Test failures

```bash
# Run with verbose output
pytest scenarios/ -v -s

# Run specific test
pytest scenarios/test_device_registration.py::test_complete_registration_flow -v -s
```

## CI/CD Integration

```yaml
# .github/workflows/did-integration-tests.yml
- name: Run DID Integration Tests
  run: |
    cd tests/did_integration
    ./run_tests.sh
```

## Performance Benchmarks

Expected performance:
- Device registration: <100ms per device
- Concurrent registrations: 50 devices in <5s
- Heartbeat updates: <50ms per update
- Device queries: <50ms per query
- Rate limiting: Enforced at configured threshold

## Notes

- Tests use mock DID generation for simplicity
- Actual signature verification depends on implementation
- Rate limiting thresholds are configurable
- Redis is cleaned up after each test
