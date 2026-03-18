#include <gtest/gtest.h>
#include "p2p/servers/relay/hop_protocol.hpp"
#include <thread>
#include <chrono>

using namespace p2p::relay::v2;

class ReservationManagerTest : public ::testing::Test {
protected:
    void SetUp() override {
        manager = std::make_unique<ReservationManager>(10, 3600, 1024 * 1024);
    }

    std::unique_ptr<ReservationManager> manager;
};

TEST_F(ReservationManagerTest, StoreAndLookup) {
    ReservationSlot slot;
    slot.peer_id = "peer123";
    slot.relay_addr = "relay-addr";
    slot.expire_time = std::time(nullptr) + 3600;
    slot.limit_duration = 3600;
    slot.limit_data = 1024 * 1024;

    EXPECT_TRUE(manager->Store(slot));
    EXPECT_EQ(manager->GetCount(), 1);

    auto result = manager->Lookup("peer123");
    ASSERT_TRUE(result.has_value());
    EXPECT_EQ(result->peer_id, "peer123");
    EXPECT_EQ(result->relay_addr, "relay-addr");
}

TEST_F(ReservationManagerTest, LookupNonExistent) {
    auto result = manager->Lookup("nonexistent");
    EXPECT_FALSE(result.has_value());
}

TEST_F(ReservationManagerTest, Remove) {
    ReservationSlot slot;
    slot.peer_id = "peer123";
    slot.expire_time = std::time(nullptr) + 3600;

    manager->Store(slot);
    EXPECT_EQ(manager->GetCount(), 1);

    manager->Remove("peer123");
    EXPECT_EQ(manager->GetCount(), 0);

    auto result = manager->Lookup("peer123");
    EXPECT_FALSE(result.has_value());
}

TEST_F(ReservationManagerTest, MaxReservations) {
    // Fill up to max
    for (size_t i = 0; i < 10; i++) {
        ReservationSlot slot;
        slot.peer_id = "peer" + std::to_string(i);
        slot.expire_time = std::time(nullptr) + 3600;
        EXPECT_TRUE(manager->Store(slot));
    }

    EXPECT_EQ(manager->GetCount(), 10);
    EXPECT_FALSE(manager->CanAcceptReservation());

    // Try to add one more
    ReservationSlot extra;
    extra.peer_id = "peer_extra";
    extra.expire_time = std::time(nullptr) + 3600;
    EXPECT_FALSE(manager->Store(extra));
}

TEST_F(ReservationManagerTest, CleanupExpired) {
    // Add expired reservation
    ReservationSlot expired;
    expired.peer_id = "expired";
    expired.expire_time = std::time(nullptr) - 1;  // Already expired
    manager->Store(expired);

    // Add valid reservation
    ReservationSlot valid;
    valid.peer_id = "valid";
    valid.expire_time = std::time(nullptr) + 3600;
    manager->Store(valid);

    EXPECT_EQ(manager->GetCount(), 2);

    size_t removed = manager->CleanupExpired();
    EXPECT_EQ(removed, 1);
    EXPECT_EQ(manager->GetCount(), 1);

    // Expired should be gone
    EXPECT_FALSE(manager->Lookup("expired").has_value());
    // Valid should still be there
    EXPECT_TRUE(manager->Lookup("valid").has_value());
}

TEST_F(ReservationManagerTest, LookupExpiredReturnsNullopt) {
    ReservationSlot slot;
    slot.peer_id = "peer123";
    slot.expire_time = std::time(nullptr) - 1;  // Already expired
    manager->Store(slot);

    // Lookup should return nullopt and remove the expired entry
    auto result = manager->Lookup("peer123");
    EXPECT_FALSE(result.has_value());
    EXPECT_EQ(manager->GetCount(), 0);
}

class VoucherManagerTest : public ::testing::Test {
protected:
    void SetUp() override {
        manager = std::make_unique<VoucherManager>("relay-peer-123");
    }

    std::unique_ptr<VoucherManager> manager;
};

TEST_F(VoucherManagerTest, SignAndVerify) {
    std::string peer_id = "peer456";
    uint64_t expiration = std::time(nullptr) + 3600;

    auto voucher = manager->SignVoucher(peer_id, expiration);
    EXPECT_FALSE(voucher.empty());

    bool valid = manager->VerifyVoucher(voucher, peer_id);
    EXPECT_TRUE(valid);
}

