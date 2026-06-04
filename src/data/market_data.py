"""Generic yfinance wrappers for any ticker.

Used by regime monitor (VIX, sector ETFs), per-symbol signals, and pre-market
analysis. Kept separate from MoomooClient so it's not tangled with Moomoo state.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import yfinance as yf

from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_quote(ticker: str) -> float | None:
    """Latest price for any yfinance-supported ticker (^GSPC, ^VIX, QQQ, etc.)."""
    try:
        tk = yf.Ticker(ticker)
        price = tk.fast_info.get("lastPrice")
        if price:
            return float(price)
        hist = tk.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        logger.error(f"No price data for {ticker}")
        return None
    except Exception as e:
        logger.error(f"get_quote({ticker}) failed: {e}")
        return None


def get_intraday_bars(
    ticker: str,
    period: str = "1d",
    interval: str = "1m",
) -> Any:
    """Pandas DataFrame of OHLCV bars. Returns None on failure."""
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period=period, interval=interval)
        if hist.empty:
            logger.warning(f"No intraday data for {ticker} ({period}/{interval})")
            return None
        return hist
    except Exception as e:
        logger.error(f"get_intraday_bars({ticker}) failed: {e}")
        return None


def get_ohlcv_arrays(
    ticker: str,
    period: str = "1d",
    interval: str = "1m",
) -> dict | None:
    """Numpy arrays for TA-Lib calculations. Returns {open, high, low, close, volume, timestamp}."""
    hist = get_intraday_bars(ticker, period=period, interval=interval)
    if hist is None or hist.empty:
        return None
    return {
        "open": hist["Open"].values.astype(np.float64),
        "high": hist["High"].values.astype(np.float64),
        "low": hist["Low"].values.astype(np.float64),
        "close": hist["Close"].values.astype(np.float64),
        "volume": hist["Volume"].values.astype(np.float64),
        "timestamp": hist.index,
    }
