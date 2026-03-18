/**
 * @file test_rate_limiter.cpp
 * @brief Unit tests for rate limiter
 */

#include <gtest/gtest.h>
#include "p2p/servers/relay/rate_limiter.hpp"
#include <thread>
#include <vector>
#include <chrono>

using namespace p2p::relay;

class RateLimiterTest : public ::testing::Test {
protected:
    void SetUp() override {
        // 5 requests/sec, 10 burst, 3 violations = ban for 5 seconds
        RateLimitConfig config(5, 10, 3, 5);
        limiter_ = std::make_unique<RateLimiter>(config);
    }

    std::unique_ptr<RateLimiter> limiter_;
};

/**
 * Test: Allow requests within rate limit
 */
TEST_F(RateLimiterTest, AllowRequestsWithinLimit) {
    std::string client = "192.168.1.100:12345";

    // Should allow burst of 10 requests
    for (int i = 0; i < 10; ++i) {
        EXPECT_TRUE(limiter_->AllowRequest(client));
    }

    // 11th request should be blocked
    EXPECT_FALSE(limiter_->AllowRequest(client));
}

/**
 * Test: Token refill over time
 */
TEST_F(RateLimiterTest, TokenRefillOverTime) {
    std::string client = "192.168.1.100:12345";

    // Consume all tokens
    for (int i = 0; i < 10; ++i) {
        limiter_->AllowRequest(client);
    }

    // Should be blocked
    EXPECT_FALSE(limiter_->AllowRequest(client));

    // Wait for 1 second (5 tokens should refill)
    std::this_thread::sleep_for(std::chrono::seconds(1));

    // Should allow 5 more requests
    for (int i = 0; i < 5; ++i) {
        EXPECT_TRUE(limiter_->AllowRequest(client));
    }

    // 6th should be blocked
    EXPECT_FALSE(limiter_->AllowRequest(client));
}

/**
 * Test: Ban after threshold violations
 */
TEST_F(RateLimiterTest, BanAfterThresholdViolations) {
    std::string client = "192.168.1.100:12345";

    // Consume all tokens
    for (int i = 0; i < 10; ++i) {
        limiter_->AllowRequest(client);
    }

    // Trigger 3 violations (ban threshold)
    for (int i = 0; i < 3; ++i) {
        EXPECT_FALSE(limiter_->AllowRequest(client));
    }

    // Should be banned now
    EXPECT_TRUE(limiter_->IsBanned(client));

    // Wait for token refill
    std::this_thread::sleep_for(std::chrono::seconds(1));

    // Still banned (ban duration is 5 seconds)
    EXPECT_FALSE(limiter_->AllowRequest(client));
}

/**
 * Test: Ban expires after duration
 */
TEST_F(RateLimiterTest, BanExpiresAfterDuration) {
    std::string client = "192.168.1.100:12345";

    // Trigger ban
    for (int i = 0; i < 10; ++i) {
        limiter_->AllowRequest(client);
    }
    for (int i = 0; i < 3; ++i) {
        limiter_->AllowRequest(client);
    }

    EXPECT_TRUE(limiter_->IsBanned(client));

    // Wait for ban to expire (5 seconds)
    std::this_thread::sleep_for(std::chrono::seconds(6));

    // Should not be banned anymore
    EXPECT_FALSE(limiter_->IsBanned(client));

    // Should allow requests again
    EXPECT_TRUE(limiter_->AllowRequest(client));
}

/**
 * Test: Multiple clients independent
 */
TEST_F(RateLimiterTest, MultipleClientsIndependent) {
    std::string client1 = "192.168.1.100:12345";
    std::string client2 = "192.168.1.101:12346";

    // Client1 consumes all tokens
    for (int i = 0; i < 10; ++i) {
        EXPECT_TRUE(limiter_->AllowRequest(client1));
    }
    EXPECT_FALSE(limiter_->AllowRequest(client1));

    // Client2 should still have tokens
    for (int i = 0; i < 10; ++i) {
        EXPECT_TRUE(limiter_->AllowRequest(client2));
    }
}

/**
 * Test: Manual ban
 */
TEST_F(RateLimiterTest, ManualBan) {
    std::string client = "192.168.1.100:12345";

    // Manually ban client
    limiter_->BanClient(client);

    EXPECT_TRUE(limiter_->IsBanned(client));
    EXPECT_FALSE(limiter_->AllowRequest(client));
}

/**
 * Test: Manual unban
 */
