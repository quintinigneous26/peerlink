#pragma once

#include "models.hpp"
#include <boost/asio/awaitable.hpp>
#include <boost/asio/ip/tcp.hpp>
#include <boost/beast/core.hpp>
#include <boost/beast/websocket.hpp>
#include <memory>
#include <string>

namespace signaling {

namespace asio = boost::asio;
namespace beast = boost::beast;
namespace websocket = beast::websocket;
using tcp = asio::ip::tcp;

// Forward declaration
class ConnectionManager;

class WebSocketSession : public std::enable_shared_from_this<WebSocketSession> {
public:
    explicit WebSocketSession(
        tcp::socket socket,
        std::shared_ptr<ConnectionManager> manager
    );

    ~WebSocketSession();

    // Start the session
    asio::awaitable<void> run(std::string device_id);

    // Send a message
    asio::awaitable<void> send(json message);

    // Close the connection
    asio::awaitable<void> close();

    // Get device ID
    const std::string& device_id() const { return device_id_; }

    // Get executor
    auto get_executor() { return ws_.get_executor(); }

private:
    // Read loop
    asio::awaitable<void> read_loop();

    // Handle incoming message
    asio::awaitable<void> handle_message(const json& message);

    websocket::stream<tcp::socket> ws_;
    std::shared_ptr<ConnectionManager> manager_;
    std::string device_id_;
    beast::flat_buffer buffer_;
};

} // namespace signaling