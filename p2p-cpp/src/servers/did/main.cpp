#include "servers/did/did_server.hpp"
#include <iostream>
#include <csignal>

std::unique_ptr<p2p::did::DIDServer> g_server;

void SignalHandler(int signal) {
    if (g_server) {
        std::cout << "\nShutting down DID server..." << std::endl;
        g_server->Stop();
    }
}

int main(int argc, char* argv[]) {
    std::signal(SIGINT, SignalHandler);
    std::signal(SIGTERM, SignalHandler);

    p2p::did::DIDServerConfig config;
    config.host = "0.0.0.0";
    config.port = 8081;
    config.redis_host = "127.0.0.1";
    config.redis_port = 6379;
    config.jwt_secret = "your_jwt_secret_here";

    try {
        g_server = std::make_unique<p2p::did::DIDServer>(config);
        std::cout << "Starting DID Server..." << std::endl;
        g_server->Run();
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
