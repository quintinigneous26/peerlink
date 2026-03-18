#pragma once

#include <string>
#include <vector>
#include <optional>
#include <memory>
#include <functional>
#include <unordered_map>
#include <mutex>
#include <thread>
#include "p2p/servers/relay/hop_protocol.hpp"
#include "p2p/servers/relay/reservation_manager.hpp"

namespace p2p {
namespace relay {
namespace v2 {

/**
 * Persistent reservation record
 */
struct PersistentReservation {
    std::string peer_id;
    uint64_t expire_time_ns;
    std::vector<uint8_t> voucher;
    std::string signature;
    uint64_t data_limit;      // Bytes
    uint64_t bandwidth_limit; // Bytes/sec
    uint64_t created_at_ns;

    // Statistics
    uint64_t bytes_relayed{0};
    uint64_t connections_accepted{0};
};

/**
 * Persistent voucher record
 */
struct PersistentVoucher {
    std::string peer_id;
    std::vector<uint8_t> voucher_data;
    std::string signature;
    uint64_t issued_at_ns;
    uint64_t expires_at_ns;
    bool revoked{false};
};

/**
 * Persistent rate limit record
 */
struct PersistentRateLimit {
    std::string client_id;  // IP address or peer ID
    uint64_t request_count;
    uint64_t window_start_ns;
    uint64_t window_end_ns;
};

/**
 * Storage backend interface
 */
class StorageBackend {
public:
    virtual ~StorageBackend() = default;

    /**
     * Initialize storage
     */
    virtual bool Initialize() = 0;

    /**
     * Shutdown storage
     */
    virtual void Shutdown() = 0;

    /**
     * Check if storage is healthy
     */
    virtual bool IsHealthy() const = 0;

    /**
     * Get storage statistics
     */
    struct Stats {
        uint64_t total_reservations{0};
        uint64_t total_vouchers{0};
        uint64_t total_rate_limits{0};
        uint64_t storage_size_bytes{0};
    };
    virtual Stats GetStats() const = 0;

    // Reservation operations (virtual for polymorphic access)
    virtual bool SaveReservation(const PersistentReservation& reservation) = 0;
    virtual std::optional<PersistentReservation> LoadReservation(const std::string& peer_id) = 0;
    virtual bool DeleteReservation(const std::string& peer_id) = 0;
    virtual std::vector<PersistentReservation> LoadAllReservations() = 0;
    virtual std::vector<PersistentReservation> LoadExpiredReservations(uint64_t now_ns) = 0;

    // Voucher operations
    virtual bool SaveVoucher(const PersistentVoucher& voucher) = 0;
    virtual std::optional<PersistentVoucher> LoadVoucher(const std::string& peer_id) = 0;
    virtual bool DeleteVoucher(const std::string& peer_id) = 0;
    virtual std::vector<PersistentVoucher> LoadAllVouchers() = 0;

    // Rate limit operations
    virtual bool SaveRateLimit(const PersistentRateLimit& limit) = 0;
    virtual std::optional<PersistentRateLimit> LoadRateLimit(const std::string& client_id) = 0;
    virtual bool DeleteRateLimit(const std::string& client_id) = 0;
};

/**
 * In-memory storage backend (for testing/fallback)
 */
class MemoryStorage : public StorageBackend {
public:
    MemoryStorage() = default;
    ~MemoryStorage() override = default;

    bool Initialize() override { return true; }
    void Shutdown() override {}
    bool IsHealthy() const override { return true; }
    Stats GetStats() const override;

    // Reservation operations
    bool SaveReservation(const PersistentReservation& reservation) override;
    std::optional<PersistentReservation> LoadReservation(const std::string& peer_id) override;
    bool DeleteReservation(const std::string& peer_id) override;
    std::vector<PersistentReservation> LoadAllReservations() override;
    std::vector<PersistentReservation> LoadExpiredReservations(uint64_t now_ns) override;

    // Voucher operations
    bool SaveVoucher(const PersistentVoucher& voucher) override;
    std::optional<PersistentVoucher> LoadVoucher(const std::string& peer_id) override;
    bool DeleteVoucher(const std::string& peer_id) override;
    std::vector<PersistentVoucher> LoadAllVouchers() override;

    // Rate limit operations
    bool SaveRateLimit(const PersistentRateLimit& limit) override;
    std::optional<PersistentRateLimit> LoadRateLimit(const std::string& client_id) override;
    bool DeleteRateLimit(const std::string& client_id) override;

private:
    mutable std::mutex mutex_;

