# Contributing to Datadog Multi-Agent Debugging

Thank you for your interest in contributing to this project! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites
- Python 3.8 or higher
- Git
- AWS account with Bedrock access
- Datadog account with API key

### Development Setup
1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/yourusername/datadog-multi-agent-debugging.git
   cd datadog-multi-agent-debugging
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -e .[dev]
   ```
5. Copy environment template:
   ```bash
   cp .env-example .env
   # Edit .env with your credentials
   ```

## 📝 Code Style

### Python Style Guide
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints for all function parameters and return values
- Keep functions small and focused (max 50 lines)
- Use descriptive variable and function names
- Add docstrings for all public functions and classes

### Formatting
We use [Black](https://black.readthedocs.io/) for code formatting:
```bash
black .
```

### Linting
We use [flake8](https://flake8.pycqa.org/) for linting:
```bash
flake8 .
```

### Type Checking
We use [mypy](http://mypy-lang.org/) for type checking:
```bash
mypy .
```

## 🧪 Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_services.py

# Run with verbose output
pytest -v
```

### Writing Tests
- Write tests for all new functionality
- Use descriptive test names
- Follow the Arrange-Act-Assert pattern
- Mock external dependencies
- Test both success and failure cases

### Test Structure
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_models/             # Model tests
├── test_services/           # Service tests
├── test_processors/         # Processor tests
├── test_orchestrators/      # Orchestrator tests
└── test_runners/            # Runner tests
```

## 🔄 Development Workflow

### 1. Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes
- Write your code following the style guidelines
- Add tests for new functionality
- Update documentation if needed

### 3. Test Your Changes
```bash
# Run all checks
black .
flake8 .
mypy .
pytest
```

### 4. Commit Your Changes
```bash
git add .
git commit -m "feat: add new feature description"
```

### 5. Push and Create Pull Request
```bash
git push origin feature/your-feature-name
```

## 📋 Pull Request Guidelines

### Before Submitting
- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] Documentation is updated
- [ ] No sensitive data is included
- [ ] Changes are tested locally

### Pull Request Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No sensitive data included
```

## 🐛 Bug Reports

### Before Reporting
1. Check existing issues
2. Try to reproduce the issue
3. Check the documentation

### Bug Report Template
```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Step 1
2. Step 2
3. Step 3

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., Ubuntu 20.04]
- Python: [e.g., 3.9.7]
- Package versions: [output of pip freeze]

## Additional Information
Any other relevant information
```

## 💡 Feature Requests

### Before Requesting
1. Check if the feature already exists
2. Consider if it fits the project scope
3. Think about implementation approach

### Feature Request Template
```markdown
## Feature Description
Clear description of the feature

## Use Case
Why this feature is needed

## Proposed Implementation
How you think it should be implemented

## Alternatives Considered
Other approaches you considered

## Additional Information
Any other relevant information
```

## 📚 Documentation

### Code Documentation
- Add docstrings to all public functions and classes
- Use Google-style docstrings
- Include type hints
- Provide usage examples

### README Updates
- Update README.md for significant changes
- Add new sections for new features
- Update installation instructions if needed

## 🔒 Security

### Security Guidelines
- Never commit sensitive data (API keys, passwords, etc.)
- Use environment variables for configuration
- Validate all inputs
- Follow the principle of least privilege
- Report security issues privately

### Reporting Security Issues
If you find a security vulnerability, please report it privately to the maintainers.

## 🏷️ Versioning

We follow [Semantic Versioning](https://semver.org/):
- MAJOR version for incompatible API changes
- MINOR version for backwards-compatible functionality
- PATCH version for backwards-compatible bug fixes

## 📞 Getting Help

### Questions and Support
- Check the documentation
- Search existing issues
- Create a new issue for questions
- Join our community discussions

### Communication
- Be respectful and inclusive
- Use clear and concise language
- Provide context for questions
- Help others when you can

## 🙏 Acknowledgments

Thank you for contributing to this project! Your contributions help make it better for everyone.

---

By contributing to this project, you agree to abide by the terms of the MIT License. 