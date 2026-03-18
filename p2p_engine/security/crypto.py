"""
Cryptographic primitives for Noise Protocol Framework.

This module provides low-level cryptographic operations for the Noise protocol:
- X25519 key generation and Diffie-Hellman
- Ed25519 key generation and signature verification
- ChaCha20-Poly1305 AEAD encryption/decryption
- HKDF key derivation
- SHA256 hashing

Protocol: Noise_XX_25519_ChaChaPoly_SHA256
Reference: https://noiseprotocol.org/noise.html
"""

import hashlib
import hmac
import struct
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import serialization


# ==================== Constants ====================

# Noise protocol name
NOISE_PROTOCOL_NAME = b"Noise_XX_25519_ChaChaPoly_SHA256"

# Sizes in bytes
DH_LEN = 32          # X25519 public/private key length
HASH_LEN = 32        # SHA256 output length
KEY_LEN = 32         # ChaCha20 key length
NONCE_LEN = 12       # ChaCha20-Poly1305 nonce length (96-bit)
TAG_LEN = 16         # Poly1305 authentication tag length

# Maximum nonce value (2^64 - 1 per Noise spec)
MAX_NONCE = 2**64 - 1


# ==================== Key Generation ====================

def generate_x25519_keypair() -> Tuple[bytes, bytes]:
    """
    Generate X25519 keypair for Diffie-Hellman.

    Returns:
        Tuple of (private_key, public_key) as bytes (32 bytes each)

    Example:
        >>> priv, pub = generate_x25519_keypair()
        >>> len(priv), len(pub)
        (32, 32)
    """
    private_key = X25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    return private_bytes, public_bytes


# ==================== Diffie-Hellman ====================

def dh(private_key: bytes, public_key: bytes) -> bytes:
    """
    Perform X25519 Diffie-Hellman key exchange.

    Args:
        private_key: Local private key (32 bytes)
        public_key: Remote public key (32 bytes)

    Returns:
        Shared secret (32 bytes)

    Raises:
        ValueError: If key lengths are invalid
        CryptoError: If DH computation fails

    Example:
        >>> priv1, pub1 = generate_x25519_keypair()
        >>> priv2, pub2 = generate_x25519_keypair()
        >>> shared1 = dh(priv1, pub2)
        >>> shared2 = dh(priv2, pub1)
        >>> shared1 == shared2
        True
    """
    if len(private_key) != DH_LEN:
        raise ValueError(f"Invalid private key length: {len(private_key)} (expected {DH_LEN})")

    if len(public_key) != DH_LEN:
        raise ValueError(f"Invalid public key length: {len(public_key)} (expected {DH_LEN})")

    try:
        priv_key_obj = X25519PrivateKey.from_private_bytes(private_key)
        pub_key_obj = X25519PublicKey.from_public_bytes(public_key)
        shared_secret = priv_key_obj.exchange(pub_key_obj)
        return shared_secret
    except Exception as e:
        raise CryptoError(f"DH computation failed: {e}") from e


# ==================== AEAD Encryption ====================

def _build_nonce(n: int) -> bytes:
    """
    Build 96-bit nonce from 64-bit counter.

    Per Noise spec: nonce = n (64-bit, big-endian) || 0x00000000 (32-bit)

    Args:
        n: 64-bit nonce counter

    Returns:
        12-byte nonce
    """
    return struct.pack('>Q', n) + b'\x00\x00\x00\x00'


def encrypt(key: bytes, nonce: int, plaintext: bytes, aad: bytes = b"") -> bytes:
    """
    Encrypt using ChaCha20-Poly1305 AEAD.

    Args:
        key: 32-byte encryption key
        nonce: 64-bit nonce counter
        plaintext: Data to encrypt
        aad: Additional authenticated data (default: empty)

    Returns:
        Ciphertext with Poly1305 tag appended (plaintext len + 16 bytes)

    Raises:
        ValueError: If key length is invalid
        CryptoError: If encryption fails

    Example:
        >>> key = b'x' * 32
        >>> plaintext = b'Hello, world!'
        >>> ct = encrypt(key, 0, plaintext)
        >>> len(ct) == len(plaintext) + 16
        True
    """
    if len(key) != KEY_LEN:
        raise ValueError(f"Invalid key length: {len(key)} (expected {KEY_LEN})")

    if nonce > MAX_NONCE:
        raise ValueError(f"Nonce exhausted: {nonce} > {MAX_NONCE}")

    try:
        cipher = ChaCha20Poly1305(key)
        nonce_bytes = _build_nonce(nonce)
        ciphertext = cipher.encrypt(nonce_bytes, plaintext, aad)
        return ciphertext
    except Exception as e:
        raise CryptoError(f"Encryption failed: {e}") from e


