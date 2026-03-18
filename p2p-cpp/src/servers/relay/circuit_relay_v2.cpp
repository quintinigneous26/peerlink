#include "p2p/servers/relay/circuit_relay_v2.hpp"
#include <iostream>
#include <chrono>
#include <algorithm>

namespace p2p {
namespace relay {
namespace v2 {

// ============================================================================
// CircuitRelayServer Implementation
// ============================================================================

CircuitRelayServer::CircuitRelayServer(const CircuitRelayConfig& config)
    : config_(config) {

    // Create reservation manager
    reservation_manager_ = std::make_shared<ReservationManager>(
        config.max_reservations,
        config.default_duration,
        config.default_data_limit);

    // Create voucher manager
    voucher_manager_ = std::make_shared<VoucherManager>(config.peer_id);

    // Create protocol handlers
    hop_protocol_ = std::make_shared<HopProtocol>(
        reservation_manager_, voucher_manager_);

    stop_protocol_ = std::make_shared<StopProtocol>(reservation_manager_);

    // Create persistence manager
    if (config.enable_persistence) {
        auto backend = std::make_unique<MemoryStorage>();
        persistence_manager_ = std::make_unique<PersistenceManager>(
            std::move(backend));
    }

    NotifyEvent("created", "CircuitRelayServer instance created");
}

CircuitRelayServer::~CircuitRelayServer() {
    Stop();
}

bool CircuitRelayServer::Start() {
    if (running_.exchange(true)) {
        return true;  // Already running
    }

    std::cout << "Starting Circuit Relay v2 Server on "
              << config_.host << ":" << config_.port << std::endl;

    // Initialize persistence
    if (persistence_manager_) {
        if (!persistence_manager_->Initialize()) {
            std::cerr << "Failed to initialize persistence" << std::endl;
            return false;
        }

        // Restore reservations
        auto restored = persistence_manager_->RestoreReservations();
        for (const auto& reservation : restored) {
            ReservationSlot slot;
            slot.peer_id = reservation.peer_id;
            slot.relay_addr = config_.public_ip;
            slot.expire_time = reservation.expire_time_ns / 1000000000ULL;
            slot.limit_data = reservation.data_limit;

            reservation_manager_->Store(slot);
            std::cout << "Restored reservation for peer: "
                      << reservation.peer_id << std::endl;
        }
    }

    // Start listener
    if (!StartListener()) {
        std::cerr << "Failed to start listener" << std::endl;
        running_ = false;
        return false;
    }

    // Start metrics thread
    if (config_.enable_metrics) {
        metrics_thread_ = std::thread([this]() {
            MetricsLoop();
        });
    }

    NotifyEvent("started", "Server started on " + config_.host + ":" +
                  std::to_string(config_.port));

    std::cout << "Circuit Relay v2 Server started successfully" << std::endl;
    return true;
}

void CircuitRelayServer::Stop() {
    if (!running_.exchange(false)) {
        return;  // Already stopped
    }

    std::cout << "Stopping Circuit Relay v2 Server..." << std::endl;

    // Stop listener
    StopListener();

    // Close all connections
    {
        std::lock_guard<std::mutex> lock(connections_mutex_);
        for (auto& [peer_id, conn] : connections_) {
            conn.connection->Close();
        }
        connections_.clear();
    }

    // Stop all forwarders
    {
        std::lock_guard<std::mutex> lock(forwarders_mutex_);
        forwarders_.clear();
    }

    // Wait for receive thread
    if (receive_thread_.joinable()) {
        receive_thread_.join();
    }

    // Wait for metrics thread
    if (metrics_thread_.joinable()) {
        metrics_thread_.join();
    }

    // Shutdown persistence
    if (persistence_manager_) {
        persistence_manager_->Shutdown();
    }

    NotifyEvent("stopped", "Server stopped");
    std::cout << "Circuit Relay v2 Server stopped" << std::endl;
}

void CircuitRelayServer::Shutdown() {
    shutdown_requested_ = true;

    // Give active connections time to complete (5 seconds)
    auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);

