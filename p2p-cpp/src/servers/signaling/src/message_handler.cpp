#include "message_handler.hpp"
#include <boost/uuid/uuid.hpp>
#include <boost/uuid/uuid_generators.hpp>
#include <boost/uuid/uuid_io.hpp>
#include <iostream>

namespace asio = boost::asio;

namespace signaling {

MessageHandler::MessageHandler(std::shared_ptr<ConnectionManager> manager)
    : manager_(std::move(manager))
{
}

asio::awaitable<std::optional<json>> MessageHandler::handle_message(
    const std::string& device_id,
    const Message& message
) {
    try {
        switch (message.type) {
            case MessageType::REGISTER:
                co_return co_await handle_register(device_id, message);
            case MessageType::UNREGISTER:
                co_return co_await handle_unregister(device_id, message);
            case MessageType::CONNECT:
                co_return co_await handle_connect(device_id, message);
            case MessageType::OFFER:
                co_return co_await handle_offer(device_id, message);
            case MessageType::ANSWER:
                co_return co_await handle_answer(device_id, message);
            case MessageType::ICE_CANDIDATE:
                co_return co_await handle_ice_candidate(device_id, message);
            case MessageType::HEARTBEAT:
                co_return co_await handle_heartbeat(device_id, message);
            case MessageType::PING:
                co_return co_await handle_ping(device_id, message);
            case MessageType::QUERY_DEVICE:
                co_return co_await handle_query_device(device_id, message);
            case MessageType::RELAY_REQUEST:
                co_return co_await handle_relay_request(device_id, message);
            default:
                ErrorResponse error{
                    ErrorCode::INVALID_REQUEST,
                    "Unknown message type",
                    message.request_id
                };
                co_return error.to_json();
        }
    } catch (const std::exception& e) {
        std::cerr << "Error handling message: " << e.what() << std::endl;
        ErrorResponse error{
            ErrorCode::INTERNAL_ERROR,
            e.what(),
            message.request_id
        };
        co_return error.to_json();
    }
}

asio::awaitable<json> MessageHandler::handle_register(
    const std::string& device_id,
    const Message& message
) {
    auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    co_return json{
        {"type", "registered"},
        {"data", {{"device_id", device_id}}},
        {"timestamp", now}
    };
}

asio::awaitable<json> MessageHandler::handle_unregister(
    const std::string& device_id,
    const Message& message
) {
    co_await manager_->disconnect(device_id);

    auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    co_return json{
        {"type", "unregister"},
        {"data", {{"device_id", device_id}}},
        {"timestamp", now}
    };
}

asio::awaitable<std::optional<json>> MessageHandler::handle_connect(
    const std::string& device_id,
    const Message& message
) {
    // Get target device ID
    if (!message.data.contains("target_device_id")) {
        ErrorResponse error{
            ErrorCode::INVALID_REQUEST,
            "Missing target_device_id",
            message.request_id
        };
        co_return error.to_json();
    }

    std::string target_device_id = message.data["target_device_id"];

    // Check if target device is connected
    if (!manager_->is_connected(target_device_id)) {
        ErrorResponse error{
            ErrorCode::DEVICE_NOT_FOUND,
            "Target device " + target_device_id + " not found",
            message.request_id
        };
        co_return error.to_json();
    }

    // Check if session already exists
    auto existing = manager_->get_session_by_devices(device_id, target_device_id);
    if (existing && existing->status != ConnectionStatus::DISCONNECTED) {
        auto now = std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::system_clock::now().time_since_epoch()
        ).count();

        co_return json{
            {"type", "connect_response"},
            {"data", {
                {"session_id", existing->session_id},
                {"status", to_string(existing->status)},
                {"existing", true}
            }},
            {"timestamp", now},
            {"request_id", message.request_id.value_or("")}
        };
    }

    // Create new session
    auto session = manager_->create_session(device_id, target_device_id);
    manager_->add_pending_request(session.session_id, device_id);

    // Forward connection request to target device
    boost::uuids::uuid request_uuid = boost::uuids::random_generator()();
    std::string request_id = boost::uuids::to_string(request_uuid);

    auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    json connect_request = {
        {"type", "connect_request"},
        {"data", {
            {"source_device_id", device_id},
            {"session_id", session.session_id},
            {"capabilities", message.data.value("capabilities", json::array())}
        }},
        {"timestamp", now},
        {"request_id", request_id}
    };