def decrypt(key: bytes, nonce: int, ciphertext: bytes, aad: bytes = b"") -> bytes:
    """
    Decrypt using ChaCha20-Poly1305 AEAD.

    Args:
        key: 32-byte decryption key
        nonce: 64-bit nonce counter
        ciphertext: Data to decrypt (with Poly1305 tag)
        aad: Additional authenticated data (default: empty)

    Returns:
        Decrypted plaintext

    Raises:
        ValueError: If key length is invalid
        CryptoError: If decryption fails (authentication error)

    Example:
        >>> key = b'x' * 32
        >>> plaintext = b'Hello, world!'
        >>> ct = encrypt(key, 0, plaintext)
        >>> pt = decrypt(key, 0, ct)
        >>> pt == plaintext
        True
    """
    if len(key) != KEY_LEN:
        raise ValueError(f"Invalid key length: {len(key)} (expected {KEY_LEN})")

    if nonce > MAX_NONCE:
        raise ValueError(f"Nonce exhausted: {nonce} > {MAX_NONCE}")

    try:
        cipher = ChaCha20Poly1305(key)
        nonce_bytes = _build_nonce(nonce)
        plaintext = cipher.decrypt(nonce_bytes, ciphertext, aad)
        return plaintext
    except Exception as e:
        raise CryptoError(f"Decryption failed (authentication error): {e}") from e


# ==================== HKDF ====================

def hkdf(chaining_key: bytes, input_key_material: bytes) -> Tuple[bytes, bytes]:
    """
    HKDF as specified in the Noise Protocol Framework.

    Derives two keys (chain key and output key) using HMAC-SHA256.

    Algorithm:
        temp = HMAC(chaining_key, input_key_material)
        output1 = HMAC(temp, 0x01)
        output2 = HMAC(temp, output1 || 0x02)

    Args:
        chaining_key: Current chain key (32 bytes)
        input_key_material: Input key material (e.g., DH shared secret)

    Returns:
        Tuple of (new_chaining_key, output_key) - each 32 bytes

    Example:
        >>> ck = b'x' * 32
        >>> ikm = b'y' * 32
        >>> new_ck, k = hkdf(ck, ikm)
        >>> len(new_ck), len(k)
        (32, 32)
    """
    if len(chaining_key) != HASH_LEN:
        raise ValueError(f"Invalid chaining key length: {len(chaining_key)}")

    # temp = HMAC(chain_key, input_key_material)
    temp = hmac.new(chaining_key, input_key_material, hashlib.sha256).digest()

    # output1 = HMAC(temp, 0x01)
    output1 = hmac.new(temp, b'\x01', hashlib.sha256).digest()

    # output2 = HMAC(temp, output1 || 0x02)
    output2 = hmac.new(temp, output1 + b'\x02', hashlib.sha256).digest()

    return output1, output2


def hkdf_expand(chaining_key: bytes, num_outputs: int = 2) -> list[bytes]:
    """
    HKDF expand-only variant (for splitting).

    Derives multiple keys from a chaining key without additional input.

    Args:
        chaining_key: Current chain key (32 bytes)
        num_outputs: Number of keys to derive (default: 2)

    Returns:
        List of derived keys (32 bytes each)

    Example:
        >>> ck = b'x' * 32
        >>> keys = hkdf_expand(ck, 3)
        >>> len(keys)
        3
        >>> all(len(k) == 32 for k in keys)
        True
    """
    if len(chaining_key) != HASH_LEN:
        raise ValueError(f"Invalid chaining key length: {len(chaining_key)}")

    if num_outputs < 1:
        raise ValueError("num_outputs must be at least 1")

    # temp = HMAC(chain_key, b"")
    temp = hmac.new(chaining_key, b"", hashlib.sha256).digest()

    outputs = []
    prev_output = b""

    for i in range(num_outputs):
        if i == 0:
            # output1 = HMAC(temp, 0x01)
            output = hmac.new(temp, b'\x01', hashlib.sha256).digest()
        elif i == 1:
            # output2 = HMAC(temp, output1 || 0x02)
            output = hmac.new(temp, outputs[0] + b'\x02', hashlib.sha256).digest()
        else:
            # For more outputs: outputN = HMAC(temp, output(N-1) || N)
            output = hmac.new(temp, prev_output + bytes([i + 1]), hashlib.sha256).digest()

        outputs.append(output)
        prev_output = output

    return outputs


# ==================== Hash ====================

def hash(data: bytes) -> bytes:
    """
    Compute SHA256 hash.

    Args:
        data: Data to hash

    Returns:
        32-byte SHA256 digest

    Example:
        >>> h = hash(b'Hello, world!')
        >>> len(h)
        32
    """
    return hashlib.sha256(data).digest()


