#include <gtest/gtest.h>
#include "p2p/crypto/ed25519_signer.hpp"
#include <vector>
#include <string>

using namespace p2p::crypto;

class Ed25519SignerTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Test data
        test_data_ = {0x01, 0x02, 0x03, 0x04, 0x05};
    }

    std::vector<uint8_t> test_data_;
};

TEST_F(Ed25519SignerTest, GenerateKeyPair) {
    // Generate a key pair
    Ed25519PrivateKey private_key = Ed25519Signer::GenerateKeyPair();

    // Check private key size
    EXPECT_EQ(private_key.GetKeyData().size(), Ed25519PrivateKey::KEY_SIZE);

    // Derive public key
    std::vector<uint8_t> public_key_data = private_key.GetPublicKey();
    EXPECT_EQ(public_key_data.size(), Ed25519PublicKey::KEY_SIZE);
}

TEST_F(Ed25519SignerTest, SignAndVerify) {
    // Generate key pair
    Ed25519PrivateKey private_key = Ed25519Signer::GenerateKeyPair();
    Ed25519PublicKey public_key = Ed25519Signer::DerivePublicKey(private_key);

    // Sign data
    Ed25519Signature signature = Ed25519Signer::Sign(private_key, test_data_);

    // Check signature size
    EXPECT_EQ(signature.data.size(), Ed25519Signature::SIGNATURE_SIZE);

    // Verify signature
    bool valid = Ed25519Signer::Verify(public_key, test_data_, signature);
    EXPECT_TRUE(valid);
}

TEST_F(Ed25519SignerTest, VerifyInvalidSignature) {
    // Generate key pair
    Ed25519PrivateKey private_key = Ed25519Signer::GenerateKeyPair();
    Ed25519PublicKey public_key = Ed25519Signer::DerivePublicKey(private_key);

    // Sign data
    Ed25519Signature signature = Ed25519Signer::Sign(private_key, test_data_);

    // Modify signature (make it invalid)
    signature.data[0] ^= 0xFF;

    // Verify should fail
    bool valid = Ed25519Signer::Verify(public_key, test_data_, signature);
    EXPECT_FALSE(valid);
}

TEST_F(Ed25519SignerTest, VerifyWithWrongPublicKey) {
    // Generate two key pairs
    Ed25519PrivateKey private_key1 = Ed25519Signer::GenerateKeyPair();
    Ed25519PrivateKey private_key2 = Ed25519Signer::GenerateKeyPair();
    Ed25519PublicKey public_key2 = Ed25519Signer::DerivePublicKey(private_key2);

    // Sign with key1
    Ed25519Signature signature = Ed25519Signer::Sign(private_key1, test_data_);

    // Verify with key2 (should fail)
    bool valid = Ed25519Signer::Verify(public_key2, test_data_, signature);
    EXPECT_FALSE(valid);
}

TEST_F(Ed25519SignerTest, VerifyWithModifiedData) {
    // Generate key pair
    Ed25519PrivateKey private_key = Ed25519Signer::GenerateKeyPair();
    Ed25519PublicKey public_key = Ed25519Signer::DerivePublicKey(private_key);

    // Sign data
    Ed25519Signature signature = Ed25519Signer::Sign(private_key, test_data_);

    // Modify data
    std::vector<uint8_t> modified_data = test_data_;
    modified_data[0] ^= 0xFF;

    // Verify should fail
    bool valid = Ed25519Signer::Verify(public_key, modified_data, signature);
    EXPECT_FALSE(valid);
}

TEST_F(Ed25519SignerTest, DerivePublicKey) {
    // Generate private key
    Ed25519PrivateKey private_key = Ed25519Signer::GenerateKeyPair();

    // Derive public key twice
    Ed25519PublicKey public_key1 = Ed25519Signer::DerivePublicKey(private_key);
    Ed25519PublicKey public_key2 = Ed25519Signer::DerivePublicKey(private_key);

    // Should be identical
    EXPECT_EQ(public_key1.GetKeyData(), public_key2.GetKeyData());
}

TEST_F(Ed25519SignerTest, InvalidPrivateKeySize) {
    // Try to create private key with wrong size
    std::vector<uint8_t> invalid_key(16);  // Should be 32 bytes

    EXPECT_THROW({
        Ed25519PrivateKey key(invalid_key);
    }, std::invalid_argument);
}

TEST_F(Ed25519SignerTest, InvalidPublicKeySize) {
    // Try to create public key with wrong size
    std::vector<uint8_t> invalid_key(16);  // Should be 32 bytes

    EXPECT_THROW({
        Ed25519PublicKey key(invalid_key);
    }, std::invalid_argument);
}

TEST_F(Ed25519SignerTest, SignEmptyData) {
    // Generate key pair
    Ed25519PrivateKey private_key = Ed25519Signer::GenerateKeyPair();
    Ed25519PublicKey public_key = Ed25519Signer::DerivePublicKey(private_key);

    // Sign empty data
    std::vector<uint8_t> empty_data;
    Ed25519Signature signature = Ed25519Signer::Sign(private_key, empty_data);

    // Verify
    bool valid = Ed25519Signer::Verify(public_key, empty_data, signature);
    EXPECT_TRUE(valid);
}

TEST_F(Ed25519SignerTest, SignLargeData) {
    // Generate key pair
    Ed25519PrivateKey private_key = Ed25519Signer::GenerateKeyPair();
    Ed25519PublicKey public_key = Ed25519Signer::DerivePublicKey(private_key);

    // Create large data (1 MB)
    std::vector<uint8_t> large_data(1024 * 1024, 0xAB);

    // Sign
    Ed25519Signature signature = Ed25519Signer::Sign(private_key, large_data);

    // Verify
    bool valid = Ed25519Signer::Verify(public_key, large_data, signature);
    EXPECT_TRUE(valid);
}
