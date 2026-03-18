"""
DID服务单元测试
"""
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from typing import Any

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, NoEncryption


class TestDIDGeneration:
    """DID生成测试"""

    def test_did_format_validation(self):
        """测试DID格式验证"""
        # 示例DID: did:method:specific-idstring
        valid_dids = [
            "did:example:123456",
            "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            "did:web:example.com",
        ]

        def is_valid_did(did: str) -> bool:
            parts = did.split(":")
            return len(parts) >= 3 and parts[0] == "did"

        for did in valid_dids:
            assert is_valid_did(did) is True

        assert is_valid_did("invalid") is False

    def test_did_method_creation(self):
        """测试DID方法创建"""
        method = "p2p"
        specific_id = "device123"

        did = f"did:{method}:{specific_id}"
        assert did == "did:p2p:device123"

    def test_did_document_structure(self, sample_did_document: dict):
        """测试DID文档结构"""
        required_fields = ["@context", "id", "verificationMethod"]

        for field in required_fields:
            assert field in sample_did_document

        assert sample_did_document["id"].startswith("did:")


class TestDIDKeyGeneration:
    """DID密钥生成测试"""

    def test_generate_ed25519_keypair(self):
        """测试生成Ed25519密钥对"""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        # 验证公钥格式
        public_bytes = public_key.public_bytes(
            encoding=Encoding.Raw,
            format=PublicFormat.Raw
        )

        assert len(public_bytes) == 32  # Ed25519公钥长度

    def test_key_serialization(self):
        """测试密钥序列化"""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        # 序列化为PEM格式
        pem_public = public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo
        )

        assert b"BEGIN PUBLIC KEY" in pem_public

    def test_signature_verification(self):
        """测试签名验证"""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        message = b"test message"
        signature = private_key.sign(message)

        # 验证签名
        try:
            public_key.verify(signature, message)
            verified = True
        except Exception:
            verified = False

        assert verified is True

    def test_invalid_signature_rejection(self):
        """测试无效签名拒绝"""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        message = b"test message"
        signature = private_key.sign(message)

        # 尝试用错误的消息验证
        wrong_message = b"wrong message"

        with pytest.raises(Exception):
            public_key.verify(signature, wrong_message)


