"""
Simple integration test for Noise secure channel.

This test verifies the Noise XX handshake works correctly
without additional protocol negotiation layers.
"""
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from p2p_engine.protocol.noise import (
    NoiseSecurity,
    NoiseSecurityTransport,
)

logger = logging.getLogger(__name__)


class MockStream:
    """Mock bidirectional stream for testing."""

    def __init__(self):
        self.initiator_buffer = bytearray()
        self.responder_buffer = bytearray()
        self.closed = False

    class Reader:
        def __init__(self, buffer: bytearray, other_buffer: bytearray):
            self.buffer = buffer
            self.other_buffer = other_buffer

        async def readexactly(self, n: int):
            while len(self.buffer) < n:
                await asyncio.sleep(0.001)
            result = bytes(self.buffer[:n])
            del self.buffer[:n]
            return result

        async def read(self, n: int = -1):
            if n == -1:
                result = bytes(self.buffer)
                self.buffer.clear()
                return result
            while len(self.buffer) < n:
                await asyncio.sleep(0.001)
            result = bytes(self.buffer[:n])
            del self.buffer[:n]
            return result

    class Writer:
        def __init__(self, buffer: bytearray, other_buffer: bytearray):
            self.buffer = buffer
            self.other_buffer = other_buffer

        def write(self, data: bytes):
            self.other_buffer.extend(data)
            return len(data)

        async def drain(self):
            await asyncio.sleep(0)

        def close(self):
            pass

        async def wait_closed(self):
            pass

    def create_initiator_streams(self):
        """Create initiator's reader and writer."""
        return (
            self.Reader(self.initiator_buffer, self.responder_buffer),
            self.Writer(self.initiator_buffer, self.responder_buffer)
        )

    def create_responder_streams(self):
        """Create responder's reader and writer."""
        return (
            self.Reader(self.responder_buffer, self.initiator_buffer),
            self.Writer(self.responder_buffer, self.initiator_buffer)
        )


async def test_noise_handshake_and_communication():
    """Test full Noise handshake and encrypted communication."""
    logger.info("Testing Noise handshake and encrypted communication...")

    # Create streams
    stream = MockStream()
    initiator_reader, initiator_writer = stream.create_initiator_streams()
    responder_reader, responder_writer = stream.create_responder_streams()

    # Use shared identity key for HMAC signature verification in test
    # In production, each peer would have their own Ed25519 keypair
    shared_identity_key = b"shared_identity_key_for_testing_32!!"

    initiator_noise = NoiseSecurity(
        identity_private_key=shared_identity_key,
        identity_public_key=shared_identity_key,
        stream_muxers=["/yamux/1.0.0"]
    )

    responder_noise = NoiseSecurity(
        identity_private_key=shared_identity_key,
        identity_public_key=shared_identity_key,
        stream_muxers=["/yamux/1.0.0", "/mplex/6.7.0"]
    )

    # Run handshake concurrently
    async def initiator_handshake():
        return await initiator_noise.handshake(
            initiator_reader,
            initiator_writer,
            is_initiator=True
        )

    async def responder_handshake():
        return await responder_noise.handshake(
            responder_reader,
            responder_writer,
            is_initiator=False
        )

    logger.info("Starting Noise XX handshake...")
    initiator_transport, responder_transport = await asyncio.gather(
        initiator_handshake(),
        responder_handshake()
    )

    # Verify both transports are created
    assert isinstance(initiator_transport, NoiseSecurityTransport)
    assert isinstance(responder_transport, NoiseSecurityTransport)
    assert initiator_transport.cipher_tx is not None
    assert initiator_transport.cipher_rx is not None
    assert responder_transport.cipher_tx is not None
    assert responder_transport.cipher_rx is not None

    logger.info("Noise handshake completed successfully!")

    # Test bidirectional communication
    test_messages = [
        b"Hello from initiator!",
        b"Hello from responder!",
        b"Third message",
        b"Final test message",
    ]

    logger.info("Testing encrypted message exchange...")

    for i, msg in enumerate(test_messages):
        if i % 2 == 0:
            # Initiator sends
            await initiator_transport.send(msg)
            received = await responder_transport.recv()
            logger.info(f"Initiator -> Responder: '{msg.decode()}'")
        else:
            # Responder sends
            await responder_transport.send(msg)
            received = await initiator_transport.recv()
            logger.info(f"Responder -> Initiator: '{msg.decode()}'")

        assert received == msg, f"Message mismatch: expected {msg}, got {received}"

    logger.info("All messages successfully encrypted and decrypted!")

    # Clean up
    await initiator_transport.close()
    await responder_transport.close()

    logger.info("✓ Test passed!")


async def test_concurrent_connections():
    """Test multiple concurrent Noise handshakes."""
    logger.info("Testing concurrent Noise handshakes...")

    async def single_handshake(index: int):
        stream = MockStream()
        initiator_reader, initiator_writer = stream.create_initiator_streams()
        responder_reader, responder_writer = stream.create_responder_streams()

        shared_key = f"test_key_{index}".encode().ljust(32, b'!')

        initiator = NoiseSecurity(
            identity_private_key=shared_key,
            identity_public_key=shared_key,
        )

        responder = NoiseSecurity(
            identity_private_key=shared_key,
            identity_public_key=shared_key,
        )

        # Run handshake
        initiator_transport, responder_transport = await asyncio.gather(
            initiator.handshake(initiator_reader, initiator_writer, is_initiator=True),
            responder.handshake(responder_reader, responder_writer, is_initiator=False)
        )

        # Test one message
        test_msg = f"Connection {index}".encode()
        await initiator_transport.send(test_msg)
        received = await responder_transport.recv()

        await initiator_transport.close()
        await responder_transport.close()

        return received == test_msg

    # Run 5 concurrent handshakes
    results = await asyncio.gather(*[single_handshake(i) for i in range(5)])

    assert all(results), "Some concurrent handshakes failed"
    logger.info("✓ All 5 concurrent handshakes succeeded!")


async def main():
    """Run all integration tests."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("=" * 60)
    logger.info("Noise Secure Channel Integration Tests")
    logger.info("=" * 60)

    try:
        await test_noise_handshake_and_communication()
        await test_concurrent_connections()

        logger.info("=" * 60)
        logger.info("ALL TESTS PASSED!")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
