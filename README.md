# Intermud3 Gateway Service

A standalone Python implementation that acts as a protocol bridge between MUDs and the global Intermud-3 network. This gateway handles all I3 protocol complexity internally while exposing a simple JSON-RPC API for easy MUD integration.

## 📚 Documentation

### Essential Documentation
- **[High-Level Implementation Plan](docs/HIGH_LEVEL_PLAN.md)** - Complete architectural overview and implementation roadmap
- **[Python Project Setup Guide](docs/python/python_project.md)** - Detailed Python development environment setup and configuration
- **[Intermud3 Protocol Documentation](docs/intermud3_docs/)** - Comprehensive I3 protocol specifications:
  - [Protocol Overview](docs/intermud3_docs/overview.md) - Introduction to Intermud3
  - [Architecture](docs/intermud3_docs/architecture.md) - System architecture details
  - [Packet Format](docs/intermud3_docs/packet-format.md) - LPC packet structure
  - [Services Documentation](docs/intermud3_docs/services/) - Individual service specifications (tell, channel, who, etc.)
  - [Router Design](docs/intermud3_docs/router-design.md) - Router implementation details
- **[TODO List](docs/TODO.md)** - Current development tasks and roadmap
- **[Changelog](docs/CHANGELOG.md)** - Version history and changes

### Developer Resources
- **[CLAUDE.md](CLAUDE.md)** - Claude Code AI assistant instructions
- **[Contributing Guide](CONTRIBUTING.md)** - How to contribute to the project
- **[Code of Conduct](CODE_OF_CONDUCT.md)** - Community guidelines

## Features

- 🌐 Full Intermud-3 protocol support (Phase 2 Complete)
- 🔄 Automatic reconnection and failover with circuit breakers
- 📡 JSON-RPC API for easy MUD integration (Phase 3 pending)
- 📊 Built-in metrics and monitoring 
- 🐳 Docker support for easy deployment
- ⚡ High performance (1000+ messages/sec)
- 🔒 Secure authentication and authorization
- ✅ Core services implemented (tell, channel, who, finger, locate)
- 🔧 60% test coverage with comprehensive unit tests

## Quick Start

### Prerequisites

- Python 3.9 or higher
- Virtual environment (recommended)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/intermud3-gateway.git
cd intermud3-gateway
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt       # Core dependencies
pip install -r requirements-dev.txt   # Development dependencies
# OR use Makefile
make install-dev
```

4. Copy and configure environment:
```bash
cp .env.example .env
# Edit .env with your MUD settings
# Key settings: MUD_NAME, MUD_PORT, GATEWAY_PORT
```

5. Run the gateway:
```bash
python -m src -c config/config.yaml
# OR
python src/__main__.py -c config/config.yaml
# OR with debug logging
LOG_LEVEL=DEBUG python -m src -c config/config.yaml
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
Intermud3/
├── src/
│   ├── __main__.py    # Entry point
│   ├── gateway.py     # Main gateway service
│   ├── network/       # MudMode protocol implementation
│   ├── services/      # I3 service handlers
│   ├── models/        # Data structures
│   ├── config/        # Configuration management
│   ├── state/         # State and cache management
│   └── utils/         # Utilities and logging
├── tests/             # Test suite
│   ├── unit/          # Unit tests
│   ├── integration/   # Integration tests
│   └── fixtures/      # Test fixtures
├── config/            # Configuration files
│   └── config.yaml    # Main configuration
├── docs/              # Documentation
│   ├── intermud3_docs/# I3 protocol documentation
│   ├── HIGH_LEVEL_PLAN.md
│   └── TODO.md
├── requirements.txt   # Core dependencies
├── pyproject.toml     # Project metadata
├── Makefile           # Build automation
└── docker-compose.yml # Docker deployment
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

- GitHub Issues: [Report bugs or request features](https://github.com/yourusername/intermud3-gateway/issues)
- Documentation: See `docs/` directory for full documentation

## Acknowledgments

- The Intermud-3 protocol creators and maintainers
- The MUD community for continued support