    bool sent = co_await manager_->send_message(target_device_id, connect_request);

    if (!sent) {
        ErrorResponse error{
            ErrorCode::CONNECTION_FAILED,
            "Failed to reach target device",
            message.request_id
        };
        co_return error.to_json();
    }

    co_return json{
        {"type", "connect_response"},
        {"data", {
            {"session_id", session.session_id},
            {"status", "connecting"}
        }},
        {"timestamp", now},
        {"request_id", message.request_id.value_or("")}
    };
}

asio::awaitable<json> MessageHandler::handle_offer(
    const std::string& device_id,
    const Message& message
) {
    auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    // Validate required fields
    if (!message.data.contains("session_id") || !message.data.contains("offer")) {
        ErrorResponse error{
            ErrorCode::INVALID_REQUEST,
            "Missing session_id or offer",
            message.request_id
        };
        co_return error.to_json();
    }

    std::string session_id = message.data["session_id"];
    std::string offer = message.data["offer"];

    // Get session
    auto session_opt = manager_->get_session(session_id);
    if (!session_opt) {
        ErrorResponse error{
            ErrorCode::INVALID_REQUEST,
            "Invalid session_id",
            message.request_id
        };
        co_return error.to_json();
    }

    auto session = *session_opt;

    // Store offer
    manager_->set_session_offer(session_id, offer);

    // Determine target device
    std::string target_device_id = (device_id == session.device_a)
        ? session.device_b
        : session.device_a;

    // Forward offer
    json offer_msg = {
        {"type", "offer"},
        {"data", {
            {"session_id", session_id},
            {"offer", offer},
            {"source_device_id", device_id}
        }},
        {"timestamp", now}
    };

    co_await manager_->send_message(target_device_id, offer_msg);

    co_return json{
        {"type", "offer"},
        {"data", {
            {"session_id", session_id},
            {"status", "forwarded"}
        }},
        {"timestamp", now},
        {"request_id", message.request_id.value_or("")}
    };
}

asio::awaitable<json> MessageHandler::handle_answer(
    const std::string& device_id,
    const Message& message
) {
    auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    // Validate required fields
    if (!message.data.contains("session_id") || !message.data.contains("answer")) {
        ErrorResponse error{
            ErrorCode::INVALID_REQUEST,
            "Missing session_id or answer",
            message.request_id
        };
        co_return error.to_json();
    }

    std::string session_id = message.data["session_id"];
    std::string answer = message.data["answer"];

    // Get session
    auto session_opt = manager_->get_session(session_id);
    if (!session_opt) {
        ErrorResponse error{
            ErrorCode::INVALID_REQUEST,
            "Invalid session_id",
            message.request_id
        };
        co_return error.to_json();
    }

    auto session = *session_opt;

    // Store answer
    manager_->set_session_answer(session_id, answer);

    // Determine target device
    std::string target_device_id = (device_id == session.device_b)
        ? session.device_a
        : session.device_b;

    // Forward answer
    json answer_msg = {
        {"type", "answer"},
        {"data", {
            {"session_id", session_id},
            {"answer", answer},
            {"source_device_id", device_id}
        }},
        {"timestamp", now}
    };

    co_await manager_->send_message(target_device_id, answer_msg);

    // Update session status
    manager_->update_session_status(session_id, ConnectionStatus::CONNECTED);

    co_return json{
        {"type", "answer"},
        {"data", {
            {"session_id", session_id},
            {"status", "forwarded"}
        }},
        {"timestamp", now},
        {"request_id", message.request_id.value_or("")}
    };
}

