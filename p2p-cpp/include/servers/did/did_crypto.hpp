#pragma once

#include <string>

namespace p2p {
namespace did {

class DIDCrypto {
public:
    static std::string GenerateKeyPair();
    static std::string Sign(const std::string& data, const std::string& private_key);
    static bool Verify(const std::string& data, const std::string& signature, const std::string& public_key);
    static std::string Hash(const std::string& data);
};

} // namespace did
} // namespace p2p
