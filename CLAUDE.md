# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Personal stock market analysis bot using AI for trading insights. Currently in early development with placeholder modules.

## Development Commands

```bash
# Setup
uv sync                    # Install dependencies
cp .env.example .env       # Configure environment

# Run
uv run main.py                    # Root entry point (placeholder)
uv run python -m src.main         # CLI application (Click-based)

# Code Quality
uv run ruff check --fix .         # Lint and auto-fix
uv run ruff format .              # Format code

# CLI Commands
uv run python -m src.main info                  # System info
uv run python -m src.main config                # View config
uv run python -m src.main analyze -t AAPL TSLA  # Analyze stocks (TODO)
uv run python -m src.main monitor -t AAPL       # Monitor stock (TODO)
uv run python -m src.main sentiment -t AAPL     # Sentiment analysis (TODO)
```

## Architecture

### Configuration System (Singleton Pattern)
- `src/config/settings.py` - Simple settings loaded from `.env` via python-dotenv
- Access via `get_settings()` singleton
- Auto-creates `data/` and `models/` directories on init
- Default tickers: AAPL, GOOGL, MSFT, TSLA

### Logging System (Dual Output)
- `src/utils/logger.py` - Loguru-based logging
- Console output: Colorized, respects `LOG_LEVEL` env var
- File outputs:
  - `logs/stonks-ai.log` - All logs (10MB rotation, 7 day retention)
  - `logs/errors.log` - Errors only (10MB rotation, 30 day retention)
- Access via `setup_logger()` (init) and `get_logger(__name__)` (usage)

### CLI Structure (Click-based)
- `src/main.py` - Entry point with commands: analyze, config, monitor, sentiment, info
- Uses Rich library for formatted console output (tables, colors)
- All commands are stubs awaiting implementation

### Module Structure
```
src/
├── config/      ✓ Settings management (python-dotenv + os.getenv)
├── utils/       ✓ Logger setup (Loguru)
├── main.py      ✓ CLI interface (Click + Rich)
├── api/         ⚠️ Empty - API integrations planned
├── data/        ⚠️ Empty - Data fetching planned
├── analysis/    ⚠️ Empty - Technical analysis planned
├── sentiment/   ⚠️ Empty - News sentiment planned
└── models/      ⚠️ Empty - ML models planned
```

## Environment Variables

Required:
- `MOOMOO_API_KEY` - Moomoo trading API key
- `MOOMOO_API_SECRET` - Moomoo API secret

Optional:
- `NEWS_API_KEY` - News API for sentiment analysis
- `DATABASE_URL` - Database connection (default: sqlite:///stonks.db)
- `ENVIRONMENT` - development/production (default: development)
- `LOG_LEVEL` - DEBUG/INFO/WARNING/ERROR (default: INFO)

## Key Design Decisions

1. **Not a package** - This is a personal script-based project, not meant for distribution
2. **Simplified structure** - Removed test infrastructure, docs, and CI/CD for personal use
3. **uv for dependencies** - Uses `uv` instead of pip/poetry for faster operations
4. **Dual entry points** - `main.py` (root) is placeholder; `src/main.py` is real CLI
5. **Configuration precedence** - `.env` file → environment variables → defaults

## Current State

Most modules are empty stubs. Working components:
- Configuration loading and validation
- Logging setup with file rotation
- CLI command structure and help text
- Directory auto-creation (data/, models/, logs/)

Next implementation priorities (all marked TODO):
- Data fetching module (Moomoo API integration)
- Analysis module (technical indicators)
- Sentiment module (news analysis)
- Models module (ML predictions)
