#include <gtest/gtest.h>
#include "p2p/servers/relay/hop_protocol.hpp"
#include "p2p/servers/relay/stop_protocol.hpp"
#include <thread>
#include <chrono>

using namespace p2p::relay::v2;

/**
 * Circuit Relay v2 Integration Tests
 *
 * These tests verify the end-to-end Circuit Relay v2 flow:
 * 1. Client reserves a slot (Hop RESERVE)
 * 2. Source connects through relay (Hop CONNECT)
 * 3. Destination accepts connection (Stop CONNECT)
 * 4. Data flows through relay
 */

class RelayV2IntegrationTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Create shared reservation manager
        reservation_mgr = std::make_shared<ReservationManager>(100, 3600, 1024 * 1024);

        // Create voucher manager
        voucher_mgr = std::make_shared<VoucherManager>("relay-peer-123");

        // Create protocol handlers
        hop_protocol = std::make_unique<HopProtocol>(reservation_mgr, voucher_mgr);
        stop_protocol = std::make_unique<StopProtocol>(reservation_mgr);
    }

    std::shared_ptr<ReservationManager> reservation_mgr;
    std::shared_ptr<VoucherManager> voucher_mgr;
    std::unique_ptr<HopProtocol> hop_protocol;
    std::unique_ptr<StopProtocol> stop_protocol;
};

TEST_F(RelayV2IntegrationTest, EndToEndReservationAndConnection) {
    // Step 1: Destination peer reserves a slot
    ReserveRequest reserve_req;
    reserve_req.peer_id = "destination-peer";
    reserve_req.addrs = {"dest-addr-1", "dest-addr-2"};

    auto reserve_resp = hop_protocol->HandleReserve(reserve_req);

    ASSERT_EQ(reserve_resp.status, StatusCode::OK);
    EXPECT_FALSE(reserve_resp.reservation.voucher.empty());
    EXPECT_GT(reserve_resp.reservation.expire_time, std::time(nullptr));

    // Step 2: Source peer connects through relay
    ConnectRequest connect_req;
    connect_req.peer_id = "destination-peer";
    connect_req.voucher = reserve_resp.reservation.voucher;

    auto connect_resp = hop_protocol->HandleConnect(connect_req);

    EXPECT_EQ(connect_resp.status, StatusCode::OK);

    // Step 3: Destination peer accepts connection
    StopConnectRequest stop_req;
    stop_req.peer_id = "destination-peer";
    stop_req.addrs = {"dest-addr-1"};

    auto stop_resp = stop_protocol->HandleConnect(stop_req);

    EXPECT_EQ(stop_resp.status, StatusCode::OK);
    ASSERT_NE(stop_resp.connection, nullptr);
}

TEST_F(RelayV2IntegrationTest, MultipleClientsReservation) {
    const int num_clients = 10;
    std::vector<ReservationSlot> reservations;

    // Multiple clients reserve slots
    for (int i = 0; i < num_clients; i++) {
        ReserveRequest req;
        req.peer_id = "peer-" + std::to_string(i);
        req.addrs = {"addr-" + std::to_string(i)};

        auto resp = hop_protocol->HandleReserve(req);

        ASSERT_EQ(resp.status, StatusCode::OK);
        reservations.push_back(resp.reservation);
    }

    // Verify all reservations are stored
    EXPECT_EQ(reservation_mgr->GetCount(), num_clients);

    // Each client can connect
    for (int i = 0; i < num_clients; i++) {
        ConnectRequest req;
        req.peer_id = "peer-" + std::to_string(i);
        req.voucher = reservations[i].voucher;

        auto resp = hop_protocol->HandleConnect(req);
        EXPECT_EQ(resp.status, StatusCode::OK);
    }
}

