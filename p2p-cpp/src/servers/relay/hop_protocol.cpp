#include "p2p/servers/relay/hop_protocol.hpp"
#include <ctime>
#include <stdexcept>

namespace p2p {
namespace relay {
namespace v2 {

// ============================================================================
// ReservationManager Implementation
// ============================================================================

ReservationManager::ReservationManager(
    size_t max_reservations,
    uint64_t default_duration,
    uint64_t default_data_limit)
    : max_reservations_(max_reservations),
      default_duration_(default_duration),
      default_data_limit_(default_data_limit) {
}

bool ReservationManager::Store(const ReservationSlot& reservation) {
    std::lock_guard<std::mutex> lock(mutex_);

    if (reservations_.size() >= max_reservations_) {
        return false;
    }

    reservations_[reservation.peer_id] = reservation;
    return true;
}

std::optional<ReservationSlot> ReservationManager::Lookup(
    const std::string& peer_id) {

    std::lock_guard<std::mutex> lock(mutex_);

    auto it = reservations_.find(peer_id);
    if (it == reservations_.end()) {
        return std::nullopt;
    }

    // Check if expired
    uint64_t now = GetCurrentTime();
    if (it->second.expire_time < now) {
        reservations_.erase(it);
        return std::nullopt;
    }

    return it->second;
}

void ReservationManager::Remove(const std::string& peer_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    reservations_.erase(peer_id);
}

size_t ReservationManager::CleanupExpired() {
    std::lock_guard<std::mutex> lock(mutex_);

    uint64_t now = GetCurrentTime();
    size_t removed = 0;

    for (auto it = reservations_.begin(); it != reservations_.end();) {
        if (it->second.expire_time < now) {
            it = reservations_.erase(it);
            removed++;
        } else {
            ++it;
        }
    }

    return removed;
}

bool ReservationManager::CanAcceptReservation() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return reservations_.size() < max_reservations_;
}

uint64_t ReservationManager::GetCurrentTime() const {
    return static_cast<uint64_t>(std::time(nullptr));
}

// ============================================================================
// VoucherManager Implementation
// ============================================================================

VoucherManager::VoucherManager(const std::string& relay_peer_id)
    : relay_peer_id_(relay_peer_id),
      private_key_(crypto::Ed25519Signer::GenerateKeyPair()) {
}

std::vector<uint8_t> VoucherManager::SignVoucher(
    const std::string& peer_id,
    uint64_t expiration) {

    // Create voucher payload
    // Format: relay_peer_id + peer_id + expiration
    std::vector<uint8_t> payload;
    payload.insert(payload.end(), relay_peer_id_.begin(), relay_peer_id_.end());
    payload.insert(payload.end(), peer_id.begin(), peer_id.end());

    // Add expiration (8 bytes, big-endian)
    for (int i = 7; i >= 0; i--) {
        payload.push_back((expiration >> (i * 8)) & 0xFF);
    }

    // Create signed envelope
    std::string payload_type = "/libp2p/relay-reservation";

    try {
        auto envelope = crypto::SignedEnvelope::Sign(private_key_, payload_type, payload);
        return envelope.Serialize();
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to sign voucher: " + std::string(e.what()));
    }
}

bool VoucherManager::VerifyVoucher(
    const std::vector<uint8_t>& voucher,
    const std::string& expected_peer_id) {

    try {
        // Deserialize signed envelope
        auto envelope_opt = crypto::SignedEnvelope::Deserialize(voucher);
        if (!envelope_opt.has_value()) {
            return false;
        }

        auto envelope = envelope_opt.value();

        // Verify signature
        std::string payload_type = "/libp2p/relay-reservation";
        if (!envelope.VerifyWithType(payload_type)) {
            return false;
        }

        // Extract and verify payload
        const auto& payload = envelope.payload;

        // Check minimum size (relay_id + peer_id + expiration)
        if (payload.size() < relay_peer_id_.size() + expected_peer_id.size() + 8) {
            return false;
        }

        // Verify relay peer ID
        if (!std::equal(relay_peer_id_.begin(), relay_peer_id_.end(),
                       payload.begin())) {
            return false;
        }

        // Verify peer ID
        size_t peer_id_offset = relay_peer_id_.size();
        if (!std::equal(expected_peer_id.begin(), expected_peer_id.end(),
                       payload.begin() + peer_id_offset)) {
            return false;
        }

        // Extract expiration
        size_t exp_offset = peer_id_offset + expected_peer_id.size();
        uint64_t expiration = 0;
        for (size_t i = 0; i < 8; i++) {
            expiration = (expiration << 8) | payload[exp_offset + i];
        }

        // Check if expired
        uint64_t now = static_cast<uint64_t>(std::time(nullptr));
        if (expiration < now) {
            return false;
        }

        return true;
    } catch (const std::exception&) {
        return false;
    }
}

// ============================================================================
// HopProtocol Implementation
// ============================================================================

HopProtocol::HopProtocol(
    std::shared_ptr<ReservationManager> reservation_mgr,
    std::shared_ptr<VoucherManager> voucher_mgr)
    : reservation_mgr_(reservation_mgr),
      voucher_mgr_(voucher_mgr) {
}

ReserveResponse HopProtocol::HandleReserve(const ReserveRequest& request) {
    ReserveResponse response;

    // Check resource limits
    if (!CheckResourceLimits()) {
        response.status = StatusCode::RESOURCE_LIMIT_EXCEEDED;
        return response;
    }

    // Generate reservation
    std::string relay_addr = "reserved-relay-address";  // TODO: Get actual relay address
    ReservationSlot reservation = GenerateReservation(
        request.peer_id, relay_addr);

    // Store reservation
    if (!reservation_mgr_->Store(reservation)) {
        response.status = StatusCode::RESOURCE_LIMIT_EXCEEDED;
        return response;
    }

    response.status = StatusCode::OK;
    response.reservation = reservation;
    return response;
}

ConnectResponse HopProtocol::HandleConnect(const ConnectRequest& request) {
    ConnectResponse response;

    // Lookup reservation
    auto reservation_opt = reservation_mgr_->Lookup(request.peer_id);
    if (!reservation_opt.has_value()) {
        response.status = StatusCode::NO_RESERVATION;
        response.text = "No reservation found for peer";
        return response;
    }

    // Verify voucher if provided
    if (!request.voucher.empty()) {
        if (!voucher_mgr_->VerifyVoucher(request.voucher, request.peer_id)) {
            response.status = StatusCode::PERMISSION_DENIED;
            response.text = "Invalid voucher";
            return response;
        }
    }

    // TODO: Establish relay connection
    response.status = StatusCode::OK;
    response.text = "Connection established";
    return response;
}

bool HopProtocol::CheckResourceLimits() {
    return reservation_mgr_->CanAcceptReservation();
}

ReservationSlot HopProtocol::GenerateReservation(
    const std::string& peer_id,
    const std::string& relay_addr) {

    ReservationSlot slot;
    slot.peer_id = peer_id;
    slot.relay_addr = relay_addr;

    // Set expiration (1 hour from now)
    uint64_t now = static_cast<uint64_t>(std::time(nullptr));
    slot.expire_time = now + 3600;

    // Set limits
    slot.limit_duration = 3600;  // 1 hour
    slot.limit_data = 1024 * 1024 * 100;  // 100 MB

    // Generate voucher
    slot.voucher = voucher_mgr_->SignVoucher(peer_id, slot.expire_time);

    return slot;
}

} // namespace v2
} // namespace relay
} // namespace p2p
