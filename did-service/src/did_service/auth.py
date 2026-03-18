"""
JWT Token management for DID service
"""

import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from .config import config

logger = logging.getLogger(__name__)


class TokenManager:
    """Manage JWT tokens for device authentication."""

    def __init__(self, secret: str | None = None, expiration: int | None = None):
        """
        Initialize token manager.

        Args:
            secret: JWT secret key (default from config)
            expiration: Token expiration time in seconds (default from config)
        """
        self.secret = secret or config.jwt_secret
        self.expiration = expiration or config.jwt_expiration
        self.algorithm = config.jwt_algorithm

    def generate_token(
        self,
        device_id: str,
        device_type: str,
        extra_claims: dict | None = None,
    ) -> str:
        """
        Generate a JWT token for a device.

        Args:
            device_id: Device identifier
            device_type: Type of device
            extra_claims: Optional additional claims

        Returns:
            JWT token string
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self.expiration)

        payload = {
            "device_id": device_id,
            "device_type": device_type,
            "iat": int(now.timestamp()),
            "exp": int(expires.timestamp()),
        }

        if extra_claims:
            payload.update(extra_claims)

        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        logger.debug(f"Token generated for {device_id}")
        return token

    def verify_token(self, token: str) -> Optional[dict]:
        """
        Verify a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
            )
            logger.debug(f"Token verified for {payload.get('device_id')}")
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def decode_token(self, token: str) -> Optional[dict]:
        """
        Decode a JWT token without verification.

        Args:
            token: JWT token string

        Returns:
            Decoded payload or None
        """
        try:
            # Decode without verification
            payload = jwt.decode(
                token,
                options={"verify_signature": False},
                algorithms=[self.algorithm],
            )
            return payload
        except Exception as e:
            logger.warning(f"Failed to decode token: {e}")
            return None

    def get_expiration(self) -> int:
        """Get token expiration time in seconds."""
        return self.expiration


# Global token manager instance
_token_manager: Optional[TokenManager] = None


def get_token_manager() -> TokenManager:
    """Get global token manager instance."""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager
