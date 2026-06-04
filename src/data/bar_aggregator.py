"""Aggregate streaming ticks into rolling OHLCV bars."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.data.tick_subscriber import TickSubscriber

BarCallback = Callable[[str, "Bar"], None]


@dataclass
class Bar:
    """OHLCV bar pinned to a fixed-interval bucket start time."""

    bucket_ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    tick_count: int = 0

    def to_dict(self) -> dict:
        return {
            "time": int(self.bucket_ts.timestamp()),  # Lightweight Charts format
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


def bucket_start(ts: datetime, interval_seconds: int) -> datetime:
    """Floor a timestamp to the nearest interval boundary (UTC)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    epoch = int(ts.timestamp())
    floored = (epoch // interval_seconds) * interval_seconds
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def update_bar(
    current: Bar | None,
    tick_price: float,
    tick_volume: int,
    tick_ts: datetime,
    interval_seconds: int,
) -> tuple[Bar, Bar | None]:
    """Pure aggregation step.

    Returns (active_bar, closed_bar) where closed_bar is non-None when the
    tick crosses an interval boundary (the previous bar just finished).
    """
    bucket = bucket_start(tick_ts, interval_seconds)

    if current is None:
        return (
            Bar(
                bucket_ts=bucket,
                open=tick_price,
                high=tick_price,
                low=tick_price,
                close=tick_price,
                volume=tick_volume,
                tick_count=1,
            ),
            None,
        )

    if bucket == current.bucket_ts:
        # same bucket — update in place
        current.high = max(current.high, tick_price)
        current.low = min(current.low, tick_price)
        current.close = tick_price
        current.volume += tick_volume
        current.tick_count += 1
        return current, None

    # rollover — current closes, new bar starts
    closed = current
    new_bar = Bar(
        bucket_ts=bucket,
        open=tick_price,
        high=tick_price,
        low=tick_price,
        close=tick_price,
        volume=tick_volume,
        tick_count=1,
    )
    return new_bar, closed


@dataclass
class _SymbolState:
    history: deque = field(default_factory=lambda: deque(maxlen=720))
    current: Bar | None = None


class BarAggregator:
    """Consumes ticks from TickSubscriber queues, builds rolling OHLCV bars.

    One asyncio consumer task per symbol. On bar close (interval rollover),
    appends the closed bar to history and fires `on_new_bar` callbacks.

    Default: 5-second bars, 720-bar history (~1 hour).
    """

    def __init__(
        self,
        tick_subscriber: "TickSubscriber",
        interval_seconds: int = 5,
        maxlen: int = 720,
    ):
        self.logger = get_logger(__name__)
        self.subscriber = tick_subscriber
        self.interval_seconds = interval_seconds
        self._states: dict[str, _SymbolState] = {
            s: _SymbolState(history=deque(maxlen=maxlen))
            for s in tick_subscriber.symbols
        }
        self._tasks: list[asyncio.Task] = []
        self._on_new_bar_callbacks: list[BarCallback] = []
        self._running = False

    def get_bars(self, symbol: str, n: int | None = None) -> list[Bar]:
        """Closed bars for symbol, most recent last."""
        state = self._states.get(symbol)
        if not state:
            return []
        bars = list(state.history)
        return bars[-n:] if n else bars

    def current_bar(self, symbol: str) -> Bar | None:
        """The in-progress bar (not yet closed)."""
        state = self._states.get(symbol)
        return state.current if state else None

    def on_new_bar(self, callback: BarCallback) -> None:
        """Register a callback fired when any symbol closes a bar."""
        self._on_new_bar_callbacks.append(callback)

    def start_monitoring(self) -> None:
        if self._running:
            return
        self._running = True
        for symbol in self.subscriber.symbols:
            task = asyncio.create_task(self._consume_loop(symbol))
            self._tasks.append(task)
        self.logger.info(
            f"BarAggregator started ({self.interval_seconds}s bars, "
            f"{len(self.subscriber.symbols)} symbols)"
        )

    def stop_monitoring(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        self.logger.info("BarAggregator stopped")

    async def _consume_loop(self, symbol: str) -> None:
        queue = self.subscriber.queue(symbol)
        state = self._states[symbol]
        while self._running:
            try:
                tick = await queue.get()
                price = tick.get("price")
                if price is None:
                    continue
                new_state, closed = update_bar(
                    state.current,
                    tick_price=float(price),
                    tick_volume=int(tick.get("volume", 0) or 0),
                    tick_ts=tick["timestamp"],
                    interval_seconds=self.interval_seconds,
                )
                state.current = new_state
                if closed is not None:
                    state.history.append(closed)
                    self._fire_new_bar(symbol, closed)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"Bar consume error for {symbol}: {e}")
                await asyncio.sleep(0.1)

    def _fire_new_bar(self, symbol: str, bar: Bar) -> None:
        for cb in self._on_new_bar_callbacks:
            try:
                cb(symbol, bar)
            except Exception as e:
                self.logger.exception(f"on_new_bar callback failed: {e}")
