#pragma once

#include "models.hpp"
#include "connection_manager.hpp"
#include <boost/asio/awaitable.hpp>
#include <memory>
#include <optional>

namespace signaling {

class MessageHandler {
public:
    explicit MessageHandler(std::shared_ptr<ConnectionManager> manager);

    // Handle incoming message
    asio::awaitable<std::optional<json>> handle_message(
        const std::string& device_id,
        const Message& message
    );

private:
    // Message handlers
    asio::awaitable<json> handle_register(
        const std::string& device_id,
        const Message& message
    );

    asio::awaitable<json> handle_unregister(
        const std::string& device_id,
        const Message& message
    );

    asio::awaitable<std::optional<json>> handle_connect(
        const std::string& device_id,
        const Message& message
    );

    asio::awaitable<json> handle_offer(
        const std::string& device_id,
        const Message& message
    );

    asio::awaitable<json> handle_answer(
        const std::string& device_id,
        const Message& message
    );

    asio::awaitable<json> handle_ice_candidate(
        const std::string& device_id,
        const Message& message
    );

    asio::awaitable<json> handle_heartbeat(
        const std::string& device_id,
        const Message& message
    );

    asio::awaitable<json> handle_ping(
        const std::string& device_id,
        const Message& message
    );

    asio::awaitable<json> handle_query_device(
        const std::string& device_id,
        const Message& message
    );

    asio::awaitable<json> handle_relay_request(
        const std::string& device_id,
        const Message& message
    );

    std::shared_ptr<ConnectionManager> manager_;
};

} // namespace signaling