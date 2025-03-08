# SUDP - Secure UDP over WebSocket

A Python-based solution for tunneling UDP traffic through WebSocket connections, providing secure and reliable UDP communication across networks.

## Features

### Implemented (v0.8.0)
- Core UDP Packet Handling with serialization/deserialization
- UDP Socket Management with async operations
- Basic TCP Server Implementation with client tracking
- Multi-instance Support with instance isolation
- Error Recovery with connection recovery and packet retransmission
- Comprehensive Testing Infrastructure

### Planned
- WebSocket Integration (v0.7.0)
- Advanced Configuration Management
- Secure communication via reverse proxy
- Performance Optimization
- Cross-platform support

## Development Status

Currently in active development (v0.8.0). See [ROADMAP.md](ROADMAP.md) for detailed development plans and progress.

## Requirements

- Python 3.8+
- pip for Python package management

## Quick Start

1. Clone the repository:
   ```bash
   git clone [repository-url]
   cd sudp
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -e .
   ```

4. Run tests:
   ```bash
   pytest
   ```

5. Try the echo server example:
   ```bash
   python examples/echo_server.py
   ```

6. Test with netcat:
   ```bash
   nc -u 127.0.0.1 5005
   ```

7. Server daemon commands:
   ```bash
   # Server daemon (default instance)
   sudpd start
   sudpd status
   sudpd stop

   # Server daemon (named instance)
   sudpd start --instance test1 --port 11224
   sudpd status --instance test1
   sudpd stop --instance test1
   
   # List all instances
   sudpd list
   ```

## Project Structure

```
sudp/
├── src/
│   ├── sudp/          # Main package
│   ├── client/        # Client-side implementation
│   ├── tests/         # Test suite
├── examples/         # Example configurations and usage
├── systemd/          # Systemd service files
├── docs/             # Documentation
├── pyproject.toml    # Project configuration
└── README.md         # This file
```

## Documentation

- [INSTALL.md](INSTALL.md) - Detailed installation instructions
- [USER_STORY.md](USER_STORY.md) - Operation flow and use cases
- [DEVELOPMENT_CONTEXT.md](DEVELOPMENT_CONTEXT.md) - Development state and context
- [ROADMAP.md](ROADMAP.md) - Development roadmap and planning

## License

MIT License - See [LICENSE.md](LICENSE.md) for details

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project. 