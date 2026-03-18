#pragma once

#include <memory>
#include <string>
#include <vector>
#include <map>
#include <optional>
#include <mutex>
#include <functional>
#include <chrono>
#include "p2p/crypto/signed_envelope.hpp"
#include "p2p/crypto/ed25519_signer.hpp"

namespace p2p {
namespace relay {
namespace v2 {

// Forward declarations
class ReservationManager;
class VoucherManager;

// Reservation slot
struct ReservationSlot {
    std::string peer_id;
    std::string relay_addr;
    uint64_t expire_time;  // Unix timestamp (seconds)
    uint64_t limit_duration;  // Max duration (seconds)
    uint64_t limit_data;  // Max data (bytes)
    std::vector<uint8_t> voucher;  // Signed envelope
};

// Hop protocol message types
enum class HopMessageType {
    RESERVE = 0,
    CONNECT = 1,
    STATUS = 2
};

// Status codes
enum class StatusCode {
    OK = 0,
    RESERVATION_REFUSED = 1,
    RESOURCE_LIMIT_EXCEEDED = 2,
    PERMISSION_DENIED = 3,
    CONNECTION_FAILED = 4,
    NO_RESERVATION = 5,
    MALFORMED_MESSAGE = 6,
    UNEXPECTED_MESSAGE = 7
};

// Status response
struct StatusResponse {
    StatusCode code;
    std::string text;
};

// RESERVE request
struct ReserveRequest {
    std::string peer_id;
    std::vector<std::string> addrs;
};

// RESERVE response
struct ReserveResponse {
    StatusCode status;
    ReservationSlot reservation;
};

// CONNECT request
struct ConnectRequest {
    std::string peer_id;
    std::vector<uint8_t> voucher;  // Optional voucher for verification
};

// CONNECT response
struct ConnectResponse {
    StatusCode status;
    std::string text;
};

/**
 * Hop Protocol Handler
 * Implements /libp2p/circuit/relay/0.2.0/hop protocol
 */
class HopProtocol {
public:
    HopProtocol(
        std::shared_ptr<ReservationManager> reservation_mgr,
        std::shared_ptr<VoucherManager> voucher_mgr);
    ~HopProtocol() = default;

    // Handle RESERVE message
    ReserveResponse HandleReserve(const ReserveRequest& request);

    // Handle CONNECT message
    ConnectResponse HandleConnect(const ConnectRequest& request);

    // Get protocol ID
    static std::string GetProtocolID() {
        return "/libp2p/circuit/relay/0.2.0/hop";
    }

private:
    std::shared_ptr<ReservationManager> reservation_mgr_;
    std::shared_ptr<VoucherManager> voucher_mgr_;

    // Check if resource limits allow new reservation
    bool CheckResourceLimits();

    // Generate reservation slot
    ReservationSlot GenerateReservation(
        const std::string& peer_id,
        const std::string& relay_addr);
};

/**
 * Voucher Manager
 * Handles Reservation Voucher signing and verification
 */
class VoucherManager {
public:
    VoucherManager(const std::string& relay_peer_id);
    ~VoucherManager() = default;

    // Sign a reservation voucher
    std::vector<uint8_t> SignVoucher(
        const std::string& peer_id,
        uint64_t expiration);

    // Verify a reservation voucher
    bool VerifyVoucher(
        const std::vector<uint8_t>& voucher,
        const std::string& expected_peer_id);

private:
    std::string relay_peer_id_;
    crypto::Ed25519PrivateKey private_key_;
};

/**
 * Reservation Manager
 * Manages active reservations
 */
class ReservationManager {
public:
    ReservationManager(
        size_t max_reservations = 1000,
        uint64_t default_duration = 3600,  // 1 hour
        uint64_t default_data_limit = 1024 * 1024 * 100);  // 100 MB
    ~ReservationManager() = default;

    // Store a reservation
    bool Store(const ReservationSlot& reservation);

    // Lookup a reservation by peer ID
    std::optional<ReservationSlot> Lookup(const std::string& peer_id);

    // Remove a reservation
    void Remove(const std::string& peer_id);

    // Cleanup expired reservations
    size_t CleanupExpired();

    // Check if we can accept more reservations
    bool CanAcceptReservation() const;

    // Get current reservation count
    size_t GetCount() const { return reservations_.size(); }

private:
    size_t max_reservations_;
    uint64_t default_duration_;
    uint64_t default_data_limit_;
    std::map<std::string, ReservationSlot> reservations_;
    mutable std::mutex mutex_;

    // Get current Unix timestamp
    uint64_t GetCurrentTime() const;
};

} // namespace v2
} // namespace relay
} // namespace p2p
