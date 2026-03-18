#include <gtest/gtest.h>
#include "p2p/servers/relay/forwarder.hpp"
#include "p2p/servers/relay/stop_protocol.hpp"
#include <thread>
#include <chrono>

using namespace p2p::relay::v2;

class ForwarderTest : public ::testing::Test {
protected:
    void SetUp() override {}
    void TearDown() override {}
};

// TokenBucket Tests
TEST_F(ForwarderTest, TokenBucketCreation) {
    TokenBucket bucket(1000, 2000);  // 1000 tokens/sec, capacity 2000
    EXPECT_GT(bucket.GetTokens(), 0);
}

TEST_F(ForwarderTest, TokenBucketConsume) {
    TokenBucket bucket(1000, 2000);

    // Should be able to consume tokens
    EXPECT_TRUE(bucket.TryConsume(100));
    EXPECT_TRUE(bucket.TryConsume(100));
}

TEST_F(ForwarderTest, TokenBucketExhaust) {
    TokenBucket bucket(100, 100);  // Small capacity

    // Consume all tokens
    EXPECT_TRUE(bucket.TryConsume(100));

    // Should fail immediately
    EXPECT_FALSE(bucket.TryConsume(50));
}

TEST_F(ForwarderTest, TokenBucketRefill) {
    TokenBucket bucket(1000, 2000);

    // Consume tokens
    bucket.TryConsume(1000);

    // Wait for refill
    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    // Should have refilled some tokens
    EXPECT_TRUE(bucket.TryConsume(50));
}

TEST_F(ForwarderTest, TokenBucketSetRate) {
    TokenBucket bucket(1000, 2000);

    bucket.SetRate(2000);  // Double the rate

    // Should refill faster
    bucket.TryConsume(1000);
    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    EXPECT_TRUE(bucket.TryConsume(100));
}

// BandwidthLimiter Tests
TEST_F(ForwarderTest, BandwidthLimiterUnlimited) {
    BandwidthLimiter limiter(0);  // Unlimited

    EXPECT_TRUE(limiter.IsUnlimited());
    EXPECT_TRUE(limiter.CanSend(1000000));
}

TEST_F(ForwarderTest, BandwidthLimiterLimited) {
    BandwidthLimiter limiter(1000);  // 1000 bytes/sec

    EXPECT_FALSE(limiter.IsUnlimited());
    EXPECT_EQ(limiter.GetLimit(), 1000);
}

TEST_F(ForwarderTest, BandwidthLimiterCanSend) {
    BandwidthLimiter limiter(10000);  // 10KB/sec

    // Should be able to send initially
    EXPECT_TRUE(limiter.CanSend(1000));
}

TEST_F(ForwarderTest, BandwidthLimiterSetLimit) {
    BandwidthLimiter limiter(1000);

    limiter.SetLimit(2000);
    EXPECT_EQ(limiter.GetLimit(), 2000);

    limiter.SetLimit(0);  // Unlimited
    EXPECT_TRUE(limiter.IsUnlimited());
}

// RelayForwarder Tests
TEST_F(ForwarderTest, ForwarderCreation) {
    auto conn_a = std::make_shared<ActiveRelayConnection>("peer-a");
    auto conn_b = std::make_shared<ActiveRelayConnection>("peer-b");

    RelayForwarder forwarder(conn_a, conn_b);

    EXPECT_EQ(forwarder.GetStatus(), ForwardingStatus::IDLE);
}

TEST_F(ForwarderTest, ForwarderStart) {
    auto conn_a = std::make_shared<ActiveRelayConnection>("peer-a");
    auto conn_b = std::make_shared<ActiveRelayConnection>("peer-b");

    RelayForwarder forwarder(conn_a, conn_b);

    EXPECT_TRUE(forwarder.Start());
    EXPECT_EQ(forwarder.GetStatus(), ForwardingStatus::ACTIVE);

    forwarder.Stop();
}

