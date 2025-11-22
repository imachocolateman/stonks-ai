# stonks-bot

AI-driven stock market analysis and trading assistant.

## Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv and install deps
uv sync

# Configure
cp .env.example .env
# Edit .env with your API keys
```

## Run

```bash
# CLI application
uv run python -m src.main info
uv run python -m src.main config
uv run python -m src.main analyze -t AAPL
```

## Dev

```bash
# Format/lint
uv run ruff check --fix .
uv run ruff format .
```
