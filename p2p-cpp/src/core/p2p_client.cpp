#include "p2p/core/p2p_client.hpp"
#include <iostream>

namespace asio = boost::asio;

namespace p2p {
namespace core {

P2PClient::P2PClient(boost::asio::io_context& io_context,
                     const std::string& did,
                     const P2PConfig& config)
    : io_context_(io_context)
    , did_(did)
    , config_(config)
    , state_(ConnectionState::DISCONNECTED)
    , next_channel_id_(1)
    , keepalive_timer_(io_context)
    , running_(false)
{
}

P2PClient::~P2PClient() {
    close();
}

void P2PClient::initialize(std::function<void(const std::error_code&)> callback) {
    if (running_) {
        callback(std::make_error_code(std::errc::already_connected));
        return;
    }

    // Detect NAT type
    detect_nat([this, callback](const std::error_code& ec) {
        if (ec) {
            callback(ec);
            return;
        }

        // Initialize UDP transport
        udp_transport_ = std::make_shared<transport::UDPTransport>(
            io_context_, config_.local_port
        );

        std::error_code transport_ec;
        udp_transport_->start(transport_ec);

        if (transport_ec) {
            callback(transport_ec);
            return;
        }

        // Set up receive callback
        udp_transport_->set_receive_callback(
            [this](const std::vector<uint8_t>& data, const auto& /*endpoint*/) {
                handle_received_message(data);
            }
        );

        running_ = true;
        callback(std::error_code());
    });
}

void P2PClient::detect_nat(std::function<void(const std::error_code&)> callback) {
    nat::detect_nat_type(
        io_context_,
        config_.stun_server,
        config_.stun_port,
        [this, callback](const nat::NATDetectionResult& result) {
            nat_type_ = result.nat_type;

            if (result.public_ip && result.public_port) {
                public_addr_ = std::make_pair(*result.public_ip, *result.public_port);
            }

            if (result.nat_type == nat::NATType::BLOCKED) {
                callback(std::make_error_code(std::errc::network_unreachable));
            } else {
                callback(std::error_code());
            }
        }
    );
}

void P2PClient::connect(const std::string& peer_did,
                        std::function<void(const std::error_code&)> callback) {
    if (!running_) {
        callback(std::make_error_code(std::errc::not_connected));
        return;
    }

    if (state_ == ConnectionState::CONNECTED_P2P ||
        state_ == ConnectionState::CONNECTED_RELAY) {
        callback(std::make_error_code(std::errc::already_connected));
        return;
    }

    state_ = ConnectionState::CONNECTING;

    // Create peer info (in real implementation, query from signaling server)
    PeerInfo peer;
    peer.did = peer_did;

    current_peer_ = peer;

    // TODO: Implement actual connection logic
    // For now, just simulate successful connection
    state_ = ConnectionState::CONNECTED_P2P;

    // Start keepalive
    start_keepalive();

    // Notify connected
    if (on_connected_) {
        on_connected_();
    }

    callback(std::error_code());
}

void P2PClient::send_data(int channel_id,
                          const std::vector<uint8_t>& data,
                          std::function<void(const std::error_code&)> callback) {
    if (!is_connected()) {
        if (callback) {
            callback(std::make_error_code(std::errc::not_connected));
        }
        return;
    }

    if (!udp_transport_) {
        if (callback) {
            callback(std::make_error_code(std::errc::not_connected));
        }
        return;
    }

    // Create channel data message
    protocol::ChannelDataMessage msg(did_, current_peer_->did, channel_id, data);
    auto encoded = msg.encode();

    udp_transport_->send(encoded, [callback](const std::error_code& ec) {
        if (callback) {
            callback(ec);
        }
    });
}

int P2PClient::create_channel() {
    int channel_id = next_channel_id_++;
    channels_[channel_id] = std::queue<std::vector<uint8_t>>();
    return channel_id;
}

void P2PClient::close_channel(int channel_id) {
    channels_.erase(channel_id);
}

void P2PClient::close() {
    if (!running_) {
        return;
    }

    running_ = false;
    state_ = ConnectionState::DISCONNECTED;

    // Stop keepalive
    keepalive_timer_.cancel();

    // Close transport
    if (udp_transport_) {
        udp_transport_->stop();
    }

    // Notify disconnected
    if (on_disconnected_) {
        on_disconnected_();
    }
}

void P2PClient::start_keepalive() {
    if (!running_) {
        return;
    }

    keepalive_timer_.expires_after(config_.keepalive_interval);
    keepalive_timer_.async_wait([this](const boost::system::error_code& ec) {
        if (!ec && running_) {
            send_keepalive();
            start_keepalive();  // Schedule next keepalive
        }
    });
}

void P2PClient::send_keepalive() {
    if (!is_connected() || !current_peer_) {
        return;
    }

    protocol::KeepaliveMessage msg(did_, current_peer_->did);
    auto encoded = msg.encode();

    if (udp_transport_) {
        udp_transport_->send(encoded, [](const std::error_code&) {
            // Ignore errors for keepalive
        });
    }
}

void P2PClient::handle_received_message(const std::vector<uint8_t>& data) {
    auto msg = protocol::Message::decode(data);
    if (!msg) {
        return;
    }

    switch (msg->type()) {
        case protocol::MessageType::HANDSHAKE:
        case protocol::MessageType::HANDSHAKE_ACK:
            // Handle handshake
            break;

        case protocol::MessageType::KEEPALIVE:
            // Keepalive received, connection is alive
            break;

        case protocol::MessageType::CHANNEL_DATA:
            if (msg->channel_id().has_value()) {
                int channel_id = msg->channel_id().value();

                // Store in channel queue
                if (channels_.find(channel_id) != channels_.end()) {
                    channels_[channel_id].push(msg->payload());
                }

                // Notify callback
                if (on_data_) {
                    on_data_(channel_id, msg->payload());
                }
            }
            break;

        case protocol::MessageType::DISCONNECT:
            close();
            break;

        default:
            break;
    }
}

} // namespace core
} // namespace p2p
