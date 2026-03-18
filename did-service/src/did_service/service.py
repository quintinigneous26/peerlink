"""
DID Service - Main application

Security Enhanced Version:
- Input validation for all endpoints
- Sanitization of user inputs
- Protection against injection attacks
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

from .config import config
from .models import APIResponse, DeviceRegistration, TokenResponse
from .crypto import DIDGenerator, KeyGenerator
from .storage import get_storage, DeviceStatus
from .auth import get_token_manager
from .validators import (
    ValidationError,
    validate_did,
    validate_signature,
    validate_challenge,
    validate_metadata,
    validate_capabilities,
    sanitize_string,
)
from .rate_limiter import RateLimiter, RateLimitConfig

logger = logging.getLogger(__name__)


# ===== Custom Exception Handler =====


class InputValidationException(Exception):
    """Input validation exception."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


# ===== Request/Response Models =====


class GenerateDIDRequest(BaseModel):
    """Request to generate a new device identity."""

    device_type: str = Field(..., description="Device type: ios, android, web, desktop")
    capabilities: list[str] = Field(default_factory=lambda: ["p2p", "relay"])
    metadata: dict = Field(default_factory=dict)

    @validator("device_type")
    def validate_device_type(cls, v):
        if not v:
            raise ValueError("device_type is required")
        v = v.lower().strip()
        if v not in config.valid_device_types:
            raise ValueError(
                f"Invalid device_type. Must be one of: {config.valid_device_types}"
            )
        return v

    @validator("capabilities")
    def validate_caps(cls, v):
        return validate_capabilities(v)

    @validator("metadata")
    def validate_meta(cls, v):
        return validate_metadata(v)


class VerifyDIDRequest(BaseModel):
    """Request to verify a device identity."""

    device_id: str = Field(..., description="Device ID to verify")
    challenge: str = Field(..., description="Random challenge string")
    signature: str = Field(..., description="Signature of the challenge")

    @validator("device_id")
    def validate_did_field(cls, v):
        return validate_did(v)

    @validator("challenge")
    def validate_challenge_field(cls, v):
        return validate_challenge(v)

    @validator("signature")
    def validate_sig_field(cls, v):
        return validate_signature(v)


class TokenRequest(BaseModel):
    """Request to get an access token."""

    device_id: str = Field(..., description="Device ID")
    signature: str = Field(..., description="Signature of device_id")

    @validator("device_id")
    def validate_did_field(cls, v):
        return validate_did(v)

    @validator("signature")
    def validate_sig_field(cls, v):
        return validate_signature(v)


class HeartbeatRequest(BaseModel):
    """Heartbeat request."""

    device_id: str = Field(..., description="Device ID")

    @validator("device_id")
    def validate_did_field(cls, v):
        return validate_did(v)


class DeviceStatusResponse(BaseModel):
    """Response with device status."""

    device_id: str
    status: str
    last_seen: int
    is_online: bool


# ===== Lifespan Management =====


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    logger.info("Starting DID Service...")
    storage = get_storage()
    # Verify Redis connection
    await storage._get_pool()
    logger.info("DID Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down DID Service...")
    await storage.close()
    logger.info("DID Service shut down")


# ===== Application =====


app = FastAPI(
    title="DID Service",
    description="Device Identity and Authentication Service (Security Enhanced)",
    version="0.2.0",
    lifespan=lifespan,
)

# Initialize rate limiter
_rate_limiter = RateLimiter(RateLimitConfig(
    requests_per_minute=60,
    requests_per_hour=1000,
    burst_size=10,
))


# ===== Exception Handlers =====


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle validation errors."""
    logger.warning(f"Validation error: {exc.field} - {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "field": exc.field,
                "message": exc.message,
            },
        },
    )


@app.exception_handler(InputValidationException)
async def input_validation_error_handler(request: Request, exc: InputValidationException):
    """Handle input validation exceptions."""
    logger.warning(f"Input validation error: {exc.field} - {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": {
                "code": "INVALID_INPUT",
                "field": exc.field,
                "message": exc.message,
            },
        },
    )


# ===== Rate Limiting Middleware =====


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all HTTP requests."""
    limiter = get_rate_limiter()
    allowed, info = limiter.check_rate_limit(request)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "success": False,
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded. Retry after {info.get('retry_after', 60)} seconds",
                    "retry_after": info.get("retry_after", 60),
                },
            },
            headers={"Retry-After": str(info.get("retry_after", 60))},
        )

    # Add rate limit headers to response
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(limiter.config.requests_per_minute)
    response.headers["X-RateLimit-Remaining"] = str(info.get("minute_remaining", limiter.config.requests_per_minute))
    return response


