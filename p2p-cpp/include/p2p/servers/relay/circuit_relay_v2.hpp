#pragma once

#include <memory>
#include <string>
#include <vector>
#include <atomic>
#include <thread>
#include <mutex>
#include <unordered_map>
#include <functional>
#include "p2p/servers/relay/relay_connection.hpp"
#include "p2p/servers/relay/forwarder.hpp"
#include "p2p/servers/relay/hop_protocol.hpp"
#include "p2p/servers/relay/stop_protocol.hpp"
#include "p2p/servers/relay/persistence.hpp"
#include "p2p/net/socket.hpp"

namespace p2p {
namespace relay {
namespace v2 {

/**
 * Circuit Relay v2 Server Configuration
 */
struct CircuitRelayConfig {
    // Network
    std::string host = "0.0.0.0";
    uint16_t port = 9001;
    std::string public_ip = "127.0.0.1";

    // Relay identity
    std::string peer_id = "relay-server";

    // Resource limits
    size_t max_reservations = 1000;
    uint64_t default_duration = 3600;        // 1 hour (seconds)
    uint64_t default_data_limit = 104857600; // 100 MB

    // Bandwidth
    uint64_t bandwidth_limit = 10485760;     // 10 MB/sec
    uint64_t per_connection_bandwidth = 1048576; // 1 MB/sec

    // Rate limiting
    uint64_t rate_limit_requests = 100;      // requests per minute
    uint64_t rate_limit_window = 60;         // seconds

    // Persistence
    bool enable_persistence = true;
    std::string persistence_path = "relay_state.db";

    // Monitoring
    bool enable_metrics = true;
    uint64_t metrics_interval = 60000;       // milliseconds
};

/**
 * Circuit Relay v2 Server Statistics
 */
struct CircuitRelayStats {
    // Connection stats
    size_t active_connections{0};
    size_t total_connections{0};
    uint64_t connections_accepted{0};
    uint64_t connections_rejected{0};

    // Data stats
    uint64_t bytes_relayed{0};
    uint64_t packets_relayed{0};

    // Reservation stats
    size_t active_reservations{0};
    uint64_t reservations_created{0};
    uint64_t reservations_expired{0};

    // Error stats
    uint64_t errors{0};
    uint64_t timeouts{0};
};

/**
 * Circuit Relay v2 Server
 * Production-grade implementation with:
 * - Hop/Stop protocol support
 * - Forwarder integration
 * - Persistence
 * - Graceful shutdown
 * - Hot reload
 */
class CircuitRelayServer {
public:
    /**
     * Create relay server with configuration
     */
    explicit CircuitRelayServer(const CircuitRelayConfig& config);

    /**
     * Destructor - ensures graceful shutdown
     */
    ~CircuitRelayServer();

    // Disable copy
    CircuitRelayServer(const CircuitRelayServer&) = delete;
    CircuitRelayServer& operator=(const CircuitRelayServer&) = delete;

    /**
     * Start the relay server
     * @return true if started successfully
     */
    bool Start();

    /**
     * Stop the relay server (graceful shutdown)
     */
    void Stop();

    /**
     * Request graceful shutdown
     * Completes active connections before stopping
     */
    void Shutdown();

    /**
     * Check if server is running
     */
    bool IsRunning() const { return running_.load(); }

    /**
     * Get current statistics
     */
    CircuitRelayStats GetStats() const;

    /**
     * Reset statistics
     */
    void ResetStats();

    /**
     * Update configuration (hot reload)
     * @return true if configuration was updated
     */
    bool UpdateConfig(const CircuitRelayConfig& config);

    /**
     * Get current configuration
     */
    const CircuitRelayConfig& GetConfig() const { return config_; }

    /**
     * Register event callback
     */
    using EventCallback = std::function<void(const std::string& event, const std::string& detail)>;
    void SetEventCallback(EventCallback callback);