asio::awaitable<json> MessageHandler::handle_ice_candidate(
    const std::string& device_id,
    const Message& message
) {
    auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    // Validate required fields
    if (!message.data.contains("session_id") || !message.data.contains("candidate")) {
        ErrorResponse error{
            ErrorCode::INVALID_REQUEST,
            "Missing session_id or candidate",
            message.request_id
        };
        co_return error.to_json();
    }

    std::string session_id = message.data["session_id"];
    json candidate = message.data["candidate"];

    // Get session
    auto session_opt = manager_->get_session(session_id);
    if (!session_opt) {
        ErrorResponse error{
            ErrorCode::INVALID_REQUEST,
            "Invalid session_id",
            message.request_id
        };
        co_return error.to_json();
    }

    auto session = *session_opt;

    // Store candidate
    json candidate_data = {
        {"candidate", candidate},
        {"sdpMid", message.data.value("sdpMid", "")},
        {"sdpMLineIndex", message.data.value("sdpMLineIndex", 0)}
    };
    manager_->add_ice_candidate(session_id, device_id, candidate_data);

    // Determine target device
    std::string target_device_id = (device_id == session.device_a)
        ? session.device_b
        : session.device_a;

    // Forward ICE candidate
    json ice_msg = {
        {"type", "ice_candidate"},
        {"data", {
            {"session_id", session_id},
            {"candidate", candidate},
            {"sdpMid", message.data.value("sdpMid", "")},
            {"sdpMLineIndex", message.data.value("sdpMLineIndex", 0)},
            {"source_device_id", device_id}
        }},
        {"timestamp", now}
    };

    co_await manager_->send_message(target_device_id, ice_msg);

    co_return json{
        {"type", "ice_candidate"},
        {"data", {
            {"session_id", session_id},
            {"status", "forwarded"}
        }},
        {"timestamp", now},
        {"request_id", message.request_id.value_or("")}
    };
}

asio::awaitable<json> MessageHandler::handle_heartbeat(
    const std::string& device_id,
    const Message& message
) {
    co_await manager_->update_heartbeat(device_id);

    auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    co_return json{
        {"type", "heartbeat_ack"},
        {"data", {{"device_id", device_id}}},
        {"timestamp", now}
    };
}

asio::awaitable<json> MessageHandler::handle_ping(
    const std::string& device_id,
    const Message& message
) {
    auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    co_return json{
        {"type", "pong"},
        {"data", {{"device_id", device_id}}},
        {"timestamp", now}
    };
}

asio::awaitable<json> MessageHandler::handle_query_device(
    const std::string& device_id,
    const Message& message
) {
    auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    // Validate required fields
    if (!message.data.contains("target_device_id")) {
        ErrorResponse error{
            ErrorCode::INVALID_REQUEST,
            "Missing target_device_id",
            message.request_id
        };
        co_return error.to_json();
    }

    std::string target_device_id = message.data["target_device_id"];
    auto device_opt = manager_->get_device(target_device_id);

    if (!device_opt) {
        co_return json{
            {"type", "device_info"},
            {"data", {
                {"device_id", target_device_id},
                {"online", false}
            }},
            {"timestamp", now},
            {"request_id", message.request_id.value_or("")}
        };
    }

    auto device = *device_opt;

    co_return json{
        {"type", "device_info"},
        {"data", {
            {"device_id", target_device_id},
            {"online", true},
            {"capabilities", device.capabilities},
            {"nat_type", to_string(device.nat_type)}
        }},
        {"timestamp", now},
        {"request_id", message.request_id.value_or("")}
    };
}

asio::awaitable<json> MessageHandler::handle_relay_request(
    const std::string& device_id,
    const Message& message
) {
    auto now = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();

    // Validate required fields
    if (!message.data.contains("session_id")) {
        ErrorResponse error{
            ErrorCode::INVALID_REQUEST,
            "Missing session_id",
            message.request_id
        };
        co_return error.to_json();
    }

    std::string session_id = message.data["session_id"];

    // Get session
    auto session_opt = manager_->get_session(session_id);
    if (!session_opt) {
        ErrorResponse error{
            ErrorCode::INVALID_REQUEST,
            "Invalid session_id",
            message.request_id
        };
        co_return error.to_json();
    }

    auto session = *session_opt;

    // Mark session to use relay
    manager_->set_relay_mode(session_id);

    // Notify both devices
    json relay_msg = {
        {"type", "relay_response"},
        {"data", {
            {"session_id", session_id},
            {"use_relay", true},
            {"relay_info", {
                {"host", "relay.example.com"},
                {"port", 50000}
            }}
        }},
        {"timestamp", now}
    };

    co_await manager_->send_message(session.device_a, relay_msg);
    co_await manager_->send_message(session.device_b, relay_msg);

    co_return json{
        {"type", "relay_response"},
        {"data", {
            {"session_id", session_id},
            {"status", "requested"}
        }},
        {"timestamp", now},
        {"request_id", message.request_id.value_or("")}
    };
}

} // namespace signaling