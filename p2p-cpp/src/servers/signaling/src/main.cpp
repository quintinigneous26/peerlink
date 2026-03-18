#include "connection_manager.hpp"
#include "websocket_session.hpp"
#include <boost/asio/co_spawn.hpp>
#include <boost/asio/detached.hpp>
#include <boost/asio/io_context.hpp>
#include <boost/asio/ip/tcp.hpp>
#include <boost/asio/signal_set.hpp>
#include <boost/asio/use_awaitable.hpp>
#include <iostream>
#include <memory>
#include <string>

namespace asio = boost::asio;

namespace signaling {

using boost::asio::ip::tcp;
using boost::asio::awaitable;
using boost::asio::co_spawn;
using boost::asio::detached;
using boost::asio::use_awaitable;

// Configuration
struct Config {
    std::string host = "0.0.0.0";
    unsigned short port = 8080;
    int heartbeat_interval = 30;
    int connection_timeout = 90;
};

// Listener for accepting connections
class Listener : public std::enable_shared_from_this<Listener> {
public:
    Listener(
        boost::asio::io_context& ioc,
        tcp::endpoint endpoint,
        std::shared_ptr<ConnectionManager> manager
    )
        : ioc_(ioc)
        , acceptor_(ioc)
        , manager_(std::move(manager))
    {
        boost::system::error_code ec;

        // Open acceptor
        acceptor_.open(endpoint.protocol(), ec);
        if (ec) {
            std::cerr << "Open error: " << ec.message() << std::endl;
            return;
        }

        // Set SO_REUSEADDR
        acceptor_.set_option(boost::asio::socket_base::reuse_address(true), ec);
        if (ec) {
            std::cerr << "Set option error: " << ec.message() << std::endl;
            return;
        }

        // Bind
        acceptor_.bind(endpoint, ec);
        if (ec) {
            std::cerr << "Bind error: " << ec.message() << std::endl;
            return;
        }

        // Listen
        acceptor_.listen(boost::asio::socket_base::max_listen_connections, ec);
        if (ec) {
            std::cerr << "Listen error: " << ec.message() << std::endl;
            return;
        }

        std::cout << "Signaling server listening on "
                  << endpoint.address() << ":" << endpoint.port() << std::endl;
    }

    void run() {
        co_spawn(
            ioc_,
            accept_loop(),
            detached
        );
    }

private:
    awaitable<void> accept_loop() {
        while (true) {
            try {
                // Accept connection
                tcp::socket socket = co_await acceptor_.async_accept(use_awaitable);

                std::cout << "New connection from "
                          << socket.remote_endpoint().address() << ":"
                          << socket.remote_endpoint().port() << std::endl;

                // Create session
                auto session = std::make_shared<WebSocketSession>(
                    std::move(socket),
                    manager_
                );

                // Generate temporary device ID (will be replaced by proper registration)
                std::string device_id = "temp_" + std::to_string(
                    std::chrono::system_clock::now().time_since_epoch().count()
                );

                // Register device
                co_await manager_->connect(
                    device_id,
                    session,
                    "",  // public_key (will be filled in register message)
                    {}   // capabilities
                );

                // Start session
                co_spawn(
                    ioc_,
                    session->run(device_id),
                    detached
                );

            } catch (const std::exception& e) {
                std::cerr << "Accept error: " << e.what() << std::endl;
            }
        }
    }

    boost::asio::io_context& ioc_;
    tcp::acceptor acceptor_;
    std::shared_ptr<ConnectionManager> manager_;
};

// Cleanup task for stale connections
awaitable<void> cleanup_task(
    std::shared_ptr<ConnectionManager> manager,
    int interval_seconds,
    int timeout_seconds
) {
    boost::asio::steady_timer timer(co_await boost::asio::this_coro::executor);

    while (true) {
        timer.expires_after(std::chrono::seconds(interval_seconds));
        co_await timer.async_wait(use_awaitable);

        int cleaned = co_await manager->cleanup_stale(timeout_seconds);
        if (cleaned > 0) {
            std::cout << "Cleaned up " << cleaned << " stale connections" << std::endl;
        }
    }
}

} // namespace signaling

int main(int argc, char* argv[]) {
    try {
        // Parse command line arguments
        signaling::Config config;
        if (argc >= 2) {
            config.port = static_cast<unsigned short>(std::atoi(argv[1]));
        }

        std::cout << "Starting Signaling Server..." << std::endl;
        std::cout << "Configuration:" << std::endl;
        std::cout << "  Host: " << config.host << std::endl;
        std::cout << "  Port: " << config.port << std::endl;
        std::cout << "  Heartbeat interval: " << config.heartbeat_interval << "s" << std::endl;
        std::cout << "  Connection timeout: " << config.connection_timeout << "s" << std::endl;

        // Create io_context
        boost::asio::io_context ioc{1};  // Single thread

        // Create connection manager
        auto manager = std::make_shared<signaling::ConnectionManager>();

        // Create listener
        auto listener = std::make_shared<signaling::Listener>(
            ioc,
            signaling::tcp::endpoint{boost::asio::ip::make_address(config.host), config.port},
            manager
        );

        // Start listener
        listener->run();

        // Start cleanup task
        signaling::co_spawn(
            ioc,
            signaling::cleanup_task(
                manager,
                config.heartbeat_interval,
                config.connection_timeout
            ),
            signaling::detached
        );

        // Setup signal handling
        boost::asio::signal_set signals(ioc, SIGINT, SIGTERM);
        signals.async_wait([&](auto, auto) {
            std::cout << "\nShutting down..." << std::endl;
            ioc.stop();
        });

        std::cout << "Signaling Server started successfully!" << std::endl;

        // Run io_context
        ioc.run();

        std::cout << "Signaling Server stopped." << std::endl;

    } catch (const std::exception& e) {
        std::cerr << "Fatal error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}