"""
System test configuration and fixtures
"""
import pytest
import docker
import time
import requests
from typing import Dict, Any

# Service endpoints
SERVICES = {
    'stun': {'host': 'localhost', 'port': 3478, 'protocol': 'udp'},
    'signaling': {'host': 'localhost', 'port': 8080, 'protocol': 'ws'},
    'relay': {'host': 'localhost', 'port': 3479, 'protocol': 'udp'},
    'did': {'host': 'localhost', 'port': 8081, 'protocol': 'http'},
    'redis': {'host': 'localhost', 'port': 6379}
}

@pytest.fixture(scope='session')
def docker_client():
    """Docker client for managing containers"""
    return docker.from_env()

@pytest.fixture(scope='session')
def services(docker_client):
    """Start all services using docker-compose"""
    import subprocess

    # Start services
    subprocess.run(['docker-compose', 'up', '-d'],
                   cwd='/Users/liuhongbo/work/p2p-platform/p2p-cpp/tests/system',
                   check=True)

    # Wait for services to be healthy
    max_wait = 60
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            # Check signaling server
            resp = requests.get('http://localhost:8080/health', timeout=2)
            if resp.status_code == 200:
                # Check DID service
                resp = requests.get('http://localhost:8081/health', timeout=2)
                if resp.status_code == 200:
                    break
        except:
            pass
        time.sleep(2)

    yield SERVICES

    # Cleanup
    subprocess.run(['docker-compose', 'down', '-v'],
                   cwd='/Users/liuhongbo/work/p2p-platform/p2p-cpp/tests/system')

@pytest.fixture
def test_device():
    """Create a test device"""
    return {
        'device_id': f'test_device_{int(time.time())}',
        'platform': 'test',
        'version': '1.0.0'
    }

@pytest.fixture
def two_devices():
    """Create two test devices"""
    timestamp = int(time.time())
    return [
        {
            'device_id': f'device_a_{timestamp}',
            'platform': 'ios',
            'version': '1.0.0'
        },
        {
            'device_id': f'device_b_{timestamp}',
            'platform': 'android',
            'version': '1.0.0'
        }
    ]
