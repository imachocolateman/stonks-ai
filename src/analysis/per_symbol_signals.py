"""Per-symbol streaming signal generator: RSI + EMA + VWAP + momentum → BUY/SELL/HOLD."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np
import talib

if TYPE_CHECKING:
    from src.data.bar_aggregator import Bar


class Action(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class SymbolSignal:
    symbol: str
    action: Action
    strength: float          # 0.0 - 1.0
    score: int               # signed net of votes
    triggers: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    price: float | None = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action.value,
            "strength": round(self.strength, 3),
            "score": self.score,
            "triggers": self.triggers,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
        }


# Configurable thresholds (could move to settings later)
RSI_OVERBOUGHT = 70.0
RSI_OVERSOLD = 30.0
MOMENTUM_BARS = 12          # 60 seconds at 5s bars
MOMENTUM_BULL_PCT = 0.10    # +0.10% over 12 bars = uptrend
MOMENTUM_BEAR_PCT = -0.10
MAX_SCORE = 5               # 5 binary votes: RSI, EMA9, EMA20, VWAP, momentum


def _vwap_of(bars: Sequence["Bar"]) -> float | None:
    if not bars:
        return None
    num = 0.0
    den = 0.0
    for b in bars:
        v = max(b.volume, 1)  # avoid zero-vol divide
        num += ((b.high + b.low + b.close) / 3) * v
        den += v
    return num / den if den > 0 else None


def generate_signal(symbol: str, bars: Sequence["Bar"]) -> SymbolSignal:
    """Pure scoring from a list of closed bars (oldest → newest).

    Returns HOLD with score=0 if there aren't enough bars yet for indicators.
    """
    n = len(bars)
    if n < 1:
        return SymbolSignal(symbol=symbol, action=Action.HOLD, strength=0.0, score=0)

    closes = np.array([b.close for b in bars], dtype=np.float64)
    last = float(closes[-1])
    triggers: list[str] = []
    votes: dict[str, int] = {}

    # ---- RSI(14) ----
    if n >= 15:
        rsi = talib.RSI(closes, timeperiod=14)
        last_rsi = float(rsi[-1])
        if not np.isnan(last_rsi):
            if last_rsi < RSI_OVERSOLD:
                votes["rsi"] = 1
                triggers.append(f"RSI oversold {last_rsi:.1f}")
            elif last_rsi > RSI_OVERBOUGHT:
                votes["rsi"] = -1
                triggers.append(f"RSI overbought {last_rsi:.1f}")
            else:
                votes["rsi"] = 0

    # Buffer to avoid hair-triggers in tight chop (0.05%)
    EMA_BUF = 1.0005

    # ---- Price vs 9-EMA ----
    if n >= 9:
        ema9 = talib.EMA(closes, timeperiod=9)
        last_ema9 = float(ema9[-1])
        if not np.isnan(last_ema9):
            if last > last_ema9 * EMA_BUF:
                votes["ema9"] = 1
                triggers.append(f"above 9-EMA ({last_ema9:.2f})")
            elif last < last_ema9 * (2 - EMA_BUF):
                votes["ema9"] = -1
                triggers.append(f"below 9-EMA ({last_ema9:.2f})")
            else:
                votes["ema9"] = 0

    # ---- Price vs 20-EMA ----
    if n >= 20:
        ema20 = talib.EMA(closes, timeperiod=20)
        last_ema20 = float(ema20[-1])
        if not np.isnan(last_ema20):
            if last > last_ema20 * EMA_BUF:
                votes["ema20"] = 1
            elif last < last_ema20 * (2 - EMA_BUF):
                votes["ema20"] = -1
            else:
                votes["ema20"] = 0

    # ---- Price vs VWAP ----
    vwap = _vwap_of(bars)
    if vwap is not None:
        if last > vwap * 1.0005:    # 0.05% buffer to avoid hair-trigger
            votes["vwap"] = 1
            triggers.append(f"above VWAP ({vwap:.2f})")
        elif last < vwap * 0.9995:
            votes["vwap"] = -1
            triggers.append(f"below VWAP ({vwap:.2f})")
        else:
            votes["vwap"] = 0

    # ---- 12-bar momentum ----
    if n >= MOMENTUM_BARS + 1:
        prev = float(closes[-MOMENTUM_BARS - 1])
        if prev > 0:
            mom_pct = (last / prev - 1) * 100
            if mom_pct > MOMENTUM_BULL_PCT:
                votes["momentum"] = 1
                triggers.append(f"+{mom_pct:.2f}% / 60s")
            elif mom_pct < MOMENTUM_BEAR_PCT:
                votes["momentum"] = -1
                triggers.append(f"{mom_pct:.2f}% / 60s")
            else:
                votes["momentum"] = 0

    score = sum(votes.values())

    if score >= 2:
        action = Action.BUY
    elif score <= -2:
        action = Action.SELL
    else:
        action = Action.HOLD

    strength = min(abs(score) / MAX_SCORE, 1.0)

    return SymbolSignal(
        symbol=symbol,
        action=action,
        strength=strength,
        score=score,
        triggers=triggers,
        price=last,
    )
