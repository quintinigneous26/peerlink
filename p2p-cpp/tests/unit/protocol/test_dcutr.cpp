#include <gtest/gtest.h>
#include "p2p/protocol/dcutr.hpp"
#include <thread>
#include <chrono>

using namespace p2p::protocol;

class DCUtRCoordinatorTest : public ::testing::Test {
protected:
    DCUtRCoordinator coordinator;
};

TEST_F(DCUtRCoordinatorTest, MeasureRTT) {
    // Simulate timing: t1=0, t4=1000, t2=200, t3=800
    int64_t t1 = 0;
    int64_t t4 = 1000000000LL;  // 1 second in ns
    int64_t t2 = 200000000LL;   // 200ms
    int64_t t3 = 800000000LL;   // 800ms

    int64_t rtt = coordinator.MeasureRTT(t1, t4, t2, t3);

    // RTT should be approximately t4 - t1 = 1000ms
    EXPECT_EQ(rtt, 1000000000LL);
}

TEST_F(DCUtRCoordinatorTest, MeasureRTTNegative) {
    // Invalid timing (t4 < t1)
    int64_t t1 = 1000000000LL;
    int64_t t4 = 0;
    int64_t t2 = 200000000LL;
    int64_t t3 = 800000000LL;

    EXPECT_THROW(coordinator.MeasureRTT(t1, t4, t2, t3), std::runtime_error);
}

TEST_F(DCUtRCoordinatorTest, CalculateInitiatorSchedule) {
    int64_t t4 = 1000000000LL;  // 1 second
    int64_t rtt = 100000000LL;  // 100ms
    std::vector<Address> addrs = {{1, 2, 3}};

    PunchSchedule schedule = coordinator.CalculateInitiatorSchedule(
        t4, rtt, addrs);

    // punch_time = t4 + RTT + buffer (100ms)
    int64_t expected = t4 + rtt + (PUNCH_BUFFER_MS * 1000000LL);
    EXPECT_EQ(schedule.punch_time_ns, expected);
    EXPECT_EQ(schedule.rtt_ns, rtt);
    EXPECT_EQ(schedule.target_addrs, addrs);
}

TEST_F(DCUtRCoordinatorTest, CalculateResponderSchedule) {
    int64_t t3 = 800000000LL;   // 800ms
    int64_t rtt = 100000000LL;  // 100ms
    std::vector<Address> addrs = {{4, 5, 6}};

    PunchSchedule schedule = coordinator.CalculateResponderSchedule(
        t3, rtt, addrs);

    // punch_time = t3 + RTT + buffer
    int64_t expected = t3 + rtt + (PUNCH_BUFFER_MS * 1000000LL);
    EXPECT_EQ(schedule.punch_time_ns, expected);
}

class DCUtRSessionTest : public ::testing::Test {
protected:
    std::string peer_id = "peer123";
    std::vector<Address> local_addrs = {{1, 2, 3}, {4, 5, 6}};
};

TEST_F(DCUtRSessionTest, InitiatorStart) {
    DCUtRSession session(true, peer_id);
    EXPECT_EQ(session.GetState(), DCUtRState::IDLE);

    session.Start(local_addrs);
    EXPECT_EQ(session.GetState(), DCUtRState::CONNECT_SENT);
}

TEST_F(DCUtRSessionTest, InitiatorGetConnectMessage) {
    DCUtRSession session(true, peer_id);
    session.Start(local_addrs);

    ConnectMessage msg = session.GetConnectMessage();
    EXPECT_EQ(msg.addrs, local_addrs);
    EXPECT_GT(msg.timestamp_ns, 0);
}

TEST_F(DCUtRSessionTest, ResponderOnConnectReceived) {
    DCUtRSession session(false, peer_id);

    ConnectMessage connect_msg;
    connect_msg.addrs = {{7, 8, 9}};
    connect_msg.timestamp_ns = 1000000000LL;

    session.OnConnectReceived(connect_msg);
    EXPECT_EQ(session.GetState(), DCUtRState::SYNC_RECEIVED);

    // Should have punch schedule
    auto schedule = session.GetPunchSchedule();
    EXPECT_TRUE(schedule.has_value());
}

TEST_F(DCUtRSessionTest, ResponderGetSyncMessage) {
    DCUtRSession session(false, peer_id);

    ConnectMessage connect_msg;
    connect_msg.addrs = {{7, 8, 9}};
    connect_msg.timestamp_ns = 1000000000LL;

    session.OnConnectReceived(connect_msg);

    SyncMessage sync_msg = session.GetSyncMessage();
    EXPECT_GT(sync_msg.echo_timestamp_ns, 0);
    EXPECT_GT(sync_msg.timestamp_ns, 0);
}

TEST_F(DCUtRSessionTest, InitiatorOnSyncReceived) {
    DCUtRSession session(true, peer_id);
    session.Start(local_addrs);

    // Simulate receiving SYNC
    SyncMessage sync_msg;
    sync_msg.addrs = {{7, 8, 9}};
    sync_msg.echo_timestamp_ns = 1000000000LL;
    sync_msg.timestamp_ns = 1100000000LL;

    session.OnSyncReceived(sync_msg);
    EXPECT_EQ(session.GetState(), DCUtRState::PUNCHING);

    // Should have punch schedule
    auto schedule = session.GetPunchSchedule();
    EXPECT_TRUE(schedule.has_value());
}

class DCUtRClientTest : public ::testing::Test {
protected:
    DCUtRClient client;
    std::string peer_id = "peer123";
    std::vector<Address> local_addrs = {{1, 2, 3}};
};

TEST_F(DCUtRClientTest, InitiateUpgrade) {
    auto session = client.InitiateUpgrade(peer_id, local_addrs);

    ASSERT_NE(session, nullptr);
    EXPECT_EQ(session->GetState(), DCUtRState::CONNECT_SENT);
}

TEST_F(DCUtRClientTest, RespondToUpgrade) {
    ConnectMessage connect_msg;
    connect_msg.addrs = {{7, 8, 9}};
    connect_msg.timestamp_ns = 1000000000LL;

    auto session = client.RespondToUpgrade(peer_id, local_addrs, connect_msg);

    ASSERT_NE(session, nullptr);
    EXPECT_EQ(session->GetState(), DCUtRState::SYNC_RECEIVED);
}

TEST_F(DCUtRClientTest, ExecuteCoordinatedPunch) {
    PunchSchedule schedule;
    schedule.punch_time_ns = std::chrono::high_resolution_clock::now()
        .time_since_epoch().count() + 10000000LL;  // 10ms from now
    schedule.target_addrs = {{1, 2, 3}};
    schedule.rtt_ns = 50000000LL;

    bool callback_called = false;
    client.ExecuteCoordinatedPunch(schedule, [&](bool success, const std::string& error) {
        callback_called = true;
        EXPECT_TRUE(success);
        EXPECT_TRUE(error.empty());
    });

    EXPECT_TRUE(callback_called);
}
