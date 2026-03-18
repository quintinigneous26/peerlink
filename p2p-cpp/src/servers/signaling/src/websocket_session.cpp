#include "websocket_session.hpp"
#include "connection_manager.hpp"
#include "message_handler.hpp"
#include <boost/asio/co_spawn.hpp>
#include <boost/asio/detached.hpp>
#include <boost/asio/use_awaitable.hpp>
#include <iostream>

namespace asio = boost::asio;

namespace signaling {

WebSocketSession::WebSocketSession(
    tcp::socket socket,
    std::shared_ptr<ConnectionManager> manager
)
    : ws_(std::move(socket))
    , manager_(std::move(manager))
{
}

WebSocketSession::~WebSocketSession() {
    // Cleanup handled by ConnectionManager
}

asio::awaitable<void> WebSocketSession::run(std::string device_id) {
    device_id_ = std::move(device_id);

    try {
        // Accept WebSocket handshake
        co_await ws_.async_accept(asio::use_awaitable);

        // Send registration confirmation
        json registered_msg = {
            {"type", "registered"},
            {"data", {
                {"device_id", device_id_},
                {"server_time", std::chrono::duration_cast<std::chrono::seconds>(
                    std::chrono::system_clock::now().time_since_epoch()
                ).count()}
            }},
            {"timestamp", std::chrono::duration_cast<std::chrono::seconds>(
                std::chrono::system_clock::now().time_since_epoch()
            ).count()}
        };

        co_await send(registered_msg);

        // Start read loop
        co_await read_loop();

    } catch (const std::exception& e) {
        std::cerr << "WebSocket error for " << device_id_ << ": " << e.what() << std::endl;
    }

    // Cleanup
    co_await manager_->disconnect(device_id_);
}

asio::awaitable<void> WebSocketSession::send(json message) {
    std::string msg_str = message.dump();
    co_await ws_.async_write(
        asio::buffer(msg_str),
        asio::use_awaitable
    );
}

asio::awaitable<void> WebSocketSession::close() {
    try {
        co_await ws_.async_close(
            websocket::close_code::normal,
            asio::use_awaitable
        );
    } catch (const std::exception&) {
        // Ignore errors during close
    }
}

asio::awaitable<void> WebSocketSession::read_loop() {
    MessageHandler handler(manager_);

    while (true) {
        try {
            // Read message
            buffer_.clear();
            co_await ws_.async_read(buffer_, asio::use_awaitable);

            // Parse JSON
            std::string msg_str = beast::buffers_to_string(buffer_.data());
            json j = json::parse(msg_str);

            // Parse message
            Message message = Message::from_json(j);
            message.source_device_id = device_id_;

            // Handle message
            auto response = co_await handler.handle_message(device_id_, message);

            // Send response if any
            if (response) {
                co_await send(*response);
            }

        } catch (const beast::system_error& e) {
            if (e.code() == websocket::error::closed) {
                // Connection closed normally
                break;
            }
            throw;
        } catch (const json::exception& e) {
            std::cerr << "JSON parse error from " << device_id_ << ": " << e.what() << std::endl;

            // Send error response
            ErrorResponse error{
                ErrorCode::INVALID_REQUEST,
                std::string("Invalid JSON: ") + e.what(),
                "" // request_id
            };
            // Cannot use co_await in catch block
            asio::co_spawn(
                ws_.get_executor(),
                send(error.to_json()),
                asio::detached
            );
        }
    }
}

asio::awaitable<void> WebSocketSession::handle_message(const json& message) {
    // This is now handled by MessageHandler in read_loop
    co_return;
}

} // namespace signaling