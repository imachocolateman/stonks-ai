"""Bridge Moomoo's thread-based streaming callback into asyncio queues."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.data.moomoo_client import MoomooClient


class TickSubscriber:
    """Subscribes to Moomoo streaming and exposes per-symbol asyncio queues.

    The Moomoo SDK invokes the tick callback from a background thread. This class
    bridges those ticks into the asyncio event loop using `run_coroutine_threadsafe`
    so async consumers (BarAggregator, etc.) can `await queue.get()`.
    """

    def __init__(
        self,
        moomoo_client: "MoomooClient",
        symbols: list[str],
        queue_maxsize: int = 1000,
    ):
        self.logger = get_logger(__name__)
        self.client = moomoo_client
        self.symbols = list(symbols)
        self._queues: dict[str, asyncio.Queue] = {
            s: asyncio.Queue(maxsize=queue_maxsize) for s in self.symbols
        }
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False
        self._dropped: dict[str, int] = {s: 0 for s in self.symbols}

    def queue(self, symbol: str) -> asyncio.Queue:
        """Get the asyncio.Queue for a symbol (created at init)."""
        return self._queues[symbol]

    def stats(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "symbols": self.symbols,
            "dropped": dict(self._dropped),
            "queue_sizes": {s: q.qsize() for s, q in self._queues.items()},
        }

    def start_monitoring(self) -> None:
        """Start streaming. Must be called from inside the asyncio event loop."""
        if self._running:
            return
        self._loop = asyncio.get_running_loop()
        ok = self.client.start_streaming(self.symbols, self._on_tick_threadsafe)
        if not ok:
            self.logger.error("TickSubscriber failed to start streaming")
            return
        self._running = True
        self.logger.info(f"TickSubscriber started ({len(self.symbols)} symbols)")

    def stop_monitoring(self) -> None:
        if not self._running:
            return
        self.client.stop_streaming()
        self._running = False
        self.logger.info("TickSubscriber stopped")

    def _on_tick_threadsafe(self, tick: dict[str, Any]) -> None:
        """Called from Moomoo SDK background thread - dispatch onto async loop."""
        symbol = tick.get("symbol")
        if not symbol or symbol not in self._queues:
            return
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        loop.call_soon_threadsafe(self._enqueue, symbol, tick)

    def _enqueue(self, symbol: str, tick: dict[str, Any]) -> None:
        """Runs on the asyncio loop. Non-blocking put; drops if queue full."""
        q = self._queues[symbol]
        try:
            q.put_nowait(tick)
        except asyncio.QueueFull:
            self._dropped[symbol] += 1
            if self._dropped[symbol] % 100 == 1:
                self.logger.warning(
                    f"Tick queue full for {symbol} (dropped {self._dropped[symbol]} total)"
                )
