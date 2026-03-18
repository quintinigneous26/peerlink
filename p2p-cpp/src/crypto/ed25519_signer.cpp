#include "p2p/crypto/ed25519_signer.hpp"
#include <openssl/evp.h>
#include <openssl/err.h>
#include <stdexcept>
#include <cstring>

namespace p2p {
namespace crypto {

// Ed25519PrivateKey implementation
Ed25519PrivateKey::Ed25519PrivateKey(const std::vector<uint8_t>& key_data)
    : key_data_(key_data) {
    if (key_data_.size() != KEY_SIZE) {
        throw std::invalid_argument("Ed25519 private key must be 32 bytes");
    }
}

Ed25519PrivateKey::Ed25519PrivateKey(const uint8_t* key_data, size_t size)
    : key_data_(key_data, key_data + size) {
    if (size != KEY_SIZE) {
        throw std::invalid_argument("Ed25519 private key must be 32 bytes");
    }
}

std::vector<uint8_t> Ed25519PrivateKey::GetPublicKey() const {
    return Ed25519Signer::DerivePublicKey(*this).GetKeyData();
}

// Ed25519PublicKey implementation
Ed25519PublicKey::Ed25519PublicKey(const std::vector<uint8_t>& key_data)
    : key_data_(key_data) {
    if (key_data_.size() != KEY_SIZE) {
        throw std::invalid_argument("Ed25519 public key must be 32 bytes");
    }
}

Ed25519PublicKey::Ed25519PublicKey(const uint8_t* key_data, size_t size)
    : key_data_(key_data, key_data + size) {
    if (size != KEY_SIZE) {
        throw std::invalid_argument("Ed25519 public key must be 32 bytes");
    }
}

// Ed25519Signer implementation
Ed25519PrivateKey Ed25519Signer::GenerateKeyPair() {
    EVP_PKEY* pkey = nullptr;
    EVP_PKEY_CTX* ctx = EVP_PKEY_CTX_new_id(EVP_PKEY_ED25519, nullptr);

    if (!ctx) {
        throw std::runtime_error("Failed to create EVP_PKEY_CTX");
    }

    if (EVP_PKEY_keygen_init(ctx) <= 0) {
        EVP_PKEY_CTX_free(ctx);
        throw std::runtime_error("Failed to initialize key generation");
    }

    if (EVP_PKEY_keygen(ctx, &pkey) <= 0) {
        EVP_PKEY_CTX_free(ctx);
        throw std::runtime_error("Failed to generate key pair");
    }

    EVP_PKEY_CTX_free(ctx);

    // Extract private key
    size_t key_len = Ed25519PrivateKey::KEY_SIZE;
    std::vector<uint8_t> private_key_data(key_len);

    if (EVP_PKEY_get_raw_private_key(pkey, private_key_data.data(), &key_len) <= 0) {
        EVP_PKEY_free(pkey);
        throw std::runtime_error("Failed to extract private key");
    }

    EVP_PKEY_free(pkey);
    return Ed25519PrivateKey(private_key_data);
}

Ed25519Signature Ed25519Signer::Sign(
    const Ed25519PrivateKey& private_key,
    const std::vector<uint8_t>& data
) {
    // Create EVP_PKEY from raw private key
    EVP_PKEY* pkey = EVP_PKEY_new_raw_private_key(
        EVP_PKEY_ED25519,
        nullptr,
        private_key.GetKeyData().data(),
        private_key.GetKeyData().size()
    );

    if (!pkey) {
        throw std::runtime_error("Failed to create EVP_PKEY from private key");
    }

    // Create signing context
    EVP_MD_CTX* md_ctx = EVP_MD_CTX_new();
    if (!md_ctx) {
        EVP_PKEY_free(pkey);
        throw std::runtime_error("Failed to create EVP_MD_CTX");
    }

    // Initialize signing
    if (EVP_DigestSignInit(md_ctx, nullptr, nullptr, nullptr, pkey) <= 0) {
        EVP_MD_CTX_free(md_ctx);
        EVP_PKEY_free(pkey);
        throw std::runtime_error("Failed to initialize signing");
    }

    // Sign the data
    size_t sig_len = Ed25519Signature::SIGNATURE_SIZE;
    std::vector<uint8_t> signature_data(sig_len);

    if (EVP_DigestSign(md_ctx, signature_data.data(), &sig_len, data.data(), data.size()) <= 0) {
        EVP_MD_CTX_free(md_ctx);
        EVP_PKEY_free(pkey);
        throw std::runtime_error("Failed to sign data");
    }

    EVP_MD_CTX_free(md_ctx);
    EVP_PKEY_free(pkey);

    return Ed25519Signature(signature_data);
}

bool Ed25519Signer::Verify(
    const Ed25519PublicKey& public_key,
    const std::vector<uint8_t>& data,
    const Ed25519Signature& signature
) {
    // Create EVP_PKEY from raw public key
    EVP_PKEY* pkey = EVP_PKEY_new_raw_public_key(
        EVP_PKEY_ED25519,
        nullptr,
        public_key.GetKeyData().data(),
        public_key.GetKeyData().size()
    );

    if (!pkey) {
        return false;
    }

    // Create verification context
    EVP_MD_CTX* md_ctx = EVP_MD_CTX_new();
    if (!md_ctx) {
        EVP_PKEY_free(pkey);
        return false;
    }

    // Initialize verification
    if (EVP_DigestVerifyInit(md_ctx, nullptr, nullptr, nullptr, pkey) <= 0) {
        EVP_MD_CTX_free(md_ctx);
        EVP_PKEY_free(pkey);
        return false;
    }

    // Verify the signature
    int result = EVP_DigestVerify(
        md_ctx,
        signature.data.data(),
        signature.data.size(),
        data.data(),
        data.size()
    );

    EVP_MD_CTX_free(md_ctx);
    EVP_PKEY_free(pkey);

    return result == 1;
}

Ed25519PublicKey Ed25519Signer::DerivePublicKey(const Ed25519PrivateKey& private_key) {
    // Create EVP_PKEY from raw private key
    EVP_PKEY* pkey = EVP_PKEY_new_raw_private_key(
        EVP_PKEY_ED25519,
        nullptr,
        private_key.GetKeyData().data(),
        private_key.GetKeyData().size()
    );

    if (!pkey) {
        throw std::runtime_error("Failed to create EVP_PKEY from private key");
    }

    // Extract public key
    size_t key_len = Ed25519PublicKey::KEY_SIZE;
    std::vector<uint8_t> public_key_data(key_len);

    if (EVP_PKEY_get_raw_public_key(pkey, public_key_data.data(), &key_len) <= 0) {
        EVP_PKEY_free(pkey);
        throw std::runtime_error("Failed to extract public key");
    }

    EVP_PKEY_free(pkey);
    return Ed25519PublicKey(public_key_data);
}

} // namespace crypto
} // namespace p2p
