# SPX 0DTE Trading Bot

Automated SPX 0DTE options trading bot with TradingView webhook integration and Moomoo execution.

## Features

- **TradingView Integration** - Receive alerts via webhook
- **Trade Suggestions** - Auto-generate entry, target, stop based on signal
- **Manual Approval** - Review before execution
- **Moomoo Execution** - Paper or live trading via OpenD API
- **Risk Management** - Position sizing, R:R calculation, daily loss limits
- **Session Awareness** - Prime time, lunch doldrums, danger zone detection
- **Auto-Exit** - Close all positions at 3:45 PM EST

## Quick Start

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone <repo>
cd stonks-bot
uv sync
cp .env.example .env
```

### Configure `.env`

```bash
# Required
WEBHOOK_PASSPHRASE=your_secret_passphrase

# Moomoo OpenD (start OpenD first)
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111
MOOMOO_TRADING_ENV=SIMULATE   # or REAL

# Trading
ACCOUNT_SIZE=25000
MAX_POSITIONS=2

# Execution
EXECUTION_ENABLED=true        # Enable order creation
AUTO_EXIT_ENABLED=true        # Auto-close at 3:45 PM
```

### Run

```bash
# Start webhook server
uv run python -m src.main serve

# In another terminal, check session status
uv run python -m src.main session
```

## TradingView Setup

1. Create alert on your chart
2. Set webhook URL: `http://your-server:8000/webhook/signal`
3. Use JSON payload:

```json
{
  "passphrase": "your_secret_passphrase",
  "ticker": "SPX",
  "signal_type": "V_DIP_LONG",
  "action": "BUY",
  "price": 5850.00,
  "time": "{{time}}"
}
```

## Signal Types

| Signal | Description |
|--------|-------------|
| `RSI_OVERSOLD_LONG` | RSI < 30, bullish reversal |
| `RSI_OVERBOUGHT_SHORT` | RSI > 70, bearish reversal |
| `RUBBERBAND_LONG` | Stretched below mean, snap back |
| `RUBBERBAND_SHORT` | Stretched above mean, snap back |
| `V_DIP_LONG` | V-shaped reversal at support |
| `PIVOT_SUPPORT` | Bounce off pivot level |
| `VWAP_BOUNCE` | Bounce off VWAP |
| `SHOOTING_STAR` | Bearish candlestick pattern |

## Order Flow

```
Signal Received
      ↓
Suggestion Generated (console output)
      ↓
Order Created (PENDING_APPROVAL)
      ↓
User Approves via API
      ↓
Order Submitted to Moomoo
      ↓
Position Opened (tracked)
      ↓
Auto-Exit at 3:45 PM (or manual close)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/signal` | POST | Receive TradingView alert |
| `/webhook/orders` | GET | List all orders |
| `/webhook/orders/{id}/approve` | POST | Approve pending order |
| `/webhook/orders/{id}/reject` | POST | Reject pending order |
| `/webhook/positions` | GET | List positions |
| `/webhook/positions/{id}/close` | POST | Close position |
| `/webhook/summary` | GET | Daily P&L |
| `/webhook/session` | GET | Current session phase |

### Approve an Order

```bash
# List pending orders
curl http://localhost:8000/webhook/orders

# Approve
curl -X POST http://localhost:8000/webhook/orders/abc123/approve

# Or reject
curl -X POST http://localhost:8000/webhook/orders/abc123/reject
```

## Session Timing (EST)

| Phase | Time | Status |
|-------|------|--------|
| Pre-Market | < 9:30 | Signals rejected |
| **Prime Time** | 9:30-11:00 | Best for entries |
| Lunch Doldrums | 11:00-13:30 | Low volatility warning |
| Mid Session | 13:30-15:30 | Trading allowed |
| **Danger Zone** | 15:30-16:00 | Auto-exit, no new trades |
| After Hours | > 16:00 | Signals rejected |

## CLI Commands

```bash
uv run python -m src.main serve        # Start server
uv run python -m src.main session      # Show session status
uv run python -m src.main test-moomoo  # Test Moomoo connection
uv run python -m src.main config       # Show current config
uv run python -m src.main info         # System info
```

## Project Structure

```
src/
├── api/           # Webhook routes, signal processing
├── analysis/      # Trade suggester, risk calculator
├── config/        # Settings from .env
├── data/          # Moomoo client, market data
├── execution/     # Order manager, executor, position tracker
├── models/        # Pydantic models (signals, options, suggestions)
├── utils/         # Logger, time utils
├── server.py      # FastAPI app
└── main.py        # CLI entry point
```

## Risk Management

- **Position Sizing**: Max 2% account risk per trade
- **Daily Loss Limit**: 3% max daily drawdown
- **Max Positions**: 2 concurrent (configurable)
- **Auto-Exit**: All positions closed at 3:45 PM EST

## Development

```bash
# Lint
uv run ruff check --fix .

# Format
uv run ruff format .
```

## Roadmap

- [x] Phase 1: Execution module with manual approval
- [ ] Phase 2: Trade journal with SQLite persistence
- [ ] Phase 3: VIX integration for market context
- [ ] Phase 4: Strategy refactor (V-dip, Rubberband classes)
- [ ] Phase 5: Backtesting with VectorBT
- [ ] Phase 6: GEX/DIX, sentiment analysis

## Requirements

- Python 3.13+
- Moomoo OpenD running locally
- TradingView account (for alerts)