    /**
     * Get protocol handlers
     */
    std::shared_ptr<HopProtocol> GetHopProtocol() { return hop_protocol_; }
    std::shared_ptr<StopProtocol> GetStopProtocol() { return stop_protocol_; }

private:
    /**
     * Start UDP listener for incoming messages
     */
    bool StartListener();

    /**
     * Stop listener
     */
    void StopListener();

    /**
     * Receive loop
     */
    void ReceiveLoop();

    /**
     * Handle incoming message
     */
    void HandleMessage(
        const std::vector<uint8_t>& data,
        const net::SocketAddr& from_addr);

    /**
     * Handle RESERVE message (Hop protocol)
     */
    std::vector<uint8_t> HandleReserve(
        const ReserveRequest& request,
        const net::SocketAddr& from_addr);

    /**
     * Handle CONNECT message (Hop protocol)
     */
    std::vector<uint8_t> HandleConnect(
        const ConnectRequest& request,
        const net::SocketAddr& from_addr);

    /**
     * Handle CONNECT message (Stop protocol)
     */
    std::vector<uint8_t> HandleStopConnect(
        const StopConnectRequest& request,
        const net::SocketAddr& from_addr);

    /**
     * Create connection for client
     */
    std::shared_ptr<RelayConnection> CreateConnection(
        const std::string& peer_id,
        const net::SocketAddr& client_addr);

    /**
     * Create forwarder between two connections
     */
    bool CreateForwarder(
        std::shared_ptr<RelayConnection> conn_a,
        std::shared_ptr<RelayConnection> conn_b);

    /**
     * Cleanup completed forwarders
     */
    void CleanupForwarders();

    /**
     * Update statistics
     */
    void UpdateStatistics();

    /**
     * Metrics collection loop
     */
    void MetricsLoop();

    /**
     * Notify event
     */
    void NotifyEvent(const std::string& event, const std::string& detail);

    // Configuration
    CircuitRelayConfig config_;
    mutable std::mutex config_mutex_;

    // Protocol handlers
    std::shared_ptr<ReservationManager> reservation_manager_;
    std::shared_ptr<VoucherManager> voucher_manager_;
    std::shared_ptr<HopProtocol> hop_protocol_;
    std::shared_ptr<StopProtocol> stop_protocol_;

    // Persistence
    std::unique_ptr<PersistenceManager> persistence_manager_;

    // Network
    std::unique_ptr<net::UDPSocket> socket_;
    std::thread receive_thread_;

    // Connections and forwarders
    struct ActiveConnection {
        std::shared_ptr<RelayConnection> connection;
        std::string peer_id;
        net::SocketAddr client_addr;
        uint64_t created_at_ns;
    };
    std::unordered_map<std::string, ActiveConnection> connections_;
    mutable std::mutex connections_mutex_;

    struct ActiveForwarder {
        std::unique_ptr<RelayForwarder> forwarder;
        std::string conn_a_id;
        std::string conn_b_id;
        uint64_t created_at_ns;
    };
    std::vector<ActiveForwarder> forwarders_;
    mutable std::mutex forwarders_mutex_;

    // State
    std::atomic<bool> running_{false};
    std::atomic<bool> shutdown_requested_{false};

    // Statistics
    CircuitRelayStats stats_;
    mutable std::mutex stats_mutex_;

    // Event callback
    EventCallback event_callback_;
    mutable std::mutex callback_mutex_;

    // Metrics thread
    std::thread metrics_thread_;
};

/**
 * Factory for creating relay servers
 */
class CircuitRelayFactory {
public:
    /**
     * Create server with default configuration
     */
    static std::unique_ptr<CircuitRelayServer> CreateDefault();

    /**
     * Create server with custom configuration
     */
    static std::unique_ptr<CircuitRelayServer> Create(const CircuitRelayConfig& config);

    /**
     * Create production server with recommended settings
     */
    static std::unique_ptr<CircuitRelayServer> CreateProduction(
        const std::string& public_ip,
        uint16_t port);
};

} // namespace v2
} // namespace relay
} // namespace p2p
