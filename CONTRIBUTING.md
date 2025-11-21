# Contributing to stonks-ai

Thank you for your interest in contributing to stonks-ai!

## Development Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/yourusername/stonks-ai.git
   cd stonks-ai
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   make install
   ```
5. Copy environment file:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Development Workflow

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes

3. Run tests and checks:
   ```bash
   make all  # Runs format, lint, type-check, and test
   ```

4. Commit your changes:
   ```bash
   git add .
   git commit -m "Add: your feature description"
   ```

5. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

6. Create a Pull Request

## Code Style

- Use Python 3.13+ features
- Follow PEP 8 style guide
- Use type hints for all functions
- Write docstrings for public APIs
- Keep functions small and focused

### Formatting
We use `black` for code formatting:
```bash
make format
```

### Linting
We use `ruff` for linting:
```bash
make lint
```

### Type Checking
We use `mypy` for type checking:
```bash
make type-check
```

## Testing

- Write tests for all new features
- Maintain or improve code coverage
- Use pytest markers appropriately:
  - `@pytest.mark.unit` for unit tests
  - `@pytest.mark.integration` for integration tests
  - `@pytest.mark.slow` for slow tests
  - `@pytest.mark.api` for tests requiring API access

Run tests:
```bash
make test
```

## Commit Messages

Use clear, descriptive commit messages:
- `Add: new feature description`
- `Fix: bug description`
- `Update: modification description`
- `Refactor: refactoring description`
- `Docs: documentation changes`
- `Test: test additions or changes`

## Pull Request Guidelines

1. Ensure all tests pass
2. Update documentation if needed
3. Add tests for new features
4. Keep PRs focused on a single feature/fix
5. Reference any related issues

## Code Review Process

1. Maintainers will review your PR
2. Address any feedback
3. Once approved, your PR will be merged

## Areas for Contribution

- **Data Layer**: Implement API integrations
- **Analysis**: Add technical indicators and patterns
- **Sentiment**: Improve sentiment analysis
- **Models**: Add ML models and features
- **Testing**: Increase test coverage
- **Documentation**: Improve guides and examples
- **Performance**: Optimize slow operations

## Questions?

Open an issue for discussion or clarification.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
