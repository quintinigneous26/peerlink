# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-15

### Added
- Initial release of P2P Platform Client SDK
- NAT type detection using STUN protocol
- UDP hole punching for direct P2P connections
- Multi-channel support (control, data, video, audio, custom)
- Automatic relay fallback when P2P fails
- Auto-reconnection on network failures
- Event-driven async/await API
- Comprehensive error handling
- Basic usage examples
- Multi-channel communication examples

### Features
- Support for Python 3.11+
- Zero external dependencies (core functionality)
- Optional websockets support
- Full type hints
- Comprehensive test coverage

[Unreleased]: https://github.com/p2p-platform/python-sdk/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/p2p-platform/python-sdk/releases/tag/v0.1.0
