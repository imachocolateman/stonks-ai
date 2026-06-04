"""Market regime classifier: aggregates SPY/breadth/VIX/sector inputs to BULL/BEAR/NEUTRAL."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from src.config import get_settings
from src.utils.logger import get_logger
from src.utils.time_utils import is_trading_allowed

if TYPE_CHECKING:
    from src.data.bar_aggregator import BarAggregator
    from src.data.slow_poller import SlowPoller
    from src.data.spx_synth import SPXSynthesizer


class MarketRegime(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# Pure scoring layer (no side effects, fully testable)
# ---------------------------------------------------------------------------


@dataclass
class RegimeInputs:
    """Inputs to the regime scorer. Missing fields contribute 0 (no signal)."""

    spy_price: float | None = None
    spy_open: float | None = None
    spy_vwap: float | None = None
    spy_ema9: float | None = None
    spy_ema20: float | None = None

    qqq_price: float | None = None
    qqq_open: float | None = None
    iwm_price: float | None = None
    iwm_open: float | None = None
    igv_price: float | None = None
    igv_open: float | None = None

    vix_level: float | None = None
    vix_recent_change: float | None = None  # %, last ~5 min via VIXY stream

    xlf_price: float | None = None
    xlf_open: float | None = None
    xle_price: float | None = None
    xle_open: float | None = None

    iv_skew: float | None = None  # placeholder, populated later from Moomoo options


@dataclass
class RegimeSnapshot:
    regime: MarketRegime
    score: int
    confidence: float
    breakdown: dict[str, int]
    inputs: RegimeInputs
    timestamp: datetime
    max_score: int = 12

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "score": self.score,
            "max_score": self.max_score,
            "confidence": round(self.confidence, 3),
            "breakdown": self.breakdown,
            "timestamp": self.timestamp.isoformat(),
        }


def _pct(price: float | None, open_: float | None) -> float | None:
    if price is None or open_ is None or open_ == 0:
        return None
    return (price / open_ - 1) * 100


def classify_regime(
    inputs: RegimeInputs,
    bullish_threshold: int = 4,
    bearish_threshold: int = -4,
) -> RegimeSnapshot:
    """Pure scoring: 12 signals, each +1/0/-1. Missing inputs contribute 0."""
    b: dict[str, int] = {}

    # ----- Price action (4) - all use SPY as SPX proxy -----
    if inputs.spy_price is not None and inputs.spy_ema9 is not None:
        b["spy_vs_ema9"] = 1 if inputs.spy_price > inputs.spy_ema9 else -1
    if inputs.spy_price is not None and inputs.spy_ema20 is not None:
        b["spy_vs_ema20"] = 1 if inputs.spy_price > inputs.spy_ema20 else -1
    if inputs.spy_price is not None and inputs.spy_vwap is not None:
        b["spy_vs_vwap"] = 1 if inputs.spy_price > inputs.spy_vwap else -1
    spy_ret = _pct(inputs.spy_price, inputs.spy_open)
    if spy_ret is not None:
        b["spy_intraday_ret"] = 1 if spy_ret > 0.3 else (-1 if spy_ret < -0.3 else 0)

    # ----- Volatility (2) -----
    if inputs.vix_level is not None:
        # <15 = bullish (calm), 15-20 = neutral, >20 = bearish (fear)
        b["vix_level"] = (
            1 if inputs.vix_level < 15 else (-1 if inputs.vix_level > 20 else 0)
        )
    if inputs.vix_recent_change is not None:
        # rising VIX = bearish, falling = bullish (threshold 1%)
        b["vix_trend"] = (
            -1 if inputs.vix_recent_change > 1.0
            else (1 if inputs.vix_recent_change < -1.0 else 0)
        )

    # ----- Breadth (2) -----
    qqq_ret = _pct(inputs.qqq_price, inputs.qqq_open)
    if qqq_ret is not None and spy_ret is not None:
        # tech leading or lagging SPX
        diff = qqq_ret - spy_ret
        b["qqq_vs_spy"] = 1 if diff > 0.1 else (-1 if diff < -0.1 else 0)
    iwm_ret = _pct(inputs.iwm_price, inputs.iwm_open)
    if iwm_ret is not None:
        # small caps = risk-on proxy
        b["iwm_intraday"] = 1 if iwm_ret > 0.2 else (-1 if iwm_ret < -0.2 else 0)

    # ----- Positioning (1) - placeholder -----
    if inputs.iv_skew is not None:
        # positive = call demand > put demand = bullish chase
        b["iv_skew"] = 1 if inputs.iv_skew > 0.02 else (-1 if inputs.iv_skew < -0.02 else 0)

    # ----- Sectors (3) -----
    igv_ret = _pct(inputs.igv_price, inputs.igv_open)
    if igv_ret is not None:
        b["igv_software"] = 1 if igv_ret > 0.2 else (-1 if igv_ret < -0.2 else 0)
    xlf_ret = _pct(inputs.xlf_price, inputs.xlf_open)
    if xlf_ret is not None:
        b["xlf_financials"] = 1 if xlf_ret > 0.2 else (-1 if xlf_ret < -0.2 else 0)
    xle_ret = _pct(inputs.xle_price, inputs.xle_open)
    if xle_ret is not None:
        # defensive tilt: XLE outperforming = bearish for risk-on
        b["xle_energy"] = -1 if xle_ret > 0.5 else (1 if xle_ret < -0.5 else 0)

    score = sum(b.values())

    if score >= bullish_threshold:
        regime = MarketRegime.BULLISH
    elif score <= bearish_threshold:
        regime = MarketRegime.BEARISH
    else:
        regime = MarketRegime.NEUTRAL

    return RegimeSnapshot(
        regime=regime,
        score=score,
        confidence=min(abs(score) / 12, 1.0),
        breakdown=b,
        inputs=inputs,
        timestamp=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Async monitor — assembles inputs from streaming + slow poller, runs every 30s
# ---------------------------------------------------------------------------


RegimeCallback = Callable[[RegimeSnapshot], None]


class RegimeMonitor:
    """Background task that polls inputs every N seconds and re-classifies."""

    def __init__(
        self,
        aggregator: "BarAggregator",
        slow_poller: "SlowPoller",
        spx_synth: "SPXSynthesizer | None" = None,
        interval_seconds: int = 30,
    ):
        self.logger = get_logger(__name__)
        self.settings = get_settings()
        self.aggregator = aggregator
        self.slow_poller = slow_poller
        self.spx_synth = spx_synth
        self.interval = interval_seconds
        self._snapshot: RegimeSnapshot | None = None
        self._last_regime: MarketRegime | None = None
        self._callbacks: list[RegimeCallback] = []
        self._task: asyncio.Task | None = None
        self._running = False

    @property
    def current_snapshot(self) -> RegimeSnapshot | None:
        return self._snapshot

    def on_transition(self, cb: RegimeCallback) -> None:
        self._callbacks.append(cb)

    def start_monitoring(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        self.logger.info(f"RegimeMonitor started ({self.interval}s)")

    def stop_monitoring(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self.logger.info("RegimeMonitor stopped")

    async def _loop(self) -> None:
        # Wait briefly for first bars and slow_poller cache to populate
        await asyncio.sleep(3)
        while self._running:
            try:
                allowed, _ = is_trading_allowed()
                if not allowed:
                    await asyncio.sleep(60)
                    continue
                snapshot = self.refresh()
                if snapshot:
                    prev = self._last_regime
                    self._snapshot = snapshot
                    if prev is not None and prev != snapshot.regime:
                        self.logger.info(
                            f"REGIME TRANSITION: {prev.value} -> {snapshot.regime.value} "
                            f"(score={snapshot.score}, confidence={snapshot.confidence:.2f})"
                        )
                        for cb in self._callbacks:
                            try:
                                cb(snapshot)
                            except Exception as e:
                                self.logger.exception(f"transition cb failed: {e}")
                    self._last_regime = snapshot.regime
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.exception(f"RegimeMonitor loop error: {e}")
                await asyncio.sleep(5)

    def refresh(self) -> RegimeSnapshot | None:
        """Assemble inputs from current state, classify, return snapshot."""
        inputs = self._gather_inputs()
        if inputs is None:
            return None
        return classify_regime(
            inputs,
            bullish_threshold=self.settings.regime_bullish_threshold,
            bearish_threshold=self.settings.regime_bearish_threshold,
        )

    def _gather_inputs(self) -> RegimeInputs | None:
        """Pull current values from aggregator + slow poller. None if too early."""
        spy_bars = self.aggregator.get_bars("US.SPY")
        if not spy_bars:
            return None  # too early, no data yet

        spy_bar = spy_bars[-1]
        spy_open = spy_bars[0].open
        spy_price = spy_bar.close

        # EMAs from recent SPY closes (talib needs np arrays of float64)
        spy_ema9 = self._ema([b.close for b in spy_bars[-30:]], 9)
        spy_ema20 = self._ema([b.close for b in spy_bars[-60:]], 20)

        # VWAP from full day's bars
        spy_vwap = self._vwap(spy_bars)

        # Breadth from streaming aggregator
        qqq_bars = self.aggregator.get_bars("US.QQQ")
        qqq_price = qqq_bars[-1].close if qqq_bars else None
        qqq_open = qqq_bars[0].open if qqq_bars else None

        iwm_bars = self.aggregator.get_bars("US.IWM")
        iwm_price = iwm_bars[-1].close if iwm_bars else None
        iwm_open = iwm_bars[0].open if iwm_bars else None

        igv_bars = self.aggregator.get_bars("US.IGV")
        igv_price = igv_bars[-1].close if igv_bars else None
        igv_open = igv_bars[0].open if igv_bars else None

        # VIXY for trend direction
        vixy_bars = self.aggregator.get_bars("US.VIXY")
        vix_recent_change = None
        if vixy_bars and len(vixy_bars) >= 5:
            recent5 = vixy_bars[-5:]
            vix_recent_change = (recent5[-1].close / recent5[0].close - 1) * 100

        # VIX spot from slow poller
        vix_quote = self.slow_poller.get("^VIX")
        vix_level = vix_quote.price if vix_quote else None

        # Sector spot from slow poller (no intraday open captured — would need history)
        # For v1, skip XLE/XLF unless slow poller stores open too. Leave None.

        return RegimeInputs(
            spy_price=spy_price,
            spy_open=spy_open,
            spy_vwap=spy_vwap,
            spy_ema9=spy_ema9,
            spy_ema20=spy_ema20,
            qqq_price=qqq_price,
            qqq_open=qqq_open,
            iwm_price=iwm_price,
            iwm_open=iwm_open,
            igv_price=igv_price,
            igv_open=igv_open,
            vix_level=vix_level,
            vix_recent_change=vix_recent_change,
        )

    @staticmethod
    def _ema(closes: list[float], span: int) -> float | None:
        if len(closes) < span:
            return None
        alpha = 2 / (span + 1)
        ema = closes[0]
        for c in closes[1:]:
            ema = alpha * c + (1 - alpha) * ema
        return ema

    @staticmethod
    def _vwap(bars) -> float | None:
        if not bars:
            return None
        num = sum(((b.high + b.low + b.close) / 3) * max(b.volume, 1) for b in bars)
        den = sum(max(b.volume, 1) for b in bars)
        return num / den if den > 0 else None
