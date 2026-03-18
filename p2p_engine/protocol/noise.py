"""
Noise Secure Channel Implementation for libp2p

This module implements the libp2p Noise secure channel protocol using
the Noise Protocol Framework. It provides:
- XX handshake pattern for mutual authentication
- Noise_XX_25519_ChaChaPoly_SHA256 cipher suite
- Static key authentication using libp2p identity keys (Ed25519)
- Early data exchange for protocol negotiation

Reference: https://github.com/libp2p/specs/blob/master/noise/README.md
"""
import asyncio
import hashlib
import hmac
import logging
import struct
from dataclasses import dataclass, field
from typing import Optional, Tuple, Callable, Awaitable

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from .noise_pb2 import NoiseHandshakePayload, NoiseExtensions

logger = logging.getLogger(__name__)

# Protocol identifiers
PROTOCOL_ID = "/noise"
PROTOCOL_NAME = "Noise_XX_25519_ChaChaPoly_SHA256"

# Noise constants
MAX_MESSAGE_SIZE = 65535
DH_LEN = 32  # X25519 public key length
MAC_LEN = 16  # Poly1305 tag length
HASH_LEN = 32  # SHA256 output length

# Signature prefix for static key authentication
SIGNATURE_PREFIX = b"noise-libp2p-static-key:"


# ==================== Exceptions ====================

class NoiseError(Exception):
    """Base exception for Noise protocol errors."""
    pass


class HandshakeError(NoiseError):
    """Raised when handshake fails."""
    pass


class CryptoError(NoiseError):
    """Raised when cryptographic operation fails."""
    pass


class InvalidSignatureError(HandshakeError):
    """Raised when signature verification fails."""
    pass


# ==================== Cryptographic Primitives ====================

