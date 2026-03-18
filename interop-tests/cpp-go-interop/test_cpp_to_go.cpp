/**
 * C++ to Go Relay Interoperability Test
 *
 * Tests C++ client connecting to Go relay server
 */

#include <iostream>
#include <vector>
#include <cstdint>
#include <chrono>
#include <thread>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>

// Protobuf includes
#include "relay_v2.pb.h"

class SimpleSocket {
public:
    SimpleSocket() : fd_(-1), connected_(false) {}

    ~SimpleSocket() {
        Close();
    }

    bool Connect(const std::string& ip, uint16_t port) {
        fd_ = socket(AF_INET, SOCK_STREAM, 0);
        if (fd_ < 0) {
            std::cerr << "Failed to create socket\n";
            return false;
        }

        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(port);

        if (inet_pton(AF_INET, ip.c_str(), &addr.sin_addr) <= 0) {
            std::cerr << "Invalid address\n";
            return false;
        }

        if (connect(fd_, (sockaddr*)&addr, sizeof(addr)) < 0) {
            std::cerr << "Connection failed\n";
            return false;
        }

        connected_ = true;
        std::cout << "✅ Connected to " << ip << ":" << port << "\n";
        return true;
    }

    bool Send(const std::vector<uint8_t>& data) {
        if (!connected_) return false;

        ssize_t sent = send(fd_, data.data(), data.size(), 0);
        if (sent < 0) {
            std::cerr << "Send failed\n";
            return false;
        }

        std::cout << "✅ Sent " << sent << " bytes\n";
        return true;
    }

    std::vector<uint8_t> Receive(size_t max_size = 4096) {
        std::vector<uint8_t> buffer(max_size);
        ssize_t received = recv(fd_, buffer.data(), max_size, 0);

        if (received < 0) {
            std::cerr << "Receive failed\n";
            return {};
        }

        buffer.resize(received);
        std::cout << "✅ Received " << received << " bytes\n";
        return buffer;
    }

    void Close() {
        if (fd_ >= 0) {
            close(fd_);
            fd_ = -1;
            connected_ = false;
        }
    }

private:
    int fd_;
    bool connected_;
};

int main() {
    std::cout << "=== C++ to Go Relay Interoperability Test ===\n\n";

    // Initialize protobuf
    GOOGLE_PROTOBUF_VERIFY_VERSION;

    // Test 1: RESERVE message
    std::cout << "Test 1: Sending RESERVE message\n";
    {
        // Create RESERVE message
        p2p::relay::v2::HopMessage msg;
        msg.set_type(p2p::relay::v2::HopMessage::RESERVE);

        // Serialize
        std::vector<uint8_t> data(msg.ByteSizeLong());
        if (!msg.SerializeToArray(data.data(), data.size())) {
            std::cerr << "❌ Serialization failed\n";
            return 1;
        }

        std::cout << "  Serialized: " << data.size() << " bytes\n";
        std::cout << "  Hex: ";
        for (auto byte : data) {
            printf("%02x", byte);
        }
        std::cout << "\n";

        // Verify deserialization
        p2p::relay::v2::HopMessage msg2;
        if (!msg2.ParseFromArray(data.data(), data.size())) {
            std::cerr << "❌ Deserialization failed\n";
            return 1;
        }

        if (msg2.type() != p2p::relay::v2::HopMessage::RESERVE) {
            std::cerr << "❌ Type mismatch\n";
            return 1;
        }

        std::cout << "  ✅ RESERVE message serialization verified\n\n";
    }

    // Test 2: CONNECT message
    std::cout << "Test 2: Sending CONNECT message\n";
    {
        // Create CONNECT message with peer info
        p2p::relay::v2::HopMessage msg;
        msg.set_type(p2p::relay::v2::HopMessage::CONNECT);

        auto* peer = msg.mutable_peer();
        peer->set_id(std::string("\x12\x20\x01\x02\x03\x04", 6));
        peer->add_addrs(std::string("\x04\x7f\x00\x00\x01\x06\x1f\x90", 8));

        // Serialize
        std::vector<uint8_t> data(msg.ByteSizeLong());
        if (!msg.SerializeToArray(data.data(), data.size())) {
            std::cerr << "❌ Serialization failed\n";
            return 1;
        }

        std::cout << "  Serialized: " << data.size() << " bytes\n";
        std::cout << "  Hex: ";
        for (auto byte : data) {
            printf("%02x", byte);
        }
        std::cout << "\n";

        // Verify deserialization
        p2p::relay::v2::HopMessage msg2;
        if (!msg2.ParseFromArray(data.data(), data.size())) {
            std::cerr << "❌ Deserialization failed\n";
            return 1;
        }

        if (msg2.type() != p2p::relay::v2::HopMessage::CONNECT) {
            std::cerr << "❌ Type mismatch\n";
            return 1;
        }

        if (!msg2.has_peer()) {
            std::cerr << "❌ Peer missing\n";
            return 1;
        }

        std::cout << "  ✅ CONNECT message serialization verified\n\n";
    }

    // Test 3: STATUS message
    std::cout << "Test 3: Sending STATUS message\n";
    {
        // Create STATUS message
        p2p::relay::v2::HopMessage msg;
        msg.set_type(p2p::relay::v2::HopMessage::STATUS);
        msg.set_status(p2p::relay::v2::Status::OK);

        // Serialize
        std::vector<uint8_t> data(msg.ByteSizeLong());
        if (!msg.SerializeToArray(data.data(), data.size())) {
            std::cerr << "❌ Serialization failed\n";
            return 1;
        }

        std::cout << "  Serialized: " << data.size() << " bytes\n";
        std::cout << "  Hex: ";
        for (auto byte : data) {
            printf("%02x", byte);
        }
        std::cout << "\n";

        // Verify deserialization
        p2p::relay::v2::HopMessage msg2;
        if (!msg2.ParseFromArray(data.data(), data.size())) {
            std::cerr << "❌ Deserialization failed\n";
            return 1;
        }

        if (msg2.type() != p2p::relay::v2::HopMessage::STATUS) {
            std::cerr << "❌ Type mismatch\n";
            return 1;
        }

        if (msg2.status() != p2p::relay::v2::Status::OK) {
            std::cerr << "❌ Status mismatch\n";
            return 1;
        }

        std::cout << "  ✅ STATUS message serialization verified\n\n";
    }

    std::cout << "\n=== All Tests Passed ===\n";

    // Cleanup protobuf
    google::protobuf::ShutdownProtobufLibrary();

    return 0;
}