# ==================== Exceptions ====================

class CryptoError(Exception):
    """Base exception for cryptographic errors."""
    pass


class SignatureError(CryptoError):
    """Raised when signature verification fails."""
    pass


# ==================== Ed25519 Signatures ====================

# Ed25519 key sizes
ED25519_PRIVATE_KEY_LEN = 32
ED25519_PUBLIC_KEY_LEN = 32
ED25519_SIGNATURE_LEN = 64
ED25519_SEED_LEN = 32


def generate_ed25519_keypair() -> Tuple[bytes, bytes]:
    """
    Generate Ed25519 keypair for digital signatures.

    Ed25519 is the recommended signature algorithm for libp2p identity keys.

    Returns:
        Tuple of (private_key, public_key) as bytes (32 bytes each for private,
        32 bytes for public)

    Example:
        >>> priv, pub = generate_ed25519_keypair()
        >>> len(priv), len(pub)
        (32, 32)
    """
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )

    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    return private_bytes, public_bytes


def generate_ed25519_keypair_from_seed(seed: bytes) -> Tuple[bytes, bytes]:
    """
    Generate Ed25519 keypair from a 32-byte seed.

    Args:
        seed: 32-byte seed for deterministic key generation

    Returns:
        Tuple of (private_key, public_key) as bytes

    Raises:
        ValueError: If seed length is not 32 bytes
    """
    if len(seed) != ED25519_SEED_LEN:
        raise ValueError(f"Invalid seed length: {len(seed)} (expected {ED25519_SEED_LEN})")

    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    public_key = private_key.public_key()

    private_bytes = seed
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    return private_bytes, public_bytes


def sign_ed25519(private_key: bytes, message: bytes) -> bytes:
    """
    Sign a message using Ed25519.

    Args:
        private_key: Ed25519 private key (32 bytes)
        message: Message to sign

    Returns:
        64-byte signature

    Raises:
        ValueError: If key length is invalid
        CryptoError: If signing fails

    Example:
        >>> priv, pub = generate_ed25519_keypair()
        >>> msg = b'Hello, world!'
        >>> sig = sign_ed25519(priv, msg)
        >>> len(sig)
        64
    """
    if len(private_key) != ED25519_PRIVATE_KEY_LEN:
        raise ValueError(f"Invalid private key length: {len(private_key)} (expected {ED25519_PRIVATE_KEY_LEN})")

    try:
        priv_key_obj = Ed25519PrivateKey.from_private_bytes(private_key)
        signature = priv_key_obj.sign(message)
        return signature
    except Exception as e:
        raise CryptoError(f"Ed25519 signing failed: {e}") from e


def verify_ed25519(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """
    Verify an Ed25519 signature.

    Args:
        public_key: Ed25519 public key (32 bytes)
        message: Message that was signed
        signature: Signature to verify (64 bytes)

    Returns:
        True if signature is valid

    Raises:
        ValueError: If key or signature length is invalid
        SignatureError: If signature is invalid

    Example:
        >>> priv, pub = generate_ed25519_keypair()
        >>> msg = b'Hello, world!'
        >>> sig = sign_ed25519(priv, msg)
        >>> verify_ed25519(pub, msg, sig)
        True
        >>> verify_ed25519(pub, msg + b'!', sig)
        False
    """
    if len(public_key) != ED25519_PUBLIC_KEY_LEN:
        raise ValueError(f"Invalid public key length: {len(public_key)} (expected {ED25519_PUBLIC_KEY_LEN})")

    if len(signature) != ED25519_SIGNATURE_LEN:
        raise ValueError(f"Invalid signature length: {len(signature)} (expected {ED25519_SIGNATURE_LEN})")

    try:
        pub_key_obj = Ed25519PublicKey.from_public_bytes(public_key)
        pub_key_obj.verify(signature, message)
        return True
    except Exception:
        return False


def ed25519_public_key_from_private(private_key: bytes) -> bytes:
    """
    Derive Ed25519 public key from private key.

    Args:
        private_key: Ed25519 private key (32 bytes)

    Returns:
        Ed25519 public key (32 bytes)

    Raises:
        ValueError: If key length is invalid
    """
    if len(private_key) != ED25519_PRIVATE_KEY_LEN:
        raise ValueError(f"Invalid private key length: {len(private_key)} (expected {ED25519_PRIVATE_KEY_LEN})")

    priv_key_obj = Ed25519PrivateKey.from_private_bytes(private_key)
    pub_key_obj = priv_key_obj.public_key()

    return pub_key_obj.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
