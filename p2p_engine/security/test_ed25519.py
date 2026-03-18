"""
Test Ed25519 signature functionality.

This module tests the Ed25519 signature operations added to the security layer.
"""
import pytest

from p2p_engine.security.crypto import (
    generate_ed25519_keypair,
    generate_ed25519_keypair_from_seed,
    sign_ed25519,
    verify_ed25519,
    ed25519_public_key_from_private,
    CryptoError,
    SignatureError,
)


def test_generate_ed25519_keypair():
    """Test Ed25519 keypair generation."""
    private_key, public_key = generate_ed25519_keypair()

    assert len(private_key) == 32
    assert len(public_key) == 32
    assert private_key != public_key


def test_generate_ed25519_keypair_from_seed():
    """Test deterministic Ed25519 keypair generation from seed."""
    seed = b"0123456789abcdef0123456789abcdef"

    private_key1, public_key1 = generate_ed25519_keypair_from_seed(seed)
    private_key2, public_key2 = generate_ed25519_keypair_from_seed(seed)

    # Same seed should produce same keys
    assert private_key1 == private_key2
    assert public_key1 == public_key2

    # Different seeds should produce different keys
    different_seed = b"0123456789abcdef0123456789abcdee"
    private_key3, public_key3 = generate_ed25519_keypair_from_seed(different_seed)

    assert private_key1 != private_key3
    assert public_key1 != public_key3


def test_ed25519_sign_and_verify():
    """Test Ed25519 signing and verification."""
    private_key, public_key = generate_ed25519_keypair()
    message = b"Hello, libp2p!"

    # Sign the message
    signature = sign_ed25519(private_key, message)
    assert len(signature) == 64

    # Verify the signature
    assert verify_ed25519(public_key, message, signature) is True

    # Wrong message should fail verification
    assert verify_ed25519(public_key, message + b"!", signature) is False

    # Wrong public key should fail verification
    _, wrong_public_key = generate_ed25519_keypair()
    assert verify_ed25519(wrong_public_key, message, signature) is False


def test_ed25519_public_key_from_private():
    """Test deriving public key from private key."""
    private_key, public_key = generate_ed25519_keypair()

    derived_public_key = ed25519_public_key_from_private(private_key)
    assert derived_public_key == public_key


def test_ed25519_invalid_key_lengths():
    """Test that invalid key lengths are rejected."""
    with pytest.raises(ValueError):
        generate_ed25519_keypair_from_seed(b"too_short")

    with pytest.raises(ValueError):
        generate_ed25519_keypair_from_seed(b"way_too_long" * 10)

    private_key, public_key = generate_ed25519_keypair()
    message = b"test"

    with pytest.raises(ValueError):
        sign_ed25519(b"short", message)

    with pytest.raises(ValueError):
        verify_ed25519(b"short", message, b"x" * 64)

    with pytest.raises(ValueError):
        verify_ed25519(public_key, message, b"short")


def test_noise_libp2p_static_key_signing():
    """Test signing the noise-libp2p-static-key prefix as per libp2p spec."""
    private_key, public_key = generate_ed25519_keypair()

    # The prefix specified in libp2p Noise spec
    prefix = b"noise-libp2p-static-key:"
    static_noise_key = b"0123456789abcdef0123456789abcdef"  # 32 bytes

    signed_data = prefix + static_noise_key
    signature = sign_ed25519(private_key, signed_data)

    assert len(signature) == 64
    assert verify_ed25519(public_key, signed_data, signature) is True

    # Tampering should fail verification
    tampered_data = prefix + b"0123456789abcdef0123456789abcdee"
    assert verify_ed25519(public_key, tampered_data, signature) is False


def test_ed25519_multiple_signatures():
    """Test that different messages produce different signatures."""
    private_key, public_key = generate_ed25519_keypair()

    messages = [
        b"message 1",
        b"message 2",
        b"different message",
        b"",
    ]

    signatures = [sign_ed25519(private_key, msg) for msg in messages]

    # All signatures should verify with their respective messages
    for msg, sig in zip(messages, signatures):
        assert verify_ed25519(public_key, msg, sig) is True

    # Signatures should be different (with very high probability)
    # Except potentially for empty message vs empty message which should be the same
    unique_signatures = set(sig.tobytes() if hasattr(sig, 'tobytes') else sig for sig in signatures)
    assert len(unique_signatures) >= len(messages) - 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