TEST_F(VoucherManagerTest, VerifyWithWrongPeerId) {
    std::string peer_id = "peer456";
    uint64_t expiration = std::time(nullptr) + 3600;

    auto voucher = manager->SignVoucher(peer_id, expiration);

    bool valid = manager->VerifyVoucher(voucher, "wrong-peer");
    EXPECT_FALSE(valid);
}

TEST_F(VoucherManagerTest, VerifyExpiredVoucher) {
    std::string peer_id = "peer456";
    uint64_t expiration = std::time(nullptr) - 1;  // Already expired

    auto voucher = manager->SignVoucher(peer_id, expiration);

    // Wait a bit to ensure it's expired
    std::this_thread::sleep_for(std::chrono::milliseconds(10));

    bool valid = manager->VerifyVoucher(voucher, peer_id);
    EXPECT_FALSE(valid);
}

TEST_F(VoucherManagerTest, VerifyInvalidVoucher) {
    std::vector<uint8_t> invalid_voucher = {1, 2, 3, 4, 5};

    bool valid = manager->VerifyVoucher(invalid_voucher, "peer456");
    EXPECT_FALSE(valid);
}

class HopProtocolTest : public ::testing::Test {
protected:
    void SetUp() override {
        reservation_mgr = std::make_shared<ReservationManager>(10, 3600, 1024 * 1024);
        voucher_mgr = std::make_shared<VoucherManager>("relay-peer-123");
        hop_protocol = std::make_unique<HopProtocol>(reservation_mgr, voucher_mgr);
    }

    std::shared_ptr<ReservationManager> reservation_mgr;
    std::shared_ptr<VoucherManager> voucher_mgr;
    std::unique_ptr<HopProtocol> hop_protocol;
};

TEST_F(HopProtocolTest, GetProtocolID) {
    EXPECT_EQ(HopProtocol::GetProtocolID(), "/libp2p/circuit/relay/0.2.0/hop");
}

TEST_F(HopProtocolTest, HandleReserveSuccess) {
    ReserveRequest request;
    request.peer_id = "peer123";
    request.addrs = {"addr1", "addr2"};

    auto response = hop_protocol->HandleReserve(request);

    EXPECT_EQ(response.status, StatusCode::OK);
    EXPECT_EQ(response.reservation.peer_id, "peer123");
    EXPECT_GT(response.reservation.expire_time, std::time(nullptr));
    EXPECT_FALSE(response.reservation.voucher.empty());
}

TEST_F(HopProtocolTest, HandleReserveResourceLimit) {
    // Fill up reservations
    for (size_t i = 0; i < 10; i++) {
        ReserveRequest request;
        request.peer_id = "peer" + std::to_string(i);
        hop_protocol->HandleReserve(request);
    }

    // Try one more
    ReserveRequest request;
    request.peer_id = "peer_extra";
    auto response = hop_protocol->HandleReserve(request);

    EXPECT_EQ(response.status, StatusCode::RESOURCE_LIMIT_EXCEEDED);
}

TEST_F(HopProtocolTest, HandleConnectSuccess) {
    // First create a reservation
    ReserveRequest reserve_req;
    reserve_req.peer_id = "peer123";
    auto reserve_resp = hop_protocol->HandleReserve(reserve_req);
    ASSERT_EQ(reserve_resp.status, StatusCode::OK);

    // Now connect
    ConnectRequest connect_req;
    connect_req.peer_id = "peer123";
    connect_req.voucher = reserve_resp.reservation.voucher;

    auto connect_resp = hop_protocol->HandleConnect(connect_req);

    EXPECT_EQ(connect_resp.status, StatusCode::OK);
}

TEST_F(HopProtocolTest, HandleConnectNoReservation) {
    ConnectRequest request;
    request.peer_id = "nonexistent";

    auto response = hop_protocol->HandleConnect(request);

    EXPECT_EQ(response.status, StatusCode::NO_RESERVATION);
}

TEST_F(HopProtocolTest, HandleConnectInvalidVoucher) {
    // Create a reservation
    ReserveRequest reserve_req;
    reserve_req.peer_id = "peer123";
    hop_protocol->HandleReserve(reserve_req);

    // Try to connect with invalid voucher
    ConnectRequest connect_req;
    connect_req.peer_id = "peer123";
    connect_req.voucher = {1, 2, 3, 4, 5};  // Invalid voucher

    auto response = hop_protocol->HandleConnect(connect_req);

    EXPECT_EQ(response.status, StatusCode::PERMISSION_DENIED);
}
