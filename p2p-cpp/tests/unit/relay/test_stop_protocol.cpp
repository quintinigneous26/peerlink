#include <gtest/gtest.h>
#include "p2p/servers/relay/stop_protocol.hpp"
#include "p2p/servers/relay/hop_protocol.hpp"

using namespace p2p::relay::v2;

class StopProtocolTest : public ::testing::Test {
protected:
    void SetUp() override {
        reservation_mgr = std::make_shared<ReservationManager>(10, 3600, 1024 * 1024);
        stop_protocol = std::make_unique<StopProtocol>(reservation_mgr);
    }

    std::shared_ptr<ReservationManager> reservation_mgr;
    std::unique_ptr<StopProtocol> stop_protocol;
};

TEST_F(StopProtocolTest, GetProtocolID) {
    EXPECT_EQ(StopProtocol::GetProtocolID(), "/libp2p/circuit/relay/0.2.0/stop");
}

TEST_F(StopProtocolTest, HandleConnectWithReservation) {
    // First create a reservation
    ReservationSlot slot;
    slot.peer_id = "peer123";
    slot.relay_addr = "relay-addr";
    slot.expire_time = std::time(nullptr) + 3600;
    slot.limit_duration = 3600;
    slot.limit_data = 1024 * 1024;
    reservation_mgr->Store(slot);

    // Now try to connect
    StopConnectRequest request;
    request.peer_id = "peer123";
    request.addrs = {"addr1", "addr2"};

    auto response = stop_protocol->HandleConnect(request);

    EXPECT_EQ(response.status, StatusCode::OK);
    EXPECT_FALSE(response.text.empty());
    ASSERT_NE(response.connection, nullptr);
    EXPECT_EQ(response.connection->GetType(), "relay");
}

TEST_F(StopProtocolTest, HandleConnectNoReservation) {
    StopConnectRequest request;
    request.peer_id = "nonexistent";
    request.addrs = {"addr1"};

    auto response = stop_protocol->HandleConnect(request);

    EXPECT_EQ(response.status, StatusCode::NO_RESERVATION);
    EXPECT_FALSE(response.text.empty());
    EXPECT_EQ(response.connection, nullptr);
}

TEST_F(StopProtocolTest, HandleConnectExpiredReservation) {
    // Create an expired reservation
    ReservationSlot slot;
    slot.peer_id = "peer123";
    slot.relay_addr = "relay-addr";
    slot.expire_time = std::time(nullptr) - 1;  // Already expired
    slot.limit_duration = 3600;
    slot.limit_data = 1024 * 1024;
    reservation_mgr->Store(slot);

    StopConnectRequest request;
    request.peer_id = "peer123";
    request.addrs = {"addr1"};

    auto response = stop_protocol->HandleConnect(request);

    // Should fail because reservation is expired
    EXPECT_EQ(response.status, StatusCode::NO_RESERVATION);
}

TEST_F(StopProtocolTest, AcceptConnectionSuccess) {
    // Create a reservation
    ReservationSlot slot;
    slot.peer_id = "peer123";
    slot.relay_addr = "relay-addr";
    slot.expire_time = std::time(nullptr) + 3600;
    reservation_mgr->Store(slot);

    auto response = stop_protocol->AcceptConnection("peer123", "source-peer-456");

    EXPECT_EQ(response.status, StatusCode::OK);
    EXPECT_FALSE(response.text.empty());
    ASSERT_NE(response.connection, nullptr);
    EXPECT_EQ(response.connection->GetType(), "relay");
    EXPECT_EQ(response.connection->GetPeerId(), "source-peer-456");
}

TEST_F(StopProtocolTest, AcceptConnectionNoReservation) {
    auto response = stop_protocol->AcceptConnection("nonexistent", "source-peer");

    EXPECT_EQ(response.status, StatusCode::NO_RESERVATION);
    EXPECT_EQ(response.connection, nullptr);
}

TEST_F(StopProtocolTest, MultipleConnections) {
    // Create reservations for multiple peers
    for (int i = 0; i < 5; i++) {
        ReservationSlot slot;
        slot.peer_id = "peer" + std::to_string(i);
        slot.relay_addr = "relay-addr";
        slot.expire_time = std::time(nullptr) + 3600;
        reservation_mgr->Store(slot);
    }

    // Accept connections for all peers
    for (int i = 0; i < 5; i++) {
        std::string peer_id = "peer" + std::to_string(i);
        std::string source_id = "source" + std::to_string(i);

        auto response = stop_protocol->AcceptConnection(peer_id, source_id);

        EXPECT_EQ(response.status, StatusCode::OK);
        ASSERT_NE(response.connection, nullptr);
        EXPECT_EQ(response.connection->GetPeerId(), source_id);
    }
}

class ActiveRelayConnectionTest : public ::testing::Test {};

TEST_F(ActiveRelayConnectionTest, CreateConnection) {
    ActiveRelayConnection conn("peer123");
    EXPECT_EQ(conn.GetType(), "active");
    EXPECT_EQ(conn.GetPeerId(), "peer123");
}

TEST_F(ActiveRelayConnectionTest, SendData) {
    ActiveRelayConnection conn("peer123");
    std::vector<uint8_t> data = {1, 2, 3, 4, 5};

    bool result = conn.Send(data);
    EXPECT_TRUE(result);
}

TEST_F(ActiveRelayConnectionTest, SendEmptyData) {
    ActiveRelayConnection conn("peer123");
    std::vector<uint8_t> empty_data;

    bool result = conn.Send(empty_data);
    EXPECT_FALSE(result);
}

TEST_F(ActiveRelayConnectionTest, ReceiveData) {
    ActiveRelayConnection conn("peer123");

    auto data = conn.Receive();
    // Currently returns empty, but should not crash
    EXPECT_TRUE(data.empty());
}

TEST_F(ActiveRelayConnectionTest, CloseConnection) {
    ActiveRelayConnection conn("peer123");

    // Should not crash
    conn.Close();
}
