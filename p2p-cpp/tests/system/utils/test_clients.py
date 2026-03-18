"""
Test utilities for system tests
"""
import socket
import struct
import asyncio
import websockets
import json
from typing import Optional, Dict, Any

class STUNClient:
    """STUN client for testing"""

    MAGIC_COOKIE = 0x2112A442
    BINDING_REQUEST = 0x0001

    def __init__(self, server_host: str, server_port: int):
        self.server_host = server_host
        self.server_port = server_port

    def send_binding_request(self) -> Optional[Dict[str, Any]]:
        """Send STUN binding request and get response"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)

        try:
            # Build STUN binding request
            msg_type = self.BINDING_REQUEST
            msg_length = 0
            transaction_id = b'\x00' * 12

            request = struct.pack('!HHI', msg_type, msg_length, self.MAGIC_COOKIE)
            request += transaction_id

            # Send request
            sock.sendto(request, (self.server_host, self.server_port))

            # Receive response
            data, addr = sock.recvfrom(1024)

            if len(data) >= 20:
                return {
                    'success': True,
                    'response_length': len(data),
                    'server_addr': addr
                }

        except socket.timeout:
            return {'success': False, 'error': 'timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            sock.close()

        return None


class SignalingClient:
    """WebSocket signaling client for testing"""

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.ws = None
        self.device_id = None

    async def connect(self, device_id: str) -> bool:
        """Connect to signaling server"""
        try:
            self.device_id = device_id
            self.ws = await websockets.connect(f'{self.server_url}/ws')

            # Send register message
            await self.ws.send(json.dumps({
                'type': 'register',
                'device_id': device_id
            }))

            # Wait for response
            response = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
            data = json.loads(response)

            return data.get('type') == 'registered'

        except Exception as e:
            print(f"Connection error: {e}")
            return False

    async def send_offer(self, peer_id: str, sdp: str) -> bool:
        """Send offer to peer"""
        if not self.ws:
            return False

        try:
            await self.ws.send(json.dumps({
                'type': 'offer',
                'target': peer_id,
                'sdp': sdp
            }))
            return True
        except:
            return False

    async def receive_message(self, timeout: float = 5.0) -> Optional[Dict]:
        """Receive message from signaling server"""
        if not self.ws:
            return None

        try:
            msg = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
            return json.loads(msg)
        except:
            return None

    async def disconnect(self):
        """Disconnect from signaling server"""
        if self.ws:
            await self.ws.close()
            self.ws = None


class TURNClient:
    """TURN/Relay client for testing"""

    ALLOCATE_REQUEST = 0x0003
    REFRESH_REQUEST = 0x0004

    def __init__(self, server_host: str, server_port: int):
        self.server_host = server_host
        self.server_port = server_port
        self.allocation_id = None

    def allocate(self) -> bool:
        """Allocate relay address"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)

        try:
            # Build ALLOCATE request
            msg_type = self.ALLOCATE_REQUEST
            msg_length = 0
            magic_cookie = 0x2112A442
            transaction_id = b'\x00' * 12

            request = struct.pack('!HHI', msg_type, msg_length, magic_cookie)
            request += transaction_id

            sock.sendto(request, (self.server_host, self.server_port))

            # Receive response
            data, addr = sock.recvfrom(1024)

            if len(data) >= 20:
                self.allocation_id = transaction_id
                return True

        except:
            pass
        finally:
            sock.close()

        return False

    def refresh(self) -> bool:
        """Refresh allocation"""
        if not self.allocation_id:
            return False

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)

        try:
            msg_type = self.REFRESH_REQUEST
            msg_length = 0
            magic_cookie = 0x2112A442

            request = struct.pack('!HHI', msg_type, msg_length, magic_cookie)
            request += self.allocation_id

            sock.sendto(request, (self.server_host, self.server_port))

            data, addr = sock.recvfrom(1024)
            return len(data) >= 20

        except:
            return False
        finally:
            sock.close()


class DIDClient:
    """DID service client for testing"""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def register_device(self, device_id: str, platform: str) -> Optional[Dict]:
        """Register a device"""
        try:
            response = requests.post(
                f'{self.base_url}/api/v1/devices/register',
                json={
                    'device_id': device_id,
                    'platform': platform
                },
                timeout=5.0
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            print(f"Registration error: {e}")

        return None

    def get_device(self, device_id: str) -> Optional[Dict]:
        """Get device information"""
        try:
            response = requests.get(
                f'{self.base_url}/api/v1/devices/{device_id}',
                timeout=5.0
            )

            if response.status_code == 200:
                return response.json()

        except:
            pass

        return None