    std::unordered_map<std::string, PersistentReservation> reservations_;
    std::unordered_map<std::string, PersistentVoucher> vouchers_;
    std::unordered_map<std::string, PersistentRateLimit> rate_limits_;
};

/**
 * SQLite storage backend (production)
 */
class SQLiteStorage : public StorageBackend {
public:
    explicit SQLiteStorage(const std::string& db_path);
    ~SQLiteStorage() override;

    bool Initialize() override;
    void Shutdown() override;
    bool IsHealthy() const override { return initialized_; }
    Stats GetStats() const override;

    // Reservation operations
    bool SaveReservation(const PersistentReservation& reservation) override;
    std::optional<PersistentReservation> LoadReservation(const std::string& peer_id) override;
    bool DeleteReservation(const std::string& peer_id) override;
    std::vector<PersistentReservation> LoadAllReservations() override;
    std::vector<PersistentReservation> LoadExpiredReservations(uint64_t now_ns) override;

    // Voucher operations
    bool SaveVoucher(const PersistentVoucher& voucher) override;
    std::optional<PersistentVoucher> LoadVoucher(const std::string& peer_id) override;
    bool DeleteVoucher(const std::string& peer_id) override;
    std::vector<PersistentVoucher> LoadAllVouchers() override;

    // Rate limit operations
    bool SaveRateLimit(const PersistentRateLimit& limit) override;
    std::optional<PersistentRateLimit> LoadRateLimit(const std::string& client_id) override;
    bool DeleteRateLimit(const std::string& client_id) override;

private:
    bool CreateTables();
    bool PrepareStatements();

    std::string db_path_;
    bool initialized_{false};

    // SQLite handles (opaque pointer to avoid sqlite3.h dependency in header)
    void* db_{nullptr};
    void* stmt_save_res_{nullptr};
    void* stmt_load_res_{nullptr};
    void* stmt_delete_res_{nullptr};
    void* stmt_load_all_res_{nullptr};
    void* stmt_load_expired_res_{nullptr};
    void* stmt_save_vouch_{nullptr};
    void* stmt_load_vouch_{nullptr};
    void* stmt_delete_vouch_{nullptr};
    void* stmt_save_rate_{nullptr};
    void* stmt_load_rate_{nullptr};
    void* stmt_delete_rate_{nullptr};
};

/**
 * Persistence Manager
 * Manages all persistent data for the relay server
 */
class PersistenceManager {
public:
    /**
     * Create persistence manager with specified backend
     */
    explicit PersistenceManager(std::unique_ptr<StorageBackend> backend);

    ~PersistenceManager();

    /**
     * Initialize persistence
     */
    bool Initialize();

    /**
     * Shutdown persistence
     */
    void Shutdown();

    /**
     * Check if persistence is healthy
     */
    bool IsHealthy() const;

    /**
     * Get storage statistics
     */
    StorageBackend::Stats GetStats() const;

    // Reservation operations
    bool SaveReservation(const PersistentReservation& reservation);
    std::optional<PersistentReservation> LoadReservation(const std::string& peer_id);
    bool DeleteReservation(const std::string& peer_id);
    bool UpdateReservationStats(const std::string& peer_id, uint64_t bytes_relayed);

    // Voucher operations
    bool SaveVoucher(const PersistentVoucher& voucher);
    std::optional<PersistentVoucher> LoadVoucher(const std::string& peer_id);
    bool RevokeVoucher(const std::string& peer_id);

    // Rate limit operations
    bool SaveRateLimit(const PersistentRateLimit& limit);
    std::optional<PersistentRateLimit> LoadRateLimit(const std::string& client_id);

    /**
     * Restore state from persistence
     * Called on server startup to reload reservations
     */
    std::vector<PersistentReservation> RestoreReservations();

    /**
     * Cleanup expired records
     */
    void CleanupExpired();

    /**
     * Set cleanup interval
     */
    void SetCleanupInterval(uint64_t interval_ns);

private:
    void CleanupLoop();

    std::unique_ptr<StorageBackend> backend_;
    std::atomic<bool> running_{false};
    std::thread cleanup_thread_;
    uint64_t cleanup_interval_ns_{60000000000ULL};  // 1 minute
};

} // namespace v2
} // namespace relay
} // namespace p2p
