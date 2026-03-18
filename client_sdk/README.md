# P2P Platform Client SDK (Python)

A Python SDK for P2P device communication with NAT traversal, UDP hole punching, and automatic relay fallback.

## Features

- **NAT Detection**: Automatic NAT type detection using STUN
- **UDP Hole Punching**: Direct P2P connection establishment
- **Multi-Channel Support**: Separate channels for control, data, video, audio
- **Automatic Relay Fallback**: Seamless fallback to relay when P2P fails
- **Auto-Reconnection**: Automatic reconnection on network failures
- **Event-Driven**: Async/await based API with event handlers

## Installation

```bash
pip install p2p-sdk
```

## Quick Start

```python
import asyncio
from p2p_sdk import P2PClient, P2PConfig, ChannelType

async def main():
    # Configure client
    config = P2PConfig(
        signaling_server="localhost",
        signaling_port=8443,
        auto_relay=True,
    )

    # Create and initialize client
    client = P2PClient(did="my-device", config=config)
    await client.initialize()

    # Connect to peer
    if await client.connect("peer-device"):
        # Create channel and send data
        channel = client.create_channel(ChannelType.DATA)
        await client.send_data(channel, b"Hello, peer!")

        # Receive data
        data = await client.recv_data(channel)

    await client.close()

asyncio.run(main())
```

## API Reference

### P2PClient

Main client class for P2P communication.

#### Methods

##### `async initialize()`
Initialize the client (NAT detection, signaling connection).

##### `async detect_nat() -> NATType`
Detect NAT type.

##### `async connect(did: str) -> bool`
Connect to a device by ID.

##### `async send_data(channel: int, data: bytes) -> None`
Send data on a channel.

##### `async recv_data(channel: int, timeout: float = None) -> bytes`
Receive data from a channel.

##### `create_channel(channel_type: ChannelType, reliable: bool = True, priority: int = 0) -> int`
Create a new data channel.

##### `close_channel(channel_id: int) -> None`
Close a data channel.

##### `async close() -> None`
Close the connection and cleanup.

#### Event Handlers

```python
@client.on_connected
async def on_connected():
    print("Connected!")

@client.on_disconnected
async def on_disconnected():
    print("Disconnected")

@client.on_data
async def on_data(channel_id: int, data: bytes):
    print(f"Received {len(data)} bytes on channel {channel_id}")

@client.on_error
async def on_error(error: Exception):
    print(f"Error: {error}")
```

### P2PConfig

Configuration for P2P client.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `signaling_server` | str | "localhost" | Signaling server address |
| `signaling_port` | int | 8443 | Signaling server port |
| `stun_server` | str | "stun.l.google.com" | STUN server |
| `stun_port` | int | 19302 | STUN server port |
| `relay_server` | str | "localhost" | Relay server address |
| `relay_port` | int | 5000 | Relay server port |
| `local_port` | int | 0 | Local UDP port (0 = auto) |
| `connection_timeout` | float | 30.0 | Connection timeout (seconds) |
| `punch_timeout` | float | 10.0 | Hole punch timeout (seconds) |
| `keepalive_interval` | float | 5.0 | Keepalive interval (seconds) |
| `max_retries` | int | 3 | Max connection retries |
| `auto_relay` | bool | True | Auto fallback to relay |

### ChannelType

Types of data channels.

- `ChannelType.CONTROL` - Control/signaling channel
- `ChannelType.DATA` - General data channel
- `ChannelType.VIDEO` - Video streaming
- `ChannelType.AUDIO` - Audio streaming
- `ChannelType.CUSTOM` - Custom application channel

### NATType

Detected NAT types.

- `NATType.PUBLIC_IP` - No NAT, public IP
- `NATType.FULL_CONE` - Full cone NAT
- `NATType.RESTRICTED_CONE` - Restricted cone NAT
- `NATType.PORT_RESTRICTED_CONE` - Port restricted cone NAT
- `NATType.SYMMETRIC` - Symmetric NAT (requires relay)
- `NATType.UNKNOWN` - Could not detect
- `NATType.BLOCKED` - UDP blocked

## Protocol

The SDK uses a custom binary protocol with the following format:

```
[total_length(4)][json_length(4)][json_header][payload]
```

### Message Types

- `handshake` - Connection establishment
- `keepalive` - Connection keepalive
- `channel_data` - Channel data transfer
- `channel_open` - Open new channel
- `channel_close` - Close channel
- `disconnect` - Graceful disconnect
- `error` - Error notification

## Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=p2p_sdk tests/
```

## Examples

See the `examples/` directory for complete examples:
- `basic_usage.py` - Basic P2P connection
- `multi_channel.py` - Multi-channel communication

## License

MIT License
