"""Recommendation combiner — fuses regime + per-symbol signal + (later) LLM + 0DTE."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.analysis.per_symbol_signals import Action, SymbolSignal, generate_signal
from src.analysis.regime import MarketRegime, RegimeSnapshot
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.data.bar_aggregator import Bar, BarAggregator
    from src.analysis.regime import RegimeMonitor
    from src.data.spx_synth import SPXSynthesizer


RecommendationCallback = Callable[["Recommendation"], None]


@dataclass
class Recommendation:
    symbol: str
    timestamp: datetime
    price: float | None
    signal: SymbolSignal
    regime: MarketRegime
    regime_confidence: float
    regime_score: int
    conflicts_regime: bool                # signal action vs regime mismatch
    llm_snippet: str | None = None        # Phase 4 fills this
    llm_updated_at: datetime | None = None
    opdte_play: dict | None = None        # Phase 4 fills this (TradeSuggestion serialized)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "signal": self.signal.to_dict(),
            "regime": self.regime.value,
            "regime_confidence": round(self.regime_confidence, 3),
            "regime_score": self.regime_score,
            "conflicts_regime": self.conflicts_regime,
            "llm_snippet": self.llm_snippet,
            "llm_updated_at": self.llm_updated_at.isoformat() if self.llm_updated_at else None,
            "opdte_play": self.opdte_play,
        }


def _conflicts(action: Action, regime: MarketRegime) -> bool:
    if regime == MarketRegime.NEUTRAL:
        return False
    if action == Action.BUY and regime == MarketRegime.BEARISH:
        return True
    if action == Action.SELL and regime == MarketRegime.BULLISH:
        return True
    return False


def build_recommendation(
    symbol: str,
    bars: list,
    regime_snapshot: RegimeSnapshot | None,
) -> Recommendation:
    """Pure: take inputs, return a Recommendation. Used by tests and the runtime."""
    signal = generate_signal(symbol, bars)
    regime = regime_snapshot.regime if regime_snapshot else MarketRegime.NEUTRAL
    return Recommendation(
        symbol=symbol,
        timestamp=datetime.now(timezone.utc),
        price=signal.price,
        signal=signal,
        regime=regime,
        regime_confidence=regime_snapshot.confidence if regime_snapshot else 0.0,
        regime_score=regime_snapshot.score if regime_snapshot else 0,
        conflicts_regime=_conflicts(signal.action, regime),
    )


@dataclass
class _SymbolSource:
    """Maps a symbol to its bar source (aggregator or spx_synth)."""

    get_bars: Callable[[], list]


class Recommender:
    """Fires a Recommendation per closed bar, per tracked symbol.

    Wires onto BarAggregator + SPXSynthesizer + RegimeMonitor. On each new bar
    closing, builds a recommendation, fans out to listeners (CLI, broadcaster).
    """

    def __init__(
        self,
        aggregator: "BarAggregator",
        regime_monitor: "RegimeMonitor",
        spx_synth: "SPXSynthesizer | None" = None,
    ):
        self.logger = get_logger(__name__)
        self.aggregator = aggregator
        self.regime_monitor = regime_monitor
        self.spx_synth = spx_synth
        self._latest: dict[str, Recommendation] = {}
        self._callbacks: list[RecommendationCallback] = []
        self._sources: dict[str, _SymbolSource] = self._build_sources()
        self._running = False

    def _build_sources(self) -> dict[str, _SymbolSource]:
        sources: dict[str, _SymbolSource] = {}
        for s in self.aggregator.subscriber.symbols:
            sources[s] = _SymbolSource(get_bars=lambda sym=s: self.aggregator.get_bars(sym))
        if self.spx_synth:
            sym = self.spx_synth.symbol
            sources[sym] = _SymbolSource(get_bars=self.spx_synth.get_bars)
        return sources

    def get_latest(self, symbol: str) -> Recommendation | None:
        return self._latest.get(symbol)

    def all_latest(self) -> dict[str, Recommendation]:
        return dict(self._latest)

    def on_recommendation(self, cb: RecommendationCallback) -> None:
        self._callbacks.append(cb)

    def start_monitoring(self) -> None:
        if self._running:
            return
        self._running = True
        self.aggregator.on_new_bar(self._on_bar)
        if self.spx_synth:
            self.spx_synth.on_new_bar(self._on_bar)
        self.logger.info(
            f"Recommender started ({len(self._sources)} symbols)"
        )

    def stop_monitoring(self) -> None:
        self._running = False
        self.logger.info("Recommender stopped")

    def _on_bar(self, symbol: str, _bar: "Bar") -> None:
        if not self._running or symbol not in self._sources:
            return
        try:
            bars = self._sources[symbol].get_bars()
            rec = build_recommendation(
                symbol=symbol,
                bars=bars,
                regime_snapshot=self.regime_monitor.current_snapshot,
            )
            self._latest[symbol] = rec
            for cb in self._callbacks:
                try:
                    cb(rec)
                except Exception as e:
                    self.logger.exception(f"recommendation cb failed: {e}")
        except Exception as e:
            self.logger.exception(f"recommendation build failed for {symbol}: {e}")
