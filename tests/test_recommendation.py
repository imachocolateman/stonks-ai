"""Unit tests for Recommendation combiner."""

from datetime import datetime, timedelta, timezone

from src.analysis.per_symbol_signals import Action
from src.analysis.recommendation import _conflicts, build_recommendation
from src.analysis.regime import (
    MarketRegime,
    RegimeInputs,
    RegimeSnapshot,
    classify_regime,
)
from src.data.bar_aggregator import Bar


def make_bars(closes):
    base = datetime(2026, 6, 1, 14, 30, tzinfo=timezone.utc)
    return [
        Bar(
            bucket_ts=base + timedelta(seconds=5 * i),
            open=c, high=c * 1.0002, low=c * 0.9998, close=c,
            volume=100, tick_count=5,
        )
        for i, c in enumerate(closes)
    ]


def bullish_regime_snapshot() -> RegimeSnapshot:
    return classify_regime(RegimeInputs(
        spy_price=760.0, spy_open=755.0, spy_vwap=757.0,
        spy_ema9=758.0, spy_ema20=756.0,
        qqq_price=745.0, qqq_open=738.0,
        iwm_price=290.0, iwm_open=288.0,
        igv_price=105.0, igv_open=104.0,
        vix_level=13.5,
    ))


# ---- _conflicts helper ----


def test_buy_signal_in_bearish_regime_conflicts():
    assert _conflicts(Action.BUY, MarketRegime.BEARISH) is True


def test_sell_signal_in_bullish_regime_conflicts():
    assert _conflicts(Action.SELL, MarketRegime.BULLISH) is True


def test_neutral_regime_never_conflicts():
    assert _conflicts(Action.BUY, MarketRegime.NEUTRAL) is False
    assert _conflicts(Action.SELL, MarketRegime.NEUTRAL) is False
    assert _conflicts(Action.HOLD, MarketRegime.NEUTRAL) is False


def test_aligned_signal_no_conflict():
    assert _conflicts(Action.BUY, MarketRegime.BULLISH) is False
    assert _conflicts(Action.SELL, MarketRegime.BEARISH) is False


def test_hold_signal_never_conflicts():
    assert _conflicts(Action.HOLD, MarketRegime.BULLISH) is False
    assert _conflicts(Action.HOLD, MarketRegime.BEARISH) is False


# ---- build_recommendation integration ----


def test_uptrend_in_bullish_regime_recommends_buy_no_conflict():
    bars = make_bars([750.0 + i * 0.5 for i in range(30)])
    rec = build_recommendation("US.SPY", bars, bullish_regime_snapshot())
    assert rec.signal.action == Action.BUY
    assert rec.regime == MarketRegime.BULLISH
    assert rec.conflicts_regime is False
    assert rec.price == 750.0 + 29 * 0.5


def test_downtrend_in_bullish_regime_flags_conflict():
    bars = make_bars([765.0 - i * 0.5 for i in range(30)])
    rec = build_recommendation("US.SPY", bars, bullish_regime_snapshot())
    assert rec.signal.action == Action.SELL
    assert rec.regime == MarketRegime.BULLISH
    assert rec.conflicts_regime is True


def test_recommendation_with_no_regime_snapshot_defaults_to_neutral():
    bars = make_bars([750.0 + i * 0.5 for i in range(30)])
    rec = build_recommendation("US.SPY", bars, None)
    assert rec.regime == MarketRegime.NEUTRAL
    assert rec.regime_score == 0
    assert rec.conflicts_regime is False


def test_recommendation_to_dict_includes_all_layers():
    bars = make_bars([750.0 + i * 0.5 for i in range(30)])
    rec = build_recommendation("US.SPY", bars, bullish_regime_snapshot())
    d = rec.to_dict()
    assert d["symbol"] == "US.SPY"
    assert d["regime"] == "bullish"
    assert "signal" in d
    assert d["signal"]["action"] == "BUY"
    assert d["opdte_play"] is None  # phase 4 placeholder
    assert d["llm_snippet"] is None
