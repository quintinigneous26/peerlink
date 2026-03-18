"""
Redis storage layer for DID service
"""

import json
import logging
from typing import Optional
import asyncio
from datetime import datetime

import redis.asyncio as aioredis

from .config import config
from .models import DeviceInfo, DeviceStatus, HeartbeatInfo

logger = logging.getLogger(__name__)


class DeviceStorage:
    """Redis-based device storage."""

    # Keys
    DEVICE_KEY_PREFIX = "device:"
    DEVICE_INDEX_KEY = "device:index"
    ONLINE_DEVICES_KEY = "devices:online"
    DEVICE_BY_TYPE_KEY = "devices:type:"

    # TTL (seconds)
    DEVICE_TTL = 86400 * 30  # 30 days
    ONLINE_TTL = 180  # 3 minutes (heartbeat should refresh this)

    def __init__(self, redis_url: str | None = None):
        """
        Initialize storage.

        Args:
            redis_url: Redis connection URL (default from config)
        """
        self.redis_url = redis_url or config.redis_url
        self._pool: Optional[aioredis.ConnectionPool] = None

    async def _get_pool(self) -> aioredis.ConnectionPool:
        """Get or create Redis connection pool."""
        if self._pool is None:
            self._pool = aioredis.from_url(
                self.redis_url,
                db=config.redis_db,
                password=config.redis_password,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._pool

    async def close(self) -> None:
        """Close Redis connections."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    def _device_key(self, device_id: str) -> str:
        """Get Redis key for device."""
        return f"{self.DEVICE_KEY_PREFIX}{device_id}"

    def _type_index_key(self, device_type: str) -> str:
        """Get Redis key for device type index."""
        return f"{self.DEVICE_BY_TYPE_KEY}{device_type}"

    async def register_device(
        self,
        device_id: str,
        device_type: str,
        public_key: str,
        capabilities: list[str],
        metadata: dict | None = None,
    ) -> DeviceInfo:
        """
        Register a new device.

        Args:
            device_id: Device identifier
            device_type: Type of device
            public_key: Device public key
            capabilities: List of device capabilities
            metadata: Optional metadata

        Returns:
            DeviceInfo
        """
        pool = await self._get_pool()
        now = int(datetime.now().timestamp())

        device_info = DeviceInfo(
            device_id=device_id,
            device_type=device_type,
            public_key=public_key,
            capabilities=capabilities,
            status=DeviceStatus.ONLINE,
            created_at=now,
            last_seen=now,
            metadata=metadata or {},
        )

        # Store device data
        device_key = self._device_key(device_id)
        await pool.hset(device_key, mapping=device_info.to_dict())
        await pool.expire(device_key, self.DEVICE_TTL)

        # Add to type index
        type_key = self._type_index_key(device_type)
        await pool.sadd(type_key, device_id)

        # Add to online set
        await pool.sadd(self.ONLINE_DEVICES_KEY, device_id)
        await pool.expire(self.ONLINE_DEVICES_KEY, self.ONLINE_TTL)

        logger.info(f"Device registered: {device_id} ({device_type})")
        return device_info

    async def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        """
        Get device information.

        Args:
            device_id: Device identifier

        Returns:
            DeviceInfo or None if not found
        """
        pool = await self._get_pool()
        device_key = self._device_key(device_id)

        data = await pool.hgetall(device_key)
        if not data:
            return None

        return DeviceInfo.from_dict(data)

    async def update_heartbeat(self, device_id: str) -> bool:
        """
        Update device heartbeat.

        Args:
            device_id: Device identifier

        Returns:
            True if device exists and was updated
        """
        pool = await self._get_pool()
        device_key = self._device_key(device_id)

        # Check if device exists
        exists = await pool.exists(device_key)
        if not exists:
            return False

        now = int(datetime.now().timestamp())
        await pool.hset(device_key, "last_seen", now)
        await pool.hset(device_key, "status", DeviceStatus.ONLINE.value)

        # Refresh online status
        await pool.sadd(self.ONLINE_DEVICES_KEY, device_id)
        await pool.expire(self.ONLINE_DEVICES_KEY, self.ONLINE_TTL)

        logger.debug(f"Heartbeat updated for {device_id}")
        return True

    async def set_device_status(self, device_id: str, status: DeviceStatus) -> bool:
        """
        Set device status.

        Args:
            device_id: Device identifier
            status: New status

        Returns:
            True if device exists
        """
        pool = await self._get_pool()
        device_key = self._device_key(device_id)

        exists = await pool.exists(device_key)
        if not exists:
            return False

        await pool.hset(device_key, "status", status.value)

        if status == DeviceStatus.OFFLINE:
            await pool.srem(self.ONLINE_DEVICES_KEY, device_id)
        else:
            await pool.sadd(self.ONLINE_DEVICES_KEY, device_id)
            await pool.expire(self.ONLINE_DEVICES_KEY, self.ONLINE_TTL)

        return True

    async def is_online(self, device_id: str) -> bool:
        """
        Check if device is online.

        Args:
            device_id: Device identifier

        Returns:
            True if device is online
        """
        pool = await self._get_pool()
        return await pool.sismember(self.ONLINE_DEVICES_KEY, device_id)

    async def get_online_devices(self) -> set[str]:
        """
        Get set of online device IDs.

        Returns:
            Set of online device IDs
        """
        pool = await self._get_pool()
        members = await pool.smembers(self.ONLINE_DEVICES_KEY)
        return set(members) if members else set()

    async def get_devices_by_type(self, device_type: str) -> list[str]:
        """
        Get devices of a specific type.

        Args:
            device_type: Device type

        Returns:
            List of device IDs
        """
        pool = await self._get_pool()
        type_key = self._type_index_key(device_type)
        members = await pool.smembers(type_key)
        return list(members) if members else []

    async def delete_device(self, device_id: str) -> bool:
        """
        Delete a device.

        Args:
            device_id: Device identifier

        Returns:
            True if device was deleted
        """
        pool = await self._get_pool()
        device_key = self._device_key(device_id)

        # Get device info before deletion
        device = await self.get_device(device_id)
        if not device:
            return False

        # Remove from indexes
        type_key = self._type_index_key(device.device_type)
        await pool.srem(type_key, device_id)
        await pool.srem(self.ONLINE_DEVICES_KEY, device_id)

        # Delete device data
        await pool.delete(device_key)

        logger.info(f"Device deleted: {device_id}")
        return True

    async def cleanup_stale_devices(self, timeout_seconds: int) -> int:
        """
        Clean up devices that haven't sent heartbeat recently.

        Args:
            timeout_seconds: Seconds since last heartbeat to consider stale

        Returns:
            Number of devices marked offline
        """
        pool = await self._get_pool()
        now = int(datetime.now().timestamp())
        cutoff = now - timeout_seconds
        count = 0

        # Get all online devices
        online_devices = await self.get_online_devices()

        for device_id in online_devices:
            device = await self.get_device(device_id)
            if device and device.last_seen < cutoff:
                await self.set_device_status(device_id, DeviceStatus.OFFLINE)
                count += 1
                logger.info(f"Device marked offline: {device_id}")

        return count


# Global storage instance
_storage: Optional[DeviceStorage] = None


def get_storage() -> DeviceStorage:
    """Get global storage instance."""
    global _storage
    if _storage is None:
        _storage = DeviceStorage()
    return _storage