TEST_F(ForwarderTest, ForwarderStop) {
    auto conn_a = std::make_shared<ActiveRelayConnection>("peer-a");
    auto conn_b = std::make_shared<ActiveRelayConnection>("peer-b");

    RelayForwarder forwarder(conn_a, conn_b);

    forwarder.Start();
    forwarder.Stop();

    EXPECT_EQ(forwarder.GetStatus(), ForwardingStatus::STOPPED);
}

TEST_F(ForwarderTest, ForwarderPauseResume) {
    auto conn_a = std::make_shared<ActiveRelayConnection>("peer-a");
    auto conn_b = std::make_shared<ActiveRelayConnection>("peer-b");

    RelayForwarder forwarder(conn_a, conn_b);

    forwarder.Start();
    EXPECT_TRUE(forwarder.IsActive());

    forwarder.Pause();
    EXPECT_EQ(forwarder.GetStatus(), ForwardingStatus::PAUSED);

    forwarder.Resume();
    EXPECT_TRUE(forwarder.IsActive());

    forwarder.Stop();
}

TEST_F(ForwarderTest, ForwarderStats) {
    auto conn_a = std::make_shared<ActiveRelayConnection>("peer-a");
    auto conn_b = std::make_shared<ActiveRelayConnection>("peer-b");

    RelayForwarder forwarder(conn_a, conn_b);

    auto stats = forwarder.GetStats();
    EXPECT_EQ(stats.bytes_sent, 0);
    EXPECT_EQ(stats.bytes_received, 0);
    EXPECT_EQ(stats.packets_sent, 0);
    EXPECT_EQ(stats.packets_received, 0);
}

TEST_F(ForwarderTest, ForwarderResetStats) {
    auto conn_a = std::make_shared<ActiveRelayConnection>("peer-a");
    auto conn_b = std::make_shared<ActiveRelayConnection>("peer-b");

    RelayForwarder forwarder(conn_a, conn_b);

    forwarder.ResetStats();

    auto stats = forwarder.GetStats();
    EXPECT_EQ(stats.bytes_sent, 0);
    EXPECT_EQ(stats.bytes_received, 0);
}

TEST_F(ForwarderTest, ForwarderBandwidthLimit) {
    auto conn_a = std::make_shared<ActiveRelayConnection>("peer-a");
    auto conn_b = std::make_shared<ActiveRelayConnection>("peer-b");

    RelayForwarder forwarder(conn_a, conn_b, 10000);  // 10KB/sec

    EXPECT_EQ(forwarder.GetBandwidthLimit(), 10000);

    forwarder.SetBandwidthLimit(20000);
    EXPECT_EQ(forwarder.GetBandwidthLimit(), 20000);
}

TEST_F(ForwarderTest, ForwarderNullConnections) {
    RelayForwarder forwarder(nullptr, nullptr);

    EXPECT_FALSE(forwarder.Start());
}

// Performance Tests
TEST_F(ForwarderTest, TokenBucketPerformance) {
    TokenBucket bucket(1000000, 2000000);  // 1MB/sec

    const int num_ops = 10000;

    auto start = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < num_ops; i++) {
        bucket.TryConsume(100);
    }

    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start);

    double avg_time_ns = static_cast<double>(duration.count()) / num_ops;

    std::cout << "Average token bucket operation: " << avg_time_ns << " ns" << std::endl;

    // Should be fast (< 1000 ns per operation)
    EXPECT_LT(avg_time_ns, 1000.0);
}

TEST_F(ForwarderTest, BandwidthLimiterPerformance) {
    BandwidthLimiter limiter(1000000);  // 1MB/sec

    const int num_ops = 10000;

    auto start = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < num_ops; i++) {
        limiter.CanSend(100);
    }

    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start);

    double avg_time_ns = static_cast<double>(duration.count()) / num_ops;

    std::cout << "Average bandwidth limiter check: " << avg_time_ns << " ns" << std::endl;

    // Should be fast (< 1000 ns per operation)
    EXPECT_LT(avg_time_ns, 1000.0);
}
