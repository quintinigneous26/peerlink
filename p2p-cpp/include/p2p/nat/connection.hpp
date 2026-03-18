#pragma once

#include <memory>
#include <vector>
#include <string>
#include <atomic>
#include <mutex>
#include "p2p/net/socket.hpp"

namespace p2p {
namespace nat {

/**
 * Base connection class for NAT traversal results
 */
class Connection {
public:
    virtual ~Connection() = default;

    /**
     * Get connection type
     */
    virtual std::string GetType() const = 0;

    /**
     * Check if connection is active
     */
    virtual bool IsConnected() const = 0;

    /**
     * Send data through the connection
     */
    virtual ssize_t Send(const std::vector<uint8_t>& data) = 0;

    /**
     * Receive data from the connection
     */
    virtual ssize_t Recv(std::vector<uint8_t>& buffer, size_t max_size = 65536) = 0;

    /**
     * Close the connection
     */
    virtual void Close() = 0;

    /**
     * Get local address
     */
    virtual std::optional<net::SocketAddr> GetLocalAddr() const = 0;

    /**
     * Get remote address
     */
    virtual std::optional<net::SocketAddr> GetRemoteAddr() const = 0;
};

/**
 * UDP Connection wrapper
 * Wraps UDPSocket with remote address for point-to-point communication
 */
class UDPConnection : public Connection {
public:
    UDPConnection(net::UDPSocket socket, const net::SocketAddr& remote_addr);
    ~UDPConnection() override;

    std::string GetType() const override { return "udp"; }
    bool IsConnected() const override { return connected_.load(); }
    ssize_t Send(const std::vector<uint8_t>& data) override;
    ssize_t Recv(std::vector<uint8_t>& buffer, size_t max_size = 65536) override;
    void Close() override;
    std::optional<net::SocketAddr> GetLocalAddr() const override;
    std::optional<net::SocketAddr> GetRemoteAddr() const override;

    /**
     * Get underlying socket
     */
    net::UDPSocket& GetSocket() { return socket_; }

    /**
     * Update remote address (for NAT traversal after punch)
     */
    void UpdateRemoteAddr(const net::SocketAddr& addr);

private:
    net::UDPSocket socket_;
    net::SocketAddr remote_addr_;
    std::atomic<bool> connected_;
    mutable std::mutex mutex_;
};

/**
 * TCP Connection wrapper
 * Wraps connected TCPSocket for stream communication
 */
class TCPConnection : public Connection {
public:
    explicit TCPConnection(net::TCPSocket socket);
    ~TCPConnection() override;

    std::string GetType() const override { return "tcp"; }
    bool IsConnected() const override;
    ssize_t Send(const std::vector<uint8_t>& data) override;
    ssize_t Recv(std::vector<uint8_t>& buffer, size_t max_size = 65536) override;
    void Close() override;
    std::optional<net::SocketAddr> GetLocalAddr() const override;
    std::optional<net::SocketAddr> GetRemoteAddr() const override;

    /**
     * Get underlying socket
     */
    net::TCPSocket& GetSocket() { return socket_; }

private:
    net::TCPSocket socket_;
    mutable std::mutex mutex_;
};

} // namespace nat
} // namespace p2p
