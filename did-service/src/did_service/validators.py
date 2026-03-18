"""
Input Validation Utilities

Provides comprehensive input validation for all API endpoints.
Security-focused validation to prevent injection attacks.
"""

import re
import html
from typing import Optional, Any
from functools import wraps


# DID格式: PREFIX-XXXXXX-YYYYY
# PREFIX: ios, android, web, desktop
# XXXXXX: 6字符十六进制
# YYYYY: 5字符字母数字
DID_PATTERN = re.compile(
    r"^(ios|android|web|desktop)-[0-9A-Fa-f]{6}-[0-9A-HJ-NP-Z]{5}$"
)

# 签名格式: 十六进制字符串 (Ed25519签名64字节)
SIGNATURE_PATTERN = re.compile(r"^[0-9a-fA-F]{128}$")

# Challenge格式: 任意可打印字符，16-256字符
CHALLENGE_MIN_LENGTH = 16
CHALLENGE_MAX_LENGTH = 256

# Metadata大小限制
METADATA_MAX_SIZE = 4096  # bytes
METADATA_MAX_KEYS = 50

# Capabilities限制
MAX_CAPABILITIES = 20
VALID_CAPABILITIES = frozenset({
    "p2p", "relay", "video", "audio", "screen_share",
    "file_transfer", "chat", "whiteboard", "recording"
})


