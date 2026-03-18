# Examples CMakeLists.txt
cmake_minimum_required(VERSION 3.20)

# Simple client example
add_executable(simple-client
    simple_client.cpp
)

target_link_libraries(simple-client
    PRIVATE
        Boost::system
        Threads::Threads
        nlohmann_json::nlohmann_json
)