/**
 * @file reservation_manager.cpp
 * @brief Relay Reservation Manager Implementation
 */

#include "p2p/servers/relay/reservation_manager.hpp"
#include <random>
#include <sstream>
#include <iomanip>
#include <algorithm>

namespace p2p {
namespace relay {

ReservationManager::ReservationManager(
    size_t max_reservations,
    uint32_t default_lifetime)
    : default_lifetime_(default_lifetime),
      max_reservations_(max_reservations) {
}

std::optional<ReservationToken> ReservationManager::CreateReservation(
    const std::string& client_id,
    uint32_t lifetime) {

    std::lock_guard<std::mutex> lock(mutex_);

    // Check if max reservations reached
    if (reservations_.size() >= max_reservations_) {
        return std::nullopt;
    }

    // Use default lifetime if not specified
    if (lifetime == 0) {
        lifetime = default_lifetime_;
    }

    // Create token
    ReservationToken token;
    token.token_id = GenerateTokenId();
    token.client_id = client_id;
    token.expiration = CurrentTimestamp() + lifetime;
    token.used = false;

    // Store reservation
    reservations_[token.token_id] = token;

    return token;
}

bool ReservationManager::ValidateAndConsumeToken(
    const std::string& token_id,
    const std::string& client_id) {

    std::lock_guard<std::mutex> lock(mutex_);

    auto it = reservations_.find(token_id);
    if (it == reservations_.end()) {
        return false;  // Token not found
    }

    auto& token = it->second;

    // Check if token is valid
    if (!token.IsValid()) {
        return false;
    }

    // Check if client ID matches
    if (token.client_id != client_id) {
        return false;
    }

    // Mark token as used
    token.used = true;

    return true;
}

bool ReservationManager::HasValidReservation(const std::string& client_id) {
    std::lock_guard<std::mutex> lock(mutex_);

    for (const auto& [token_id, token] : reservations_) {
        if (token.client_id == client_id && token.IsValid()) {
            return true;
        }
    }

    return false;
}

size_t ReservationManager::CleanupExpired() {
    std::lock_guard<std::mutex> lock(mutex_);

    size_t removed = 0;
    auto it = reservations_.begin();
    while (it != reservations_.end()) {
        if (it->second.IsExpired() || it->second.used) {
            it = reservations_.erase(it);
            ++removed;
        } else {
            ++it;
        }
    }

    return removed;
}

ReservationManager::Stats ReservationManager::GetStats() const {
    std::lock_guard<std::mutex> lock(mutex_);

    Stats stats;
    stats.total_reservations = reservations_.size();
    stats.active_reservations = 0;
    stats.used_reservations = 0;
    stats.expired_reservations = 0;
    stats.max_reservations = max_reservations_;

    for (const auto& [token_id, token] : reservations_) {
        if (token.used) {
            ++stats.used_reservations;
        } else if (token.IsExpired()) {
            ++stats.expired_reservations;
        } else {
            ++stats.active_reservations;
        }
    }

    return stats;
}

std::string ReservationManager::GenerateTokenId() {
    // Generate UUID-like token
    std::random_device rd;
    std::mt19937_64 gen(rd());
    std::uniform_int_distribution<uint64_t> dis;

    uint64_t part1 = dis(gen);
    uint64_t part2 = dis(gen);

    std::ostringstream oss;
    oss << std::hex << std::setfill('0')
        << std::setw(16) << part1
        << std::setw(16) << part2;

    return oss.str();
}

uint64_t ReservationManager::CurrentTimestamp() const {
    auto now = std::chrono::system_clock::now();
    return std::chrono::duration_cast<std::chrono::seconds>(
        now.time_since_epoch()).count();
}

} // namespace relay
} // namespace p2p
