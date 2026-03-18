#include <gtest/gtest.h>
#include "p2p/transport/udp_transport.hpp"
#include <boost/asio.hpp>
#include <thread>
#include <chrono>

using namespace p2p::transport;
using boost::asio::ip::udp;

class UDPTransportTest : public ::testing::Test {
protected:
    std::unique_ptr<boost::asio::io_context> io_context_;
    std::thread io_thread_;

    void SetUp() override {
        io_context_ = std::make_unique<boost::asio::io_context>();
    }

    void TearDown() override {
        if (io_context_) {
            io_context_->stop();
        }
        if (io_thread_.joinable()) {
            io_thread_.join();
        }
    }

    void run_io_context() {
        io_thread_ = std::thread([this]() {
            io_context_->run();
        });
    }
};

TEST_F(UDPTransportTest, Construction) {
    auto transport = std::make_shared<UDPTransport>(*io_context_, 0);
    EXPECT_NE(transport, nullptr);

    // Should have a valid local endpoint
    auto local_ep = transport->local_endpoint();
    EXPECT_GT(local_ep.port(), 0);
}

TEST_F(UDPTransportTest, StartStop) {
    auto transport = std::make_shared<UDPTransport>(*io_context_, 0);

    std::error_code ec;
    transport->start(ec);
    EXPECT_FALSE(ec);

    transport->stop();
}

TEST_F(UDPTransportTest, DoubleStart) {
    auto transport = std::make_shared<UDPTransport>(*io_context_, 0);

    std::error_code ec1;
    transport->start(ec1);
    EXPECT_FALSE(ec1);

    // Second start should fail
    std::error_code ec2;
    transport->start(ec2);
    EXPECT_TRUE(ec2);
    EXPECT_EQ(ec2, std::errc::already_connected);

    transport->stop();
}

