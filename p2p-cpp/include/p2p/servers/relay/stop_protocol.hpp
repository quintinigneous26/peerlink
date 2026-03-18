#pragma once

#include <memory>
#include <string>
#include <vector>
#include <functional>
#include "p2p/servers/relay/hop_protocol.hpp"
#include "p2p/servers/relay/relay_connection.hpp"

namespace p2p {
namespace relay {
namespace v2 {

// Forward declarations
class ReservationManager;

// CONNECT request for Stop protocol
struct StopConnectRequest {
    std::string peer_id;
    std::vector<std::string> addrs;
};

// CONNECT response for Stop protocol
struct StopConnectResponse {
    StatusCode status;
    std::string text;
    std::shared_ptr<RelayConnection> connection;
};

/**
 * Stop Protocol Handler
 * Implements /libp2p/circuit/relay/0.2.0/stop protocol
 *
 * The Stop protocol is used by the destination peer to accept
 * incoming relay connections.
 */
class StopProtocol {
public:
    StopProtocol(std::shared_ptr<ReservationManager> reservation_mgr);
    ~StopProtocol() = default;

    // Handle CONNECT message
    StopConnectResponse HandleConnect(const StopConnectRequest& request);

    // Accept incoming connection
    StopConnectResponse AcceptConnection(
        const std::string& peer_id,
        const std::string& source_peer_id);

    // Get protocol ID
    static std::string GetProtocolID() {
        return "/libp2p/circuit/relay/0.2.0/stop";
    }

private:
    std::shared_ptr<ReservationManager> reservation_mgr_;

    // Verify that the peer has a valid reservation
    bool VerifyReservation(const std::string& peer_id);

    // Establish relay connection
    std::shared_ptr<RelayConnection> EstablishRelayConnection(
        const std::string& peer_id,
        const std::string& source_peer_id);
};

} // namespace v2
} // namespace relay
} // namespace p2p
