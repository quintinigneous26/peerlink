#pragma once

#include <boost/asio.hpp>
#include <memory>
#include <string>

namespace p2p {
namespace did {

namespace asio = boost::asio;

struct DIDServerConfig {
    std::string host = "0.0.0.0";
    uint16_t port = 8081;
    std::string redis_host = "127.0.0.1";
    uint16_t redis_port = 6379;
    std::string jwt_secret = "default_secret";
    int max_connections = 1000;
};

class DIDServer {
public:
    explicit DIDServer(const DIDServerConfig& config);
    ~DIDServer();

    void Run();
    void Stop();

private:
    DIDServerConfig config_;
    asio::io_context io_context_;
    bool running_;
};

} // namespace did
} // namespace p2p
