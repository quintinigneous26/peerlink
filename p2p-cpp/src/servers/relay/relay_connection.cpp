#include "p2p/servers/relay/relay_connection.hpp"
#include <chrono>

namespace p2p {
namespace relay {
namespace v2 {

// ============================================================================
// ActiveRelayConnection Implementation
// ============================================================================

ActiveRelayConnection::ActiveRelayConnection(
    std::unique_ptr<net::UDPSocket> client_socket,
    const net::SocketAddr& client_addr,
    const std::string& peer_id)
    : peer_id_(peer_id),
      client_socket_(std::move(client_socket)),
      client_addr_(client_addr),
      open_(true) {

    NotifyEvent("created", "Connection established for peer: " + peer_id);
}

ActiveRelayConnection::ActiveRelayConnection(const std::string& peer_id)
    : peer_id_(peer_id),
      open_(true) {

    NotifyEvent("created", "Connection created for peer: " + peer_id);
}

ActiveRelayConnection::~ActiveRelayConnection() {
    Close();
}

bool ActiveRelayConnection::Send(const std::vector<uint8_t>& data) {
    if (!open_.load() || data.empty()) {
        errors_.fetch_add(1);
        return false;
    }

    try {
        if (client_socket_ && client_socket_->IsValid()) {
            // Send to client
            ssize_t sent = client_socket_->SendTo(data, client_addr_);
            if (sent > 0) {
                bytes_sent_.fetch_add(sent);
                packets_sent_.fetch_add(1);
                return true;
            }
        }

        // If we have a relay address, try to send there
        if (relay_addr_) {
            // This would be handled by the relay forwarder
            // For now, just queue the data
            std::lock_guard<std::mutex> lock(queue_mutex_);
            receive_queue_.push_back(data);  // Echo back for testing
            queue_cv_.notify_one();
            bytes_sent_.fetch_add(data.size());
            packets_sent_.fetch_add(1);
            return true;
        }

        errors_.fetch_add(1);
        return false;
    } catch (const std::exception& e) {
        NotifyEvent("error", std::string("Send failed: ") + e.what());
        errors_.fetch_add(1);
        return false;
    }
}

std::vector<uint8_t> ActiveRelayConnection::Receive(size_t max_size, int timeout_ms) {
    std::unique_lock<std::mutex> lock(queue_mutex_);

    // Wait for data with timeout
    if (timeout_ms > 0) {
        queue_cv_.wait_for(lock, std::chrono::milliseconds(timeout_ms), [this]() {
            return !receive_queue_.empty() || !open_.load();
        });
    } else {
        queue_cv_.wait(lock, [this]() {
            return !receive_queue_.empty() || !open_.load();
        });
    }

    if (receive_queue_.empty() || !open_.load()) {
        return {};
    }

    auto data = std::move(receive_queue_.front());
    receive_queue_.erase(receive_queue_.begin());

    // Truncate if needed
    if (data.size() > max_size) {
        data.resize(max_size);
    }

    bytes_received_.fetch_add(data.size());
    packets_received_.fetch_add(1);

    return data;
}

void ActiveRelayConnection::Close() {
    if (!open_.exchange(false)) {
        return;  // Already closed
    }

    NotifyEvent("closed", "Connection closed for peer: " + peer_id_);

    // Close socket
    if (client_socket_) {
        client_socket_->Close();
    }

    // Wake up any waiting receivers
    queue_cv_.notify_all();
}

ActiveRelayConnection::Stats ActiveRelayConnection::GetStats() const {
    return {
        bytes_sent_.load(),
        bytes_received_.load(),
        packets_sent_.load(),
        packets_received_.load(),
        errors_.load()
    };
}

void ActiveRelayConnection::ResetStats() {
    bytes_sent_.store(0);
    bytes_received_.store(0);
    packets_sent_.store(0);
    packets_received_.store(0);
    errors_.store(0);
}

std::optional<net::SocketAddr> ActiveRelayConnection::GetClientAddr() const {
    if (client_socket_ && client_socket_->IsValid()) {
        return client_socket_->GetLocalAddr();
    }
    return std::nullopt;
}

void ActiveRelayConnection::SetRelayAddr(const net::SocketAddr& addr) {
    relay_addr_ = addr;
    NotifyEvent("relay_set", "Relay address set: " + addr.ToString());
}

std::optional<net::SocketAddr> ActiveRelayConnection::GetRelayAddr() const {
    return relay_addr_;
}

void ActiveRelayConnection::NotifyEvent(const std::string& event, const std::string& detail) {
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
// ConnectionFactory Implementation
// ============================================================================

std::shared_ptr<ActiveRelayConnection> ConnectionFactory::CreateForClient(
    std::unique_ptr<net::UDPSocket> socket,
    const net::SocketAddr& client_addr,
    const std::string& peer_id) {

    return std::make_shared<ActiveRelayConnection>(
        std::move(socket), client_addr, peer_id);
}

std::shared_ptr<ActiveRelayConnection> ConnectionFactory::CreateForRelay(
    const std::string& peer_id,
    const net::SocketAddr& relay_addr) {

    auto conn = std::make_shared<ActiveRelayConnection>(peer_id);
    conn->SetRelayAddr(relay_addr);
    return conn;
}

} // namespace v2
} // namespace relay
} // namespace p2p