# ===== Health Check =====


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "did-service", "version": "0.2.0"}


# ===== API Routes =====


@app.post("/api/v1/did/generate", response_model=dict)
async def generate_did(request: GenerateDIDRequest) -> dict:
    """
    Generate a new device identity.

    Creates a new DID, generates a keypair, and registers the device.
    The private key is only returned once.
    """
    # Generate DID
    device_id = DIDGenerator.generate(request.device_type)

    # Generate keypair
    private_key, public_key = KeyGenerator.generate_keypair()
    public_key_hex = KeyGenerator.serialize_public_key(public_key)
    private_key_hex = KeyGenerator.serialize_private_key(private_key)

    # Store device
    storage = get_storage()
    device_info = await storage.register_device(
        device_id=device_id,
        device_type=request.device_type,
        public_key=public_key_hex,
        capabilities=request.capabilities,
        metadata=request.metadata,
    )

    response = APIResponse(
        success=True,
        data={
            "device_id": device_info.device_id,
            "device_type": device_info.device_type,
            "public_key": public_key_hex,
            "private_key": private_key_hex,
            "capabilities": device_info.capabilities,
            "created_at": device_info.created_at,
        },
    )

    logger.info(f"Generated DID: {device_id}")
    return response.to_dict()


@app.post("/api/v1/did/verify", response_model=dict)
async def verify_did(request: VerifyDIDRequest) -> dict:
    """
    Verify a device identity using signature challenge.

    The device should sign the challenge with its private key.
    """
    storage = get_storage()
    device = await storage.get_device(request.device_id)

    if not device:
        response = APIResponse(
            success=False,
            error={"code": "DEVICE_NOT_FOUND", "message": "Device not registered"},
        )
        return response.to_dict()

    # Verify signature
    try:
        public_key = KeyGenerator.deserialize_public_key(device.public_key)
        challenge_bytes = request.challenge.encode()
        signature_bytes = bytes.fromhex(request.signature)

        is_valid = KeyGenerator.verify(public_key, challenge_bytes, signature_bytes)
    except Exception as e:
        logger.warning(f"Signature verification error: {e}")
        is_valid = False

    response = APIResponse(
        success=is_valid,
        data={
            "device_id": device.device_id,
            "valid": is_valid,
            "device_type": device.device_type,
        },
        error=None if is_valid else {"code": "INVALID_SIGNATURE", "message": "Signature verification failed"},
    )

    return response.to_dict()


@app.post("/api/v1/did/token", response_model=dict)
async def get_token(request: TokenRequest) -> dict:
    """
    Get an access token for a device.

    The device should sign its device_id with its private key.
    """
    storage = get_storage()
    device = await storage.get_device(request.device_id)

    if not device:
        response = APIResponse(
            success=False,
            error={"code": "DEVICE_NOT_FOUND", "message": "Device not registered"},
        )
        return response.to_dict()

    # Verify signature
    try:
        public_key = KeyGenerator.deserialize_public_key(device.public_key)
        message_bytes = request.device_id.encode()
        signature_bytes = bytes.fromhex(request.signature)

        is_valid = KeyGenerator.verify(public_key, message_bytes, signature_bytes)
    except Exception as e:
        logger.warning(f"Signature verification error: {e}")
        is_valid = False

    if not is_valid:
        response = APIResponse(
            success=False,
            error={"code": "INVALID_SIGNATURE", "message": "Signature verification failed"},
        )
        return response.to_dict()

    # Generate token
    token_manager = get_token_manager()
    token = token_manager.generate_token(
        device_id=device.device_id,
        device_type=device.device_type,
    )

    response = APIResponse(
        success=True,
        data={
            "token": token,
            "expires_in": token_manager.get_expiration(),
            "device_id": device.device_id,
        },
    )

    return response.to_dict()


