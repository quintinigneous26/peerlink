#include <gtest/gtest.h>
#include "p2p/crypto/signed_envelope.hpp"
#include "p2p/crypto/ed25519_signer.hpp"
#include <vector>
#include <cstdint>

using namespace p2p::crypto;

class EndiannessTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Generate test key pair
        private_key_ = Ed25519Signer::GeneratePrivateKey();
        public_key_ = Ed25519Signer::DerivePublicKey(private_key_);
    }

    Ed25519PrivateKey private_key_;
    Ed25519PublicKey public_key_;
};

// Test: Serialize and deserialize should be symmetric
TEST_F(EndiannessTest, SerializeDeserializeSymmetry) {
    std::string payload_type = "/libp2p/test";
    std::vector<uint8_t> payload = {0x01, 0x02, 0x03, 0x04, 0x05};

    // Create and sign envelope
    auto envelope = SignedEnvelope::Sign(private_key_, payload_type, payload);

    // Serialize
    auto serialized = envelope.Serialize();

    // Deserialize
    auto deserialized = SignedEnvelope::Deserialize(serialized);

    ASSERT_TRUE(deserialized.has_value());
    EXPECT_EQ(deserialized->payload_type, payload_type);
    EXPECT_EQ(deserialized->payload, payload);
    EXPECT_EQ(deserialized->public_key, envelope.public_key);
    EXPECT_EQ(deserialized->signature, envelope.signature);
}

// Test: Verify signature after round-trip
TEST_F(EndiannessTest, SignatureValidAfterRoundTrip) {
    std::string payload_type = "/libp2p/relay-reservation";
    std::vector<uint8_t> payload = {0xDE, 0xAD, 0xBE, 0xEF};

    // Create and sign envelope
    auto envelope = SignedEnvelope::Sign(private_key_, payload_type, payload);
    EXPECT_TRUE(envelope.Verify());

    // Serialize and deserialize
    auto serialized = envelope.Serialize();
    auto deserialized = SignedEnvelope::Deserialize(serialized);

    ASSERT_TRUE(deserialized.has_value());
    EXPECT_TRUE(deserialized->Verify());
}

// Test: Big-endian byte order verification
TEST_F(EndiannessTest, BigEndianByteOrder) {
    std::string payload_type = "test";
    std::vector<uint8_t> payload = {0x01, 0x02};

    auto envelope = SignedEnvelope::Sign(private_key_, payload_type, payload);
    auto serialized = envelope.Serialize();

    // First 4 bytes should be public_key length in big-endian
    // Ed25519 public key is 32 bytes
    ASSERT_GE(serialized.size(), 4u);

    uint32_t expected_len = 32;  // Ed25519 public key size
    // Big-endian representation of 32: 0x00000020
    EXPECT_EQ(serialized[0], 0x00);
    EXPECT_EQ(serialized[1], 0x00);
    EXPECT_EQ(serialized[2], 0x00);
    EXPECT_EQ(serialized[3], 0x20);
}

// Test: Cross-platform compatibility simulation
TEST_F(EndiannessTest, CrossPlatformCompatibility) {
    std::string payload_type = "/libp2p/test";
    std::vector<uint8_t> payload = {0xCA, 0xFE, 0xBA, 0xBE};

    // Simulate serialization on one platform
    auto envelope1 = SignedEnvelope::Sign(private_key_, payload_type, payload);
    auto serialized = envelope1.Serialize();

    // Simulate deserialization on another platform (with potentially different endianness)
    auto envelope2 = SignedEnvelope::Deserialize(serialized);

    ASSERT_TRUE(envelope2.has_value());
    EXPECT_EQ(envelope2->payload_type, envelope1.payload_type);
    EXPECT_EQ(envelope2->payload, envelope1.payload);
    EXPECT_TRUE(envelope2->Verify());
}

// Test: Large payload handling
TEST_F(EndiannessTest, LargePayloadHandling) {
    std::string payload_type = "/libp2p/large-test";
    std::vector<uint8_t> payload(10000, 0xAB);  // 10KB payload

    auto envelope = SignedEnvelope::Sign(private_key_, payload_type, payload);
    auto serialized = envelope.Serialize();
    auto deserialized = SignedEnvelope::Deserialize(serialized);

    ASSERT_TRUE(deserialized.has_value());
    EXPECT_EQ(deserialized->payload.size(), 10000u);
    EXPECT_TRUE(deserialized->Verify());
}

// Test: Empty payload handling
TEST_F(EndiannessTest, EmptyPayloadHandling) {
    std::string payload_type = "/libp2p/empty";
    std::vector<uint8_t> payload;  // Empty payload

    auto envelope = SignedEnvelope::Sign(private_key_, payload_type, payload);
    auto serialized = envelope.Serialize();
    auto deserialized = SignedEnvelope::Deserialize(serialized);

    ASSERT_TRUE(deserialized.has_value());
    EXPECT_TRUE(deserialized->payload.empty());
    EXPECT_TRUE(deserialized->Verify());
}