TEST_F(RelayV2IntegrationTest, ReservationExpiration) {
    // Create a reservation with very short expiration
    ReservationSlot slot;
    slot.peer_id = "short-lived-peer";
    slot.relay_addr = "relay-addr";
    slot.expire_time = std::time(nullptr) + 1;  // Expires in 1 second
    slot.limit_duration = 1;
    slot.limit_data = 1024;

    reservation_mgr->Store(slot);
    EXPECT_EQ(reservation_mgr->GetCount(), 1);

    // Wait for expiration
    std::this_thread::sleep_for(std::chrono::seconds(2));

    // Cleanup expired reservations
    size_t removed = reservation_mgr->CleanupExpired();
    EXPECT_EQ(removed, 1);
    EXPECT_EQ(reservation_mgr->GetCount(), 0);

    // Try to connect with expired reservation
    ConnectRequest req;
    req.peer_id = "short-lived-peer";

    auto resp = hop_protocol->HandleConnect(req);
    EXPECT_EQ(resp.status, StatusCode::NO_RESERVATION);
}

TEST_F(RelayV2IntegrationTest, ResourceLimitEnforcement) {
    // Fill up to max reservations
    const size_t max_reservations = 100;

    for (size_t i = 0; i < max_reservations; i++) {
        ReserveRequest req;
        req.peer_id = "peer-" + std::to_string(i);

        auto resp = hop_protocol->HandleReserve(req);
        EXPECT_EQ(resp.status, StatusCode::OK);
    }

    EXPECT_EQ(reservation_mgr->GetCount(), max_reservations);
    EXPECT_FALSE(reservation_mgr->CanAcceptReservation());

    // Try to reserve one more - should fail
    ReserveRequest extra_req;
    extra_req.peer_id = "peer-extra";

    auto extra_resp = hop_protocol->HandleReserve(extra_req);
    EXPECT_EQ(extra_resp.status, StatusCode::RESOURCE_LIMIT_EXCEEDED);
}

TEST_F(RelayV2IntegrationTest, ConcurrentReservations) {
    const int num_threads = 5;
    const int reservations_per_thread = 10;
    std::vector<std::thread> threads;
    std::atomic<int> success_count{0};

    for (int t = 0; t < num_threads; t++) {
        threads.emplace_back([&, t]() {
            for (int i = 0; i < reservations_per_thread; i++) {
                ReserveRequest req;
                req.peer_id = "thread-" + std::to_string(t) + "-peer-" + std::to_string(i);

                auto resp = hop_protocol->HandleReserve(req);
                if (resp.status == StatusCode::OK) {
                    success_count++;
                }
            }
        });
    }

    for (auto& thread : threads) {
        thread.join();
    }

    EXPECT_EQ(success_count, num_threads * reservations_per_thread);
    EXPECT_EQ(reservation_mgr->GetCount(), num_threads * reservations_per_thread);
}

TEST_F(RelayV2IntegrationTest, HopAndStopProtocolIntegration) {
    // Destination reserves
    ReserveRequest reserve_req;
    reserve_req.peer_id = "dest-peer";
    auto reserve_resp = hop_protocol->HandleReserve(reserve_req);
    ASSERT_EQ(reserve_resp.status, StatusCode::OK);

    // Source connects via Hop
    ConnectRequest hop_connect_req;
    hop_connect_req.peer_id = "dest-peer";
    hop_connect_req.voucher = reserve_resp.reservation.voucher;
    auto hop_connect_resp = hop_protocol->HandleConnect(hop_connect_req);
    EXPECT_EQ(hop_connect_resp.status, StatusCode::OK);

    // Destination accepts via Stop
    auto stop_resp = stop_protocol->AcceptConnection("dest-peer", "source-peer");
    EXPECT_EQ(stop_resp.status, StatusCode::OK);
    ASSERT_NE(stop_resp.connection, nullptr);

    // Verify connection properties
    EXPECT_EQ(stop_resp.connection->GetType(), "active");
    EXPECT_EQ(stop_resp.connection->GetPeerId(), "source-peer");
}

