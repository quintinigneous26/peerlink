#include "servers/did/did_server.hpp"
#include <iostream>
#include <csignal>
#include <cstdlib>

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

    const char* jwt_secret = std::getenv("JWT_SECRET");
    if (!jwt_secret || std::string(jwt_secret).empty()) {
        std::cerr << "FATAL: JWT_SECRET environment variable is not set." << std::endl;
        std::cerr << "Set it before starting: export JWT_SECRET=<your-secret>" << std::endl;
        return 1;
    }

    p2p::did::DIDServerConfig config;
    config.host = "0.0.0.0";
    config.port = 8081;
    config.redis_host = "127.0.0.1";
    config.redis_port = 6379;
    config.jwt_secret = jwt_secret;

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