@app.post("/api/v1/devices/{device_id}/heartbeat", response_model=dict)
async def heartbeat(device_id: str, request: HeartbeatRequest | None = None) -> dict:
    """
    Update device heartbeat.

    Keeps the device marked as online.
    """
    # Validate device_id from path
    try:
        validated_device_id = validate_did(device_id)
    except ValidationError as e:
        return APIResponse(
            success=False,
            error={"code": "INVALID_DEVICE_ID", "message": e.message},
        ).to_dict()

    storage = get_storage()
    updated = await storage.update_heartbeat(validated_device_id)

    if not updated:
        response = APIResponse(
            success=False,
            error={"code": "DEVICE_NOT_FOUND", "message": "Device not registered"},
        )
        return response.to_dict()

    response = APIResponse(
        success=True,
        data={
            "device_id": validated_device_id,
            "status": "online",
        },
    )

    return response.to_dict()


@app.get("/api/v1/devices/{device_id}", response_model=dict)
async def get_device(device_id: str) -> dict:
    """
    Get device information.
    """
    # Validate device_id from path
    try:
        validated_device_id = validate_did(device_id)
    except ValidationError as e:
        return APIResponse(
            success=False,
            error={"code": "INVALID_DEVICE_ID", "message": e.message},
        ).to_dict()

    storage = get_storage()
    device = await storage.get_device(validated_device_id)

    if not device:
        response = APIResponse(
            success=False,
            error={"code": "DEVICE_NOT_FOUND", "message": "Device not registered"},
        )
        return response.to_dict()

    # Check online status
    is_online = await storage.is_online(validated_device_id)

    response = APIResponse(
        success=True,
        data={
            "device_id": device.device_id,
            "device_type": device.device_type,
            "public_key": device.public_key,
            "status": device.status.value,
            "is_online": is_online,
            "last_seen": device.last_seen,
            "created_at": device.created_at,
            "capabilities": device.capabilities,
        },
    )

    return response.to_dict()


@app.get("/api/v1/devices", response_model=dict)
async def list_devices(device_type: Optional[str] = None, online_only: bool = False) -> dict:
    """
    List devices.

    Query parameters:
    - device_type: Filter by device type
    - online_only: Only return online devices
    """
    # Validate device_type if provided
    if device_type:
        device_type = device_type.lower().strip()
        if device_type not in config.valid_device_types:
            return APIResponse(
                success=False,
                error={"code": "INVALID_DEVICE_TYPE", "message": f"Must be one of: {config.valid_device_types}"},
            ).to_dict()

    storage = get_storage()

    if device_type:
        device_ids = await storage.get_devices_by_type(device_type)
    elif online_only:
        device_ids = list(await storage.get_online_devices())
    else:
        # Return all devices of all types
        device_ids = []
        for dt in config.valid_device_types:
            device_ids.extend(await storage.get_devices_by_type(dt))

    devices = []
    for device_id in device_ids:
        device = await storage.get_device(device_id)
        if device:
            is_online = await storage.is_online(device_id)
            if not online_only or is_online:
                devices.append({
                    "device_id": device.device_id,
                    "device_type": device.device_type,
                    "status": device.status.value,
                    "is_online": is_online,
                    "last_seen": device.last_seen,
                })

    response = APIResponse(
        success=True,
        data={
            "devices": devices,
            "count": len(devices),
        },
    )

    return response.to_dict()


@app.delete("/api/v1/devices/{device_id}", response_model=dict)
async def delete_device(device_id: str) -> dict:
    """
    Delete a device.
    """
    # Validate device_id from path
    try:
        validated_device_id = validate_did(device_id)
    except ValidationError as e:
        return APIResponse(
            success=False,
            error={"code": "INVALID_DEVICE_ID", "message": e.message},
        ).to_dict()

    storage = get_storage()
    deleted = await storage.delete_device(validated_device_id)

    if not deleted:
        response = APIResponse(
            success=False,
            error={"code": "DEVICE_NOT_FOUND", "message": "Device not registered"},
        )
        return response.to_dict()

    response = APIResponse(
        success=True,
        data={"device_id": validated_device_id},
    )

    return response.to_dict()


# ===== Background Tasks =====


@app.post("/api/v1/admin/cleanup", response_model=dict)
async def cleanup_stale_devices():
    """
    Clean up stale devices (admin endpoint).

    Marks devices offline if they haven't sent heartbeat recently.
    """
    storage = get_storage()
    count = await storage.cleanup_stale_devices(config.heartbeat_timeout)

    response = APIResponse(
        success=True,
        data={
            "cleaned_count": count,
            "timeout": config.heartbeat_timeout,
        },
    )

    return response.to_dict()
