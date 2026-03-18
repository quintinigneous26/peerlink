#include "stun_server.hpp"
#include <boost/asio.hpp>
#include <csignal>
#include <iostream>
#include <memory>

namespace asio = boost::asio;

std::shared_ptr<p2p::server::StunServer> g_server;

void signal_handler(int signal) {
    if (signal == SIGINT || signal == SIGTERM) {
        std::cout << "\nReceived shutdown signal" << std::endl;
        if (g_server) {
            g_server->stop();
        }
    }
}

int main(int argc, char* argv[]) {
    try {
        // Parse command line arguments
        std::string host = "0.0.0.0";
        uint16_t udp_port = 3478;
        uint16_t tcp_port = 3479;

        if (argc > 1) {
            host = argv[1];
        }
        if (argc > 2) {
            udp_port = static_cast<uint16_t>(std::stoi(argv[2]));
        }
        if (argc > 3) {
            tcp_port = static_cast<uint16_t>(std::stoi(argv[3]));
        }

        // Setup signal handlers
        std::signal(SIGINT, signal_handler);
        std::signal(SIGTERM, signal_handler);

        // Create io_context
        boost::asio::io_context io_context;

        // Create and start server
        g_server = std::make_shared<p2p::server::StunServer>(
            io_context, host, udp_port, tcp_port
        );
        g_server->start();

        // Run io_context
        io_context.run();

        std::cout << "Server exited" << std::endl;
        return 0;

    } catch (const std::exception& e) {
        std::cerr << "Fatal error: " << e.what() << std::endl;
        return 1;
    }
}
