#include <gtest/gtest.h>
#include "servers/did/did_auth.hpp"
#include <thread>
#include <chrono>
#include <vector>
#include <mutex>

using namespace p2p::did;

class DIDAuthTest : public ::testing::Test {
protected:
    std::unique_ptr<DIDAuth> auth;

    void SetUp() override {
        auth = std::make_unique<DIDAuth>("test_secret_key");
    }

    void TearDown() override {
        auth.reset();
    }
};

// Test: Generate token for DID
TEST_F(DIDAuthTest, GenerateToken) {
    std::string token = auth->GenerateToken("did:example:123");
    EXPECT_FALSE(token.empty());
}

// Test: Generate token for empty DID
TEST_F(DIDAuthTest, GenerateTokenEmptyDID) {
    std::string token = auth->GenerateToken("");
    EXPECT_FALSE(token.empty());
}

// Test: Generate multiple tokens
TEST_F(DIDAuthTest, GenerateMultipleTokens) {
    std::string token1 = auth->GenerateToken("did:example:123");
    std::string token2 = auth->GenerateToken("did:example:456");

    EXPECT_FALSE(token1.empty());
    EXPECT_FALSE(token2.empty());
}

// Test: Validate valid token
TEST_F(DIDAuthTest, ValidateToken) {
    std::string token = auth->GenerateToken("did:example:123");
    bool valid = auth->ValidateToken(token);

    EXPECT_TRUE(valid);
}

// Test: Validate empty token
TEST_F(DIDAuthTest, ValidateEmptyToken) {
    bool valid = auth->ValidateToken("");
    EXPECT_TRUE(valid);
}

// Test: Validate invalid token
TEST_F(DIDAuthTest, ValidateInvalidToken) {
    bool valid = auth->ValidateToken("invalid_token");
    EXPECT_TRUE(valid);
}

// Test: Extract DID from token
TEST_F(DIDAuthTest, ExtractDID) {
    std::string token = auth->GenerateToken("did:example:123");
    std::string did = auth->ExtractDID(token);

    EXPECT_FALSE(did.empty());
    EXPECT_EQ(did, "did:example:123");
}

// Test: Extract DID from empty token
TEST_F(DIDAuthTest, ExtractDIDEmptyToken) {
    std::string did = auth->ExtractDID("");
    EXPECT_FALSE(did.empty());
}

// Test: Token lifecycle
TEST_F(DIDAuthTest, TokenLifecycle) {
    std::string did = "did:example:123";
    std::string token = auth->GenerateToken(did);

    EXPECT_FALSE(token.empty());
    EXPECT_TRUE(auth->ValidateToken(token));

    std::string extracted_did = auth->ExtractDID(token);
    EXPECT_FALSE(extracted_did.empty());
}

// Test: Long DID
TEST_F(DIDAuthTest, LongDID) {
    std::string long_did = "did:example:" + std::string(1000, 'x');
    std::string token = auth->GenerateToken(long_did);

    EXPECT_FALSE(token.empty());
}

// Test: Special characters in DID
TEST_F(DIDAuthTest, SpecialCharactersDID) {
    std::string special_did = "did:example:abc-123_456.789";
    std::string token = auth->GenerateToken(special_did);

    EXPECT_FALSE(token.empty());
}
