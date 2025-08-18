# Contributing to Intermud3

Thank you for your interest in contributing to the Intermud3 project for LuminariMUD/tbaMUD! This document provides guidelines for contributing to the project.

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
- C compiler (GCC or Clang recommended)
- Make build system
- Git
- Basic understanding of MUD development and networking protocols

### Building the Project
```bash
make
```

### Running Tests
```bash
make test
```

## Code Style Guidelines

- Follow the existing code style in the project
- Use consistent indentation (2 spaces for C code)
- Keep lines under 80 characters when possible
- Add comments for complex logic
- Use meaningful variable and function names
- Follow C89/C90 standard for maximum compatibility

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

- Add tests for new features
- Ensure all existing tests pass
- Test with different MUD codebases (LuminariMUD, tbaMUD)
- Verify network protocol compatibility

## Documentation

- Update documentation for any API changes
- Add inline comments for complex code
- Update README if adding new features
- Document any new configuration options

## Communication

- Be respectful and constructive in all interactions
- Ask questions if you're unsure about something
- Join discussions in issues and pull requests
- Follow our Code of Conduct

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project.

## Recognition

Contributors will be recognized in the project's AUTHORS file.

## Questions?

If you have questions about contributing, please open an issue with the "question" label.

Thank you for helping improve Intermud3 for the MUD community!