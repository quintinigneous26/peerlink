cmake_minimum_required(VERSION 3.20)
project(CPP_Go_Interop_Tests)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find Protobuf
find_package(Protobuf REQUIRED)

# Proto files directory
set(PROTO_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../p2p-cpp/proto")

# Generate protobuf sources
set(PROTO_FILES
    "${PROTO_DIR}/relay_v2.proto"
)

protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS ${PROTO_FILES})

# Include directories
include_directories(
    ${CMAKE_CURRENT_BINARY_DIR}
    ${Protobuf_INCLUDE_DIRS}
)

# Test executables
add_executable(test_cpp_to_go
    test_cpp_to_go.cpp
    ${PROTO_SRCS}
)

target_link_libraries(test_cpp_to_go
    ${Protobuf_LIBRARIES}
)

add_executable(test_network_interop
    test_network_interop.cpp
)

# Print configuration
message(STATUS "Protobuf version: ${Protobuf_VERSION}")
message(STATUS "Protobuf include: ${Protobuf_INCLUDE_DIRS}")
message(STATUS "Protobuf libraries: ${Protobuf_LIBRARIES}")