class ValidationError(Exception):
    """Validation error with details."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def validate_did(device_id: str) -> str:
    """
    Validate Device ID (DID) format.

    Args:
        device_id: Device identifier string

    Returns:
        Validated device_id

    Raises:
        ValidationError: If format is invalid
    """
    if not device_id:
        raise ValidationError("device_id", "Device ID is required")

    if not isinstance(device_id, str):
        raise ValidationError("device_id", "Device ID must be a string")

    # 长度检查
    if len(device_id) > 64:
        raise ValidationError("device_id", "Device ID too long (max 64 chars)")

    # 格式检查
    if not DID_PATTERN.match(device_id):
        raise ValidationError(
            "device_id",
            f"Invalid DID format. Expected: PREFIX-XXXXXX-YYYYY, got: {device_id[:20]}..."
        )

    # 安全检查: 防止注入
    if any(c in device_id for c in ["<", ">", '"', "'", "&", "\n", "\r", "\0"]):
        raise ValidationError("device_id", "Device ID contains invalid characters")

    return device_id


def validate_signature(signature: str) -> str:
    """
    Validate signature format.

    Args:
        signature: Hex-encoded signature string

    Returns:
        Validated signature (lowercase)

    Raises:
        ValidationError: If format is invalid
    """
    if not signature:
        raise ValidationError("signature", "Signature is required")

    if not isinstance(signature, str):
        raise ValidationError("signature", "Signature must be a string")

    # 长度检查 (Ed25519签名 = 64字节 = 128十六进制字符)
    if len(signature) != 128:
        raise ValidationError(
            "signature",
            f"Invalid signature length. Expected 128 chars, got {len(signature)}"
        )

    # 格式检查
    if not SIGNATURE_PATTERN.match(signature):
        raise ValidationError("signature", "Signature must be 128 hex characters")

    return signature.lower()


def validate_challenge(challenge: str) -> str:
    """
    Validate challenge string.

    Args:
        challenge: Challenge string

    Returns:
        Validated challenge

    Raises:
        ValidationError: If format is invalid
    """
    if not challenge:
        raise ValidationError("challenge", "Challenge is required")

    if not isinstance(challenge, str):
        raise ValidationError("challenge", "Challenge must be a string")

    # 长度检查
    if len(challenge) < CHALLENGE_MIN_LENGTH:
        raise ValidationError(
            "challenge",
            f"Challenge too short. Min {CHALLENGE_MIN_LENGTH} chars"
        )

    if len(challenge) > CHALLENGE_MAX_LENGTH:
        raise ValidationError(
            "challenge",
            f"Challenge too long. Max {CHALLENGE_MAX_LENGTH} chars"
        )

    # 安全检查: 只允许可打印ASCII字符
    if not all(32 <= ord(c) <= 126 for c in challenge):
        raise ValidationError("challenge", "Challenge contains invalid characters")

    # HTML转义防止XSS
    sanitized = html.escape(challenge)
    if sanitized != challenge:
        raise ValidationError("challenge", "Challenge contains potentially dangerous content")

    return challenge


def validate_metadata(metadata: dict) -> dict:
    """
    Validate metadata dictionary.

    Args:
        metadata: Metadata dictionary

    Returns:
        Validated metadata

    Raises:
        ValidationError: If format is invalid
    """
    if not isinstance(metadata, dict):
        raise ValidationError("metadata", "Metadata must be a dictionary")

    # 键数量检查
    if len(metadata) > METADATA_MAX_KEYS:
        raise ValidationError(
            "metadata",
            f"Too many keys. Max {METADATA_MAX_KEYS}, got {len(metadata)}"
        )

    # 大小检查
    import json
    try:
        size = len(json.dumps(metadata))
        if size > METADATA_MAX_SIZE:
            raise ValidationError(
                "metadata",
                f"Metadata too large. Max {METADATA_MAX_SIZE} bytes, got {size}"
            )
    except (TypeError, ValueError) as e:
        raise ValidationError("metadata", f"Metadata must be JSON serializable: {e}")

    # 键名检查
    for key in metadata.keys():
        if not isinstance(key, str):
            raise ValidationError("metadata", "Metadata keys must be strings")
        if len(key) > 64:
            raise ValidationError("metadata", f"Metadata key too long: {key[:20]}...")
        if not re.match(r"^[a-zA-Z0-9_-]+$", key):
            raise ValidationError("metadata", f"Invalid metadata key: {key}")

    # 值类型检查
    for key, value in metadata.items():
        if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
            raise ValidationError(
                "metadata",
                f"Invalid metadata value type for key '{key}': {type(value).__name__}"
            )

    return metadata


def validate_capabilities(capabilities: list[str]) -> list[str]:
    """
    Validate capabilities list.

    Args:
        capabilities: List of capability strings

    Returns:
        Validated capabilities

    Raises:
        ValidationError: If format is invalid
    """
    if not isinstance(capabilities, list):
        raise ValidationError("capabilities", "Capabilities must be a list")

    if len(capabilities) > MAX_CAPABILITIES:
        raise ValidationError(
            "capabilities",
            f"Too many capabilities. Max {MAX_CAPABILITIES}, got {len(capabilities)}"
        )

    validated = []
    for cap in capabilities:
        if not isinstance(cap, str):
            raise ValidationError("capabilities", "Each capability must be a string")

        cap_lower = cap.lower()
        if cap_lower not in VALID_CAPABILITIES:
            raise ValidationError(
                "capabilities",
                f"Invalid capability: {cap}. Valid: {VALID_CAPABILITIES}"
            )

        if cap_lower not in validated:  # 去重
            validated.append(cap_lower)

    return validated


def sanitize_string(value: str, max_length: int = 1024) -> str:
    """
    Sanitize a string value.

    Args:
        value: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        raise ValidationError("value", "Value must be a string")

    # 截断
    if len(value) > max_length:
        value = value[:max_length]

    # HTML转义
    value = html.escape(value)

    # 移除控制字符
    value = "".join(c for c in value if ord(c) >= 32 or c in "\n\r\t")

    return value.strip()


# 装饰器: 自动验证函数参数
def validate_params(**validators):
    """
    Decorator to validate function parameters.

    Usage:
        @validate_params(device_id=validate_did, signature=validate_signature)
        def my_function(device_id: str, signature: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 验证kwargs中的参数
            for param_name, validator in validators.items():
                if param_name in kwargs:
                    try:
                        kwargs[param_name] = validator(kwargs[param_name])
                    except ValidationError as e:
                        raise ValueError(f"Parameter validation failed: {e}")
            return func(*args, **kwargs)
        return wrapper
    return decorator
