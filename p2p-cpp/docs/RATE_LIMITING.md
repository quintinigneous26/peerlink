# Rate Limiting Implementation

## Overview
Implemented token bucket rate limiting for TURN relay server control messages to prevent abuse and DoS attacks.

## Architecture

### Token Bucket Algorithm
Each client gets a token bucket with:
- **Rate**: Tokens added per second (requests/second)
- **Capacity**: Maximum burst size
- **Tokens**: Current available tokens

Requests consume 1 token. If no tokens available, request is blocked.

### Ban Mechanism
- Track violations when rate limit exceeded
- Ban client after threshold violations
- Ban duration configurable (default 60 seconds)
- Automatic unban after duration expires

## Components

### 1. ClientRateLimiter
Per-client rate limiting state:
```cpp
class ClientRateLimiter {
    uint32_t rate_;        // tokens per second
    uint32_t capacity_;    // max burst
    double tokens_;        // current tokens
    uint32_t violations_;  // violation count
};
```

### 2. RateLimiter
Global rate limiter managing all clients:
```cpp
class RateLimiter {
    RateLimitConfig config_;
    std::unordered_map<std::string, std::unique_ptr<ClientRateLimiter>> limiters_;
};
```

### 3. RateLimitConfig
Configuration parameters:
```cpp
struct RateLimitConfig {
    uint32_t requests_per_second = 10;   // Max requests/sec
    uint32_t burst_size = 20;             // Max burst
    uint32_t ban_threshold = 5;           // Violations before ban
    uint32_t ban_duration_seconds = 60;   // Ban duration
};
```

## Integration

### RelayServer Integration
Rate limiting applied to all control messages:

1. **Check rate limit** before processing message
2. **Send error response** if rate limited
3. **Track statistics** for monitoring

```cpp
void RelayServer::HandleControlMessage(...) {
    // Check rate limit
    if (!rate_limiter_->AllowRequest(client_key)) {
        // Send error response
        return;
    }

    // Process message normally
    ...
}
```

### Configuration
Add to RelayServerConfig:
```cpp
struct RelayServerConfig {
    ...
    RateLimitConfig rate_limit;
};
```

## Default Limits

| Parameter | Default | Description |
|-----------|---------|-------------|
| requests_per_second | 10 | Sustained rate limit |
| burst_size | 20 | Maximum burst |
| ban_threshold | 5 | Violations before ban |
| ban_duration_seconds | 60 | Ban duration |

## Usage Examples

### Basic Usage
```cpp
RateLimitConfig config(10, 20, 5, 60);
RateLimiter limiter(config);

// Check if request allowed
if (limiter.AllowRequest("192.168.1.100:12345")) {
    // Process request
} else {
    // Reject request
}
```

### Manual Ban/Unban
```cpp
// Ban abusive client
limiter.BanClient("192.168.1.100:12345");

// Unban after investigation
limiter.UnbanClient("192.168.1.100:12345");
```

### Statistics
```cpp
auto stats = limiter.GetStats();
std::cout << "Total requests: " << stats.total_requests << "\n";
std::cout << "Blocked: " << stats.blocked_requests << "\n";
std::cout << "Block rate: " << stats.block_rate << "\n";
std::cout << "Banned clients: " << stats.banned_clients << "\n";
```

## Performance Characteristics

### Time Complexity
- AllowRequest: O(1) average
- IsBanned: O(1)
- CleanupExpired: O(n) where n = number of clients

### Space Complexity
- O(n) where n = number of unique clients
- Automatic cleanup removes inactive clients

### Concurrency
- Thread-safe with per-client mutexes
- Minimal lock contention
- Lock-free statistics updates

## Testing

### Unit Tests
Comprehensive test coverage in `test_rate_limiter.cpp`:

1. **Basic functionality**
   - Allow requests within limit
   - Token refill over time
   - Ban after threshold violations
   - Ban expiration

2. **Multi-client scenarios**
   - Independent client limits
   - Concurrent requests
   - Different clients isolation

