# CLAUDE.md

Guidance for Claude Code when working with this repository.

## Project Overview

SPX 0DTE options trading bot with TradingView webhook integration. Receives signals, generates trade suggestions, and executes via Moomoo broker API.

## Development Commands

```bash
# Setup
uv sync                    # Install dependencies
cp .env.example .env       # Configure environment

# Run
uv run python -m src.main serve        # Start webhook server
uv run python -m src.main session      # Show trading session status
uv run python -m src.main test-moomoo  # Test Moomoo connection
uv run python -m src.main info         # System info
uv run python -m src.main config       # View config

# Code Quality
uv run ruff check --fix .              # Lint and auto-fix
uv run ruff format .                   # Format code
```

## Architecture

### Signal Flow
```
TradingView Alert → Webhook → SignalProcessor → TradeSuggester → OrderManager → MoomooExecutor
```

### Module Structure
```
src/
├── api/
│   ├── webhook.py         # FastAPI routes for webhooks + order/position management
│   └── signals.py         # SignalProcessor - orchestrates suggestion + execution
├── analysis/
│   ├── suggester.py       # TradeSuggester - generates trade suggestions
│   └── risk.py            # RiskCalculator - position sizing, R:R, confidence
├── config/
│   └── settings.py        # Settings singleton from .env
├── data/
│   └── moomoo_client.py   # Moomoo OpenD client + yfinance for SPX price
├── execution/
│   ├── order_types.py     # Order, Fill, Position Pydantic models
│   ├── order_manager.py   # Order lifecycle + manual approval flow
│   ├── executor.py        # Moomoo trade API wrapper
│   └── position_tracker.py # Position monitoring + auto-exit at 3:45 PM
├── models/
│   ├── signals.py         # TradingViewSignal model
│   ├── options.py         # OptionContract, Greeks, OptionsChain
│   └── suggestions.py     # TradeSuggestion, TradeType, Confidence
├── utils/
│   ├── logger.py          # Loguru setup
│   └── time_utils.py      # Session phases (prime time, danger zone, etc.)
├── server.py              # FastAPI app with lifespan management
└── main.py                # CLI entry point (Click)
```

### Key Components

**SignalProcessor** (`src/api/signals.py`)
- Validates session timing
- Fetches SPX price + options chain
- Generates suggestion via TradeSuggester
- Creates order via OrderManager (if execution enabled)

**OrderManager** (`src/execution/order_manager.py`)
- Manual approval flow: Order created → PENDING_APPROVAL → user approves → SUBMITTED → FILLED
- Position limits (max 2 concurrent)
- Tracks orders and positions in memory

**PositionTracker** (`src/execution/position_tracker.py`)
- Background monitoring task
- Auto-closes all positions at 3:45 PM (danger zone)
- Daily P&L tracking

**MoomooExecutor** (`src/execution/executor.py`)
- Wraps Moomoo OpenSecTradeContext
- Paper trading (SIMULATE) or live (REAL)
- Submit, cancel, query orders

## API Endpoints

All under `/webhook/` prefix:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/signal` | POST | Receive TradingView alert |
| `/orders` | GET | List all orders |
| `/orders/{id}/approve` | POST | Approve pending order |
| `/orders/{id}/reject` | POST | Reject pending order |
| `/positions` | GET | List all positions |
| `/positions/{id}/close` | POST | Close position at market |
| `/summary` | GET | Daily P&L summary |
| `/session` | GET | Current session phase |
| `/health` | GET | Health check |

## Environment Variables

### Required
```bash
WEBHOOK_PASSPHRASE=your_secret    # TradingView webhook auth
```

### Moomoo Connection
```bash
MOOMOO_HOST=127.0.0.1             # OpenD host
MOOMOO_PORT=11111                 # OpenD port
MOOMOO_TRADING_ENV=SIMULATE       # SIMULATE or REAL
```

### Trading Settings
```bash
ACCOUNT_SIZE=25000                # Account size for position sizing
MAX_RISK_PER_TRADE=0.02           # 2% max risk per trade
MAX_DAILY_RISK=0.03               # 3% max daily loss
DEFAULT_TARGET_DELTA=0.25         # Target delta for strike selection
```

### Execution Settings
```bash
EXECUTION_ENABLED=false           # Enable order creation from signals
AUTO_EXECUTE=false                # Auto-execute (skip manual approval)
MAX_POSITIONS=2                   # Max concurrent positions
AUTO_EXIT_ENABLED=true            # Auto-close at 3:45 PM
```

### Optional
```bash
NEWS_API_KEY=                     # For future sentiment analysis
DATABASE_URL=sqlite:///stonks.db  # For future persistence
ENVIRONMENT=development           # development or production
LOG_LEVEL=INFO                    # DEBUG/INFO/WARNING/ERROR
```

## Session Timing (EST)

| Phase | Time | Trading |
|-------|------|---------|
| PRE_MARKET | < 9:30 | No |
| PRIME_TIME | 9:30-11:00 | Yes (best) |
| LUNCH_DOLDRUMS | 11:00-13:30 | Yes (low vol) |
| MID_SESSION | 13:30-15:30 | Yes |
| DANGER_ZONE | 15:30-16:00 | No (auto-exit) |
| AFTER_HOURS | > 16:00 | No |

## Signal Types Supported

- RSI_OVERSOLD_LONG
- RSI_OVERBOUGHT_SHORT
- RUBBERBAND_LONG / RUBBERBAND_SHORT
- SHOOTING_STAR
- V_DIP_LONG
- PIVOT_SUPPORT
- VWAP_BOUNCE

## Order Flow (Manual Approval Mode)

1. Signal received via webhook
2. SignalProcessor generates TradeSuggestion
3. OrderManager creates Order (status: PENDING_APPROVAL)
4. Console shows approval prompt
5. User calls `POST /webhook/orders/{id}/approve`
6. Order submitted to Moomoo → FILLED
7. Position created and tracked
8. Auto-exit at 3:45 PM if still open

## Key Design Decisions

1. **Manual approval by default** - No auto-execution without explicit approval
2. **In-memory state** - Orders/positions stored in memory (persistence in Phase 2)
3. **Moomoo for execution** - Uses OpenSecTradeContext for paper/live trading
4. **yfinance for SPX price** - Free, doesn't require Moomoo connection
5. **Session-aware** - Blocks trades in danger zone, warns during lunch

## Future Phases

- **Phase 2**: Trade journal with SQLite persistence
- **Phase 3**: VIX integration for market context
- **Phase 4**: Strategy refactor (V-dip, Rubberband classes)
- **Phase 5**: Backtesting with VectorBT
- **Phase 6**: GEX/DIX, sentiment, event-driven architecture
