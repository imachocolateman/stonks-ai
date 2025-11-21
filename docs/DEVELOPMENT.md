# Development Guide

## Project Structure

```
stonks-ai/
├── src/                    # Main application source code
│   ├── config/            # Configuration management
│   ├── data/              # Data fetching and storage
│   ├── analysis/          # Technical analysis modules
│   ├── sentiment/         # News sentiment analysis
│   ├── models/            # Predictive ML models
│   ├── api/               # External API integrations
│   └── utils/             # Utility functions
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── notebooks/            # Jupyter notebooks for exploration
├── data/                 # Local data storage (gitignored)
├── models/               # Trained model files (gitignored)
├── docs/                 # Documentation
└── scripts/              # Utility scripts
```

## Setup

### Prerequisites

- Python 3.13+
- pip or poetry for dependency management
- TA-Lib system library (for technical analysis)

### Installation

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install TA-Lib (system dependency):
```bash
# macOS
brew install ta-lib

# Ubuntu/Debian
sudo apt-get install ta-lib

# Windows - download from: https://github.com/TA-Lib/ta-lib-python
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your API keys
```

5. Run tests:
```bash
pytest
```

## Development Workflow

### Running the Application

```bash
python -m src.main
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src

# Specific test file
pytest tests/unit/test_config.py

# With verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type checking
mypy src/
```

## Module Overview

### src/config
Configuration management using Pydantic settings. Loads from environment variables and .env file.

### src/data
Data fetching and storage layer. Handles market data retrieval and caching.

### src/analysis
Technical analysis indicators and pattern recognition.

### src/sentiment
News fetching and sentiment analysis.

### src/models
Machine learning models for predictions.

### src/api
External API integrations (Moomoo, News API, etc.).

### src/utils
Shared utility functions and helpers.

## Adding New Features

1. Create feature branch: `git checkout -b feature/your-feature`
2. Write tests first (TDD approach)
3. Implement feature
4. Ensure tests pass and code quality checks pass
5. Update documentation
6. Create pull request

## Debugging

- Logs are stored in `logs/` directory
- Use `LOG_LEVEL=DEBUG` in .env for detailed logging
- Check `logs/errors.log` for error-specific logs

## Common Tasks

### Adding a New Technical Indicator

1. Create module in `src/analysis/indicators/`
2. Implement indicator calculation
3. Add tests in `tests/unit/analysis/`
4. Document usage in docstrings

### Adding a New API Integration

1. Create client in `src/api/`
2. Implement authentication and endpoints
3. Add integration tests
4. Update .env.example with required keys

## Performance Optimization

- Use pandas vectorized operations
- Cache API responses
- Implement batch processing for multiple tickers
- Profile code with `cProfile` for bottlenecks
