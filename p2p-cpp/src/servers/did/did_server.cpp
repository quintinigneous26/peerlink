#include "servers/did/did_server.hpp"
#include <iostream>

namespace p2p {
namespace did {

DIDServer::DIDServer(const DIDServerConfig& config)
    : config_(config), running_(false) {
}

DIDServer::~DIDServer() {
    Stop();
}

void DIDServer::Run() {
    running_ = true;
    std::cout << "DID Server running on " << config_.host << ":" << config_.port << std::endl;
    io_context_.run();
}

void DIDServer::Stop() {
    if (running_) {
        running_ = false;
        io_context_.stop();
    }
}

} // namespace did
} // namespace p2p