3. **Management operations**
   - Manual ban/unban
   - Client removal
   - Cleanup expired

4. **Stress testing**
   - High load (2000 requests, 20 threads)
   - Concurrent same client
   - Concurrent different clients

### Integration Tests
Test with relay server:
```bash
# Send burst of requests
for i in {1..30}; do
    echo "Request $i"
    # Send STUN message
done

# Verify rate limiting
# First 20 should succeed (burst)
# Next 10 should be rate limited
```

## Security Considerations

### DoS Protection
- Prevents request flooding
- Automatic ban for persistent abuse
- Per-client isolation

### Resource Management
- Bounded memory usage
- Automatic cleanup of inactive clients
- Configurable limits

### Attack Scenarios

#### 1. Single Client Flood
**Attack**: One client sends many requests
**Defense**: Rate limit + ban after threshold

#### 2. Distributed Attack
**Attack**: Many clients send requests
**Defense**: Per-client limits prevent resource exhaustion

#### 3. Slow Rate Attack
**Attack**: Stay just under rate limit
**Defense**: Sustained rate limit prevents long-term abuse

## Monitoring

### Metrics to Track
1. **Total requests**: Overall traffic
2. **Blocked requests**: Rate limiting effectiveness
3. **Block rate**: Percentage of blocked requests
4. **Banned clients**: Number of abusive clients
5. **Active clients**: Current client count

### Alerting Thresholds
- Block rate > 50%: Possible attack
- Banned clients > 100: Widespread abuse
- Total requests spike: Traffic anomaly

## Configuration Tuning

### High Traffic Scenarios
```cpp
RateLimitConfig config(
    50,    // 50 requests/sec
    100,   // 100 burst
    10,    // 10 violations
    300    // 5 min ban
);
```

### Strict Security
```cpp
RateLimitConfig config(
    5,     // 5 requests/sec
    10,    // 10 burst
    3,     // 3 violations
    3600   // 1 hour ban
);
```

### Development/Testing
```cpp
RateLimitConfig config(
    1000,  // 1000 requests/sec
    2000,  // 2000 burst
    100,   // 100 violations
    10     // 10 sec ban
);
```

## Files Modified

1. **include/p2p/servers/relay/rate_limiter.hpp** (new)
   - RateLimitConfig struct
   - ClientRateLimiter class
   - RateLimiter class

2. **src/servers/relay/rate_limiter.cpp** (new)
   - Token bucket implementation
   - Ban mechanism
   - Statistics tracking

3. **include/p2p/servers/relay/relay_server.hpp**
   - Added rate_limiter_ member
   - Added rate_limit to config
   - Added rate_limit to Stats

4. **src/servers/relay/relay_server.cpp**
   - Initialize rate_limiter_
   - Check rate limit in HandleControlMessage
   - Include rate_limit stats in GetStats

5. **tests/unit/relay/test_rate_limiter.cpp** (new)
   - 16 comprehensive unit tests
   - Stress tests with 2000 requests

## Future Enhancements

### 1. Adaptive Rate Limiting
Adjust limits based on server load:
```cpp
if (server_load > 80%) {
    config.requests_per_second /= 2;
}
```

### 2. IP Reputation System
Track client behavior over time:
```cpp
struct ClientReputation {
    uint32_t total_requests;
    uint32_t total_violations;
    double reputation_score;
};
```

### 3. Whitelist/Blacklist
Permanent allow/deny lists:
```cpp
std::unordered_set<std::string> whitelist_;
std::unordered_set<std::string> blacklist_;
```

### 4. Geographic Rate Limiting
Different limits per region:
```cpp
std::unordered_map<std::string, RateLimitConfig> region_configs_;
```

## Conclusion

The rate limiting implementation provides robust DoS protection for the TURN relay server with:
- Token bucket algorithm for smooth rate limiting
- Automatic ban mechanism for persistent abuse
- Per-client isolation
- Thread-safe concurrent access
- Comprehensive testing
- Configurable limits for different scenarios

All endpoints are now protected against abuse while maintaining good performance for legitimate clients.
