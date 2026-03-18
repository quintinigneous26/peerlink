#pragma once

#include <memory>
#include <string>
#include <vector>
#include <functional>
#include <atomic>
#include <mutex>
#include <condition_variable>
#include "p2p/net/socket.hpp"

namespace p2p {
namespace relay {
namespace v2 {

/**
 * Connection events callback
 */
using ConnectionEventCallback = std::function<void(const std::string& event, const std::string& detail)>;

/**
 * Base Relay Connection interface
 * Provides unified interface for different connection types
 */
class RelayConnection {
public:
    virtual ~RelayConnection() = default;

    /**
     * Get connection type
     */
    virtual std::string GetType() const = 0;

    /**
     * Get peer ID
     */
    virtual std::string GetPeerId() const = 0;

    /**
     * Check if connection is open
     */
    virtual bool IsOpen() const = 0;

    /**
     * Send data through connection
     * @return true if data was queued for sending
     */
    virtual bool Send(const std::vector<uint8_t>& data) = 0;

    /**
     * Receive data from connection (blocking with timeout)
     * @param max_size Maximum bytes to receive
     * @param timeout_ms Timeout in milliseconds (0 = no timeout)
     * @return Received data, empty on error/timeout
     */
    virtual std::vector<uint8_t> Receive(size_t max_size = 65536, int timeout_ms = 0) = 0;

    /**
     * Close connection
     */
    virtual void Close() = 0;

    /**
     * Set event callback
     */
    virtual void SetEventCallback(ConnectionEventCallback callback) = 0;

    /**
     * Get statistics
     */
    struct Stats {
        uint64_t bytes_sent{0};
        uint64_t bytes_received{0};
        uint64_t packets_sent{0};
        uint64_t packets_received{0};
        uint64_t errors{0};
    };
    virtual Stats GetStats() const = 0;

    /**
     * Reset statistics
     */
    virtual void ResetStats() = 0;
};

/**
 * Active Connection implementation
 * Wraps actual network sockets and provides queue-based communication
 */
class ActiveRelayConnection : public RelayConnection {
public:
    /**
     * Create connection with existing sockets
     */
    ActiveRelayConnection(
        std::unique_ptr<net::UDPSocket> client_socket,
        const net::SocketAddr& client_addr,
        const std::string& peer_id);

    /**
     * Create connection with just peer ID (for accepted connections)
     */
    explicit ActiveRelayConnection(const std::string& peer_id);

    ~ActiveRelayConnection() override;

    std::string GetType() const override { return "active"; }
    std::string GetPeerId() const override { return peer_id_; }
    bool IsOpen() const override { return open_.load(); }

    bool Send(const std::vector<uint8_t>& data) override;
    std::vector<uint8_t> Receive(size_t max_size = 65536, int timeout_ms = 0) override;
    void Close() override;

    void SetEventCallback(ConnectionEventCallback callback) override {
        std::lock_guard<std::mutex> lock(callback_mutex_);
        event_callback_ = std::move(callback);
    }

    Stats GetStats() const override;
    void ResetStats() override;

    /**
     * Get client address
     */
    std::optional<net::SocketAddr> GetClientAddr() const;

    /**
     * Set remote relay address (for relayed connections)
     */
    void SetRelayAddr(const net::SocketAddr& addr);

    /**
     * Get relay address
     */
    std::optional<net::SocketAddr> GetRelayAddr() const;

private:
    void NotifyEvent(const std::string& event, const std::string& detail);

    std::string peer_id_;
    std::unique_ptr<net::UDPSocket> client_socket_;
    net::SocketAddr client_addr_;
    std::optional<net::SocketAddr> relay_addr_;

    std::atomic<bool> open_;

    // Receive queue
    std::vector<std::vector<uint8_t>> receive_queue_;
    mutable std::mutex queue_mutex_;
    std::condition_variable queue_cv_;

    // Event callback
    ConnectionEventCallback event_callback_;
    mutable std::mutex callback_mutex_;

    // Statistics
    std::atomic<uint64_t> bytes_sent_{0};
    std::atomic<uint64_t> bytes_received_{0};
    std::atomic<uint64_t> packets_sent_{0};
    std::atomic<uint64_t> packets_received_{0};
    std::atomic<uint64_t> errors_{0};
};

/**
 * Connection Factory
 * Creates connections for different scenarios
 */
class ConnectionFactory {
public:
    /**
     * Create connection for incoming client
     */
    static std::shared_ptr<ActiveRelayConnection> CreateForClient(
        std::unique_ptr<net::UDPSocket> socket,
        const net::SocketAddr& client_addr,
        const std::string& peer_id);

    /**
     * Create connection for relayed peer
     */
    static std::shared_ptr<ActiveRelayConnection> CreateForRelay(
        const std::string& peer_id,
        const net::SocketAddr& relay_addr);
};

} // namespace v2
} // namespace relay
} // namespace p2p
