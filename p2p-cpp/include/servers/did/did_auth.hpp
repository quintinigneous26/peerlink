#pragma once

#include <string>

namespace p2p {
namespace did {

class DIDAuth {
public:
    explicit DIDAuth(const std::string& jwt_secret);

    std::string GenerateToken(const std::string& did);
    bool ValidateToken(const std::string& token);
    std::string ExtractDID(const std::string& token);

private:
    std::string jwt_secret_;
};

} // namespace did
} // namespace p2p