    while (std::chrono::steady_clock::now() < deadline) {
        std::lock_guard<std::mutex> lock(forwarders_mutex_);
        if (forwarders_.empty()) {
            break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    Stop();
}

CircuitRelayStats CircuitRelayServer::GetStats() const {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    return stats_;
}

void CircuitRelayServer::ResetStats() {
    std::lock_guard<std::mutex> lock(stats_mutex_);
    stats_ = CircuitRelayStats{};
}

bool CircuitRelayServer::UpdateConfig(const CircuitRelayConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);

    // Update non-critical settings
    config_.bandwidth_limit = config.bandwidth_limit;
    config_.per_connection_bandwidth = config.per_connection_bandwidth;
    config_.rate_limit_requests = config.rate_limit_requests;
    config_.rate_limit_window = config.rate_limit_window;
    config_.enable_metrics = config.enable_metrics;

    NotifyEvent("config_updated", "Configuration updated");
    return true;
}

void CircuitRelayServer::SetEventCallback(EventCallback callback) {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    event_callback_ = std::move(callback);
}

bool CircuitRelayServer::StartListener() {
    try {
        socket_ = std::make_unique<net::UDPSocket>();
        if (!socket_->IsValid()) {
            return false;
        }

        net::SocketAddr bind_addr(config_.host, config_.port);
        if (!socket_->Bind(bind_addr)) {
            std::cerr << "Failed to bind to " << config_.host
                      << ":" << config_.port << std::endl;
            return false;
        }

        // Start receive loop
        receive_thread_ = std::thread([this]() {
            ReceiveLoop();
        });

        return true;
    } catch (const std::exception& e) {
        std::cerr << "Exception in StartListener: " << e.what() << std::endl;
        return false;
    }
}

void CircuitRelayServer::StopListener() {
    if (socket_) {
        socket_->Close();
    }
}

void CircuitRelayServer::ReceiveLoop() {
    std::vector<uint8_t> buffer;
    net::SocketAddr from_addr;

    while (running_) {
        buffer.clear();

        ssize_t received = socket_->RecvFrom(buffer, from_addr);
        if (received > 0) {
            HandleMessage(buffer, from_addr);
        } else if (received < 0) {
            // Error
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
    }
}

void CircuitRelayServer::HandleMessage(
    const std::vector<uint8_t>& data,
    const net::SocketAddr& from_addr) {

    try {
        // Parse message type from first byte
        if (data.empty()) {
            return;
        }

        uint8_t msg_type = data[0];

        switch (msg_type) {
            case 0:  // RESERVE
                {
                    ReserveRequest req;
                    // TODO: Parse actual request from data
                    HandleReserve(req, from_addr);
                }
                break;

            case 1:  // CONNECT (Hop)
                {
                    ConnectRequest req;
                    // TODO: Parse actual request from data
                    HandleConnect(req, from_addr);
                }
                break;

            case 2:  // CONNECT (Stop)
                {
                    StopConnectRequest req;
                    // TODO: Parse actual request from data
                    HandleStopConnect(req, from_addr);
                }
                break;

            default:
                std::cerr << "Unknown message type: " << (int)msg_type << std::endl;
                break;
        }
    } catch (const std::exception& e) {
        std::cerr << "Exception in HandleMessage: " << e.what() << std::endl;
        stats_.errors++;
    }
}

std::vector<uint8_t> CircuitRelayServer::HandleReserve(
    const ReserveRequest& request,
    const net::SocketAddr& from_addr) {

    std::cout << "Received RESERVE request from peer: "
              << request.peer_id << std::endl;

    // Check resource limits
    if (!reservation_manager_->CanAcceptReservation()) {
        stats_.connections_rejected++;
        NotifyEvent("reserve_rejected", "Resource limit exceeded");

        ReserveResponse response;
        response.status = StatusCode::RESOURCE_LIMIT_EXCEEDED;
        // TODO: Serialize response
        return {};
    }

    // Generate reservation
    auto response = hop_protocol_->HandleReserve(request);

    if (response.status == StatusCode::OK) {
        stats_.reservations_created++;

        // Persist reservation
        if (persistence_manager_) {
            PersistentReservation pr;
            pr.peer_id = response.reservation.peer_id;
            pr.expire_time_ns = response.reservation.expire_time * 1000000000ULL;
            pr.voucher = response.reservation.voucher;
            pr.data_limit = response.reservation.limit_data;
            pr.bandwidth_limit = config_.per_connection_bandwidth;
            pr.created_at_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now().time_since_epoch()).count();

            persistence_manager_->SaveReservation(pr);
        }

        NotifyEvent("reserve_created", "Reservation for peer: " + request.peer_id);
    } else {
        stats_.connections_rejected++;
    }

    // TODO: Serialize and return response
    return {};
}

std::vector<uint8_t> CircuitRelayServer::HandleConnect(
    const ConnectRequest& request,
    const net::SocketAddr& from_addr) {

    std::cout << "Received CONNECT (Hop) request from peer: "
              << request.peer_id << std::endl;

    // Verify reservation
    auto reservation = reservation_manager_->Lookup(request.peer_id);
    if (!reservation) {
        stats_.connections_rejected++;
        NotifyEvent("connect_rejected", "No reservation for peer: " + request.peer_id);

        ConnectResponse response;
        response.status = StatusCode::NO_RESERVATION;
        // TODO: Serialize response
        return {};
    }

    // Create connection
    auto conn = CreateConnection(request.peer_id, from_addr);
    if (!conn) {
        stats_.connections_rejected++;
        return {};
    }

    stats_.connections_accepted++;
    NotifyEvent("connected", "Hop connection for peer: " + request.peer_id);

    ConnectResponse response;
    response.status = StatusCode::OK;
    // TODO: Serialize response
    return {};
}

std::vector<uint8_t> CircuitRelayServer::HandleStopConnect(
    const StopConnectRequest& request,
    const net::SocketAddr& from_addr) {

    std::cout << "Received CONNECT (Stop) request from peer: "
              << request.peer_id << std::endl;

    auto response = stop_protocol_->HandleConnect(request);

    if (response.status == StatusCode::OK && response.connection) {
        stats_.connections_accepted++;
        NotifyEvent("connected", "Stop connection for peer: " + request.peer_id);
    } else {
        stats_.connections_rejected++;
    }

    // TODO: Serialize response
    return {};
}

std::shared_ptr<RelayConnection> CircuitRelayServer::CreateConnection(
    const std::string& peer_id,
    const net::SocketAddr& client_addr) {

    auto socket = std::make_unique<net::UDPSocket>();
    if (!socket->IsValid()) {
        return nullptr;
    }

    // Bind to ephemeral port
    net::SocketAddr bind_addr("0.0.0.0", 0);
    if (!socket->Bind(bind_addr)) {
        return nullptr;
    }

    auto conn = ConnectionFactory::CreateForClient(
        std::move(socket), client_addr, peer_id);

    // Store connection
    std::lock_guard<std::mutex> lock(connections_mutex_);

    ActiveConnection active_conn;
    active_conn.connection = conn;
    active_conn.peer_id = peer_id;
    active_conn.client_addr = client_addr;
    active_conn.created_at_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();

    connections_[peer_id] = std::move(active_conn);
    stats_.active_connections++;
    stats_.total_connections++;

    return conn;
}

bool CircuitRelayServer::CreateForwarder(
    std::shared_ptr<RelayConnection> conn_a,
    std::shared_ptr<RelayConnection> conn_b) {

    auto forwarder = std::make_unique<RelayForwarder>(
        conn_a, conn_b, config_.per_connection_bandwidth);

    if (!forwarder->Start()) {
        return false;
    }

    std::lock_guard<std::mutex> lock(forwarders_mutex_);

    ActiveForwarder active;
    active.forwarder = std::move(forwarder);
    active.conn_a_id = conn_a->GetPeerId();
    active.conn_b_id = conn_b->GetPeerId();
    active.created_at_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();

    forwarders_.push_back(std::move(active));
    return true;
}

void CircuitRelayServer::CleanupForwarders() {
    std::lock_guard<std::mutex> lock(forwarders_mutex_);

    auto it = std::remove_if(forwarders_.begin(), forwarders_.end(),
        [](const ActiveForwarder& f) {
            return !f.forwarder->IsActive();
        });

    if (it != forwarders_.end()) {
        size_t removed = std::distance(it, forwarders_.end());
        forwarders_.erase(it, forwarders_.end());
        std::cout << "Cleaned up " << removed << " completed forwarders" << std::endl;
    }
}

void CircuitRelayServer::UpdateStatistics() {
    // Update active connection count
    {
        std::lock_guard<std::mutex> lock(connections_mutex_);
        stats_.active_connections = connections_.size();
    }

    // Update reservation count
    stats_.active_reservations = reservation_manager_->GetCount();

    // Update relayed data from forwarders
    {
        std::lock_guard<std::mutex> lock(forwarders_mutex_);
        for (const auto& f : forwarders_) {
            auto f_stats = f.forwarder->GetStats();
            stats_.bytes_relayed += f_stats.bytes_sent + f_stats.bytes_received;
            stats_.packets_relayed += f_stats.packets_sent + f_stats.packets_received;
        }
    }
}

void CircuitRelayServer::MetricsLoop() {
    while (running_) {
        std::this_thread::sleep_for(
            std::chrono::milliseconds(config_.metrics_interval));

        if (!running_) break;

        CleanupForwarders();
        UpdateStatistics();

        // Log statistics
        std::cout << "=== Circuit Relay Statistics ===" << std::endl;
        std::cout << "Active connections: " << stats_.active_connections << std::endl;
        std::cout << "Active reservations: " << stats_.active_reservations << std::endl;
        std::cout << "Bytes relayed: " << stats_.bytes_relayed << std::endl;
        std::cout << "Packets relayed: " << stats_.packets_relayed << std::endl;
        std::cout << "Total connections: " << stats_.total_connections << std::endl;
        std::cout << "===============================" << std::endl;
    }
}

void CircuitRelayServer::NotifyEvent(const std::string& event, const std::string& detail) {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    if (event_callback_) {
        try {
            event_callback_(event, detail);
        } catch (...) {
            // Ignore callback errors
        }
    }
}

// ============================================================================
// CircuitRelayFactory Implementation
// ============================================================================

std::unique_ptr<CircuitRelayServer> CircuitRelayFactory::CreateDefault() {
    CircuitRelayConfig config;
    return std::make_unique<CircuitRelayServer>(config);
}

std::unique_ptr<CircuitRelayServer> CircuitRelayFactory::Create(
    const CircuitRelayConfig& config) {

    return std::make_unique<CircuitRelayServer>(config);
}

std::unique_ptr<CircuitRelayServer> CircuitRelayFactory::CreateProduction(
    const std::string& public_ip,
    uint16_t port) {

    CircuitRelayConfig config;
    config.host = "0.0.0.0";
    config.port = port;
    config.public_ip = public_ip;
    config.max_reservations = 10000;
    config.bandwidth_limit = 104857600;  // 100 MB/sec
    config.per_connection_bandwidth = 10485760;  // 10 MB/sec
    config.enable_persistence = true;
    config.enable_metrics = true;

    return std::make_unique<CircuitRelayServer>(config);
}

} // namespace v2
} // namespace relay
} // namespace p2p
