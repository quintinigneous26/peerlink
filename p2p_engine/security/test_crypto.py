"""
Tests for cryptographic primitives.

Tests cover:
- X25519 key generation and DH
- ChaCha20-Poly1305 encryption/decryption
- HKDF key derivation
- SHA256 hashing
"""

import pytest

from .crypto import (
    # Functions
    generate_x25519_keypair,
    dh,
    encrypt,
    decrypt,
    hkdf,
    hkdf_expand,
    hash,

    # Constants
    DH_LEN,
    HASH_LEN,
    KEY_LEN,
    NONCE_LEN,
    TAG_LEN,
    NOISE_PROTOCOL_NAME,

    # Exceptions
    CryptoError,
)


# ==================== Protocol Name ====================

def test_noise_protocol_name():
    """Test that protocol name matches Noise spec."""
    assert NOISE_PROTOCOL_NAME == b"Noise_XX_25519_ChaChaPoly_SHA256"


# ==================== Constants ====================

def test_constants():
    """Test cryptographic constants are correct."""
    assert DH_LEN == 32  # X25519
    assert HASH_LEN == 32  # SHA256
    assert KEY_LEN == 32  # ChaCha20
    assert NONCE_LEN == 12  # 96-bit nonce
    assert TAG_LEN == 16  # Poly1305


# ==================== Key Generation ====================

def test_generate_keypair():
    """Test X25519 keypair generation."""
    priv, pub = generate_x25519_keypair()

    assert len(priv) == DH_LEN
    assert len(pub) == DH_LEN
    assert priv != pub  # Private and public keys should differ


def test_generate_unique_keys():
    """Test that multiple generations produce different keys."""
    priv1, pub1 = generate_x25519_keypair()
    priv2, pub2 = generate_x25519_keypair()

    # Keys should be unique
    assert priv1 != priv2
    assert pub1 != pub2


# ==================== Diffie-Hellman ====================

def test_dh_shared_secret():
    """Test that DH produces same shared secret for both parties."""
    priv1, pub1 = generate_x25519_keypair()
    priv2, pub2 = generate_x25519_keypair()

    shared1 = dh(priv1, pub2)
    shared2 = dh(priv2, pub1)

    assert shared1 == shared2
    assert len(shared1) == DH_LEN


def test_dh_invalid_key_length():
    """Test DH rejects invalid key lengths."""
    priv, _ = generate_x25519_keypair()

    with pytest.raises(ValueError, match="Invalid private key length"):
        dh(priv[:16], b"x" * 32)

    with pytest.raises(ValueError, match="Invalid public key length"):
        dh(priv, b"x" * 16)


def test_dh_deterministic():
    """Test DH is deterministic with same inputs."""
    priv, pub = generate_x25519_keypair()

    shared1 = dh(priv, pub)
    shared2 = dh(priv, pub)

    assert shared1 == shared2


# ==================== AEAD Encryption ====================

def test_encrypt_decrypt():
    """Test basic encryption and decryption."""
    key = b"x" * KEY_LEN
    plaintext = b"Hello, world!"

    ciphertext = encrypt(key, 0, plaintext)
    decrypted = decrypt(key, 0, ciphertext)

    assert decrypted == plaintext


def test_encrypt_ciphertext_length():
    """Test ciphertext includes authentication tag."""
    key = b"x" * KEY_LEN
    plaintext = b"Hello, world!"

    ciphertext = encrypt(key, 0, plaintext)

    assert len(ciphertext) == len(plaintext) + TAG_LEN


def test_encrypt_with_aad():
    """Test encryption with additional authenticated data."""
    key = b"x" * KEY_LEN
    plaintext = b"Hello, world!"
    aad = b"additional data"

    ciphertext = encrypt(key, 0, plaintext, aad)
    decrypted = decrypt(key, 0, ciphertext, aad)

    assert decrypted == plaintext


def test_encrypt_wrong_aad_fails():
    """Test decryption fails with wrong AAD."""
    key = b"x" * KEY_LEN
    plaintext = b"Hello, world!"
    aad1 = b"additional data 1"
    aad2 = b"additional data 2"

    ciphertext = encrypt(key, 0, plaintext, aad1)

    with pytest.raises(CryptoError, match="Decryption failed"):
        decrypt(key, 0, ciphertext, aad2)


def test_encrypt_wrong_key_fails():
    """Test decryption fails with wrong key."""
    key1 = b"x" * KEY_LEN
    key2 = b"y" * KEY_LEN
    plaintext = b"Hello, world!"

    ciphertext = encrypt(key1, 0, plaintext)

    with pytest.raises(CryptoError, match="Decryption failed"):
        decrypt(key2, 0, ciphertext)


def test_encrypt_different_nonce():
    """Test different nonce produces different ciphertext."""
    key = b"x" * KEY_LEN
    plaintext = b"Hello, world!"

    ct1 = encrypt(key, 0, plaintext)
    ct2 = encrypt(key, 1, plaintext)

    assert ct1 != ct2


