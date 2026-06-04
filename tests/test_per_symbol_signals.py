"""Unit tests for per-symbol signal scoring."""

from datetime import datetime, timedelta, timezone

from src.analysis.per_symbol_signals import Action, generate_signal
from src.data.bar_aggregator import Bar


def make_bars(closes: list[float]) -> list[Bar]:
    """Build a list of Bar objects from a sequence of close prices."""
    base = datetime(2026, 6, 1, 14, 30, 0, tzinfo=timezone.utc)
    bars = []
    for i, c in enumerate(closes):
        # Trivially fill OHL around close so volume math is sensible
        bars.append(Bar(
            bucket_ts=base + timedelta(seconds=5 * i),
            open=c, high=c * 1.0002, low=c * 0.9998, close=c,
            volume=100, tick_count=5,
        ))
    return bars


# ---- empty / insufficient data ----


def test_empty_bars_returns_hold_with_zero_score():
    s = generate_signal("US.SPY", [])
    assert s.action == Action.HOLD
    assert s.score == 0
    assert s.strength == 0.0


def test_one_bar_returns_hold_at_minimum():
    s = generate_signal("US.SPY", make_bars([755.0]))
    assert s.action == Action.HOLD
    # Only VWAP can fire on 1 bar, and price == vwap → 0
    assert s.score == 0


# ---- bullish trend ----


def test_steady_uptrend_returns_buy():
    # 30 bars rising from 750 to 765 — pure uptrend
    closes = [750.0 + i * 0.5 for i in range(30)]
    s = generate_signal("US.SPY", make_bars(closes))
    assert s.action == Action.BUY
    assert s.score >= 2
    # We expect at least: above EMA9, above EMA20, above VWAP, +momentum
    assert any("EMA" in t for t in s.triggers)


def test_steady_downtrend_returns_sell():
    closes = [765.0 - i * 0.5 for i in range(30)]
    s = generate_signal("US.SPY", make_bars(closes))
    assert s.action == Action.SELL
    assert s.score <= -2


# ---- RSI edge cases ----


def test_oversold_rsi_adds_bullish_vote_to_signal():
    # Big drop then flat — RSI ends very low
    closes = [800.0] * 5 + [770.0 - i * 0.1 for i in range(20)]
    s = generate_signal("US.SPY", make_bars(closes))
    # the RSI vote should be +1 (oversold), but trend is so down other votes are -1
    # net score depends, but RSI trigger string should appear
    triggers_blob = " ".join(s.triggers)
    assert "RSI" in triggers_blob


# ---- consolidation / chop ----


def test_flat_chop_returns_hold():
    # 30 bars oscillating tightly around 755 — no real trend
    closes = [755.0 + (0.05 if i % 2 == 0 else -0.05) for i in range(30)]
    s = generate_signal("US.SPY", make_bars(closes))
    assert s.action == Action.HOLD
    assert abs(s.score) < 2


# ---- price reported ----


def test_signal_reports_last_close_as_price():
    closes = [750.0 + i * 0.5 for i in range(25)]
    s = generate_signal("US.SPY", make_bars(closes))
    assert s.price == closes[-1]


def test_strength_normalized_zero_to_one():
    closes = [750.0 + i * 0.5 for i in range(30)]
    s = generate_signal("US.SPY", make_bars(closes))
    assert 0.0 <= s.strength <= 1.0


def test_to_dict_is_json_safe():
    closes = [755.0 + i * 0.1 for i in range(25)]
    s = generate_signal("US.QQQ", make_bars(closes))
    d = s.to_dict()
    assert d["symbol"] == "US.QQQ"
    assert d["action"] in ("BUY", "SELL", "HOLD")
    assert isinstance(d["triggers"], list)
    assert isinstance(d["score"], int)
