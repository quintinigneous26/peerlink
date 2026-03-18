#include "p2p/servers/relay/stop_protocol.hpp"
#include "p2p/servers/relay/relay_connection.hpp"
#include "p2p/net/socket.hpp"
#include <stdexcept>

namespace p2p {
namespace relay {
namespace v2 {

// ============================================================================
// StopProtocol Implementation
// ============================================================================

StopProtocol::StopProtocol(std::shared_ptr<ReservationManager> reservation_mgr)
    : reservation_mgr_(reservation_mgr) {
}

StopConnectResponse StopProtocol::HandleConnect(const StopConnectRequest& request) {
    StopConnectResponse response;

    // Verify reservation
    if (!VerifyReservation(request.peer_id)) {
        response.status = StatusCode::NO_RESERVATION;
        response.text = "No valid reservation found";
        return response;
    }

    // For Stop protocol, we need the source peer ID
    // In a real implementation, this would come from the relay
    std::string source_peer_id = "source-peer-id";

    // Establish relay connection
    auto connection = EstablishRelayConnection(request.peer_id, source_peer_id);
    if (!connection) {
        response.status = StatusCode::CONNECTION_FAILED;
        response.text = "Failed to establish relay connection";
        return response;
    }

    response.status = StatusCode::OK;
    response.text = "Connection established";
    response.connection = connection;
    return response;
}

StopConnectResponse StopProtocol::AcceptConnection(
    const std::string& peer_id,
    const std::string& source_peer_id) {

    StopConnectResponse response;

    // Verify reservation
    if (!VerifyReservation(peer_id)) {
        response.status = StatusCode::NO_RESERVATION;
        response.text = "No valid reservation found";
        return response;
    }

    // Establish relay connection
    auto connection = EstablishRelayConnection(peer_id, source_peer_id);
    if (!connection) {
        response.status = StatusCode::CONNECTION_FAILED;
        response.text = "Failed to establish relay connection";
        return response;
    }

    response.status = StatusCode::OK;
    response.text = "Connection accepted";
    response.connection = connection;
    return response;
}

bool StopProtocol::VerifyReservation(const std::string& peer_id) {
    auto reservation = reservation_mgr_->Lookup(peer_id);
    return reservation.has_value();
}

std::shared_ptr<RelayConnection> StopProtocol::EstablishRelayConnection(
    const std::string& peer_id,
    const std::string& source_peer_id) {

    // TODO: Implement actual relay connection establishment
    // For now, create a mock connection with a relay address for testing
    auto conn = std::make_shared<ActiveRelayConnection>(source_peer_id);
    net::SocketAddr mock_relay_addr("127.0.0.1", 9000);
    conn->SetRelayAddr(mock_relay_addr);
    return conn;
}

} // namespace v2
} // namespace relay
} // namespace p2p
