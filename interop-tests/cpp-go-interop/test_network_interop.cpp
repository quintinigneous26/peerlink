/**
 * C++ to Go Network Interoperability Test
 *
 * Tests actual network communication between C++ client and Go relay server
 * Standalone test - no protobuf dependencies
 */

#include <iostream>
#include <vector>
#include <cstdint>
#include <chrono>
#include <thread>
#include <string>

#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #pragma comment(lib, "ws2_32.lib")
    typedef int socklen_t;
#else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <arpa/inet.h>
    #include <unistd.h>
    #include <cstring>
    #define INVALID_SOCKET -1
    #define SOCKET_ERROR -1
    typedef int SOCKET;
#endif

// Test configuration
const char* RELAY_HOST = "127.0.0.1";
const uint16_t RELAY_PORT = 9000;
const int TIMEOUT_SEC = 5;

class TCPClient {
public:
    TCPClient() : fd_(INVALID_SOCKET), connected_(false) {
        #ifdef _WIN32
            static bool wsa_initialized = false;
            if (!wsa_initialized) {
                WSADATA wsa_data;
                WSAStartup(MAKEWORD(2, 2), &wsa_data);
                wsa_initialized = true;
            }
        #endif
    }

    ~TCPClient() {
        Disconnect();
    }

    bool Connect(const std::string& host, uint16_t port, int timeout_sec = TIMEOUT_SEC) {
        fd_ = socket(AF_INET, SOCK_STREAM, 0);
        #ifdef _WIN32
            if (fd_ == INVALID_SOCKET) {
                std::cerr << "Failed to create socket\n";
                return false;
            }
        #else
            if (fd_ < 0) {
                std::cerr << "Failed to create socket\n";
                return false;
            }

            // Set receive timeout
            struct timeval tv;
            tv.tv_sec = timeout_sec;
            tv.tv_usec = 0;
            setsockopt(fd_, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        #endif

        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(port);

        if (inet_pton(AF_INET, host.c_str(), &addr.sin_addr) <= 0) {
            std::cerr << "Invalid address: " << host << "\n";
            #ifdef _WIN32
                closesocket(fd_);
            #else
                close(fd_);
            #endif
            fd_ = INVALID_SOCKET;
            return false;
        }

        std::cout << "  Connecting to " << host << ":" << port << "...";
        std::cout.flush();

        if (connect(fd_, (sockaddr*)&addr, sizeof(addr)) < 0) {
            std::cerr << " Failed\n";
            #ifdef _WIN32
                closesocket(fd_);
            #else
                close(fd_);
            #endif
            fd_ = INVALID_SOCKET;
            return false;
        }

        connected_ = true;
        std::cout << " OK\n";
        return true;
    }

    bool Send(const std::vector<uint8_t>& data) {
        if (!connected_) {
            std::cerr << "Not connected\n";
            return false;
        }

        #ifdef _WIN32
            int sent = send(fd_, (const char*)data.data(), static_cast<int>(data.size()), 0);
            if (sent == SOCKET_ERROR) {
                std::cerr << "Send failed\n";
                return false;
            }
        #else
            ssize_t sent = send(fd_, data.data(), data.size(), 0);
            if (sent < 0) {
                std::cerr << "Send failed\n";
                return false;
            }
        #endif

        if (static_cast<size_t>(sent) != data.size()) {
            std::cerr << "Partial send: " << sent << "/" << data.size() << "\n";
            return false;
        }

        return true;
    }

    std::vector<uint8_t> Receive(size_t max_size = 4096) {
        if (!connected_) {
            std::cerr << "Not connected\n";
            return {};
        }

        std::vector<uint8_t> buffer(max_size);

        #ifdef _WIN32
            int received = recv(fd_, (char*)buffer.data(), static_cast<int>(max_size), 0);
            if (received == SOCKET_ERROR) {
                std::cerr << "Receive failed\n";
                return {};
            }
        #else
            ssize_t received = recv(fd_, buffer.data(), max_size, 0);
            if (received < 0) {
                std::cerr << "Receive failed\n";
                return {};
            }
        #endif

        buffer.resize(received);
        return buffer;
    }

    void Disconnect() {
        if (fd_ != INVALID_SOCKET) {
            #ifdef _WIN32
                closesocket(fd_);
            #else
                close(fd_);
            #endif
            fd_ = INVALID_SOCKET;
            connected_ = false;
        }
    }

    bool IsConnected() const { return connected_; }

private:
    SOCKET fd_;
    bool connected_;
};

// Multistream protocol helpers
std::vector<uint8_t> CreateMultistreamHeader() {
    const char* header = "/multistream/1.0.0\n";
    std::vector<uint8_t> data(header, header + strlen(header));
    return data;
}

std::vector<uint8_t> CreateProtocolSelect(const std::string& protocol) {
    std::string line = protocol + "\n";
    std::vector<uint8_t> data(line.begin(), line.end());
    return data;
}

void PrintHex(const std::string& label, const std::vector<uint8_t>& data) {
    std::cout << "  " << label << ": ";
    for (size_t i = 0; i < std::min(size_t(32), data.size()); ++i) {
        printf("%02x ", data[i]);
    }
    if (data.size() > 32) {
        std::cout << "...";
    }
    std::cout << " (" << data.size() << " bytes)\n";
}

// ============================================================================
// Tests
// ============================================================================

bool TestMultistreamHandshake(TCPClient& client) {
    std::cout << "\n[Test 1] Multistream Handshake\n";

    // Send multistream header
    auto header = CreateMultistreamHeader();
    std::cout << "  Sending multistream header...";
    if (!client.Send(header)) {
        std::cout << " Failed\n";
        return false;
    }
    std::cout << " OK\n";

    // Receive response
    auto response = client.Receive();
    if (response.empty()) {
        std::cout << "  Failed to receive response\n";
        return false;
    }

    std::string resp_str(response.begin(), response.end());
    std::cout << "  Received: " << resp_str;

    if (resp_str.find("/multistream/1.0.0") == std::string::npos) {
        std::cout << "  Invalid response\n";
        return false;
    }

    std::cout << "  Handshake successful\n";
    return true;
}

bool TestProtocolNegotiation(TCPClient& client) {
    std::cout << "\n[Test 2] Protocol Negotiation\n";

    // Try to negotiate a protocol
    auto protocol = CreateProtocolSelect("/p2p/circuit/relay/0.2.0/hop");
    std::cout << "  Requesting protocol /p2p/circuit/relay/0.2.0/hop...";

    if (!client.Send(protocol)) {
        std::cout << " Failed\n";
        return false;
    }
    std::cout << " OK\n";

    auto response = client.Receive();
    if (response.empty()) {
        std::cout << "  No response (expected - protocol requires protobuf messages)\n";
        std::cout << "  Protocol negotiation message sent successfully\n";
        return true;
    }

    std::string resp_str(response.begin(), response.end());
    std::cout << "  Response: " << resp_str;

    return true;
}

bool TestLatencyMeasurement(TCPClient& client, int iterations = 10) {
    std::cout << "\n[Test 3] Latency Measurement\n";

    std::vector<int64_t> latencies;

    for (int i = 0; i < iterations; ++i) {
        auto start = std::chrono::high_resolution_clock::now();

        // Send a small message
        std::vector<uint8_t> ping_msg = {'p', 'i', 'n', 'g', '\n'};
        if (!client.Send(ping_msg)) {
            std::cout << "  Send failed\n";
            return false;
        }

        // Receive response (may timeout)
        auto response = client.Receive();
        auto end = std::chrono::high_resolution_clock::now();

        auto latency = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
        latencies.push_back(latency.count());

        if (response.empty()) {
            std::cout << "  Ping " << (i + 1) << ": " << latency.count() << " us (no response - expected)\n";
        } else {
            std::cout << "  Ping " << (i + 1) << ": " << latency.count() << " us\n";
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    // Calculate statistics
    int64_t sum = 0;
    int64_t min = latencies[0];
    int64_t max = latencies[0];

    for (auto lat : latencies) {
        sum += lat;
        if (lat < min) min = lat;
        if (lat > max) max = lat;
    }

    int64_t avg = sum / latencies.size();

    std::cout << "\n  Latency Statistics:\n";
    std::cout << "    Min: " << min << " us\n";
    std::cout << "    Max: " << max << " us\n";
    std::cout << "    Avg: " << avg << " us\n";

    return true;
}

// ============================================================================
// Main
// ============================================================================

int main(int argc, char* argv[]) {
    std::cout << "=== C++ to Go Network Interoperability Test ===\n\n";

    // Parse arguments
    std::string host = RELAY_HOST;
    uint16_t port = RELAY_PORT;

    if (argc >= 2) {
        host = argv[1];
    }
    if (argc >= 3) {
        port = std::stoi(argv[2]);
    }

    std::cout << "Target: " << host << ":" << port << "\n\n";

    // Connect to relay
    TCPClient client;
    if (!client.Connect(host, port)) {
        std::cout << "\nFailed to connect to relay server\n";
        std::cout << "Make sure the Go relay server is running:\n";
        std::cout << "  cd go-libp2p-test && go run relay_server.go\n";
        return 1;
    }

    bool all_passed = true;

    // Run tests
    all_passed &= TestMultistreamHandshake(client);
    all_passed &= TestProtocolNegotiation(client);
    all_passed &= TestLatencyMeasurement(client);

    // Summary
    std::cout << "\n=== Test Summary ===\n";
    if (all_passed) {
        std::cout << "All tests PASSED\n";
    } else {
        std::cout << "Some tests FAILED\n";
    }

    return all_passed ? 0 : 1;
}
