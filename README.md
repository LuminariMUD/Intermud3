# I3 Gateway - Intermud3 Protocol Gateway Service

A standalone Python implementation that acts as a protocol bridge between MUDs and the global Intermud-3 network.

## Features

- 🌐 Full Intermud-3 protocol support
- 🔄 Automatic reconnection and failover
- 📡 JSON-RPC API for easy MUD integration
- 📊 Built-in metrics and monitoring
- 🐳 Docker support for easy deployment
- ⚡ High performance (1000+ messages/sec)
- 🔒 Secure authentication and authorization

## Quick Start

### Prerequisites

- Python 3.9 or higher
- Virtual environment (recommended)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/i3-gateway.git
cd i3-gateway
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
make install-dev  # For development
# OR
pip install -e .  # For production
```

4. Copy and configure environment:
```bash
cp .env.example .env
# Edit .env with your MUD settings
```

5. Run the gateway:
```bash
make run
# OR
python -m i3_gateway
```

## Development

### Setup Development Environment

```bash
make setup  # Complete development setup
```

### Running Tests

```bash
make test           # Run all tests
make test-coverage  # Run with coverage report
```

### Code Quality

```bash
make lint    # Run linting checks
make format  # Auto-format code
make check   # Run all checks
```

### Pre-commit Hooks

```bash
pre-commit install  # Install hooks
make pre-commit     # Run manually
```

## Docker Deployment

### Build and Run

```bash
make docker-build
make docker-run
```

### Using Docker Compose

```bash
docker-compose up -d
```

## Configuration

The gateway is configured via `config/config.yaml` with environment variable support:

```yaml
mud:
  name: ${MUD_NAME:YourMUD}
  port: ${MUD_PORT:4000}
  
router:
  primary:
    host: ${I3_ROUTER_HOST:204.209.44.3}
    port: ${I3_ROUTER_PORT:8080}
```

See `.env.example` for all available environment variables.

## API Documentation

The gateway exposes a JSON-RPC API on port 4001 by default.

### Example: Send Tell

```json
{
  "jsonrpc": "2.0",
  "method": "send_tell",
  "params": {
    "from_user": "player",
    "to_mud": "OtherMUD",
    "to_user": "friend",
    "message": "Hello!"
  },
  "id": 1
}
```

## Project Structure

```
i3-gateway/
├── src/i3_gateway/
│   ├── network/      # MudMode protocol implementation
│   ├── services/     # I3 service handlers
│   ├── models/       # Data structures
│   ├── config/       # Configuration management
│   └── state/        # State and cache management
├── tests/            # Test suite
├── config/           # Configuration files
└── docs/             # Documentation
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

- GitHub Issues: [Report bugs or request features](https://github.com/yourusername/i3-gateway/issues)
- Documentation: [Full documentation](https://i3-gateway.readthedocs.io)

## Acknowledgments

- The Intermud-3 protocol creators and maintainers
- The MUD community for continued support