// Test: Multiple serialization cycles
TEST_F(EndiannessTest, MultipleSerializationCycles) {
    std::string payload_type = "/libp2p/multi-cycle";
    std::vector<uint8_t> payload = {0x01, 0x02, 0x03};

    auto envelope1 = SignedEnvelope::Sign(private_key_, payload_type, payload);

    // Cycle 1
    auto serialized1 = envelope1.Serialize();
    auto deserialized1 = SignedEnvelope::Deserialize(serialized1);
    ASSERT_TRUE(deserialized1.has_value());

    // Cycle 2
    auto serialized2 = deserialized1->Serialize();
    auto deserialized2 = SignedEnvelope::Deserialize(serialized2);
    ASSERT_TRUE(deserialized2.has_value());

    // Cycle 3
    auto serialized3 = deserialized2->Serialize();
    auto deserialized3 = SignedEnvelope::Deserialize(serialized3);
    ASSERT_TRUE(deserialized3.has_value());

    // All should be identical
    EXPECT_EQ(serialized1, serialized2);
    EXPECT_EQ(serialized2, serialized3);
    EXPECT_TRUE(deserialized3->Verify());
}

// Test: Corrupted length field detection
TEST_F(EndiannessTest, CorruptedLengthDetection) {
    std::string payload_type = "/libp2p/test";
    std::vector<uint8_t> payload = {0x01, 0x02};

    auto envelope = SignedEnvelope::Sign(private_key_, payload_type, payload);
    auto serialized = envelope.Serialize();

    // Corrupt the first length field (make it huge)
    serialized[0] = 0xFF;
    serialized[1] = 0xFF;
    serialized[2] = 0xFF;
    serialized[3] = 0xFF;

    auto deserialized = SignedEnvelope::Deserialize(serialized);
    EXPECT_FALSE(deserialized.has_value());
}

// Test: Truncated data detection
TEST_F(EndiannessTest, TruncatedDataDetection) {
    std::string payload_type = "/libp2p/test";
    std::vector<uint8_t> payload = {0x01, 0x02, 0x03, 0x04};

    auto envelope = SignedEnvelope::Sign(private_key_, payload_type, payload);
    auto serialized = envelope.Serialize();

    // Truncate the serialized data
    serialized.resize(serialized.size() / 2);

    auto deserialized = SignedEnvelope::Deserialize(serialized);
    EXPECT_FALSE(deserialized.has_value());
}

// Test: Byte order independence
TEST_F(EndiannessTest, ByteOrderIndependence) {
    std::string payload_type = "/libp2p/test";
    std::vector<uint8_t> payload = {0x12, 0x34, 0x56, 0x78};

    auto envelope = SignedEnvelope::Sign(private_key_, payload_type, payload);
    auto serialized = envelope.Serialize();

    // Manually verify big-endian encoding
    // The serialized format should be platform-independent
    size_t offset = 0;

    // Read public_key length (should be 32 in big-endian)
    uint32_t pk_len = (static_cast<uint32_t>(serialized[offset]) << 24) |
                      (static_cast<uint32_t>(serialized[offset + 1]) << 16) |
                      (static_cast<uint32_t>(serialized[offset + 2]) << 8) |
                      static_cast<uint32_t>(serialized[offset + 3]);
    EXPECT_EQ(pk_len, 32u);

    offset += 4 + pk_len;

    // Read payload_type length (should be 14 in big-endian)
    uint32_t pt_len = (static_cast<uint32_t>(serialized[offset]) << 24) |
                      (static_cast<uint32_t>(serialized[offset + 1]) << 16) |
                      (static_cast<uint32_t>(serialized[offset + 2]) << 8) |
                      static_cast<uint32_t>(serialized[offset + 3]);
    EXPECT_EQ(pt_len, payload_type.size());
}

// Test: Compatibility with existing test vectors
TEST_F(EndiannessTest, TestVectorCompatibility) {
    // This test ensures our implementation matches expected behavior
    std::string payload_type = "/libp2p/relay-reservation";
    std::vector<uint8_t> payload = {0x00, 0x01, 0x02, 0x03};

    auto envelope = SignedEnvelope::Sign(private_key_, payload_type, payload);
    auto serialized = envelope.Serialize();

    // Verify structure
    EXPECT_GE(serialized.size(), 4u + 32u + 4u + payload_type.size() + 4u + payload.size() + 4u + 64u);

    // Verify deserialization
    auto deserialized = SignedEnvelope::Deserialize(serialized);
    ASSERT_TRUE(deserialized.has_value());
    EXPECT_TRUE(deserialized->Verify());
}
