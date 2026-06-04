"""Derive synthetic SPX bars from streaming SPY bars.

SPX index is not available on Alpaca's IEX feed (or anywhere free for that
matter), but SPX = SPY × ratio where ratio ≈ 10.024. We compute the ratio
from a yfinance snapshot at startup, refresh every 5 minutes (drifts slowly
with dividends and creation/redemption), and emit a synthetic US.SPX bar
whenever SPY closes a bar.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.data.market_data import get_quote
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.data.bar_aggregator import Bar, BarAggregator

SPX_SYNTHETIC_SYMBOL = "US.SPX"
DEFAULT_RATIO = 10.024  # fallback if yfinance fails

BarCallback = Callable[[str, "Bar"], None]


class SPXSynthesizer:
    """Listens to SPY bar closes, emits synthetic SPX bars (SPY × ratio)."""

    def __init__(
        self,
        aggregator: "BarAggregator",
        source_symbol: str = "US.SPY",
        refresh_interval_seconds: int = 300,
        maxlen: int = 720,
    ):
        self.logger = get_logger(__name__)
        self.aggregator = aggregator
        self.source_symbol = source_symbol
        self.refresh_interval = refresh_interval_seconds
        self.ratio: float = DEFAULT_RATIO
        self._history: deque = deque(maxlen=maxlen)
        self._current: "Bar | None" = None
        self._callbacks: list[BarCallback] = []
        self._task: asyncio.Task | None = None
        self._running = False

    @property
    def symbol(self) -> str:
        return SPX_SYNTHETIC_SYMBOL

    def get_bars(self, n: int | None = None) -> list:
        bars = list(self._history)
        return bars[-n:] if n else bars

    def current_bar(self):
        return self._current

    def on_new_bar(self, callback: BarCallback) -> None:
        self._callbacks.append(callback)

    def start_monitoring(self) -> None:
        if self._running:
            return
        self._running = True
        self.aggregator.on_new_bar(self._on_source_bar)
        self._task = asyncio.create_task(self._refresh_loop())
        self.logger.info(
            f"SPXSynthesizer started (ratio={self.ratio:.4f}, source={self.source_symbol})"
        )

    def stop_monitoring(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self.logger.info("SPXSynthesizer stopped")

    def _on_source_bar(self, symbol: str, bar) -> None:
        if symbol != self.source_symbol:
            return
        from src.data.bar_aggregator import Bar

        synth = Bar(
            bucket_ts=bar.bucket_ts,
            open=bar.open * self.ratio,
            high=bar.high * self.ratio,
            low=bar.low * self.ratio,
            close=bar.close * self.ratio,
            volume=0,  # SPY share volume doesn't translate to SPX
            tick_count=bar.tick_count,
        )
        self._current = synth
        self._history.append(synth)
        for cb in self._callbacks:
            try:
                cb(self.symbol, synth)
            except Exception as e:
                self.logger.exception(f"SPX callback failed: {e}")

    async def _refresh_loop(self) -> None:
        # Initial pull to set the right ratio
        await self._refresh_ratio()
        while self._running:
            try:
                await asyncio.sleep(self.refresh_interval)
                if self._running:
                    await self._refresh_ratio()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning(f"Ratio refresh error: {e}")
                await asyncio.sleep(60)

    async def _refresh_ratio(self) -> None:
        spx = await asyncio.to_thread(get_quote, "^GSPC")
        spy = await asyncio.to_thread(get_quote, "SPY")
        if spx and spy and spy > 0:
            new_ratio = spx / spy
            if 9.5 < new_ratio < 10.5:  # sanity check
                if abs(new_ratio - self.ratio) > 0.001:
                    self.logger.info(
                        f"SPX/SPY ratio updated: {self.ratio:.4f} -> {new_ratio:.4f}"
                    )
                self.ratio = new_ratio
