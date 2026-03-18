#pragma once

#include <string>

namespace p2p {
namespace did {

class DIDStorage {
public:
    DIDStorage(const std::string& redis_host, uint16_t redis_port);

    bool Store(const std::string& key, const std::string& value);
    std::string Retrieve(const std::string& key);
    bool Delete(const std::string& key);

private:
    std::string redis_host_;
    uint16_t redis_port_;
};

} // namespace did
} // namespace p2p
