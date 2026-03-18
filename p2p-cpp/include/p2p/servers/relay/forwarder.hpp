#pragma once

#include <memory>
#include <atomic>
#include <thread>
#include <vector>
#include <cstdint>
#include <functional>
#include "p2p/servers/relay/relay_connection.hpp"

namespace p2p {
namespace relay {
namespace v2 {

// Forward declarations
class BandwidthLimiter;

// Use RelayConnection from relay_connection.hpp
using Connection = RelayConnection;

/**
 * Traffic statistics for a forwarding session
 */
struct TrafficStats {
    uint64_t bytes_sent{0};
    uint64_t bytes_received{0};
    uint64_t packets_sent{0};
    uint64_t packets_received{0};
    uint64_t errors{0};
};

/**
 * Forwarding status
 */
enum class ForwardingStatus {
    IDLE,
    ACTIVE,
    PAUSED,
    STOPPED,
    ERROR
};

/**
 * RelayForwarder handles bidirectional data forwarding between two connections
 *
 * Features:
 * - Bidirectional forwarding
 * - Traffic statistics
 * - Bandwidth limiting
 * - Error handling
 * - Graceful shutdown
 */
class RelayForwarder {
public:
    /**
     * Create a forwarder for two connections
     * @param conn_a First connection
     * @param conn_b Second connection
     * @param bandwidth_limit Bandwidth limit in bytes/sec (0 = unlimited)
     */
    RelayForwarder(std::shared_ptr<Connection> conn_a,
                   std::shared_ptr<Connection> conn_b,
                   uint64_t bandwidth_limit = 0);

    ~RelayForwarder();

    // Disable copy
    RelayForwarder(const RelayForwarder&) = delete;
    RelayForwarder& operator=(const RelayForwarder&) = delete;

    /**
     * Start forwarding
     * @return true if started successfully
     */
    bool Start();

    /**
     * Stop forwarding
     */
    void Stop();

    /**
     * Pause forwarding
     */
    void Pause();

    /**
     * Resume forwarding
     */
    void Resume();

    /**
     * Get current status
     */
    ForwardingStatus GetStatus() const { return status_; }

    /**
     * Get traffic statistics
     */
    TrafficStats GetStats() const;

    /**
     * Reset statistics
     */
    void ResetStats();

    /**
     * Set bandwidth limit
     * @param limit Bandwidth limit in bytes/sec (0 = unlimited)
     */
    void SetBandwidthLimit(uint64_t limit);

    /**
     * Get bandwidth limit
     */
    uint64_t GetBandwidthLimit() const;

    /**
     * Check if forwarding is active
     */
    bool IsActive() const { return status_ == ForwardingStatus::ACTIVE; }

private:
    /**
     * Forward data from source to destination
     */
    void ForwardLoop(std::shared_ptr<Connection> source,
                     std::shared_ptr<Connection> dest,
                     const std::string& direction);

    /**
     * Check if should continue forwarding
     */
    bool ShouldContinue() const;

    std::shared_ptr<Connection> conn_a_;
    std::shared_ptr<Connection> conn_b_;
    std::shared_ptr<BandwidthLimiter> bandwidth_limiter_;

    std::atomic<ForwardingStatus> status_;

    // Atomic counters for thread-safe statistics
    std::atomic<uint64_t> bytes_sent_{0};
    std::atomic<uint64_t> bytes_received_{0};
    std::atomic<uint64_t> packets_sent_{0};
    std::atomic<uint64_t> packets_received_{0};
    std::atomic<uint64_t> errors_{0};

    std::thread thread_a_to_b_;
    std::thread thread_b_to_a_;
};

/**
 * Token Bucket algorithm for bandwidth limiting
 */
class TokenBucket {
public:
    /**
     * Create a token bucket
     * @param rate Tokens per second
     * @param capacity Maximum tokens
     */
    TokenBucket(uint64_t rate, uint64_t capacity);

    /**
     * Try to consume tokens
     * @param tokens Number of tokens to consume
     * @return true if tokens were consumed
     */
    bool TryConsume(uint64_t tokens);

    /**
     * Wait until tokens are available
     * @param tokens Number of tokens needed
     */
    void Consume(uint64_t tokens);

    /**
     * Set rate
     */
    void SetRate(uint64_t rate);

    /**
     * Get current tokens
     */
    uint64_t GetTokens() const;

private:
    void Refill();

    uint64_t rate_;           // Tokens per second
    uint64_t capacity_;       // Maximum tokens
    std::atomic<uint64_t> tokens_;
    std::atomic<uint64_t> last_refill_ns_;
};

/**
 * Bandwidth limiter using token bucket
 */
class BandwidthLimiter {
public:
    /**
     * Create a bandwidth limiter
     * @param bytes_per_sec Bandwidth limit in bytes/sec (0 = unlimited)
     */
    explicit BandwidthLimiter(uint64_t bytes_per_sec);

    /**
     * Check if can send data
     * @param bytes Number of bytes to send
     * @return true if allowed
     */
    bool CanSend(uint64_t bytes);

    /**
     * Wait until can send data
     * @param bytes Number of bytes to send
     */
    void WaitToSend(uint64_t bytes);

    /**
     * Set bandwidth limit
     * @param bytes_per_sec Bandwidth limit in bytes/sec (0 = unlimited)
     */
    void SetLimit(uint64_t bytes_per_sec);

    /**
     * Get bandwidth limit
     */
    uint64_t GetLimit() const { return limit_; }

    /**
     * Check if unlimited
     */
    bool IsUnlimited() const { return limit_ == 0; }

private:
    uint64_t limit_;
    std::unique_ptr<TokenBucket> bucket_;
};

}  // namespace v2
}  // namespace relay
}  // namespace p2p
