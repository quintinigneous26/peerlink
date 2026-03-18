"""
Security module for P2P Engine.

Provides cryptographic primitives and secure channel implementations.
"""

from .crypto import (
    # Key generation
    generate_x25519_keypair,
    generate_ed25519_keypair,
    generate_ed25519_keypair_from_seed,

    # DH operations
    dh,

    # Ed25519 signatures
    sign_ed25519,
    verify_ed25519,
    ed25519_public_key_from_private,

    # AEAD encryption
    encrypt,
    decrypt,

    # HKDF
    hkdf,
    hkdf_expand,

    # Hash
    hash,

    # Constants
    DH_LEN,
    HASH_LEN,
    KEY_LEN,
    NONCE_LEN,
    TAG_LEN,
    ED25519_PRIVATE_KEY_LEN,
    ED25519_PUBLIC_KEY_LEN,
    ED25519_SIGNATURE_LEN,
    ED25519_SEED_LEN,

    # Protocol name
    NOISE_PROTOCOL_NAME,

    # Exceptions
    CryptoError,
    SignatureError,
)

__all__ = [
    # Key generation
    "generate_x25519_keypair",
    "generate_ed25519_keypair",
    "generate_ed25519_keypair_from_seed",

    # DH operations
    "dh",

    # Ed25519 signatures
    "sign_ed25519",
    "verify_ed25519",
    "ed25519_public_key_from_private",

    # AEAD encryption
    "encrypt",
    "decrypt",

    # HKDF
    "hkdf",
    "hkdf_expand",

    # Hash
    "hash",

    # Constants
    "DH_LEN",
    "HASH_LEN",
    "KEY_LEN",
    "NONCE_LEN",
    "TAG_LEN",
    "ED25519_PRIVATE_KEY_LEN",
    "ED25519_PUBLIC_KEY_LEN",
    "ED25519_SIGNATURE_LEN",
    "ED25519_SEED_LEN",

    # Protocol name
    "NOISE_PROTOCOL_NAME",

    # Exceptions
    "CryptoError",
    "SignatureError",
]
