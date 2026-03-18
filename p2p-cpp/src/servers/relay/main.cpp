/**
 * @file main.cpp
 * @brief Relay Server Entry Point
 */

#include "p2p/servers/relay/relay_server.hpp"
#include <iostream>
#include <csignal>
#include <atomic>

using namespace p2p::relay;

std::atomic<bool> g_running{true};
RelayServer* g_server = nullptr;

void signal_handler(int signal) {
    std::cout << "\nReceived signal " << signal << ", shutting down..." << std::endl;
    g_running = false;
    if (g_server) {
        g_server->Stop();
    }
}

void print_usage(const char* program_name) {
    std::cout << "Usage: " << program_name << " [OPTIONS]\n"
              << "\nOptions:\n"
              << "  --host HOST          Host to bind to (default: 0.0.0.0)\n"
              << "  --port PORT          Control port (default: 9001)\n"
              << "  --public-ip IP       Public IP address (default: 127.0.0.1)\n"
              << "  --min-port PORT      Minimum relay port (default: 50000)\n"
              << "  --max-port PORT      Maximum relay port (default: 50100)\n"
              << "  --lifetime SECONDS   Default allocation lifetime (default: 600)\n"
              << "  --max-allocs NUM     Maximum concurrent allocations (default: 1000)\n"
              << "  --help               Show this help message\n"
              << std::endl;
}

int main(int argc, char* argv[]) {
    // Parse command line arguments
    RelayServerConfig config;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "--help" || arg == "-h") {
            print_usage(argv[0]);
            return 0;
        } else if (arg == "--host" && i + 1 < argc) {
            config.host = argv[++i];
        } else if (arg == "--port" && i + 1 < argc) {
            config.port = static_cast<uint16_t>(std::stoi(argv[++i]));
        } else if (arg == "--public-ip" && i + 1 < argc) {
            config.public_ip = argv[++i];
        } else if (arg == "--min-port" && i + 1 < argc) {
            config.min_port = static_cast<uint16_t>(std::stoi(argv[++i]));
        } else if (arg == "--max-port" && i + 1 < argc) {
            config.max_port = static_cast<uint16_t>(std::stoi(argv[++i]));
        } else if (arg == "--lifetime" && i + 1 < argc) {
            config.default_lifetime = static_cast<uint32_t>(std::stoi(argv[++i]));
        } else if (arg == "--max-allocs" && i + 1 < argc) {
            config.max_allocations = static_cast<size_t>(std::stoi(argv[++i]));
        } else {
            std::cerr << "Unknown option: " << arg << std::endl;
            print_usage(argv[0]);
            return 1;
        }
    }

    // Setup signal handlers
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    try {
        // Create and start server
        std::cout << "Starting Relay/TURN Server..." << std::endl;
        std::cout << "Configuration:" << std::endl;
        std::cout << "  Host: " << config.host << std::endl;
        std::cout << "  Port: " << config.port << std::endl;
        std::cout << "  Public IP: " << config.public_ip << std::endl;
        std::cout << "  Port Range: " << config.min_port << "-" << config.max_port << std::endl;
        std::cout << "  Default Lifetime: " << config.default_lifetime << "s" << std::endl;
        std::cout << "  Max Allocations: " << config.max_allocations << std::endl;

        RelayServer server(config);
        g_server = &server;

        server.Start();

        // Main loop - print statistics periodically
        while (g_running) {
            std::this_thread::sleep_for(std::chrono::seconds(30));

            if (g_running) {
                auto stats = server.GetStats();
                std::cout << "\n=== Server Statistics ===" << std::endl;
                std::cout << "Allocations: " << stats.allocations.active_allocations
                          << "/" << stats.allocations.total_allocations
                          << " (max: " << stats.allocations.max_allocations << ")" << std::endl;
                std::cout << "Port Pool: " << stats.allocations.port_pool_available
                          << " available (" << stats.allocations.port_pool_usage << " used)" << std::endl;
                std::cout << "Relay Sockets: " << stats.relay_sockets << std::endl;
                std::cout << "Bandwidth: "
                          << "Read=" << stats.bandwidth.available_read_tokens
                          << " Write=" << stats.bandwidth.available_write_tokens << std::endl;
                std::cout << "Total Bytes: "
                          << "Sent=" << stats.allocations.total_bytes_sent
                          << " Received=" << stats.allocations.total_bytes_received << std::endl;
            }
        }

        server.Stop();
        g_server = nullptr;

        std::cout << "Server shutdown complete" << std::endl;
        return 0;

    } catch (const std::exception& e) {
        std::cerr << "Fatal error: " << e.what() << std::endl;
        return 1;
    }
}
