# Protobuf Generation
cmake_minimum_required(VERSION 3.20)

# Find Protobuf
find_package(Protobuf REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(ABSL REQUIRED absl_log_internal_check_op)

# Protobuf files
set(PROTO_FILES
    dcutr.proto
    relay_v2.proto
)

# Generate C++ code from protobuf
protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS ${PROTO_FILES})

# Create protobuf library
add_library(p2p-proto STATIC ${PROTO_SRCS} ${PROTO_HDRS})

# Suppress nullability warnings from protobuf/abseil
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    target_compile_options(p2p-proto PRIVATE
        -Wno-nullability-extension
        -Wno-nullability-completeness
    )
endif()

# Link protobuf
target_link_libraries(p2p-proto
    PUBLIC
        protobuf::libprotobuf
        ${ABSL_LIBRARIES}
)

target_link_directories(p2p-proto
    PUBLIC
        ${ABSL_LIBRARY_DIRS}
)

# Include directories
target_include_directories(p2p-proto
    PUBLIC
        ${CMAKE_CURRENT_BINARY_DIR}
        ${Protobuf_INCLUDE_DIRS}
)

# Installation
install(TARGETS p2p-proto
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
)

# Install generated headers
install(FILES ${PROTO_HDRS}
    DESTINATION include/p2p/proto
)
