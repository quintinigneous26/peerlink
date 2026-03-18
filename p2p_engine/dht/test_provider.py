"""
Unit tests for Kademlia DHT Provider Manager

Tests for provider record management, announcements, and lookups.
"""

import asyncio
import pytest
import time
from p2p_engine.dht.provider import (
    ProviderRecord,
    ProviderManager,
    compute_key,
    create_provider_message,
    parse_provider_message,
    PROVIDER_EXPIRATION,
    MAX_PROVIDERS_PER_KEY,
)


class TestProviderRecord:
    """Tests for ProviderRecord dataclass."""

    def test_provider_record_creation(self):
        """Test creating a provider record."""
        peer_id = b"\x01" * 32
        key = b"\x02" * 32

        record = ProviderRecord(peer_id=peer_id, key=key)

        assert record.peer_id == peer_id
        assert record.key == key
        assert not record.is_expired()

    def test_provider_record_expiration(self):
        """Test provider record expiration."""
        peer_id = b"\x01" * 32
        key = b"\x02" * 32

        # Create record that expires immediately
        record = ProviderRecord(
            peer_id=peer_id,
            key=key,
            expires=time.time() - 1
        )

        assert record.is_expired()

    def test_provider_record_refresh(self):
        """Test refreshing provider record."""
        peer_id = b"\x01" * 32
        key = b"\x02" * 32

        record = ProviderRecord(
            peer_id=peer_id,
            key=key,
            expires=time.time() - 1
        )

        assert record.is_expired()

        record.refresh(ttl=3600)

        assert not record.is_expired()


class TestComputeKey:
    """Tests for DHT key computation."""

    def test_compute_key_consistent(self):
        """Test key computation is consistent."""
        input_key = b"test_content_id"

        key1 = compute_key(input_key)
        key2 = compute_key(input_key)

        assert key1 == key2

    def test_compute_key_length(self):
        """Test computed key is correct length."""
        input_key = b"test_content_id"

        dht_key = compute_key(input_key)

        assert len(dht_key) == 32  # SHA-256 output

    def test_compute_key_different_inputs(self):
        """Test different inputs produce different keys."""
        key1 = compute_key(b"content_1")
        key2 = compute_key(b"content_2")

        assert key1 != key2


class TestProviderManager:
    """Tests for ProviderManager."""

    @pytest.fixture
    def manager(self):
        """ProviderManager instance for testing."""
        return ProviderManager(max_providers=5)

    def test_manager_creation(self, manager):
        """Test creating provider manager."""
        assert manager.max_providers == 5
        assert manager.provider_count == 0
        assert manager.key_count == 0

    @pytest.mark.asyncio
    async def test_add_provider(self, manager):
        """Test adding a provider."""
        key = b"test_cid"
        peer_id = b"\x01" * 32

        result = await manager.add_provider(key, peer_id)

        assert result is True
        assert manager.provider_count == 1
        assert manager.key_count == 1

    @pytest.mark.asyncio
    async def test_add_duplicate_provider(self, manager):
        """Test adding duplicate provider refreshes record."""
        key = b"test_cid"
        peer_id = b"\x01" * 32

        await manager.add_provider(key, peer_id)
        await manager.add_provider(key, peer_id)

        # Should still have 1 record
        assert manager.provider_count == 1

    @pytest.mark.asyncio
    async def test_add_multiple_providers_same_key(self, manager):
        """Test adding multiple providers for same key."""
        key = b"test_cid"

        for i in range(5):
            peer_id = bytes([i]) * 32
            await manager.add_provider(key, peer_id)

        assert manager.provider_count == 5
        assert manager.key_count == 1

    @pytest.mark.asyncio
    async def test_add_provider_exceeds_max(self, manager):
        """Test adding providers beyond max replaces oldest."""
        key = b"test_cid"

        # Add max providers
        for i in range(5):
            peer_id = bytes([i]) * 32
            await manager.add_provider(key, peer_id)

        # Add one more
        new_peer_id = b"\xff" * 32
        await manager.add_provider(key, new_peer_id)

        # Should still have max providers
        providers = manager.get_providers(key)
        assert len(providers) <= 5

    @pytest.mark.asyncio
    async def test_remove_provider(self, manager):
        """Test removing a provider."""
        key = b"test_cid"
        peer_id = b"\x01" * 32

        await manager.add_provider(key, peer_id)
        removed = await manager.remove_provider(key, peer_id)

        assert removed is True
        assert manager.provider_count == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent_provider(self, manager):
        """Test removing non-existent provider."""
        key = b"test_cid"
        peer_id = b"\x01" * 32

        removed = await manager.remove_provider(key, peer_id)

        assert removed is False

    def test_get_providers(self, manager):
        """Test getting providers for a key."""
        key = b"test_cid"

        # Add providers synchronously (bypass async)
        asyncio.run(manager.add_provider(key, b"\x01" * 32))
        asyncio.run(manager.add_provider(key, b"\x02" * 32))

        providers = manager.get_providers(key)

        assert len(providers) == 2

    @pytest.mark.asyncio
    async def test_add_local_provider(self, manager):
        """Test adding local provider."""
        key = b"test_cid"

        await manager.add_local_provider(key)

        assert manager.is_providing(key)

    @pytest.mark.asyncio
    async def test_remove_local_provider(self, manager):
        """Test removing local provider."""
        key = b"test_cid"

        await manager.add_local_provider(key)
        await manager.remove_local_provider(key)

        assert not manager.is_providing(key)

    def test_get_local_providers(self, manager):
        """Test getting all local providers."""
        keys = [b"key1", b"key2", b"key3"]

        for key in keys:
            asyncio.run(manager.add_local_provider(key))

        local = manager.get_local_providers()

        assert set(local) == set(keys)

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, manager):
        """Test cleaning up expired providers."""
        key = b"test_cid"

        # Add provider that's already expired
        peer_id = b"\x01" * 32
        await manager.add_provider(key, peer_id, ttl=-1)

        assert manager.provider_count == 1

        removed = await manager.cleanup_expired()

        assert removed == 1
        assert manager.provider_count == 0

    @pytest.mark.asyncio
    async def test_get_providers_with_limit(self, manager):
        """Test getting providers with count limit."""
        key = b"test_cid"

        for i in range(10):
            peer_id = bytes([i]) * 32
            await manager.add_provider(key, peer_id)

        providers = manager.get_providers(key, max_count=5)

        assert len(providers) == 5


class TestProviderMessages:
    """Tests for provider message encoding/decoding."""

    def test_create_provider_message(self):
        """Test creating provider message."""
        key = b"test_cid"
        peer_id = b"\x01" * 32

        message = create_provider_message(key, peer_id)

        assert len(message) == 1 + len(key) + len(peer_id)

    def test_parse_provider_message(self):
        """Test parsing provider message."""
        key = b"test_cid"
        peer_id = b"\x01" * 32

        message = create_provider_message(key, peer_id)
        parsed_key, parsed_peer_id = parse_provider_message(message)

        assert parsed_key == key
        assert parsed_peer_id == peer_id

    def test_parse_invalid_message(self):
        """Test parsing invalid message."""
        invalid_message = b"\x01"  # Length byte but no data

        with pytest.raises(ValueError):
            parse_provider_message(invalid_message)

    def test_roundtrip_message(self):
        """Test roundtrip message encoding/decoding."""
        keys = [b"key1", b"key2", b"longer_key_here"]

        for key in keys:
            peer_id = b"\xab" * 32
            message = create_provider_message(key, peer_id)
            parsed_key, parsed_peer_id = parse_provider_message(message)

            assert parsed_key == key
            assert parsed_peer_id == peer_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