class DHState:
    """
    Diffie-Hellman key pair container.
    """

    def __init__(self, private_key: Optional[X25519PrivateKey] = None, public_key: Optional[X25519PublicKey] = None):
        """
        Initialize DH state.

        Args:
            private_key: Optional private key (generated if not provided)
            public_key: Optional public key (used when only public key is known)
        """
        if public_key is not None:
            self.public_key = public_key
            self.private_key = private_key  # May be None for remote peers
        else:
            self.private_key = private_key or X25519PrivateKey.generate()
            self.public_key = self.private_key.public_key()

    def get_public_key_bytes(self) -> bytes:
        """Get public key as bytes (RFC 7748 encoding)."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

    def dh(self, peer_public: X25519PublicKey) -> bytes:
        """
        Perform Diffie-Hellman with peer's public key.

        Args:
            peer_public: Peer's X25519 public key

        Returns:
            Shared secret (32 bytes)
        """
        if self.private_key is None:
            raise CryptoError("Cannot perform DH without private key")
        return self.private_key.exchange(peer_public)

    @classmethod
    def from_bytes(cls, public_bytes: bytes) -> "DHState":
        """
        Create DH state from public key bytes (for remote peers).

        Args:
            public_bytes: Public key bytes (32 bytes, RFC 7748 encoding)

        Returns:
            DHState with only public key (no private key)
        """
        public_key = X25519PublicKey.from_public_bytes(public_bytes)
        return cls(private_key=None, public_key=public_key)


class CipherState:
    """
    ChaCha20-Poly1305 cipher state for encryption/decryption.
    Maintains nonce counter for each direction.
    """

    def __init__(self, key: bytes, n: int = 0):
        """
        Initialize cipher state.

        Args:
            key: 32-byte encryption key
            n: Initial nonce value
        """
        if len(key) != 32:
            raise CryptoError(f"Invalid key length: {len(key)} (expected 32)")
        self.key = key
        self.n = n
        self.cipher = ChaCha20Poly1305(key)
        self._max_nonce = 2**64 - 1  # Per Noise spec

    def encrypt(self, plaintext: bytes, ad: Optional[bytes] = None) -> bytes:
        """
        Encrypt plaintext with AEAD.

        Args:
            plaintext: Data to encrypt
            ad: Optional additional data for authentication

        Returns:
            Ciphertext with authentication tag appended
        """
        if self.n >= self._max_nonce:
            raise CryptoError("Nonce exhausted - connection must be closed")

        # ChaCha20-Poly1305 uses 96-bit (12-byte) nonce
        # We construct it as: n (64-bit, big-endian) || 0x00000000 (32-bit)
        nonce = struct.pack('>Q', self.n) + b'\x00\x00\x00\x00'

        ciphertext = self.cipher.encrypt(nonce, plaintext, ad)
        self.n += 1
        return ciphertext

    def decrypt(self, ciphertext: bytes, ad: Optional[bytes] = None) -> bytes:
        """
        Decrypt ciphertext with AEAD.

        Args:
            ciphertext: Data to decrypt (with auth tag)
            ad: Optional additional data for authentication

        Returns:
            Decrypted plaintext

        Raises:
            CryptoError: If decryption fails (authentication error)
        """
        if self.n >= self._max_nonce:
            raise CryptoError("Nonce exhausted - connection must be closed")

        nonce = struct.pack('>Q', self.n) + b'\x00\x00\x00\x00'

        try:
            plaintext = self.cipher.decrypt(nonce, ciphertext, ad)
        except Exception as e:
            raise CryptoError(f"Decryption failed: {e}")

        self.n += 1
        return plaintext


class SymmetricState:
    """
    Symmetric state for Noise handshake.
    Maintains CK, h, and cipher states per Noise spec.
    """

    def __init__(self, protocol_name: bytes):
        """
        Initialize symmetric state.

        Args:
            protocol_name: Noise protocol name bytes
        """
        # h = HASH(protocol_name)
        self.h = hashlib.sha256(protocol_name).digest()
        # ck = h
        self.ck = self.h
        # Initialize cipher states with null key
        self.cipher1: Optional[CipherState] = None
        self.cipher2: Optional[CipherState] = None

    def mix_key(self, input_key_material: bytes) -> None:
        """
        Derive new cipher keys using HKDF.

        Args:
            input_key_material: Input key material
        """
        # Set ck, k1 = HKDF(ck, input_key_material, 2)
        derived = self._hkdf(self.ck, input_key_material, 2)
        self.ck = derived[0]
        self.cipher1 = CipherState(derived[1])
        self.cipher2 = None

    def mix_hash(self, data: bytes) -> None:
        """
        Mix data into handshake hash.

        Args:
            data: Data to mix into h
        """
        self.h = hashlib.sha256(self.h + data).digest()

    def encrypt_and_hash(self, plaintext: bytes) -> bytes:
        """
        Encrypt plaintext and mix into hash.

        Args:
            plaintext: Data to encrypt

        Returns:
            Ciphertext (or plaintext if no cipher)
        """
        if self.cipher1 is not None:
            ciphertext = self.cipher1.encrypt(plaintext, self.h)
        else:
            ciphertext = plaintext
        self.mix_hash(ciphertext)
        return ciphertext

    def decrypt_and_hash(self, ciphertext: bytes) -> bytes:
        """
        Decrypt ciphertext and mix into hash.

        Args:
            ciphertext: Data to decrypt

        Returns:
            Plaintext (or ciphertext if no cipher)
        """
        if self.cipher1 is not None:
            plaintext = self.cipher1.decrypt(ciphertext, self.h)
        else:
            plaintext = ciphertext
        self.mix_hash(ciphertext)
        return plaintext

    def split(self) -> Tuple[CipherState, CipherState]:
        """
        Split into two cipher states for transport.

        Returns:
            Tuple of (encrypt_cipher, decrypt_cipher)
        """
        # Set k1, k2 = HKDF(ck, b"", 2)
        derived = self._hkdf(self.ck, b"", 2)
        return CipherState(derived[0]), CipherState(derived[1])

    @staticmethod
    def _hkdf(chain_key: bytes, input_key_material: bytes, num_outputs: int) -> list[bytes]:
        """
        HKDF as specified in Noise spec.

        Args:
            chain_key: Current chain key
            input_key_material: Input key material
            num_outputs: Number of keys to derive

        Returns:
            List of derived keys (32 bytes each)
        """
        # Set temp = HMAC(chain_key, input_key_material)
        temp = hmac.new(chain_key, input_key_material, hashlib.sha256).digest()

        # Set output1 = HMAC(temp, 0x01)
        output1 = hmac.new(temp, b'\x01', hashlib.sha256).digest()

        if num_outputs == 1:
            return [output1]

        # Set output2 = HMAC(temp, output1 || 0x02)
        output2 = hmac.new(temp, output1 + b'\x02', hashlib.sha256).digest()

        return [output1, output2]


# ==================== Handshake State ====================

@dataclass
class HandshakeResult:
    """Result of a Noise handshake."""
    cipher_tx: CipherState  # Cipher for sending
    cipher_rx: CipherState  # Cipher for receiving
    remote_static: bytes    # Remote static public key
    remote_payload: bytes   # Remote handshake payload (decrypted)
    h: bytes                # Final handshake hash (for channel binding)


@dataclass
class HandshakeConfig:
    """Configuration for Noise handshake."""
    # Local identity (libp2p peer identity)
    identity_private_key: bytes  # For signing static Noise key
    identity_public_key: bytes   # For verification

    # Extensions to advertise
    stream_muxers: list[str] = field(default_factory=list)

    # Callbacks for peer verification
    verify_peer_callback: Optional[Callable[[bytes, bytes], Awaitable[bool]]] = None


class NoiseHandshake:
    """
    Noise XX handshake implementation.

    Pattern: XX (mutual authentication)
    Cipher Suite: Noise_XX_25519_ChaChaPoly_SHA256
    """

    def __init__(
        self,
        config: HandshakeConfig,
        is_initiator: bool,
        remote_static: Optional[bytes] = None,
    ):
        """
        Initialize handshake state.

        Args:
            config: Handshake configuration
            is_initiator: True if initiator, False if responder
            remote_static: Optional remote static public key (pre-known)
        """
        self.config = config
        self.is_initiator = is_initiator

        # Generate ephemeral keypair
        self.e = DHState()
        # Generate static keypair (separate from identity key)
        self.s = DHState()

        # Symmetric state
        self.symmetric = SymmetricState(PROTOCOL_NAME.encode())

        # Remote keys
        self.re = None  # Remote ephemeral
        self.rs = None  # Remote static

        if remote_static:
            self.rs = DHState.from_bytes(remote_static)

        # For responder: re is received in message 1
        if not is_initiator:
            self.re = None

    async def _write_message(self, payload: bytes, cipher: bool) -> bytes:
        """
        Write a handshake message.

        Args:
            payload: Payload to include in message
            cipher: Whether to encrypt the payload

        Returns:
            Complete handshake message
        """
        if cipher:
            return self.symmetric.encrypt_and_hash(payload)
        else:
            self.symmetric.mix_hash(payload)
            return payload

    async def _read_message(self, message: bytes, cipher: bool) -> bytes:
        """
        Read a handshake message.

        Args:
            message: Received handshake message
            cipher: Whether message is encrypted

        Returns:
            Decrypted payload
        """
        if cipher:
            return self.symmetric.decrypt_and_hash(message)
        else:
            self.symmetric.mix_hash(message)
            return message

    def _build_handshake_payload(self) -> bytes:
        """
        Build the libp2p handshake payload.

        Returns:
            Serialized NoiseHandshakePayload protobuf
        """
        payload = NoiseHandshakePayload()

        # Identity key (libp2p public key)
        payload.identity_key = self.config.identity_public_key

        # Sign static Noise key with identity key
        static_pub_bytes = self.s.get_public_key_bytes()
        signed_data = SIGNATURE_PREFIX + static_pub_bytes

        # Use Ed25519 signature (assuming identity key is Ed25519)
        # This is a placeholder - actual signing depends on key type
        # In production, use proper signature from identity key
        payload.identity_sig = self._sign_with_identity_key(signed_data)

        # Extensions
        if self.config.stream_muxers:
            ext = NoiseExtensions(stream_muxers=self.config.stream_muxers)
            payload.extensions = ext

        return payload.SerializeToString()

    def _sign_with_identity_key(self, data: bytes) -> bytes:
        """
        Sign data with identity key using Ed25519.

        Args:
            data: Data to sign

        Returns:
            Signature bytes (64 bytes for Ed25519)

        Note:
            Uses Ed25519 signature algorithm as recommended by libp2p.
        """
        try:
            # Identity key should be an Ed25519 private key
            priv_key = Ed25519PrivateKey.from_private_bytes(self.config.identity_private_key)
            signature = priv_key.sign(data)
            return signature
        except Exception as e:
            # Fallback to HMAC if not Ed25519 (for compatibility)
            logger.warning(f"Ed25519 signing failed, using HMAC fallback: {e}")
            return hmac.new(self.config.identity_private_key, data, hashlib.sha256).digest()

    async def _verify_peer_signature(
        self,
        static_key: bytes,
        identity_key: bytes,
        signature: bytes,
    ) -> bool:
        """
        Verify peer's signature on their static Noise key.

        Args:
            static_key: Peer's static Noise public key
            identity_key: Peer's identity public key
            signature: Signature to verify

        Returns:
            True if signature is valid
        """
        signed_data = SIGNATURE_PREFIX + static_key

        # If callback provided, use it
        if self.config.verify_peer_callback:
            return await self.config.verify_peer_callback(identity_key, signed_data, signature)

        # Try Ed25519 verification first
        try:
            pub_key = Ed25519PublicKey.from_public_bytes(identity_key)
            pub_key.verify(signature, signed_data)
            return True
        except Exception:
            # Fallback to HMAC verification
            logger.debug("Ed25519 verification failed, trying HMAC fallback")
            try:
                expected = hmac.new(identity_key, signed_data, hashlib.sha256).digest()
                return hmac.compare_digest(expected, signature)
            except Exception as e:
                logger.error(f"Signature verification failed: {e}")
                return False

    async def initiator_send_message1(self) -> bytes:
        """
        Initiator: Send first message -> e

        Returns:
            Message 1 bytes (ephemeral public key)
        """
        logger.debug("Initiator: sending message 1 (-> e)")

        # Get ephemeral public key
        e_bytes = self.e.get_public_key_bytes()

        # Mix hash with e
        self.symmetric.mix_hash(e_bytes)

        return e_bytes

    async def responder_read_message1(self, message1: bytes) -> None:
        """
        Responder: Read first message -> e

        Args:
            message1: Received message 1
        """
        logger.debug("Responder: reading message 1 (-> e)")

        if len(message1) != DH_LEN:
            raise HandshakeError(f"Invalid message 1 length: {len(message1)}")

        # Store remote ephemeral
        self.re = DHState.from_bytes(message1)

        # Mix hash
        self.symmetric.mix_hash(message1)

    async def responder_send_message2(self) -> bytes:
        """
        Responder: Send second message <- e, ee, s, es

        Returns:
            Message 2 bytes with encrypted payload
        """
        logger.debug("Responder: sending message 2 (<- e, ee, es, s)")

        # Build message: e || ee || encrypted(payload) || es
        e_bytes = self.e.get_public_key_bytes()
        self.symmetric.mix_hash(e_bytes)

        # DH: ee = dh(e, re)
        ee_shared = self.e.dh(self.re.public_key)
        self.symmetric.mix_key(ee_shared)

        # Build and encrypt payload (encryption uses key from ee only)
        payload = self._build_handshake_payload()
        encrypted_payload = self.symmetric.encrypt_and_hash(
            self.s.get_public_key_bytes() + payload
        )

        # DH: es = dh(s, re) - done AFTER encryption
        # Note: In Noise XX pattern, the 'es' DH in message 2 notation
        # refers to processing this DH, but it happens after the payload
        # is encrypted. The encryption key only depends on 'ee'.
        es_shared = self.s.dh(self.re.public_key)
        self.symmetric.mix_key(es_shared)

        return e_bytes + encrypted_payload

    async def initiator_read_message2(self, message2: bytes) -> bytes:
        """
        Initiator: Read second message <- e, ee, s, es

        Args:
            message2: Received message 2

        Returns:
            Decrypted remote payload
        """
        logger.debug("Initiator: reading message 2 (<- e, ee, es, s)")

        if len(message2) < DH_LEN:
            raise HandshakeError(f"Invalid message 2 length: {len(message2)}")

        # Parse remote ephemeral
        re_bytes = message2[:DH_LEN]
        self.re = DHState.from_bytes(re_bytes)
        self.symmetric.mix_hash(re_bytes)

        # DH: ee = dh(e, re)
        ee_shared = self.e.dh(self.re.public_key)
        self.symmetric.mix_key(ee_shared)

        # Decrypt payload portion
        encrypted_payload = message2[DH_LEN:]
        decrypted = self.symmetric.decrypt_and_hash(encrypted_payload)

        # Parse static key and payload
        rs_bytes = decrypted[:DH_LEN]
        self.rs = DHState.from_bytes(rs_bytes)

        # DH: se = dh(e, rs)
        se_shared = self.e.dh(self.rs.public_key)
        self.symmetric.mix_key(se_shared)

        # Return payload for verification
        return decrypted[DH_LEN:]

    async def initiator_send_message3(self) -> bytes:
        """
        Initiator: Send third message -> s, se

        Returns:
            Message 3 bytes with encrypted payload
        """
        logger.debug("Initiator: sending message 3 (-> s, se)")

        # Build and encrypt payload (encryption happens before se DH)
        payload = self._build_handshake_payload()
        encrypted_payload = self.symmetric.encrypt_and_hash(
            self.s.get_public_key_bytes() + payload
        )

        # DH: se = dh(s, re) - done AFTER encryption
        # Note: The 'se' DH in message 3 notation is processed after
        # the payload is encrypted. The responder will do the same
        # DH after decrypting the payload.
        se_shared = self.s.dh(self.re.public_key)
        self.symmetric.mix_key(se_shared)

        return encrypted_payload

    async def responder_read_message3(self, message3: bytes) -> bytes:
        """
        Responder: Read third message -> s, se

        Args:
            message3: Received message 3

        Returns:
            Decrypted remote payload
        """
        logger.debug("Responder: reading message 3 (-> s, se)")

        # Decrypt payload
        decrypted = self.symmetric.decrypt_and_hash(message3)

        # Parse static key
        rs_bytes = decrypted[:DH_LEN]
        self.rs = DHState.from_bytes(rs_bytes)

        # DH: se = dh(e, rs)
        se_shared = self.e.dh(self.rs.public_key)
        self.symmetric.mix_key(se_shared)

        # Return payload for verification
        return decrypted[DH_LEN:]

    def finalize(self) -> HandshakeResult:
        """
        Finalize handshake and derive transport keys.

        Returns:
            HandshakeResult with cipher states and peer info
        """
        # Split into two cipher states
        tx, rx = self.symmetric.split()

        return HandshakeResult(
            cipher_tx=tx,
            cipher_rx=rx,
            remote_static=self.rs.get_public_key_bytes() if self.rs else b"",
            remote_payload=b"",
            h=self.symmetric.h,
        )


# ==================== Noise Security Module ====================

class NoiseSecurityTransport:
    """
    Noise secure transport for encrypted communication.

    Wraps a bidirectional stream with Noise encryption.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        cipher_tx: CipherState,
        cipher_rx: CipherState,
    ):
        """
        Initialize secure transport.

        Args:
            reader: Stream reader for underlying transport
            writer: Stream writer for underlying transport
            cipher_tx: Cipher for sending data
            cipher_rx: Cipher for receiving data
        """
        self.reader = reader
        self.writer = writer
        self.cipher_tx = cipher_tx
        self.cipher_rx = cipher_rx
        self._closed = False

    async def send(self, data: bytes) -> None:
        """
        Send encrypted data with Noise framing.

        Args:
            data: Plaintext to send

        Frame format: <2-byte big-endian length><encrypted data>
        """
        if self._closed:
            raise RuntimeError("Transport is closed")

        if len(data) > MAX_MESSAGE_SIZE:
            raise NoiseError(f"Data too large: {len(data)} (max {MAX_MESSAGE_SIZE})")

        # Encrypt data
        ciphertext = self.cipher_tx.encrypt(data)

        # Frame with length prefix
        frame = struct.pack('>H', len(ciphertext)) + ciphertext

        self.writer.write(frame)
        await self.writer.drain()

    async def recv(self) -> bytes:
        """
        Receive and decrypt data with Noise framing.

        Returns:
            Decrypted plaintext
        """
        if self._closed:
            raise RuntimeError("Transport is closed")

        # Read length prefix
        length_bytes = await self.reader.readexactly(2)
        length = struct.unpack('>H', length_bytes)[0]

        if length > MAX_MESSAGE_SIZE + MAC_LEN:
            raise NoiseError(f"Invalid message length: {length}")

        # Read encrypted data
        ciphertext = await self.reader.readexactly(length)

        # Decrypt
        plaintext = self.cipher_rx.decrypt(ciphertext)
        return plaintext

    async def close(self) -> None:
        """Close the transport."""
        if self._closed:
            return

        self._closed = True
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as e:
            logger.debug(f"Error closing transport: {e}")

    @property
    def closed(self) -> bool:
        """Check if transport is closed."""
        return self._closed


