"""
DCUtR Protocol Usage Example

This example demonstrates how to use the DCUtR protocol to upgrade
a relay connection to a direct connection.
"""
import asyncio
import logging

from ...types import NATInfo, NATType, ISP
from ..dcutr import (
    DCUtRProtocol,
    DCUtRMessage,
    DCUtRMessageType,
    PROTOCOL_ID,
)


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def example_dcutr_active_side():
    """
    Example: Active side (initiator) of DCUtR upgrade

    This is the peer that initiates the upgrade from relay to direct.
    """
    # Setup local NAT information
    local_nat = NATInfo(
        type=NATType.PORT_RESTRICTED,
        public_ip="203.0.113.1",  # Example public IP
        public_port=12345,
        local_ip="10.0.0.1",
        local_port=54321,
    )

    # Create DCUtR protocol instance
    dcutr = DCUtRProtocol(
        local_peer_id="QmInitiatorPeer",
        local_nat=local_nat,
        local_isp=ISP.CHINA_TELECOM,
        max_retry_attempts=3,
        sync_timeout_ms=10000,
    )

    # Simulated relay connection (in real use, this comes from circuit relay)
    # For this example, we'll skip the actual relay connection setup

    # Local addresses to share with remote peer
    # These would typically come from Identify protocol observations
    local_addrs = [
        "/ip4/203.0.113.1/tcp/12345",
        "/ip4/203.0.113.1/udp/12346/quic",
    ]

    logger.info("Starting DCUtR upgrade (active side)...")

    # In a real scenario, you would have actual relay streams:
    # result = await dcutr.upgrade_to_direct(
    #     relay_reader=relay_reader,
    #     relay_writer=relay_writer,
    #     local_addrs=local_addrs,
    #     remote_peer_id="QmRemotePeer",
    # )

    # For this example, just show the flow
    logger.info(f"Would upgrade using addresses: {local_addrs}")
    logger.info(f"Protocol ID: {PROTOCOL_ID}")

    # Cleanup
    dcutr.close()


async def example_dcutr_passive_side():
    """
    Example: Passive side (receiver) of DCUtR upgrade

    This is the peer that receives the upgrade request.
    """
    # Setup local NAT information
    local_nat = NATInfo(
        type=NATType.FULL_CONE,
        public_ip="198.51.100.1",  # Example public IP
        public_port=23456,
        local_ip="10.0.1.1",
        local_port=65432,
    )

    # Create DCUtR protocol instance
    dcutr = DCUtRProtocol(
        local_peer_id="QmPassivePeer",
        local_nat=local_nat,
        local_isp=ISP.CHINA_UNICOM,
    )

    # Local addresses to share
    local_addrs = [
        "/ip4/198.51.100.1/tcp/23456",
        "/ip4/198.51.100.1/udp/23457/quic",
    ]

    logger.info("Waiting for DCUtR upgrade request (passive side)...")

    # In a real scenario, you would handle incoming requests:
    # result = await dcutr.handle_incoming_upgrade(
    #     relay_reader=relay_reader,
    #     relay_writer=relay_writer,
    #     local_addrs=local_addrs,
    # )

    logger.info(f"Would share addresses: {local_addrs}")

    # Cleanup
    dcutr.close()


async def example_message_encoding():
    """Example: Encoding and decoding DCUtR messages"""
    logger.info("=== DCUtR Message Encoding Example ===")

    # Create a CONNECT message with observed addresses
    connect_msg = DCUtRMessage(
        message_type=DCUtRMessageType.CONNECT,
        obs_addrs=[
            b"/ip4/203.0.113.1/tcp/12345",
            b"/ip4/203.0.113.1/udp/12346/quic",
        ],
    )

    # Encode the message
    encoded = connect_msg.encode()
    logger.info(f"Encoded CONNECT message: {len(encoded)} bytes")
    logger.info(f"  Hex: {encoded.hex()}")

    # Decode the message
    length, offset = DCUtRMessage.decode_varint(encoded)
    msg_data = encoded[offset:offset + length]
    decoded = DCUtRMessage.decode(msg_data)

    logger.info(f"Decoded message type: {decoded.message_type.name}")
    logger.info(f"Decoded addresses: {[addr.decode() for addr in decoded.obs_addrs]}")

    # Create a SYNC message
    sync_msg = DCUtRMessage(message_type=DCUtRMessageType.SYNC)
    sync_encoded = sync_msg.encode()
    logger.info(f"Encoded SYNC message: {len(sync_encoded)} bytes")


async def example_protocol_flow():
    """Example: Complete DCUtR protocol flow"""
    logger.info("=== DCUtR Protocol Flow Example ===")
    logger.info("")
    logger.info("Step 1: Relay connection established")
    logger.info("  Peer A ---relay---> Peer B")
    logger.info("")
    logger.info("Step 2: Peer B opens DCUtR stream")
    logger.info("  B -> A: CONNECT (with B's observed addresses)")
    logger.info("")
    logger.info("Step 3: Peer A responds")
    logger.info("  A -> B: CONNECT (with A's observed addresses)")
    logger.info("  [RTT measured]")
    logger.info("")
    logger.info("Step 4: Peer B synchronizes")
    logger.info("  B -> A: SYNC")
    logger.info("  [B starts timer = RTT/2]")
    logger.info("")
    logger.info("Step 5: Simultaneous connect")
    logger.info("  A: Immediately connects to B's addresses")
    logger.info("  B: After timer, connects to A's addresses")
    logger.info("")
    logger.info("Step 6: Direct connection established")
    logger.info("  Peer A <---direct---> Peer B")
    logger.info("  Relay connection can be closed")


async def main():
    """Run all examples"""
    logger.info("=" * 60)
    logger.info("DCUtR Protocol Examples")
    logger.info("=" * 60)
    logger.info("")

    await example_message_encoding()
    logger.info("")

    await example_protocol_flow()
    logger.info("")

    await example_dcutr_active_side()
    logger.info("")

    await example_dcutr_passive_side()
    logger.info("")

    logger.info("=" * 60)
    logger.info("Examples completed")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
