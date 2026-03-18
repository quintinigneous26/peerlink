# Tests CMakeLists.txt
cmake_minimum_required(VERSION 3.20)

# Find GTest (optional)
find_package(GTest QUIET)

if(GTest_FOUND)
    add_executable(signaling-server-tests
        test_models.cpp
        test_connection_manager.cpp
    )

    target_link_libraries(signaling-server-tests
        PRIVATE
            signaling-server-lib
            GTest::gtest
            GTest::gtest_main
    )

    add_test(NAME signaling-server-tests COMMAND signaling-server-tests)
else()
    message(STATUS "GTest not found, skipping tests")
endif()