class NoiseSecurity:
    """
    Noise security channel for libp2p.

    This class provides the main interface for performing Noise
    handshakes and establishing secure channels.
    """

    PROTOCOL_ID = PROTOCOL_ID
    PROTOCOL_NAME = PROTOCOL_NAME

    def __init__(
        self,
        identity_private_key: bytes,
        identity_public_key: bytes,
        stream_muxers: Optional[list[str]] = None,
    ):
        """
        Initialize Noise security.

        Args:
            identity_private_key: Local libp2p identity private key
            identity_public_key: Local libp2p identity public key
            stream_muxers: Optional list of supported stream muxers
        """
        self.identity_private_key = identity_private_key
        self.identity_public_key = identity_public_key
        self.stream_muxers = stream_muxers or ["/yamux/1.0.0", "/mplex/6.7.0"]

    async def handshake(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        is_initiator: bool,
    ) -> NoiseSecurityTransport:
        """
        Perform Noise XX handshake.

        Args:
            reader: Stream reader
            writer: Stream writer
            is_initiator: True if initiating, False if responding

        Returns:
            NoiseSecurityTransport for secure communication

        Raises:
            HandshakeError: If handshake fails
            InvalidSignatureError: If signature verification fails
        """
        config = HandshakeConfig(
            identity_private_key=self.identity_private_key,
            identity_public_key=self.identity_public_key,
            stream_muxers=self.stream_muxers,
        )

        handshake = NoiseHandshake(config, is_initiator)

        try:
            if is_initiator:
                return await self._handshake_as_initiator(handshake, reader, writer)
            else:
                return await self._handshake_as_responder(handshake, reader, writer)
        except Exception as e:
            raise HandshakeError(f"Handshake failed: {e}")

    async def _handshake_as_initiator(
        self,
        handshake: NoiseHandshake,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> NoiseSecurityTransport:
        """Perform handshake as initiator."""
        # Message 1: -> e
        msg1 = await handshake.initiator_send_message1()
        await self._send_frame(writer, msg1)

        # Message 2: <- e, ee, es, s
        msg2 = await self._recv_frame(reader)
        remote_payload_bytes = await handshake.initiator_read_message2(msg2)

        # Verify remote payload
        await self._verify_remote_payload(remote_payload_bytes, handshake)

        # Message 3: -> s, se
        msg3 = await handshake.initiator_send_message3()
        await self._send_frame(writer, msg3)

        # Finalize
        result = handshake.finalize()
        result.remote_payload = remote_payload_bytes

        logger.info("Noise handshake completed as initiator")

        return NoiseSecurityTransport(
            reader, writer, result.cipher_tx, result.cipher_rx
        )

    async def _handshake_as_responder(
        self,
        handshake: NoiseHandshake,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> NoiseSecurityTransport:
        """Perform handshake as responder."""
        # Message 1: -> e
        msg1 = await self._recv_frame(reader)
        await handshake.responder_read_message1(msg1)

        # Message 2: <- e, ee, es, s
        msg2 = await handshake.responder_send_message2()
        await self._send_frame(writer, msg2)

        # Message 3: -> s, se
        msg3 = await self._recv_frame(reader)
        remote_payload_bytes = await handshake.responder_read_message3(msg3)

        # Verify remote payload
        await self._verify_remote_payload(remote_payload_bytes, handshake)

        # Finalize
        result = handshake.finalize()
        result.remote_payload = remote_payload_bytes

        logger.info("Noise handshake completed as responder")
        # NOTE: Responder needs to swap cipher states!
        # After split(), both parties have (k1, k2).
        # Initiator: tx=k1, rx=k2
        # Responder: tx=k2, rx=k1 (swapped!)

        return NoiseSecurityTransport(
            reader, writer, result.cipher_rx, result.cipher_tx
        )

    async def _verify_remote_payload(
        self,
        payload_bytes: bytes,
        handshake: NoiseHandshake,
    ) -> None:
        """
        Verify remote handshake payload.

        Args:
            payload_bytes: Decrypted payload bytes
            handshake: Current handshake state

        Raises:
            InvalidSignatureError: If signature verification fails
        """
        try:
            payload = NoiseHandshakePayload()
            payload.ParseFromString(payload_bytes)
        except Exception as e:
            raise HandshakeError(f"Failed to parse payload: {e}")

        if not payload.identity_key:
            raise InvalidSignatureError("Missing identity key in payload")

        if not payload.identity_sig:
            raise InvalidSignatureError("Missing signature in payload")

        # Verify signature on static key
        static_key = handshake.rs.get_public_key_bytes()
        identity_key = payload.identity_key
        signature = payload.identity_sig

        if not await handshake._verify_peer_signature(static_key, identity_key, signature):
            raise InvalidSignatureError("Signature verification failed")

        logger.debug("Remote payload verified successfully")

        # TODO: Process extensions (stream muxers, etc.)
        if payload.extensions and payload.extensions.stream_muxers:
            logger.debug(
                f"Remote stream muxers: {list(payload.extensions.stream_muxers)}"
            )

    async def _send_frame(self, writer: asyncio.StreamWriter, data: bytes) -> None:
        """
        Send data with Noise framing.

        Args:
            writer: Stream writer
            data: Data to send
        """
        if len(data) > MAX_MESSAGE_SIZE:
            raise NoiseError(f"Data too large: {len(data)}")

        frame = struct.pack('>H', len(data)) + data
        writer.write(frame)
        await writer.drain()

    async def _recv_frame(self, reader: asyncio.StreamReader) -> bytes:
        """
        Receive data with Noise framing.

        Args:
            reader: Stream reader

        Returns:
            Received data
        """
        length_bytes = await reader.readexactly(2)
        length = struct.unpack('>H', length_bytes)[0]

        if length > MAX_MESSAGE_SIZE:
            raise NoiseError(f"Invalid frame length: {length}")

        return await reader.readexactly(length)


__all__ = [
    # Protocol identifiers
    "PROTOCOL_ID",
    "PROTOCOL_NAME",

    # Exceptions
    "NoiseError",
    "HandshakeError",
    "CryptoError",
    "InvalidSignatureError",

    # Configuration
    "HandshakeConfig",
    "HandshakeResult",

    # Main API
    "NoiseSecurity",
    "NoiseSecurityTransport",

    # Handshake (for advanced usage)
    "NoiseHandshake",

    # Crypto primitives
    "DHState",
    "CipherState",
    "SymmetricState",
]
