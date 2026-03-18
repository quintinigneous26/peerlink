find_package(GTest REQUIRED)

# Protocol tests (if exists)
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/test_protocol.cpp)
    add_executable(test_protocol test_protocol.cpp)
    target_link_libraries(test_protocol
        PRIVATE
            p2p_protocol
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME ProtocolTest COMMAND test_protocol)
endif()

# Transport tests (if exists)
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/test_transport.cpp)
    add_executable(test_transport test_transport.cpp)
    target_link_libraries(test_transport
        PRIVATE
            p2p_transport
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME TransportTest COMMAND test_transport)
endif()

# NAT tests (if exists)
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/test_nat.cpp)
    add_executable(test_nat test_nat.cpp)
    target_compile_definitions(test_nat PRIVATE TESTING)
    target_link_libraries(test_nat
        PRIVATE
            p2p_nat
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME NATTest COMMAND test_nat)
endif()

# Core client tests (if exists)
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/test_client.cpp)
    add_executable(test_client test_client.cpp)
    target_link_libraries(test_client
        PRIVATE
            p2p_core
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME ClientTest COMMAND test_client)
endif()

# Varint tests
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/test_varint.cpp)
    add_executable(test_varint test_varint.cpp)
    target_link_libraries(test_varint
        PRIVATE
            p2p_core
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME VarintTest COMMAND test_varint)
endif()

# Multiaddr tests
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/test_multiaddr.cpp)
    add_executable(test_multiaddr test_multiaddr.cpp)
    target_link_libraries(test_multiaddr
        PRIVATE
            p2p_core
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME MultiaddrTest COMMAND test_multiaddr)
endif()

# Crypto tests
add_subdirectory(crypto)

# Net tests
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/net/CMakeLists.txt)
    add_subdirectory(net)
endif()

# DCUtR protocol tests
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/protocol/test_dcutr.cpp)
    add_executable(test_dcutr protocol/test_dcutr.cpp)
    target_link_libraries(test_dcutr
        PRIVATE
            p2p_protocol
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME DCUtRTest COMMAND test_dcutr)
endif()

# Protocol negotiator tests
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/protocol/test_negotiator.cpp)
    add_executable(test_negotiator protocol/test_negotiator.cpp)
    target_link_libraries(test_negotiator
        PRIVATE
            p2p_protocol
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME NegotiatorTest COMMAND test_negotiator)
endif()

# Message wrapper tests
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/protocol/test_message_wrapper.cpp)
    add_executable(test_message_wrapper protocol/test_message_wrapper.cpp)
    target_link_libraries(test_message_wrapper
        PRIVATE
            p2p_protocol
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME MessageWrapperTest COMMAND test_message_wrapper)
endif()

# NAT puncher tests
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/nat/test_puncher.cpp)
    add_executable(test_puncher nat/test_puncher.cpp)
    target_link_libraries(test_puncher
        PRIVATE
            p2p_nat
            p2p_protocol
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME PuncherTest COMMAND test_puncher)
endif()

# Hop protocol tests
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/relay/test_hop_protocol.cpp)
    add_executable(test_hop_protocol relay/test_hop_protocol.cpp)
    target_link_libraries(test_hop_protocol
        PRIVATE
            relay_server
            p2p-crypto
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME HopProtocolTest COMMAND test_hop_protocol)
endif()

# Stop protocol tests
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/relay/test_stop_protocol.cpp)
    add_executable(test_stop_protocol relay/test_stop_protocol.cpp)
    target_link_libraries(test_stop_protocol
        PRIVATE
            relay_server
            p2p-crypto
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME StopProtocolTest COMMAND test_stop_protocol)
endif()

# Forwarder tests
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/relay/test_forwarder.cpp)
    add_executable(test_forwarder relay/test_forwarder.cpp)
    target_link_libraries(test_forwarder
        PRIVATE
            relay_server
            p2p-crypto
            GTest::gtest
            GTest::gtest_main
    )
    add_test(NAME ForwarderTest COMMAND test_forwarder)
endif()

