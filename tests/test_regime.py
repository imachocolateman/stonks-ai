"""Unit tests for regime scoring logic."""

from src.analysis.regime import MarketRegime, RegimeInputs, classify_regime


def _all_bullish_inputs() -> RegimeInputs:
    return RegimeInputs(
        spy_price=760.0, spy_open=755.0,  # +0.66% — bullish
        spy_vwap=757.0,  # above
        spy_ema9=758.0, spy_ema20=756.0,
        qqq_price=745.0, qqq_open=738.0,  # +0.95% — outpacing SPY
        iwm_price=290.0, iwm_open=288.0,  # +0.69% — small cap risk-on
        igv_price=105.0, igv_open=104.0,  # +0.96%
        vix_level=13.5,  # <15 calm
        vix_recent_change=-2.0,  # falling fast
        xlf_price=51.5, xlf_open=51.0,  # +0.98%
        xle_price=56.0, xle_open=57.0,  # -1.75% (defensive selling = risk-on)
    )


def _all_bearish_inputs() -> RegimeInputs:
    return RegimeInputs(
        spy_price=750.0, spy_open=755.0,  # -0.66%
        spy_vwap=753.0,  # below
        spy_ema9=752.0, spy_ema20=754.0,  # both above
        qqq_price=730.0, qqq_open=738.0,  # -1.08%
        iwm_price=285.0, iwm_open=288.0,  # -1.04%
        igv_price=102.0, igv_open=104.0,  # -1.92%
        vix_level=22.5,  # >20 fear
        vix_recent_change=3.5,  # spiking
        xlf_price=50.5, xlf_open=51.0,  # -0.98%
        xle_price=58.0, xle_open=57.0,  # +1.75% (defensive buying)
    )


# ---- bullish path ----


def test_all_bullish_returns_bullish_regime():
    snap = classify_regime(_all_bullish_inputs())
    assert snap.regime == MarketRegime.BULLISH
    assert snap.score >= 4
    assert snap.confidence > 0
    assert all(v >= 0 for v in snap.breakdown.values())


def test_all_bearish_returns_bearish_regime():
    snap = classify_regime(_all_bearish_inputs())
    assert snap.regime == MarketRegime.BEARISH
    assert snap.score <= -4
    assert all(v <= 0 for v in snap.breakdown.values())


# ---- neutral / edge cases ----


def test_empty_inputs_return_neutral_with_zero_score():
    snap = classify_regime(RegimeInputs())
    assert snap.regime == MarketRegime.NEUTRAL
    assert snap.score == 0
    assert snap.breakdown == {}


def test_mixed_signals_return_neutral():
    inputs = RegimeInputs(
        spy_price=756.0, spy_open=755.0,  # +0.13% — neutral (not > +0.3%)
        spy_vwap=756.0, spy_ema9=755.5, spy_ema20=755.0,  # all above
        vix_level=18.0,  # in neutral zone
    )
    snap = classify_regime(inputs)
    # spy_vs_ema9, ema20, vwap = +3, intraday=0, vix_level=0 → score 3, just under threshold
    assert snap.regime == MarketRegime.NEUTRAL
    assert -4 < snap.score < 4


# ---- individual signal correctness ----


def test_vix_level_thresholds():
    # <15 = +1
    s1 = classify_regime(RegimeInputs(vix_level=12.0))
    assert s1.breakdown["vix_level"] == 1
    # 15-20 = 0
    s2 = classify_regime(RegimeInputs(vix_level=17.0))
    assert s2.breakdown["vix_level"] == 0
    # >20 = -1
    s3 = classify_regime(RegimeInputs(vix_level=25.0))
    assert s3.breakdown["vix_level"] == -1


def test_xle_inverted_signal_defensive_buying_is_bearish():
    """Energy outperforming = defensive tilt = bearish for the broader market."""
    inputs = RegimeInputs(xle_price=58.0, xle_open=57.0)  # +1.75%
    snap = classify_regime(inputs)
    assert snap.breakdown["xle_energy"] == -1


def test_spy_intraday_below_minus_03_pct_is_bearish():
    inputs = RegimeInputs(spy_price=752.0, spy_open=755.0)  # -0.40%
    snap = classify_regime(inputs)
    assert snap.breakdown["spy_intraday_ret"] == -1


def test_iwm_breadth_threshold():
    # iwm +0.5% with no other signals — should be +1 breadth
    inputs = RegimeInputs(iwm_price=290.0, iwm_open=288.5)
    snap = classify_regime(inputs)
    assert snap.breakdown["iwm_intraday"] == 1


def test_qqq_vs_spy_relative_strength():
    # QQQ outperforms SPY by >0.1% → +1
    inputs = RegimeInputs(
        spy_price=755.5, spy_open=755.0,  # +0.066%
        qqq_price=740.0, qqq_open=738.0,  # +0.271% — outperforms
    )
    snap = classify_regime(inputs)
    assert snap.breakdown["qqq_vs_spy"] == 1


def test_confidence_capped_at_one():
    """Even hypothetical perfect 12/12 stays at confidence=1.0."""
    snap = classify_regime(_all_bullish_inputs())
    assert 0 <= snap.confidence <= 1.0


def test_custom_thresholds_change_classification():
    inputs = _all_bullish_inputs()  # normally bullish at threshold=4
    # Raise threshold to 100 — same inputs now neutral
    snap = classify_regime(inputs, bullish_threshold=100, bearish_threshold=-100)
    assert snap.regime == MarketRegime.NEUTRAL


def test_to_dict_serializable():
    snap = classify_regime(_all_bullish_inputs())
    d = snap.to_dict()
    assert d["regime"] == "bullish"
    assert isinstance(d["breakdown"], dict)
    assert d["max_score"] == 12
    assert "timestamp" in d