TEST_F(RateLimiterTest, ManualUnban) {
    std::string client = "192.168.1.100:12345";

    // Ban and then unban
    limiter_->BanClient(client);
    EXPECT_TRUE(limiter_->IsBanned(client));

    limiter_->UnbanClient(client);
    EXPECT_FALSE(limiter_->IsBanned(client));

    // Should allow requests
    EXPECT_TRUE(limiter_->AllowRequest(client));
}

/**
 * Test: Cleanup expired clients
 */
TEST_F(RateLimiterTest, CleanupExpiredClients) {
    // Create multiple clients
    for (int i = 0; i < 10; ++i) {
        std::string client = "192.168.1." + std::to_string(i) + ":12345";
        limiter_->AllowRequest(client);
    }

    auto stats = limiter_->GetStats();
    EXPECT_EQ(stats.total_clients, 10);

    // Cleanup (should remove clients with no violations and not banned)
    size_t cleaned = limiter_->CleanupExpired();
    EXPECT_GT(cleaned, 0);

    stats = limiter_->GetStats();
    EXPECT_LT(stats.total_clients, 10);
}

/**
 * Test: Statistics tracking
 */
TEST_F(RateLimiterTest, StatisticsTracking) {
    std::string client = "192.168.1.100:12345";

    // Make some requests
    for (int i = 0; i < 15; ++i) {
        limiter_->AllowRequest(client);
    }

    auto stats = limiter_->GetStats();
    EXPECT_EQ(stats.total_requests, 15);
    EXPECT_EQ(stats.blocked_requests, 5);  // 10 allowed, 5 blocked
    EXPECT_GT(stats.block_rate, 0.0);
    EXPECT_LT(stats.block_rate, 1.0);
}

/**
 * Test: Concurrent requests from same client
 */
TEST_F(RateLimiterTest, ConcurrentRequestsSameClient) {
    std::string client = "192.168.1.100:12345";
    std::atomic<int> allowed{0};
    std::atomic<int> blocked{0};

    std::vector<std::thread> threads;
    for (int t = 0; t < 5; ++t) {
        threads.emplace_back([this, &client, &allowed, &blocked]() {
            for (int i = 0; i < 10; ++i) {
                if (limiter_->AllowRequest(client)) {
                    allowed++;
                } else {
                    blocked++;
                }
            }
        });
    }

    for (auto& t : threads) {
        t.join();
    }

    // Total 50 requests, should allow ~10 (burst size)
    EXPECT_LE(allowed, 15);  // Allow some tolerance
    EXPECT_GE(blocked, 35);
}

/**
 * Test: Concurrent requests from different clients
 */
TEST_F(RateLimiterTest, ConcurrentRequestsDifferentClients) {
    std::atomic<int> total_allowed{0};

    std::vector<std::thread> threads;
    for (int t = 0; t < 10; ++t) {
        threads.emplace_back([this, &total_allowed, t]() {
            std::string client = "192.168.1." + std::to_string(t) + ":12345";
            for (int i = 0; i < 10; ++i) {
                if (limiter_->AllowRequest(client)) {
                    total_allowed++;
                }
            }
        });
    }

    for (auto& t : threads) {
        t.join();
    }

    // Each client should get ~10 requests (burst size)
    EXPECT_GE(total_allowed, 90);  // Most should be allowed
}

/**
 * Test: Remove client
 */
TEST_F(RateLimiterTest, RemoveClient) {
    std::string client = "192.168.1.100:12345";

    limiter_->AllowRequest(client);

    auto stats = limiter_->GetStats();
    EXPECT_EQ(stats.total_clients, 1);

    limiter_->RemoveClient(client);

    stats = limiter_->GetStats();
    EXPECT_EQ(stats.total_clients, 0);
}

/**
 * Test: High load stress test
 */
TEST_F(RateLimiterTest, HighLoadStressTest) {
    std::atomic<int> total_requests{0};
    std::atomic<int> total_allowed{0};

    std::vector<std::thread> threads;
    for (int t = 0; t < 20; ++t) {
        threads.emplace_back([this, &total_requests, &total_allowed, t]() {
            std::string client = "192.168.1." + std::to_string(t % 5) + ":12345";
            for (int i = 0; i < 100; ++i) {
                total_requests++;
                if (limiter_->AllowRequest(client)) {
                    total_allowed++;
                }
            }
        });
    }

    for (auto& t : threads) {
        t.join();
    }

    EXPECT_EQ(total_requests, 2000);

    auto stats = limiter_->GetStats();
    EXPECT_EQ(stats.total_requests, 2000);
    EXPECT_GT(stats.blocked_requests, 0);
    EXPECT_LE(stats.total_clients, 5);
}
