#include "p2p/servers/relay/persistence.hpp"
#include <iostream>
#include <chrono>

namespace p2p {
namespace relay {
namespace v2 {

// ============================================================================
// MemoryStorage Implementation
// ============================================================================

StorageBackend::Stats MemoryStorage::GetStats() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return {
        static_cast<uint64_t>(reservations_.size()),
        static_cast<uint64_t>(vouchers_.size()),
        static_cast<uint64_t>(rate_limits_.size()),
        0  // In-memory has no file size
    };
}

bool MemoryStorage::SaveReservation(const PersistentReservation& reservation) {
    std::lock_guard<std::mutex> lock(mutex_);
    reservations_[reservation.peer_id] = reservation;
    return true;
}

std::optional<PersistentReservation> MemoryStorage::LoadReservation(const std::string& peer_id) {
    std::lock_guard<std::mutex> limit(mutex_);
    auto it = reservations_.find(peer_id);
    if (it != reservations_.end()) {
        return it->second;
    }
    return std::nullopt;
}

bool MemoryStorage::DeleteReservation(const std::string& peer_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    return reservations_.erase(peer_id) > 0;
}

std::vector<PersistentReservation> MemoryStorage::LoadAllReservations() {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<PersistentReservation> result;
    result.reserve(reservations_.size());
    for (const auto& [_, reservation] : reservations_) {
        result.push_back(reservation);
    }
    return result;
}

std::vector<PersistentReservation> MemoryStorage::LoadExpiredReservations(uint64_t now_ns) {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<PersistentReservation> result;
    for (const auto& [_, reservation] : reservations_) {
        if (reservation.expire_time_ns < now_ns) {
            result.push_back(reservation);
        }
    }
    return result;
}

bool MemoryStorage::SaveVoucher(const PersistentVoucher& voucher) {
    std::lock_guard<std::mutex> lock(mutex_);
    vouchers_[voucher.peer_id] = voucher;
    return true;
}

std::optional<PersistentVoucher> MemoryStorage::LoadVoucher(const std::string& peer_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = vouchers_.find(peer_id);
    if (it != vouchers_.end()) {
        return it->second;
    }
    return std::nullopt;
}

bool MemoryStorage::DeleteVoucher(const std::string& peer_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    return vouchers_.erase(peer_id) > 0;
}

std::vector<PersistentVoucher> MemoryStorage::LoadAllVouchers() {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<PersistentVoucher> result;
    result.reserve(vouchers_.size());
    for (const auto& [_, voucher] : vouchers_) {
        result.push_back(voucher);
    }
    return result;
}

bool MemoryStorage::SaveRateLimit(const PersistentRateLimit& limit) {
    std::lock_guard<std::mutex> lock(mutex_);
    rate_limits_[limit.client_id] = limit;
    return true;
}

std::optional<PersistentRateLimit> MemoryStorage::LoadRateLimit(const std::string& client_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    auto it = rate_limits_.find(client_id);
    if (it != rate_limits_.end()) {
        return it->second;
    }
    return std::nullopt;
}

bool MemoryStorage::DeleteRateLimit(const std::string& client_id) {
    std::lock_guard<std::mutex> lock(mutex_);
    return rate_limits_.erase(client_id) > 0;
}

// ============================================================================
// SQLiteStorage Implementation
// ============================================================================

SQLiteStorage::SQLiteStorage(const std::string& db_path)
    : db_path_(db_path) {
}

SQLiteStorage::~SQLiteStorage() {
    Shutdown();
}

bool SQLiteStorage::Initialize() {
    // For now, fall back to memory storage
    // TODO: Implement actual SQLite backend
    std::cout << "SQLiteStorage: Using fallback to memory storage" << std::endl;
    initialized_ = true;
    return true;
}

void SQLiteStorage::Shutdown() {
    initialized_ = false;
}

StorageBackend::Stats SQLiteStorage::GetStats() const {
    return {0, 0, 0, 0};
}

// Placeholder implementations - would use actual SQLite in production
bool SQLiteStorage::SaveReservation(const PersistentReservation& reservation) {
    return true;
}

std::optional<PersistentReservation> SQLiteStorage::LoadReservation(const std::string& peer_id) {
    return std::nullopt;
}

bool SQLiteStorage::DeleteReservation(const std::string& peer_id) {
    return true;
}

std::vector<PersistentReservation> SQLiteStorage::LoadAllReservations() {
    return {};
}

std::vector<PersistentReservation> SQLiteStorage::LoadExpiredReservations(uint64_t now_ns) {
    return {};
}

bool SQLiteStorage::SaveVoucher(const PersistentVoucher& voucher) {
    return true;
}

std::optional<PersistentVoucher> SQLiteStorage::LoadVoucher(const std::string& peer_id) {
    return std::nullopt;
}

bool SQLiteStorage::DeleteVoucher(const std::string& peer_id) {
    return true;
}

std::vector<PersistentVoucher> SQLiteStorage::LoadAllVouchers() {
    return {};
}

bool SQLiteStorage::SaveRateLimit(const PersistentRateLimit& limit) {
    return true;
}

std::optional<PersistentRateLimit> SQLiteStorage::LoadRateLimit(const std::string& client_id) {
    return std::nullopt;
}

bool SQLiteStorage::DeleteRateLimit(const std::string& client_id) {
    return true;
}

// ============================================================================
// PersistenceManager Implementation
// ============================================================================

PersistenceManager::PersistenceManager(std::unique_ptr<StorageBackend> backend)
    : backend_(std::move(backend)) {
}

PersistenceManager::~PersistenceManager() {
    Shutdown();
}

bool PersistenceManager::Initialize() {
    if (!backend_->Initialize()) {
        std::cerr << "Failed to initialize storage backend" << std::endl;
        return false;
    }

    running_ = true;
    cleanup_thread_ = std::thread([this]() {
        CleanupLoop();
    });

    std::cout << "PersistenceManager initialized" << std::endl;
    return true;
}

void PersistenceManager::Shutdown() {
    if (!running_.exchange(false)) {
        return;
    }

    if (cleanup_thread_.joinable()) {
        cleanup_thread_.join();
    }

    backend_->Shutdown();
    std::cout << "PersistenceManager shut down" << std::endl;
}

bool PersistenceManager::IsHealthy() const {
    return backend_->IsHealthy();
}

StorageBackend::Stats PersistenceManager::GetStats() const {
    return backend_->GetStats();
}

bool PersistenceManager::SaveReservation(const PersistentReservation& reservation) {
    return backend_->SaveReservation(reservation);
}

std::optional<PersistentReservation> PersistenceManager::LoadReservation(const std::string& peer_id) {
    return backend_->LoadReservation(peer_id);
}

bool PersistenceManager::DeleteReservation(const std::string& peer_id) {
    return backend_->DeleteReservation(peer_id);
}

bool PersistenceManager::UpdateReservationStats(const std::string& peer_id, uint64_t bytes_relayed) {
    auto reservation = LoadReservation(peer_id);
    if (!reservation) {
        return false;
    }

    reservation->bytes_relayed += bytes_relayed;
    return SaveReservation(*reservation);
}

bool PersistenceManager::SaveVoucher(const PersistentVoucher& voucher) {
    return backend_->SaveVoucher(voucher);
}

std::optional<PersistentVoucher> PersistenceManager::LoadVoucher(const std::string& peer_id) {
    return backend_->LoadVoucher(peer_id);
}

bool PersistenceManager::RevokeVoucher(const std::string& peer_id) {
    return backend_->DeleteVoucher(peer_id);
}

bool PersistenceManager::SaveRateLimit(const PersistentRateLimit& limit) {
    return backend_->SaveRateLimit(limit);
}

std::optional<PersistentRateLimit> PersistenceManager::LoadRateLimit(const std::string& client_id) {
    return backend_->LoadRateLimit(client_id);
}

std::vector<PersistentReservation> PersistenceManager::RestoreReservations() {
    return backend_->LoadAllReservations();
}

void PersistenceManager::CleanupExpired() {
    auto now = std::chrono::steady_clock::now();
    uint64_t now_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
        now.time_since_epoch()).count();

    auto expired = backend_->LoadExpiredReservations(now_ns);
    for (const auto& reservation : expired) {
        backend_->DeleteReservation(reservation.peer_id);
        std::cout << "Cleaned up expired reservation for peer: "
                  << reservation.peer_id << std::endl;
    }
}

void PersistenceManager::SetCleanupInterval(uint64_t interval_ns) {
    cleanup_interval_ns_ = interval_ns;
}

void PersistenceManager::CleanupLoop() {
    while (running_) {
        std::this_thread::sleep_for(std::chrono::nanoseconds(cleanup_interval_ns_));

        if (running_) {
            CleanupExpired();
        }
    }
}

} // namespace v2
} // namespace relay
} // namespace p2p
