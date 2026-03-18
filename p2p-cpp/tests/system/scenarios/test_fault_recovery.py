"""
Scenario 4: Fault Recovery
"""
import pytest
import asyncio
import subprocess
import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.test_clients import SignalingClient, DIDClient

@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_device_reconnection(services, test_device):
    """Test device offline and reconnection"""
    signaling_url = f"ws://{services['signaling']['host']}:{services['signaling']['port']}"
    client = SignalingClient(signaling_url)

    # Initial connection
    connected = await client.connect(test_device['device_id'])
    assert connected == True

    # Disconnect
    await client.disconnect()
    await asyncio.sleep(2)

    # Reconnect
    connected = await client.connect(test_device['device_id'])
    assert connected == True

    await client.disconnect()


@pytest.mark.asyncio
@pytest.mark.timeout(90)
async def test_signaling_server_restart(services, test_device):
    """Test signaling server restart recovery"""
    signaling_url = f"ws://{services['signaling']['host']}:{services['signaling']['port']}"
    client = SignalingClient(signaling_url)

    # Connect before restart
    connected = await client.connect(test_device['device_id'])
    assert connected == True

    # Restart signaling server
    subprocess.run(['docker-compose', 'restart', 'signaling-server'],
                   cwd='/Users/liuhongbo/work/p2p-platform/p2p-cpp/tests/system')

    # Wait for server to restart
    await asyncio.sleep(10)

    # Try to reconnect
    await client.disconnect()
    client = SignalingClient(signaling_url)

    max_retries = 5
    for i in range(max_retries):
        try:
            connected = await client.connect(test_device['device_id'])
            if connected:
                break
        except:
            pass
        await asyncio.sleep(2)

    assert connected == True, "Failed to reconnect after server restart"
    await client.disconnect()


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_redis_connection_recovery(services, test_device):
    """Test Redis connection recovery"""
    did_client = DIDClient(f"http://{services['did']['host']}:{services['did']['port']}")

    # Register device before Redis restart
    result = did_client.register_device(test_device['device_id'], test_device['platform'])
    assert result is not None

    # Restart Redis
    subprocess.run(['docker-compose', 'restart', 'redis'],
                   cwd='/Users/liuhongbo/work/p2p-platform/p2p-cpp/tests/system')

    # Wait for Redis to restart
    await asyncio.sleep(5)

    # Try to register another device
    new_device_id = f"{test_device['device_id']}_after_restart"

    max_retries = 5
    success = False
    for i in range(max_retries):
        result = did_client.register_device(new_device_id, test_device['platform'])
        if result and result.get('success'):
            success = True
            break
        await asyncio.sleep(2)

    assert success == True, "Failed to recover after Redis restart"