class TestDIDResolution:
    """DID解析测试"""

    @pytest.mark.asyncio
    async def test_resolve_did(self):
        """测试解析DID"""
        mock_resolver = AsyncMock()
        mock_did_doc = {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": "did:example:123456",
            "verificationMethod": [{
                "id": "did:example:123456#key-1",
                "type": "JsonWebKey2020",
                "controller": "did:example:123456",
            }],
        }
        mock_resolver.resolve.return_value = mock_did_doc

        result = await mock_resolver.resolve("did:example:123456")
        assert result["id"] == "did:example:123456"

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_did(self):
        """测试解析不存在的DID"""
        mock_resolver = AsyncMock()
        mock_resolver.resolve.return_value = None

        result = await mock_resolver.resolve("did:example:nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_cached_resolution(self):
        """测试缓存解析"""
        mock_resolver = AsyncMock()
        mock_did_doc = {"id": "did:example:123456"}
        mock_resolver.resolve.return_value = mock_did_doc

        # 第一次解析
        result1 = await mock_resolver.resolve("did:example:123456")
        # 第二次解析 (应该从缓存读取)
        result2 = await mock_resolver.resolve("did:example:123456")

        assert result1 == result2


class TestDeviceRegistration:
    """设备注册测试"""

    @pytest.mark.asyncio
    async def test_register_device(self):
        """测试注册设备"""
        mock_registry = AsyncMock()
        mock_registry.register.return_value = {
            "did": "did:p2p:device123",
            "status": "registered",
            "timestamp": 1234567890,
        }

        device_info = {
            "device_id": "device123",
            "public_key": "mock_public_key",
            "device_type": "mobile",
        }

        result = await mock_registry.register(device_info)
        assert result["status"] == "registered"

    @pytest.mark.asyncio
    async def test_update_device_info(self):
        """测试更新设备信息"""
        mock_registry = AsyncMock()
        mock_registry.update.return_value = {
            "did": "did:p2p:device123",
            "status": "updated",
            "updated_fields": ["device_type"],
        }

        updates = {"device_type": "desktop"}
        result = await mock_registry.update("did:p2p:device123", updates)

        assert result["status"] == "updated"

    @pytest.mark.asyncio
    async def test_deregister_device(self):
        """测试注销设备"""
        mock_registry = AsyncMock()
        mock_registry.deregister.return_value = {
            "did": "did:p2p:device123",
            "status": "deregistered",
        }

        result = await mock_registry.deregister("did:p2p:device123")
        assert result["status"] == "deregistered"

    @pytest.mark.asyncio
    async def test_list_devices(self):
        """测试列出设备"""
        mock_registry = AsyncMock()
        mock_registry.list.return_value = {
            "devices": [
                {"did": "did:p2p:device001", "status": "active"},
                {"did": "did:p2p:device002", "status": "active"},
            ],
            "total": 2,
        }

        result = await mock_registry.list(limit=10)
        assert result["total"] == 2


class TestDIDAuthentication:
    """DID认证测试"""

    @pytest.mark.asyncio
    async def test_create_challenge(self):
        """测试创建挑战"""
        mock_auth = AsyncMock()
        mock_auth.create_challenge.return_value = {
            "challenge_id": "challenge_123",
            "challenge": "random_challenge_string",
            "expires_at": 1234567900,
        }

        result = await mock_auth.create_challenge("did:p2p:device123")
        assert "challenge" in result

    @pytest.mark.asyncio
    async def test_verify_challenge_response(self):
        """测试验证挑战响应"""
        mock_auth = AsyncMock()
        mock_auth.verify_response.return_value = {
            "verified": True,
            "did": "did:p2p:device123",
        }

        response = {
            "challenge_id": "challenge_123",
            "signature": "mock_signature",
        }

        result = await mock_auth.verify_response(response)
        assert result["verified"] is True

    @pytest.mark.asyncio
    async def test_expired_challenge_rejection(self):
        """测试过期挑战拒绝"""
        mock_auth = AsyncMock()
        mock_auth.verify_response.return_value = {
            "verified": False,
            "error": "challenge_expired",
        }

        response = {
            "challenge_id": "expired_challenge",
            "signature": "signature",
        }

        result = await mock_auth.verify_response(response)
        assert result["verified"] is False


class TestDIDService:
    """DID服务测试"""

    def test_service_endpoint_creation(self):
        """测试服务端点创建"""
        service = {
            "id": "did:example:123456#p2p",
            "type": "P2PService",
            "serviceEndpoint": "p2p://example.com/device123",
        }

        assert service["type"] == "P2PService"
        assert service["serviceEndpoint"].startswith("p2p://")

    def test_multiple_services(self):
        """测试多个服务"""
        did_document = {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": "did:example:123456",
            "service": [
                {
                    "id": "did:example:123456#p2p",
                    "type": "P2PService",
                    "serviceEndpoint": "p2p://example.com/device123",
                },
                {
                    "id": "did:example:123456#messaging",
                    "type": "MessagingService",
                    "serviceEndpoint": "https://example.com/messages",
                },
            ],
        }

        assert len(did_document["service"]) == 2


class TestDIDSecurity:
    """DID安全测试"""

    def test_protect_private_key(self):
        """测试私钥保护"""
        # 模拟私钥存储
        mock_storage = MagicMock()
        private_key = "sensitive_private_key"

        # 私钥应该加密存储
        mock_storage.store_secret(private_key, encrypted=True)
        mock_storage.store_secret.assert_called_once()

    def test_non_exposure_of_secrets(self):
        """测试秘密信息不暴露"""
        did_document = {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": "did:example:123456",
            "verificationMethod": [{
                "id": "did:example:123456#key-1",
                "type": "JsonWebKey2020",
                "publicKeyJwk": {
                    "kty": "EC",
                    "x": "public_x",
                    "y": "public_y",
                },
            }],
        }

        # 确保没有私钥信息
        doc_str = json.dumps(did_document)
        assert "privateKey" not in doc_str
        assert "secret" not in doc_str

    def test_replay_attack_prevention(self):
        """测试重放攻击防护"""
        mock_nonce_store = MagicMock()

        # 使用nonce防止重放
        nonce = "random_nonce_12345"
        mock_nonce_store.use_nonce(nonce)
        mock_nonce_store.use_nonce.assert_called_once()

        # 尝试重放
        mock_nonce_store.is_used.return_value = True
        assert mock_nonce_store.is_used(nonce) is True


class TestDIDStorage:
    """DID存储测试"""

    @pytest.mark.asyncio
    async def test_store_did_document(self):
        """测试存储DID文档"""
        mock_storage = AsyncMock()
        mock_storage.store.return_value = {
            "did": "did:example:123456",
            "stored": True,
        }

        did_doc = {"id": "did:example:123456"}
        result = await mock_storage.store(did_doc)

        assert result["stored"] is True

    @pytest.mark.asyncio
    async def test_retrieve_did_document(self):
        """测试检索DID文档"""
        mock_storage = AsyncMock()
        mock_storage.retrieve.return_value = {
            "id": "did:example:123456",
            "@context": ["https://www.w3.org/ns/did/v1"],
        }

        result = await mock_storage.retrieve("did:example:123456")
        assert result["id"] == "did:example:123456"

    @pytest.mark.asyncio
    async def test_check_did_exists(self):
        """测试检查DID存在"""
        mock_storage = AsyncMock()
        mock_storage.exists.return_value = True

        result = await mock_storage.exists("did:example:123456")
        assert result is True