TEST_F(RelayV2IntegrationTest, VoucherLifecycle) {
    // Reserve and get voucher
    ReserveRequest req;
    req.peer_id = "peer123";
    auto resp = hop_protocol->HandleReserve(req);
    ASSERT_EQ(resp.status, StatusCode::OK);

    auto voucher = resp.reservation.voucher;
    EXPECT_FALSE(voucher.empty());

    // Verify voucher is valid
    bool valid = voucher_mgr->VerifyVoucher(voucher, "peer123");
    EXPECT_TRUE(valid);

    // Use voucher to connect
    ConnectRequest connect_req;
    connect_req.peer_id = "peer123";
    connect_req.voucher = voucher;
    auto connect_resp = hop_protocol->HandleConnect(connect_req);
    EXPECT_EQ(connect_resp.status, StatusCode::OK);

    // Voucher should still be valid for the same peer
    valid = voucher_mgr->VerifyVoucher(voucher, "peer123");
    EXPECT_TRUE(valid);

    // Voucher should not be valid for different peer
    valid = voucher_mgr->VerifyVoucher(voucher, "different-peer");
    EXPECT_FALSE(valid);
}

TEST_F(RelayV2IntegrationTest, ConnectionDataFlow) {
    // Setup connection
    ReserveRequest reserve_req;
    reserve_req.peer_id = "peer123";
    auto reserve_resp = hop_protocol->HandleReserve(reserve_req);

    auto stop_resp = stop_protocol->AcceptConnection("peer123", "source-peer");
    ASSERT_NE(stop_resp.connection, nullptr);

    auto conn = stop_resp.connection;

    // Test data send
    std::vector<uint8_t> test_data = {1, 2, 3, 4, 5, 6, 7, 8};
    bool sent = conn->Send(test_data);
    EXPECT_TRUE(sent);

    // Test empty data
    std::vector<uint8_t> empty_data;
    sent = conn->Send(empty_data);
    EXPECT_FALSE(sent);

    // Test receive (mock connection echoes back sent data)
    auto received = conn->Receive();
    EXPECT_EQ(received, test_data);  // Echo back for testing

    // Test close
    conn->Close();
}

TEST_F(RelayV2IntegrationTest, ReservationCleanupUnderLoad) {
    // Create mix of valid and expired reservations
    for (int i = 0; i < 50; i++) {
        ReservationSlot slot;
        slot.peer_id = "peer-" + std::to_string(i);
        slot.relay_addr = "relay-addr";

        // Half expired, half valid
        if (i % 2 == 0) {
            slot.expire_time = std::time(nullptr) - 1;  // Expired
        } else {
            slot.expire_time = std::time(nullptr) + 3600;  // Valid
        }

        reservation_mgr->Store(slot);
    }

    EXPECT_EQ(reservation_mgr->GetCount(), 50);

    // Cleanup expired
    size_t removed = reservation_mgr->CleanupExpired();
    EXPECT_EQ(removed, 25);
    EXPECT_EQ(reservation_mgr->GetCount(), 25);

    // Verify only valid reservations remain
    for (int i = 0; i < 50; i++) {
        std::string peer_id = "peer-" + std::to_string(i);
        auto reservation = reservation_mgr->Lookup(peer_id);

        if (i % 2 == 0) {
            EXPECT_FALSE(reservation.has_value());  // Expired should be gone
        } else {
            EXPECT_TRUE(reservation.has_value());   // Valid should remain
        }
    }
}

// Performance test
TEST_F(RelayV2IntegrationTest, ReservationPerformance) {
    const int num_operations = 1000;

    auto start = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < num_operations; i++) {
        ReserveRequest req;
        req.peer_id = "perf-peer-" + std::to_string(i);
        hop_protocol->HandleReserve(req);
    }

    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);

    double avg_time_us = static_cast<double>(duration.count()) / num_operations;

    std::cout << "Average reservation time: " << avg_time_us << " μs" << std::endl;

    // Should be fast (< 100 μs per reservation)
    EXPECT_LT(avg_time_us, 100.0);
}

TEST_F(RelayV2IntegrationTest, VoucherVerificationPerformance) {
    // Create a voucher
    auto voucher = voucher_mgr->SignVoucher("peer123", std::time(nullptr) + 3600);

    const int num_verifications = 10000;

    auto start = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < num_verifications; i++) {
        voucher_mgr->VerifyVoucher(voucher, "peer123");
    }

    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start);

    double avg_time_ns = static_cast<double>(duration.count()) / num_verifications;

    std::cout << "Average voucher verification time: " << avg_time_ns << " ns" << std::endl;

    // Should be reasonably fast (< 100000 ns = 100 μs per verification)
    EXPECT_LT(avg_time_ns, 100000.0);
}
