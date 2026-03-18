/**
 * @file basic_client.cpp
 * @brief Basic P2P client usage example
 *
 * This example demonstrates:
 * - Client initialization
 * - NAT detection
 * - P2P connection establishment
 * - Sending and receiving data
 */

#include "p2p/core/p2p_client.hpp"
#include <iostream>
#include <string>

using namespace p2p;

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0] << " <my_did> <peer_did>" << std::endl;
        return 1;
    }

    std::string my_did = argv[1];
    std::string peer_did = argv[2];

    try {
        // Create IO context
        boost::asio::io_context io_context;

        // Configure client
        core::P2PConfig config;
        config.signaling_server = "localhost";
        config.signaling_port = 8443;
        config.stun_server = "stun.l.google.com";
        config.stun_port = 19302;

        // Create client
        auto client = std::make_shared<core::P2PClient>(io_context, my_did, config);

        // Set up event handlers
        client->on_connected([&]() {
            std::cout << "Connected to peer: " << peer_did << std::endl;
            std::cout << "Connection type: " << (client->is_p2p() ? "P2P" : "Relay") << std::endl;

            // Create a data channel
            int channel_id = client->create_channel();
            std::cout << "Created channel: " << channel_id << std::endl;

            // Send test message
            std::string message = "Hello from " + my_did;
            std::vector<uint8_t> data(message.begin(), message.end());

            client->send_data(channel_id, data, [](const std::error_code& ec) {
                if (ec) {
                    std::cerr << "Send failed: " << ec.message() << std::endl;
                } else {
                    std::cout << "Message sent successfully" << std::endl;
                }
            });
        });

        client->on_disconnected([&]() {
            std::cout << "Disconnected from peer" << std::endl;
            io_context.stop();
        });

        client->on_data([](int channel_id, const std::vector<uint8_t>& data) {
            std::string message(data.begin(), data.end());
            std::cout << "Received on channel " << channel_id << ": " << message << std::endl;
        });

        client->on_error([](const std::error_code& ec, const std::string& message) {
            std::cerr << "Error: " << message << " (" << ec.message() << ")" << std::endl;
        });

        // Initialize client
        std::cout << "Initializing client..." << std::endl;
        client->initialize([&](const std::error_code& ec) {
            if (ec) {
                std::cerr << "Initialization failed: " << ec.message() << std::endl;
                io_context.stop();
                return;
            }

            std::cout << "Client initialized successfully" << std::endl;

            // Connect to peer
            std::cout << "Connecting to peer: " << peer_did << std::endl;
            client->connect(peer_did, [&](const std::error_code& ec) {
                if (ec) {
                    std::cerr << "Connection failed: " << ec.message() << std::endl;
                    io_context.stop();
                    return;
                }

                std::cout << "Connection established" << std::endl;
            });
        });

        // Run IO context
        std::cout << "Starting event loop..." << std::endl;
        io_context.run();

        std::cout << "Client stopped" << std::endl;

    } catch (const std::exception& e) {
        std::cerr << "Exception: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
