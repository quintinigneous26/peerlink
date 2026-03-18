#include "p2p/servers/relay/forwarder.hpp"
#include "p2p/servers/relay/stop_protocol.hpp"
#include <chrono>
#include <thread>
#include <algorithm>

namespace p2p {
namespace relay {
namespace v2 {

// TokenBucket implementation
TokenBucket::TokenBucket(uint64_t rate, uint64_t capacity)
    : rate_(rate), capacity_(capacity), tokens_(capacity) {
    auto now = std::chrono::steady_clock::now();
    last_refill_ns_ = std::chrono::duration_cast<std::chrono::nanoseconds>(
        now.time_since_epoch()).count();
}

void TokenBucket::Refill() {
    auto now = std::chrono::steady_clock::now();
    uint64_t now_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
        now.time_since_epoch()).count();

    uint64_t last_ns = last_refill_ns_.load();
    uint64_t elapsed_ns = now_ns - last_ns;

    // Calculate tokens to add
    uint64_t tokens_to_add = (rate_ * elapsed_ns) / 1000000000ULL;

    if (tokens_to_add > 0) {
        uint64_t current = tokens_.load();
        uint64_t new_tokens = std::min(current + tokens_to_add, capacity_);
        tokens_ = new_tokens;
        last_refill_ns_ = now_ns;
    }
}

bool TokenBucket::TryConsume(uint64_t tokens) {
    Refill();

    uint64_t current = tokens_.load();
    if (current >= tokens) {
        tokens_ = current - tokens;
        return true;
    }

    return false;
}

void TokenBucket::Consume(uint64_t tokens) {
    while (!TryConsume(tokens)) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}

void TokenBucket::SetRate(uint64_t rate) {
    rate_ = rate;
}

uint64_t TokenBucket::GetTokens() const {
    return tokens_.load();
}

// BandwidthLimiter implementation
BandwidthLimiter::BandwidthLimiter(uint64_t bytes_per_sec)
    : limit_(bytes_per_sec) {
    if (bytes_per_sec > 0) {
        // Capacity = 2x rate for burst handling
        bucket_ = std::make_unique<TokenBucket>(bytes_per_sec, bytes_per_sec * 2);
    }
}

bool BandwidthLimiter::CanSend(uint64_t bytes) {
    if (IsUnlimited()) return true;
    return bucket_->TryConsume(bytes);
}

void BandwidthLimiter::WaitToSend(uint64_t bytes) {
    if (IsUnlimited()) return;
    bucket_->Consume(bytes);
}

void BandwidthLimiter::SetLimit(uint64_t bytes_per_sec) {
    limit_ = bytes_per_sec;
    if (bytes_per_sec > 0) {
        if (bucket_) {
            bucket_->SetRate(bytes_per_sec);
        } else {
            bucket_ = std::make_unique<TokenBucket>(bytes_per_sec, bytes_per_sec * 2);
        }
    } else {
        bucket_.reset();
    }
}

// RelayForwarder implementation
RelayForwarder::RelayForwarder(std::shared_ptr<Connection> conn_a,
                               std::shared_ptr<Connection> conn_b,
                               uint64_t bandwidth_limit)
    : conn_a_(conn_a),
      conn_b_(conn_b),
      bandwidth_limiter_(std::make_shared<BandwidthLimiter>(bandwidth_limit)),
      status_(ForwardingStatus::IDLE) {
}

RelayForwarder::~RelayForwarder() {
    Stop();
}

bool RelayForwarder::Start() {
    if (status_ != ForwardingStatus::IDLE) {
        return false;
    }

    if (!conn_a_ || !conn_b_) {
        return false;
    }

    status_ = ForwardingStatus::ACTIVE;

    // Start forwarding threads
    thread_a_to_b_ = std::thread([this]() {
        ForwardLoop(conn_a_, conn_b_, "A->B");
    });

    thread_b_to_a_ = std::thread([this]() {
        ForwardLoop(conn_b_, conn_a_, "B->A");
    });

    return true;
}

void RelayForwarder::Stop() {
    if (status_ == ForwardingStatus::STOPPED) {
        return;
    }

    status_ = ForwardingStatus::STOPPED;

    // Wait for threads to finish
    if (thread_a_to_b_.joinable()) {
        thread_a_to_b_.join();
    }

    if (thread_b_to_a_.joinable()) {
        thread_b_to_a_.join();
    }

    // Close connections
    if (conn_a_) {
        conn_a_->Close();
    }

    if (conn_b_) {
        conn_b_->Close();
    }
}

void RelayForwarder::Pause() {
    if (status_ == ForwardingStatus::ACTIVE) {
        status_ = ForwardingStatus::PAUSED;
    }
}

void RelayForwarder::Resume() {
    if (status_ == ForwardingStatus::PAUSED) {
        status_ = ForwardingStatus::ACTIVE;
    }
}

TrafficStats RelayForwarder::GetStats() const {
    TrafficStats stats;
    stats.bytes_sent = bytes_sent_.load();
    stats.bytes_received = bytes_received_.load();
    stats.packets_sent = packets_sent_.load();
    stats.packets_received = packets_received_.load();
    stats.errors = errors_.load();
    return stats;
}

void RelayForwarder::ResetStats() {
    bytes_sent_ = 0;
    bytes_received_ = 0;
    packets_sent_ = 0;
    packets_received_ = 0;
    errors_ = 0;
}

void RelayForwarder::SetBandwidthLimit(uint64_t limit) {
    if (bandwidth_limiter_) {
        bandwidth_limiter_->SetLimit(limit);
    }
}

uint64_t RelayForwarder::GetBandwidthLimit() const {
    if (bandwidth_limiter_) {
        return bandwidth_limiter_->GetLimit();
    }
    return 0;
}

bool RelayForwarder::ShouldContinue() const {
    auto status = status_.load();
    return status == ForwardingStatus::ACTIVE || status == ForwardingStatus::PAUSED;
}

void RelayForwarder::ForwardLoop(std::shared_ptr<Connection> source,
                                 std::shared_ptr<Connection> dest,
                                 const std::string& direction) {
    const size_t buffer_size = 65536;  // 64KB buffer

    while (ShouldContinue()) {
        // Wait if paused
        if (status_ == ForwardingStatus::PAUSED) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            continue;
        }

        // Receive data from source
        auto data = source->Receive();

        if (data.empty()) {
            // No data available, wait a bit
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }

        // Apply bandwidth limiting
        if (bandwidth_limiter_ && !bandwidth_limiter_->IsUnlimited()) {
            bandwidth_limiter_->WaitToSend(data.size());
        }

        // Send data to destination
        bool sent = dest->Send(data);

        if (sent) {
            // Update statistics
            if (direction == "A->B") {
                bytes_sent_ += data.size();
                packets_sent_++;
            } else {
                bytes_received_ += data.size();
                packets_received_++;
            }
        } else {
            // Send failed
            errors_++;

            // Check if connection is closed
            if (!dest->IsOpen()) {
                status_ = ForwardingStatus::ERROR;
                break;
            }
        }
    }
}

}  // namespace v2
}  // namespace relay
}  // namespace p2p
