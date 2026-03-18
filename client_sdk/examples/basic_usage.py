"""
Basic usage example for P2P Client SDK.

This example demonstrates how to use the P2P SDK to:
1. Initialize the client
2. Detect NAT type
3. Connect to a peer
4. Send/receive data
5. Handle events
"""

import asyncio
import logging

from p2p_sdk import P2PClient, P2PConfig, NATType, ChannelType


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main example function."""

    # Configure the client
    config = P2PConfig(
        signaling_server="localhost",
        signaling_port=8443,
        stun_server="stun.l.google.com",
        stun_port=19302,
        relay_server="localhost",
        relay_port=5000,
        connection_timeout=30.0,
        auto_relay=True,
    )

    # Create client with device ID
    client = P2PClient(did="device-001", config=config)

    # Setup event handlers
    @client.on_connected
    async def on_connected():
        logger.info("Connection established!")

    @client.on_disconnected
    async def on_disconnected():
        logger.info("Connection closed")

    @client.on_data
    async def on_data(channel_id: int, data: bytes):
        logger.info(f"Received {len(data)} bytes on channel {channel_id}")

    @client.on_error
    async def on_error(error: Exception):
        logger.error(f"Error: {error}")

    try:
        # Initialize the client
        await client.initialize()

        # Detect NAT type
        nat_type = await client.detect_nat()
        logger.info(f"NAT Type: {nat_type.value}")

        # Create a data channel
        data_channel = client.create_channel(
            channel_type=ChannelType.DATA,
            reliable=True,
            priority=1,
        )
        logger.info(f"Created data channel: {data_channel}")

        # Connect to peer
        peer_did = "device-002"
        success = await client.connect(peer_did)

        if success:
            logger.info(f"Connected to {peer_did}")
            logger.info(f"Connection type: {'P2P' if client.is_p2p else 'Relay'}")

            # Send data
            await client.send_data(data_channel, b"Hello, peer!")
            logger.info("Sent data")

            # Receive data
            try:
                data = await asyncio.wait_for(
                    client.recv_data(data_channel),
                    timeout=5.0,
                )
                logger.info(f"Received: {data.decode()}")
            except asyncio.TimeoutError:
                logger.info("No data received within timeout")

            # Keep connection alive for a bit
            await asyncio.sleep(10)

        else:
            logger.error(f"Failed to connect to {peer_did}")

    except Exception as e:
        logger.error(f"Error: {e}")

    finally:
        # Cleanup
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
