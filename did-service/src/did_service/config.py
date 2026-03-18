"""
DID Service Configuration

Security Notice:
- JWT_SECRET must be set via environment variable in production
- Minimum key length: 32 characters
- Use: python -c "import secrets; print(secrets.token_urlsafe(32))"
"""

import os
import sys
from dataclasses import dataclass
from typing import Literal, Optional


def _get_jwt_secret() -> str:
    """
    Get JWT secret with security validation.

    In production: JWT_SECRET is required (min 32 chars)
    In development: Allow default for convenience

    Returns:
        JWT secret string
    """
    environment = os.getenv("ENVIRONMENT", "development")
    secret = os.getenv("JWT_SECRET")

    if environment == "production":
        if not secret:
            print("[ERROR] JWT_SECRET environment variable is required in production")
            print("[INFO] Generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
            sys.exit(1)
        if len(secret) < 32:
            print("[ERROR] JWT_SECRET must be at least 32 characters in production")
            sys.exit(1)
        return secret
    else:
        # Development mode: allow default but warn
        if not secret:
            print("[WARNING] Using default JWT secret. Set JWT_SECRET environment variable for security.")
            return "dev-secret-key-change-in-production-min-32-chars"
        return secret


@dataclass(frozen=True)
class Config:
    """Service configuration."""

    # Environment
    environment: Literal["development", "staging", "production"] = os.getenv("ENVIRONMENT", "development")

    # Server settings
    host: str = os.getenv("DID_SERVICE_HOST", "0.0.0.0")
    port: int = int(os.getenv("DID_SERVICE_PORT", "9000"))

    # Redis settings
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: str | None = os.getenv("REDIS_PASSWORD")

    # Device ID settings
    did_prefix: str = os.getenv("DID_PREFIX", "did:p2p")
    device_id_random_bytes: int = int(os.getenv("DEVICE_ID_RANDOM_BYTES", "16"))

    # JWT settings - Secure by default
    jwt_secret: str = _get_jwt_secret()
    jwt_expiration: int = int(os.getenv("JWT_EXPIRATION", "3600"))  # seconds
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")

    # Key rotation settings
    jwt_previous_secret: str | None = os.getenv("JWT_PREVIOUS_SECRET")  # For key rotation
    jwt_rotation_enabled: bool = os.getenv("JWT_ROTATION_ENABLED", "false").lower() == "true"

    # Heartbeat settings
    heartbeat_timeout: int = int(os.getenv("HEARTBEAT_TIMEOUT", "120"))  # seconds

    # Device types
    valid_device_types: set[str] = frozenset({"ios", "android", "web", "desktop"})

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    def validate(self) -> bool:
        """
        Validate configuration.

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid
        """
        errors = []

        # Validate JWT settings
        if len(self.jwt_secret) < 32:
            errors.append("jwt_secret must be at least 32 characters")

        if self.jwt_expiration < 60:
            errors.append("jwt_expiration must be at least 60 seconds")

        if self.jwt_expiration > 86400 * 7:  # 7 days
            errors.append("jwt_expiration should not exceed 7 days for security")

        # Validate Redis URL
        if not self.redis_url.startswith(("redis://", "rediss://")):
            errors.append("redis_url must start with redis:// or rediss://")

        if errors:
            raise ValueError("Configuration validation failed: " + "; ".join(errors))

        return True


# Global config instance (initialized on import)
config = Config()

# Validate on startup in production
if config.is_production():
    try:
        config.validate()
        print(f"[INFO] Configuration validated successfully for {config.environment} environment")
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
