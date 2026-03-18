"""
Multi-channel example for P2P Client SDK.

This example demonstrates using multiple channels for different
types of data (control, video, audio, etc.).
"""

import asyncio
import logging

from p2p_sdk import P2PClient, P2PConfig, ChannelType


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def multi_channel_example():
    """Demonstrate multi-channel communication."""

    config = P2PConfig(
        signaling_server="localhost",
        signaling_port=8443,
        auto_relay=True,
    )

    client = P2PClient(did="device-sender", config=config)

    @client.on_connected
    async def on_connected():
        logger.info("Multi-channel connection established")

    try:
        await client.initialize()

        # Create multiple channels
        control_channel = client.create_channel(ChannelType.CONTROL, priority=10)
        video_channel = client.create_channel(ChannelType.VIDEO, reliable=False, priority=5)
        audio_channel = client.create_channel(ChannelType.AUDIO, reliable=False, priority=5)
        data_channel = client.create_channel(ChannelType.DATA, reliable=True)

        logger.info(f"Created channels: control={control_channel}, video={video_channel}, "
                   f"audio={audio_channel}, data={data_channel}")

        # Connect to peer
        if await client.connect("device-receiver"):
            # Send control messages
            await client.send_data(control_channel, b"START_STREAM")
            logger.info("Sent control command")

            # Simulate video data
            for i in range(10):
                video_frame = b"VIDEO_FRAME_" + str(i).encode()
                await client.send_data(video_channel, video_frame)

                audio_packet = b"AUDIO_PACKET_" + str(i).encode()
                await client.send_data(audio_channel, audio_packet)

                await asyncio.sleep(0.1)

            # Send stop command
            await client.send_data(control_channel, b"STOP_STREAM")

            # Close video and audio channels
            client.close_channel(video_channel)
            client.close_channel(audio_channel)
            logger.info("Closed media channels")

            await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(multi_channel_example())
