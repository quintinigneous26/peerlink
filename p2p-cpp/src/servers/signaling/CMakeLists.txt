cmake_minimum_required(VERSION 3.20)

# Signaling Server Library
add_library(p2p_signaling_server
    src/models.cpp
    src/connection_manager.cpp
    src/websocket_session.cpp
    src/message_handler.cpp
)

target_include_directories(p2p_signaling_server
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src
)

target_link_libraries(p2p_signaling_server
    PUBLIC
        p2p_utils
        nlohmann_json::nlohmann_json
        pthread
)

# Signaling Server Executable
add_executable(p2p-signaling-server
    src/main.cpp
)

target_link_libraries(p2p-signaling-server
    PRIVATE
        p2p_signaling_server
)

# Installation
install(TARGETS p2p_signaling_server p2p-signaling-server
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
)

install(DIRECTORY include/
    DESTINATION include
    FILES_MATCHING PATTERN "*.hpp"
)