def test_encrypt_invalid_key_length():
    """Test encryption rejects invalid key length."""
    with pytest.raises(ValueError, match="Invalid key length"):
        encrypt(b"short", 0, b"plaintext")


def test_nonce_exhaustion():
    """Test nonce exhaustion check."""
    key = b"x" * KEY_LEN

    with pytest.raises(ValueError, match="Nonce exhausted"):
        encrypt(key, 2**64, b"plaintext")


# ==================== HKDF ====================

def test_hkdf_lengths():
    """Test HKDF produces correct key lengths."""
    ck = b"x" * HASH_LEN
    ikm = b"y" * DH_LEN

    new_ck, k = hkdf(ck, ikm)

    assert len(new_ck) == HASH_LEN
    assert len(k) == HASH_LEN


def test_hkdf_deterministic():
    """Test HKDF is deterministic with same inputs."""
    ck = b"x" * HASH_LEN
    ikm = b"y" * DH_LEN

    ck1, k1 = hkdf(ck, ikm)
    ck2, k2 = hkdf(ck, ikm)

    assert ck1 == ck2
    assert k1 == k2


def test_hkdf_chain():
    """Test HKDF can chain multiple derivations."""
    ck = b"x" * HASH_LEN

    # First derivation
    ikm1 = b"input_1"
    ck, k1 = hkdf(ck, ikm1)

    # Second derivation
    ikm2 = b"input_2"
    ck, k2 = hkdf(ck, ikm2)

    assert len(k1) == HASH_LEN
    assert len(k2) == HASH_LEN
    assert k1 != k2


def test_hkdf_invalid_chaining_key():
    """Test HKDF rejects invalid chaining key length."""
    with pytest.raises(ValueError, match="Invalid chaining key length"):
        hkdf(b"short", b"ikm")


def test_hkdf_expand():
    """Test HKDF expand-only variant."""
    ck = b"x" * HASH_LEN

    keys = hkdf_expand(ck, 2)

    assert len(keys) == 2
    assert all(len(k) == HASH_LEN for k in keys)
    assert keys[0] != keys[1]


def test_hkdf_expand_single():
    """Test HKDF expand with single output."""
    ck = b"x" * HASH_LEN

    keys = hkdf_expand(ck, 1)

    assert len(keys) == 1
    assert len(keys[0]) == HASH_LEN


def test_hkdf_expand_multiple():
    """Test HKDF expand with multiple outputs."""
    ck = b"x" * HASH_LEN

    keys = hkdf_expand(ck, 5)

    assert len(keys) == 5
    assert all(len(k) == HASH_LEN for k in keys)


# ==================== Hash ====================

def test_hash_length():
    """Test SHA256 produces correct length."""
    data = b"Hello, world!"
    h = hash(data)

    assert len(h) == HASH_LEN


def test_hash_deterministic():
    """Test hash is deterministic."""
    data = b"Hello, world!"

    h1 = hash(data)
    h2 = hash(data)

    assert h1 == h2


def test_hash_different_inputs():
    """Test different inputs produce different hashes."""
    h1 = hash(b"input_1")
    h2 = hash(b"input_2")

    assert h1 != h2


def test_hash_empty_input():
    """Test hash of empty input."""
    h = hash(b"")

    assert len(h) == HASH_LEN
    # SHA256 of empty string is a known value
    assert h == bytes.fromhex("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")


# ==================== Integration Tests ====================

def test_noise_kdf_chain():
    """
    Test KDF chain as used in Noise handshake.

    Simulates the key derivation during Noise XX handshake:
    1. Initialize with hash of protocol name
    2. Mix key from ee DH
    3. Mix key from es DH
    4. Split into two cipher keys
    """
    # h = HASH(protocol_name)
    h = hash(NOISE_PROTOCOL_NAME)
    ck = h  # ck = h initially

    # Simulate ee DH
    ee_shared = dh(generate_x25519_keypair()[0], generate_x25519_keypair()[1])
    ck, k1 = hkdf(ck, ee_shared)

    # Simulate es DH
    es_shared = dh(generate_x25519_keypair()[0], generate_x25519_keypair()[1])
    ck, k2 = hkdf(ck, es_shared)

    # Split into two cipher keys
    keys = hkdf_expand(ck, 2)
    k_tx, k_rx = keys[0], keys[1]

    assert len(k_tx) == KEY_LEN
    assert len(k_rx) == KEY_LEN
    assert k_tx != k_rx


def test_full_encrypt_round_trip():
    """Test full encryption round trip with derived keys."""
    # Generate key via HKDF
    ck = b"x" * HASH_LEN
    ikm = b"y" * DH_LEN
    _, k = hkdf(ck, ikm)

    # Encrypt/decrypt
    plaintext = b"Important secret message"
    aad = b"context"

    ct = encrypt(k, 0, plaintext, aad)
    pt = decrypt(k, 0, ct, aad)

    assert pt == plaintext


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
