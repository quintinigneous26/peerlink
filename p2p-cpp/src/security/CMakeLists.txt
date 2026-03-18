# Security Module (Placeholder)
# TODO: Implement TLS/DTLS/Noise Protocol support

# Placeholder library
add_library(p2p_security INTERFACE)
target_include_directories(p2p_security INTERFACE
    ${CMAKE_SOURCE_DIR}/include
)