TEST_F(UDPTransportTest, SendReceive) {
    auto transport1 = std::make_shared<UDPTransport>(*io_context_, 0);
    auto transport2 = std::make_shared<UDPTransport>(*io_context_, 0);

    std::error_code ec;
    transport1->start(ec);
    ASSERT_FALSE(ec);

    transport2->start(ec);
    ASSERT_FALSE(ec);

    // Set up receive callback
    std::vector<uint8_t> received_data;
    udp::endpoint received_from;
    bool received = false;

    transport2->set_receive_callback(
        [&](const std::vector<uint8_t>& data, const udp::endpoint& from) {
            received_data = data;
            received_from = from;
            received = true;
        }
    );

    // Start IO context AFTER setting up everything
    run_io_context();

    // Give io_context time to start
    std::this_thread::sleep_for(std::chrono::milliseconds(50));

    // Send data
    std::vector<uint8_t> test_data = {1, 2, 3, 4, 5};
    bool send_complete = false;

    // Create localhost endpoint with transport2's port
    auto target_endpoint = udp::endpoint(
        boost::asio::ip::make_address("127.0.0.1"),
        transport2->local_endpoint().port()
    );

    transport1->send_to(
        test_data,
        target_endpoint,
        [&](std::error_code ec) {
            EXPECT_FALSE(ec);
            send_complete = true;
        }
    );

    // Wait for send and receive
    for (int i = 0; i < 100 && (!send_complete || !received); ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    EXPECT_TRUE(send_complete);
    EXPECT_TRUE(received);
    EXPECT_EQ(received_data, test_data);

    transport1->stop();
    transport2->stop();
}

TEST_F(UDPTransportTest, SendWithoutPeer) {
    auto transport = std::make_shared<UDPTransport>(*io_context_, 0);

    std::error_code ec;
    transport->start(ec);
    ASSERT_FALSE(ec);

    // Send without setting peer should fail
    std::vector<uint8_t> test_data = {1, 2, 3};
    bool callback_called = false;
    std::error_code send_ec;

    transport->send(test_data, [&](std::error_code ec) {
        callback_called = true;
        send_ec = ec;
    });

    run_io_context();

    // Wait for callback
    for (int i = 0; i < 10 && !callback_called; ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    EXPECT_TRUE(callback_called);
    EXPECT_TRUE(send_ec);
    EXPECT_EQ(send_ec, std::errc::destination_address_required);

    transport->stop();
}

TEST_F(UDPTransportTest, SendWithPeer) {
    auto transport1 = std::make_shared<UDPTransport>(*io_context_, 0);
    auto transport2 = std::make_shared<UDPTransport>(*io_context_, 0);

    std::error_code ec;
    transport1->start(ec);
    ASSERT_FALSE(ec);

    transport2->start(ec);
    ASSERT_FALSE(ec);

    // Set peer with localhost address
    auto peer_endpoint = udp::endpoint(
        boost::asio::ip::make_address("127.0.0.1"),
        transport2->local_endpoint().port()
    );
    transport1->set_peer(peer_endpoint);

    // Set up receive callback
    bool received = false;
    transport2->set_receive_callback(
        [&](const std::vector<uint8_t>&, const udp::endpoint&) {
            received = true;
        }
    );

    run_io_context();

    // Give io_context time to start
    std::this_thread::sleep_for(std::chrono::milliseconds(50));

    // Send using send() instead of send_to()
    std::vector<uint8_t> test_data = {1, 2, 3};
    bool send_complete = false;

    transport1->send(test_data, [&](std::error_code ec) {
        EXPECT_FALSE(ec);
        send_complete = true;
    });

    // Wait
    for (int i = 0; i < 100 && (!send_complete || !received); ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    EXPECT_TRUE(send_complete);
    EXPECT_TRUE(received);

    transport1->stop();
    transport2->stop();
}

TEST_F(UDPTransportTest, LargePacket) {
    auto transport1 = std::make_shared<UDPTransport>(*io_context_, 0);
    auto transport2 = std::make_shared<UDPTransport>(*io_context_, 0);

    std::error_code ec;
    transport1->start(ec);
    ASSERT_FALSE(ec);

    transport2->start(ec);
    ASSERT_FALSE(ec);

    // Set up receive callback
    std::vector<uint8_t> received_data;
    bool received = false;

    transport2->set_receive_callback(
        [&](const std::vector<uint8_t>& data, const udp::endpoint&) {
            received_data = data;
            received = true;
        }
    );

    run_io_context();

    // Give io_context time to start
    std::this_thread::sleep_for(std::chrono::milliseconds(50));

    // Send large packet (within typical MTU limits - use 8KB which is safe)
    std::vector<uint8_t> large_data(8000, 0xAB);
    bool send_complete = false;

    auto target_endpoint = udp::endpoint(
        boost::asio::ip::make_address("127.0.0.1"),
        transport2->local_endpoint().port()
    );

    transport1->send_to(
        large_data,
        target_endpoint,
        [&](std::error_code ec) {
            send_complete = true;
        }
    );

    // Wait
    for (int i = 0; i < 100 && (!send_complete || !received); ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    EXPECT_TRUE(send_complete);
    EXPECT_TRUE(received);
    EXPECT_EQ(received_data.size(), 8000);
    EXPECT_EQ(received_data[0], 0xAB);

    transport1->stop();
    transport2->stop();
}

TEST_F(UDPTransportTest, MultipleMessages) {
    auto transport1 = std::make_shared<UDPTransport>(*io_context_, 0);
    auto transport2 = std::make_shared<UDPTransport>(*io_context_, 0);

    std::error_code ec;
    transport1->start(ec);
    ASSERT_FALSE(ec);

    transport2->start(ec);
    ASSERT_FALSE(ec);

    // Set up receive callback
    int received_count = 0;
    transport2->set_receive_callback(
        [&](const std::vector<uint8_t>&, const udp::endpoint&) {
            received_count++;
        }
    );

    run_io_context();

    // Give io_context time to start
    std::this_thread::sleep_for(std::chrono::milliseconds(50));

    // Send multiple messages
    const int num_messages = 10;
    int send_count = 0;

    auto target_endpoint = udp::endpoint(
        boost::asio::ip::make_address("127.0.0.1"),
        transport2->local_endpoint().port()
    );

    for (int i = 0; i < num_messages; ++i) {
        std::vector<uint8_t> data = {static_cast<uint8_t>(i)};
        transport1->send_to(
            data,
            target_endpoint,
            [&](std::error_code) {
                send_count++;
            }
        );
    }

    // Wait
    for (int i = 0; i < 200 && (send_count < num_messages || received_count < num_messages); ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    EXPECT_EQ(send_count, num_messages);
    EXPECT_EQ(received_count, num_messages);

    transport1->stop();
    transport2->stop();
}

TEST_F(UDPTransportTest, SendAfterStop) {
    auto transport = std::make_shared<UDPTransport>(*io_context_, 0);

    std::error_code ec;
    transport->start(ec);
    ASSERT_FALSE(ec);

    transport->stop();

    // Send after stop should fail
    std::vector<uint8_t> test_data = {1, 2, 3};
    bool callback_called = false;
    std::error_code send_ec;

    transport->send_to(
        test_data,
        udp::endpoint(udp::v4(), 12345),
        [&](std::error_code ec) {
            callback_called = true;
            send_ec = ec;
        }
    );

    EXPECT_TRUE(callback_called);
    EXPECT_TRUE(send_ec);
    EXPECT_EQ(send_ec, std::errc::not_connected);
}

TEST_F(UDPTransportTest, LocalEndpoint) {
    auto transport = std::make_shared<UDPTransport>(*io_context_, 12345);

    auto local_ep = transport->local_endpoint();
    EXPECT_EQ(local_ep.port(), 12345);
}

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
