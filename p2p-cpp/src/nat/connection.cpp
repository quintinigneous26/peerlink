#include "p2p/nat/connection.hpp"
#include <stdexcept>

namespace p2p {
namespace nat {

// ============================================================================
// UDPConnection Implementation
// ============================================================================

UDPConnection::UDPConnection(net::UDPSocket socket, const net::SocketAddr& remote_addr)
    : socket_(std::move(socket)),
      remote_addr_(remote_addr),
      connected_(socket_.IsValid()) {
}

UDPConnection::~UDPConnection() {
    Close();
}

ssize_t UDPConnection::Send(const std::vector<uint8_t>& data) {
    if (!connected_.load()) {
        return -1;
    }

    std::lock_guard<std::mutex> lock(mutex_);
    return socket_.SendTo(data, remote_addr_);
}

ssize_t UDPConnection::Recv(std::vector<uint8_t>& buffer, size_t max_size) {
    if (!connected_.load()) {
        return -1;
    }

    std::lock_guard<std::mutex> lock(mutex_);
    net::SocketAddr from;
    ssize_t n = socket_.RecvFrom(buffer, from);

    // For UDP, we accept packets from the remote address
    // or update the remote address if this is a new peer (after NAT punch)
    if (n > 0) {
        // Accept packet from expected remote or update on first receive
        // (NAT may have mapped to different external port)
        connected_.store(true);
    }

    return n;
}

void UDPConnection::Close() {
    connected_.store(false);
    std::lock_guard<std::mutex> lock(mutex_);
    socket_.Close();
}

std::optional<net::SocketAddr> UDPConnection::GetLocalAddr() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return socket_.GetLocalAddr();
}

std::optional<net::SocketAddr> UDPConnection::GetRemoteAddr() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return remote_addr_;
}

void UDPConnection::UpdateRemoteAddr(const net::SocketAddr& addr) {
    std::lock_guard<std::mutex> lock(mutex_);
    remote_addr_ = addr;
}

// ============================================================================
// TCPConnection Implementation
// ============================================================================

TCPConnection::TCPConnection(net::TCPSocket socket)
    : socket_(std::move(socket)) {
}

TCPConnection::~TCPConnection() {
    Close();
}

bool TCPConnection::IsConnected() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return socket_.IsConnected();
}

ssize_t TCPConnection::Send(const std::vector<uint8_t>& data) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!socket_.IsConnected()) {
        return -1;
    }
    return socket_.Send(data);
}

ssize_t TCPConnection::Recv(std::vector<uint8_t>& buffer, size_t max_size) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (!socket_.IsConnected()) {
        return -1;
    }
    return socket_.Recv(buffer, max_size);
}

void TCPConnection::Close() {
    std::lock_guard<std::mutex> lock(mutex_);
    socket_.Close();
}

std::optional<net::SocketAddr> TCPConnection::GetLocalAddr() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return socket_.GetLocalAddr();
}

std::optional<net::SocketAddr> TCPConnection::GetRemoteAddr() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return socket_.GetPeerAddr();
}

} // namespace nat
} // namespace p2p
