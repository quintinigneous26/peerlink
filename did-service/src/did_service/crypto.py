"""
Cryptography utilities for DID service
"""

import secrets
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend


class KeyGenerator:
    """Generate and manage cryptographic keys."""

    @staticmethod
    def generate_keypair() -> tuple[bytes, bytes]:
        """
        Generate Ed25519 keypair for device authentication.

        Returns:
            Tuple of (private_key, public_key) as bytes
        """
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )

        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        return private_bytes, public_bytes

    @staticmethod
    def serialize_public_key(public_key: bytes) -> str:
        """Serialize public key to hex string."""
        return public_key.hex()

    @staticmethod
    def serialize_private_key(private_key: bytes) -> str:
        """Serialize private key to hex string."""
        return private_key.hex()

    @staticmethod
    def deserialize_public_key(hex_key: str) -> bytes:
        """Deserialize public key from hex string."""
        return bytes.fromhex(hex_key)

    @staticmethod
    def deserialize_private_key(hex_key: str) -> bytes:
        """Deserialize private key from hex string."""
        return bytes.fromhex(hex_key)

    @staticmethod
    def sign(private_key: bytes, message: bytes) -> bytes:
        """
        Sign a message using Ed25519.

        Args:
            private_key: Private key bytes
            message: Message to sign

        Returns:
            Signature bytes
        """
        key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
        signature = key.sign(message)
        return signature

    @staticmethod
    def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
        """
        Verify a signature using Ed25519.

        Args:
            public_key: Public key bytes
            message: Original message
            signature: Signature to verify

        Returns:
            True if signature is valid
        """
        try:
            key = ed25519.Ed25519PublicKey.from_public_bytes(public_key)
            key.verify(signature, message)
            return True
        except Exception:
            return False


class DIDGenerator:
    """Generate DIDs according to the specified format."""

    # Format: PREFIX-XXXXXX-YYYYY
    # PREFIX: Device type prefix (e.g., ios, android, web, desktop)
    # XXXXXX: 6-character random hex (3 bytes)
    # YYYYY: 5-character random alphanumeric

    PREFIX_LENGTH = 6
    SUFFIX_LENGTH = 5

    @staticmethod
    def generate(device_type: str) -> str:
        """
        Generate a DID for a device.

        Args:
            device_type: Type of device (ios, android, web, desktop)

        Returns:
            DID string in format: PREFIX-XXXXXX-YYYYY
        """
        # Generate middle section (6 hex chars = 3 bytes)
        middle = secrets.token_hex(3).upper()

        # Generate suffix section (5 alphanumeric chars)
        alphabet = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # No ambiguous chars
        suffix = "".join(secrets.choice(alphabet) for _ in range(DIDGenerator.SUFFIX_LENGTH))

        return f"{device_type}-{middle}-{suffix}"

    @staticmethod
    def validate(device_id: str) -> bool:
        """
        Validate a DID format.

        Args:
            device_id: DID string to validate

        Returns:
            True if format is valid
        """
        parts = device_id.split("-")
        if len(parts) != 3:
            return False

        prefix, middle, suffix = parts

        # Validate prefix
        valid_prefixes = {"ios", "android", "web", "desktop"}
        if prefix.lower() not in valid_prefixes:
            return False

        # Validate middle (6 hex chars)
        if len(middle) != 6 or not all(c in "0123456789ABCDEFabcdef" for c in middle):
            return False

        # Validate suffix (5 alphanumeric chars, no ambiguous chars)
        alphabet = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
        if len(suffix) != 5 or not all(c in alphabet for c in suffix):
            return False

        return True
