# Contributing to Kratos AI

Thank you for your interest in contributing to Kratos AI! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions. We welcome contributors of all backgrounds and experience levels.

## How to Contribute

### Reporting Bugs

1. Check existing issues first
2. Create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (K8s version, Python version, etc.)

### Suggesting Features

1. Open an issue with the `enhancement` label
2. Describe the use case and expected behavior
3. Explain why this would be valuable

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Add tests for new functionality
5. Run tests: `pytest tests/ -v`
6. Run linting: `ruff check src/`
7. Commit with clear messages
8. Push and create a PR

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/kratos-ai.git
cd kratos-ai

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linting
ruff check src/
```

## Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for public APIs
- Keep functions focused and small
- Add tests for new features

## Architecture Guidelines

### Adding New Predictors

1. Inherit from `BasePredictor` in `src/ml/predictors.py`
2. Implement `train()` and `predict()` methods
3. Add tests in `tests/test_predictors.py`

### Adding New Remediation Actions

1. Add to `RemediationAction` enum in `src/core/types.py`
2. Implement handler in `RemediationEngine`
3. Add safety checks if needed
4. Update action library

### Adding New Incident Types

1. Add to `IncidentType` enum
2. Update pattern detection logic
3. Add recommended actions mapping

## Testing

- Unit tests: Test individual components
- Integration tests: Test component interactions
- Run all tests before submitting PR

```bash
# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=html
```

## Documentation

- Update README.md for user-facing changes
- Add docstrings to new public APIs
- Update examples if API changes

## Questions?

Open an issue with the `question` label or reach out to maintainers.
