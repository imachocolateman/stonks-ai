"""Slow yfinance poller for inputs Alpaca can't stream (indices, optional sectors).

Background asyncio task that polls a list of yfinance tickers every N seconds
and caches the latest quote. Used by RegimeMonitor for ^VIX, ^GSPC, sectors.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from src.data.market_data import get_quote
from src.utils.logger import get_logger
from src.utils.time_utils import is_trading_allowed


@dataclass
class SlowQuote:
    symbol: str
    price: float
    fetched_at: datetime


class SlowPoller:
    """Polls yfinance for a list of tickers on a fixed cadence. Cache-only."""

    def __init__(self, symbols: list[str], interval_seconds: int = 30):
        self.logger = get_logger(__name__)
        self.symbols = list(symbols)
        self.interval = interval_seconds
        self._cache: dict[str, SlowQuote] = {}
        self._task: asyncio.Task | None = None
        self._running = False

    def get(self, symbol: str) -> SlowQuote | None:
        return self._cache.get(symbol)

    def all_quotes(self) -> dict[str, SlowQuote]:
        return dict(self._cache)

    def start_monitoring(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        self.logger.info(
            f"SlowPoller started ({self.interval}s, {len(self.symbols)} symbols)"
        )

    def stop_monitoring(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self.logger.info("SlowPoller stopped")

    async def _loop(self) -> None:
        # Prime cache once on startup so consumers don't get None
        await self._refresh()
        while self._running:
            try:
                allowed, _ = is_trading_allowed()
                sleep_for = self.interval if allowed else max(self.interval * 4, 120)
                await asyncio.sleep(sleep_for)
                if self._running:
                    await self._refresh()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"SlowPoller loop error: {e}")
                await asyncio.sleep(5)

    async def _refresh(self) -> None:
        """Run yfinance calls off the event loop (they're sync/blocking)."""
        for sym in self.symbols:
            try:
                price = await asyncio.to_thread(get_quote, sym)
                if price is not None:
                    self._cache[sym] = SlowQuote(
                        symbol=sym,
                        price=price,
                        fetched_at=datetime.now(timezone.utc),
                    )
            except Exception as e:
                self.logger.warning(f"SlowPoller failed for {sym}: {e}")
