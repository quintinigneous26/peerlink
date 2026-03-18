/**
 * @file reservation_manager.hpp
 * @brief Relay Reservation Manager
 *
 * Manages relay reservations with token-based authentication.
 * Provides basic security to prevent unauthorized relay usage.
 */

#pragma once

#include <string>
#include <unordered_map>
#include <mutex>
#include <chrono>
#include <optional>
#include <cstdint>

namespace p2p {
namespace relay {

/**
 * @brief Reservation Token
 *
 * Simple token for relay reservation authentication.
 */
struct ReservationToken {
    std::string token_id;           // UUID token identifier
    std::string client_id;          // Client identifier (IP:port or Peer ID)
    uint64_t expiration;            // Expiration timestamp (seconds)
    bool used;                      // Whether token has been used

    /**
     * @brief Check if token is expired
     */
    bool IsExpired() const {
        auto now = std::chrono::system_clock::now();
        auto now_ts = static_cast<uint64_t>(
            std::chrono::duration_cast<std::chrono::seconds>(
                now.time_since_epoch()).count());
        return now_ts >= expiration;  // Use >= to include exact expiration time
    }

    /**
     * @brief Check if token is valid
     */
    bool IsValid() const {
        return !used && !IsExpired();
    }
};

/**
 * @brief Reservation Manager
 *
 * Manages relay reservations and token-based authentication.
 * Provides basic security to prevent unauthorized relay usage.
 */
class ReservationManager {
public:
    /**
     * @brief Constructor
     * @param max_reservations Maximum concurrent reservations
     * @param default_lifetime Default reservation lifetime (seconds)
     */
    ReservationManager(
        size_t max_reservations = 1000,
        uint32_t default_lifetime = 3600);

    /**
     * @brief Create reservation
     * @param client_id Client identifier
     * @param lifetime Requested lifetime (0 = use default)
     * @return Reservation token or empty if failed
     */
    std::optional<ReservationToken> CreateReservation(
        const std::string& client_id,
        uint32_t lifetime = 0);

    /**
     * @brief Validate and consume token
     * @param token_id Token identifier
     * @param client_id Client identifier
     * @return true if token is valid and consumed
     */
    bool ValidateAndConsumeToken(
        const std::string& token_id,
        const std::string& client_id);

    /**
     * @brief Check if client has valid reservation
     * @param client_id Client identifier
     * @return true if client has valid reservation
     */
    bool HasValidReservation(const std::string& client_id);

    /**
     * @brief Cleanup expired reservations
     * @return Number of reservations removed
     */
    size_t CleanupExpired();

    /**
     * @brief Get statistics
     */
    struct Stats {
        size_t total_reservations;
        size_t active_reservations;
        size_t used_reservations;
        size_t expired_reservations;
        size_t max_reservations;
    };
    Stats GetStats() const;

private:
    uint32_t default_lifetime_;
    size_t max_reservations_;

    mutable std::mutex mutex_;
    std::unordered_map<std::string, ReservationToken> reservations_;  // token_id -> token

    /**
     * @brief Generate unique token ID
     */
    std::string GenerateTokenId();

    /**
     * @brief Get current timestamp
     */
    uint64_t CurrentTimestamp() const;
};

} // namespace relay
} // namespace p2p

