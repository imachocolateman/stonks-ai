"""Alpaca real-time WebSocket streaming provider.

Drop-in replacement for `MoomooClient.start_streaming` — exposes the same
sync `start_streaming(symbols, on_tick)` / `stop_streaming()` interface so
`TickSubscriber` works against either provider without changes.

Alpaca's SDK is async-native but `.run()` is blocking, so we spawn it in a
daemon thread. The async handler invokes the sync `on_tick` callback from
the streaming thread; `TickSubscriber` bridges back to the asyncio loop.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from alpaca.data.enums import DataFeed
from alpaca.data.live import StockDataStream

from src.utils.logger import get_logger

TickCallback = Callable[[dict[str, Any]], None]


class AlpacaStreamingProvider:
    """Wraps Alpaca's StockDataStream for use with TickSubscriber."""

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        feed: str = "iex",
    ):
        self.logger = get_logger(__name__)
        self._api_key = api_key
        self._secret_key = secret_key
        self._feed = DataFeed(feed)  # "iex" (free) or "sip" (paid)
        self._stream: StockDataStream | None = None
        self._thread: threading.Thread | None = None
        self._symbols: list[str] = []

    @staticmethod
    def _to_alpaca_symbol(s: str) -> str:
        """Strip Moomoo-style prefix. 'US.SPY' -> 'SPY'."""
        return s.split(".", 1)[1] if "." in s else s

    @staticmethod
    def _to_normalized_symbol(s: str) -> str:
        """Add Moomoo-style prefix for cross-provider consistency."""
        return f"US.{s}" if "." not in s else s

    def start_streaming(self, symbols: list[str], on_tick: TickCallback) -> bool:
        if not self._api_key or not self._secret_key:
            self.logger.error("Alpaca credentials missing - set ALPACA_API_KEY/ALPACA_API_SECRET")
            return False

        alpaca_symbols = [self._to_alpaca_symbol(s) for s in symbols]
        self._symbols = list(symbols)
        try:
            self._stream = StockDataStream(
                self._api_key, self._secret_key, feed=self._feed
            )
        except Exception as e:
            self.logger.error(f"Failed to create Alpaca stream: {e}")
            return False

        async def trade_handler(trade):
            try:
                on_tick({
                    "symbol": self._to_normalized_symbol(trade.symbol),
                    "price": float(trade.price),
                    "volume": int(getattr(trade, "size", 0) or 0),
                    "timestamp": trade.timestamp,
                    "raw": trade,
                })
            except Exception as e:
                self.logger.exception(f"trade_handler failed: {e}")

        self._stream.subscribe_trades(trade_handler, *alpaca_symbols)

        def runner():
            try:
                self._stream.run()
            except Exception as e:
                self.logger.exception(f"Alpaca stream thread crashed: {e}")

        self._thread = threading.Thread(target=runner, daemon=True, name="alpaca-stream")
        self._thread.start()
        self.logger.info(
            f"Alpaca streaming started ({self._feed.value}, {len(alpaca_symbols)} symbols: {alpaca_symbols})"
        )
        return True

    def stop_streaming(self) -> None:
        if self._stream is None:
            return
        try:
            # .stop() is the sync entry point; signals the internal async stop_ws()
            self._stream.stop()
            self.logger.info(f"Alpaca streaming stopped for {self._symbols}")
        except Exception as e:
            self.logger.warning(f"Stop streaming error: {e}")
        finally:
            self._stream = None
            self._symbols = []
