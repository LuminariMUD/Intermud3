# Contributing to Intermud3

Thank you for your interest in contributing to the Intermud3 Gateway project! This document provides guidelines for contributing to the Python-based I3 Gateway service that enables MUD-to-Intermud3 network bridging.

## Getting Started

1. Fork the repository
2. Clone your fork to your local machine
3. Create a new branch for your feature or bug fix
4. Make your changes
5. Test your changes thoroughly
6. Commit your changes with clear, descriptive commit messages
7. Push to your fork
8. Submit a pull request

## Development Setup

### Prerequisites
- Python 3.9 or higher (Python 3.12 recommended)
- pip package manager
- Git
- Basic understanding of MUD development and networking protocols
- Understanding of async/await Python programming

### Setting up Development Environment
```bash
# Clone the repository
git clone https://github.com/yourusername/Intermud3.git
cd Intermud3

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate     # On Windows

# Install development dependencies
make install-dev
# or manually:
pip install -r requirements-dev.txt
```

### Running the Application
```bash
# Run the I3 Gateway
make run
# or
python -m src

# Run in development mode with debug logging
make dev
```

### Running Tests
```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run tests with coverage
make test-coverage
```

### Code Quality Tools
```bash
# Format code
make format

# Run linting
make lint

# Run type checking
make type-check

# Run all quality checks
make check
```

## Code Style Guidelines

- Follow PEP 8 Python style guidelines
- Use 4 spaces for indentation (no tabs)
- Keep lines under 100 characters (configured in Black)
- Add type hints for all function parameters and return values
- Use meaningful variable and function names in snake_case
- Add docstrings for all public functions and classes
- Follow async/await patterns for asynchronous code
- Use structured logging with the configured logger
- Add comments for complex business logic
- Use dataclasses or Pydantic models for data structures

## Contribution Process

### Reporting Bugs

Before submitting a bug report:
- Check if the issue has already been reported
- Verify the bug exists in the latest version
- Collect relevant information (error messages, logs, steps to reproduce)

When reporting bugs, please include:
- Clear description of the issue
- Steps to reproduce the problem
- Expected behavior
- Actual behavior
- System information (OS, compiler version, etc.)
- Relevant logs or error messages

### Suggesting Features

We welcome feature suggestions! Please:
- Check if the feature has already been requested
- Provide a clear use case
- Explain how it benefits the MUD community
- Consider backward compatibility with existing Intermud3 implementations

### Submitting Pull Requests

1. **Branch Naming**: Use descriptive branch names:
   - `feature/add-channel-encryption`
   - `bugfix/fix-memory-leak`
   - `docs/update-protocol-spec`

2. **Commit Messages**: Write clear commit messages:
   - Use present tense ("Add feature" not "Added feature")
   - Keep the first line under 50 characters
   - Provide detailed description if needed

3. **Pull Request Description**: Include:
   - Summary of changes
   - Related issue numbers
   - Testing performed
   - Screenshots (if UI changes)

4. **Code Review**: Be responsive to feedback and questions during review

## Testing

- Add unit tests for new functions and classes in `tests/unit/`
- Add integration tests for service interactions in `tests/integration/`
- Use pytest fixtures and async test patterns
- Ensure all existing tests pass before submitting PR
- Test with different MUD codebases when possible
- Verify network protocol compatibility with Intermud3 specification
- Add performance tests for high-throughput scenarios when relevant
- Mock external dependencies in unit tests
- Aim for high test coverage (80%+ target)

## Documentation

- Update API documentation in `docs/API_REFERENCE.md` for any API changes
- Add docstrings following Google or NumPy style
- Update README.md if adding new features or changing setup instructions
- Document any new configuration options in `config/config.yaml` and docs
- Update architecture documentation in `docs/ARCHITECTURE.md` for significant changes
- Add inline comments for complex business logic
- Keep documentation current with code changes

## Communication

- Be respectful and constructive in all interactions
- Ask questions if you're unsure about something
- Join discussions in issues and pull requests
- Follow our Code of Conduct

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project.

## Project Structure

When contributing, familiarize yourself with the project structure:

```
src/
├── api/           # REST/WebSocket API for MUD integration
├── config/        # Configuration management
├── models/        # Data models and packet definitions
├── network/       # Network layer and protocol handling
├── services/      # I3 service implementations
├── state/         # State management
└── utils/         # Utility functions

tests/
├── unit/          # Unit tests
├── integration/   # Integration tests
└── performance/   # Performance benchmarks

docs/              # Project documentation
config/            # Configuration files
```

## Recognition

Contributors will be recognized in the project's contributor list and commit history.

## Questions?

If you have questions about contributing, please open an issue with the "question" label.

Thank you for helping improve the Intermud3 Gateway for the MUD community!
