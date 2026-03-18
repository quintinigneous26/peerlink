cmake_minimum_required(VERSION 3.20)
project(signaling-server-cpp VERSION 0.1.0 LANGUAGES CXX)

# C++20 required for coroutines
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Compiler warnings
if(MSVC)
    add_compile_options(/W4 /WX)
else()
    add_compile_options(-Wall -Wextra -Wpedantic -Werror)
endif()

# Find dependencies
find_package(Boost 1.75 REQUIRED COMPONENTS system)
find_package(Threads REQUIRED)

# nlohmann/json (header-only)
include(FetchContent)
FetchContent_Declare(
    json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.3
)
FetchContent_MakeAvailable(json)

# Include directories
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# Library
add_library(signaling-server-lib
    src/connection_manager.cpp
    src/websocket_session.cpp
    src/message_handler.cpp
    src/models.cpp
)

target_link_libraries(signaling-server-lib
    PUBLIC
        Boost::system
        Threads::Threads
        nlohmann_json::nlohmann_json
)

target_include_directories(signaling-server-lib
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# Executable
add_executable(signaling-server
    src/main.cpp
)

target_link_libraries(signaling-server
    PRIVATE
        signaling-server-lib
)

# Tests
enable_testing()
add_subdirectory(tests)

# Examples
add_subdirectory(examples)
